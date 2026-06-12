"""
Stage 10D-2 tests: Range download, resume, Content-Range parsing, progress.

Uses aiohttp server mocks (no real Emby server needed).
"""

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.downloader.range_downloader import (
    download_file,
    parse_content_range,
)
from app.downloader.base import DownloadResult, DownloadStatus


class TestParseContentRange:
    """Tests for Content-Range header parsing."""

    def test_parse_bytes_standard(self):
        start, end, total = parse_content_range("bytes 0-999/2000")
        assert start == 0
        assert end == 999
        assert total == 2000

    def test_parse_bytes_mid_range(self):
        start, end, total = parse_content_range("bytes 400-999/1000")
        assert start == 400
        assert end == 999
        assert total == 1000

    def test_parse_bytes_416_unsatisfiable(self):
        start, end, total = parse_content_range("bytes */2000")
        assert start is None
        assert end is None
        assert total == 2000

    def test_parse_bytes_416_with_spaces(self):
        start, end, total = parse_content_range("bytes */1500")
        assert start is None
        assert end is None
        assert total == 1500

    def test_parse_empty_header(self):
        start, end, total = parse_content_range("")
        assert start is None
        assert end is None
        assert total is None

    def test_parse_none_header(self):
        start, end, total = parse_content_range(None)
        assert start is None
        assert end is None
        assert total is None

    def test_parse_malformed_header(self):
        start, end, total = parse_content_range("garbage")
        assert start is None
        assert end is None
        assert total is None

    def test_parse_large_range(self):
        start, end, total = parse_content_range("bytes 0-104857599/209715200")
        assert start == 0
        assert end == 104857599
        assert total == 209715200


class TestDownloadHTTP200:
    """Test new download with HTTP 200."""

    @pytest.mark.asyncio
    async def test_http200_new_download_with_content_length(self, tmp_path):
        """HTTP 200 new download: Content-Length=1000, progress correct."""
        dest = str(tmp_path / "test.mkv")
        expected_data = b"x" * 1000

        # Mock session
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # HEAD response for file size
        mock_head_response = MagicMock()
        mock_head_response.status = 200
        mock_head_response.headers = {"Content-Length": "1000"}
        mock_head_response.__aenter__ = AsyncMock(return_value=mock_head_response)
        mock_head_response.__aexit__ = AsyncMock(return_value=None)

        # GET response for download
        mock_get_response = MagicMock()
        mock_get_response.status = 200
        mock_get_response.headers = {"Content-Length": "1000"}

        async def iter_chunks(chunk_size):
            yield expected_data[:chunk_size]
        mock_get_response.content.iter_chunked = MagicMock(side_effect=iter_chunks)
        mock_get_response.__aenter__ = AsyncMock(return_value=mock_get_response)
        mock_get_response.__aexit__ = AsyncMock(return_value=None)

        mock_session.head.return_value = mock_head_response
        mock_session.get.return_value = mock_get_response

        # Track progress calls
        progress_calls = []

        def progress_cb(downloaded, total, speed):
            progress_calls.append((downloaded, total, speed))

        # Remove .part if exists
        part_path = dest + ".part"
        if os.path.exists(part_path):
            os.remove(part_path)

        # Patch aiohttp.ClientSession
        with patch('app.downloader.range_downloader.aiohttp.ClientSession',
                   return_value=mock_session):
            with patch('app.downloader.range_downloader.aiohttp.ClientTimeout',
                       return_value=MagicMock()):
                with patch('app.downloader.range_downloader.aiohttp.TCPConnector',
                           return_value=MagicMock()):
                    result = await download_file(
                        url="http://fake/Items/123/Download",
                        dest_path=dest,
                        resume=False,
                        progress_callback=progress_cb,
                    )

        assert result.success is True, f"result.status={result.status}, error={result.error_message}"
        assert os.path.exists(dest)
        assert os.path.getsize(dest) == 1000
        assert result.total_bytes == 1000
        assert result.downloaded_bytes == 1000
        assert result.status == DownloadStatus.COMPLETED

        # Verify progress total matches Content-Length
        assert len(progress_calls) > 0
        last_call = progress_calls[-1]
        assert last_call[0] == 1000  # downloaded
        assert last_call[1] == 1000  # total (NOT None, NOT downloaded)


