"""Tests for dynamic WebSocket routing via /chat/{username}."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import User
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


def _make_user(
    username="alice",
    resume_content="Alice is a software engineer with 5 years of experience.",
    chat_enabled=True,
):
    """Create a User object for testing."""
    user = User(
        id=uuid4(),
        username=username,
        email=f"{username}@example.com",
        password_hash="hashed",
        resume_content=resume_content,
        resume_filename="resume.pdf" if resume_content else None,
        chat_enabled=chat_enabled,
    )
    return user


def test_chat_user_not_found(test_client):
    """Test /chat/{username} returns error when user doesn't exist."""
    with test_client.websocket_connect("/chat/nonexistent") as websocket:
        msg = websocket.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "USER_NOT_FOUND"


def test_chat_no_resume(test_client):
    """Test /chat/{username} returns error when user has no resume."""
    user = _make_user(resume_content=None)

    with patch(
        "app.main.UserRepository.get_by_username",
        new_callable=AsyncMock,
        return_value=user,
    ):
        with test_client.websocket_connect("/chat/alice") as websocket:
            msg = websocket.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "NO_RESUME"


def test_chat_disabled(test_client):
    """Test /chat/{username} returns error when chat is disabled."""
    user = _make_user(chat_enabled=False)

    with patch(
        "app.main.UserRepository.get_by_username",
        new_callable=AsyncMock,
        return_value=user,
    ):
        with test_client.websocket_connect("/chat/alice") as websocket:
            msg = websocket.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "CHAT_DISABLED"


def test_chat_connection_success(test_client, mock_llm_client):
    """Test successful connection to /chat/{username} with valid user."""
    user = _make_user()

    with (
        patch(
            "app.main.UserRepository.get_by_username",
            new_callable=AsyncMock,
            return_value=user,
        ),
        patch("app.main.create_llm_client", return_value=mock_llm_client),
    ):
        with test_client.websocket_connect("/chat/alice") as websocket:
            welcome = websocket.receive_json()
            assert welcome["type"] == "system"
            assert "alice" in welcome["message"]
            assert welcome["session_id"] is not None


def test_chat_basic_conversation(test_client, mock_llm_client):
    """Test basic chat via /chat/{username}."""
    user = _make_user()

    with (
        patch(
            "app.main.UserRepository.get_by_username",
            new_callable=AsyncMock,
            return_value=user,
        ),
        patch("app.main.create_llm_client", return_value=mock_llm_client),
    ):
        with test_client.websocket_connect("/chat/alice") as websocket:
            welcome = websocket.receive_json()
            assert welcome["type"] == "system"

            websocket.send_json(
                {"type": "question", "question": "What is Alice's experience?"}
            )
            response = websocket.receive_json()
            assert response["type"] == "response"
            assert response["response"] == "Mock LLM response"


def test_chat_session_resumption(test_client, mock_llm_client):
    """Test session resumption via session_id query parameter."""
    user = _make_user()

    with (
        patch(
            "app.main.UserRepository.get_by_username",
            new_callable=AsyncMock,
            return_value=user,
        ),
        patch("app.main.create_llm_client", return_value=mock_llm_client),
    ):
        # First connection - get session_id
        with test_client.websocket_connect("/chat/alice") as websocket:
            welcome = websocket.receive_json()
            session_id = welcome["session_id"]

        # Second connection - resume session
        with test_client.websocket_connect(
            f"/chat/alice?session_id={session_id}"
        ) as websocket:
            welcome = websocket.receive_json()
            assert welcome["type"] == "system"
            assert welcome["session_id"] == session_id


def test_chat_different_users_get_different_contexts(test_client, mock_llm_client):
    """Test that different usernames load different resume contexts."""
    alice = _make_user(username="alice", resume_content="Alice is a backend engineer.")
    bob = _make_user(username="bob", resume_content="Bob is a frontend developer.")

    async def lookup_user(username):
        if username == "alice":
            return alice
        elif username == "bob":
            return bob
        return None

    with (
        patch(
            "app.main.UserRepository.get_by_username",
            new_callable=AsyncMock,
            side_effect=lookup_user,
        ),
        patch("app.main.create_llm_client", return_value=mock_llm_client),
    ):
        # Connect as alice
        with test_client.websocket_connect("/chat/alice") as websocket:
            welcome = websocket.receive_json()
            assert "alice" in welcome["message"]

        # Connect as bob
        with test_client.websocket_connect("/chat/bob") as websocket:
            welcome = websocket.receive_json()
            assert "bob" in welcome["message"]


def test_chat_html_page(test_client):
    """Test that GET /chat/{username} serves the chat HTML page."""
    response = test_client.get("/chat/alice")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
