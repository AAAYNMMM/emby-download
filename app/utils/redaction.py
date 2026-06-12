"""Helpers for removing sensitive values from user-visible text."""

from __future__ import annotations

import re
from typing import Any


_REDACTION_PATTERNS = (
    (re.compile(r"(?i)(api[_-]?key=)[^&\s]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(X-Emby-Token[\"']?\s*[:=]\s*[\"']?)[^\"'\s,}]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(AccessToken[\"']?\s*[:=]\s*[\"']?)[^\"'\s,}]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:password|passwd|pwd)[\"']?\s*[:=]\s*[\"']?)[^\"'\s,}]+"), r"\1[REDACTED]"),
)


def redact_sensitive(value: Any) -> str:
    """Return text with obvious tokens and passwords replaced."""
    text = str(value)
    for pattern, replacement in _REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