class TestDownloadHTTP206Resume:
    """Test resume with HTTP 206."""

    @pytest.mark.asyncio
    async def test_http206_resume_from_part_file(self, tmp_path):
        """Resume: .part has 400 bytes, server returns 206 with Content-Range."""
        dest = str(tmp_path / "test.mkv")
        part_path = dest + ".part"

        # Pre-create part file with 400 bytes
        existing_data = b"a" * 400
        with open(part_path, "wb") as f:
            f.write(existing_data)

        remaining_data = b"b" * 600  # bytes 400-999

        # Mock session
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # HEAD response
        mock_head_response = MagicMock()
        mock_head_response.status = 200
        mock_head_response.headers = {"Content-Length": "1000"}
        mock_head_response.__aenter__ = AsyncMock(return_value=mock_head_response)
        mock_head_response.__aexit__ = AsyncMock(return_value=None)

        # GET response - should receive Range request, return 206
        mock_get_response = MagicMock()
        mock_get_response.status = 206
        mock_get_response.headers = {
            "Content-Range": "bytes 400-999/1000",
        }

        async def iter_chunks(chunk_size):
            yield remaining_data[:chunk_size]
        mock_get_response.content.iter_chunked = MagicMock(side_effect=iter_chunks)
        mock_get_response.__aenter__ = AsyncMock(return_value=mock_get_response)
        mock_get_response.__aexit__ = AsyncMock(return_value=None)

        mock_session.head.return_value = mock_head_response
        mock_session.get.return_value = mock_get_response

        progress_calls = []

        def progress_cb(downloaded, total, speed):
            progress_calls.append((downloaded, total, speed))

        with patch('app.downloader.range_downloader.aiohttp.ClientSession',
                   return_value=mock_session):
            with patch('app.downloader.range_downloader.aiohttp.ClientTimeout',
                       return_value=MagicMock()):
                with patch('app.downloader.range_downloader.aiohttp.TCPConnector',
                           return_value=MagicMock()):
                    result = await download_file(
                        url="http://fake/Items/123/Download",
                        dest_path=dest,
                        resume=True,
                        progress_callback=progress_cb,
                    )

        assert result.success is True
        assert os.path.exists(dest)
        file_size = os.path.getsize(dest)
        assert file_size == 1000, f"Expected 1000 bytes, got {file_size}"

        # Verify content is correct (not appended)
        with open(dest, "rb") as f:
            content = f.read()
        assert content[:400] == b"a" * 400
        assert content[400:] == b"b" * 600

        assert result.total_bytes == 1000
        assert result.downloaded_bytes == 1000
        assert result.status == DownloadStatus.COMPLETED

        # Progress should show total=1000 from Content-Range
        for dl, tot, sp in progress_calls:
            if tot is not None:
                assert tot == 1000, f"Progress total should be 1000, got {tot}"


