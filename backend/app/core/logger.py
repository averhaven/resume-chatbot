import logging
import sys

from app.core.config import Settings, get_settings
from app.core.context import get_session_id


class ContextFormatter(logging.Formatter):
    """Custom formatter that includes session ID from context."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with context variables.

        Args:
            record: The log record to format

        Returns:
            Formatted log string with session_id
        """
        record.session_id = get_session_id()
        return super().format(record)


def setup_logging(config: Settings | None = None) -> None:
    """Configure application logging based on settings.

    Args:
        config: Settings instance to use. If None, gets settings from factory.
    """
    cfg = config or get_settings()

    # Determine log level from settings
    log_level = getattr(logging, cfg.log_level.upper(), logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to allow reconfiguration
    root_logger.handlers.clear()

    # Create and configure handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    formatter = ContextFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(session_id)s] %(message)s"
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Set specific log levels for third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module"""
    return logging.getLogger(name)
