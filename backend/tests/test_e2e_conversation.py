"""End-to-end tests for conversation lifecycle with database persistence.

These tests verify the complete conversation flow including:
- Database persistence of messages
- Session resumption by session_id
- Multi-message sequences
- Conversation continuity across reconnects

Unlike test_integration.py which mocks everything, these tests verify actual
database operations while only mocking the LLM client.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Conversation, Message
from app.main import app
from tests.conftest import TestDatabase


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client that returns predefined responses."""
    mock_client = AsyncMock()
    mock_client.call_llm = AsyncMock(return_value="Test LLM response")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


class TestConversationPersistence:
    """Tests for verifying messages are persisted to the database."""

    def test_messages_are_persisted_to_database(self, mock_llm_client, event_loop):
        """Test that sent messages are actually saved to the database."""
        with patch("app.main.create_llm_client", return_value=mock_llm_client):
            with TestClient(app) as client:
                with client.websocket_connect("/ws") as websocket:
                    # Receive welcome message
                    welcome = websocket.receive_json()
                    assert welcome["type"] == "system"

                    # Send a question
                    websocket.send_json(
                        {"type": "question", "question": "What are your skills?"}
                    )
                    response = websocket.receive_json()
                    assert response["type"] == "response"

        # Verify messages in database
        async def check_database():
            async with TestDatabase.session_factory() as session:
                # Check conversations table
                conv_result = await session.execute(select(Conversation))
                conversations = conv_result.scalars().all()
                assert len(conversations) == 1

                # Check messages table
                msg_result = await session.execute(
                    select(Message).where(
                        Message.conversation_id == conversations[0].id
                    )
                )
                messages = msg_result.scalars().all()

                # Should have user question + assistant response
                assert len(messages) == 2
                assert messages[0].role == "user"
                assert messages[0].content == "What are your skills?"
                assert messages[1].role == "assistant"
                assert messages[1].content == "Test LLM response"

        event_loop.run_until_complete(check_database())

    def test_multi_message_sequence_persisted(self, mock_llm_client, event_loop):
        """Test that multiple messages in sequence are all persisted."""
        responses = ["Response 1", "Response 2", "Response 3"]
        mock_llm_client.call_llm = AsyncMock(side_effect=responses)

        with patch("app.main.create_llm_client", return_value=mock_llm_client):
            with TestClient(app) as client:
                with client.websocket_connect("/ws") as websocket:
                    welcome = websocket.receive_json()
                    assert welcome["type"] == "system"

                    # Send multiple questions
                    for i in range(3):
                        websocket.send_json(
                            {"type": "question", "question": f"Question {i + 1}"}
                        )
                        response = websocket.receive_json()
                        assert response["response"] == f"Response {i + 1}"

        # Verify all messages in database
        async def check_database():
            async with TestDatabase.session_factory() as session:
                msg_result = await session.execute(
                    select(Message).order_by(Message.created_at)
                )
                messages = msg_result.scalars().all()

                # Should have 6 messages (3 questions + 3 responses)
                assert len(messages) == 6

                # Verify alternating user/assistant pattern
                for i in range(3):
                    user_msg = messages[i * 2]
                    assistant_msg = messages[i * 2 + 1]
                    assert user_msg.role == "user"
                    assert user_msg.content == f"Question {i + 1}"
                    assert assistant_msg.role == "assistant"
                    assert assistant_msg.content == f"Response {i + 1}"

        event_loop.run_until_complete(check_database())


