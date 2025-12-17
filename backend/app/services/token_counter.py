"""Token counting service for tracking token usage."""

import tiktoken

from app.core.logger import get_logger

logger = get_logger(__name__)

# Token overhead per message in OpenAI-compatible format
# Each message has role, content, and structural tokens
MESSAGE_OVERHEAD_TOKENS = 4


class TokenCounter:
    """Service for counting tokens in text and message lists.

    Uses tiktoken with cl100k_base encoding (compatible with GPT-4/Claude).
    """

    def __init__(self, encoding_name: str = "cl100k_base"):
        """Initialize token counter with specified encoding.

        Args:
            encoding_name: Name of the tiktoken encoding to use.
                          Default is "cl100k_base" (GPT-4/Claude compatible).
        """
        self.encoding = tiktoken.get_encoding(encoding_name)
        logger.debug(f"TokenCounter initialized with encoding: {encoding_name}")

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens in the text
        """
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def count_messages(self, messages: list[dict[str, str]]) -> int:
        """Count total tokens in a list of messages.

        Includes per-message overhead for message structure (role, separators).

        Args:
            messages: List of message dicts with 'role' and 'content' keys

        Returns:
            Total token count including overhead
        """
        total = 0
        for message in messages:
            # Count content tokens
            content = message.get("content", "")
            total += self.count_tokens(content)

            # Add overhead for message structure (role + formatting)
            total += MESSAGE_OVERHEAD_TOKENS

        return total
