"""app.logger
=================
Mini-README: Configures structured logging utilities across the platform. Exposes a
factory for obtaining module-specific loggers with consistent formatting and log levels.
"""

import logging
from logging.config import dictConfig

_LOGGING_CONFIG = {
    "version": 1,
    "formatters": {
        "default": {
            "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": "DEBUG",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

dictConfig(_LOGGING_CONFIG)


def get_logger(name: str) -> logging.Logger:
    """Return a module-specific logger instance."""

    return logging.getLogger(name)
