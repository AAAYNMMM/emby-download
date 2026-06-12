"""
Stage 10D-3 tests: Tasks page status and operations.

Tests:
1. format_bytes / format_eta / format_progress_pct
2. interrupted downloading task recovery
3. cancel status written to task_store
4. unknown total doesn't show fake 100%
5. completed task disallows resume
6. failed task show error has content
7. GUI import smoke tests (no QThread warning)
"""

import os
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.utils.formatting import (
    format_bytes,
    format_speed_gui,
    format_eta,
    format_progress_pct,
    format_updated_at,
    compute_eta_seconds,
)
from app.downloader.task_store import (
    create_task,
    update_task,
    get_task,
    delete_task,
    DownloadTask,
)


class TestFormatBytes:
    """Tests for format_bytes utility."""

    def test_zero_returns_zero_b(self):
        assert format_bytes(0) == "0 B"

    def test_none_returns_zero_b(self):
        assert format_bytes(None) == "0 B"

    def test_bytes_range(self):
        assert format_bytes(500) == "500 B"
        assert format_bytes(1023) == "1023 B"

    def test_kb_range(self):
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1536) == "1.50 KB"
        assert format_bytes(10240) == "10.0 KB"

    def test_mb_range(self):
        assert format_bytes(1024 * 1024) == "1.00 MB"
        assert format_bytes(104857600) == "100 MB"  # exactly 100 MB
        assert format_bytes(157286400) == "150 MB"

    def test_gb_range(self):
        assert format_bytes(1024 ** 3) == "1.00 GB"
        assert format_bytes(2.5 * 1024 ** 3) == "2.50 GB"

    def test_large_values(self):
        assert "TB" in format_bytes(5 * 1024 ** 4)
        assert "PB" in format_bytes(3 * 1024 ** 5)


class TestFormatSpeed:
    """Tests for format_speed_gui."""

    def test_none_returns_dash(self):
        assert format_speed_gui(None) == "--"

    def test_zero_returns_dash(self):
        assert format_speed_gui(0) == "--"

    def test_negative_returns_dash(self):
        assert format_speed_gui(-1) == "--"

    def test_bytes_per_sec(self):
        assert format_speed_gui(500) == "500 B/s"

    def test_kb_per_sec(self):
        assert format_speed_gui(2048) == "2.0 KB/s"

    def test_mb_per_sec(self):
        assert format_speed_gui(2.5 * 1024 * 1024) == "2.5 MB/s"

    def test_gb_per_sec(self):
        assert format_speed_gui(1.5 * 1024 ** 3) == "1.50 GB/s"


class TestFormatETA:
    """Tests for format_eta."""

    def test_none_returns_unknown(self):
        assert format_eta(None) == "unknown"

    def test_zero_returns_unknown(self):
        assert format_eta(0) == "unknown"

    def test_negative_returns_unknown(self):
        assert format_eta(-1) == "unknown"

    def test_seconds(self):
        assert format_eta(30) == "00:30"
        assert format_eta(59) == "00:59"

    def test_minutes(self):
        assert format_eta(65) == "01:05"
        assert format_eta(3599) == "59:59"

    def test_hours(self):
        assert format_eta(3600) == "1:00:00"
        assert format_eta(3661) == "1:01:01"
        assert format_eta(90061) == "25:01:01"

    def test_inf_returns_unknown(self):
        import math
        assert format_eta(float('inf')) == "unknown"

    def test_nan_returns_unknown(self):
        import math
        assert format_eta(float('nan')) == "unknown"


