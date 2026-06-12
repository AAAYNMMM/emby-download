"""
GUI worker threads for non-blocking operations.

Each worker is a QObject that can be moved to a QThread.
Signals: finished(object), error(str)
"""

import sys
from typing import Optional, Callable
import asyncio as _asyncio

from PySide6.QtCore import QObject, Signal

from app.core.auth import login as auth_login, get_token
from app.core.emby_api import EmbyApiClient, EmbyAuthError
from app.config.settings import load_config, save_config
from app.downloader.task_store import (
    list_tasks as db_list_tasks,
    count_tasks,
    create_task,
    update_task,
    get_task,
)


class LoginWorker(QObject):
    """Login to Emby server in background thread."""
    finished = Signal(object)
    error = Signal(str)

    def __init__(self):
        super().__init__()

    def run(self, server_url: str, username: str, password: str, config_path: Optional[str] = None):
        try:
            config, user_id = auth_login(
                server_url=server_url,
                username=username,
                password=password,
                storage_method="file",
            )
            existing = load_config(config_path)
            existing.server_url = config.server_url
            existing.username = config.username
            existing.token_encrypted = config.token_encrypted
            existing.token_storage = config.token_storage
            save_config(existing, config_path)
            self.finished.emit({"username": username, "user_id": user_id, "server_url": server_url})
        except EmbyAuthError as e:
            self.error.emit(f"Authentication failed: {e}")
        except ConnectionError as e:
            self.error.emit(f"Connection failed: {e}")
        except Exception as e:
            self.error.emit(f"Login failed: {e}")


class PingWorker(QObject):
    """Check if Emby server is reachable."""
    finished = Signal(object)
    error = Signal(str)

    def run(self, server_url: str):
        import requests
        server_url = server_url.rstrip("/")
        try:
            r = requests.get(f"{server_url}/System/Info", timeout=10)
            if r.status_code == 200:
                data = r.json()
                self.finished.emit({
                    "server_name": data.get("ServerName", "?"),
                    "version": data.get("Version", "?"),
                })
            elif r.status_code == 401:
                self.finished.emit({"server_name": "(auth required)", "version": ""})
            else:
                self.error.emit(f"Server returned HTTP {r.status_code}")
        except requests.exceptions.ConnectionError as e:
            error_str = str(e).lower()
            if "refused" in error_str:
                self.error.emit(f"Connection refused. Is the server running?")
            else:
                self.error.emit(f"Cannot connect to {server_url}")
        except requests.exceptions.Timeout:
            self.error.emit(f"Timeout connecting to {server_url}")
        except Exception as e:
            error_text = str(e).strip() or repr(e) or type(e).__name__
            self.error.emit(error_text)


class WhoamiWorker(QObject):
    """Check authentication status."""
    finished = Signal(object)
    error = Signal(str)

    def run(self, server_url: str, token: str):
        try:
            client = EmbyApiClient(server_url, token)
            user = client.get_user()
            policy = user.get("Policy", {})
            self.finished.emit({
                "username": user.get("Name", "?"),
                "user_id": user.get("Id", "?"),
                "download_enabled": policy.get("EnableDownload", "?"),
                "media_conversion_enabled": policy.get("EnableMediaConversion", "?"),
            })
        except EmbyAuthError as e:
            if "401" in str(e):
                self.error.emit("Token invalid or expired. Please login again.")
            elif "403" in str(e):
                self.error.emit("Token valid but account lacks permissions.")
            else:
                self.error.emit(str(e))
        except Exception as e:
            self.error.emit(str(e))


class SearchWorker(QObject):
    """Search for media items in background."""
    finished = Signal(object)
    error = Signal(str)

    def run(
        self,
        server_url: str,
        token: str,
        query: str,
        limit: int = 20,
        library_id: Optional[str] = None,
        include_types: Optional[list[str]] = None,
    ):
        try:
            client = EmbyApiClient(server_url, token)
            try:
                user = client.get_user()
                user_id = user.get("Id", "")
            except Exception as e:
                self.error.emit(f"Failed to get user info: {e}")
                return

            items = client.search_items(
                user_id=user_id,
                query=query,
                parent_id=library_id,
                limit=limit,
                include_types=include_types,
            )
            self.finished.emit(items)
        except EmbyAuthError:
            self.error.emit("Token invalid or expired. Please login again.")
        except Exception as e:
            self.error.emit(str(e))


