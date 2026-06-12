"""
Base types and constants for the downloader module.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DownloadStatus(Enum):
    """Status of a download task."""

    PENDING = "pending"
    PREPARING = "preparing"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadResult:
    """Result of a download operation.

    total_bytes can be None when the server doesn't disclose file size.
    """

    success: bool
    file_path: str = ""
    total_bytes: Optional[int] = None
    downloaded_bytes: int = 0
    elapsed_seconds: float = 0.0
    error_message: str = ""
    status: DownloadStatus = DownloadStatus.FAILED
    range_not_supported: bool = False


# Default chunk size: 8 MB
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024

# Part file suffix for partial downloads
PART_SUFFIX = ".part"
