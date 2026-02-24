"""Repository for User CRUD operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.db.models import User

logger = get_logger(__name__)


class UserRepository:
    """Repository for managing users in the database."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def create_user(
        self,
        username: str,
        email: str,
        password_hash: str,
    ) -> User:
        """Create a new user.

        Args:
            username: Username (must be unique)
            email: User email address (must be unique)
            password_hash: Hashed password

        Returns:
            Created User instance
        """
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
        )

        self.session.add(user)
        await self.session.flush()  # Get ID without committing

        logger.info(f"Created user: {user.id} (username: {username})")
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID.

        Args:
            user_id: User UUID

        Returns:
            User if found, None otherwise
        """
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username.

        Args:
            username: Username

        Returns:
            User if found, None otherwise
        """
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            logger.debug(f"Found user by username: {user.id}")

        return user

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email.

        Args:
            email: User email address

        Returns:
            User if found, None otherwise
        """
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            logger.debug(f"Found user by email: {user.id}")

        return user

    async def update_resume(self, user_id: UUID, filename: str, content: str) -> bool:
        """Update user's resume.

        Args:
            user_id: User UUID
            filename: Resume filename
            content: Resume content

        Returns:
            True if user was found and updated, False otherwise
        """
        user = await self.get_by_id(user_id)
        if user:
            user.resume_filename = filename
            user.resume_content = content
            await self.session.flush()
            logger.info(f"Updated resume for user {user_id}")
            return True
        return False

    async def update_chat_enabled(self, user_id: UUID, enabled: bool) -> bool:
        """Update user's chat enabled status.

        Args:
            user_id: User UUID
            enabled: Whether chat is enabled

        Returns:
            True if user was found and updated, False otherwise
        """
        user = await self.get_by_id(user_id)
        if user:
            user.chat_enabled = enabled
            await self.session.flush()
            logger.info(f"Updated chat_enabled for user {user_id}: {enabled}")
            return True
        return False

    async def delete_user(self, user_id: UUID) -> bool:
        """Delete a user and all associated data.

        Args:
            user_id: User UUID

        Returns:
            True if deleted, False if not found
        """
        user = await self.get_by_id(user_id)
        if user:
            await self.session.delete(user)
            await self.session.flush()
            logger.info(f"Deleted user: {user_id}")
            return True
        return False
