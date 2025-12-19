"""Tests for token counting service."""

import pytest

from app.services.token_counter import (
    MESSAGE_OVERHEAD_TOKENS,
    TokenCounter,
)


class TestTokenCounter:
    """Tests for TokenCounter class."""

    def test_count_tokens_empty_string(self):
        """Empty string should return 0 tokens."""
        counter = TokenCounter()
        assert counter.count_tokens("") == 0

    def test_count_tokens_simple_text(self):
        """Simple text should return expected token count."""
        counter = TokenCounter()
        # "Hello world" is typically 2 tokens
        tokens = counter.count_tokens("Hello world")
        assert tokens > 0
        assert tokens == 2

    def test_count_tokens_longer_text(self):
        """Longer text should return more tokens."""
        counter = TokenCounter()
        short_tokens = counter.count_tokens("Hello")
        long_tokens = counter.count_tokens("Hello, how are you doing today?")
        assert long_tokens > short_tokens

    def test_count_tokens_unicode(self):
        """Unicode characters should be counted correctly."""
        counter = TokenCounter()
        tokens = counter.count_tokens("Hello 世界 🌍")
        assert tokens > 0

    def test_count_tokens_whitespace(self):
        """Whitespace should contribute to token count."""
        counter = TokenCounter()
        # Multiple spaces typically count as tokens
        tokens = counter.count_tokens("Hello    world")
        assert tokens > 0

    def test_count_tokens_special_characters(self):
        """Special characters should be counted."""
        counter = TokenCounter()
        tokens = counter.count_tokens("!@#$%^&*()")
        assert tokens > 0

    def test_count_tokens_multiline(self):
        """Multiline text should be counted correctly."""
        counter = TokenCounter()
        tokens = counter.count_tokens("Line 1\nLine 2\nLine 3")
        assert tokens > 0

    def test_count_tokens_code(self):
        """Code snippets should be tokenized."""
        counter = TokenCounter()
        code = "def hello(): return 'world'"
        tokens = counter.count_tokens(code)
        assert tokens > 0


class TestCountMessages:
    """Tests for count_messages method."""

    def test_count_messages_empty_list(self):
        """Empty message list should return 0."""
        counter = TokenCounter()
        assert counter.count_messages([]) == 0

    def test_count_messages_single_message(self):
        """Single message should include content tokens plus overhead."""
        counter = TokenCounter()
        messages = [{"role": "user", "content": "Hello"}]
        tokens = counter.count_messages(messages)
        content_tokens = counter.count_tokens("Hello")
        assert tokens == content_tokens + MESSAGE_OVERHEAD_TOKENS

    def test_count_messages_multiple_messages(self):
        """Multiple messages should accumulate tokens and overhead."""
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        tokens = counter.count_messages(messages)
        expected = (
            counter.count_tokens("Hello")
            + MESSAGE_OVERHEAD_TOKENS
            + counter.count_tokens("Hi there!")
            + MESSAGE_OVERHEAD_TOKENS
        )
        assert tokens == expected

    def test_count_messages_with_system_message(self):
        """System messages should be counted the same as others."""
        counter = TokenCounter()
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        tokens = counter.count_messages(messages)
        expected = (
            counter.count_tokens("You are a helpful assistant.")
            + MESSAGE_OVERHEAD_TOKENS
            + counter.count_tokens("Hello")
            + MESSAGE_OVERHEAD_TOKENS
        )
        assert tokens == expected

    def test_count_messages_empty_content(self):
        """Message with empty content should still count overhead."""
        counter = TokenCounter()
        messages = [{"role": "user", "content": ""}]
        tokens = counter.count_messages(messages)
        assert tokens == MESSAGE_OVERHEAD_TOKENS

    def test_count_messages_missing_content(self):
        """Message without content key should handle gracefully."""
        counter = TokenCounter()
        messages = [{"role": "user"}]
        tokens = counter.count_messages(messages)
        # Should just count overhead for missing content
        assert tokens == MESSAGE_OVERHEAD_TOKENS


class TestMessageOverheadTokens:
    """Tests for MESSAGE_OVERHEAD_TOKENS constant."""

    def test_message_overhead_tokens_value(self):
        """MESSAGE_OVERHEAD_TOKENS should be 4."""
        assert MESSAGE_OVERHEAD_TOKENS == 4

    def test_message_overhead_is_reasonable(self):
        """Overhead should be a small positive integer."""
        assert MESSAGE_OVERHEAD_TOKENS > 0
        assert MESSAGE_OVERHEAD_TOKENS < 10


class TestTokenCounterEncoding:
    """Tests for TokenCounter encoding initialization."""

    def test_default_encoding(self):
        """Default encoding should be cl100k_base."""
        counter = TokenCounter()
        # Verify the encoding is working by counting tokens
        tokens = counter.count_tokens("test")
        assert tokens > 0

    def test_custom_encoding(self):
        """Custom encoding should be accepted."""
        # p50k_base is another valid encoding
        counter = TokenCounter(encoding_name="p50k_base")
        tokens = counter.count_tokens("test")
        assert tokens > 0

    def test_invalid_encoding_raises(self):
        """Invalid encoding name should raise an error."""
        with pytest.raises(ValueError):
            TokenCounter(encoding_name="invalid_encoding_name")
