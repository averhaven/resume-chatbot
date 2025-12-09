import logging
from app.core.logger import setup_logging, get_logger
from app.core.config import Settings


def test_debug_mode_sets_debug_level():
    """Test that debug=True sets DEBUG log level"""
    setup_logging(Settings(debug=True))
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG


def test_production_mode_sets_info_level():
    """Test that debug=False sets INFO log level"""
    setup_logging(Settings(debug=False))
    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO


def test_get_logger_returns_logger():
    """Test that get_logger returns a logger instance"""
    logger = get_logger("my_module")
    assert logger.name == "my_module"
    assert isinstance(logger, logging.Logger)


def test_logging_reconfiguration():
    """Test that logging can be reconfigured with different settings"""
    # Configure with debug=True
    setup_logging(Settings(debug=True))
    assert logging.getLogger().level == logging.DEBUG

    # Reconfigure with debug=False
    setup_logging(Settings(debug=False))
    assert logging.getLogger().level == logging.INFO
