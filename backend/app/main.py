from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.resumes import router as resumes_router
from app.core.config import get_settings, validate_settings
from app.core.context import set_session_id
from app.core.errors import ErrorCode, get_user_message
from app.core.logger import get_logger, setup_logging
from app.core.rate_limit import WebSocketRateLimiter
from app.db.repositories.user import UserRepository
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
from app.services.resume_loader import (
    ResumeContext,
    ResumeContextCache,
)
from app.services.token_counter import TokenCounter

logger = get_logger(__name__)


async def send_error_response(
    websocket: WebSocket,
    error_code: ErrorCode | str,
    log_message: str | None = None,
    log_level: str = "error",
) -> None:
    """Send user-friendly error response via WebSocket and log internal details.

    The user receives a friendly, non-technical message while the full error
    details are logged for debugging purposes.

    Args:
        websocket: WebSocket connection
        error_code: Error code identifier (ErrorCode enum or string)
        log_message: Internal error details for logging (not sent to user)
        log_level: Logging level - "error", "warning", or "info"
    """
    # Get user-friendly message (hides internal details)
    user_message = get_user_message(error_code)

    # Get string code for the response
    code_str = error_code.value if isinstance(error_code, ErrorCode) else error_code

    error = ErrorMessage(error=user_message, code=code_str)
    await websocket.send_json(error.model_dump())

    # Log internal details (not sent to user)
    log_func = getattr(logger, log_level, logger.error)
    if log_message:
        log_func(f"{code_str}: {log_message}")
    else:
        log_func(f"{code_str}: {user_message}")


async def process_question(
    question: str,
    conversation_manager: DatabaseConversationManager,
    resume_context: ResumeContext,
    llm_client: OpenRouterClient,
    token_counter: TokenCounter,
) -> str:
    """Process a user question and generate LLM response.

    Handles the full question/answer flow: history retrieval, prompt building,
    LLM call, and message persistence. Caller must commit the transaction.

    Args:
        question: User's question text
        conversation_manager: Database-backed conversation manager
        resume_context: Resume context with system prompt
        llm_client: LLM client instance
        token_counter: Token counter instance for pruning

    Returns:
        LLM response text
    """
    settings = get_settings()

    # Get conversation history
    history = await conversation_manager.get_conversation()

    # Prune history to fit within token limits
    pruned_history, tokens_removed = prune_conversation_history(
        history=history,
        token_counter=token_counter,
        system_tokens=resume_context.system_prompt_tokens,
        max_tokens=settings.max_context_tokens,
        min_exchanges=settings.min_conversation_exchanges,
        response_reserve=settings.max_response_tokens,
    )

    if tokens_removed > 0:
        logger.info(f"Pruned {tokens_removed} tokens from conversation history")

    messages = build_prompt(resume_context.system_prompt, pruned_history, question)

    logger.info("Calling LLM API")
    response_text = await llm_client.call_llm(messages)

    # Persist messages (caller must commit)
    await conversation_manager.add_message("user", question)
    await conversation_manager.add_message("assistant", response_text)

    return response_text


