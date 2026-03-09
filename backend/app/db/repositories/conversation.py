"""Repository for Conversation CRUD operations."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logger import get_logger
from app.db.models import Conversation

logger = get_logger(__name__)


class ConversationRepository:
    """Repository for managing conversations in the database."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def create_conversation(
        self,
        session_id: str,
        title: str | None = None,
        metadata_: dict | None = None,
        user_id: UUID | None = None,
    ) -> Conversation:
        """Create a new conversation.

        Args:
            session_id: Unique session identifier
            title: Optional conversation title
            metadata_: Optional metadata dictionary
            user_id: Optional user ID for tenant isolation

        Returns:
            Created Conversation instance
        """
        conversation = Conversation(
            session_id=session_id, title=title, metadata_=metadata_, user_id=user_id
        )

        self.session.add(conversation)
        await self.session.flush()  # Get ID without committing

        logger.info(f"Created conversation: {conversation.id} (session: {session_id})")
        return conversation

    async def get_by_session_id(
        self, session_id: str, user_id: UUID | None = None
    ) -> Conversation | None:
        """Get conversation by session ID.

        Args:
            session_id: Session identifier
            user_id: Optional user ID filter for tenant isolation

        Returns:
            Conversation if found, None otherwise
        """
        stmt = (
            select(Conversation)
            .where(Conversation.session_id == session_id)
            .options(selectinload(Conversation.messages))  # Eager load messages
        )

        if user_id is not None:
            stmt = stmt.where(Conversation.user_id == user_id)

        result = await self.session.execute(stmt)
        conversation = result.scalar_one_or_none()

        if conversation:
            logger.debug(f"Found conversation: {conversation.id}")

        return conversation

    async def get_by_id(
        self, conversation_id: UUID, user_id: UUID | None = None
    ) -> Conversation | None:
        """Get conversation by ID.

        Args:
            conversation_id: Conversation UUID
            user_id: Optional user ID filter for tenant isolation

        Returns:
            Conversation if found, None otherwise
        """
        stmt = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )

        if user_id is not None:
            stmt = stmt.where(Conversation.user_id == user_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_conversations(
        self, limit: int = 50, offset: int = 0, user_id: UUID | None = None
    ) -> list[Conversation]:
        """List conversations ordered by most recent.

        Args:
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip
            user_id: Optional user ID filter for tenant isolation

        Returns:
            List of Conversation instances
        """
        stmt = (
            select(Conversation)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )

        if user_id is not None:
            stmt = stmt.where(Conversation.user_id == user_id)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_timestamp(
        self, conversation_id: UUID, user_id: UUID | None = None
    ) -> bool:
        """Update conversation's updated_at timestamp.

        Args:
            conversation_id: Conversation UUID
            user_id: Optional user ID filter for tenant isolation

        Returns:
            True if conversation was found and updated, False otherwise
        """
        stmt = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=datetime.now(UTC))
        )

        if user_id is not None:
            stmt = stmt.where(Conversation.user_id == user_id)

        result = await self.session.execute(stmt)
        return result.rowcount > 0  # type: ignore

    async def delete_conversation(
        self, conversation_id: UUID, user_id: UUID | None = None
    ) -> bool:
        """Delete a conversation and all its messages.

        Args:
            conversation_id: Conversation UUID
            user_id: Optional user ID filter for tenant isolation

        Returns:
            True if deleted, False if not found
        """
        conversation = await self.get_by_id(conversation_id, user_id=user_id)
        if conversation:
            await self.session.delete(conversation)
            await self.session.flush()
            logger.info(f"Deleted conversation: {conversation_id}")
            return True
        return False