class TestResumeServerReturns200:
    """Test: resume request but server returns 200 instead of 206."""

    @pytest.mark.asyncio
    async def test_resume_200_fallback_restart(self, tmp_path):
        """Resume with .part=400 bytes, server returns 200 -> restart from 0."""
        dest = str(tmp_path / "test.mkv")
        part_path = dest + ".part"

        # Pre-create part file with 400 bytes (will be overwritten)
        with open(part_path, "wb") as f:
            f.write(b"a" * 400)

        full_data = b"x" * 1000

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # HEAD
        mock_head_response = MagicMock()
        mock_head_response.status = 200
        mock_head_response.headers = {"Content-Length": "1000"}
        mock_head_response.__aenter__ = AsyncMock(return_value=mock_head_response)
        mock_head_response.__aexit__ = AsyncMock(return_value=None)

        # GET - server returns 200 ignoring Range
        mock_get_response = MagicMock()
        mock_get_response.status = 200
        mock_get_response.headers = {"Content-Length": "1000"}

        async def iter_chunks(chunk_size):
            yield full_data[:chunk_size]
        mock_get_response.content.iter_chunked = MagicMock(side_effect=iter_chunks)
        mock_get_response.__aenter__ = AsyncMock(return_value=mock_get_response)
        mock_get_response.__aexit__ = AsyncMock(return_value=None)

        mock_session.head.return_value = mock_head_response
        mock_session.get.return_value = mock_get_response

        progress_calls = []

        def progress_cb(downloaded, total, speed):
            progress_calls.append((downloaded, total, speed))

        with patch('app.downloader.range_downloader.aiohttp.ClientSession',
                   return_value=mock_session):
            with patch('app.downloader.range_downloader.aiohttp.ClientTimeout',
                       return_value=MagicMock()):
                with patch('app.downloader.range_downloader.aiohttp.TCPConnector',
                           return_value=MagicMock()):
                    result = await download_file(
                        url="http://fake/Items/123/Download",
                        dest_path=dest,
                        resume=True,
                        progress_callback=progress_cb,
                    )

        assert result.success is True
        assert os.path.exists(dest)
        file_size = os.path.getsize(dest)
        assert file_size == 1000, (
            f"Expected 1000 bytes (restart), got {file_size}. "
            f"Append bug: file should NOT be 1400 bytes!"
        )
        assert result.status == DownloadStatus.COMPLETED


class TestUnknownTotal:
    """Test: no Content-Length, no Content-Range."""

    @pytest.mark.asyncio
    async def test_no_content_length_unknown_total(self, tmp_path):
        """No Content-Length header -> total should be None, not downloaded."""
        dest = str(tmp_path / "test.mkv")

        full_data = b"z" * 500
        get_call_count = [0]

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # HEAD (no Content-Length)
        mock_head_response = MagicMock()
        mock_head_response.status = 200
        mock_head_response.headers = {}  # No Content-Length
        mock_head_response.__aenter__ = AsyncMock(return_value=mock_head_response)
        mock_head_response.__aexit__ = AsyncMock(return_value=None)

        # First GET: returns data (200, no Content-Length)
        mock_get_response_200 = MagicMock()
        mock_get_response_200.status = 200
        mock_get_response_200.headers = {}

        async def iter_chunks(chunk_size):
            yield full_data[:chunk_size]
        mock_get_response_200.content.iter_chunked = MagicMock(side_effect=iter_chunks)
        mock_get_response_200.__aenter__ = AsyncMock(return_value=mock_get_response_200)
        mock_get_response_200.__aexit__ = AsyncMock(return_value=None)

        # Second GET: 416 with Content-Range indicating total=500
        mock_get_response_416 = MagicMock()
        mock_get_response_416.status = 416
        mock_get_response_416.headers = {"Content-Range": "bytes */500"}
        mock_get_response_416.__aenter__ = AsyncMock(return_value=mock_get_response_416)
        mock_get_response_416.__aexit__ = AsyncMock(return_value=None)

        def get_side_effect(*args, **kwargs):
            get_call_count[0] += 1
            if get_call_count[0] == 1:
                return mock_get_response_200
            else:
                return mock_get_response_416

        mock_session.head.return_value = mock_head_response
        mock_session.get.side_effect = get_side_effect

        progress_calls = []

        def progress_cb(downloaded, total, speed):
            progress_calls.append((downloaded, total, speed))

        with patch('app.downloader.range_downloader.aiohttp.ClientSession',
                   return_value=mock_session):
            with patch('app.downloader.range_downloader.aiohttp.ClientTimeout',
                       return_value=MagicMock()):
                with patch('app.downloader.range_downloader.aiohttp.TCPConnector',
                           return_value=MagicMock()):
                    result = await download_file(
                        url="http://fake/Items/123/Download",
                        dest_path=dest,
                        resume=False,
                        progress_callback=progress_cb,
                    )

        assert result.success is True
        assert os.path.exists(dest)
        assert os.path.getsize(dest) == 500

        # Progress should NOT show total=downloaded (no fake 100%)
        # (progress_calls may be empty if total unknown triggers no report)
        for dl, tot, sp in progress_calls:
            if tot is not None:
                assert tot != dl, (
                    f"BUG: progress total={tot} should NOT equal downloaded={dl} "
                    f"(would show fake 100%)"
                )


