"""Tests for UserRepository."""

from uuid import uuid4

import pytest

from app.db.repositories.user import UserRepository


class TestUserRepository:
    """Tests for UserRepository CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session):
        """Test creating a user."""
        repo = UserRepository(db_session)

        user = await repo.create_user(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
        )

        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password_hash == "hashed_password"

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session):
        """Test getting user by ID."""
        repo = UserRepository(db_session)

        # Create user
        user = await repo.create_user(
            username="testuser", email="test@example.com", password_hash="hashed"
        )
        await db_session.commit()

        # Get by ID
        found_user = await repo.get_by_id(user.id)

        assert found_user is not None
        assert found_user.id == user.id
        assert found_user.username == user.username
        assert found_user.email == user.email

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, db_session):
        """Test getting user by ID when not found."""
        repo = UserRepository(db_session)

        user = await repo.get_by_id(uuid4())

        assert user is None

    @pytest.mark.asyncio
    async def test_get_by_username(self, db_session):
        """Test getting user by username."""
        repo = UserRepository(db_session)

        # Create user
        username = "testuser"
        await repo.create_user(
            username=username, email="test@example.com", password_hash="hashed"
        )
        await db_session.commit()

        # Get by username
        found_user = await repo.get_by_username(username)

        assert found_user is not None
        assert found_user.username == username

    @pytest.mark.asyncio
    async def test_get_by_username_not_found(self, db_session):
        """Test getting user by username when not found."""
        repo = UserRepository(db_session)

        user = await repo.get_by_username("nonexistent")

        assert user is None

    @pytest.mark.asyncio
    async def test_get_by_email(self, db_session):
        """Test getting user by email."""
        repo = UserRepository(db_session)

        # Create user
        email = "test@example.com"
        await repo.create_user(username="testuser", email=email, password_hash="hashed")
        await db_session.commit()

        # Get by email
        found_user = await repo.get_by_email(email)

        assert found_user is not None
        assert found_user.email == email

    @pytest.mark.asyncio
    async def test_get_by_email_not_found(self, db_session):
        """Test getting user by email when not found."""
        repo = UserRepository(db_session)

        user = await repo.get_by_email("nonexistent@example.com")

        assert user is None

    @pytest.mark.asyncio
    async def test_delete_user(self, db_session):
        """Test deleting a user."""
        repo = UserRepository(db_session)

        # Create user
        user = await repo.create_user(
            username="testuser", email="test@example.com", password_hash="hashed"
        )
        await db_session.commit()

        user_id = user.id

        # Delete user
        result = await repo.delete_user(user_id)
        await db_session.commit()

        assert result is True

        # Verify deletion
        deleted_user = await repo.get_by_id(user_id)
        assert deleted_user is None

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, db_session):
        """Test deleting non-existent user."""
        repo = UserRepository(db_session)

        result = await repo.delete_user(uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_update_resume(self, db_session):
        """Test updating user's resume."""
        repo = UserRepository(db_session)

        # Create user
        user = await repo.create_user(
            username="testuser", email="test@example.com", password_hash="hashed"
        )
        await db_session.commit()

        # Update resume
        result = await repo.update_resume(
            user.id, filename="resume.pdf", content="My resume content"
        )
        await db_session.commit()

        assert result is True

        # Verify update
        updated_user = await repo.get_by_id(user.id)
        assert updated_user.resume_filename == "resume.pdf"
        assert updated_user.resume_content == "My resume content"

    @pytest.mark.asyncio
    async def test_update_resume_not_found(self, db_session):
        """Test updating resume for non-existent user."""
        repo = UserRepository(db_session)

        result = await repo.update_resume(uuid4(), "resume.pdf", "content")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_chat_enabled(self, db_session):
        """Test updating user's chat enabled status."""
        repo = UserRepository(db_session)

        # Create user
        user = await repo.create_user(
            username="testuser", email="test@example.com", password_hash="hashed"
        )
        await db_session.commit()

        # Disable chat
        result = await repo.update_chat_enabled(user.id, False)
        await db_session.commit()

        assert result is True

        # Verify update
        updated_user = await repo.get_by_id(user.id)
        assert updated_user.chat_enabled is False

    @pytest.mark.asyncio
    async def test_update_chat_enabled_not_found(self, db_session):
        """Test updating chat enabled for non-existent user."""
        repo = UserRepository(db_session)

        result = await repo.update_chat_enabled(uuid4(), False)

        assert result is False
