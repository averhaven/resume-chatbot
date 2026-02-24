"""Tests for multi-tenant model relationships."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import Conversation, User


class TestConversationUserRelationship:
    """Tests for Conversation relationships with User."""

    @pytest.mark.asyncio
    async def test_conversation_with_user(self, db_session):
        """Test creating a conversation linked to user."""
        # Create user
        user = User(
            username="testuser", email="user@example.com", password_hash="hashed"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Create conversation
        conversation = Conversation(session_id=str(uuid4()), user_id=user.id)
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        assert conversation.user_id == user.id

    @pytest.mark.asyncio
    async def test_conversation_cascade_delete_on_user(self, db_session):
        """Test that deleting user deletes conversations."""
        user = User(
            username="testuser", email="user@example.com", password_hash="hashed"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        conversation = Conversation(session_id=str(uuid4()), user_id=user.id)
        db_session.add(conversation)
        await db_session.commit()

        # Delete user
        await db_session.delete(user)
        await db_session.commit()

        # Check that conversation is also deleted
        stmt = select(Conversation).where(Conversation.id == conversation.id)
        result = await db_session.execute(stmt)
        deleted_conv = result.scalar_one_or_none()

        assert deleted_conv is None
