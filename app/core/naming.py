"""
File naming utilities for EmbyD.

Handles:
- Sanitizing filenames (removing Windows-invalid characters)
- Building filenames from templates
"""

import re
from typing import Optional


# Windows-invalid filename characters
_INVALID_CHARS = r'[<>:"/\\|?*\x00-\x1f]'

# Maximum filename length (Windows limit minus safety margin)
_MAX_FILENAME_LENGTH = 240


def sanitize_filename(name: str) -> str:
    """
    Remove or replace characters that are invalid in Windows filenames.

    Invalid characters: \\ / : * ? " < > | and control characters (0x00-0x1F)

    Args:
        name: Raw filename (without extension).

    Returns:
        Clean filename safe for Windows filesystem.
    """
    # Replace invalid characters with space
    cleaned = re.sub(_INVALID_CHARS, " ", name)

    # Replace multiple spaces with single space
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Strip leading/trailing whitespace and dots
    cleaned = cleaned.strip(" .")

    # Ensure not empty
    if not cleaned:
        cleaned = "untitled"

    # Truncate if too long
    if len(cleaned) > _MAX_FILENAME_LENGTH:
        cleaned = cleaned[:_MAX_FILENAME_LENGTH].rstrip()

    return cleaned


def build_filename(template: str, name: str, year: Optional[str] = None, container: str = "mkv") -> str:
    """
    Build a filename from a template.

    Supports template variables:
        {Name}  - Movie name
        {Year}  - Production year
        {Id}    - Item ID
        {Container} - File container/extension

    Args:
        template: Filename template (e.g., "{Name} ({Year})")
        name: Movie name
        year: Production year
        container: File container/extension

    Returns:
        Full filename with extension.
    """
    filename = template.replace("{Name}", name)
    if year:
        filename = filename.replace("{Year}", year)
    else:
        filename = filename.replace(" ({Year})", "").replace("{Year}", "")

    filename = sanitize_filename(filename)
    return f"{filename}.{container}"


def build_episode_filename(
    series_name: str,
    season_number: int,
    episode_number: int,
    episode_title: str = "",
    extension: str = "mkv",
) -> str:
    """
    Build a Windows-safe episode filename.

    Format: ``Series Name - S01E02 - Episode Title.ext``

    *season_number* and *episode_number* are zero-padded to two digits.
    Season 0 (Specials) produces ``S00E01``.
    Missing *episode_title* is gracefully omitted.
    *extension* may be ``"mkv"`` or ``".mkv"``; the leading dot is normalised.

    The final filename is truncated to respect the Windows path length
    safety margin (240 chars for the base name).

    Args:
        series_name:  Name of the series (e.g. "Breaking Bad").
        season_number:  Season number (0 for specials).
        episode_number:  Episode number within the season.
        episode_title:  Optional episode title.
        extension:  File extension with or without leading dot.

    Returns:
        Sanitised filename string with extension, e.g.
        ``"Breaking Bad - S01E02 - Cat's in the Bag.mkv"``.
    """
    # Normalise inputs
    name = sanitize_filename(series_name or "Unknown Series")

    # Zero-padded season / episode code
    sn = max(0, int(season_number or 0))
    en = max(0, int(episode_number or 0))
    code = f"S{sn:02d}E{en:02d}"

    # Normalise extension: strip leading dot, then re-add one
    ext = (extension or "mkv").lstrip(".")

    # Assemble base name – only include title when non-empty
    parts = [name, code]
    if episode_title:
        parts.append(sanitize_filename(str(episode_title)))
    base = " - ".join(parts)
    base = sanitize_filename(base)

    # Truncate if too long (reserve space for dot + extension)
    max_base = _MAX_FILENAME_LENGTH - len(ext) - 1
    if len(base) > max_base:
        base = base[:max_base].rstrip()

    return f"{base}.{ext}"