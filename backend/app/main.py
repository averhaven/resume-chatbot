from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import get_settings, validate_settings
from app.core.context import set_session_id
from app.core.logger import get_logger, setup_logging
from app.core.rate_limit import WebSocketRateLimiter
from app.db.session import DatabaseManager
from app.models.websocket import (
    ErrorMessage,
    QuestionMessage,
    ResponseMessage,
    SystemMessage,
)
from app.services.conversation_db import DatabaseConversationManager
from app.services.llm_client import (
    LLMAPIError,
    LLMError,
    LLMRateLimitError,
    OpenRouterClient,
    create_llm_client,
)
from app.services.prompts import build_prompt, prune_conversation_history
from app.services.resume_loader import ResumeContext
from app.services.token_counter import TokenCounter

logger = get_logger(__name__)


async def send_error_response(
    websocket: WebSocket,
    error_message: str,
    error_code: str,
    log_level: str = "error",
) -> None:
    """Send error response via WebSocket and log it.

    Args:
        websocket: WebSocket connection
        error_message: Error message to send to client
        error_code: Error code identifier
        log_level: Logging level - "error", "warning", or "info"
    """
    error = ErrorMessage(error=error_message, code=error_code)
    await websocket.send_json(error.model_dump())

    log_func = getattr(logger, log_level, logger.error)
    log_func(f"{error_code}: {error_message}")


async def process_question(
    question: str,
    system_prompt: str,
    system_prompt_tokens: int,
    conversation_manager: DatabaseConversationManager,
    llm_client: OpenRouterClient,
    token_counter: TokenCounter,
) -> str:
    """Process a user question and generate LLM response.

    Args:
        question: User's question text
        system_prompt: Pre-built system prompt with resume context
        system_prompt_tokens: Token count of the system prompt
        conversation_manager: Conversation manager instance
        llm_client: LLM client instance
        token_counter: Token counter instance for pruning

    Returns:
        LLM response text

    Note:
        Caller must commit the database session.
    """
    settings = get_settings()

    # Get history and prune if needed
    history = await conversation_manager.get_conversation()

    # Prune history to fit within token limits
    pruned_history, tokens_removed = prune_conversation_history(
        history=history,
        token_counter=token_counter,
        system_tokens=system_prompt_tokens,
        max_tokens=settings.max_context_tokens,
        min_exchanges=settings.min_conversation_exchanges,
        response_reserve=settings.max_response_tokens,
    )

    if tokens_removed > 0:
        logger.info(f"Pruned {tokens_removed} tokens from conversation history")

    messages = build_prompt(system_prompt, pruned_history, question)

    logger.info("Calling LLM API")
    response_text = await llm_client.call_llm(messages)

    await conversation_manager.add_message("user", question)
    await conversation_manager.add_message("assistant", response_text)

    return response_text


