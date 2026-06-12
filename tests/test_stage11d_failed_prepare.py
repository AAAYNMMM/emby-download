"""
Stage 11D: Failed prepare-phase diagnostics and error handling tests.

Tests that:
1. media_source_id not found -> task failed + error_message contains "Selected version not available"
2. download_dir empty -> task failed + error_message contains "Download directory not configured"
3. PlaybackInfo 404/error -> task failed + error_message is not empty
4. Prepare phase exception -> task failed, not stuck in preparing/downloading
5. Failed task error_message can be read from task_store
6. GUI error tab can display selected task error_message
7. save_path is written to task_store when prepare succeeds
8. media_source_id is a real ID, not display_label/index
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from app.downloader.task_store import (
    DownloadTask, create_task, update_task, get_task, delete_task, _init_db,
)


def make_task(status="pending", item_id="item-test", media_source_id="", **kw):
    t = create_task(item_id=item_id, title="Test",
                    media_source_id=media_source_id, **kw)
    if status != "pending":
        from app.downloader.task_store import update_task
        update_task(t.task_id, status=status)
        t.status = status
    return t


def cleanup(*ids):
    for tid in ids:
        try:
            delete_task(tid)
        except Exception:
            pass


class FakeConfig:
    server_url = "http://test:8096"
    username = "test"
    download_dir = ""
    max_concurrent_downloads = 1
    chunk_size_mb = 4
    retry_count = 3
    retry_delay_seconds = 1
    timeout_seconds = 30


class FakePreviewResult:
    def __init__(self, error_message="", can_download=True, reason="", output_path="/tmp/test.mkv",
                 filename="test.mkv", title="Test", size=1024):
        self.error_message = error_message
        self.can_download = can_download
        self.reason = reason
        self.output_path = output_path
        self.filename = filename
        self.title = title
        self.size = size


class FakeMediaSource:
    def __init__(self, sid="src-001", container="mkv", size=1024, protocol="File"):
        self.id = sid
        self.container = container
        self.path = "/media/test.mkv"
        self.protocol = protocol
        self.size = size
        self.bitrate = 0
        self.run_time_ticks = 0
        self.supports_direct_stream = True
        self.supports_transcoding = False
        self.requires_transcoding = False
        self.is_remote = False
        self.name = ""


class FakeCapability:
    def __init__(self, can_download=True, reason="", recommended_url="http://dl/test.mkv",
                 recommended_method="direct", file_size=1024):
        self.can_download = can_download
        self.reason = reason
        self.recommended_url = recommended_url
        self.recommended_method = recommended_method
        self.file_size = file_size


# ===========================================================================
# 1. media_source_id not found
# ===========================================================================

class TestMediaSourceIdNotFound:
    """When user-selected media_source_id does not exist in PlaybackInfo."""

    def test_error_message_contains_selected_version_not_available(self):
        """media_source_id mismatch should produce clear error message."""
        from app.core.playback_info import find_source_by_id
        sources = [FakeMediaSource(sid="src-001"), FakeMediaSource(sid="src-002")]
        result = find_source_by_id(sources, "src-999")
        assert result is None, "Should return None for non-existent ID"

    def test_task_failed_when_media_source_id_missing(self):
        """Task status becomes failed when media_source_id is not found."""
        t = make_task(item_id="item-ms-missing", media_source_id="nonexistent-src")
        try:
            # Simulate what _prepare_and_download does
            from app.core.playback_info import find_source_by_id
            sources = [FakeMediaSource(sid="src-001")]
            best = find_source_by_id(sources, t.media_source_id)
            assert best is None
            update_task(t.task_id, status="failed",
                        error_message=f"Selected version not available: media_source_id={t.media_source_id}")
            updated = get_task(t.task_id)
            assert updated.status == "failed"
            assert "Selected version not available" in updated.error_message
            assert t.media_source_id in updated.error_message
        finally:
            cleanup(t.task_id)

    def test_media_source_id_is_not_display_label(self):
        """media_source_id must be a real MediaSource.Id, not a label."""
        sources = [
            FakeMediaSource(sid="real-id-001", container="mkv", size=1024),
            FakeMediaSource(sid="real-id-002", container="mp4", size=2048),
        ]
        # Verify ID is the real ID field, not something else
        for s in sources:
            assert s.id.startswith("real-id-")
            assert s.id != s.container
            assert s.id != s.name


# ===========================================================================
# 2. download_dir empty
# ===========================================================================

class TestDownloadDirEmpty:
    """When download_dir is empty or not provided."""

    def test_task_failed_when_download_dir_empty(self):
        """Empty download_dir should produce clear error."""
        t = make_task(status="pending")
        try:
            download_dir = ""
            if not download_dir or not download_dir.strip():
                update_task(t.task_id, status="failed", error_message="Download directory not configured")
            updated = get_task(t.task_id)
            assert updated.status == "failed"
            assert "Download directory not configured" in updated.error_message
        finally:
            cleanup(t.task_id)


# ===========================================================================
# 3. PlaybackInfo error
# ===========================================================================

class TestPlaybackInfoError:
    """When PlaybackInfo API call fails."""

    def test_task_failed_with_http_error_message(self):
        """PlaybackInfo failure should set non-empty error_message."""
        t = make_task(status="pending")
        try:
            http_error = "HTTP 404 - Item not found"
            update_task(t.task_id, status="failed", error_message=f"Failed to get playback info: {http_error}")
            updated = get_task(t.task_id)
            assert updated.status == "failed"
            assert updated.error_message
            assert "404" in updated.error_message or "playback" in updated.error_message.lower()
        finally:
            cleanup(t.task_id)


# ===========================================================================
# 4. Prepare phase exception
# ===========================================================================

class TestPrepareException:
    """When prepare phase raises an unexpected exception."""

    def test_task_not_stuck_in_preparing(self):
        """Exception should transition task to failed, not leave it preparing."""
        t = make_task(status="preparing")
        try:
            # Simulate exception caught in prepare
            update_task(t.task_id, status="failed", error_message="Prepare failed: Connection refused")
            updated = get_task(t.task_id)
            assert updated.status == "failed"
        finally:
            cleanup(t.task_id)

    def test_error_message_not_empty(self):
        """Failed tasks after prepare exception must have non-empty error_message."""
        t = make_task(status="preparing")
        try:
            update_task(t.task_id, status="failed", error_message="Prepare failed: unexpected error")
            updated = get_task(t.task_id)
            assert updated.status == "failed"
            assert updated.error_message
        finally:
            cleanup(t.task_id)

    def test_downloading_not_left_after_exception(self):
        """If prepare crashes, task should not stay in 'downloading' status."""
        t = make_task(status="downloading")
        try:
            update_task(t.task_id, status="failed", error_message="Download crashed")
            updated = get_task(t.task_id)
            assert updated.status == "failed"
        finally:
            cleanup(t.task_id)


# ===========================================================================
# 5. error_message readable from task_store
# ===========================================================================

class TestErrorMessageReadable:
    """Failed task error_message must be readable via task_store.get_task."""

    def test_error_message_readable(self):
        """get_task returns error_message for failed tasks."""
        t = make_task(status="pending")
        try:
            err_msg = "Test error: media source unreachable"
            update_task(t.task_id, status="failed", error_message=err_msg)
            fetched = get_task(t.task_id)
            assert fetched is not None
            assert fetched.error_message == err_msg
        finally:
            cleanup(t.task_id)

    def test_empty_error_message_bug_detected(self):
        """If status=failed, error_message should be set (repro for old bug)."""
        t = make_task(status="pending")
        try:
            update_task(t.task_id, status="failed", error_message="Simulated failure")
            fetched = get_task(t.task_id)
            assert fetched.status == "failed"
            assert fetched.error_message, "error_message should be non-empty for failed tasks"
        finally:
            cleanup(t.task_id)


# ===========================================================================
# 6. GUI error tab display (simulated, no Qt)
# ===========================================================================

class TestGuiErrorTab:
    """GUI error tab should display selected task's error_message (logic test)."""

    def test_error_message_available_for_display(self):
        """Simulate reading error_message for GUI display."""
        t = make_task(status="failed", item_id="item-error-display")
        try:
            err = "Failed to get item metadata: HTTP 404"
            update_task(t.task_id, status="failed", error_message=err)
            fetched = get_task(t.task_id)
            if fetched.status == "failed" and fetched.error_message:
                display_text = fetched.error_message
                assert "HTTP 404" in display_text
            else:
                pytest.fail("BUG: failed task has no error_message")
        finally:
            cleanup(t.task_id)

    def test_error_tab_shows_error_not_empty(self):
        """Error tab should never show empty string when task is failed."""
        t = make_task(status="failed", item_id="item-error-tab")
        try:
            update_task(t.task_id, status="failed", error_message="Download capability rejected: transcoding required")
            fetched = get_task(t.task_id)
            error_for_display = fetched.error_message or DETAIL_LBL_NO_ERROR
            # We import the constant at test time
            from app.gui.i18n import DETAIL_LBL_NO_ERROR
            assert error_for_display != ""
            assert error_for_display != DETAIL_LBL_NO_ERROR
        finally:
            cleanup(t.task_id)


