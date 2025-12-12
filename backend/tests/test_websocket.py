from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def test_client():
    """Create a test client."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client for testing."""
    mock_client = AsyncMock()
    mock_client.call_llm = AsyncMock(return_value="Mock LLM response")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


def test_websocket_connection(test_client, mock_llm_client):
    """Test that a client can successfully connect to the WebSocket endpoint"""
    with patch("app.main.create_llm_client", return_value=mock_llm_client):
        with test_client.websocket_connect("/ws") as websocket:
            # Should receive welcome message
            welcome = websocket.receive_json()
            assert welcome["type"] == "system"
            assert "Connected" in welcome["message"]


def test_websocket_basic_chat(test_client, mock_llm_client):
    """Test basic chat functionality via WebSocket"""
    with patch("app.main.create_llm_client", return_value=mock_llm_client):
        with test_client.websocket_connect("/ws") as websocket:
            # Receive welcome message
            welcome = websocket.receive_json()
            assert welcome["type"] == "system"

            # Send a question
            question = {"type": "question", "question": "What is your name?"}
            websocket.send_json(question)

            # Receive response
            response = websocket.receive_json()
            assert response["type"] == "response"
            assert "response" in response
            assert response["response"] == "Mock LLM response"


def test_websocket_multiple_messages(test_client, mock_llm_client):
    """Test sending multiple messages in sequence"""
    responses = ["Response 1", "Response 2", "Response 3"]
    mock_llm_client.call_llm = AsyncMock(side_effect=responses)

    with patch("app.main.create_llm_client", return_value=mock_llm_client):
        with test_client.websocket_connect("/ws") as websocket:
            # Receive welcome message
            welcome = websocket.receive_json()
            assert welcome["type"] == "system"

            questions = ["Question 1", "Question 2", "Question 3"]

            for i, question_text in enumerate(questions):
                websocket.send_json({"type": "question", "question": question_text})
                response = websocket.receive_json()
                assert response["type"] == "response"
                assert response["response"] == responses[i]


def test_websocket_invalid_json_structure(test_client, mock_llm_client):
    """Test that invalid message structure is handled gracefully"""
    with patch("app.main.create_llm_client", return_value=mock_llm_client):
        with test_client.websocket_connect("/ws") as websocket:
            # Receive welcome message
            welcome = websocket.receive_json()
            assert welcome["type"] == "system"

            # Send invalid message (missing 'question' field)
            invalid_message = {"type": "question"}
            websocket.send_json(invalid_message)

            # Should receive error message
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert "error" in response
            assert response["code"] == "VALIDATION_ERROR"


def test_websocket_disconnect(test_client, mock_llm_client):
    """Test that WebSocket disconnection is handled gracefully"""
    with patch("app.main.create_llm_client", return_value=mock_llm_client):
        with test_client.websocket_connect("/ws") as websocket:
            # Receive welcome message
            welcome = websocket.receive_json()
            assert welcome["type"] == "system"

            # Send a message to confirm connection works
            websocket.send_json({"type": "question", "question": "Test question"})
            response = websocket.receive_json()
            assert response["type"] == "response"

        # Context manager automatically closes the connection
        # If we get here without errors, disconnect was handled gracefully