class DryRunWorker(QObject):
    """Preview download without actual download."""
    finished = Signal(object)
    error = Signal(str)

    def run(self, item_id: str, server_url: str, token: str, download_dir: str, method: str = "auto"):
        try:
            from app.core.download_preview import build_download_preview
            result = build_download_preview(
                item_id=item_id,
                server_url=server_url,
                token=token,
                download_dir=download_dir,
                method=method,
            )
            if result.error_message:
                self.error.emit(result.error_message)
            else:
                self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))



class MediaSourcesWorker(QObject):
    """Fetch PlaybackInfo and return media source options for selection.

    Runs in a background thread (never accesses QWidget).
    """

    finished = Signal(object)  # list[dict] of source options
    error = Signal(str)

    def __init__(self):
        super().__init__()

    def run(self, item_id: str, server_url: str, token: str):
        try:
            from app.core.emby_api import EmbyApiClient
            from app.core.playback_info import parse_media_sources, build_media_source_options

            client = EmbyApiClient(server_url, token)
            try:
                user = client.get_user()
                user_id = user.get("Id", "")
            except Exception as e:
                self.error.emit(f"Failed to get user info: {e}")
                client.close()
                return

            try:
                playback_info = client.get_playback_info(item_id, user_id)
            except Exception as e:
                self.error.emit(f"Failed to get PlaybackInfo: {e}")
                client.close()
                return

            client.close()

            sources = parse_media_sources(playback_info)
            options = build_media_source_options(sources)
            self.finished.emit(options)

        except Exception as e:
            self.error.emit(str(e))

