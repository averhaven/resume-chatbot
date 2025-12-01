from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.logger import get_logger, setup_logging
from app.models.websocket import WebSocketMessage
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
    """WebSocket endpoint for real-time communication

    Accepts JSON messages with format: {"type": "echo", "data": "message"}
    Echoes back the same message for Phase 1B testing.
    """
    await websocket.accept()
    logger.info("Client connected to WebSocket")
    try:
        while True:
            # Receive and parse JSON message
            data = await websocket.receive_json()
            message = WebSocketMessage(**data)
            logger.debug(f"Received message: type={message.type}, data={message.data}")

            # Echo back the message
            await websocket.send_json(message.model_dump())
            logger.debug("Sent echo response")
    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