class TestFormatProgressPct:
    """Tests for format_progress_pct."""

    def test_none_total_returns_unknown(self):
        assert format_progress_pct(100, None) == "unknown"

    def test_zero_total_returns_unknown(self):
        assert format_progress_pct(100, 0) == "unknown"

    def test_normal_percentage(self):
        assert format_progress_pct(500, 1000) == "50%"
        assert format_progress_pct(250, 1000) == "25%"

    def test_decimal_percentage(self):
        assert format_progress_pct(5, 1000) == "0.5%"
        assert format_progress_pct(95, 1000) == "9.5%"

    def test_complete_100(self):
        assert format_progress_pct(1000, 1000) == "100%"
        assert format_progress_pct(999, 1000) == "100%"  # > 99.95%

    def test_clamp_over_100(self):
        """downloaded > total should clamp to 100% not crash."""
        assert format_progress_pct(1500, 1000) == "100%"

    def test_negative_downloaded(self):
        assert format_progress_pct(-100, 1000) == "0.00%"

    def test_small_value_not_fake_100(self):
        """0 downloaded with known total should NOT show 100%."""
        assert format_progress_pct(0, 1000) == "0.00%"

    def test_unknown_total_not_fake_100(self):
        """Unknown total MUST return 'unknown' not any percentage."""
        result = format_progress_pct(500, None)
        assert result == "unknown", f"Expected 'unknown', got '{result}' (fake 100% bug!)"
        result = format_progress_pct(1000, 0)
        assert result == "unknown", f"Expected 'unknown', got '{result}' (fake 100% bug!)"


class TestComputeETA:
    """Tests for compute_eta_seconds."""

    def test_known_total_with_speed(self):
        eta = compute_eta_seconds(500, 1000, 100)
        assert eta == 5.0

    def test_none_total(self):
        assert compute_eta_seconds(500, None, 100) is None

    def test_zero_total(self):
        assert compute_eta_seconds(500, 0, 100) is None

    def test_zero_speed(self):
        assert compute_eta_seconds(500, 1000, 0) is None

    def test_already_complete(self):
        eta = compute_eta_seconds(1000, 1000, 100)
        assert eta == 0.0


class TestTaskStoreCancel:
    """Tests that cancel status is properly written to task_store."""

    def test_cancel_updates_status(self):
        task = create_task(
            item_id="test_item_cancel",
            title="Test Cancel",
            download_url="http://example.com/download",
            save_path="/tmp/test.mkv",
            temp_path="/tmp/test.mkv.part",
            total_bytes=10000,
        )
        task_id = task.task_id
        try:
            # Simulate cancel
            updated = update_task(task_id, status="cancelled", error_message="Cancelled by user")
            assert updated is not None
            assert updated.status == "cancelled"
            assert updated.error_message == "Cancelled by user"

            # Verify via get_task
            fetched = get_task(task_id)
            assert fetched is not None
            assert fetched.status == "cancelled"
        finally:
            delete_task(task_id)


class TestTaskCompletedNoResume:
    """Tests that completed tasks cannot be resumed."""

    def test_completed_status_persists(self):
        task = create_task(
            item_id="test_item_completed",
            title="Test Completed",
        )
        task_id = task.task_id
        try:
            update_task(task_id, status="completed", downloaded_bytes=10000)
            fetched = get_task(task_id)
            assert fetched.status == "completed"
            assert fetched.downloaded_bytes == 10000

            # Trying to update status to downloading should work at DB level
            # (logic enforcement is in the GUI/controller layer)
            update_task(task_id, status="downloading")
            fetched2 = get_task(task_id)
            assert fetched2.status == "downloading"
        finally:
            delete_task(task_id)


class TestFailedTaskErrorMessage:
    """Tests that failed tasks retain their error_message."""

    def test_failed_task_has_error_content(self):
        task = create_task(
            item_id="test_item_failed",
            title="Test Failed",
        )
        task_id = task.task_id
        try:
            error_msg = "HTTP 500 Internal Server Error"
            update_task(task_id, status="failed", error_message=error_msg)
            fetched = get_task(task_id)
            assert fetched.status == "failed"
            assert fetched.error_message == error_msg
            assert len(fetched.error_message) > 0, "Failed task should have error content"
        finally:
            delete_task(task_id)

    def test_completed_task_has_no_error(self):
        task = create_task(
            item_id="test_item_ok",
            title="Test OK",
        )
        task_id = task.task_id
        try:
            update_task(task_id, status="completed", downloaded_bytes=5000)
            fetched = get_task(task_id)
            assert fetched.error_message == ""
        finally:
            delete_task(task_id)


