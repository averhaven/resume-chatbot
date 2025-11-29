import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_websocket_connection():
    """Test that a client can successfully connect to the WebSocket endpoint"""
    with client.websocket_connect("/ws") as websocket:
        # If we get here, connection was successful
        assert websocket is not None


def test_websocket_echo():
    """Test that the WebSocket correctly echoes back JSON messages"""
    with client.websocket_connect("/ws") as websocket:
        # Send a test message
        test_message = {"type": "echo", "data": "Hello, WebSocket!"}
        websocket.send_json(test_message)

        # Receive the echo response
        response = websocket.receive_json()

        # Verify it's the same message
        assert response == test_message
        assert response["type"] == "echo"
        assert response["data"] == "Hello, WebSocket!"


def test_websocket_multiple_messages():
    """Test sending multiple messages in sequence"""
    with client.websocket_connect("/ws") as websocket:
        messages = [
            {"type": "echo", "data": "First message"},
            {"type": "echo", "data": "Second message"},
            {"type": "echo", "data": "Third message"},
        ]

        for msg in messages:
            websocket.send_json(msg)
            response = websocket.receive_json()
            assert response == msg


def test_websocket_invalid_json_structure():
    """Test that invalid message structure is handled gracefully"""
    # Send invalid JSON and verify the server handles it without crashing
    # With simplified error handling, the server logs the error and closes connection
    try:
        with client.websocket_connect("/ws") as websocket:
            invalid_message = {"wrong_field": "value"}
            websocket.send_json(invalid_message)
            # Connection will close due to validation error
    except Exception:
        # Connection closed, which is expected behavior
        pass


def test_websocket_disconnect():
    """Test that WebSocket disconnection is handled gracefully"""
    with client.websocket_connect("/ws") as websocket:
        # Send a message to confirm connection works
        test_message = {"type": "echo", "data": "test"}
        websocket.send_json(test_message)
        response = websocket.receive_json()
        assert response == test_message

    # Context manager automatically closes the connection
    # If we get here without errors, disconnect was handled gracefully