async def handle_websocket_messages(
    websocket: WebSocket,
    conversation_manager: DatabaseConversationManager,
    resume_context: ResumeContext,
    llm_client: OpenRouterClient,
    rate_limiter: WebSocketRateLimiter,
    session_id: str,
    token_counter: TokenCounter,
) -> None:
    """Handle WebSocket message loop.

    Receives questions, processes them, and sends responses until disconnect.

    Args:
        websocket: WebSocket connection
        conversation_manager: Database-backed conversation manager
        resume_context: Resume context with system prompt
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
                    ErrorCode.RATE_LIMIT_EXCEEDED,
                    log_message="Rate limit exceeded for session",
                    log_level="warning",
                )
                continue

            question_msg = QuestionMessage(**data)
            logger.info("Received question")

            response_text = await process_question(
                question_msg.question,
                conversation_manager,
                resume_context,
                llm_client,
                token_counter,
            )

            await conversation_manager.commit()

            response = ResponseMessage(response=response_text)
            await websocket.send_json(response.model_dump())
            logger.info(f"Sent response ({len(response_text)} chars)")

        except ValidationError as e:
            await send_error_response(
                websocket,
                ErrorCode.VALIDATION_ERROR,
                log_message=f"Invalid message format: {e!s}",
                log_level="warning",
            )

        except LLMRateLimitError as e:
            await send_error_response(
                websocket,
                ErrorCode.RATE_LIMIT,
                log_message=f"LLM rate limit exceeded: {e!s}",
                log_level="warning",
            )

        except LLMAPIError as e:
            await send_error_response(
                websocket,
                ErrorCode.API_ERROR,
                log_message=f"LLM API error: {e!s}",
            )

        except LLMError as e:
            await send_error_response(
                websocket,
                ErrorCode.LLM_ERROR,
                log_message=f"LLM service error: {e!s}",
            )

        except OperationalError as e:
            await send_error_response(
                websocket,
                ErrorCode.DATABASE_ERROR,
                log_message=f"Database connection error: {e!s}",
            )

        except SQLAlchemyError as e:
            await send_error_response(
                websocket,
                ErrorCode.DATABASE_ERROR,
                log_message=f"Database error: {e!s}",
            )

        except Exception as e:
            await send_error_response(
                websocket,
                ErrorCode.INTERNAL_ERROR,
                log_message=f"Unexpected error: {e!s}",
            )


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

    # Initialize per-user resume context cache (lazy-loaded on first connection)
    app.state.resume_cache = ResumeContextCache()
    logger.info("Resume context cache initialized")

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

app.include_router(auth_router)
app.include_router(resumes_router)
app.include_router(dashboard_router)


@app.get("/health")
async def health_check(deep: bool = False):
    """Health check endpoint.

    Args:
        deep: If True, performs deep health checks including database
              connectivity and resume loading verification.

    Returns:
        JSON response with health status. Returns 200 if healthy,
        503 if any component is unhealthy (only for deep checks).
    """
    logger.debug(f"Health check requested (deep={deep})")

    status = {"status": "healthy", "checks": {}}

    if deep:
        # Database connectivity check
        try:
            db_manager: DatabaseManager = getattr(app.state, "db_manager", None)
            if db_manager is None:
                status["checks"]["database"] = "unavailable"
                status["status"] = "degraded"
            else:
                async with db_manager.get_session() as session:
                    await session.execute(text("SELECT 1"))
                status["checks"]["database"] = "healthy"
        except Exception as e:
            status["checks"]["database"] = "unhealthy"
            status["status"] = "degraded"
            logger.warning(f"Database health check failed: {e}")

        # Resume context cache check
        try:
            resume_cache: ResumeContextCache = getattr(app.state, "resume_cache", None)
            if resume_cache is None:
                status["checks"]["resume_cache"] = "unavailable"
                status["status"] = "degraded"
            else:
                status["checks"]["resume_cache"] = (
                    f"healthy ({resume_cache.size} cached)"
                )
        except Exception as e:
            status["checks"]["resume_cache"] = "unhealthy"
            status["status"] = "degraded"
            logger.warning(f"Resume cache health check failed: {e}")

    http_status = 200 if status["status"] == "healthy" else 503
    return JSONResponse(content=status, status_code=http_status)


def _render_landing_html() -> str:
    """Render the product landing page HTML."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resume Chatbot</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }
        .card {
            background: white;
            border-radius: 16px;
            padding: 3rem 2.5rem;
            max-width: 680px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.2);
        }
        .hero { text-align: center; margin-bottom: 2.5rem; }
        .hero h1 {
            font-size: 2rem;
            font-weight: 700;
            color: #1a1a2e;
            margin-bottom: 0.75rem;
        }
        .hero p {
            font-size: 1.05rem;
            color: #555;
            line-height: 1.6;
        }
        .steps { margin-bottom: 2rem; }
        .steps h2 {
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #aaa;
            margin-bottom: 1rem;
        }
        .step {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 0.75rem;
        }
        .step-num {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            font-weight: 700;
            font-size: 0.8rem;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .step-text { color: #444; font-size: 0.9rem; }
        .step-text strong { color: #1a1a2e; }
        .step-text code {
            background: #f3f0ff;
            color: #764ba2;
            padding: 1px 6px;
            border-radius: 4px;
            font-size: 0.82rem;
        }
        .btn {
            display: block;
            width: 100%;
            padding: 0.75rem 1.25rem;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 600;
            text-decoration: none;
            text-align: center;
            transition: opacity 0.15s, transform 0.1s;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }
        .btn:hover { opacity: 0.88; transform: translateY(-1px); }
        .formats {
            margin-top: 1.5rem;
            text-align: center;
            font-size: 0.8rem;
            color: #aaa;
        }
        .disclaimer {
            margin-top: 1rem;
            text-align: center;
            font-size: 0.8rem;
            color: #aaa;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="hero">
            <h1>Your Resume, Your Chatbot</h1>
            <p>Upload your resume and get a shareable AI chatbot link<br>
               Let recruiters ask questions about you</p>
        </div>

        <div class="steps">
            <h2>How it works</h2>
            <div class="step">
                <div class="step-num">1</div>
                <div class="step-text"><strong>Open <a href="/docs" style="color:#764ba2">/docs</a></strong> — everything is interactive there</div>
            </div>
            <div class="step">
                <div class="step-num">2</div>
                <div class="step-text"><strong>Register</strong> via <code>POST /auth/register</code>, then click <strong>Authorize</strong> to log in</div>
            </div>
            <div class="step">
                <div class="step-num">3</div>
                <div class="step-text"><strong>Upload your resume</strong> via <code>POST /resume/upload</code></div>
            </div>
            <div class="step">
                <div class="step-num">4</div>
                <div class="step-text"><strong>Share</strong> your live chatbot at <code>/chat/<em>your-username</em></code></div>
            </div>
        </div>

        <a href="/chat/alexandra" class="btn">Chat with Alexandra Verhaven &rarr;</a>

        <p class="formats">Accepts PDF &middot; DOCX &middot; TXT &middot; Markdown &middot; JSON &nbsp;&mdash;&nbsp; up to 5 MB</p>
        <p class="disclaimer"><strong>This is a personal demo.</strong> Please don&rsquo;t upload a real resume &mdash; data is stored unencrypted and may be deleted without notice.</p>
    </div>
</body>
</html>"""


def _render_chat_html(
    title: str, heading: str, subheading: str, placeholder: str
) -> str:
    """Render the chat interface HTML with the given header content.

    Args:
        title: Browser tab title
        heading: Main heading displayed in the chat header
        subheading: Subheading text beneath the heading
        placeholder: Input field placeholder text
    """
    return f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>{title}</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    padding: 20px;
                }}
                .container {{
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    width: 100%;
                    max-width: 800px;
                    height: 600px;
                    display: flex;
                    flex-direction: column;
                }}
                .header {{
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border-radius: 12px 12px 0 0;
                    text-align: center;
                }}
                .header h1 {{
                    font-size: 24px;
                    font-weight: 600;
                }}
                .header p {{
                    font-size: 14px;
                    opacity: 0.9;
                    margin-top: 5px;
                }}
                #messages {{
                    flex: 1;
                    overflow-y: auto;
                    padding: 20px;
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                }}
                .message {{
                    padding: 12px 16px;
                    border-radius: 8px;
                    max-width: 80%;
                    word-wrap: break-word;
                    animation: fadeIn 0.3s;
                }}
                @keyframes fadeIn {{
                    from {{ opacity: 0; transform: translateY(10px); }}
                    to {{ opacity: 1; transform: translateY(0); }}
                }}
                .user-message {{
                    background: #667eea;
                    color: white;
                    align-self: flex-end;
                    margin-left: auto;
                }}
                .assistant-message {{
                    background: #f3f4f6;
                    color: #1f2937;
                    align-self: flex-start;
                }}
                .system-message {{
                    background: #dbeafe;
                    color: #1e40af;
                    align-self: center;
                    text-align: center;
                    font-size: 14px;
                    font-style: italic;
                }}
                .error-message {{
                    background: #fee2e2;
                    color: #991b1b;
                    align-self: center;
                    text-align: center;
                    font-size: 14px;
                }}
                .input-area {{
                    padding: 20px;
                    border-top: 1px solid #e5e7eb;
                    display: flex;
                    gap: 10px;
                }}
                #messageInput {{
                    flex: 1;
                    padding: 12px;
                    border: 2px solid #e5e7eb;
                    border-radius: 8px;
                    font-size: 14px;
                    outline: none;
                    transition: border-color 0.2s;
                }}
                #messageInput:focus {{
                    border-color: #667eea;
                }}
                button {{
                    padding: 12px 24px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: transform 0.2s, box-shadow 0.2s;
                }}
                button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
                }}
                button:active {{
                    transform: translateY(0);
                }}
                button:disabled {{
                    opacity: 0.5;
                    cursor: not-allowed;
                    transform: none;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{heading}</h1>
                    <p>{subheading}</p>
                </div>
                <div id="messages"></div>
                <div class="input-area">
                    <input
                        type="text"
                        id="messageInput"
                        placeholder="{placeholder}"
                        autocomplete="off"
                    />
                    <button onclick="sendMessage()" id="sendButton">Send</button>
                </div>
            </div>

            <script>
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const messagesDiv = document.getElementById("messages");
                const messageInput = document.getElementById("messageInput");
                const sendButton = document.getElementById("sendButton");

                let ws = null;
                let sessionId = null;
                let reconnectAttempts = 0;
                const maxReconnectAttempts = 5;

                function connect() {{
                    const basePath = window.location.pathname === '/' ? '/ws' : window.location.pathname;
                    const url = sessionId
                        ? `${{protocol}}//${{window.location.host}}${{basePath}}?session_id=${{sessionId}}`
                        : `${{protocol}}//${{window.location.host}}${{basePath}}`;

                    ws = new WebSocket(url);

                    ws.onopen = function(event) {{
                        console.log("WebSocket connected");
                        reconnectAttempts = 0;
                        enableInput();
                    }};

                    ws.onmessage = function(event) {{
                        const data = JSON.parse(event.data);

                        if (data.type === "system") {{
                            // Only show welcome message on first connect
                            if (!sessionId) {{
                                addMessage(data.message, "system-message");
                            }}
                            // Extract session_id if provided
                            if (data.session_id) {{
                                sessionId = data.session_id;
                            }}
                        }} else if (data.type === "response") {{
                            addMessage(data.response, "assistant-message");
                        }} else if (data.type === "error") {{
                            addMessage(`Error: ${{data.error}}`, "error-message");
                        }}

                        enableInput();
                    }};

                    ws.onerror = function(error) {{
                        console.error("WebSocket error:", error);
                    }};

                    ws.onclose = function(event) {{
                        console.log("WebSocket disconnected");
                        disableInput();

                        if (reconnectAttempts < maxReconnectAttempts) {{
                            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
                            reconnectAttempts++;
                            addMessage(`Connection lost. Reconnecting in ${{delay/1000}}s...`, "system-message");
                            setTimeout(connect, delay);
                        }} else {{
                            addMessage("Unable to reconnect. Please refresh the page.", "error-message");
                        }}
                    }};
                }}

                function addMessage(text, className) {{
                    const messageDiv = document.createElement("div");
                    messageDiv.className = `message ${{className}}`;
                    messageDiv.textContent = text;
                    messagesDiv.appendChild(messageDiv);
                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                }}

                function sendMessage() {{
                    const message = messageInput.value.trim();
                    if (message === "" || !ws || ws.readyState !== WebSocket.OPEN) {{
                        return;
                    }}

                    // Display user message
                    addMessage(message, "user-message");

                    // Send to WebSocket
                    ws.send(JSON.stringify({{
                        type: "question",
                        question: message
                    }}));

                    // Clear input and disable until response
                    messageInput.value = "";
                    disableInput();
                }}

                function disableInput() {{
                    messageInput.disabled = true;
                    sendButton.disabled = true;
                }}

                function enableInput() {{
                    messageInput.disabled = false;
                    sendButton.disabled = false;
                    messageInput.focus();
                }}

                // Send message on Enter key
                messageInput.addEventListener("keypress", function(event) {{
                    if (event.key === "Enter") {{
                        sendMessage();
                    }}
                }});

                // Initial connection
                connect();
            </script>
        </body>
    </html>
    """


@app.get("/", response_class=HTMLResponse)
async def get_landing_page():
    """Serve the product landing page."""
    return _render_landing_html()


@app.get("/chat/{username}", response_class=HTMLResponse)
async def get_user_chat_interface(request: Request, username: str):
    """Serve HTML chat interface for a specific user's resume chatbot."""
    db_manager: DatabaseManager = request.app.state.db_manager
    async with db_manager.get_session() as session:
        repo = UserRepository(session)
        user = await repo.get_by_username(username)
    display = (user.display_name or username) if user else username
    return _render_chat_html(
        title=f"{display} | Resume Chat",
        heading=display,
        subheading="Ask me anything about their background, skills, and experience",
        placeholder=f"e.g., What technologies has {display} worked with?",
    )


@app.websocket("/chat/{username}")
async def chat_websocket_endpoint(
    websocket: WebSocket, username: str, session_id: str | None = None
):
    """WebSocket endpoint for per-user resume chatbot.

    Routes to a specific user's resume based on their username.
    The conversation is linked to the resume owner's user_id.

    Args:
        websocket: WebSocket connection
        username: Username to look up (from URL path)
        session_id: Optional session ID for resuming conversations
    """
    await websocket.accept()

    logger.info(
        f"Client connected to /chat/{username} (session_id param: {session_id})"
    )

    db_manager: DatabaseManager = websocket.app.state.db_manager
    token_counter: TokenCounter = websocket.app.state.token_counter
    actual_session_id = session_id

    try:
        async with db_manager.get_session() as db_session:
            # Look up user by username
            user_repo = UserRepository(db_session)
            user = await user_repo.get_by_username(username)

            if not user:
                error = ErrorMessage(
                    error=get_user_message(ErrorCode.USER_NOT_FOUND),
                    code=ErrorCode.USER_NOT_FOUND.value,
                )
                await websocket.send_json(error.model_dump())
                await websocket.close(code=4004, reason="User not found")
                return

            if not user.resume_content:
                error = ErrorMessage(
                    error=get_user_message(ErrorCode.NO_RESUME),
                    code=ErrorCode.NO_RESUME.value,
                )
                await websocket.send_json(error.model_dump())
                await websocket.close(code=4004, reason="No resume uploaded")
                return

            if not user.chat_enabled:
                error = ErrorMessage(
                    error=get_user_message(ErrorCode.CHAT_DISABLED),
                    code=ErrorCode.CHAT_DISABLED.value,
                )
                await websocket.send_json(error.model_dump())
                await websocket.close(code=4003, reason="Chat disabled")
                return

            # Get resume context from cache (or build and cache it)
            resume_cache: ResumeContextCache = websocket.app.state.resume_cache
            resume_context = resume_cache.get_or_create(
                str(user.id), user.resume_content, token_counter
            )

            # Create conversation manager linked to this user
            conversation_manager = DatabaseConversationManager(
                db_session, session_id, user_id=user.id
            )
            actual_session_id = conversation_manager.session_id
            set_session_id(actual_session_id)
            logger.info(f"Session established: {actual_session_id} (user: {username})")

            # Send welcome message
            display = user.display_name or user.username
            welcome = SystemMessage(
                message=f"Hi! I'm an AI assistant here to answer questions about {display}'s resume. Feel free to ask about their experience, skills, or projects.",
                session_id=actual_session_id,
            )
            await websocket.send_json(welcome.model_dump())

            rate_limiter: WebSocketRateLimiter = websocket.app.state.rate_limiter

            async with create_llm_client() as llm_client:
                await handle_websocket_messages(
                    websocket,
                    conversation_manager,
                    resume_context,
                    llm_client,
                    rate_limiter,
                    actual_session_id,
                    token_counter,
                )

    except WebSocketDisconnect:
        logger.info(
            f"Client disconnected from /chat/{username} (session: {actual_session_id})"
        )

    except OperationalError as e:
        logger.error(
            f"Database error (session: {actual_session_id}): {e}", exc_info=True
        )

    except Exception as e:
        logger.error(
            f"WebSocket error (session: {actual_session_id}): {e}", exc_info=True
        )

    finally:
        if actual_session_id:
            await websocket.app.state.rate_limiter.reset(actual_session_id)
        logger.info(
            f"Connection closed for /chat/{username} (session: {actual_session_id})"
        )
