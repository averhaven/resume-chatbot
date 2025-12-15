"""Tests for session context management."""

import contextvars

from app.core.context import get_session_id, session_id_var, set_session_id


class TestSessionIdContext:
    """Tests for session_id context variable management."""

    def test_get_session_id_default(self):
        """Test that get_session_id returns default value when not set."""
        # Create a new context to ensure clean state
        ctx = contextvars.copy_context()
        result = ctx.run(get_session_id)
        assert result == "-"

    def test_set_session_id(self):
        """Test that set_session_id sets the value in context."""
        test_id = "test-session-123"
        token = session_id_var.set(test_id)

        try:
            set_session_id(test_id)
            assert get_session_id() == test_id
        finally:
            session_id_var.reset(token)

    def test_session_id_with_uuid_format(self):
        """Test that session_id works with UUID-formatted strings."""
        uuid_id = "550e8400-e29b-41d4-a716-446655440000"
        token = session_id_var.set(uuid_id)

        try:
            set_session_id(uuid_id)
            assert get_session_id() == uuid_id
        finally:
            session_id_var.reset(token)

    def test_session_id_overwrites_previous(self):
        """Test that setting session_id overwrites the previous value."""
        ctx = contextvars.copy_context()

        def run_test():
            set_session_id("first")
            assert get_session_id() == "first"

            set_session_id("second")
            assert get_session_id() == "second"

        ctx.run(run_test)
