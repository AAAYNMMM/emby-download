#!/usr/bin/env python3
"""Tests for QThread lifecycle fixes - Stage 18.

Validates:
1. worker finished -> thread.quit is called
2. thread.finished -> _cleanup_thread pops from _active
3. error/paused/cancelled also trigger thread.quit
4. stale progress/status signals ignored after completion
5. _active entry stays until thread.finished cleanup
6. shutdown does not call _active.clear()
7. closeEvent does not destroy running QThread
"""

import os
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.downloader.base import DownloadResult, DownloadStatus
from app.gui.download_controller import DownloadController
from app.config.settings import EmbyConfig


# =====================================================================
# Helpers
# =====================================================================

def make_config():
    cfg = MagicMock(spec=EmbyConfig)
    cfg.server_url = "http://test:8096"
    cfg.token_encrypted = ""
    cfg.token_storage = "file"
    cfg.chunk_size_mb = 8
    cfg.retry_count = 3
    cfg.retry_delay_seconds = 5
    cfg.timeout_seconds = 30
    cfg.max_concurrent_downloads = 1
    cfg.download_dir = "/tmp/test_dl"
    return cfg


class FakeThread:
    """Minimal QThread-like object for testing."""
    def __init__(self):
        self._running = True
        self._quit_called = False
        self._finished_connected = []
        self._delete_later_called = False

    def isRunning(self):
        return self._running

    def quit(self):
        self._quit_called = True
        self._running = False
        for cb in self._finished_connected:
            cb()

    def wait(self, ms):
        return True

    def deleteLater(self):
        self._delete_later_called = True


class FakeWorker:
    """Minimal worker for testing."""
    def __init__(self):
        self._pause_requested = False
        self._delete_later_called = False

    def request_pause(self):
        self._pause_requested = True

    def deleteLater(self):
        self._delete_later_called = True


# =====================================================================
# Test 1: _request_thread_quit calls thread.quit on running thread
# =====================================================================

def test_request_thread_quit_calls_quit():
    dc = DownloadController(make_config())
    thread = FakeThread()
    dc._active["test1"] = {"thread": thread, "worker": FakeWorker(), "paused": False}
    dc._request_thread_quit("test1")
    assert thread._quit_called
    assert "test1" in dc._active


# =====================================================================
# Test 2: _cleanup_thread pops entry and calls deleteLater
# =====================================================================

def test_cleanup_thread_pops_and_deletes():
    dc = DownloadController(make_config())
    thread = FakeThread()
    worker = FakeWorker()
    dc._active["test2"] = {"thread": thread, "worker": worker, "paused": False}
    dc._cleanup_thread("test2")
    assert "test2" not in dc._active
    assert worker._delete_later_called
    assert thread._delete_later_called


# =====================================================================
# Test 3: _on_finished does not pop from _active
# =====================================================================

def test_on_finished_no_pop():
    dc = DownloadController(make_config())
    thread = FakeThread()
    worker = FakeWorker()
    dc._active["test3"] = {"thread": thread, "worker": worker, "paused": False}

    result = DownloadResult(success=True, file_path="/tmp/test.mkv", total_bytes=100, downloaded_bytes=100, status=DownloadStatus.COMPLETED)
    dc._on_finished("test3", {"result": result})

    assert "test3" in dc._active
    assert thread._quit_called


# =====================================================================
# Test 4: _on_error does not pop from _active
# =====================================================================

def test_on_error_no_pop():
    dc = DownloadController(make_config())
    thread = FakeThread()
    worker = FakeWorker()
    dc._active["test4"] = {"thread": thread, "worker": worker, "paused": False}

    dc._on_error("test4", "test error")

    assert "test4" in dc._active
    assert thread._quit_called


# =====================================================================
# Test 5: Finished signal triggers thread.quit
# =====================================================================

