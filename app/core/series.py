"""
Series / Season / Episode metadata normalization and sorting utilities.

Provides pure functions that convert raw Emby API item dicts into
standardised dicts with safe defaults for missing fields.
"""

from typing import Optional


def _safe_int(value, default: int = 0) -> int:
    """Convert a value to int, returning *default* on failure or None."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------
# Normalizers
# ------------------------------------------------------------------

def normalize_series_item(item: dict) -> dict:
    """Normalize a raw Emby Series item to standard fields.

    Args:
        item: Raw item dict from the Emby API.

    Returns:
        Dict with keys: item_id, name, production_year, overview, media_type.
    """
    return {
        "item_id": item.get("Id") or "",
        "name": item.get("Name") or "Unknown Series",
        "production_year": item.get("ProductionYear") or None,
        "overview": item.get("Overview") or "",
        "media_type": "Series",
    }


def normalize_season_item(item: dict) -> dict:
    """Normalize a raw Emby Season item to standard fields.

    Args:
        item: Raw item dict from the Emby API.

    Returns:
        Dict with keys: item_id, name, series_id, series_name,
        season_number, production_year, overview, media_type.
    """
    return {
        "item_id": item.get("Id") or "",
        "name": item.get("Name") or "Unknown Season",
        "series_id": item.get("SeriesId") or "",
        "series_name": item.get("SeriesName") or "",
        "season_number": _safe_int(item.get("IndexNumber")),
        "production_year": item.get("ProductionYear") or None,
        "overview": item.get("Overview") or "",
        "media_type": "Season",
    }


def normalize_episode_item(item: dict) -> dict:
    """Normalize a raw Emby Episode item to standard fields.

    Args:
        item: Raw item dict from the Emby API.

    Returns:
        Dict with keys: item_id, name, series_id, series_name, season_id,
        season_name, season_number, episode_number, production_year,
        overview, runtime_ticks, media_type.
    """
    return {
        "item_id": item.get("Id") or "",
        "name": item.get("Name") or "Unknown Episode",
        "series_id": item.get("SeriesId") or "",
        "series_name": item.get("SeriesName") or item.get("Series") or "",
        "season_id": item.get("SeasonId") or "",
        "season_name": item.get("SeasonName") or "",
        "season_number": _safe_int(item.get("ParentIndexNumber")),
        "episode_number": _safe_int(item.get("IndexNumber")),
        "production_year": item.get("ProductionYear") or None,
        "overview": item.get("Overview") or "",
        "runtime_ticks": item.get("RunTimeTicks") or 0,
        "media_type": "Episode",
    }


# ------------------------------------------------------------------
# Sorters
# ------------------------------------------------------------------

def sort_seasons(seasons: list[dict]) -> list[dict]:
    """Sort seasons by season_number ascending.

    Seasons with missing / None season_number sort last (treated as 999999).
    Season 0 (Specials) sorts first.

    Args:
        seasons: List of normalized season dicts.

    Returns:
        New sorted list (does not mutate input).
    """
    def _key(s: dict) -> tuple:
        sn = s.get("season_number")
        if sn is None:
            return (1, 999999)
        return (0, sn)

    return sorted(seasons, key=_key)


def sort_episodes(episodes: list[dict]) -> list[dict]:
    """Sort episodes by (season_number, episode_number) ascending.

    Episodes with missing / None numbers sort last within their group.

    Args:
        episodes: List of normalized episode dicts.

    Returns:
        New sorted list (does not mutate input).
    """
    def _key(e: dict) -> tuple:
        sn = e.get("season_number")
        en = e.get("episode_number")
        sn_key = (0, sn) if sn is not None else (1, 999999)
        en_key = (0, en) if en is not None else (1, 999999)
        return sn_key + en_key

    return sorted(episodes, key=_key)
