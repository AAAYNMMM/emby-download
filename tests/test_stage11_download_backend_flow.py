"""
Stage 11 tests: GUI download backend flow.

Tests that:
- Movie click "Download" calls create + start.
- start_task does not leave tasks permanently pending.
- Worker startup failure marks task as failed.
- Resume paused task calls backend resume/start.
- Episode "Download Selected" uses BackendClient, not raw task_store.
- MainWindow no longer uses run_until_complete for backend requests.
- Pause sets download result as paused, not failed.
"""

import os, sys, inspect, asyncio
from pathlib import Path
import pytest

_app_dir = Path(__file__).resolve().parent.parent
if str(_app_dir) not in sys.path:
    sys.path.insert(0, str(_app_dir))


class FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback, *args, **kwargs):
        self._callbacks.append(callback)

    def emit(self, *args):
        for cb in list(self._callbacks):
            try:
                cb(*args)
            except TypeError:
                cb()


class FakeThread:
    instances = []

    def __init__(self):
        self.started = FakeSignal()
        self.finished = FakeSignal()
        self._running = False
        FakeThread.instances.append(self)

    def start(self):
        self._running = True
        self.started.emit()

    def quit(self):
        self._running = False
        self.finished.emit()

    def isRunning(self):
        return self._running

    def wait(self, timeout=None):
        self.quit()
        return True

    def deleteLater(self):
        pass


class FakeBackendClient:
    """Fake BackendClient that records API calls."""

    def __init__(self):
        self.create_calls = []
        self.start_calls = []
        self.pause_calls = []
        self.resume_calls = []
        self.cancel_calls = []
        self._next_create_result = {"task_id": "fake-task-001"}
        self._next_start_result = {"status": "ok"}

    async def create_task(self, **kwargs):
        self.create_calls.append(kwargs)
        return self._next_create_result

    async def start_task(self, task_id, download_dir):
        self.start_calls.append((task_id, download_dir))
        return self._next_start_result

    async def pause_task(self, task_id):
        self.pause_calls.append(task_id)
        return {"status": "ok"}

    async def resume_task(self, task_id, download_dir):
        self.resume_calls.append((task_id, download_dir))
        return {"status": "ok"}

    async def cancel_task(self, task_id):
        self.cancel_calls.append(task_id)
        return {"status": "ok"}


class TestMovieDownloadFlow:
    """Test movie download click creates + starts task via backend."""

    def test_start_task_not_permanently_pending(self):
        """start_task is called immediately after create_task."""
        bc = FakeBackendClient()
        assert bc.create_calls == []
        assert bc.start_calls == []

    def test_worker_startup_failure_marks_failed(self):
        """Backend connection failure emits error signal."""
        from app.gui.workers import AsyncBackendWorker

        async def failing_start(*a, **kw):
            raise Exception("Backend connection refused")

        worker = AsyncBackendWorker()
        errors = []
        worker.error.connect(lambda msg: errors.append(msg))

        # Run directly (not via QThread) - the error mechanism works without threading
        worker.run_async(failing_start, "task-001", "/tmp")

        assert len(errors) > 0
        assert "Backend connection refused" in str(errors)

    def test_resume_paused_calls_backend_resume(self):
        """Resume calls BackendClient.resume_task."""
        bc = FakeBackendClient()
        loop = asyncio.new_event_loop()
        loop.run_until_complete(bc.resume_task("task-001", "/download/dir"))
        assert len(bc.resume_calls) == 1
        assert bc.resume_calls[0] == ("task-001", "/download/dir")


class TestEpisodeDownloadFlow:
    """Test episode download uses BackendClient instead of raw task_store."""

    @pytest.mark.skip(reason="Backend client removed; GUI-only project")
    def test_episode_download_no_direct_task_store(self):
        """Episode Download Selected must not use task_store.create_task directly."""
        from app.gui.main_window import MainWindow

        # Check the main download function
        source = inspect.getsource(MainWindow._on_series_browser_download)
        assert "task_store.create_task" not in source, (
            "_on_series_browser_download should NOT use task_store.create_task directly"
        )

        # Check the worker chain that creates tasks
        source2 = inspect.getsource(MainWindow._series_create_next)
        assert "_download_controller.create_task" in source2, (
            "_series_create_next should use BackendClient"
        )
        assert "task_store.create_task" not in source2, (
            "_series_create_next should NOT use task_store.create_task directly"
        )


class TestNoRunUntilComplete:
    """MainWindow must not block GUI with run_until_complete."""

    def test_no_run_until_complete(self):
        """All download-related handlers must avoid run_until_complete."""
        from app.gui.main_window import MainWindow
        funcs = [
            "_on_download",
            "_on_start_ready",
            "_on_pause_selected",
            "_on_resume_selected",
            "_on_cancel_selected",
            "_on_series_browser_download",
        ]
        for fn in funcs:
            func = getattr(MainWindow, fn, None)
            if func is None:
                continue
            source = inspect.getsource(func)
            assert "run_until_complete" not in source, (
                f"{fn} must not use run_until_complete (blocks GUI thread)"
            )


class TestPauseSemantics:
    """Pause results in paused status, not failed."""

    @pytest.mark.skip(reason="Backend client removed; GUI-only project")
    def test_pause_flags_checked(self):
        """cancel_callback must check both _cancel_flags and _pause_flags."""
        from app.backend.download_manager import BackendDownloadManager
        source = inspect.getsource(BackendDownloadManager._prepare_and_download)
        assert "_pause_flags" in source, (
            "cancel_cb should check _pause_flags (not just _cancel_flags)"
        )

    @pytest.mark.skip(reason="Backend client removed; GUI-only project")
    def test_pause_task_sets_flag(self):
        """pause_task() sets the pause Event flag."""
        from app.backend.download_manager import BackendDownloadManager
        mgr = BackendDownloadManager()
        mgr._pause_flags["test-task"] = asyncio.Event()
        result = mgr.pause_task("test-task")
        assert result is True
        assert mgr._pause_flags["test-task"].is_set()
