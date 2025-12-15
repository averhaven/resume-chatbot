"""Integration tests for end-to-end chat functionality."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_client import LLMAPIError, LLMRateLimitError


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client that returns predefined responses."""
    mock_client = AsyncMock()
    mock_client.call_llm = AsyncMock(
        return_value="This is a test response from the LLM."
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


@pytest.fixture
def mock_resume_text():
    """Mock resume text."""
    return """# John Doe
## Software Engineer

### Contact Information
- Email: john@example.com
- Location: San Francisco, CA

### Professional Summary
Experienced software engineer with 5 years of experience.

### Work Experience
#### Senior Developer at Tech Corp
San Francisco, CA | 2020 - Present
- Built scalable web applications
- Led team of 3 developers

### Skills
- **Languages**: Python, JavaScript, Go
- **Frameworks**: FastAPI, React, Django
"""


class TestEndToEndChat:
    """Integration tests for the complete chat flow."""

    def test_websocket_connection_and_question(self, mock_llm_client, mock_resume_text):
        """Test connecting to WebSocket and sending a question."""
        with patch("app.main.create_llm_client", return_value=mock_llm_client):
            with TestClient(app) as client:
                with client.websocket_connect("/ws") as websocket:
                    # Receive welcome message
                    welcome = websocket.receive_json()
                    assert welcome["type"] == "system"
                    assert "Connected" in welcome["message"]

                    # Send a question
                    websocket.send_json(
                        {"type": "question", "question": "What is your name?"}
                    )

                    # Receive response
                    response = websocket.receive_json()
                    assert response["type"] == "response"
                    assert "response" in response
                    assert (
                        response["response"] == "This is a test response from the LLM."
                    )

    def test_conversation_history_accumulation(self, mock_llm_client):
        """Test that conversation history accumulates across multiple messages."""
        responses = ["First response", "Second response", "Third response"]
        mock_llm_client.call_llm = AsyncMock(side_effect=responses)

        with patch("app.main.create_llm_client", return_value=mock_llm_client):
            with TestClient(app) as client:
                # Note: Each WebSocket connection gets its own conversation manager
                with client.websocket_connect("/ws") as websocket:
                    # Receive welcome message
                    welcome = websocket.receive_json()
                    assert welcome["type"] == "system"

                    # Send first question
                    websocket.send_json({"type": "question", "question": "Question 1"})
                    response1 = websocket.receive_json()
                    assert response1["response"] == "First response"

                    # Send second question
                    websocket.send_json({"type": "question", "question": "Question 2"})
                    response2 = websocket.receive_json()
                    assert response2["response"] == "Second response"

                    # Send third question
                    websocket.send_json({"type": "question", "question": "Question 3"})
                    response3 = websocket.receive_json()
                    assert response3["response"] == "Third response"

                    # Verify that call_llm was called with increasing history
                    assert mock_llm_client.call_llm.call_count == 3

                    # Check that the last call included conversation history
                    last_call_messages = mock_llm_client.call_llm.call_args_list[-1][0][
                        0
                    ]
                    # Should have: system + q1 + a1 + q2 + a2 + q3
                    # System message is always first, then history alternates user/assistant
                    user_messages = [
                        msg for msg in last_call_messages if msg["role"] == "user"
                    ]
                    assert len(user_messages) == 3  # All three questions

    def test_invalid_message_format(self, mock_llm_client):
        """Test that invalid message format returns error."""
        with patch("app.main.create_llm_client", return_value=mock_llm_client):
            with TestClient(app) as client:
                with client.websocket_connect("/ws") as websocket:
                    # Receive welcome message
                    welcome = websocket.receive_json()
                    assert welcome["type"] == "system"

                    # Send invalid message (missing 'question' field)
                    websocket.send_json({"type": "question"})

                    # Should receive error message
                    response = websocket.receive_json()
                    assert response["type"] == "error"
                    assert "error" in response
                    assert response["code"] == "VALIDATION_ERROR"

    def test_llm_api_error_handling(self, mock_llm_client):
        """Test that LLM API errors are handled gracefully."""
        mock_llm_client.call_llm = AsyncMock(side_effect=LLMAPIError("API Error"))

        with patch("app.main.create_llm_client", return_value=mock_llm_client):
            with TestClient(app) as client:
                with client.websocket_connect("/ws") as websocket:
                    # Receive welcome message
                    welcome = websocket.receive_json()
                    assert welcome["type"] == "system"

                    # Send question
                    websocket.send_json(
                        {"type": "question", "question": "Test question"}
                    )

                    # Should receive error message
                    response = websocket.receive_json()
                    assert response["type"] == "error"
                    assert response["code"] == "API_ERROR"
                    assert "API error" in response["error"]

    def test_llm_rate_limit_error_handling(self, mock_llm_client):
        """Test that rate limit errors are handled gracefully."""
        mock_llm_client.call_llm = AsyncMock(
            side_effect=LLMRateLimitError("Rate limit exceeded")
        )

        with patch("app.main.create_llm_client", return_value=mock_llm_client):
            with TestClient(app) as client:
                with client.websocket_connect("/ws") as websocket:
                    # Receive welcome message
                    welcome = websocket.receive_json()
                    assert welcome["type"] == "system"

                    # Send question
                    websocket.send_json(
                        {"type": "question", "question": "Test question"}
                    )

                    # Should receive error message
                    response = websocket.receive_json()
                    assert response["type"] == "error"
                    assert response["code"] == "RATE_LIMIT"
                    assert "Rate limit" in response["error"]

    def test_conversation_persists_within_session(self, mock_llm_client):
        """Test that conversation history persists within a WebSocket session."""
        responses = ["Response 1", "Response 2"]
        mock_llm_client.call_llm = AsyncMock(side_effect=responses)

        with patch("app.main.create_llm_client", return_value=mock_llm_client):
            with TestClient(app) as client:
                # Single connection with multiple messages
                with client.websocket_connect("/ws") as websocket:
                    welcome = websocket.receive_json()
                    assert welcome["type"] == "system"

                    # Send first question
                    websocket.send_json({"type": "question", "question": "Question 1"})
                    response1 = websocket.receive_json()
                    assert response1["type"] == "response"
                    assert response1["response"] == "Response 1"

                    # Send second question
                    websocket.send_json({"type": "question", "question": "Question 2"})
                    response2 = websocket.receive_json()
                    assert response2["type"] == "response"
                    assert response2["response"] == "Response 2"

                    # Verify conversation history was passed to LLM
                    # The second call should include the first question and response
                    assert mock_llm_client.call_llm.call_count == 2
                    second_call_messages = mock_llm_client.call_llm.call_args_list[1][
                        0
                    ][0]
                    user_messages = [
                        msg for msg in second_call_messages if msg["role"] == "user"
                    ]
                    # Should have both questions in history
                    assert len(user_messages) == 2

    def test_sessions_are_isolated(self, mock_llm_client):
        """Test that different WebSocket sessions have isolated conversations."""
        responses = ["Response 1", "Response 2"]
        mock_llm_client.call_llm = AsyncMock(side_effect=responses)

        with patch("app.main.create_llm_client", return_value=mock_llm_client):
            with TestClient(app) as client:
                # First connection sends a message
                with client.websocket_connect("/ws") as ws1:
                    ws1.receive_json()  # welcome message
                    ws1.send_json(
                        {"type": "question", "question": "Question from session 1"}
                    )
                    response1 = ws1.receive_json()
                    assert response1["response"] == "Response 1"

                # Reset mock for second connection
                mock_llm_client.call_llm = AsyncMock(
                    return_value="Response from session 2"
                )

                # Second connection should have clean conversation (no history from first)
                with client.websocket_connect("/ws") as ws2:
                    ws2.receive_json()  # welcome message
                    ws2.send_json(
                        {"type": "question", "question": "Question from session 2"}
                    )
                    response2 = ws2.receive_json()
                    assert response2["response"] == "Response from session 2"

                    # Verify the second connection only saw its own message
                    second_session_call = mock_llm_client.call_llm.call_args_list[-1][
                        0
                    ][0]
                    user_messages = [
                        msg for msg in second_session_call if msg["role"] == "user"
                    ]
                    # Should only have one question (the new one, not from first session)
                    assert len(user_messages) == 1
                    assert user_messages[0]["content"] == "Question from session 2"
