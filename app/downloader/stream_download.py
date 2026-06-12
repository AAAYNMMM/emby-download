"""
Stream download handler - wraps range_downloader with /stream URL logic.
"""
from typing import Optional

from app.downloader.base import DownloadResult, DEFAULT_CHUNK_SIZE
from app.downloader.range_downloader import download_file, ProgressCallback, CancelCallback


async def download_stream(
    url: str,
    dest_path: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    resume: bool = False,
    retry_count: int = 3,
    retry_delay: int = 5,
    timeout: int = 30,
    progress_callback: Optional[ProgressCallback] = None,
    cancel_callback: Optional[CancelCallback] = None,
) -> DownloadResult:
    """
    Download via Emby's /Videos/{id}/stream API (Direct Stream).

    IMPORTANT: no_range=True is forced because stream URLs create a
    new transcode/remux session per Range request, so byte offsets
    between Range segments do not align.  The file must be downloaded
    in one continuous HTTP response.

    Args:
        url: Full stream URL from get_stream_url().
        dest_path: Local path to save the file.
        chunk_size: Chunk size in bytes.
        resume: Whether to try resuming.
        retry_count: Max retries on failure.
        retry_delay: Base retry delay in seconds.
        timeout: HTTP timeout.
        progress_callback: Progress callback.

    Returns:
        DownloadResult.
    """
    return await download_file(
        url=url,
        dest_path=dest_path,
        chunk_size=chunk_size,
        resume=resume,
        no_range=True,
        retry_count=retry_count,
        retry_delay=retry_delay,
        timeout=timeout,
        progress_callback=progress_callback,
        cancel_callback=cancel_callback,
    )
