"""Tests for User model."""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import User


class TestUserModel:
    """Tests for User model."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session):
        """Test creating a user."""
        username = "testuser"
        email = "test@example.com"
        password_hash = "hashed_password_123"

        user = User(username=username, email=email, password_hash=password_hash)

        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.id is not None
        assert user.username == username
        assert user.email == email
        assert user.password_hash == password_hash
        assert isinstance(user.created_at, datetime)

    @pytest.mark.asyncio
    async def test_user_username_unique(self, db_session):
        """Test that username must be unique."""
        username = "duplicate"

        # Create first user
        user1 = User(
            username=username, email="user1@example.com", password_hash="hash1"
        )
        db_session.add(user1)
        await db_session.commit()

        # Try to create second user with same username
        user2 = User(
            username=username, email="user2@example.com", password_hash="hash2"
        )
        db_session.add(user2)

        # Should raise IntegrityError due to unique constraint violation
        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_user_email_unique(self, db_session):
        """Test that email must be unique."""
        email = "duplicate@example.com"

        # Create first user
        user1 = User(username="user1", email=email, password_hash="hash1")
        db_session.add(user1)
        await db_session.commit()

        # Try to create second user with same email
        user2 = User(username="user2", email=email, password_hash="hash2")
        db_session.add(user2)

        # Should raise IntegrityError due to unique constraint violation
        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_user_repr(self, db_session):
        """Test user string representation."""
        username = "testuser"
        user = User(username=username, email="test@example.com", password_hash="hashed")

        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        repr_str = repr(user)
        assert "User" in repr_str
        assert str(user.id) in repr_str
        assert username in repr_str

    @pytest.mark.asyncio
    async def test_user_with_resume(self, db_session):
        """Test creating a user with resume content."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed",
            resume_filename="resume.pdf",
            resume_content="My resume content",
        )

        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.resume_filename == "resume.pdf"
        assert user.resume_content == "My resume content"
        assert user.chat_enabled is True

    @pytest.mark.asyncio
    async def test_user_chat_disabled(self, db_session):
        """Test creating a user with chat disabled."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed",
            chat_enabled=False,
        )

        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.chat_enabled is False
