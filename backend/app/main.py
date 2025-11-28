from fastapi import FastAPI
from app.core.logger import setup_logging, get_logger

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
