"""
PlaybackInfo parsing module for EmbyD.

Parses the Emby PlaybackInfo API response into structured MediaSource objects
and provides utility methods for selecting the best media source for download.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MediaSource:
    """
    Represents a single media source from PlaybackInfo response.
    """
    id: str                           # MediaSourceId
    container: str                    # mkv, mp4, avi, etc.
    path: str                         # Server-side file path
    protocol: str                     # File, Http, etc.
    size: int = 0                     # File size in bytes
    bitrate: int = 0                  # Bitrate in bps
    run_time_ticks: int = 0           # Duration in ticks (10ms units)
    supports_direct_stream: bool = False
    supports_transcoding: bool = False
    requires_transcoding: bool = False
    is_remote: bool = False
    name: str = ""
    etag: Optional[str] = None

    @property
    def size_human(self) -> str:
        """Human-readable file size."""
        size = float(self.size)
        if size == 0:
            return "Unknown"
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    @property
    def duration_human(self) -> str:
        """Human-readable duration (HH:MM:SS)."""
        total_seconds = self.run_time_ticks // 100  # 1 tick = 10ms
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


def parse_media_sources(playback_info: dict) -> list[MediaSource]:
    """
    Parse the PlaybackInfo API response into a list of MediaSource objects.

    Args:
        playback_info: The JSON response from GET /Items/{id}/PlaybackInfo

    Returns:
        List of MediaSource dataclass instances.
        Empty list if no MediaSources found.
    """
    raw_sources = playback_info.get("MediaSources", [])
    if not raw_sources:
        return []

    sources = []
    for raw in raw_sources:
        source = MediaSource(
            id=raw.get("Id", ""),
            container=raw.get("Container", ""),
            path=raw.get("Path", ""),
            protocol=raw.get("Protocol", ""),
            size=int(raw.get("Size", 0) or 0),
            bitrate=int(raw.get("Bitrate", 0) or 0),
            run_time_ticks=int(raw.get("RunTimeTicks", 0) or 0),
            supports_direct_stream=bool(raw.get("SupportsDirectStream", False)),
            supports_transcoding=bool(raw.get("SupportsTranscoding", False)),
            requires_transcoding=bool(raw.get("RequiresTranscoding", False)),
            is_remote=bool(raw.get("IsRemote", False)),
            name=raw.get("Name", ""),
            etag=raw.get("ETag"),
        )
        sources.append(source)

    return sources


def select_best_source(sources: list[MediaSource]) -> Optional[MediaSource]:
    """
    Select the best MediaSource for download.

    Priority:
    1. User-specified MediaSourceId (handled elsewhere)
    2. Default source (IsDefault=true)
    3. MKV container (most complete, supports subtitles)
    4. Largest file size (highest quality)
    5. Protocol "File" (local file, fastest)

    Args:
        sources: List of MediaSource objects

    Returns:
        Best MediaSource, or None if list is empty.
    """
    if not sources:
        return None

    if len(sources) == 1:
        return sources[0]

    # Score each source
    def score(source: MediaSource) -> int:
        s = 0
        # Prefer direct-stream capable
        if source.supports_direct_stream:
            s += 100
        # Prefer non-remote
        if not source.is_remote:
            s += 50
        # Prefer MKV container (most complete)
        if source.container.lower() == "mkv":
            s += 30
        # Prefer larger files (higher quality)
        if source.size > 0:
            # Size score: 1 point per GB, capped at 100
            size_gb = source.size / (1024 ** 3)
            s += min(int(size_gb), 100)
        # Prefer File protocol
        if source.protocol == "File":
            s += 20
        return s

    sorted_sources = sorted(sources, key=score, reverse=True)
    return sorted_sources[0]

def build_media_source_options(sources: list[MediaSource]) -> list[dict]:
    """Build display options from media sources for UI selection.

    Returns a list of dicts with keys: id, label, size, container, width, height, bitrate.
    The original MediaSource fields (width, height, codec, etc.) are included if available.

    Args:
        sources: List of MediaSource objects from parse_media_sources().

    Returns:
        List of option dicts suitable for populating a combo box.
    """
    if not sources:
        return []

    options = []
    for source in sources:
        label_parts = []
        # Try to detect resolution from source attributes
        resolution = _guess_resolution(source)
        if resolution:
            label_parts.append(resolution)
        if source.container:
            label_parts.append(source.container.upper())
        if source.size > 0:
            label_parts.append(source.size_human)

        label = " / ".join(label_parts) if label_parts else source.id[:12]
        if source.name and source.name != source.id:
            label = f'"{source.name}" ({label})'

        options.append({
            "id": source.id,
            "label": label,
            "size": source.size,
            "container": source.container,
            "bitrate": source.bitrate,
        })

    return options


def _guess_resolution(source: MediaSource) -> str:
    """Heuristic to guess resolution from bitrate and size characteristics.

    MediaSource from PlaybackInfo may not always include width/height.
    We use bitrate as a rough proxy.
    """
    # Check if MediaSource has width/height as extra attrs
    width = getattr(source, "width", None)
    height = getattr(source, "height", None)

    if width and height:
        if height >= 2160:
            return "4K"
        elif height >= 1080:
            return "1080p"
        elif height >= 720:
            return "720p"
        elif height >= 480:
            return "480p"
        return f"{height}p"

    # Guess from bitrate
    bps = source.bitrate
    if bps > 20_000_000:
        return "4K"
    elif bps > 8_000_000:
        return "1080p"
    elif bps > 3_000_000:
        return "720p"
    elif bps > 1_000_000:
        return "480p"

    return ""


def find_source_by_id(sources: list[MediaSource], source_id: str) -> MediaSource | None:
    """Find a MediaSource by its ID.

    Args:
        sources: List of MediaSource objects.
        source_id: The MediaSourceId to find.

    Returns:
        Matching MediaSource or None.
    """
    for source in sources:
        if source.id == source_id:
            return source
    return None


def format_size(bytes_size: int) -> str:
    """Format bytes to human-readable string."""
    if bytes_size == 0:
        return "Unknown"
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(bytes_size)
    for unit in units:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