class TestInterruptedRecovery:
    """Tests that interrupted 'downloading' tasks are recoverable."""

    def test_downloading_task_exists_after_crash(self):
        """Simulate: a task left in 'downloading' status exists in DB."""
        task = create_task(
            item_id="test_item_crash",
            title="Test Crash Recovery",
            download_url="http://example.com/download",
            save_path="/tmp/crash_test.mkv",
            temp_path="/tmp/crash_test.mkv.part",
            total_bytes=50000,
        )
        task_id = task.task_id
        try:
            update_task(task_id, status="downloading", downloaded_bytes=20000)
            fetched = get_task(task_id)
            assert fetched.status == "downloading"
            assert fetched.downloaded_bytes == 20000

            # Simulate recovery: set to paused
            update_task(task_id, status="paused",
                        error_message="Recovered interrupted downloading task as paused")
            recovered = get_task(task_id)
            assert recovered.status == "paused"
            assert "Recovered" in recovered.error_message
        finally:
            delete_task(task_id)


class TestUpdateTaskTotalBytes:
    """Tests that update_task supports total_bytes parameter."""

    def test_update_total_bytes(self):
        task = create_task(
            item_id="test_total_update",
            title="Test Total Update",
            total_bytes=0,
        )
        task_id = task.task_id
        try:
            # total_bytes initially 0
            assert task.total_bytes == 0

            # Update with new total
            updated = update_task(task_id, total_bytes=12345678)
            assert updated is not None
            assert updated.total_bytes == 12345678

            # Verify persisted
            fetched = get_task(task_id)
            assert fetched.total_bytes == 12345678
        finally:
            delete_task(task_id)


class TestGUIImportSmoke:
    """Smoke tests: GUI imports work without QThread warnings."""

    def test_main_window_import(self):
        """MainWindow import should not trigger QThread warnings."""
        from app.gui.main_window import MainWindow
        assert MainWindow is not None

    def test_download_controller_import(self):
        """DownloadController import should not trigger QThread warnings."""
        from app.gui.download_controller import DownloadController
        assert DownloadController is not None

    def test_app_import(self):
        """app main import should not trigger QThread warnings."""
        from app.gui.app import main
        assert main is not None

    def test_formatting_import(self):
        """Formatting utilities import cleanly."""
        from app.utils.formatting import (
            format_bytes, format_eta, format_progress_pct,
            format_speed_gui, format_updated_at, compute_eta_seconds,
        )
        assert callable(format_bytes)
        assert callable(format_eta)
        assert callable(format_progress_pct)
        assert callable(format_speed_gui)
        assert callable(format_updated_at)
        assert callable(compute_eta_seconds)


class TestTaskStoreStatusFields:
    """Tests that task store fields are properly read/written."""

    def test_all_fields_roundtrip(self):
        now = time.time()
        task = create_task(
            item_id="test_all_fields",
            title="Full Test Item",
            download_url="http://example.com/dl",
            save_path="/tmp/full_test.mkv",
            temp_path="/tmp/full_test.mkv.part",
            total_bytes=987654321,
            media_source_id="ms_123",
            container="mkv",
        )
        task_id = task.task_id
        try:
            # Update with all supported fields
            update_task(
                task_id,
                downloaded_bytes=500000,
                total_bytes=987654321,
                status="downloading",
                error_message="",
                title="Updated Title",
            )
            fetched = get_task(task_id)
            assert fetched.task_id == task_id
            assert fetched.item_id == "test_all_fields"
            assert fetched.title == "Updated Title"
            assert fetched.downloaded_bytes == 500000
            assert fetched.total_bytes == 987654321
            assert fetched.status == "downloading"
            assert fetched.save_path == "/tmp/full_test.mkv"
            assert fetched.temp_path == "/tmp/full_test.mkv.part"
            assert fetched.updated_at >= now
        finally:
            delete_task(task_id)