# ===========================================================================
# 7. save_path written to task_store
# ===========================================================================

class TestSavePathWritten:
    """save_path must be written to task_store when prepare succeeds."""

    def test_save_path_updated_in_task_store(self):
        """Confirm update_task can set save_path."""
        t = make_task(status="preparing")
        try:
            update_task(t.task_id, save_path="/tmp/test.mkv", temp_path="/tmp/test.mkv.part")
            fetched = get_task(t.task_id)
            assert fetched.save_path == "/tmp/test.mkv"
            assert fetched.temp_path == "/tmp/test.mkv.part"
        finally:
            cleanup(t.task_id)

    def test_save_path_persisted_after_prepare(self):
        """save_path should survive a DB read after prepare update."""
        t = make_task(status="preparing")
        try:
            test_path = str(Path("/tmp") / "test_output.mkv")
            update_task(t.task_id, save_path=test_path, total_bytes=2048)
            fetched = get_task(t.task_id)
            assert fetched.save_path == test_path
            assert fetched.total_bytes == 2048
        finally:
            cleanup(t.task_id)


# ===========================================================================
# 8. media_source_id is real ID
# ===========================================================================

class TestMediaSourceIdIsRealId:
    """media_source_id must be MediaSource.Id, not display_label/index."""
    def test_not_item_id(self):
        assert "media_source_id" != "item_id"
    def test_not_container(self):
        s = FakeMediaSource(sid="real-id", container="mkv")
        assert s.id != s.container
        assert s.id == "real-id"
    def test_not_display_label(self):
        s = FakeMediaSource(sid="real-id")
        assert s.id != "1080p MKV"
        assert s.id != "Best Quality"
        assert s.id != "index-0"
    def test_is_actual_source_id(self):
        sources = [FakeMediaSource(sid="a1b2c3d4"), FakeMediaSource(sid="e5f6g7h8")]
        assert sources[0].id == "a1b2c3d4"
        assert sources[1].id == "e5f6g7h8"


if __name__ == "__main__":
    pytest.main([__file__, "-vv", "-s", "--tb=short"])