"""
Small timing helpers for download pipeline diagnostics.

The helpers intentionally log only IDs and stage names. Any free-form value is
passed through the existing redactor before it reaches the application logger.
"""

from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Iterator

from app.utils.logger import get_logger
from app.utils.redaction import redact_sensitive


DEFAULT_WARNING_MS = 100.0


def _format_fields(fields: dict[str, object]) -> str:
    parts: list[str] = []
    for key, value in fields.items():
        if value is None or value == "":
            continue
        safe_value = redact_sensitive(str(value))
        parts.append(f"{key}={safe_value}")
    return " ".join(parts)


def timing_event(stage: str, **fields: object) -> None:
    """Log a single timing event."""
    suffix = _format_fields(fields)
    message = f"timing {stage}"
    if suffix:
        message = f"{message} {suffix}"
    get_logger().info(message)


@contextmanager
def timed_step(
    stage: str,
    warning_ms: float = DEFAULT_WARNING_MS,
    **fields: object,
) -> Iterator[None]:
    """Log enter/exit for a stage and warn when it exceeds *warning_ms*."""
    suffix = _format_fields(fields)
    logger = get_logger()
    enter = f"timing {stage} enter"
    if suffix:
        enter = f"{enter} {suffix}"
    logger.debug(enter)

    started = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (perf_counter() - started) * 1000.0
        exit_msg = f"timing {stage} exit elapsed_ms={elapsed_ms:.1f}"
        if suffix:
            exit_msg = f"{exit_msg} {suffix}"
        if elapsed_ms > warning_ms:
            logger.warning(exit_msg)
        else:
            logger.info(exit_msg)
