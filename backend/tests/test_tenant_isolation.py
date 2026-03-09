"""Tests for tenant (user_id) isolation in conversations."""

from uuid import uuid4

import pytest

from app.db.models import User
from app.db.repositories.conversation import ConversationRepository
from app.services.conversation_db import DatabaseConversationManager


async def create_test_user(db_session, username: str | None = None) -> User:
    """Helper to create a test user and return it."""
    user = User(
        id=uuid4(),
        username=username or f"user-{uuid4().hex[:8]}",
        email=f"{uuid4().hex[:8]}@test.com",
        password_hash="hashed",
    )
    db_session.add(user)
    await db_session.flush()
    return user


class TestConversationRepositoryTenantIsolation:
    """Tests for user_id filtering in ConversationRepository."""

    @pytest.fixture
    def repo(self, db_session):
        return ConversationRepository(db_session)

    @pytest.mark.asyncio
    async def test_create_conversation_with_user_id(self, repo, db_session):
        """Creating a conversation with user_id sets the FK correctly."""
        user = await create_test_user(db_session)
        conv = await repo.create_conversation(session_id=str(uuid4()), user_id=user.id)
        assert conv.user_id == user.id

    @pytest.mark.asyncio
    async def test_create_conversation_without_user_id(self, repo, db_session):
        """Creating a conversation without user_id leaves it None (backward compat)."""
        conv = await repo.create_conversation(session_id=str(uuid4()))
        assert conv.user_id is None

    @pytest.mark.asyncio
    async def test_get_by_session_id_wrong_user_returns_none(self, repo, db_session):
        """get_by_session_id with wrong user_id returns None."""
        user_a = await create_test_user(db_session)
        user_b = await create_test_user(db_session)

        session_id = str(uuid4())
        await repo.create_conversation(session_id=session_id, user_id=user_a.id)
        await db_session.commit()

        # Correct user finds it
        assert await repo.get_by_session_id(session_id, user_id=user_a.id) is not None
        # Wrong user does not
        assert await repo.get_by_session_id(session_id, user_id=user_b.id) is None

    @pytest.mark.asyncio
    async def test_get_by_id_wrong_user_returns_none(self, repo, db_session):
        """get_by_id with wrong user_id returns None."""
        user_a = await create_test_user(db_session)
        user_b = await create_test_user(db_session)

        conv = await repo.create_conversation(
            session_id=str(uuid4()), user_id=user_a.id
        )
        await db_session.commit()

        assert await repo.get_by_id(conv.id, user_id=user_a.id) is not None
        assert await repo.get_by_id(conv.id, user_id=user_b.id) is None

    @pytest.mark.asyncio
    async def test_list_conversations_filtered_by_user(self, repo, db_session):
        """list_conversations returns only the given user's conversations."""
        user_a = await create_test_user(db_session)
        user_b = await create_test_user(db_session)

        for _ in range(3):
            await repo.create_conversation(session_id=str(uuid4()), user_id=user_a.id)
        for _ in range(2):
            await repo.create_conversation(session_id=str(uuid4()), user_id=user_b.id)
        await db_session.commit()

        assert len(await repo.list_conversations(user_id=user_a.id)) == 3
        assert len(await repo.list_conversations(user_id=user_b.id)) == 2

    @pytest.mark.asyncio
    async def test_list_conversations_no_user_returns_all(self, repo, db_session):
        """list_conversations without user_id returns all conversations."""
        user = await create_test_user(db_session)
        await repo.create_conversation(session_id=str(uuid4()), user_id=user.id)
        await repo.create_conversation(session_id=str(uuid4()))  # no user
        await db_session.commit()

        assert len(await repo.list_conversations()) == 2

    @pytest.mark.asyncio
    async def test_delete_conversation_wrong_user_returns_false(self, repo, db_session):
        """delete_conversation with wrong user_id returns False (no deletion)."""
        user_a = await create_test_user(db_session)
        user_b = await create_test_user(db_session)

        conv = await repo.create_conversation(
            session_id=str(uuid4()), user_id=user_a.id
        )
        await db_session.commit()

        # Wrong user cannot delete
        assert await repo.delete_conversation(conv.id, user_id=user_b.id) is False
        # Conversation still exists
        assert await repo.get_by_id(conv.id) is not None

    @pytest.mark.asyncio
    async def test_update_timestamp_wrong_user_returns_false(self, repo, db_session):
        """update_timestamp with wrong user_id returns False."""
        user_a = await create_test_user(db_session)
        user_b = await create_test_user(db_session)

        conv = await repo.create_conversation(
            session_id=str(uuid4()), user_id=user_a.id
        )
        await db_session.commit()

        assert await repo.update_timestamp(conv.id, user_id=user_b.id) is False
        assert await repo.update_timestamp(conv.id, user_id=user_a.id) is True


class TestDatabaseConversationManagerTenantIsolation:
    """Tests for user_id isolation in DatabaseConversationManager."""

    @pytest.mark.asyncio
    async def test_manager_creates_conversation_with_user_id(self, db_session):
        """Manager with user_id creates a conversation owned by that user."""
        user = await create_test_user(db_session)
        manager = DatabaseConversationManager(
            db_session, session_id=str(uuid4()), user_id=user.id
        )
        await manager.add_message("user", "Hello")

        repo = ConversationRepository(db_session)
        conv = await repo.get_by_id(manager._conversation_id)
        assert conv.user_id == user.id

    @pytest.mark.asyncio
    async def test_manager_without_user_id_backward_compat(self, db_session):
        """Manager without user_id still works (backward compatibility)."""
        manager = DatabaseConversationManager(db_session, session_id=str(uuid4()))
        await manager.add_message("user", "Hello")
        messages = await manager.get_conversation()
        assert len(messages) == 1

    @pytest.mark.asyncio
    async def test_manager_isolation_between_users(self, db_session):
        """Two managers with different user_ids don't see each other's conversations."""
        user_a = await create_test_user(db_session)
        user_b = await create_test_user(db_session)
        session_id = str(uuid4())

        # User A creates a conversation
        manager_a = DatabaseConversationManager(
            db_session, session_id=session_id, user_id=user_a.id
        )
        await manager_a.add_message("user", "User A message")

        # User B with same session_id should NOT find it — gets a new conversation
        manager_b = DatabaseConversationManager(
            db_session, session_id=f"{session_id}-b", user_id=user_b.id
        )
        messages_b = await manager_b.get_conversation()
        assert messages_b == []
