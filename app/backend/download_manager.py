# Stage 11: Backend download manager
# Manages download queue using asyncio tasks.
# Broadcasts events via callbacks (WebSocket bridge).

import asyncio
import time
from typing import Optional, Callable

from app.config.settings import load_config
from app.core.auth import get_token
from app.core.download_preview import build_download_preview
from app.core.emby_api import EmbyApiClient
from app.core.playback_info import parse_media_sources, select_best_source
from app.core.download_capability import check_download_capability
from app.downloader.base import DownloadResult, DownloadStatus
from app.downloader.direct_download import download_direct
from app.downloader.stream_download import download_stream
from app.downloader.task_store import (
    create_task,
    update_task,
    get_task,
    find_tasks_by_item_id,
    list_tasks,
    DownloadTask,
)
from app.utils.logger import get_logger

_logger = get_logger()


EventCallback = Callable[[str, dict], None]


class BackendDownloadManager:
    """Manages the download queue in the backend process.

    Handles task lifecycle: create, prepare, download, pause, resume, cancel.
    Broadcasts events via an event_callback (typically to WebSocket clients).
    """

    def __init__(self, config=None, event_callback: Optional[EventCallback] = None):
        self._config = config or load_config()
        self._event_callback = event_callback
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._pause_flags: dict[str, asyncio.Event] = {}
        self._cancel_flags: dict[str, asyncio.Event] = {}
        self._max_concurrent = self._config.max_concurrent_downloads or 1
        self._semaphore = asyncio.Semaphore(self._max_concurrent)

    def set_event_callback(self, cb: EventCallback):
        self._event_callback = cb

    def _emit(self, event_type: str, data: dict):
        if self._event_callback:
            try:
                self._event_callback(event_type, data)
            except Exception:
                pass

    # ---- Public API ----

    async def create_pending_task(self, item_id: str, download_dir: str = "",
                                   media_type: str = "", series_id: str = "",
                                   season_id: str = "", episode_id: str = "",
                                   season_number: Optional[int] = None,
                                   episode_number: Optional[int] = None,
                                   parent_title: str = "", display_title: str = "",
                                   download_method: str = "",
                                   media_source_id: str = "") -> Optional[dict]:
        """Create a pending task and return its dict representation."""
        existing = find_tasks_by_item_id(item_id)
        if existing:
            statuses = {t.status for t in existing}
            _logger.warning(f"Item {item_id} already has tasks: {statuses}")
            return None

        title = display_title or parent_title or item_id
        task = create_task(
            item_id=item_id, title=title,
            media_type=media_type, series_id=series_id,
            season_id=season_id, episode_id=episode_id,
            season_number=season_number, episode_number=episode_number,
            parent_title=parent_title, display_title=display_title,
            download_method=download_method,
            media_source_id=media_source_id,
        )
        self._emit("task_created", _task_to_dict(task))
        return _task_to_dict(task)

    async def start_task(self, task_id: str, download_dir: str) -> bool:
        """Start a pending/paused/failed task."""
        task = get_task(task_id)
        if task is None:
            _logger.error(f"Task {task_id} not found")
            return False
        if task.status not in ("pending", "paused", "failed"):
            _logger.warning(f"Task {task_id} is {task.status}, not starting")
            return False

        update_task(task_id, status="preparing", error_message="")
        self._emit("status_changed", {"task_id": task_id, "status": "preparing"})

        asyncio_task = asyncio.create_task(self._download_task(task_id, download_dir))
        self._active_tasks[task_id] = asyncio_task
        return True

    async def start_multiple(self, task_ids: list[str], download_dir: str) -> int:
        """Start multiple tasks. Returns count of tasks started."""
        started = 0
        for tid in task_ids:
            if await self.start_task(tid, download_dir):
                started += 1
        return started

    def pause_task(self, task_id: str) -> bool:
        """Signal a task to pause."""
        if task_id in self._pause_flags:
            self._pause_flags[task_id].set()
            return True
        return False

    def resume_task(self, task_id: str, download_dir: str) -> bool:
        """Resume a paused/failed/pending task."""
        task = get_task(task_id)
        if task is None:
            _logger.error(f"Resume: task {task_id} not found")
            return False
        if task.status not in ("paused", "failed", "pending"):
            _logger.warning(f"Resume: task {task_id} is {task.status}, not resuming")
            return False
        asyncio.ensure_future(self._resume_task(task_id, download_dir))
        return True

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        if task_id in self._cancel_flags:
            self._cancel_flags[task_id].set()
            return True
        # If not running, mark cancelled directly
        task = get_task(task_id)
        if task and task.status in ("pending", "paused", "failed"):
            update_task(task_id, status="cancelled", error_message="Cancelled by user")
            self._emit("status_changed", {"task_id": task_id, "status": "cancelled"})
            return True
        return False

    def delete_task(self, task_id: str) -> bool:
        """Delete a task. Cancels first if running."""
        self.cancel_task(task_id)
        from app.downloader.task_store import delete_task as db_delete_task
        result = db_delete_task(task_id)
        if result:
            self._emit("task_deleted", {"task_id": task_id})
        return result

    async def list_tasks_api(self, status_filter: Optional[str] = None,
                              limit: int = 200) -> list[dict]:
        """Return list of tasks as dicts."""
        from app.downloader.task_store import count_tasks
        tasks = list_tasks(status_filter=status_filter, limit=limit)
        return [_task_to_dict(t) for t in tasks]

    # ---- Internal download logic ----

    async def _download_task(self, task_id: str, download_dir: str):
        """Full download lifecycle: prepare → download → finish."""
        async with self._semaphore:
            self._pause_flags[task_id] = asyncio.Event()
            self._cancel_flags[task_id] = asyncio.Event()

            try:
                success = await self._prepare_and_download(task_id, download_dir)
            except asyncio.CancelledError:
                update_task(task_id, status="cancelled", error_message="Task cancelled")
                self._emit("status_changed", {"task_id": task_id, "status": "cancelled"})
            except Exception as e:
                _logger.error(f"Task {task_id} crashed: {e}")
                update_task(task_id, status="failed", error_message=str(e))
                self._emit("error", {"task_id": task_id, "message": str(e)})
                self._emit("status_changed", {"task_id": task_id, "status": "failed"})
            finally:
                self._active_tasks.pop(task_id, None)
                self._pause_flags.pop(task_id, None)
                self._cancel_flags.pop(task_id, None)

    async def _prepare_and_download(self, task_id: str, download_dir: str) -> bool:
        """Prepare download (resolve URL) then execute it.

        Each step sets a descriptive error_message on failure so the GUI
        error tab can display exactly what went wrong.
        """
        # ===== Step 1: Token =====
        token = get_token(self._config)
        if not token:
            msg = "Not logged in - token not available"
            update_task(task_id, status="failed", error_message=msg)
            self._emit("error", {"task_id": task_id, "message": msg})
            self._emit("status_changed", {"task_id": task_id, "status": "failed"})
            return False

        # ===== Step 2: Load task =====
        task = get_task(task_id)
        if task is None:
            msg = f"Task {task_id} not found in database"
            _logger.error(msg)
            return False

        # ===== Step 3: Prepare phase start =====
        update_task(task_id, status="preparing", error_message="")
        self._emit("status_changed", {"task_id": task_id, "status": "preparing"})

        try:
            # ===== Step 4: Validate download_dir =====
            if not download_dir or not str(download_dir).strip():
                msg = "Download directory not configured - use --dir or set download_dir in config"
                update_task(task_id, status="failed", error_message=msg)
                self._emit("error", {"task_id": task_id, "message": msg})
                self._emit("status_changed", {"task_id": task_id, "status": "failed"})
                return False

            # ===== Step 5: Build download preview =====
            _logger.info(f"Task {task_id}: building download preview for item {task.item_id}")
            from app.core.download_preview import build_download_preview
            preview = build_download_preview(
                item_id=task.item_id,
                server_url=self._config.server_url,
                token=token,
                download_dir=download_dir,
            )
            if preview.error_message:
                err_msg = preview.error_message
                update_task(task_id, status="failed", error_message=err_msg)
                self._emit("error", {"task_id": task_id, "message": err_msg})
                self._emit("status_changed", {"task_id": task_id, "status": "failed"})
                return False
            if not preview.can_download:
                err_msg = preview.reason or "Item is not downloadable"
                update_task(task_id, status="failed", error_message=err_msg)
                self._emit("error", {"task_id": task_id, "message": err_msg})
                self._emit("status_changed", {"task_id": task_id, "status": "failed"})
                return False

            # ===== Step 6: Fetch PlaybackInfo for media source selection =====
            _logger.info(f"Task {task_id}: fetching playback info")
            client = EmbyApiClient(self._config.server_url, token)
            try:
                user = client.get_user()
                user_id = user.get("Id", "")
            except Exception as e:
                msg = f"Failed to get user info: {e}"
                update_task(task_id, status="failed", error_message=msg)
                self._emit("error", {"task_id": task_id, "message": msg})
                self._emit("status_changed", {"task_id": task_id, "status": "failed"})
                return False

            try:
                playback_info = client.get_playback_info(task.item_id, user_id)
            except Exception as e:
                msg = f"Failed to get playback info: {e}"
                update_task(task_id, status="failed", error_message=msg)
                self._emit("error", {"task_id": task_id, "message": msg})
                self._emit("status_changed", {"task_id": task_id, "status": "failed"})
                return False

            sources = parse_media_sources(playback_info)
            if not sources:
                msg = "No media sources returned from server"
                update_task(task_id, status="failed", error_message=msg)
                self._emit("error", {"task_id": task_id, "message": msg})
                self._emit("status_changed", {"task_id": task_id, "status": "failed"})
                return False

            # ===== Step 7: Select media source =====
            _logger.info(f"Task {task_id}: media_source_id={task.media_source_id or '(auto)'}")
            if task.media_source_id:
                from app.core.playback_info import find_source_by_id
                best = find_source_by_id(sources, task.media_source_id)
                if best is None:
                    msg = (f"Selected version not available: media_source_id={task.media_source_id}. "
                           f"Available sources: {len(sources)}")
                    update_task(task_id, status="failed", error_message=msg)
                    self._emit("error", {"task_id": task_id, "message": msg})
                    self._emit("status_changed", {"task_id": task_id, "status": "failed"})
                    return False
            else:
                best = select_best_source(sources)
                if best is None:
                    msg = "No media sources available (auto-select returned none)"
                    update_task(task_id, status="failed", error_message=msg)
                    self._emit("error", {"task_id": task_id, "message": msg})
                    self._emit("status_changed", {"task_id": task_id, "status": "failed"})
                    return False

            # ===== Step 8: Check download capability =====
            _logger.info(f"Task {task_id}: checking download capability")
            cap = check_download_capability(client, task.item_id, best)
            if not cap.can_download:
                msg = cap.reason or "Download not allowed for this source"
                update_task(task_id, status="failed", error_message=msg)
                self._emit("error", {"task_id": task_id, "message": msg})
                self._emit("status_changed", {"task_id": task_id, "status": "failed"})
                return False

            download_url = cap.recommended_url
            download_method = cap.recommended_method
            file_size = cap.file_size or preview.size

            # ===== Step 9: Build save_path / temp_path =====
            dest_path = preview.output_path
            if not dest_path:
                msg = "Output path not generated - download_dir may be invalid"
                update_task(task_id, status="failed", error_message=msg)
                self._emit("error", {"task_id": task_id, "message": msg})
                self._emit("status_changed", {"task_id": task_id, "status": "failed"})
                return False

            temp_path = dest_path + ".part"
            _logger.info(f"Task {task_id}: save_path={dest_path}")

            # ===== Step 10: Persist prepare results =====
            method_str = str(download_method.value if hasattr(download_method, "value") else download_method)
            update_task(task_id, status="preparing",
                        download_url=download_url,
                        save_path=dest_path, temp_path=temp_path,
                        total_bytes=file_size,
                        title=preview.filename or preview.title,
                        media_source_id=best.id,
                        container=best.container or "",
                        download_method=method_str)
            client.close()

        except Exception as e:
            _logger.error(f"Prepare failed for task {task_id}: {e}")
            err_msg = f"Prepare failed: {e}"
            update_task(task_id, status="failed", error_message=err_msg)
            self._emit("error", {"task_id": task_id, "message": err_msg})
            self._emit("status_changed", {"task_id": task_id, "status": "failed"})
            return False

        # ===== Download phase =====
        task = get_task(task_id)
        update_task(task_id, status="downloading")
        self._emit("status_changed", {"task_id": task_id, "status": "downloading"})

        chunk_size = self._config.chunk_size_mb * 1024 * 1024
        retry_count = self._config.retry_count
        retry_delay = self._config.retry_delay_seconds
        timeout = self._config.timeout_seconds

        def prog_cb(downloaded, total, speed):
            self._emit("progress", {
                "task_id": task_id,
                "downloaded": downloaded,
                "total": total,
                "speed": speed,
            })

        def cancel_cb():
            cancel = self._cancel_flags.get(task_id, asyncio.Event())
            pause = self._pause_flags.get(task_id, asyncio.Event())
            return cancel.is_set() or pause.is_set()

        try:
            if download_method and hasattr(download_method, "value") and download_method.value == "stream":
                result = await download_stream(
                    url=download_url, dest_path=dest_path,
                    chunk_size=chunk_size, resume=False,
                    retry_count=retry_count, retry_delay=retry_delay,
                    timeout=timeout, progress_callback=prog_cb,
                    cancel_callback=cancel_cb,
                )
            else:
                result = await download_direct(
                    url=download_url, dest_path=dest_path,
                    chunk_size=chunk_size, resume=False,
                    retry_count=retry_count, retry_delay=retry_delay,
                    timeout=timeout, progress_callback=prog_cb,
                    cancel_callback=cancel_cb,
                )
        except Exception as e:
            _logger.error(f"Download failed for task {task_id}: {e}")
            update_task(task_id, status="failed", error_message=str(e),
                        downloaded_bytes=0)
            self._emit("error", {"task_id": task_id, "message": str(e)})
            self._emit("status_changed", {"task_id": task_id, "status": "failed"})
            return False

        # Handle result
        task = get_task(task_id)
        if task is None:
            return False

        if result.success:
            final_bytes = result.total_bytes if result.total_bytes else result.downloaded_bytes
            update_task(task_id, status="completed", downloaded_bytes=final_bytes)
            self._emit("status_changed", {"task_id": task_id, "status": "completed"})
            self._emit("finished", {"task_id": task_id, "output_path": result.file_path})
            return True
        elif result.status == DownloadStatus.PAUSED:
            update_task(task_id, status="paused", error_message=result.error_message,
                        downloaded_bytes=result.downloaded_bytes)
            self._emit("status_changed", {"task_id": task_id, "status": "paused"})
            return False
        else:
            update_task(task_id, status="failed", error_message=result.error_message or "Download failed",
                        downloaded_bytes=result.downloaded_bytes)
            self._emit("error", {"task_id": task_id, "message": result.error_message or "Download failed"})
            self._emit("status_changed", {"task_id": task_id, "status": "failed"})
            return False

    async def _resume_task(self, task_id: str, download_dir: str):
        """Resume a paused task."""
        await self.start_task(task_id, download_dir)

    async def shutdown(self):
        """Cancel all active tasks and clean up."""
        for tid in list(self._active_tasks.keys()):
            self.cancel_task(tid)
        for tid, t in self._active_tasks.items():
            t.cancel()
        # Give tasks a moment to clean up
        await asyncio.sleep(0.5)


def _task_to_dict(task: DownloadTask) -> dict:
    return {
        "task_id": task.task_id,
        "item_id": task.item_id,
        "title": task.title,
        "download_url": task.download_url,
        "save_path": task.save_path,
        "temp_path": task.temp_path,
        "total_bytes": task.total_bytes,
        "downloaded_bytes": task.downloaded_bytes,
        "status": task.status,
        "error_message": task.error_message,
        "media_source_id": task.media_source_id,
        "container": task.container,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "media_type": task.media_type,
        "series_id": task.series_id,
        "season_id": task.season_id,
        "episode_id": task.episode_id,
        "season_number": task.season_number,
        "episode_number": task.episode_number,
        "parent_title": task.parent_title,
        "display_title": task.display_title,
        "download_method": task.download_method,
    }
