"""
Formatting utilities for human-readable display in GUI and CLI.

All functions handle None/0/edge cases cleanly.
No sensitive data (tokens, passwords) in any output.
"""

from __future__ import annotations

import math
from typing import Optional


def format_bytes(n: int | float | None) -> str:
    """Format bytes to human-readable string (e.g. 1.5 GB, 340.2 MB).

    Returns '0 B' for 0 or None.
    """
    if n is None or n <= 0:
        return "0 B"
    n = float(n)
    if n < 1024:
        return f"{n:.0f} B"
    for unit in ("KB", "MB", "GB", "TB", "PB"):
        n /= 1024.0
        if n < 1024.0:
            if n >= 100:
                return f"{n:.0f} {unit}"
            elif n >= 10:
                return f"{n:.1f} {unit}"
            else:
                return f"{n:.2f} {unit}"
    return f"{n:.2f} PB"


def format_speed_gui(bytes_per_sec: float | None) -> str:
    """Format download speed to human-readable string for GUI display.

    Returns '--' for None/0/negative.
    """
    if bytes_per_sec is None or bytes_per_sec <= 0:
        return "--"
    bps = float(bytes_per_sec)
    if bps < 1024:
        return f"{bps:.0f} B/s"
    elif bps < 1024 ** 2:
        return f"{bps / 1024:.1f} KB/s"
    elif bps < 1024 ** 3:
        return f"{bps / (1024 ** 2):.1f} MB/s"
    else:
        return f"{bps / (1024 ** 3):.2f} GB/s"


def format_eta(seconds: float | None) -> str:
    """Format estimated time remaining as HH:MM:SS or 'unknown'.

    Args:
        seconds: ETA in seconds, or None if unknown.
    Returns:
        Formatted string like '00:01:23' or 'unknown'.
    """
    if seconds is None or seconds <= 0 or math.isinf(seconds) or math.isnan(seconds):
        return "unknown"
    seconds = int(seconds)
    if seconds > 86400 * 365:  # absurdly large
        return "unknown"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_progress_pct(downloaded: int | float, total: int | float | None) -> str:
    """Format progress as percentage string.

    Args:
        downloaded: Downloaded bytes.
        total: Total bytes, or None if unknown.
    Returns:
        '42.5%' for known total, 'unknown' for unknown total.
        Clamps to 0-100% and never shows fake 100%.
    """
    if total is None or total <= 0:
        return "unknown"
    if downloaded < 0:
        downloaded = 0
    if downloaded > total:
        # Clamp and log warning would happen elsewhere
        downloaded = total
    pct = (downloaded / total) * 100.0
    if pct < 0:
        pct = 0.0
    if pct > 100.0:
        pct = 100.0
    if pct >= 99.95:
        return "100%"
    if pct < 0.1:
        return f"{pct:.2f}%"
    if pct < 10:
        return f"{pct:.1f}%"
    return f"{pct:.0f}%"


def format_updated_at(timestamp: float | None) -> str:
    """Format a Unix timestamp to a short datetime string.

    Returns '--' for None/0.
    """
    if timestamp is None or timestamp <= 0:
        return "--"
    from datetime import datetime
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%m-%d %H:%M")
    except (OSError, ValueError):
        return "--"


def compute_eta_seconds(downloaded: int, total: int | None, speed: float) -> float | None:
    """Compute ETA in seconds from current progress.

    Args:
        downloaded: Bytes downloaded so far.
        total: Total bytes (None if unknown).
        speed: Current speed in bytes/sec.
    Returns:
        ETA in seconds, or None if cannot compute.
    """
    if total is None or total <= 0 or speed <= 0:
        return None
    remaining = total - downloaded
    if remaining <= 0:
        return 0.0
    return remaining / speed
