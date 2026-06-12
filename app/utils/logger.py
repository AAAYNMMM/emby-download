"""
Logging configuration for EmbyD.

Provides:
- Console logging (colored levels)
- File logging (rotating, max 10MB)
- Sensitive data redaction (no tokens/passwords in logs)
"""

import logging
import logging.handlers
import sys
from pathlib import Path

from app.utils.redaction import redact_sensitive


class RedactingFormatter(logging.Formatter):
    """Formatter that redacts tokens/passwords from log messages and tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return redact_sensitive(formatted)

    def formatException(self, ei) -> str:
        return redact_sensitive(super().formatException(ei))


def setup_logger(
    level: str = "INFO",
    log_file: Path | None = None,
    name: str = "embyd",
) -> logging.Logger:
    """
    Configure and return the application logger.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file. If None, no file logging.
        name: Logger name.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    console_format = RedactingFormatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=3
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = RedactingFormatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "embyd") -> logging.Logger:
    """Get the application logger."""
    return logging.getLogger(name)