class TestSessionResumption:
    """Tests for resuming conversations by session_id."""

    def test_resume_conversation_by_session_id(self, mock_llm_client, event_loop):
        """Test that connecting with a session_id resumes the conversation."""
        captured_session_id = None

        # First connection - establish conversation
        mock_llm_client.call_llm = AsyncMock(return_value="First response")
        with patch("app.main.create_llm_client", return_value=mock_llm_client):
            with TestClient(app) as client:
                with client.websocket_connect("/ws") as websocket:
                    welcome = websocket.receive_json()
                    assert welcome["type"] == "system"

                    websocket.send_json(
                        {"type": "question", "question": "First question"}
                    )
                    response = websocket.receive_json()
                    assert response["response"] == "First response"

        # Get the session_id from the database
        async def get_session_id():
            async with TestDatabase.session_factory() as session:
                result = await session.execute(select(Conversation))
                conv = result.scalar_one()
                return conv.session_id

        captured_session_id = event_loop.run_until_complete(get_session_id())

        # Second connection - resume with session_id
        mock_llm_client.call_llm = AsyncMock(return_value="Second response")
        with patch("app.main.create_llm_client", return_value=mock_llm_client):
            with TestClient(app) as client:
                # Connect with the captured session_id
                with client.websocket_connect(
                    f"/ws?session_id={captured_session_id}"
                ) as websocket:
                    welcome = websocket.receive_json()
                    assert welcome["type"] == "system"

                    websocket.send_json(
                        {"type": "question", "question": "Second question"}
                    )
                    response = websocket.receive_json()
                    assert response["response"] == "Second response"

        # Verify conversation history was passed to LLM on second call
        # The second call should include the first question/response in history
        second_call = mock_llm_client.call_llm.call_args_list[-1]
        messages_sent = second_call[0][0]

        # Find all user messages in the conversation
        user_messages = [m for m in messages_sent if m["role"] == "user"]
        assert len(user_messages) == 2
        assert user_messages[0]["content"] == "First question"
        assert user_messages[1]["content"] == "Second question"

    def test_session_id_creates_single_conversation(self, mock_llm_client, event_loop):
        """Test that using the same session_id doesn't create duplicate conversations."""
        session_id = "test-session-12345"

        for i in range(3):
            mock_llm_client.call_llm = AsyncMock(return_value=f"Response {i + 1}")
            with patch("app.main.create_llm_client", return_value=mock_llm_client):
                with TestClient(app) as client:
                    with client.websocket_connect(
                        f"/ws?session_id={session_id}"
                    ) as websocket:
                        websocket.receive_json()  # welcome
                        websocket.send_json(
                            {"type": "question", "question": f"Question {i + 1}"}
                        )
                        websocket.receive_json()

        # Verify only one conversation exists
        async def check_database():
            async with TestDatabase.session_factory() as session:
                conv_result = await session.execute(select(Conversation))
                conversations = conv_result.scalars().all()
                assert len(conversations) == 1
                assert conversations[0].session_id == session_id

                # All messages should be in the same conversation
                msg_result = await session.execute(select(Message))
                messages = msg_result.scalars().all()
                assert len(messages) == 6  # 3 questions + 3 responses

        event_loop.run_until_complete(check_database())