class TaskListWorker(QObject):
    """Fetch download tasks in background."""
    finished = Signal(object)
    error = Signal(str)

    def run(self, status_filter: Optional[str] = None, limit: int = 200):
        try:
            tasks = db_list_tasks(status_filter=status_filter, limit=limit)
            total = count_tasks(status_filter=status_filter)
            counts = {}
            for s in ("pending", "preparing", "downloading", "paused", "completed", "failed", "cancelled"):
                counts[s] = count_tasks(status_filter=s)
            self.finished.emit({"tasks": tasks, "total": total, "counts": counts})
        except Exception as e:
            self.error.emit(str(e))


    def __init__(self):
        super().__init__()
        self._pause_requested = False
        self._current_worker = None
        super().__init__()
        self._pause_requested = False

        self._item_id: str = ""
        self._server_url: str = ""
        self._token: str = ""
        self._download_dir: str = ""
        self._chunk_size: int = 8388608
        self._retry_count: int = 3
        self._retry_delay: int = 5
        self._timeout: int = 30
        self._resume: bool = False
        self._task_id: str = ""
        self._current_worker = None

    def request_pause(self):
        self._pause_requested = True
        if self._current_worker is not None:
            self._current_worker.request_pause()

    def run(self, url: str, dest_path: str, chunk_size: int = 8*1024*1024,
            retry_count: int = 3, retry_delay: int = 5, timeout: int = 30):
        import asyncio
        from app.downloader.direct_download import download_direct
        from app.downloader.stream_download import download_stream
        from app.downloader.base import DownloadStatus

        self._pause_requested = False
        use_stream = "/stream?" in url  # heuristic: stream URLs contain /stream?

        progress_callback = None

        def prog(downloaded, total, speed):
            self.progress.emit(downloaded, total, speed)

        progress_callback = prog

        async def run():
            if use_stream:
                return await download_stream(
                    url=url, dest_path=dest_path,
                    chunk_size=chunk_size,
                    resume=False,
                    retry_count=retry_count,
                    retry_delay=retry_delay,
                    timeout=timeout,
                    progress_callback=progress_callback,
                    cancel_callback=lambda: self._pause_requested,
                )
            else:
                return await download_direct(
                    url=url, dest_path=dest_path,
                    chunk_size=chunk_size,
                    resume=False,
                    retry_count=retry_count,
                    retry_delay=retry_delay,
                    timeout=timeout,
                    progress_callback=progress_callback,
                    cancel_callback=lambda: self._pause_requested,
                )

        try:
            result = asyncio.run(run())
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class DownloadItemWorker(QObject):
    """Prepare and download one item entirely in a worker thread."""

    prepared = Signal(object)
    download_started = Signal(object)
    progress = Signal(object, object, float)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self._pause_requested = False

    def request_pause(self):
        self._pause_requested = True

    def run(self):
        import asyncio
        from app.core.download_preview import build_download_preview
        from app.core.emby_api import EmbyApiClient
        from app.core.playback_info import parse_media_sources, select_best_source, find_source_by_id
        from app.core.download_capability import check_download_capability, DownloadMethod
        from app.downloader.direct_download import download_direct
        from app.downloader.stream_download import download_stream
        from app.downloader.base import DownloadStatus
        from app.utils.timing import timed_step, timing_event

        self._pause_requested = False

        item_id = self._item_id
        server_url = self._server_url
        token = self._token
        download_dir = self._download_dir
        chunk_size = self._chunk_size
        retry_count = self._retry_count
        retry_delay = self._retry_delay
        timeout = self._timeout
        resume = self._resume
        task_id = self._task_id
        media_source_id = self._media_source_id

        timing_event("worker run entered", item_id=item_id, task_id=task_id)

        try:
            with timed_step("build_download_preview", item_id=item_id, task_id=task_id):
                preview = build_download_preview(
                    item_id=item_id,
                    server_url=server_url,
                    token=token,
                    download_dir=download_dir,
                )
            if preview.error_message or not preview.can_download:
                self.error.emit(preview.error_message or "Item is not downloadable.")
                return

            client = EmbyApiClient(server_url, token)
            try:
                user = client.get_user()
                user_id = user.get("Id", "")
                with timed_step("PlaybackInfo", item_id=item_id, task_id=task_id):
                    playback_info = client.get_playback_info(item_id, user_id)
                sources = parse_media_sources(playback_info)
                with timed_step("MediaSource selected", item_id=item_id, task_id=task_id):
                    if media_source_id:
                        chosen = find_source_by_id(sources, media_source_id)
                        if not chosen:
                            self.error.emit(f"specified MediaSource {media_source_id[:12]}... not found, please re-select.")
                            return
                    else:
                        chosen = select_best_source(sources)
                if not chosen:
                    self.error.emit("No media sources found for this item.")
                    return
                timing_event("MediaSource selected", item_id=item_id, task_id=task_id, media_source_id=chosen.id)
                with timed_step("HEAD", item_id=item_id, task_id=task_id, media_source_id=chosen.id):
                    cap = check_download_capability(client, item_id, chosen)
                if not cap.can_download:
                    self.error.emit(cap.reason)
                    return
                download_url = cap.recommended_url
                download_method = cap.recommended_method
                file_size = cap.file_size or preview.size
            finally:
                client.close()

            dest_path = preview.output_path
            temp_path = dest_path + ".part"
            task = get_task(task_id) if task_id else None
            if task is None:
                task = create_task(
                    item_id=item_id,
                    title=preview.filename or preview.title,
                    download_url=download_url,
                    save_path=dest_path,
                    temp_path=temp_path,
                    total_bytes=file_size,
                )
            else:
                update_task(
                    task.task_id,
                    status="preparing",
                    temp_path=temp_path,
                    save_path=dest_path,
                    title=preview.filename or preview.title,
                    total_bytes=file_size,
                    download_method=str(download_method.value if hasattr(download_method, "value") else download_method),
                )

            update_task(task.task_id, status="preparing")
            self.prepared.emit({
                "task_id": task.task_id,
                "title": preview.title,
                "filename": preview.filename,
                "dest_path": dest_path,
                "total_bytes": file_size,
            })

            def prog(downloaded, total, speed):
                self.progress.emit(downloaded, total, speed)

            async def run_download():
                kwargs = dict(
                    url=download_url,
                    dest_path=dest_path,
                    chunk_size=chunk_size,
                    resume=resume,
                    retry_count=retry_count,
                    retry_delay=retry_delay,
                    timeout=timeout,
                    progress_callback=prog,
                    cancel_callback=lambda: self._pause_requested,
                )
                if download_method == DownloadMethod.STREAM:
                    return await download_stream(**kwargs)
                return await download_direct(**kwargs)

            update_task(task.task_id, status="downloading")
            timing_event("GET started", item_id=item_id, task_id=task.task_id)
            self.download_started.emit({
                "task_id": task.task_id,
                "dest_path": dest_path,
                "download_method": str(download_method.value if hasattr(download_method, "value") else download_method),
            })
            result = asyncio.run(run_download())
            if result.success:
                update_task(task.task_id, status="completed", downloaded_bytes=result.total_bytes)
            elif result.status == DownloadStatus.PAUSED:
                update_task(
                    task.task_id,
                    status="paused",
                    error_message=result.error_message,
                    downloaded_bytes=result.downloaded_bytes,
                )
            else:
                update_task(
                    task.task_id,
                    status="failed",
                    error_message=result.error_message,
                    downloaded_bytes=result.downloaded_bytes,
                )

            self.finished.emit({
                "task_id": task.task_id,
                "result": result,
                "dest_path": dest_path,
                "title": preview.title,
            })
        except Exception as e:
            self.error.emit(str(e))


