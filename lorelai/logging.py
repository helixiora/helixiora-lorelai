"""Centralized logging configuration for Lorelai.

This module provides consistent logging configuration across all Lorelai components,
including the Flask application and RQ workers.

Usage:
    from lorelai.logging import configure_logging
    configure_logging()
"""

import logging
import colorlog
import os


def get_log_level() -> int:
    """Get the log level from environment variable.

    Returns
    -------
    int
        The logging level to use (defaults to INFO if not set or invalid)
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    try:
        return getattr(logging, level_name)
    except AttributeError:
        # If an invalid level is specified, default to INFO
        return logging.INFO


def configure_logging(level=None):
    """Configure logging with consistent formatting and colors.

    This function sets up logging with the following features:
    - Colored output based on log level
    - Timestamp in HH:MM:SS format
    - Module name in yellow
    - Log level with appropriate color
    - Message with the actual log content

    Parameters
    ----------
    level : int, optional
        The logging level to use. If None, uses LOG_LEVEL env var (defaults to INFO)
    """
    # Use provided level or get from environment
    level = level if level is not None else get_log_level()

    root_logger = logging.getLogger()

    # Remove any existing handlers to avoid duplicate logs
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler with color formatting
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(asctime)s%(reset)s \
%(yellow)s%(name)s%(reset)s - %(message)s",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
            secondary_log_colors={},
            style="%",
            datefmt="%H:%M:%S",
        )
    )

    # Add handler to root logger and set level
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Also configure Flask's logger
    flask_logger = logging.getLogger("flask")
    flask_logger.setLevel(level)

    # Configure RQ logger
    rq_logger = logging.getLogger("rq")
    rq_logger.setLevel(level)

    # Configure SQLAlchemy logger
    sqlalchemy_logger = logging.getLogger("sqlalchemy")
    sqlalchemy_logger.setLevel(logging.WARNING)  # Keep SQLAlchemy at WARNING to reduce noise

    # Configure Werkzeug logger
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.setLevel(level)

    # Log the level we're using
    root_logger.debug("Logging configured with level: %s", logging.getLevelName(level))
