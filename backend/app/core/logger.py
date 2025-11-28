import logging
import sys
from app.core.config import Settings, settings


def setup_logging(config: Settings | None = None) -> None:
    """Configure application logging based on settings

    Args:
        config: Settings instance to use. If None, uses global settings.
    """
    cfg = config or settings

    # Determine log level based on debug setting
    log_level = logging.DEBUG if cfg.debug else logging.INFO

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
