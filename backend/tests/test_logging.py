import logging

from app.core.config import Settings
from app.core.logger import get_logger, setup_logging


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
