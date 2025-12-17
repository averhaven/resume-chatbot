"""Tests for conversation pruning functionality."""

import pytest

from app.services.prompts import prune_conversation_history
from app.services.token_counter import TokenCounter


class TestPruneConversationHistory:
    """Tests for prune_conversation_history function."""

    @pytest.fixture
    def token_counter(self):
        """Create a token counter instance."""
        return TokenCounter()

    def test_empty_history_returns_empty(self, token_counter):
        """Empty history should return empty list and 0 tokens removed."""
        pruned, removed = prune_conversation_history(
            history=[],
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=8000,
            min_exchanges=2,
            response_reserve=2000,
        )
        assert pruned == []
        assert removed == 0

    def test_history_within_budget_not_pruned(self, token_counter):
        """History within token budget should not be pruned."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        pruned, removed = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=8000,
            min_exchanges=2,
            response_reserve=2500,
        )
        assert len(pruned) == 2
        assert removed == 0

    def test_history_exceeding_budget_is_pruned(self, token_counter):
        """History exceeding token budget should be pruned."""
        # Create a history with many messages
        history = []
        for i in range(20):
            history.append({"role": "user", "content": f"Question {i} " * 50})
            history.append({"role": "assistant", "content": f"Answer {i} " * 50})

        # Use tight token limits to force pruning
        pruned, removed = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=500,
            max_tokens=2000,
            min_exchanges=2,
            response_reserve=500,
        )

        assert len(pruned) < len(history)
        assert removed > 0

    def test_minimum_exchanges_preserved(self, token_counter):
        """Minimum number of exchanges should be preserved even if over budget."""
        # Create history that exceeds budget but should keep minimum exchanges
        history = [
            {"role": "user", "content": "First question " * 100},
            {"role": "assistant", "content": "First answer " * 100},
            {"role": "user", "content": "Second question " * 100},
            {"role": "assistant", "content": "Second answer " * 100},
            {"role": "user", "content": "Third question " * 100},
            {"role": "assistant", "content": "Third answer " * 100},
        ]

        # Very tight budget but min_exchanges=2 should preserve 4 messages
        pruned, _ = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=500,  # Very tight
            min_exchanges=2,
            response_reserve=100,
        )

        # Should keep at least 4 messages (2 exchanges)
        assert len(pruned) >= 4

    def test_oldest_messages_removed_first(self, token_counter):
        """Oldest messages should be removed first during pruning."""
        history = [
            {"role": "user", "content": "First question " * 50},
            {"role": "assistant", "content": "First answer " * 50},
            {"role": "user", "content": "Second question " * 50},
            {"role": "assistant", "content": "Second answer " * 50},
            {"role": "user", "content": "Third question"},
            {"role": "assistant", "content": "Third answer"},
        ]

        # Tight budget to force some pruning
        pruned, _ = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=1000,
            min_exchanges=1,
            response_reserve=300,
        )

        # If pruned, later messages should be kept
        if len(pruned) < len(history):
            # The last messages should be preserved
            assert pruned[-1]["content"] == "Third answer"
            assert pruned[-2]["content"] == "Third question"

    def test_returns_copy_not_original(self, token_counter):
        """Pruning should return a copy, not modify the original."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        original_len = len(history)

        _pruned, _ = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=8000,
            min_exchanges=2,
            response_reserve=2000,
        )

        # Original should be unchanged
        assert len(history) == original_len

    def test_no_available_tokens_keeps_min_exchanges(self, token_counter):
        """When no tokens available, still keep min_exchanges for context."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "Good!"},
            {"role": "user", "content": "Great"},
            {"role": "assistant", "content": "Thanks!"},
        ]

        # System tokens + reserve exceed max
        pruned, removed = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=5000,
            max_tokens=5000,
            min_exchanges=2,
            response_reserve=2500,
        )

        # Should keep the most recent min_exchanges (2 exchanges = 4 messages)
        assert len(pruned) == 4
        # Should keep the most recent messages
        assert pruned[0]["content"] == "How are you?"
        assert pruned[-1]["content"] == "Thanks!"
        assert removed > 0

    def test_custom_min_exchanges(self, token_counter):
        """Custom min_exchanges should be respected."""
        history = []
        for i in range(10):
            history.append({"role": "user", "content": f"Question {i}"})
            history.append({"role": "assistant", "content": f"Answer {i}"})

        # Force pruning with min_exchanges=3
        pruned, _ = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=500,
            min_exchanges=3,
            response_reserve=100,
        )

        # Should keep at least 6 messages (3 exchanges)
        assert len(pruned) >= 6

    def test_custom_response_reserve(self, token_counter):
        """Custom response_reserve should affect available tokens."""
        history = []
        for i in range(10):
            history.append({"role": "user", "content": f"Question {i} " * 20})
            history.append({"role": "assistant", "content": f"Answer {i} " * 20})

        # Large response reserve
        pruned_large, _ = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=4000,
            min_exchanges=1,
            response_reserve=3000,  # Large reserve
        )

        # Small response reserve
        pruned_small, _ = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=4000,
            min_exchanges=1,
            response_reserve=500,  # Small reserve
        )

        # Small reserve should allow more history
        assert len(pruned_small) >= len(pruned_large)

    def test_single_exchange_within_budget(self, token_counter):
        """Single exchange within budget should be preserved."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]

        pruned, removed = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=8000,
            min_exchanges=2,
            response_reserve=2000,
        )

        assert len(pruned) == 2
        assert removed == 0