class TestConversationAcrossReconnects:
    """Tests for conversation continuity across WebSocket reconnections."""

    def test_conversation_history_loads_on_reconnect(self, mock_llm_client, event_loop):
        """Test that reconnecting loads previous messages from database."""
        session_id = "reconnect-test-session"

        # First connection - send a few messages
        responses = ["Answer 1", "Answer 2"]
        mock_llm_client.call_llm = AsyncMock(side_effect=responses)

        with patch("app.main.create_llm_client", return_value=mock_llm_client):
            with TestClient(app) as client:
                with client.websocket_connect(
                    f"/ws?session_id={session_id}"
                ) as websocket:
                    websocket.receive_json()  # welcome

                    websocket.send_json({"type": "question", "question": "Question 1"})
                    websocket.receive_json()

                    websocket.send_json({"type": "question", "question": "Question 2"})
                    websocket.receive_json()

        # Reconnect and send another message
        mock_llm_client.call_llm = AsyncMock(return_value="Answer 3")

        with patch("app.main.create_llm_client", return_value=mock_llm_client):
            with TestClient(app) as client:
                with client.websocket_connect(
                    f"/ws?session_id={session_id}"
                ) as websocket:
                    websocket.receive_json()  # welcome

                    websocket.send_json({"type": "question", "question": "Question 3"})
                    websocket.receive_json()

        # Verify the LLM received full conversation history on reconnect
        last_call = mock_llm_client.call_llm.call_args_list[-1]
        messages_sent = last_call[0][0]

        user_messages = [m for m in messages_sent if m["role"] == "user"]
        assistant_messages = [m for m in messages_sent if m["role"] == "assistant"]

        # Should have all 3 questions
        assert len(user_messages) == 3
        assert user_messages[0]["content"] == "Question 1"
        assert user_messages[1]["content"] == "Question 2"
        assert user_messages[2]["content"] == "Question 3"

        # Should have previous 2 responses
        assert len(assistant_messages) == 2
        assert assistant_messages[0]["content"] == "Answer 1"
        assert assistant_messages[1]["content"] == "Answer 2"

    def test_multiple_reconnections_preserve_full_history(
        self, mock_llm_client, event_loop
    ):
        """Test that history is preserved across multiple reconnections."""
        session_id = "multi-reconnect-session"

        # Perform 5 connect/disconnect cycles, each sending one message
        for i in range(5):
            mock_llm_client.call_llm = AsyncMock(return_value=f"Answer {i + 1}")

            with patch("app.main.create_llm_client", return_value=mock_llm_client):
                with TestClient(app) as client:
                    with client.websocket_connect(
                        f"/ws?session_id={session_id}"
                    ) as websocket:
                        websocket.receive_json()  # welcome
                        websocket.send_json(
                            {"type": "question", "question": f"Question {i + 1}"}
                        )
                        websocket.receive_json()

        # Verify database has all 10 messages
        async def check_database():
            async with TestDatabase.session_factory() as session:
                msg_result = await session.execute(
                    select(Message).order_by(Message.created_at)
                )
                messages = msg_result.scalars().all()
                assert len(messages) == 10

        event_loop.run_until_complete(check_database())

        # Verify last call received full history
        last_call = mock_llm_client.call_llm.call_args_list[-1]
        messages_sent = last_call[0][0]
        user_messages = [m for m in messages_sent if m["role"] == "user"]

        # Last call should have seen all 5 questions
        assert len(user_messages) == 5
        for i, msg in enumerate(user_messages):
            assert msg["content"] == f"Question {i + 1}"


class TestNewVsExistingSession:
    """Tests for new session creation vs existing session resumption."""

    def test_no_session_id_creates_new_conversation(self, mock_llm_client, event_loop):
        """Test that connecting without session_id creates a new conversation each time."""
        mock_llm_client.call_llm = AsyncMock(return_value="Test response")

        # Two connections without session_id
        for _ in range(2):
            with patch("app.main.create_llm_client", return_value=mock_llm_client):
                with TestClient(app) as client:
                    with client.websocket_connect("/ws") as websocket:
                        websocket.receive_json()  # welcome
                        websocket.send_json({"type": "question", "question": "Hello"})
                        websocket.receive_json()

        # Should have 2 separate conversations
        async def check_database():
            async with TestDatabase.session_factory() as session:
                result = await session.execute(select(Conversation))
                conversations = result.scalars().all()
                assert len(conversations) == 2
                # Each should have different session_id
                assert conversations[0].session_id != conversations[1].session_id

        event_loop.run_until_complete(check_database())

    def test_invalid_session_id_creates_new_conversation(
        self, mock_llm_client, event_loop
    ):
        """Test that using a non-existent session_id creates a new conversation."""
        mock_llm_client.call_llm = AsyncMock(return_value="Test response")

        with patch("app.main.create_llm_client", return_value=mock_llm_client):
            with TestClient(app) as client:
                with client.websocket_connect(
                    "/ws?session_id=nonexistent-session-xyz"
                ) as websocket:
                    websocket.receive_json()  # welcome
                    websocket.send_json({"type": "question", "question": "Hello"})
                    websocket.receive_json()

        # Verify conversation was created with the provided session_id
        async def check_database():
            async with TestDatabase.session_factory() as session:
                result = await session.execute(select(Conversation))
                conv = result.scalar_one()
                assert conv.session_id == "nonexistent-session-xyz"

        event_loop.run_until_complete(check_database())