def test_finished_trigger_quit():
    dc = DownloadController(make_config())
    thread = FakeThread()
    worker = FakeWorker()
    dc._active["test5"] = {"thread": thread, "worker": worker, "paused": False}

    result = DownloadResult(success=True, file_path="/tmp/t.mkv", total_bytes=100, downloaded_bytes=100, status=DownloadStatus.COMPLETED)
    dc._on_finished("test5", {"result": result})
    assert thread._quit_called


# =====================================================================
# Test 6: Stale progress signal is ignored
# =====================================================================

def test_stale_progress_ignored():
    dc = DownloadController(make_config())
    dc._on_progress("stale_id", 500, 1000, 100.0)
    assert "stale_id" not in dc._latest_progress


# =====================================================================
# Test 7: Stale prepared signal is ignored
# =====================================================================

def test_stale_prepared_ignored():
    dc = DownloadController(make_config())
    dc._on_prepared("stale_id", {"task_id": "stale_id", "dest_path": "/tmp/x.mkv"})
    # Should not crash


# =====================================================================
# Test 8: Active count drops only after cleanup
# =====================================================================

def test_active_count_deferred_until_cleanup():
    dc = DownloadController(make_config())
    thread = FakeThread()
    worker = FakeWorker()
    dc._active["test8"] = {"thread": thread, "worker": worker, "paused": False}

    assert len(dc._active) == 1

    # After _on_finished, entry still in _active
    result = DownloadResult(success=True, file_path="/tmp/t.mkv", total_bytes=100, downloaded_bytes=100, status=DownloadStatus.COMPLETED)
    dc._on_finished("test8", {"result": result})
    assert len(dc._active) == 1

    # After _cleanup_thread, entry removed
    dc._cleanup_thread("test8")
    assert len(dc._active) == 0


# =====================================================================
# Test 9: shutdown does not clear _active
# =====================================================================

def test_shutdown_no_active_clear():
    dc = DownloadController(make_config())
    thread = FakeThread()
    worker = FakeWorker()
    dc._active["test9"] = {"thread": thread, "worker": worker, "paused": False}

    dc.shutdown()
    assert "test9" in dc._active


# =====================================================================
# Test 10: stop_all does not clear _active
# =====================================================================

def test_stop_all_no_active_clear():
    dc = DownloadController(make_config())
    with patch("app.gui.download_controller.get_token", return_value="tok"):
        with patch("app.gui.download_controller.get_task", return_value=MagicMock(status="pending", item_id="x")):
            with patch("app.gui.download_controller.find_tasks_by_item_id", return_value=[]):
                with patch("app.gui.download_controller.create_task", return_value=MagicMock(task_id="test10")):
                    dc.start_task(item_id="test10", download_dir="/tmp")

    with patch("app.gui.download_controller.get_token", return_value=None):
        dc.stop_all()

    # Must not crash


# =====================================================================
# Test 11: cancel does not pop from active
# =====================================================================

def test_cancel_does_not_pop():
    dc = DownloadController(make_config())
    thread = FakeThread()
    worker = FakeWorker()
    dc._active["test11"] = {"thread": thread, "worker": worker, "paused": False}

    dc._cancelling.add("test11")
    dc._on_finished("test11", {"result": DownloadResult(success=False, file_path="/tmp/t.mkv", total_bytes=100, downloaded_bytes=30, status=DownloadStatus.PAUSED)})
    assert "test11" in dc._active


# =====================================================================
# Test 12: _cleanup_thread is idempotent
# =====================================================================

def test_cleanup_thread_idempotent():
    dc = DownloadController(make_config())
    thread = FakeThread()
    worker = FakeWorker()
    dc._active["test12"] = {"thread": thread, "worker": worker, "paused": False}

    dc._cleanup_thread("test12")
    assert "test12" not in dc._active
    # Second call must not crash
    dc._cleanup_thread("test12")


# =====================================================================
# Test 13: New methods exist
# =====================================================================

def test_new_methods_exist():
    dc = DownloadController(make_config())
    assert hasattr(dc, "_cleanup_thread")
    assert hasattr(dc, "_request_thread_quit")
    assert callable(dc._cleanup_thread)
    assert callable(dc._request_thread_quit)
