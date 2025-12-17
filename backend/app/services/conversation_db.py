"""Database-backed conversation management."""

from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.db.models import Message
from app.db.repositories.conversation import ConversationRepository
from app.db.repositories.message import MessageRepository
from app.models.conversation import MessageRole

logger = get_logger(__name__)

# Valid message roles
VALID_ROLES = {"system", "user", "assistant"}


class DatabaseConversationManager:
    """Conversation manager with PostgreSQL persistence.

    Persists all conversation data to PostgreSQL with transaction control
    left to the caller.
    """

    def __init__(
        self,
        session: AsyncSession,
        session_id: str | None = None,
    ):
        """Initialize database conversation manager.

        Args:
            session: SQLAlchemy async session
            session_id: Optional session ID (generates new UUID if not provided)
        """
        self.session = session
        self.session_id = session_id or str(uuid4())
        self._conversation_id: UUID | None = None
        self._conversation_repo = ConversationRepository(session)
        self._message_repo = MessageRepository(session)

        logger.info(f"Manager initialized (session: {self.session_id})")

    async def _ensure_conversation(self) -> UUID:
        """Ensure conversation exists in database, creating if necessary.

        Returns:
            Conversation UUID
        """
        if self._conversation_id:
            return self._conversation_id

        conversation = await self._conversation_repo.get_by_session_id(self.session_id)

        if not conversation:
            conversation = await self._conversation_repo.create_conversation(
                session_id=self.session_id
            )

        self._conversation_id = conversation.id
        return self._conversation_id

    async def add_message(self, role: MessageRole, content: str) -> None:
        """Add a message to the conversation.

        Args:
            role: Message role (system, user, or assistant)
            content: Message content

        Raises:
            ValueError: If role is not valid

        Note:
            Caller must commit the transaction.
        """
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role}. Must be one of {VALID_ROLES}")

        conversation_id = await self._ensure_conversation()

        await self._message_repo.add_message(
            conversation_id=conversation_id, role=role, content=content
        )
        await self._conversation_repo.update_timestamp(conversation_id)

        logger.debug(f"Added {role} message ({len(content)} chars)")

    async def get_conversation(self) -> list[dict[str, str]]:
        """Get all messages in the conversation.

        Returns:
            List of message dictionaries with 'role' and 'content' keys
        """
        conversation_id = await self._ensure_conversation()
        messages = await self._message_repo.get_conversation_messages(conversation_id)
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    async def get_message_count(self) -> int:
        """Get the number of messages efficiently using a database count.

        Returns:
            Number of messages in the conversation
        """
        conversation_id = await self._ensure_conversation()

        stmt = select(func.count()).where(Message.conversation_id == conversation_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def clear(self) -> None:
        """Clear all messages by deleting the conversation.

        Note:
            Caller must commit the transaction.
        """
        if self._conversation_id:
            await self._conversation_repo.delete_conversation(self._conversation_id)
            self._conversation_id = None
            logger.info(f"Cleared conversation (session: {self.session_id})")
