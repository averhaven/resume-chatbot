from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.core.logger import setup_logging, get_logger
from app.models.websocket import WebSocketMessage

# Setup logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Resume Chatbot API",
    description="A chatbot that answers questions about your resume using RAG",
    version="0.1.0"
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
            logger.debug(f"Sent echo response")
    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
