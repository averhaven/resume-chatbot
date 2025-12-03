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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Setup logging
    setup_logging()
    logger = get_logger(__name__)
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
    description="A chatbot that answers questions about your resume using RAG",
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

                    # Get conversation history (excludes system messages)
                    history = conversation_manager.get_conversation()

                    # Build prompt with resume, history, and new question
                    messages = build_prompt(resume_text, history, question_msg.question)

                    # Call LLM API
                    logger.info("Calling LLM API")
                    response_text = await llm_client.call_llm(messages)

                    # Add user question and assistant response to conversation history
                    conversation_manager.add_message("user", question_msg.question)
                    conversation_manager.add_message("assistant", response_text)

                    # Send response back to client
                    response = ResponseMessage(response=response_text)
                    await websocket.send_json(response.model_dump())
                    logger.info(f"Sent response ({len(response_text)} chars)")

                except ValidationError as e:
                    # Invalid message format
                    error = ErrorMessage(
                        error=f"Invalid message format: {str(e)}", code="VALIDATION_ERROR"
                    )
                    await websocket.send_json(error.model_dump())
                    logger.warning(f"Validation error: {e}")

                except LLMRateLimitError:
                    # Rate limit exceeded
                    error = ErrorMessage(
                        error="Rate limit exceeded. Please try again later.",
                        code="RATE_LIMIT",
                    )
                    await websocket.send_json(error.model_dump())
                    logger.warning("Rate limit exceeded")

                except LLMAPIError as e:
                    # LLM API error
                    error = ErrorMessage(
                        error=f"API error: {str(e)}", code="API_ERROR"
                    )
                    await websocket.send_json(error.model_dump())
                    logger.error(f"API error: {e}")

                except LLMError as e:
                    # Other LLM errors
                    error = ErrorMessage(
                        error=f"Service error: {str(e)}", code="LLM_ERROR"
                    )
                    await websocket.send_json(error.model_dump())
                    logger.error(f"LLM error: {e}")

                except Exception as e:
                    # Unexpected error
                    error = ErrorMessage(
                        error="An unexpected error occurred. Please try again.",
                        code="INTERNAL_ERROR",
                    )
                    await websocket.send_json(error.model_dump())
                    logger.error(f"Unexpected error: {e}", exc_info=True)

    except WebSocketDisconnect:
        logger.info("Client disconnected")

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)

    finally:
        logger.info("WebSocket connection closed")
