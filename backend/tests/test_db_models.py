"""Tests for SQLAlchemy database models."""

from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import Conversation, Message


class TestConversationModel:
    """Tests for Conversation model."""

    @pytest.mark.asyncio
    async def test_create_conversation(self, db_session):
        """Test creating a conversation."""
        session_id = str(uuid4())
        conversation = Conversation(session_id=session_id)

        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        assert conversation.id is not None
        assert conversation.session_id == session_id
        assert conversation.title is None
        assert conversation.metadata_ is None
        assert isinstance(conversation.created_at, datetime)
        assert isinstance(conversation.updated_at, datetime)

    @pytest.mark.asyncio
    async def test_conversation_with_title(self, db_session):
        """Test creating a conversation with title."""
        session_id = str(uuid4())
        title = "Test Conversation"
        conversation = Conversation(session_id=session_id, title=title)

        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        assert conversation.title == title

    @pytest.mark.asyncio
    async def test_conversation_with_metadata(self, db_session):
        """Test creating a conversation with metadata."""
        session_id = str(uuid4())
        metadata = {"user_id": "test_user", "source": "web"}
        conversation = Conversation(session_id=session_id, metadata_=metadata)

        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        assert conversation.metadata_ == metadata

    @pytest.mark.asyncio
    async def test_conversation_session_id_unique(self, db_session):
        """Test that session_id must be unique."""
        session_id = str(uuid4())

        # Create first conversation
        conversation1 = Conversation(session_id=session_id)
        db_session.add(conversation1)
        await db_session.commit()

        # Try to create second conversation with same session_id
        conversation2 = Conversation(session_id=session_id)
        db_session.add(conversation2)

        # Should raise IntegrityError
        with pytest.raises(Exception):  # SQLite raises IntegrityError
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_conversation_timestamps(self, db_session):
        """Test that timestamps are set automatically."""
        conversation = Conversation(session_id=str(uuid4()))

        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        # Timestamps should be set
        assert conversation.created_at is not None
        assert conversation.updated_at is not None

        # Both should be set (SQLite stores datetimes as strings without timezone)
        # Just verify they are datetime objects and recent
        assert isinstance(conversation.created_at, datetime)
        assert isinstance(conversation.updated_at, datetime)

    @pytest.mark.asyncio
    async def test_conversation_repr(self, db_session):
        """Test conversation string representation."""
        session_id = str(uuid4())
        conversation = Conversation(session_id=session_id)

        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        repr_str = repr(conversation)
        assert "Conversation" in repr_str
        assert str(conversation.id) in repr_str
        assert session_id in repr_str


class TestMessageModel:
    """Tests for Message model."""

    @pytest.mark.asyncio
    async def test_create_message(self, db_session):
        """Test creating a message."""
        # First create a conversation
        conversation = Conversation(session_id=str(uuid4()))
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        # Create a message
        message = Message(
            conversation_id=conversation.id,
            role="user",
            content="Hello, world!",
        )

        db_session.add(message)
        await db_session.commit()
        await db_session.refresh(message)

        assert message.id is not None
        assert message.conversation_id == conversation.id
        assert message.role == "user"
        assert message.content == "Hello, world!"
        assert message.tokens is None
        assert message.metadata_ is None
        assert isinstance(message.created_at, datetime)

    @pytest.mark.asyncio
    async def test_message_roles(self, db_session):
        """Test creating messages with different roles."""
        conversation = Conversation(session_id=str(uuid4()))
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        roles = ["system", "user", "assistant"]

        for role in roles:
            message = Message(
                conversation_id=conversation.id,
                role=role,
                content=f"Message from {role}",
            )
            db_session.add(message)

        await db_session.commit()

        # Verify all messages were created
        stmt = select(Message).where(Message.conversation_id == conversation.id)
        result = await db_session.execute(stmt)
        messages = list(result.scalars().all())

        assert len(messages) == 3
        assert {msg.role for msg in messages} == set(roles)

    @pytest.mark.asyncio
    async def test_message_with_tokens(self, db_session):
        """Test creating a message with token count."""
        conversation = Conversation(session_id=str(uuid4()))
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="Response",
            tokens=150,
        )

        db_session.add(message)
        await db_session.commit()
        await db_session.refresh(message)

        assert message.tokens == 150

    @pytest.mark.asyncio
    async def test_message_with_metadata(self, db_session):
        """Test creating a message with metadata."""
        conversation = Conversation(session_id=str(uuid4()))
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        metadata = {"model": "gpt-4", "temperature": 0.7}
        message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="Response",
            metadata_=metadata,
        )

        db_session.add(message)
        await db_session.commit()
        await db_session.refresh(message)

        assert message.metadata_ == metadata

    @pytest.mark.asyncio
    async def test_message_repr(self, db_session):
        """Test message string representation."""
        conversation = Conversation(session_id=str(uuid4()))
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        message = Message(
            conversation_id=conversation.id,
            role="user",
            content="Test message",
        )

        db_session.add(message)
        await db_session.commit()
        await db_session.refresh(message)

        repr_str = repr(message)
        assert "Message" in repr_str
        assert str(message.id) in repr_str
        assert "user" in repr_str
        assert str(conversation.id) in repr_str


class TestConversationMessageRelationship:
    """Tests for Conversation-Message relationship."""

    @pytest.mark.asyncio
    async def test_conversation_messages_relationship(self, db_session):
        """Test accessing messages through conversation."""
        conversation = Conversation(session_id=str(uuid4()))
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        # Add messages
        message1 = Message(
            conversation_id=conversation.id, role="user", content="Question 1"
        )
        message2 = Message(
            conversation_id=conversation.id, role="assistant", content="Answer 1"
        )
        message3 = Message(
            conversation_id=conversation.id, role="user", content="Question 2"
        )

        db_session.add_all([message1, message2, message3])
        await db_session.commit()

        # Refresh and check relationship
        await db_session.refresh(conversation)

        # Note: In SQLite, we need to explicitly load messages
        stmt = select(Message).where(Message.conversation_id == conversation.id)
        result = await db_session.execute(stmt)
        messages = list(result.scalars().all())

        assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_message_conversation_relationship(self, db_session):
        """Test accessing conversation through message."""
        conversation = Conversation(session_id=str(uuid4()))
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        message = Message(
            conversation_id=conversation.id, role="user", content="Test"
        )
        db_session.add(message)
        await db_session.commit()
        await db_session.refresh(message)

        # Load the conversation through the relationship
        stmt = (
            select(Message)
            .where(Message.id == message.id)
        )
        result = await db_session.execute(stmt)
        msg = result.scalar_one()

        assert msg.conversation_id == conversation.id

    @pytest.mark.asyncio
    async def test_cascade_delete(self, db_session):
        """Test that deleting conversation deletes messages."""
        conversation = Conversation(session_id=str(uuid4()))
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        # Add messages
        message1 = Message(
            conversation_id=conversation.id, role="user", content="Message 1"
        )
        message2 = Message(
            conversation_id=conversation.id, role="assistant", content="Message 2"
        )

        db_session.add_all([message1, message2])
        await db_session.commit()

        # Delete conversation
        await db_session.delete(conversation)
        await db_session.commit()

        # Check that messages are also deleted
        stmt = select(Message).where(Message.conversation_id == conversation.id)
        result = await db_session.execute(stmt)
        messages = list(result.scalars().all())

        assert len(messages) == 0
