from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    """Test the health check endpoint (shallow)"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["checks"] == {}


def test_health_check_deep():
    """Test the deep health check endpoint"""
    # Use context manager to run lifespan and initialize app state
    with TestClient(app) as test_client:
        response = test_client.get("/health?deep=true")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data["checks"]
        assert "resume" in data["checks"]
        assert data["checks"]["database"] == "healthy"
        assert data["checks"]["resume"] == "healthy"


def test_app_creation():
    """Test that the FastAPI app is created successfully"""
    assert app.title == "Resume Chatbot API"
    assert app.version == "0.1.0"
