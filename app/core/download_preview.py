"""
Download preview module - pure business logic for dry-run.

Provides a single function `build_download_preview()` that returns a
structured `DownloadPreviewResult` dataclass. Contains no print/output logic,
so it can be used by both CLI and GUI.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.core.emby_api import EmbyApiClient
from app.core.playback_info import parse_media_sources, select_best_source, format_size
from app.core.download_capability import (
    check_download_capability,
    DownloadMethod,
    get_method_label,
)
from app.core.naming import sanitize_filename


@dataclass
class DownloadPreviewResult:
    """Structured result of a download preview (dry-run)."""

    item_id: str = ""
    title: str = ""
    year: str = ""
    item_type: str = ""
    series_name: str = ""
    season_number: int = 0
    episode_number: int = 0
    media_source_count: int = 0
    container: str = ""
    size: int = 0
    runtime_seconds: int = 0
    protocol: str = ""
    can_download: bool = False
    recommended_method: str = "none"  # direct / stream / transcode / none
    method_label: str = ""
    reason: str = ""
    output_path: str = ""
    filename: str = ""
    error_message: str = ""

    @property
    def size_human(self) -> str:
        """Human-readable file size."""
        return format_size(self.size) if self.size > 0 else "Unknown"

    @property
    def runtime_human(self) -> str:
        """Human-readable runtime."""
        minutes = self.runtime_seconds // 60
        hours = minutes // 60
        mins = minutes % 60
        if hours > 0:
            return f"{hours}h {mins}min"
        return f"{mins}min"


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def format_episode_code(season_number: int = 0, episode_number: int = 0) -> str:
    """Return an SxxEyy label when season/episode numbers are available."""
    if season_number > 0 and episode_number > 0:
        return f"S{season_number:02d}E{episode_number:02d}"
    if season_number > 0:
        return f"S{season_number:02d}"
    if episode_number > 0:
        return f"E{episode_number:02d}"
    return ""


def build_item_display_title(item: dict) -> str:
    """Build a readable title for movies and TV episodes."""
    item_type = item.get("Type", "")
    name = item.get("Name", "Unknown")
    if item_type == "Episode":
        series_name = item.get("SeriesName") or item.get("Series", "")
        code = format_episode_code(
            _as_int(item.get("ParentIndexNumber")),
            _as_int(item.get("IndexNumber")),
        )
        parts = [p for p in (series_name, code, name) if p]
        return " - ".join(parts) if parts else name

    year = str(item.get("ProductionYear", "") or "")
    return f"{name} ({year})" if year else name


def build_item_filename_base(item: dict) -> str:
    """Build a Windows-safe base filename for movies and TV episodes."""
    return sanitize_filename(build_item_display_title(item))


def build_download_preview(
    item_id: str,
    server_url: str,
    token: str,
    download_dir: str = "",
    user_id: Optional[str] = None,
    method: str = "auto",
) -> DownloadPreviewResult:
    """
    Build a download preview for a given media item.

    Pure business logic - no print/output. Returns a DownloadPreviewResult
    that can be used by CLI (for print) or GUI (for display).

    Args:
        item_id: Emby media item ID.
        server_url: Emby server URL (e.g., http://192.168.1.100:8096).
        token: Access token.
        download_dir: Target download directory.
        user_id: Emby user ID. If None, will be fetched from server.
        method: Download method preference ("auto", "direct", "stream").

    Returns:
        DownloadPreviewResult with preview data.
        On error, result.error_message will be set.
    """
    result = DownloadPreviewResult(item_id=item_id)

    if not download_dir or not str(download_dir).strip():
        result.error_message = (
            "Download directory is not set. Use --dir or set download_dir first."
        )
        return result

    client = EmbyApiClient(server_url, token)
    try:
        # Get user ID if not provided
        if not user_id:
            try:
                user = client.get_user()
                user_id = user.get("Id", "")
            except Exception as e:
                result.error_message = f"Failed to get user info: {e}"
                return result

        # Get item metadata
        try:
            item = client.get_item_metadata(item_id, user_id)
        except Exception as e:
            result.error_message = f"Failed to get item metadata: {e}"
            return result

        result.title = item.get("Name", f"item_{item_id}")
        result.year = str(item.get("ProductionYear", ""))
        result.item_type = item.get("Type", "")
        result.series_name = item.get("SeriesName") or item.get("Series", "")
        result.season_number = _as_int(item.get("ParentIndexNumber"))
        result.episode_number = _as_int(item.get("IndexNumber"))
        runtime_ticks = item.get("RunTimeTicks", 0)
        result.runtime_seconds = int(runtime_ticks // 100) if runtime_ticks else 0

        # Get PlaybackInfo
        try:
            playback_info = client.get_playback_info(item_id, user_id)
        except Exception as e:
            result.error_message = f"Failed to get playback info: {e}"
            return result

        sources = parse_media_sources(playback_info)
        result.media_source_count = len(sources)

        if not sources:
            result.error_message = (
                "No media sources found for this item. "
                "The item may not be a downloadable movie/episode, may have no playable media, "
                "or the server returned an unexpected response format."
            )
            return result

        best_source = select_best_source(sources)
        cap = check_download_capability(client, item_id, best_source)

        result.container = best_source.container.upper() if best_source.container else "N/A"
        result.size = best_source.size
        result.protocol = best_source.protocol
        result.can_download = cap.can_download
        result.recommended_method = cap.recommended_method.value
        result.method_label = get_method_label(cap.recommended_method)
        result.reason = cap.reason

        # Build output path
        filename_base = build_item_filename_base(item)
        ext = (best_source.container or "mkv").lower()
        result.filename = f"{filename_base}.{ext}"

        dl_path = Path(download_dir).resolve()
        result.output_path = str(dl_path / result.filename)

        if method != "auto" and method == "direct" and not cap.can_download:
            pass  # caller can check method vs capability

        return result

    finally:
        client.close()
