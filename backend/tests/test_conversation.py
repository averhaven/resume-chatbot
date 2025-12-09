"""Tests for conversation state management."""

import pytest

from app.services.conversation import ConversationManager, create_conversation_manager


class TestConversationMessage:
    """Tests for ConversationMessage class."""

    def test_to_dict(self):
        """Test converting message to dictionary."""
        from app.services.conversation import ConversationMessage

        msg = ConversationMessage("user", "Hello, world!")
        result = msg.to_dict()

        assert result == {"role": "user", "content": "Hello, world!"}


class TestConversationManager:
    """Tests for ConversationManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh conversation manager for each test."""
        mgr = ConversationManager()
        yield mgr
        # Clean up after each test
        mgr.clear()

    def test_initial_state(self, manager):
        """Test that manager starts with empty conversation."""
        assert manager.get_message_count() == 0
        assert manager.get_conversation() == []

    def test_add_message(self, manager):
        """Test adding messages to the conversation."""
        manager.add_message("user", "Hello")
        manager.add_message("assistant", "Hi there!")

        conversation = manager.get_conversation()
        assert len(conversation) == 2
        assert conversation[0] == {"role": "user", "content": "Hello"}
        assert conversation[1] == {"role": "assistant", "content": "Hi there!"}

    def test_get_conversation(self, manager):
        """Test retrieving conversation history."""
        manager.add_message("user", "Question 1")
        manager.add_message("assistant", "Answer 1")
        manager.add_message("user", "Question 2")

        conversation = manager.get_conversation()

        assert len(conversation) == 3
        assert all(isinstance(msg, dict) for msg in conversation)
        assert all("role" in msg and "content" in msg for msg in conversation)

    def test_get_conversation_empty(self, manager):
        """Test getting conversation when empty returns empty list."""
        conversation = manager.get_conversation()
        assert conversation == []

    def test_clear(self, manager):
        """Test clearing the conversation."""
        manager.add_message("user", "Hello")
        manager.add_message("assistant", "Hi!")
        assert manager.get_message_count() == 2

        manager.clear()

        assert manager.get_message_count() == 0
        assert manager.get_conversation() == []

    def test_clear_empty_conversation(self, manager):
        """Test clearing empty conversation doesn't raise error."""
        # Should not raise any error
        manager.clear()
        assert manager.get_message_count() == 0

    def test_get_message_count(self, manager):
        """Test getting the number of messages."""
        assert manager.get_message_count() == 0

        manager.add_message("user", "Hello")
        assert manager.get_message_count() == 1

        manager.add_message("assistant", "Hi!")
        assert manager.get_message_count() == 2

        manager.add_message("user", "How are you?")
        assert manager.get_message_count() == 3

    def test_multiple_message_types(self, manager):
        """Test adding messages with different roles."""
        manager.add_message("system", "System message")
        manager.add_message("user", "User message")
        manager.add_message("assistant", "Assistant message")

        conversation = manager.get_conversation()
        assert len(conversation) == 3
        assert conversation[0]["role"] == "system"
        assert conversation[1]["role"] == "user"
        assert conversation[2]["role"] == "assistant"


class TestCreateConversationManager:
    """Tests for create_conversation_manager factory function."""

    def test_creates_new_instance(self):
        """Test that factory creates a new ConversationManager instance."""
        manager = create_conversation_manager()

        assert isinstance(manager, ConversationManager)
        assert manager.get_message_count() == 0

    def test_creates_independent_instances(self):
        """Test that each call creates an independent instance."""
        manager1 = create_conversation_manager()
        manager2 = create_conversation_manager()

        # They should be different instances
        assert manager1 is not manager2

        # Changes to one should not affect the other
        manager1.add_message("user", "Message in manager1")
        assert manager1.get_message_count() == 1
        assert manager2.get_message_count() == 0
