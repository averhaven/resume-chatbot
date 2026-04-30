"""Repository for Message CRUD operations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.db.models import Conversation, Message

logger = get_logger(__name__)


class MessageRepository:
    """Repository for managing messages in the database."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        tokens: int | None = None,
        metadata_: dict | None = None,
    ) -> Message:
        """Add a message to a conversation.

        Args:
            conversation_id: Conversation UUID
            role: Message role ('system', 'user', 'assistant')
            content: Message content
            tokens: Optional token count
            metadata_: Optional metadata dictionary

        Returns:
            Created Message instance
        """
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tokens=tokens,
            metadata_=metadata_,
        )

        self.session.add(message)
        await self.session.flush()

        logger.debug(f"Added {role} message to conversation {conversation_id}")
        return message

    async def get_conversation_messages(self, conversation_id: UUID) -> list[Message]:
        """Get all messages for a conversation.

        Args:
            conversation_id: Conversation UUID

        Returns:
            List of Message instances ordered by created_at
        """
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_user_messages(self, user_id: UUID) -> int:
        """Count all messages belonging to a user's conversations.

        Args:
            user_id: User ID to filter by (via conversation ownership)

        Returns:
            Total message count for the user
        """
        stmt = (
            select(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_user_messages_since(self, user_id: UUID, since: datetime) -> int:
        """Count messages belonging to a user created since a given datetime.

        Args:
            user_id: User ID to filter by
            since: Datetime lower bound (inclusive)

        Returns:
            Count of messages created since the given datetime
        """
        stmt = (
            select(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.user_id == user_id)
            .where(Message.created_at >= since)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_recent_messages(
        self, conversation_id: UUID, limit: int
    ) -> list[Message]:
        """Get the N most recent messages for a conversation.

        Args:
            conversation_id: Conversation UUID
            limit: Number of messages to return

        Returns:
            List of Message instances (most recent last)
        """
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        messages = list(result.scalars().all())

        # Reverse to get chronological order (oldest first)
        return list(reversed(messages))