class TestHTTP416:
    """Test HTTP 416 handling."""

    @pytest.mark.asyncio
    async def test_416_part_complete(self, tmp_path):
        """416 with part file size == total -> should complete."""
        dest = str(tmp_path / "test.mkv")
        part_path = dest + ".part"

        # Part file already has all 1000 bytes
        with open(part_path, "wb") as f:
            f.write(b"c" * 1000)

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # HEAD
        mock_head_response = MagicMock()
        mock_head_response.status = 200
        mock_head_response.headers = {"Content-Length": "1000"}
        mock_head_response.__aenter__ = AsyncMock(return_value=mock_head_response)
        mock_head_response.__aexit__ = AsyncMock(return_value=None)

        # GET returns 416
        mock_get_response = MagicMock()
        mock_get_response.status = 416
        mock_get_response.headers = {"Content-Range": "bytes */1000"}
        mock_get_response.__aenter__ = AsyncMock(return_value=mock_get_response)
        mock_get_response.__aexit__ = AsyncMock(return_value=None)

        mock_session.head.return_value = mock_head_response
        mock_session.get.return_value = mock_get_response

        with patch('app.downloader.range_downloader.aiohttp.ClientSession',
                   return_value=mock_session):
            with patch('app.downloader.range_downloader.aiohttp.ClientTimeout',
                       return_value=MagicMock()):
                with patch('app.downloader.range_downloader.aiohttp.TCPConnector',
                           return_value=MagicMock()):
                    result = await download_file(
                        url="http://fake/Items/123/Download",
                        dest_path=dest,
                        resume=True,
                    )

        assert result.success is True
        assert result.status == DownloadStatus.COMPLETED
        assert os.path.exists(dest)

    @pytest.mark.asyncio
    async def test_416_part_incomplete(self, tmp_path):
        """416 with part file size < total -> should fail."""
        dest = str(tmp_path / "test.mkv")
        part_path = dest + ".part"

        # Part file only has 400 of 1000 bytes
        with open(part_path, "wb") as f:
            f.write(b"c" * 400)

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_head_response = MagicMock()
        mock_head_response.status = 200
        mock_head_response.headers = {"Content-Length": "1000"}
        mock_head_response.__aenter__ = AsyncMock(return_value=mock_head_response)
        mock_head_response.__aexit__ = AsyncMock(return_value=None)

        mock_get_response = MagicMock()
        mock_get_response.status = 416
        mock_get_response.headers = {"Content-Range": "bytes */1000"}
        mock_get_response.__aenter__ = AsyncMock(return_value=mock_get_response)
        mock_get_response.__aexit__ = AsyncMock(return_value=None)

        mock_session.head.return_value = mock_head_response
        mock_session.get.return_value = mock_get_response

        with patch('app.downloader.range_downloader.aiohttp.ClientSession',
                   return_value=mock_session):
            with patch('app.downloader.range_downloader.aiohttp.ClientTimeout',
                       return_value=MagicMock()):
                with patch('app.downloader.range_downloader.aiohttp.TCPConnector',
                           return_value=MagicMock()):
                    result = await download_file(
                        url="http://fake/Items/123/Download",
                        dest_path=dest,
                        resume=True,
                    )

        assert result.success is False
        assert result.status == DownloadStatus.FAILED


