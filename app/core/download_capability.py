"""
Download capability determination for EmbyD.

Analyzes whether a media item can be downloaded and recommends
the best download method based on server permissions and MediaSource properties.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.core.emby_api import EmbyApiClient, EmbyAuthError
from app.core.playback_info import MediaSource
from app.utils.logger import get_logger


class DownloadMethod(Enum):
    """Supported download methods."""

    DIRECT = "direct"         # /Items/{id}/Download - original file
    STREAM = "stream"         # /Videos/{id}/stream (Direct Stream)
    TRANSCODE = "transcode"   # /Videos/{id}/stream (transcoded)
    NONE = "none"             # Cannot download


@dataclass
class DownloadCapability:
    """
    Result of a download capability check.

    Attributes:
        can_download: Whether the item can be downloaded by any method
        recommended_method: The best download method to use
        recommended_url: The URL for the recommended download method
        file_size: File size in bytes (from HEAD request or MediaSource)
        reason: Human-readable explanation, especially when cannot download
    """

    can_download: bool = False
    recommended_method: DownloadMethod = DownloadMethod.NONE
    recommended_url: str = ""
    file_size: int = 0
    reason: str = ""


_logger = get_logger()


def check_download_capability(
    client: EmbyApiClient,
    item_id: str,
    media_source: Optional[MediaSource] = None,
) -> DownloadCapability:
    """
    Determine if and how a media item can be downloaded.

    Strategy:
    1. First try HEAD /Items/{id}/Download -> 200/206 = direct download available
    2. If 403, check MediaSource.SupportsDirectStream
    3. If SupportsDirectStream -> use Direct Stream URL
    4. If only SupportsTranscoding -> warn about quality loss
    5. None -> cannot download

    Args:
        client: Authenticated EmbyApiClient instance
        item_id: Emby media item ID
        media_source: Optional MediaSource (will be used for fallback checks)

    Returns:
        DownloadCapability with the result
    """
    result = DownloadCapability()

    # Strategy 1: Check direct download
    direct_url = client.get_download_url(item_id)
    try:
        response = client._head(direct_url, timeout=15)
        if response.status_code in (200, 206):
            result.can_download = True
            result.recommended_method = DownloadMethod.DIRECT
            result.recommended_url = direct_url
            # Get file size from HEAD response or MediaSource
            content_length = response.headers.get("Content-Length")
            if content_length:
                result.file_size = int(content_length)
            elif media_source:
                result.file_size = media_source.size
            result.reason = "Direct download available (original file)"
            _logger.debug(f"Item {item_id}: Direct download available")
            return result
    except EmbyAuthError:
        # 401/403 = no direct download permission
        pass
    except Exception as e:
        _logger.debug(f"Item {item_id}: HEAD request failed for direct download: {e}")

    # Strategy 2: No direct download, try Direct Stream
    if media_source:
        if media_source.supports_direct_stream and not media_source.requires_transcoding:
            stream_url = client.get_stream_url(item_id, media_source.id, static=True)
            result.can_download = True
            result.recommended_method = DownloadMethod.STREAM
            result.recommended_url = stream_url
            result.file_size = media_source.size
            result.reason = (
                f"Direct Stream available (re-muxed, no re-encode). "
                f"Container: {media_source.container.upper()}"
            )
            _logger.debug(f"Item {item_id}: Direct stream available")
            return result

        # Strategy 3: Only transcoding available
        if media_source.supports_transcoding:
            transcode_url = client.get_stream_url(item_id, media_source.id, static=False)
            result.can_download = True
            result.recommended_method = DownloadMethod.TRANSCODE
            result.recommended_url = transcode_url
            result.file_size = media_source.size
            result.reason = (
                "Only transcoded stream available. "
                "WARNING: This may result in quality loss and missing audio/subtitle tracks."
            )
            _logger.debug(f"Item {item_id}: Only transcoding available")
            return result

        # Strategy 4: No supported method
        result.can_download = False
        result.recommended_method = DownloadMethod.NONE
        result.file_size = media_source.size
        result.reason = (
            "Cannot download this media source. "
            "The server does not allow download or direct stream for this item."
        )
        _logger.debug(f"Item {item_id}: No download method available")
        return result

    # No MediaSource provided and direct download failed
    result.can_download = False
    result.recommended_method = DownloadMethod.NONE
    result.reason = (
        "No download capability detected. "
        "Your account may not have download/direct-stream permissions, "
        "or the server does not support download for this item."
    )
    return result


def get_method_icon(method: DownloadMethod) -> str:
    """Get a display icon for the download method."""
    icons = {
        DownloadMethod.DIRECT: "[OK]",
        DownloadMethod.STREAM: "[~]",
        DownloadMethod.TRANSCODE: "[!]",
        DownloadMethod.NONE: "[X]",
    }
    return icons.get(method, "[?]")


def get_method_label(method: DownloadMethod) -> str:
    """Get a human-readable label for the download method."""
    labels = {
        DownloadMethod.DIRECT: "Original File Download",
        DownloadMethod.STREAM: "Direct Stream (Re-muxed)",
        DownloadMethod.TRANSCODE: "Transcoded Stream (May lose quality)",
        DownloadMethod.NONE: "Not Available",
    }
    return labels.get(method, "Unknown")