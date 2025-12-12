"""Tests for MessageRepository."""

from uuid import uuid4

import pytest
import pytest_asyncio

from app.db.models import Conversation, Message
from app.db.repositories.message import MessageRepository


class TestMessageRepository:
    """Tests for MessageRepository CRUD operations."""

    @pytest_asyncio.fixture
    async def conversation(self, db_session):
        """Create a test conversation for each test."""
        conversation = Conversation(session_id=str(uuid4()))
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)
        return conversation

    @pytest.fixture
    def repo(self, db_session):
        """Create a MessageRepository for each test."""
        return MessageRepository(db_session)

    @pytest.mark.asyncio
    async def test_add_message(self, repo, conversation, db_session):
        """Test adding a message to a conversation."""
        message = await repo.add_message(
            conversation_id=conversation.id,
            role="user",
            content="Hello, world!",
        )

        assert message.id is not None
        assert message.conversation_id == conversation.id
        assert message.role == "user"
        assert message.content == "Hello, world!"
        assert message.tokens is None
        assert message.metadata_ is None

    @pytest.mark.asyncio
    async def test_add_message_with_tokens(self, repo, conversation, db_session):
        """Test adding a message with token count."""
        message = await repo.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content="Response",
            tokens=250,
        )

        assert message.tokens == 250

    @pytest.mark.asyncio
    async def test_add_message_with_metadata(self, repo, conversation, db_session):
        """Test adding a message with metadata."""
        metadata = {"model": "gpt-4", "temperature": 0.7}
        message = await repo.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content="Response",
            metadata_=metadata,
        )

        assert message.metadata_ == metadata

    @pytest.mark.asyncio
    async def test_add_multiple_messages(self, repo, conversation, db_session):
        """Test adding multiple messages to a conversation."""
        messages = []
        for i in range(3):
            msg = await repo.add_message(
                conversation_id=conversation.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )
            messages.append(msg)

        assert len(messages) == 3
        assert all(m.conversation_id == conversation.id for m in messages)

    @pytest.mark.asyncio
    async def test_get_conversation_messages_empty(self, repo, conversation, db_session):
        """Test getting messages for conversation with no messages."""
        messages = await repo.get_conversation_messages(conversation.id)

        assert messages == []

    @pytest.mark.asyncio
    async def test_get_conversation_messages(self, repo, conversation, db_session):
        """Test getting all messages for a conversation."""
        # Add messages
        await repo.add_message(
            conversation_id=conversation.id, role="user", content="Question 1"
        )
        await repo.add_message(
            conversation_id=conversation.id, role="assistant", content="Answer 1"
        )
        await repo.add_message(
            conversation_id=conversation.id, role="user", content="Question 2"
        )
        await db_session.commit()

        # Get messages
        messages = await repo.get_conversation_messages(conversation.id)

        assert len(messages) == 3
        assert all(isinstance(m, Message) for m in messages)
        assert all(m.conversation_id == conversation.id for m in messages)

    @pytest.mark.asyncio
    async def test_get_conversation_messages_ordered(self, repo, conversation, db_session):
        """Test that messages are ordered by created_at."""
        # Add messages in order
        await repo.add_message(
            conversation_id=conversation.id, role="user", content="First"
        )
        await db_session.commit()

        await repo.add_message(
            conversation_id=conversation.id, role="assistant", content="Second"
        )
        await db_session.commit()

        await repo.add_message(
            conversation_id=conversation.id, role="user", content="Third"
        )
        await db_session.commit()

        # Get messages
        messages = await repo.get_conversation_messages(conversation.id)

        # Should be ordered by created_at (oldest first)
        assert len(messages) == 3
        assert messages[0].content == "First"
        assert messages[1].content == "Second"
        assert messages[2].content == "Third"

    @pytest.mark.asyncio
    async def test_get_conversation_messages_different_conversations(
        self, repo, db_session
    ):
        """Test that messages are filtered by conversation ID."""
        # Create two conversations
        conv1 = Conversation(session_id=str(uuid4()))
        conv2 = Conversation(session_id=str(uuid4()))
        db_session.add_all([conv1, conv2])
        await db_session.commit()
        await db_session.refresh(conv1)
        await db_session.refresh(conv2)

        # Add messages to each
        await repo.add_message(
            conversation_id=conv1.id, role="user", content="Conv1 Message"
        )
        await repo.add_message(
            conversation_id=conv2.id, role="user", content="Conv2 Message"
        )
        await db_session.commit()

        # Get messages for conv1
        messages = await repo.get_conversation_messages(conv1.id)

        assert len(messages) == 1
        assert messages[0].content == "Conv1 Message"

    @pytest.mark.asyncio
    async def test_get_recent_messages_empty(self, repo, conversation, db_session):
        """Test getting recent messages when none exist."""
        messages = await repo.get_recent_messages(conversation.id, limit=5)

        assert messages == []

    @pytest.mark.asyncio
    async def test_get_recent_messages(self, repo, conversation, db_session):
        """Test getting N most recent messages."""
        # Add 5 messages
        for i in range(5):
            await repo.add_message(
                conversation_id=conversation.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )
        await db_session.commit()

        # Get 3 most recent
        messages = await repo.get_recent_messages(conversation.id, limit=3)

        assert len(messages) == 3
        # Should be in chronological order (oldest first)
        assert messages[0].content == "Message 2"
        assert messages[1].content == "Message 3"
        assert messages[2].content == "Message 4"

    @pytest.mark.asyncio
    async def test_get_recent_messages_limit_greater_than_total(
        self, repo, conversation, db_session
    ):
        """Test getting recent messages when limit is greater than total."""
        # Add 3 messages
        for i in range(3):
            await repo.add_message(
                conversation_id=conversation.id, role="user", content=f"Message {i}"
            )
        await db_session.commit()

        # Request 10 messages
        messages = await repo.get_recent_messages(conversation.id, limit=10)

        # Should get all 3 messages
        assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_get_recent_messages_returns_chronological_order(
        self, repo, conversation, db_session
    ):
        """Test that recent messages are returned in chronological order."""
        # Add 10 messages
        for i in range(10):
            await repo.add_message(
                conversation_id=conversation.id, role="user", content=f"Message {i}"
            )
        await db_session.commit()

        # Get 5 most recent
        messages = await repo.get_recent_messages(conversation.id, limit=5)

        # Should be messages 5-9 in chronological order (oldest first)
        assert len(messages) == 5
        assert messages[0].content == "Message 5"
        assert messages[1].content == "Message 6"
        assert messages[2].content == "Message 7"
        assert messages[3].content == "Message 8"
        assert messages[4].content == "Message 9"

    @pytest.mark.asyncio
    async def test_add_message_different_roles(self, repo, conversation, db_session):
        """Test adding messages with different valid roles."""
        roles = ["system", "user", "assistant"]

        for role in roles:
            message = await repo.add_message(
                conversation_id=conversation.id,
                role=role,
                content=f"Message from {role}",
            )
            assert message.role == role

        await db_session.commit()

        # Verify all messages were created
        messages = await repo.get_conversation_messages(conversation.id)
        assert len(messages) == 3
        assert {m.role for m in messages} == set(roles)