class SeriesSeasonsWorker(QObject):
    """Fetch seasons for a Series in a background thread."""
    finished = Signal(object)  # dict: {series_id, series_name, seasons: list[dict]}
    error = Signal(str)

    def __init__(self):
        super().__init__()

    def run(self, server_url: str, token: str, series_id: str, series_name: str = ""):
        try:
            from app.core.emby_api import EmbyApiClient, EmbyAuthError
            from app.core.series import normalize_season_item, sort_seasons

            client = EmbyApiClient(server_url, token)
            try:
                user = client.get_user()
                user_id = user.get("Id", "")
            except Exception as e:
                self.error.emit(f"Failed to get user info: {e}")
                return

            try:
                raw_seasons = client.get_series_seasons(series_id, user_id)
            except EmbyAuthError:
                self.error.emit("Token invalid or expired. Please login again.")
                return
            except Exception as e:
                self.error.emit(str(e))
                return
            finally:
                client.close()

            seasons = [normalize_season_item(s) for s in raw_seasons]
            seasons = sort_seasons(seasons)

            self.finished.emit({
                "series_id": series_id,
                "series_name": series_name,
                "seasons": seasons,
            })
        except Exception as e:
            self.error.emit(str(e))


class SeasonEpisodesWorker(QObject):
    """Fetch episodes for a Season in a background thread."""
    finished = Signal(object)  # dict: {season_id, episodes: list[dict]}
    error = Signal(str)

    def __init__(self):
        super().__init__()

    def run(self, server_url: str, token: str, series_id: str, season_id: str):
        try:
            from app.core.emby_api import EmbyApiClient, EmbyAuthError
            from app.core.series import normalize_episode_item, sort_episodes

            client = EmbyApiClient(server_url, token)
            try:
                user = client.get_user()
                user_id = user.get("Id", "")
            except Exception as e:
                self.error.emit(f"Failed to get user info: {e}")
                return

            try:
                raw_episodes = client.get_season_episodes(season_id, user_id, series_id=series_id)
            except EmbyAuthError:
                self.error.emit("Token invalid or expired. Please login again.")
                return
            except Exception as e:
                self.error.emit(str(e))
                return
            finally:
                client.close()

            episodes = [normalize_episode_item(e) for e in raw_episodes]
            episodes = sort_episodes(episodes)

            self.finished.emit({
                "season_id": season_id,
                "episodes": episodes,
            })
        except Exception as e:
            self.error.emit(str(e))


