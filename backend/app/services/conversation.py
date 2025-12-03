"""Conversation state management for tracking chat history."""

from typing import Literal

from app.core.logger import get_logger

logger = get_logger(__name__)

# Type alias for message roles
MessageRole = Literal["system", "user", "assistant"]


class ConversationMessage:
    """A single message in a conversation."""

    def __init__(self, role: MessageRole, content: str):
        """Initialize a conversation message.

        Args:
            role: Message role (system, user, or assistant)
            content: Message content
        """
        self.role = role
        self.content = content

    def to_dict(self) -> dict[str, str]:
        """Convert message to dictionary format for LLM API.

        Returns:
            Dictionary with 'role' and 'content' keys
        """
        return {"role": self.role, "content": self.content}


class ConversationManager:
    """Manages conversation state for a single user.

    This is a simplified conversation manager that maintains one conversation
    history. Suitable for single-user applications like a personal resume chatbot.
    """

    def __init__(self):
        """Initialize the conversation manager with an empty conversation."""
        self._messages: list[ConversationMessage] = []
        logger.info("Conversation manager initialized")

    def add_message(self, role: MessageRole, content: str) -> None:
        """Add a message to the conversation.

        Args:
            role: Message role (system, user, or assistant)
            content: Message content
        """
        message = ConversationMessage(role, content)
        self._messages.append(message)
        logger.debug(f"Added {role} message ({len(content)} chars)")

    def get_conversation(self) -> list[dict[str, str]]:
        """Get all messages in the conversation.

        Returns:
            List of message dictionaries with 'role' and 'content' keys
        """
        return [msg.to_dict() for msg in self._messages]

    def clear(self) -> None:
        """Clear all messages from the conversation."""
        message_count = len(self._messages)
        self._messages = []
        logger.info(f"Cleared conversation ({message_count} messages)")

    def get_message_count(self) -> int:
        """Get the number of messages in the conversation.

        Returns:
            Number of messages
        """
        return len(self._messages)


def create_conversation_manager() -> ConversationManager:
    """Create a new conversation manager instance.

    Returns:
        ConversationManager instance
    """
    return ConversationManager()