async def handle_websocket_messages(
    websocket: WebSocket,
    conversation_manager: DatabaseConversationManager,
    system_prompt: str,
    system_prompt_tokens: int,
    llm_client: OpenRouterClient,
    rate_limiter: WebSocketRateLimiter,
    session_id: str,
    token_counter: TokenCounter,
) -> None:
    """Handle WebSocket message loop.

    Extracted from websocket_endpoint to eliminate code duplication.
    Receives questions, processes them, and sends responses until connection closes.

    Args:
        websocket: WebSocket connection
        conversation_manager: Database-backed conversation manager
        system_prompt: Pre-built system prompt with resume context
        system_prompt_tokens: Token count of the system prompt
        llm_client: LLM client for API calls
        rate_limiter: Rate limiter instance
        session_id: Session ID for rate limiting
        token_counter: Token counter for pruning
    """
    while True:
        data = await websocket.receive_json()

        try:
            # Check rate limit before processing
            if not await rate_limiter.is_allowed(session_id):
                await send_error_response(
                    websocket,
                    "Too many requests. Please wait a moment before sending more messages.",
                    "RATE_LIMIT_EXCEEDED",
                    "warning",
                )
                continue

            question_msg = QuestionMessage(**data)
            logger.info("Received question")

            response_text = await process_question(
                question_msg.question,
                system_prompt,
                system_prompt_tokens,
                conversation_manager,
                llm_client,
                token_counter,
            )

            # Commit database transaction
            await conversation_manager.session.commit()

            response = ResponseMessage(response=response_text)
            await websocket.send_json(response.model_dump())
            logger.info(f"Sent response ({len(response_text)} chars)")

        except ValidationError as e:
            await send_error_response(
                websocket,
                f"Invalid message format: {e!s}",
                "VALIDATION_ERROR",
                "warning",
            )

        except LLMRateLimitError as e:
            await send_error_response(
                websocket,
                f"Rate limit exceeded: {e!s}. Please try again later.",
                "RATE_LIMIT",
                "warning",
            )

        except LLMAPIError as e:
            await send_error_response(websocket, f"API error: {e!s}", "API_ERROR")

        except LLMError as e:
            await send_error_response(websocket, f"Service error: {e!s}", "LLM_ERROR")

        except OperationalError as e:
            await send_error_response(
                websocket,
                "Database connection error. Please try again.",
                "DATABASE_ERROR",
            )
            logger.error(f"Database connection error: {e}", exc_info=True)

        except SQLAlchemyError as e:
            await send_error_response(
                websocket,
                "Database error. Please try again.",
                "DATABASE_ERROR",
            )
            logger.error(f"Database error: {e}", exc_info=True)

        except Exception as e:
            await send_error_response(
                websocket,
                "An unexpected error occurred. Please try again.",
                "INTERNAL_ERROR",
            )
            logger.error(f"Unexpected error details: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    setup_logging()
    logger.info("Application starting up")

    # Validate configuration before proceeding
    validate_settings()
    logger.info("Configuration validated successfully")

    settings = get_settings()

    # Initialize database
    db_manager = DatabaseManager()
    db_manager.initialize(settings)
    app.state.db_manager = db_manager

    # Initialize token counter
    app.state.token_counter = TokenCounter()
    logger.info("Token counter initialized")

    # Load resume and build system prompt
    resume_path = Path(settings.resume_path)
    if not resume_path.is_absolute():
        resume_path = Path(__file__).parent.parent / resume_path

    app.state.resume_context = ResumeContext.from_file(
        resume_path, app.state.token_counter
    )
    logger.info(f"Resume loaded from {resume_path}")

    # Initialize rate limiter
    app.state.rate_limiter = WebSocketRateLimiter(
        settings.rate_limit_requests_per_minute
    )
    logger.info(
        f"Rate limiter initialized: {settings.rate_limit_requests_per_minute} req/min"
    )

    yield

    # Shutdown cleanup
    await db_manager.close()
    logger.info("Application shutting down")


app = FastAPI(
    title="Resume Chatbot API",
    description="A chatbot that answers questions about your resume using direct LLM calls",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.debug("Health check requested")
    return {"status": "healthy"}


@app.get("/", response_class=HTMLResponse)
async def get_chat_interface():
    """Serve simple HTML chat interface for testing the WebSocket chatbot."""
    return """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Resume Chatbot</title>
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    padding: 20px;
                }
                .container {
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    width: 100%;
                    max-width: 800px;
                    height: 600px;
                    display: flex;
                    flex-direction: column;
                }
                .header {
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border-radius: 12px 12px 0 0;
                    text-align: center;
                }
                .header h1 {
                    font-size: 24px;
                    font-weight: 600;
                }
                .header p {
                    font-size: 14px;
                    opacity: 0.9;
                    margin-top: 5px;
                }
                #messages {
                    flex: 1;
                    overflow-y: auto;
                    padding: 20px;
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                }
                .message {
                    padding: 12px 16px;
                    border-radius: 8px;
                    max-width: 80%;
                    word-wrap: break-word;
                    animation: fadeIn 0.3s;
                }
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                .user-message {
                    background: #667eea;
                    color: white;
                    align-self: flex-end;
                    margin-left: auto;
                }
                .assistant-message {
                    background: #f3f4f6;
                    color: #1f2937;
                    align-self: flex-start;
                }
                .system-message {
                    background: #dbeafe;
                    color: #1e40af;
                    align-self: center;
                    text-align: center;
                    font-size: 14px;
                    font-style: italic;
                }
                .error-message {
                    background: #fee2e2;
                    color: #991b1b;
                    align-self: center;
                    text-align: center;
                    font-size: 14px;
                }
                .input-area {
                    padding: 20px;
                    border-top: 1px solid #e5e7eb;
                    display: flex;
                    gap: 10px;
                }
                #messageInput {
                    flex: 1;
                    padding: 12px;
                    border: 2px solid #e5e7eb;
                    border-radius: 8px;
                    font-size: 14px;
                    outline: none;
                    transition: border-color 0.2s;
                }
                #messageInput:focus {
                    border-color: #667eea;
                }
                button {
                    padding: 12px 24px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: transform 0.2s, box-shadow 0.2s;
                }
                button:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
                }
                button:active {
                    transform: translateY(0);
                }
                button:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                    transform: none;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Resume Chatbot</h1>
                    <p>Ask me anything about the resume</p>
                </div>
                <div id="messages"></div>
                <div class="input-area">
                    <input
                        type="text"
                        id="messageInput"
                        placeholder="Ask a question about the resume..."
                        autocomplete="off"
                    />
                    <button onclick="sendMessage()" id="sendButton">Send</button>
                </div>
            </div>

            <script>
                const ws = new WebSocket("ws://localhost:8000/ws");
                const messagesDiv = document.getElementById("messages");
                const messageInput = document.getElementById("messageInput");
                const sendButton = document.getElementById("sendButton");

                ws.onopen = function(event) {
                    console.log("WebSocket connected");
                };

                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);

                    if (data.type === "system") {
                        addMessage(data.message, "system-message");
                    } else if (data.type === "response") {
                        addMessage(data.response, "assistant-message");
                    } else if (data.type === "error") {
                        addMessage(`Error: ${data.error}`, "error-message");
                    }

                    enableInput();
                };

                ws.onerror = function(error) {
                    console.error("WebSocket error:", error);
                    addMessage("Connection error. Please refresh the page.", "error-message");
                    enableInput();
                };

                ws.onclose = function(event) {
                    console.log("WebSocket disconnected");
                    addMessage("Disconnected. Please refresh the page.", "error-message");
                    disableInput();
                };

                function addMessage(text, className) {
                    const messageDiv = document.createElement("div");
                    messageDiv.className = `message ${className}`;
                    messageDiv.textContent = text;
                    messagesDiv.appendChild(messageDiv);
                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                }

                function sendMessage() {
                    const message = messageInput.value.trim();
                    if (message === "" || ws.readyState !== WebSocket.OPEN) {
                        return;
                    }

                    // Display user message
                    addMessage(message, "user-message");

                    // Send to WebSocket
                    ws.send(JSON.stringify({
                        type: "question",
                        question: message
                    }));

                    // Clear input and disable until response
                    messageInput.value = "";
                    disableInput();
                }

                function disableInput() {
                    messageInput.disabled = true;
                    sendButton.disabled = true;
                }

                function enableInput() {
                    messageInput.disabled = false;
                    sendButton.disabled = false;
                    messageInput.focus();
                }

                // Send message on Enter key
                messageInput.addEventListener("keypress", function(event) {
                    if (event.key === "Enter") {
                        sendMessage();
                    }
                });

                // Focus input on load
                messageInput.focus();
            </script>
        </body>
    </html>
    """


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str | None = None):
    """WebSocket endpoint for resume chatbot conversation.

    Handles real-time chat interactions with database persistence:
    1. Receives user questions (JSON: {"type": "question", "question": "..."})
    2. Builds prompts with resume context and conversation history
    3. Calls LLM API to generate responses
    4. Sends responses back (JSON: {"type": "response", "response": "..."})
    5. Persists conversation history to PostgreSQL database

    Args:
        websocket: WebSocket connection
        session_id: Optional session ID for resuming conversations
    """
    await websocket.accept()

    logger.info(f"Client connected (session_id param: {session_id})")

    resume_context: ResumeContext = websocket.app.state.resume_context

    welcome = SystemMessage(
        message="Connected! Ready to answer questions about the resume."
    )
    await websocket.send_json(welcome.model_dump())

    # Track the actual session_id (may be generated by manager)
    actual_session_id = session_id

    try:
        # Use database-backed conversation manager
        db_manager: DatabaseManager = websocket.app.state.db_manager
        token_counter: TokenCounter = websocket.app.state.token_counter
        async with db_manager.get_session() as db_session:
            conversation_manager = DatabaseConversationManager(db_session, session_id)
            # Get the actual session_id (generated if not provided)
            actual_session_id = conversation_manager.session_id
            # Set session_id in context for logging
            set_session_id(actual_session_id)
            logger.info(f"Session established: {actual_session_id}")

            rate_limiter: WebSocketRateLimiter = websocket.app.state.rate_limiter

            async with create_llm_client() as llm_client:
                await handle_websocket_messages(
                    websocket,
                    conversation_manager,
                    resume_context.system_prompt,
                    resume_context.system_prompt_tokens,
                    llm_client,
                    rate_limiter,
                    actual_session_id,
                    token_counter,
                )

    except WebSocketDisconnect:
        logger.info(f"Client disconnected (session: {actual_session_id})")

    except OperationalError as e:
        logger.error(
            f"Database error (session: {actual_session_id}): {e}", exc_info=True
        )

    except Exception as e:
        logger.error(
            f"WebSocket error (session: {actual_session_id}): {e}", exc_info=True
        )

    finally:
        # Clean up rate limit tracking for this session
        if actual_session_id:
            await websocket.app.state.rate_limiter.reset(actual_session_id)
        logger.info(f"Connection closed (session: {actual_session_id})")
