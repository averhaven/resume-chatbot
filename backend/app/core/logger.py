import logging
import sys

from app.core.config import Settings, get_settings


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
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Set specific log levels for third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module"""
    return logging.getLogger(name)
