import logging

from app.core.config import Settings
from app.core.context import session_id_var, set_session_id
from app.core.logger import ContextFormatter, get_logger, setup_logging


def test_debug_mode_sets_debug_level():
    """Test that log_level='DEBUG' sets DEBUG log level"""
    setup_logging(Settings(log_level="DEBUG"))
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG


def test_production_mode_sets_info_level():
    """Test that log_level='INFO' sets INFO log level"""
    setup_logging(Settings(log_level="INFO"))
    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO


def test_get_logger_returns_logger():
    """Test that get_logger returns a logger instance"""
    logger = get_logger("my_module")
    assert logger.name == "my_module"
    assert isinstance(logger, logging.Logger)


def test_logging_reconfiguration():
    """Test that logging can be reconfigured with different settings"""
    # Configure with DEBUG level
    setup_logging(Settings(log_level="DEBUG"))
    assert logging.getLogger().level == logging.DEBUG

    # Reconfigure with INFO level
    setup_logging(Settings(log_level="INFO"))
    assert logging.getLogger().level == logging.INFO


class TestContextFormatter:
    """Tests for ContextFormatter with session_id integration."""

    def test_context_formatter_includes_session_id(self):
        """Test that ContextFormatter adds session_id to log records."""
        formatter = ContextFormatter("%(session_id)s - %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )

        test_session = "test-session-abc"
        token = session_id_var.set(test_session)

        try:
            set_session_id(test_session)
            formatted = formatter.format(record)
            assert test_session in formatted
            assert "test message" in formatted
        finally:
            session_id_var.reset(token)

    def test_context_formatter_default_session_id(self):
        """Test that ContextFormatter uses default '-' when session_id not set."""
        formatter = ContextFormatter("[%(session_id)s] %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )

        # Ensure we're at default state by setting and resetting
        token = session_id_var.set("-")
        session_id_var.reset(token)

        formatted = formatter.format(record)
        assert "[-]" in formatted or formatted.startswith("-")

    def test_context_formatter_full_format(self):
        """Test ContextFormatter with the full production format string."""
        formatter = ContextFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(session_id)s] %(message)s"
        )
        record = logging.LogRecord(
            name="app.main",
            level=logging.INFO,
            pathname="main.py",
            lineno=10,
            msg="Received question",
            args=(),
            exc_info=None,
        )

        session_id = "550e8400-e29b-41d4-a716-446655440000"
        token = session_id_var.set(session_id)

        try:
            set_session_id(session_id)
            formatted = formatter.format(record)
            assert "app.main" in formatted
            assert "INFO" in formatted
            assert f"[{session_id}]" in formatted
            assert "Received question" in formatted
        finally:
            session_id_var.reset(token)

    def test_context_formatter_session_id_changes_between_records(self):
        """Test that formatter picks up session_id changes between log records."""
        formatter = ContextFormatter("[%(session_id)s] %(message)s")

        record1 = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="first",
            args=(),
            exc_info=None,
        )
        record2 = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="second",
            args=(),
            exc_info=None,
        )

        session1 = "session-1"
        session2 = "session-2"

        token1 = session_id_var.set(session1)
        try:
            set_session_id(session1)
            formatted1 = formatter.format(record1)
            assert f"[{session1}]" in formatted1

            set_session_id(session2)
            formatted2 = formatter.format(record2)
            assert f"[{session2}]" in formatted2
        finally:
            session_id_var.reset(token1)
