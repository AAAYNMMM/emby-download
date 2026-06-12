"""
HTTP Range-based downloader with resume support.

Core download engine that handles:
- HTTP Range requests for chunked download
- Resume from .part files
- HTTP 206 Content-Range parsing
- HTTP 200 fallback when server ignores Range
- Proper 416 handling with validation
- Progress reporting with clear total/unknown semantics
- Retry with exponential backoff
- Completion verification (file size vs known total)
"""

import asyncio
import os
import re
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

import aiohttp
import aiofiles

from app.downloader.base import DownloadResult, DownloadStatus, DEFAULT_CHUNK_SIZE, PART_SUFFIX
from app.utils.logger import get_logger
from app.utils.timing import timed_step, timing_event

_logger = get_logger()

# Progress callback type: (downloaded_bytes, total_bytes_or_None, speed_bps)
# total_bytes is None when total size is unknown.
ProgressCallback = Callable[[int, Optional[int], float], None]
CancelCallback = Callable[[], bool]

# Regex to parse Content-Range header: "bytes 0-999/2000" or "bytes */2000"
_CONTENT_RANGE_RE = re.compile(r"bytes\s+(\d+)-(\d+)/(\d+)|bytes\s+\*/(\d+)")


def parse_content_range(header: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Parse HTTP Content-Range header.

    Returns:
        (start_byte, end_byte, total_bytes) or (None, None, total_bytes) for unsatisfiable.
        Returns (None, None, None) if parsing fails.
    """
    if not header:
        return None, None, None
    m = _CONTENT_RANGE_RE.match(header.strip())
    if not m:
        return None, None, None
    if m.group(4) is not None:
        # "bytes */total" (416 response)
        total = int(m.group(4))
        return None, None, total
    # "bytes start-end/total"
    start = int(m.group(1))
    end = int(m.group(2))
    total = int(m.group(3))
    return start, end, total


async def download_file(
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
    Download a file with HTTP Range support and resume capability.

    Args:
        url: Full download URL.
        dest_path: Final file path to save to.
        chunk_size: Size of each chunk in bytes.
        resume: Whether to try resuming from existing .part file.
        retry_count: Number of retries on failure.
        retry_delay: Base delay in seconds between retries.
        timeout: HTTP request timeout in seconds.
        progress_callback: Called with (downloaded, total_or_None, speed) during download.
                           total is None when size is unknown.
        cancel_callback: Called periodically; return True to stop.

    Returns:
        DownloadResult with status and file info.
    """
    result = DownloadResult(success=False, file_path=dest_path)
    part_path = dest_path + PART_SUFFIX

    # Determine starting point and total size
    existing_size = 0
    total_size: Optional[int] = None

    if resume and os.path.exists(part_path):
        existing_size = os.path.getsize(part_path)
        if existing_size > 0:
            _logger.info(f"Found .part file with {existing_size} bytes - will try resume")
        else:
            existing_size = 0

    # If final file already exists and is complete
    if resume and os.path.exists(dest_path):
        file_size = os.path.getsize(dest_path)
        if file_size > 0:
            result.success = True
            result.file_path = dest_path
            result.total_bytes = file_size
            result.downloaded_bytes = file_size
            result.status = DownloadStatus.COMPLETED
            return result

    # --- Phase 1: HEAD request to get total size ---
    timeout_obj = aiohttp.ClientTimeout(total=timeout, connect=timeout)
    connector = aiohttp.TCPConnector(limit_per_host=1)
    downloaded = 0

    try:
        async with aiohttp.ClientSession(timeout=timeout_obj, connector=connector) as session:
            with timed_step("HEAD download_file"):
                total_size, accept_ranges = await _get_file_info(session, url)

            # --- Phase 2: Download with range support ---
            downloaded = await _download_with_range(
                session=session,
                url=url,
                part_path=part_path,
                existing_size=existing_size,
                total_size=total_size,
                chunk_size=chunk_size,
                resume=resume,
                retry_count=retry_count,
                retry_delay=retry_delay,
                timeout=timeout,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
                result=result,
            )

            # Check for early termination (pause, cancel, or explicit failure)
            if result.status == DownloadStatus.PAUSED:
                result.downloaded_bytes = downloaded
                return result
            # Only treat FAILED if it was explicitly set with an error message
            # (default FAILED status means download loop completed normally)
            if result.status == DownloadStatus.FAILED and result.error_message:
                result.downloaded_bytes = downloaded
                return result

            # --- Phase 3: Completion verification ---
            if not os.path.exists(part_path) or os.path.getsize(part_path) == 0:
                result.error_message = "Part file missing or empty after download"
                result.status = DownloadStatus.FAILED
                return result

            actual_size = os.path.getsize(part_path)

            # Verify against known total if available
            if total_size is not None and actual_size != total_size:
                _logger.warning(
                    f"Size mismatch: downloaded {actual_size} bytes, expected {total_size} bytes"
                )
                result.error_message = (
                    f"Download incomplete: got {actual_size} bytes, expected {total_size} bytes"
                )
                result.downloaded_bytes = actual_size
                result.total_bytes = total_size
                result.status = DownloadStatus.FAILED
                return result

            # Rename .part to final file
            try:
                os.replace(part_path, dest_path)
            except OSError as e:
                result.error_message = f"Failed to rename .part to final file: {e}"
                result.status = DownloadStatus.FAILED
                return result

            _logger.info(f"Download complete: {dest_path} ({actual_size} bytes)")
            result.success = True
            result.file_path = dest_path
            result.total_bytes = total_size or actual_size
            result.downloaded_bytes = actual_size
            result.status = DownloadStatus.COMPLETED
            return result

    except asyncio.CancelledError:
        _logger.info("Download cancelled by user")
        result.downloaded_bytes = downloaded
        result.total_bytes = total_size
        result.status = DownloadStatus.PAUSED
        result.error_message = "Download paused by user"
        return result
    except Exception as e:
        _logger.error(f"Download failed unexpectedly: {e}", exc_info=True)
        result.error_message = str(e)
        result.status = DownloadStatus.FAILED
        return result


async def _download_with_range(
    session: aiohttp.ClientSession,
    url: str,
    part_path: str,
    existing_size: int,
    total_size: Optional[int],
    chunk_size: int,
    resume: bool,
    retry_count: int,
    retry_delay: int,
    timeout: int,
    progress_callback: Optional[ProgressCallback],
    cancel_callback: Optional[CancelCallback],
    result: DownloadResult,
) -> int:
    """
    Core download loop with Range support.

    Sets result.status to PAUSED or FAILED (with error_message) on early termination.
    Leaves result.status untouched on normal completion (caller handles validation).

    Returns:
        Total downloaded bytes (including existing_size before this call).
    """
    start_time = time.time()
    last_report_time = start_time
    downloaded = existing_size
    retries = 0
    file_mode = "ab" if existing_size > 0 else "wb"
    range_not_supported = False
    get_started_logged = False

    async with aiofiles.open(part_path, file_mode) as f:
        while True:
            # Check if we know the total and have finished
            if total_size is not None and downloaded >= total_size:
                break

            # Cancel / pause check
            if cancel_callback and cancel_callback():
                result.downloaded_bytes = downloaded
                result.total_bytes = total_size
                result.status = DownloadStatus.PAUSED
                result.error_message = "Download paused by user"
                return downloaded

            # Build Range header for resume
            headers = {}
            request_range = False
            if resume and total_size is not None and downloaded > 0 and not range_not_supported:
                end_byte = downloaded + chunk_size - 1
                if total_size:
                    end_byte = min(end_byte, total_size - 1)
                headers["Range"] = f"bytes={downloaded}-{end_byte}"
                request_range = True

            try:
                if not get_started_logged:
                    timing_event("GET started download_file")
                    get_started_logged = True
                async with session.get(url, headers=headers) as response:
                    # --- Handle 416 Range Not Satisfiable ---
                    if response.status == 416:
                        _logger.debug(f"HTTP 416 at byte {downloaded}")
                        content_range = response.headers.get("Content-Range", "")
                        _, _, cr_total = parse_content_range(content_range)
                        if cr_total is not None:
                            total_size = cr_total

                        current_part_size = (
                            os.path.getsize(part_path) if os.path.exists(part_path)
                            else downloaded
                        )
                        if total_size is not None and current_part_size >= total_size:
                            _logger.info(
                                f"416 but part file is complete "
                                f"({current_part_size} >= {total_size}) - marking complete"
                            )
                            break
                        else:
                            result.error_message = (
                                f"HTTP 416: Range not satisfiable at byte {downloaded}"
                                + (f" (total={total_size})" if total_size else "")
                            )
                            result.downloaded_bytes = downloaded
                            result.total_bytes = total_size
                            result.status = DownloadStatus.FAILED
                            return downloaded

                    # --- Handle HTTP 200 when Range was requested ---
                    # Server ignored Range header - must restart
                    if request_range and response.status == 200:
                        _logger.warning(
                            f"Server returned 200 instead of 206 for Range request "
                            f"(byte {downloaded}). Restarting from beginning."
                        )
                        range_not_supported = True
                        downloaded = 0
                        await f.close()
                        f = await aiofiles.open(part_path, "wb")
                        cl = response.headers.get("Content-Length")
                        if cl:
                            try:
                                total_size = int(cl)
                            except ValueError:
                                pass

                    # --- Handle other error statuses ---
                    if response.status not in (200, 206):
                        _logger.error(f"HTTP {response.status} at byte {downloaded}")
                        retries += 1
                        if retries > retry_count:
                            result.error_message = (
                                f"HTTP {response.status} after {retry_count} retries"
                            )
                            result.downloaded_bytes = downloaded
                            result.total_bytes = total_size
                            result.status = DownloadStatus.FAILED
                            return downloaded
                        await asyncio.sleep(retry_delay * (2 ** (retries - 1)))
                        continue

                    retries = 0

                    # --- Parse Content-Range from 206 ---
                    if response.status == 206:
                        content_range = response.headers.get("Content-Range", "")
                        cr_start, cr_end, cr_total = parse_content_range(content_range)
                        if cr_total is not None and cr_total > 0:
                            total_size = cr_total

                    # Try Content-Length as fallback for total
                    if total_size is None:
                        cl = response.headers.get("Content-Length")
                        if cl:
                            try:
                                parsed = int(cl)
                                if response.status == 200:
                                    total_size = parsed
                                # For 206, Content-Length is chunk size, not total;
                                # Content-Range total is already set above.
                            except ValueError:
                                pass
                    elif response.status == 200:
                        # HEAD gave a known total, but GET 200 Content-Length differs.
                        # The GET value is more authoritative for what is delivered.
                        cl = response.headers.get("Content-Length")
                        if cl:
                            try:
                                cl_int = int(cl)
                                if cl_int != total_size:
                                    _logger.warning(
                                        f"Content-Length mismatch: HEAD={total_size}, GET={cl_int}"
                                    )
                                    total_size = cl_int
                            except ValueError:
                                pass

                    # --- Read and write chunk ---
                    async for data in response.content.iter_chunked(65536):
                        if cancel_callback and cancel_callback():
                            result.downloaded_bytes = downloaded
                            result.total_bytes = total_size
                            result.status = DownloadStatus.PAUSED
                            result.error_message = "Download paused by user"
                            return downloaded

                        await f.write(data)
                        downloaded += len(data)

                        now = time.time()
                        if progress_callback and (
                            now - last_report_time >= 0.25
                            or (total_size and downloaded >= total_size)
                        ):
                            elapsed = now - start_time
                            speed = (
                                (downloaded - existing_size) / elapsed
                                if elapsed > 0 else 0
                            )
                            progress_callback(downloaded, total_size, speed)
                            last_report_time = now

                    # If total is unknown and server returned 200 (full content),
                    # the response body ended naturally - download is complete.
                    if total_size is None and response.status == 200:
                        break

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                _logger.warning(f"Download error at byte {downloaded}: {e}")
                retries += 1
                if retries > retry_count:
                    result.error_message = (
                        f"Download failed after {retry_count} retries: {e}"
                    )
                    result.downloaded_bytes = downloaded
                    result.total_bytes = total_size
                    result.status = DownloadStatus.FAILED
                    return downloaded
                await asyncio.sleep(retry_delay * (2 ** (retries - 1)))

    return downloaded


async def _get_file_info(session: aiohttp.ClientSession, url: str) -> tuple:
    """Get file size and Range support via HEAD request.

    Returns:
        (total_size, accept_ranges) where:
        - total_size: int or None (Content-Length)
        - accept_ranges: bool (server sent Accept-Ranges: bytes)
    """
    try:
        async with session.head(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                content_length = response.headers.get("Content-Length")
                total_size = None
                if content_length:
                    try:
                        total_size = int(content_length)
                    except ValueError:
                        pass
                ar = response.headers.get("Accept-Ranges", "")
                accept_ranges = (ar.lower() == "bytes")
                return total_size, accept_ranges
            return None, False
    except Exception:
        return None, False


def format_speed(bytes_per_sec: float) -> str:
    """Format download speed to human-readable string."""
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.0f} B/s"
    elif bytes_per_sec < 1024 ** 2:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    elif bytes_per_sec < 1024 ** 3:
        return f"{bytes_per_sec / 1024 ** 2:.1f} MB/s"
    else:
        return f"{bytes_per_sec / 1024 ** 3:.2f} GB/s"


def format_time(seconds: float) -> str:
    """Format seconds to HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
