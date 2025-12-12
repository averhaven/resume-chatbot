from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_app_creation():
    """Test that the FastAPI app is created successfully"""
    assert app.title == "Resume Chatbot API"
    assert app.version == "0.1.0"