class TestPruneConversationHistoryEdgeCases:
    """Edge case tests for prune_conversation_history."""

    @pytest.fixture
    def token_counter(self):
        """Create a token counter instance."""
        return TokenCounter()

    def test_single_message_history(self, token_counter):
        """Single message history should be handled correctly."""
        history = [{"role": "user", "content": "Hello"}]

        pruned, _ = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=8000,
            min_exchanges=1,
            response_reserve=2000,
        )

        # Single message is less than min_exchanges * 2 (2 messages)
        # So it won't be pruned even if over budget
        assert len(pruned) <= 1

    def test_very_long_single_message(self, token_counter):
        """Very long single message should be handled."""
        # Create a message with many tokens
        long_content = "word " * 1000
        history = [
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": "Short response"},
        ]

        pruned, _ = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=2000,
            min_exchanges=1,
            response_reserve=500,
        )

        # Even if over budget, min_exchanges should preserve messages
        assert len(pruned) >= 2

    def test_zero_max_tokens_keeps_min_exchanges(self, token_counter):
        """Zero max_tokens should still keep min_exchanges for context."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]

        pruned, removed = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=0,
            max_tokens=0,
            min_exchanges=2,
            response_reserve=0,
        )

        # History is already <= min_exchanges, so keep all
        assert pruned == history
        assert removed == 0

    def test_messages_with_empty_content(self, token_counter):
        """Messages with empty content should be counted for overhead."""
        history = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": ""},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]

        pruned, _ = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=8000,
            min_exchanges=2,
            response_reserve=2000,
        )

        # All messages should be preserved if within budget
        assert len(pruned) == 4

    def test_only_user_messages(self, token_counter):
        """History with only user messages should be handled."""
        history = [
            {"role": "user", "content": "Question 1"},
            {"role": "user", "content": "Question 2"},
        ]

        pruned, _ = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=8000,
            min_exchanges=2,
            response_reserve=2000,
        )

        assert len(pruned) == 2

    def test_only_assistant_messages(self, token_counter):
        """History with only assistant messages should be handled."""
        history = [
            {"role": "assistant", "content": "Response 1"},
            {"role": "assistant", "content": "Response 2"},
        ]

        pruned, _ = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=8000,
            min_exchanges=2,
            response_reserve=2000,
        )

        assert len(pruned) == 2


class TestPruneConversationHistoryTokenCalculations:
    """Tests verifying token calculations in pruning."""

    @pytest.fixture
    def token_counter(self):
        """Create a token counter instance."""
        return TokenCounter()

    def test_tokens_removed_matches_removed_messages(self, token_counter):
        """Tokens removed should match the tokens of removed messages."""
        history = []
        for i in range(10):
            history.append({"role": "user", "content": f"Question {i} " * 30})
            history.append({"role": "assistant", "content": f"Answer {i} " * 30})

        original_tokens = token_counter.count_messages(history)

        pruned, tokens_removed = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=100,
            max_tokens=2000,
            min_exchanges=2,
            response_reserve=500,
        )

        pruned_tokens = token_counter.count_messages(pruned)

        # tokens_removed should equal the difference
        assert tokens_removed == original_tokens - pruned_tokens

    def test_pruned_history_fits_budget(self, token_counter):
        """Pruned history should fit within available token budget."""
        history = []
        for i in range(20):
            history.append({"role": "user", "content": f"Question {i} " * 50})
            history.append({"role": "assistant", "content": f"Answer {i} " * 50})

        system_tokens = 500
        max_tokens = 3000
        response_reserve = 1000
        available = max_tokens - system_tokens - response_reserve

        pruned, _ = prune_conversation_history(
            history=history,
            token_counter=token_counter,
            system_tokens=system_tokens,
            max_tokens=max_tokens,
            min_exchanges=2,
            response_reserve=response_reserve,
        )

        pruned_tokens = token_counter.count_messages(pruned)

        # Either fits budget OR is at minimum exchanges
        min_messages = 2 * 2  # min_exchanges * 2
        if len(pruned) > min_messages:
            assert pruned_tokens <= available