class TestCancelPause:
    """Test cancel/pause callback behavior."""

    @pytest.mark.asyncio
    async def test_cancel_preserves_part(self, tmp_path):
        """Cancel while downloading should preserve .part and return PAUSED."""
        dest = str(tmp_path / "test.mkv")
        part_path = dest + ".part"

        full_data = b"d" * 2000

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_head_response = MagicMock()
        mock_head_response.status = 200
        mock_head_response.headers = {"Content-Length": "2000"}
        mock_head_response.__aenter__ = AsyncMock(return_value=mock_head_response)
        mock_head_response.__aexit__ = AsyncMock(return_value=None)

        # This counter triggers cancel after first chunk
        chunk_count = [0]

        mock_get_response = MagicMock()
        mock_get_response.status = 200
        mock_get_response.headers = {"Content-Length": "2000"}

        async def iter_chunks(chunk_size):
            chunk_count[0] += 1
            yield full_data[:chunk_size]

        mock_get_response.content.iter_chunked = MagicMock(side_effect=iter_chunks)
        mock_get_response.__aenter__ = AsyncMock(return_value=mock_get_response)
        mock_get_response.__aexit__ = AsyncMock(return_value=None)

        mock_session.head.return_value = mock_head_response
        mock_session.get.return_value = mock_get_response

        def cancel_cb():
            return True  # Cancel immediately

        progress_calls = []

        def progress_cb(downloaded, total, speed):
            progress_calls.append((downloaded, total, speed))

        with patch('app.downloader.range_downloader.aiohttp.ClientSession',
                   return_value=mock_session):
            with patch('app.downloader.range_downloader.aiohttp.ClientTimeout',
                       return_value=MagicMock()):
                with patch('app.downloader.range_downloader.aiohttp.TCPConnector',
                           return_value=MagicMock()):
                    result = await download_file(
                        url="http://fake/Items/123/Download",
                        dest_path=dest,
                        resume=False,
                        cancel_callback=cancel_cb,
                        progress_callback=progress_cb,
                    )

        # Should be PAUSED, not FAILED
        assert result.status == DownloadStatus.PAUSED, (
            f"Cancel should return PAUSED, got {result.status}"
        )
        assert result.success is False
        # Should NOT rename .part to final file
        assert not os.path.exists(dest), "Final file should not exist on cancel"
        # .part file should exist (partial data preserved)
        assert os.path.exists(part_path), ".part file should be preserved on cancel"


class TestCompletionVerification:
    """Test size verification at completion."""

    @pytest.mark.asyncio
    async def test_size_mismatch_detected(self, tmp_path):
        """Known total=1000, but only 500 bytes delivered -> should fail."""
        dest = str(tmp_path / "test.mkv")

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_head_response = MagicMock()
        mock_head_response.status = 200
        mock_head_response.headers = {"Content-Length": "1000"}
        mock_head_response.__aenter__ = AsyncMock(return_value=mock_head_response)
        mock_head_response.__aexit__ = AsyncMock(return_value=None)

        mock_get_response = MagicMock()
        mock_get_response.status = 200
        mock_get_response.headers = {"Content-Length": "500"}  # Mismatched

        async def iter_chunks(chunk_size):
            yield b"d" * 500  # Only deliver 500 bytes
        mock_get_response.content.iter_chunked = MagicMock(side_effect=iter_chunks)
        mock_get_response.__aenter__ = AsyncMock(return_value=mock_get_response)
        mock_get_response.__aexit__ = AsyncMock(return_value=None)

        mock_session.head.return_value = mock_head_response
        mock_session.get.return_value = mock_get_response

        with patch('app.downloader.range_downloader.aiohttp.ClientSession',
                   return_value=mock_session):
            with patch('app.downloader.range_downloader.aiohttp.ClientTimeout',
                       return_value=MagicMock()):
                with patch('app.downloader.range_downloader.aiohttp.TCPConnector',
                           return_value=MagicMock()):
                    result = await download_file(
                        url="http://fake/Items/123/Download",
                        dest_path=dest,
                        resume=False,
                    )

        # HEAD reported 1000, but actual download only 500
        # The download loop should detect this mismatch
        assert result.success is False, "Should detect size mismatch"
        assert result.status == DownloadStatus.FAILED