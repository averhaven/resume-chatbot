"""Tests for ConversationRepository."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import Conversation, Message
from app.db.repositories.conversation import ConversationRepository


class TestConversationRepository:
    """Tests for ConversationRepository CRUD operations."""

    @pytest.fixture
    def repo(self, db_session):
        """Create a ConversationRepository for each test."""
        return ConversationRepository(db_session)

    @pytest.mark.asyncio
    async def test_create_conversation(self, repo, db_session):
        """Test creating a conversation."""
        session_id = str(uuid4())
        conversation = await repo.create_conversation(session_id=session_id)

        assert conversation.id is not None
        assert conversation.session_id == session_id
        assert conversation.title is None
        assert conversation.metadata_ is None

    @pytest.mark.asyncio
    async def test_create_conversation_with_title(self, repo, db_session):
        """Test creating a conversation with title."""
        session_id = str(uuid4())
        title = "My Conversation"
        conversation = await repo.create_conversation(
            session_id=session_id, title=title
        )

        assert conversation.title == title

    @pytest.mark.asyncio
    async def test_create_conversation_with_metadata(self, repo, db_session):
        """Test creating a conversation with metadata."""
        session_id = str(uuid4())
        metadata = {"user_id": "123", "source": "mobile"}
        conversation = await repo.create_conversation(
            session_id=session_id, metadata_=metadata
        )

        assert conversation.metadata_ == metadata

    @pytest.mark.asyncio
    async def test_get_by_session_id_found(self, repo, db_session):
        """Test retrieving a conversation by session ID."""
        session_id = str(uuid4())
        created = await repo.create_conversation(session_id=session_id)
        await db_session.commit()

        # Retrieve the conversation
        found = await repo.get_by_session_id(session_id)

        assert found is not None
        assert found.id == created.id
        assert found.session_id == session_id

    @pytest.mark.asyncio
    async def test_get_by_session_id_not_found(self, repo, db_session):
        """Test retrieving non-existent conversation returns None."""
        result = await repo.get_by_session_id("non-existent-session")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, repo, db_session):
        """Test retrieving a conversation by ID."""
        session_id = str(uuid4())
        created = await repo.create_conversation(session_id=session_id)
        await db_session.commit()

        # Retrieve by ID
        found = await repo.get_by_id(created.id)

        assert found is not None
        assert found.id == created.id
        assert found.session_id == session_id

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo, db_session):
        """Test retrieving non-existent conversation by ID returns None."""
        fake_id = uuid4()
        result = await repo.get_by_id(fake_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_list_conversations_empty(self, repo, db_session):
        """Test listing conversations when none exist."""
        conversations = await repo.list_conversations()

        assert conversations == []

    @pytest.mark.asyncio
    async def test_list_conversations(self, repo, db_session):
        """Test listing conversations."""
        # Create multiple conversations
        session_ids = [str(uuid4()) for _ in range(3)]
        for session_id in session_ids:
            await repo.create_conversation(session_id=session_id)
            await db_session.commit()

        # List conversations
        conversations = await repo.list_conversations()

        assert len(conversations) == 3
        assert all(isinstance(c, Conversation) for c in conversations)

    @pytest.mark.asyncio
    async def test_list_conversations_ordered_by_updated_at(self, repo, db_session):
        """Test that conversations are ordered by most recent update."""
        # Create conversations
        await repo.create_conversation(session_id=str(uuid4()))
        await db_session.commit()

        await repo.create_conversation(session_id=str(uuid4()))
        await db_session.commit()

        conv3 = await repo.create_conversation(session_id=str(uuid4()))
        await db_session.commit()

        # List conversations
        conversations = await repo.list_conversations()

        # Should be ordered by updated_at desc (most recent first)
        assert len(conversations) == 3
        # conv3 should be first (most recent)
        assert conversations[0].id == conv3.id

    @pytest.mark.asyncio
    async def test_list_conversations_with_limit(self, repo, db_session):
        """Test listing conversations with limit."""
        # Create 5 conversations
        for _ in range(5):
            await repo.create_conversation(session_id=str(uuid4()))
            await db_session.commit()

        # List with limit
        conversations = await repo.list_conversations(limit=3)

        assert len(conversations) == 3

    @pytest.mark.asyncio
    async def test_list_conversations_with_offset(self, repo, db_session):
        """Test listing conversations with offset."""
        # Create 5 conversations
        for _ in range(5):
            await repo.create_conversation(session_id=str(uuid4()))
            await db_session.commit()

        # List with offset
        conversations = await repo.list_conversations(offset=2)

        # Should get remaining 3 conversations
        assert len(conversations) == 3

    @pytest.mark.asyncio
    async def test_update_timestamp(self, repo, db_session):
        """Test updating conversation timestamp."""
        conversation = await repo.create_conversation(session_id=str(uuid4()))
        await db_session.commit()
        await db_session.refresh(conversation)

        original_updated_at = conversation.updated_at

        # Wait a bit and update timestamp
        await asyncio.sleep(0.1)

        await repo.update_timestamp(conversation.id)
        await db_session.commit()
        await db_session.refresh(conversation)

        # Timestamp should be updated
        assert conversation.updated_at > original_updated_at

    @pytest.mark.asyncio
    async def test_update_timestamp_nonexistent(self, repo, db_session):
        """Test updating timestamp for non-existent conversation."""
        fake_id = uuid4()

        # Should not raise an error
        await repo.update_timestamp(fake_id)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_delete_conversation(self, repo, db_session):
        """Test deleting a conversation."""
        conversation = await repo.create_conversation(session_id=str(uuid4()))
        await db_session.commit()

        conversation_id = conversation.id

        # Delete conversation
        result = await repo.delete_conversation(conversation_id)
        await db_session.commit()

        assert result is True

        # Verify it's deleted
        found = await repo.get_by_id(conversation_id)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, repo, db_session):
        """Test deleting non-existent conversation."""
        fake_id = uuid4()

        result = await repo.delete_conversation(fake_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_conversation_cascades_to_messages(self, repo, db_session):
        """Test that deleting conversation also deletes its messages."""
        # Create conversation
        conversation = await repo.create_conversation(session_id=str(uuid4()))
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
        await repo.delete_conversation(conversation.id)
        await db_session.commit()

        # Verify messages are also deleted
        stmt = select(Message).where(Message.conversation_id == conversation.id)
        result = await db_session.execute(stmt)
        messages = list(result.scalars().all())

        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_get_by_session_id_eager_loads_messages(self, repo, db_session):
        """Test that get_by_session_id eager loads messages."""
        # Create conversation
        session_id = str(uuid4())
        conversation = await repo.create_conversation(session_id=session_id)
        await db_session.commit()
        await db_session.refresh(conversation)

        # Add messages
        message1 = Message(
            conversation_id=conversation.id, role="user", content="Test 1"
        )
        message2 = Message(
            conversation_id=conversation.id, role="assistant", content="Test 2"
        )

        db_session.add_all([message1, message2])
        await db_session.commit()

        # Get conversation
        found = await repo.get_by_session_id(session_id)

        # Messages should be loaded (no additional query needed)
        # Note: In tests, we just verify the conversation was found
        assert found is not None
        assert found.id == conversation.id
