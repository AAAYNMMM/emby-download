"""
Stage 10G tests: GUI download queue and pending-to-active flow.

These tests use fake worker/thread objects so no real HTTP request, token,
server, or download file is touched.  The focus is the Controller state
machine that keeps GUI tasks from getting stuck in pending.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest


class FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback, *args, **kwargs):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self._callbacks):
            try:
                callback(*args)
            except TypeError:
                callback()


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
        was_running = self._running
        self._running = False
        if was_running:
            self.finished.emit()

    def isRunning(self):
        return self._running

    def wait(self, timeout=None):
        self.quit()
        return True

    def deleteLater(self):
        pass


class FakeDownloadWorker:
    instances = []
    mode = "hold"

    def __init__(self):
        self.prepared = FakeSignal()
        self.download_started = FakeSignal()
        self.progress = FakeSignal()
        self.finished = FakeSignal()
        self.error = FakeSignal()
        self.run_calls = []
        self.pause_requested = False
        FakeDownloadWorker.instances.append(self)

    def moveToThread(self, thread):
        self.thread = thread

    def deleteLater(self):
        pass

    def request_pause(self):
        self.pause_requested = True

    def run(self, **kwargs):
        self.run_calls.append(kwargs)
        task_id = kwargs["task_id"]
        self.prepared.emit({
            "task_id": task_id,
            "dest_path": str(Path(kwargs["download_dir"]) / f"{kwargs['item_id']}.mkv"),
        })
        if self.mode == "complete":
            self.download_started.emit({"task_id": task_id})
            self.progress.emit(100, 100, 1024.0)
            self.finished.emit({
                "task_id": task_id,
                "result": make_result(success=True, downloaded_bytes=100),
                "dest_path": str(Path(kwargs["download_dir"]) / f"{kwargs['item_id']}.mkv"),
            })
        elif self.mode == "error":
            self.error.emit("boom")


def make_result(success=True, status=None, downloaded_bytes=100, error_message=""):
    from app.downloader.base import DownloadResult, DownloadStatus

    if status is None:
        status = DownloadStatus.COMPLETED if success else DownloadStatus.FAILED
    return DownloadResult(
        success=success,
        status=status,
        file_path="out.mkv",
        total_bytes=downloaded_bytes,
        downloaded_bytes=downloaded_bytes,
        error_message=error_message,
    )


@pytest.fixture(autouse=True)
def isolate_db(monkeypatch):
    import app.downloader.task_store as ts

    fd, tmp_db = tempfile.mkstemp(suffix=".db", prefix="test_s10g_")
    os.close(fd)
    monkeypatch.setattr(ts, "_DB_PATH", Path(tmp_db))
    yield
    try:
        os.unlink(tmp_db)
    except OSError:
        pass


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def fake_controller(monkeypatch, tmp_path, qapp):
    from app.config.schema import EmbyConfig
    import app.gui.download_controller as dc

    FakeThread.instances.clear()
    FakeDownloadWorker.instances.clear()
    FakeDownloadWorker.mode = "hold"

    monkeypatch.setattr(dc, "QThread", FakeThread)
    monkeypatch.setattr(dc, "DownloadItemWorker", FakeDownloadWorker)
    monkeypatch.setattr(dc, "get_token", lambda config: "fake-token")

    config = EmbyConfig(
        server_url="http://127.0.0.1:8096",
        download_dir=str(tmp_path),
        max_concurrent_downloads=1,
    )
    return dc.DownloadController(config)


def test_movie_start_task_creates_pending_then_pumps_to_completed(fake_controller, tmp_path):
    from app.downloader.task_store import get_task

    task_id = fake_controller.start_task("movie-1", str(tmp_path))
    task = get_task(task_id)
    assert task.status == "preparing"
    assert task.item_id == "movie-1"

    fake_controller._on_download_started(task_id, {"task_id": task_id})
    assert get_task(task_id).status == "downloading"

    fake_controller._on_finished(task_id, {
        "result": make_result(success=True, downloaded_bytes=123),
        "dest_path": str(tmp_path / "movie-1.mkv"),
    })
    task = get_task(task_id)
    assert task.status == "completed"
    assert task.downloaded_bytes == 123


def test_worker_start_error_marks_failed_not_pending(fake_controller, tmp_path):
    from app.downloader.task_store import get_task

    FakeDownloadWorker.mode = "error"
    task_id = fake_controller.start_task("movie-error", str(tmp_path))

    task = get_task(task_id)
    assert task.status == "failed"
    assert task.error_message == "boom"


def test_resume_paused_task_pumps_to_downloading_then_completed(fake_controller, tmp_path):
    from app.downloader.task_store import create_task, get_task, update_task

    task = create_task(item_id="paused-1", title="Paused")
    update_task(task.task_id, status="paused", downloaded_bytes=50)

    resumed = fake_controller.resume_task(task.task_id, str(tmp_path))
    assert resumed == task.task_id
    assert get_task(task.task_id).status == "preparing"
    assert FakeDownloadWorker.instances[-1].run_calls[-1]["resume"] is True

    fake_controller._on_download_started(task.task_id, {"task_id": task.task_id})
    assert get_task(task.task_id).status == "downloading"

    fake_controller._on_finished(task.task_id, {
        "result": make_result(success=True, downloaded_bytes=150),
    })
    assert get_task(task.task_id).status == "completed"


def test_pending_queue_starts_next_after_first_finishes(fake_controller, tmp_path):
    from app.downloader.task_store import get_task

    first = fake_controller.start_task("queue-1", str(tmp_path))
    second = fake_controller.start_task("queue-2", str(tmp_path))

    assert get_task(first).status == "preparing"
    assert get_task(second).status == "pending"
    assert list(fake_controller._active.keys()) == [first]

    fake_controller._on_finished(first, {"result": make_result(success=True)})

    assert get_task(first).status == "completed"
    assert get_task(second).status == "preparing"
    assert list(fake_controller._active.keys()) == [second]


def test_episode_download_selected_tasks_are_independent_and_queued(fake_controller, tmp_path):
    from app.downloader.task_store import get_task

    ep1 = fake_controller.start_task(
        "ep-1", str(tmp_path), media_type="Episode", series_id="series",
        season_id="season-1", episode_id="ep-1", season_number=1,
        episode_number=1, parent_title="Show", display_title="Show S01E01",
    )
    ep2 = fake_controller.start_task(
        "ep-2", str(tmp_path), media_type="Episode", series_id="series",
        season_id="season-1", episode_id="ep-2", season_number=1,
        episode_number=2, parent_title="Show", display_title="Show S01E02",
    )

    t1 = get_task(ep1)
    t2 = get_task(ep2)
    assert t1.media_type == "Episode"
    assert t1.episode_id == "ep-1"
    assert t1.status == "preparing"
    assert t2.media_type == "Episode"
    assert t2.episode_id == "ep-2"
    assert t2.status == "pending"


@pytest.mark.parametrize("status", ["pending", "preparing", "downloading", "paused", "completed"])
def test_duplicate_skip_for_existing_active_or_completed_status(fake_controller, tmp_path, status):
    from app.downloader.task_store import create_task, get_task, update_task

    existing = create_task(item_id="dup-1", title="Duplicate")
    update_task(existing.task_id, status=status)

    returned = fake_controller.start_task("dup-1", str(tmp_path))

    assert returned == existing.task_id
    assert len(FakeDownloadWorker.instances) == 0
    assert get_task(existing.task_id).status == status


def test_gui_status_mapping_chinese():
    from app.gui.i18n import status_text

    assert status_text("preparing") == "准备中"
    assert status_text("downloading") == "下载中"
    assert status_text("pending") == "等待中"


def test_mainwindow_smoke_no_qthread_warning(qapp):
    from app.gui.main_window import MainWindow

    window = MainWindow()
    qapp.processEvents()
    window._shutdown_threads()
    window.close()
    qapp.processEvents()
