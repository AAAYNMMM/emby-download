# Stage 11: REST API route handlers for the backend server.

import json
from aiohttp import web

from app.backend.download_manager import BackendDownloadManager
from app.downloader.task_store import (
    get_task, update_task, list_tasks, count_tasks, delete_task,
)
from app.utils.logger import get_logger

_logger = get_logger()


def setup_routes(app: web.Application, manager: BackendDownloadManager):
    app.router.add_get("/api/health", health_handler)
    app.router.add_get("/api/tasks", lambda r: list_tasks_handler(r, manager))
    app.router.add_post("/api/tasks", lambda r: create_task_handler(r, manager))
    app.router.add_get("/api/tasks/{task_id}", lambda r: get_task_handler(r, manager))
    app.router.add_post("/api/tasks/{task_id}/start", lambda r: start_task_handler(r, manager))
    app.router.add_post("/api/tasks/batch-start", lambda r: batch_start_handler(r, manager))
    app.router.add_post("/api/tasks/{task_id}/pause", lambda r: pause_task_handler(r, manager))
    app.router.add_post("/api/tasks/{task_id}/resume", lambda r: resume_task_handler(r, manager))
    app.router.add_post("/api/tasks/{task_id}/cancel", lambda r: cancel_task_handler(r, manager))
    app.router.add_delete("/api/tasks/{task_id}", lambda r: delete_task_handler(r, manager))
    app.router.add_get("/api/tasks/stats", lambda r: stats_handler(r, manager))
    app.router.add_get("/api/config", lambda r: config_handler(r, manager))


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def list_tasks_handler(request: web.Request, manager: BackendDownloadManager) -> web.Response:
    status_filter = request.query.get("status")
    limit = int(request.query.get("limit", "200"))
    tasks = await manager.list_tasks_api(status_filter=status_filter, limit=limit)
    return web.json_response(tasks)


async def create_task_handler(request: web.Request, manager: BackendDownloadManager) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    item_id = data.get("item_id", "").strip()
    if not item_id:
        return web.json_response({"error": "item_id required"}, status=400)

    task = await manager.create_pending_task(
        item_id=item_id,
        download_dir=data.get("download_dir", ""),
        media_type=data.get("media_type", ""),
        series_id=data.get("series_id", ""),
        season_id=data.get("season_id", ""),
        episode_id=data.get("episode_id", ""),
        season_number=data.get("season_number"),
        episode_number=data.get("episode_number"),
        parent_title=data.get("parent_title", ""),
        display_title=data.get("display_title", ""),
        download_method=data.get("download_method", ""),
        media_source_id=data.get("media_source_id", ""),
    )
    if task is None:
        return web.json_response({"error": "Task already exists or failed to create"}, status=409)
    return web.json_response(task, status=201)


async def get_task_handler(request: web.Request, manager: BackendDownloadManager) -> web.Response:
    task_id = request.match_info["task_id"]
    task = get_task(task_id)
    if task is None:
        return web.json_response({"error": "Task not found"}, status=404)
    return web.json_response({
        "task_id": task.task_id, "item_id": task.item_id,
        "title": task.title, "status": task.status,
        "total_bytes": task.total_bytes, "downloaded_bytes": task.downloaded_bytes,
        "save_path": task.save_path, "error_message": task.error_message,
        "media_type": task.media_type, "display_title": task.display_title,
        "created_at": task.created_at, "updated_at": task.updated_at,
    })


async def start_task_handler(request: web.Request, manager: BackendDownloadManager) -> web.Response:
    task_id = request.match_info["task_id"]
    try:
        data = await request.json()
    except Exception:
        data = {}
    download_dir = data.get("download_dir", "")
    if not download_dir:
        return web.json_response({"error": "download_dir required"}, status=400)

    ok = await manager.start_task(task_id, download_dir)
    if not ok:
        return web.json_response({"error": "Failed to start task"}, status=400)
    return web.json_response({"status": "ok"})


async def batch_start_handler(request: web.Request, manager: BackendDownloadManager) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    task_ids = data.get("task_ids", [])
    download_dir = data.get("download_dir", "")
    if not task_ids or not download_dir:
        return web.json_response({"error": "task_ids and download_dir required"}, status=400)

    count = await manager.start_multiple(task_ids, download_dir)
    return web.json_response({"started": count})


async def pause_task_handler(request: web.Request, manager: BackendDownloadManager) -> web.Response:
    task_id = request.match_info["task_id"]
    ok = manager.pause_task(task_id)
    if not ok:
        return web.json_response({"error": "Task not found or not running"}, status=400)
    return web.json_response({"status": "ok"})


async def resume_task_handler(request: web.Request, manager: BackendDownloadManager) -> web.Response:
    task_id = request.match_info["task_id"]
    try:
        data = await request.json()
    except Exception:
        data = {}
    download_dir = data.get("download_dir", "")
    if not download_dir:
        return web.json_response({"error": "download_dir required"}, status=400)

    ok = manager.resume_task(task_id, download_dir)
    if not ok:
        return web.json_response({"error": "Task not found or not paused"}, status=400)
    return web.json_response({"status": "ok"})


async def cancel_task_handler(request: web.Request, manager: BackendDownloadManager) -> web.Response:
    task_id = request.match_info["task_id"]
    ok = manager.cancel_task(task_id)
    if not ok:
        return web.json_response({"error": "Task not found"}, status=400)
    return web.json_response({"status": "ok"})


async def delete_task_handler(request: web.Request, manager: BackendDownloadManager) -> web.Response:
    task_id = request.match_info["task_id"]
    ok = manager.delete_task(task_id)
    if not ok:
        return web.json_response({"error": "Task not found"}, status=404)
    return web.json_response({"status": "ok"})


async def stats_handler(request: web.Request, manager: BackendDownloadManager) -> web.Response:
    stats = {}
    for s in ("pending", "preparing", "downloading", "paused", "completed", "failed", "cancelled"):
        stats[s] = count_tasks(status_filter=s)
    return web.json_response(stats)


async def config_handler(request: web.Request, manager: BackendDownloadManager) -> web.Response:
    return web.json_response({
        "server_url": manager._config.server_url,
        "username": manager._config.username,
        "download_dir": manager._config.download_dir,
        "max_concurrent": manager._config.max_concurrent_downloads,
    })
