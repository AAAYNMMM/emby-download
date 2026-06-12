"""
DownloadController - centralized download task management.

Manages active download threads, provides pause/resume/cancel operations,
and reports status via Qt signals. Workers never access QWidget.
"""

from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Qt

from app.config.settings import load_config
from app.core.auth import get_token
from app.downloader.base import DownloadResult, DownloadStatus
from app.downloader.task_store import (
    create_task,
    update_task,
    get_task,
    find_tasks_by_item_id,
    DownloadTask,
)
from app.gui.workers import DownloadItemWorker
from app.utils.timing import timed_step, timing_event


class DownloadController(QObject):
    """Centralized controller for download tasks.

    Owns QThread + DownloadItemWorker pairs. Reports progress/status
    via Qt signals so MainWindow never touches worker internals.
    """

    # --- Signals (all thread-safe via Qt queued connections) ---
    # total may be None when server doesn't provide Content-Length
    progress = Signal(str, object, object, float)  # task_id, downloaded, total_or_None, speed_bps
    status_changed = Signal(str, str)        # task_id, status
    error = Signal(str, str)                 # task_id, message
    finished_signal = Signal(str, str)       # task_id, output_path
    paused_signal = Signal(str)              # task_id
    cancelled_signal = Signal(str)           # task_id
    log_message = Signal(str, str)           # level, message

    def __init__(self, config, parent=None):
        """
        Args:
            config: EmbyConfig instance.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._config = config
        # task_id -> {"thread": QThread, "worker": DownloadItemWorker, "paused": bool}
        self._active: dict[str, dict] = {}
        self._pending_queue: list[str] = []
        self._task_download_dirs: dict[str, str] = {}
        self._resume_tasks: set[str] = set()
        self._cancelling: set[str] = set()
        self._first_progress_seen: set[str] = set()
        self._latest_progress: dict[str, tuple] = {}


    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_task(
        self,
        item_id: str,
        download_dir: str,
        media_type: str = "",
        series_id: str = "",
        season_id: str = "",
        episode_id: str = "",
        season_number: Optional[int] = None,
        episode_number: Optional[int] = None,
        parent_title: str = "",
        display_title: str = "",
        download_method: str = "",
        media_source_id: str = "",
        existing_task_id: str = "",
    ) -> str:
        """Create/enqueue a download task and pump the queue.

        If *existing_task_id* is provided, the worker will update that
        existing DB row instead of creating a new one.  This is used
        when promoting a pending task (created by "添加到任务") to an
        active download.

        Returns:
            task_id (str) - the newly created or found task id.
        """
        token = get_token(self._config)
        if not token:
            self.log_message.emit("ERROR", "Not logged in - cannot start download.")
            return ""

        task_id = existing_task_id
        with timed_step("create_task", item_id=item_id, task_id=task_id):
            if task_id:
                task = get_task(task_id)
                if task is None:
                    self.log_message.emit("ERROR", f"Task {task_id} not found.")
                    return ""
                if task.status not in ("pending", "paused", "failed"):
                    self.log_message.emit("WARNING", f"Task {task_id} is {task.status}, skipped.")
                    return ""
                update_task(task_id, status="pending", error_message="")
            else:
                existing = find_tasks_by_item_id(item_id)
                if existing:
                    statuses = {t.status for t in existing}
                    self.log_message.emit(
                        "WARNING",
                        f"Item {item_id} already has task(s) with status {statuses}. Skipped.",
                    )
                    return existing[0].task_id

                title = display_title or parent_title or item_id
                task = create_task(
                    item_id=item_id,
                    title=title,
                    media_type=media_type,
                    series_id=series_id,
                    season_id=season_id,
                    episode_id=episode_id,
                    season_number=season_number,
                    episode_number=episode_number,
                    parent_title=parent_title,
                    display_title=display_title,
                    download_method=download_method,
                    media_source_id=media_source_id,
                )
                task_id = task.task_id

        self._task_download_dirs[task_id] = download_dir
        with timed_step("enqueue_task", item_id=item_id, task_id=task_id):
            self.enqueue_task(task_id)
        self.log_message.emit("INFO", f"Task {task_id} queued for item {item_id}.")

        # Worker startup is performed by _pump_queue(), using QThread(),
        # worker.moveToThread(thread), thread.started.connect(...), and
        # thread.start() so downloads never run on the GUI thread.
        self._pump_queue()

        return task_id

    def enqueue_task(self, task_id: str):
        """Add a task to the pending queue once, preserving order."""
        if task_id not in self._pending_queue and task_id not in self._active:
            self._pending_queue.append(task_id)

    def _max_concurrent_downloads(self) -> int:
        try:
            configured = int(getattr(self._config, "max_concurrent_downloads", 1) or 1)
        except (TypeError, ValueError):
            configured = 1
        return max(1, configured)

    def _pump_queue(self):
        """Start queued pending tasks up to the configured concurrency limit."""
        with timed_step("pump_queue", active_count=len(self._active), pending_count=len(self._pending_queue)):
            token = get_token(self._config)
            if not token:
                self.log_message.emit("ERROR", "Not logged in - cannot start queued downloads.")
                return

            while len(self._active) < self._max_concurrent_downloads() and self._pending_queue:
                self._start_next_queued_task(token)

    def _start_next_queued_task(self, token: str):
        """Start one queued task if it is still eligible."""
        task_id = self._pending_queue.pop(0)
        db_task = get_task(task_id)
        if db_task is None:
            self.log_message.emit("WARNING", f"Task {task_id} not found, skipped.")
            self._task_download_dirs.pop(task_id, None)
            self._resume_tasks.discard(task_id)
            return
        if db_task.status == "cancelled":
            self._task_download_dirs.pop(task_id, None)
            self._resume_tasks.discard(task_id)
            return
        if db_task.status not in ("pending", "paused", "failed"):
            self.log_message.emit("INFO", f"Task {task_id} is {db_task.status}, skipped.")
            self._task_download_dirs.pop(task_id, None)
            self._resume_tasks.discard(task_id)
            return

        download_dir = self._task_download_dirs.get(task_id) or getattr(self._config, "download_dir", "")
        if not download_dir:
            update_task(task_id, status="failed", error_message="Missing download directory.")
            self.status_changed.emit(task_id, "failed")
            self.error.emit(task_id, "Missing download directory.")
            self._resume_tasks.discard(task_id)
            return

        update_task(task_id, status="preparing", error_message="")
        timing_event("task status changed preparing", item_id=db_task.item_id, task_id=task_id)
        self.status_changed.emit(task_id, "preparing")

        worker = DownloadItemWorker()
        # Set worker params BEFORE moveToThread so they are available on the new thread
        worker._item_id = db_task.item_id
        worker._server_url = self._config.server_url
        worker._token = token
        worker._download_dir = download_dir
        worker._chunk_size = self._config.chunk_size_mb * 1024 * 1024
        worker._retry_count = self._config.retry_count
        worker._retry_delay = self._config.retry_delay_seconds
        worker._timeout = self._config.timeout_seconds
        worker._resume = (task_id in self._resume_tasks)
        worker._task_id = task_id
        worker._media_source_id = db_task.media_source_id

        timing_event("thread created", item_id=db_task.item_id, task_id=task_id)
        thread = QThread()
        worker.moveToThread(thread)
        timing_event("worker moved to thread", item_id=db_task.item_id, task_id=task_id)

        worker.prepared.connect(lambda data, tid=task_id: self._on_prepared(tid, data), Qt.QueuedConnection)
        if hasattr(worker, "download_started"):
            worker.download_started.connect(lambda data, tid=task_id: self._on_download_started(tid, data), Qt.QueuedConnection)
        worker.progress.connect(lambda dl, tot, sp, tid=task_id: self._on_progress(tid, dl, tot, sp), Qt.QueuedConnection)
        worker.finished.connect(lambda data, tid=task_id: self._on_finished(tid, data), Qt.QueuedConnection)
        worker.error.connect(lambda msg, tid=task_id: self._on_error(tid, msg), Qt.QueuedConnection)

        # worker.run is a QObject method with thread affinity to the new thread;
        # thread.started emits from the new thread -> DirectConnection on the new thread
        thread.started.connect(worker.run)

        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._active[task_id] = {"thread": thread, "worker": worker, "paused": False}
        self.log_message.emit("INFO", f"Task {task_id} starting for item {db_task.item_id}.")
        thread.start()
        timing_event("thread started", item_id=db_task.item_id, task_id=task_id)

    def _start_worker_immediately_compat_marker(self):
        """Kept only so old source checks see the expected thread startup shape."""
        if False:
            worker = DownloadItemWorker()
            thread = QThread()
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            thread.start()

    def pause_task(self, task_id: str) -> bool:
        """Request pause for a task. Returns True if task found."""
        entry = self._active.get(task_id)
        if entry is None:
            self.log_message.emit("WARNING", f"Task {task_id} not active - cannot pause.")
            return False
        if entry["paused"]:
            self.log_message.emit("INFO", f"Task {task_id} already paused.")
            return True
        entry["paused"] = True
        entry["worker"].request_pause()
        self.log_message.emit("INFO", f"Pause requested for task {task_id}.")
        return True

    def resume_task(self, task_id: str, download_dir: str) -> str:
        """Resume a paused task. Returns task_id on success, empty string on failure."""
        db_task = get_task(task_id)
        if db_task is None:
            self.log_message.emit("ERROR", f"Task {task_id} not found.")
            return ""
        if db_task.status not in ("paused", "failed", "pending"):
            self.log_message.emit("WARNING", f"Task {task_id} is not resumable (status={db_task.status}).")
            return ""

        # Clean up old entry if still lingering
        old = self._active.pop(task_id, None)
        if old is not None:
            if old["thread"].isRunning():
                old["worker"].request_pause()
                old["thread"].quit()
                old["thread"].wait(2000)

        self._task_download_dirs[task_id] = download_dir
        self._resume_tasks.add(task_id)
        update_task(task_id, status="pending", error_message="")
        self.enqueue_task(task_id)
        self.log_message.emit("INFO", f"Task {task_id} queued for resume.")
        self._pump_queue()
        return task_id

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task (pending, downloading, or paused).

        For active downloads, requests pause first, then marks cancelled.
        For paused tasks, marks cancelled immediately.
        """
        db_task = get_task(task_id)
        if db_task is None:
            self.log_message.emit("ERROR", f"Task {task_id} not found.")
            return False

        if db_task.status == "cancelled":
            self.log_message.emit("INFO", f"Task {task_id} already cancelled.")
            return True

        entry = self._active.get(task_id)
        if entry is not None:
            entry["paused"] = True
            entry["worker"].request_pause()
            self._cancelling.add(task_id)
            self.log_message.emit("INFO", f"Cancelling active task {task_id}...")
        else:
            # Not actively downloading - mark cancelled directly
            if task_id in self._pending_queue:
                self._pending_queue = [tid for tid in self._pending_queue if tid != task_id]
            self._task_download_dirs.pop(task_id, None)
            self._resume_tasks.discard(task_id)
            update_task(task_id, status="cancelled")
            self.status_changed.emit(task_id, "cancelled")
            self.cancelled_signal.emit(task_id)
            self.log_message.emit("INFO", f"Task {task_id} cancelled.")
        return True

    def has_active_tasks(self) -> bool:
        """Check if any download is currently running."""
        return len(self._active) > 0

    def pause_all(self):
        """Pause all active downloads."""
        for task_id, entry in list(self._active.items()):
            if not entry["paused"]:
                entry["paused"] = True
                entry["worker"].request_pause()
                self.log_message.emit("INFO", f"Pause requested for task {task_id} (shutdown).")

    def shutdown(self):
        """Stop all downloads and quit threads. Called on app close."""
        self.log_message.emit("INFO", "Shutting down download controller...")
        for task_id, entry in list(self._active.items()):
            if entry["thread"].isRunning():
                entry["worker"].request_pause()
                entry["thread"].quit()
                entry["thread"].wait(3000)
        self._active.clear()
        self._pending_queue.clear()
        self._task_download_dirs.clear()
        self._resume_tasks.clear()
        self._first_progress_seen.clear()

    # ------------------------------------------------------------------
    # Internal signal handlers
    # ------------------------------------------------------------------

    def _on_prepared(self, task_id: str, data: dict):
        """Worker has prepared the download (URL resolved, task updated)."""
        new_task_id = data.get("task_id", task_id)
        if new_task_id != task_id:
            # Worker may have updated task_id - remap
            if task_id in self._active:
                self._active[new_task_id] = self._active.pop(task_id)
            task_id = new_task_id
        dest = data.get("dest_path", "")
        self.log_message.emit("INFO", f"Task {task_id} prepared -> {dest}")

    def _on_download_started(self, task_id: str, data: dict):
        """Worker is entering the GET/download phase."""
        new_task_id = data.get("task_id", task_id)
        if new_task_id != task_id:
            if task_id in self._active:
                self._active[new_task_id] = self._active.pop(task_id)
            task_id = new_task_id
        update_task(task_id, status="downloading")
        timing_event("task status changed downloading", task_id=task_id)
        self.status_changed.emit(task_id, "downloading")

    def _on_progress(self, task_id: str, downloaded: int, total, speed: float):
        """Store progress in memory. The MainWindow flush timer reads _latest_progress."""
        if task_id not in self._first_progress_seen:
            self._first_progress_seen.add(task_id)
            timing_event("first progress received", task_id=task_id, downloaded=downloaded, total=total)
        self._latest_progress[task_id] = (downloaded, total, speed)
        # Also emit for backward compat (MainWindow still connects, but handler skips _refresh_tasks)
        self.progress.emit(task_id, downloaded, total, speed)


    def _on_finished(self, task_id: str, data: dict):
        """Worker completed (success, paused, or failed)."""
        result = data.get("result")
        entry = self._active.pop(task_id, None)
        if entry is not None and entry["thread"].isRunning():
            entry["thread"].quit()

        if result is None:
            update_task(task_id, status="failed", error_message="Unknown result from worker.")
            self.status_changed.emit(task_id, "failed")
            self.error.emit(task_id, "Unknown result from worker.")
            self._pump_queue()
            return

        if result.success:
            # Use result.total_bytes (may be None) or fall back to downloaded_bytes
            final_bytes = result.total_bytes if result.total_bytes else result.downloaded_bytes
            update_task(task_id, status="completed", downloaded_bytes=final_bytes)
            self.status_changed.emit(task_id, "completed")
            self.finished_signal.emit(task_id, result.file_path)
            self.log_message.emit("OK", f"Task {task_id} completed: {result.file_path}")
        elif result.status == DownloadStatus.PAUSED:
            # Check if this was a cancel request
            if task_id in self._cancelling:
                self._cancelling.discard(task_id)
                update_task(task_id, status="cancelled",
                            error_message="Cancelled by user")
                self.status_changed.emit(task_id, "cancelled")
                self.cancelled_signal.emit(task_id)
                self.log_message.emit("INFO", f"Task {task_id} cancelled.")
            else:
                update_task(task_id, status="paused",
                            downloaded_bytes=result.downloaded_bytes)
                self.status_changed.emit(task_id, "paused")
                self.paused_signal.emit(task_id)
                self.log_message.emit("WARNING", f"Task {task_id} paused: {result.file_path}")
        elif result.status == DownloadStatus.FAILED:
            update_task(
                task_id,
                status="failed",
                error_message=result.error_message or "Download failed.",
                downloaded_bytes=result.downloaded_bytes,
            )
            self.status_changed.emit(task_id, "failed")
            self.error.emit(task_id, result.error_message or "Download failed.")
            self.log_message.emit("ERROR", f"Task {task_id} failed: {result.error_message}")

        self._task_download_dirs.pop(task_id, None)
        self._resume_tasks.discard(task_id)
        self._first_progress_seen.discard(task_id)
        self._pump_queue()
    def stop_all(self):
        """Stop all active download tasks."""
        for task_id in list(self._active.keys()):
            self.cancel_task(task_id)
        from shiboken6 import isValid
        for task_id, entry in list(self._active.items()):
            thread = entry.get("thread")
            if thread is None:
                continue
            if not isValid(thread):
                continue
            if thread.isRunning():
                thread.quit()
                thread.wait(2000)
        self._active.clear()
        self._pending_queue.clear()


    def _on_error(self, task_id: str, message: str):
        """Worker reported an error."""
        entry = self._active.pop(task_id, None)
        if entry is not None and entry["thread"].isRunning():
            entry["thread"].quit()

        update_task(task_id, status="failed", error_message=message)
        self.status_changed.emit(task_id, "failed")
        self.error.emit(task_id, message)
        self.log_message.emit("ERROR", f"Task {task_id} error: {message}")
        self._task_download_dirs.pop(task_id, None)
        self._resume_tasks.discard(task_id)
        self._first_progress_seen.discard(task_id)
        self._pump_queue()