class SeriesSearchWorker(QObject):
    """Search for Series items only, in a background thread.

    Used by the Series Browser tab to find series without leaving
    the tab.  Filters search results to Type == Series.
    Never accesses QWidget.
    """

    finished = Signal(object)  # list[dict] of Series items
    error = Signal(str)

    def __init__(self):
        super().__init__()

    def run(
        self,
        server_url: str,
        token: str,
        query: str,
        limit: int = 20,
    ):
        try:
            from app.core.emby_api import EmbyApiClient, EmbyAuthError

            client = EmbyApiClient(server_url, token)
            try:
                user = client.get_user()
                user_id = user.get("Id", "")
                # Search with all types, then filter to Series
                items = client.search_items(
                    user_id=user_id,
                    query=query,
                    limit=max(limit * 3, 60),  # fetch more since we filter
                    include_types=["Series"],
                )
            except EmbyAuthError:
                self.error.emit("Token无效或已过期。请重新登录。")
                return
            except Exception as e:
                self.error.emit(str(e))
                return
            finally:
                client.close()

            self.finished.emit(items)

        except Exception as e:
            self.error.emit(str(e))


class BatchDownloadWorker(QObject):
    """Download multiple items sequentially without blocking the GUI."""

    item_started = Signal(object)
    item_finished = Signal(object)
    progress = Signal(int, int, float)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self._pause_requested = False

    def request_pause(self):
        self._pause_requested = True

    def run(self, item_ids: list[str], server_url: str, token: str, download_dir: str, config):
        completed = 0
        failed = 0
        paused = False
        for item_id in item_ids:
            if self._pause_requested:
                paused = True
                break

            worker = DownloadItemWorker()
            self._current_worker = worker
            worker.prepared.connect(self.item_started.emit)
            worker.progress.connect(self.progress.emit)
            result_box = {"done": None, "error": None}
            worker.finished.connect(lambda data, box=result_box: box.__setitem__("done", data))
            worker.error.connect(lambda msg, box=result_box: box.__setitem__("error", msg))
            worker.run(
                item_id=item_id,
                server_url=server_url,
                token=token,
                download_dir=download_dir,
                chunk_size=config.chunk_size_mb * 1024 * 1024,
                retry_count=config.retry_count,
                retry_delay=config.retry_delay_seconds,
                timeout=config.timeout_seconds,
                resume=True,
            )

            if result_box["error"]:
                failed += 1
                self.item_finished.emit({"item_id": item_id, "success": False, "error": result_box["error"]})
            else:
                data = result_box["done"]
                result = data["result"]
                if result.success:
                    completed += 1
                elif result.status.value == "paused":
                    paused = True
                else:
                    failed += 1
                self.item_finished.emit(data)

            if paused:
                break

        self._current_worker = None
        self.finished.emit({"completed": completed, "failed": failed, "paused": paused})


class StartTasksWorker(QObject):
    """Check pending tasks in a background thread (DB reads never block GUI).
    Emits 'ready' for each valid pending task; caller starts download on main thread.
    """

    ready = Signal(str, str)       # task_id, item_id
    log_msg = Signal(str, str)     # level, message
    finished = Signal(int)         # total ready count
    error = Signal(str)

    def __init__(self):
        super().__init__()

    def run(self, task_ids: list[str]):
        """Read task status in background thread. Emit 'ready' for each pending task."""
        from app.downloader.task_store import get_task

        count = 0
        for task_id in task_ids:
            t = get_task(task_id)
            if t is None:
                self.log_msg.emit("WARNING", f"Task {task_id} not found.")
                continue
            if t.status != "pending":
                self.log_msg.emit("INFO", f"Task {task_id} is {t.status}, skipped.")
                continue
            self.ready.emit(task_id, t.item_id)
            count += 1

        self.finished.emit(count)



class AsyncBackendWorker(QObject):
    """(Deprecated) Run async backend API calls in a background QThread.

    Deprecated: No longer used by MainWindow.
    Use DownloadController directly instead.
    """


    finished = Signal(object)  # result dict or None
    error = Signal(str)

    def __init__(self):
        super().__init__()

    def run_async(self, coro_fn: Callable, *args, **kwargs):
        """Execute an async callable in a background event loop."""
        try:
            loop = _asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(coro_fn(*args, **kwargs))
                self.finished.emit(result)
            finally:
                loop.close()
        except Exception as e:
            self.error.emit(str(e))