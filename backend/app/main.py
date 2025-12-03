from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logger import get_logger, setup_logging
from app.models.websocket import ErrorMessage, QuestionMessage, ResponseMessage, SystemMessage
from app.services.conversation import create_conversation_manager
from app.services.llm_client import LLMAPIError, LLMError, LLMRateLimitError, create_llm_client
from app.services.prompts import build_prompt
from app.services.resume_loader import create_resume_loader

# Get logger instance (will be configured during startup)
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
    resume_text: str,
    conversation_manager,
    llm_client,
) -> str:
    """Process a user question and generate LLM response.

    Args:
        question: User's question text
        resume_text: Formatted resume text
        conversation_manager: Conversation manager instance
        llm_client: LLM client instance

    Returns:
        LLM response text
    """
    # Get conversation history
    history = conversation_manager.get_conversation()

    # Build prompt with resume, history, and new question
    messages = build_prompt(resume_text, history, question)

    # Call LLM API
    logger.info("Calling LLM API")
    response_text = await llm_client.call_llm(messages)

    # Add user question and assistant response to conversation history
    conversation_manager.add_message("user", question)
    conversation_manager.add_message("assistant", response_text)

    return response_text


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Setup logging
    setup_logging()
    logger.info("Application starting up")

    # Load resume data
    settings = get_settings()
    resume_path = Path(settings.resume_path)

    # Make path absolute if it's relative
    if not resume_path.is_absolute():
        resume_path = Path(__file__).parent.parent / resume_path

    app.state.resume_loader = create_resume_loader(resume_path)
    logger.info(f"Resume loaded from {resume_path}")

    # Create conversation manager
    app.state.conversation_manager = create_conversation_manager()
    logger.info("Conversation manager initialized")

    yield

    # Shutdown: Cleanup if needed
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


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for resume chatbot conversation.

    Handles real-time chat interactions for a single user:
    1. Receives user questions (JSON: {"type": "question", "question": "..."})
    2. Builds prompts with resume context and conversation history
    3. Calls LLM API to generate responses
    4. Sends responses back (JSON: {"type": "response", "response": "..."})
    5. Maintains conversation history in memory
    """
    await websocket.accept()
    logger.info("Client connected to WebSocket")

    # Get services from app state
    conversation_manager = websocket.app.state.conversation_manager
    resume_loader = websocket.app.state.resume_loader
    resume_text = resume_loader.get_resume_text()

    # Send welcome message
    welcome = SystemMessage(message="Connected! Ready to answer questions about the resume.")
    await websocket.send_json(welcome.model_dump())

    try:
        # Create LLM client using async context manager
        async with create_llm_client() as llm_client:
            while True:
                # Receive and parse JSON message
                data = await websocket.receive_json()

                try:
                    # Parse as question message
                    question_msg = QuestionMessage(**data)
                    logger.info("Received question")

                    # Process question and get response
                    response_text = await process_question(
                        question_msg.question,
                        resume_text,
                        conversation_manager,
                        llm_client,
                    )

                    # Send response back to client
                    response = ResponseMessage(response=response_text)
                    await websocket.send_json(response.model_dump())
                    logger.info(f"Sent response ({len(response_text)} chars)")

                except ValidationError as e:
                    await send_error_response(
                        websocket,
                        f"Invalid message format: {str(e)}",
                        "VALIDATION_ERROR",
                        "warning",
                    )

                except LLMRateLimitError:
                    await send_error_response(
                        websocket,
                        "Rate limit exceeded. Please try again later.",
                        "RATE_LIMIT",
                        "warning",
                    )

                except LLMAPIError as e:
                    await send_error_response(
                        websocket, f"API error: {str(e)}", "API_ERROR"
                    )

                except LLMError as e:
                    await send_error_response(
                        websocket, f"Service error: {str(e)}", "LLM_ERROR"
                    )

                except Exception as e:
                    await send_error_response(
                        websocket,
                        "An unexpected error occurred. Please try again.",
                        "INTERNAL_ERROR",
                    )
                    logger.error(f"Unexpected error details: {e}", exc_info=True)

    except WebSocketDisconnect:
        logger.info("Client disconnected")

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)

    finally:
        logger.info("WebSocket connection closed")
