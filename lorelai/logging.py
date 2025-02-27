"""Centralized logging configuration for Lorelai.

This module provides consistent logging configuration across all Lorelai components,
including the Flask application and RQ workers.

Usage:
    from lorelai.logging import configure_logging
    configure_logging()
"""

import logging
import os
import sys
from logging.config import dictConfig


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


def configure_logging(app=None, log_level=None):
    """Configure logging for the application.

    Parameters
    ----------
    app : Flask
        The Flask application instance.
    log_level : str
        The log level to use.
    """
    if app:
        log_level = log_level or app.config.get("LOG_LEVEL", "INFO")
    else:
        log_level = log_level or "INFO"

    # Define the logging configuration
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                # Update the formatter to include file name and line number
                "format": (
                    "%(levelname)-8s %(asctime)s %(name)s [%(filename)s:%(lineno)d] - %(message)s"
                ),
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "standard",
                "stream": sys.stdout,
            },
        },
        "loggers": {
            "": {  # Root logger
                "handlers": ["console"],
                "level": log_level,
                "propagate": True,
            },
            # Add specific loggers as needed
            "werkzeug": {
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False,
            },
            "stripe": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
        },
    }

    # Apply the configuration
    dictConfig(logging_config)

    # Log the configuration
    logging.info(f"Logging configured with level: {log_level}")

    return logging_config
