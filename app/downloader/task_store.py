"""
Download task storage using SQLite.

Persists download task records with status, progress, and error info.
"""

import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.config.settings import get_app_dir


@dataclass
class DownloadTask:
    """Represents a single download task in the store."""

    task_id: str = ""
    item_id: str = ""
    title: str = ""
    download_url: str = ""
    save_path: str = ""
    temp_path: str = ""
    total_bytes: int = 0
    downloaded_bytes: int = 0
    status: str = "pending"  # pending | preparing | downloading | completed | failed | paused | cancelled
    error_message: str = ""
    media_source_id: str = ""
    container: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    # --- Episode / series metadata (Stage 10D-4) ---
    media_type: str = ""         # "Movie", "Episode", etc.
    series_id: str = ""
    season_id: str = ""
    episode_id: str = ""
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    parent_title: str = ""       # series name for episodes
    display_title: str = ""      # formatted display title
    download_method: str = ""    # "direct" or "stream"


_DB_PATH = get_app_dir() / "tasks.db"


def _get_connection() -> sqlite3.Connection:
    """Get a connection to the task database."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_task_db_path() -> Path:
    """Return the task database path."""
    return _DB_PATH


def _init_db():
    """Initialize the database schema and migrate if needed."""
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                download_url TEXT NOT NULL DEFAULT '',
                save_path TEXT NOT NULL DEFAULT '',
                temp_path TEXT NOT NULL DEFAULT '',
                total_bytes INTEGER NOT NULL DEFAULT 0,
                downloaded_bytes INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT NOT NULL DEFAULT '',
                media_source_id TEXT NOT NULL DEFAULT '',
                container TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL DEFAULT 0,
                media_type TEXT NOT NULL DEFAULT '',
                series_id TEXT NOT NULL DEFAULT '',
                season_id TEXT NOT NULL DEFAULT '',
                episode_id TEXT NOT NULL DEFAULT '',
                season_number INTEGER DEFAULT NULL,
                episode_number INTEGER DEFAULT NULL,
                parent_title TEXT NOT NULL DEFAULT '',
                display_title TEXT NOT NULL DEFAULT '',
                download_method TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_item_id ON tasks(item_id)
        """)

        # ---- Stage 10D-4 migration: add missing columns for old task DBs ----
        existing = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        _stage10d4_columns = {
            "media_type":      "TEXT NOT NULL DEFAULT ''",
            "series_id":       "TEXT NOT NULL DEFAULT ''",
            "season_id":       "TEXT NOT NULL DEFAULT ''",
            "episode_id":      "TEXT NOT NULL DEFAULT ''",
            "season_number":   "INTEGER DEFAULT NULL",
            "episode_number":  "INTEGER DEFAULT NULL",
            "parent_title":    "TEXT NOT NULL DEFAULT ''",
            "display_title":   "TEXT NOT NULL DEFAULT ''",
            "download_method": "TEXT NOT NULL DEFAULT ''",
        }
        for col_name, col_def in _stage10d4_columns.items():
            if col_name not in existing:
                conn.execute(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_def}")

        conn.commit()
    finally:
        conn.close()


def create_task(
    item_id: str,
    title: str = "",
    download_url: str = "",
    save_path: str = "",
    temp_path: str = "",
    total_bytes: int = 0,
    media_source_id: str = "",
    container: str = "",
    media_type: str = "",
    series_id: str = "",
    season_id: str = "",
    episode_id: str = "",
    season_number: Optional[int] = None,
    episode_number: Optional[int] = None,
    parent_title: str = "",
    display_title: str = "",
    download_method: str = "",
) -> DownloadTask:
    """
    Create a new download task in the database.

    Args:
        item_id: Emby item ID.
        title: Movie / episode title.
        download_url: Full download URL.
        save_path: Final file path.
        temp_path: Temporary .part file path.
        total_bytes: Total file size.
        media_source_id: MediaSource ID.
        container: File container.
        media_type: "Movie" or "Episode" etc.
        series_id: Series (Show) ID for episodes.
        season_id: Season ID for episodes.
        episode_id: Episode ID.
        season_number: Season number.
        episode_number: Episode number within season.
        parent_title: Series name for episodes.
        display_title: Formatted display title.
        download_method: "direct" or "stream".

    Returns:
        Created DownloadTask.
    """
    _init_db()

    task = DownloadTask(
        task_id=str(uuid.uuid4())[:8],
        item_id=item_id,
        title=title,
        download_url=download_url,
        save_path=save_path,
        temp_path=temp_path,
        total_bytes=total_bytes,
        media_source_id=media_source_id,
        container=container,
        status="pending",
        created_at=time.time(),
        updated_at=time.time(),
        media_type=media_type,
        series_id=series_id,
        season_id=season_id,
        episode_id=episode_id,
        season_number=season_number,
        episode_number=episode_number,
        parent_title=parent_title,
        display_title=display_title,
        download_method=download_method,
    )

    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO tasks (task_id, item_id, title, download_url, save_path,
                               temp_path, total_bytes, downloaded_bytes, status,
                               error_message, media_source_id, container,
                               created_at, updated_at,
                               media_type, series_id, season_id, episode_id,
                               season_number, episode_number, parent_title,
                               display_title, download_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.task_id, task.item_id, task.title, task.download_url,
                task.save_path, task.temp_path, task.total_bytes,
                task.downloaded_bytes, task.status, task.error_message,
                task.media_source_id, task.container,
                task.created_at, task.updated_at,
                task.media_type, task.series_id, task.season_id, task.episode_id,
                task.season_number, task.episode_number, task.parent_title,
                task.display_title, task.download_method,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return task


def update_task(
    task_id: str,
    downloaded_bytes: Optional[int] = None,
    total_bytes: Optional[int] = None,
    status: Optional[str] = None,
    error_message: Optional[str] = None,
    temp_path: Optional[str] = None,
    save_path: Optional[str] = None,
    title: Optional[str] = None,
    media_type: Optional[str] = None,
    series_id: Optional[str] = None,
    season_id: Optional[str] = None,
    episode_id: Optional[str] = None,
    season_number: Optional[int] = None,
    episode_number: Optional[int] = None,
    parent_title: Optional[str] = None,
    display_title: Optional[str] = None,
    download_method: Optional[str] = None,
) -> Optional[DownloadTask]:
    """
    Update an existing task's progress or status.

    Args:
        task_id: Task ID to update.
        downloaded_bytes: New downloaded byte count.
        total_bytes: New total byte count (updated when size becomes known).
        status: New status.
        error_message: New error message.
        temp_path: Updated temp path.
        save_path: Updated save path.
        title: Updated title.
        media_type: "Movie" or "Episode".
        series_id: Series (Show) ID.
        season_id: Season ID.
        episode_id: Episode ID.
        season_number: Season number.
        episode_number: Episode number.
        parent_title: Series name.
        display_title: Formatted display title.
        download_method: "direct" or "stream".

    Returns:
        Updated task, or None if not found.
    """
    _init_db()
    conn = _get_connection()
    try:
        task = get_task(task_id)
        if not task:
            return None

        updates = []
        values = []

        if downloaded_bytes is not None:
            updates.append("downloaded_bytes = ?")
            values.append(downloaded_bytes)
        if total_bytes is not None:
            updates.append("total_bytes = ?")
            values.append(total_bytes)
        if status is not None:
            updates.append("status = ?")
            values.append(status)
        if error_message is not None:
            updates.append("error_message = ?")
            values.append(error_message)
        if temp_path is not None:
            updates.append("temp_path = ?")
            values.append(temp_path)
        if save_path is not None:
            updates.append("save_path = ?")
            values.append(save_path)
        if title is not None:
            updates.append("title = ?")
            values.append(title)
        if media_type is not None:
            updates.append("media_type = ?")
            values.append(media_type)
        if series_id is not None:
            updates.append("series_id = ?")
            values.append(series_id)
        if season_id is not None:
            updates.append("season_id = ?")
            values.append(season_id)
        if episode_id is not None:
            updates.append("episode_id = ?")
            values.append(episode_id)
        if season_number is not None:
            updates.append("season_number = ?")
            values.append(season_number)
        if episode_number is not None:
            updates.append("episode_number = ?")
            values.append(episode_number)
        if parent_title is not None:
            updates.append("parent_title = ?")
            values.append(parent_title)
        if display_title is not None:
            updates.append("display_title = ?")
            values.append(display_title)
        if download_method is not None:
            updates.append("download_method = ?")
            values.append(download_method)

        if not updates:
            return task

        updates.append("updated_at = ?")
        values.append(time.time())
        values.append(task_id)

        conn.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = ?",
            values,
        )
        conn.commit()

        return get_task(task_id)
    finally:
        conn.close()


def get_task(task_id: str) -> Optional[DownloadTask]:
    """Get a task by its ID."""
    _init_db()
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row:
            return _row_to_task(row)
        return None
    finally:
        conn.close()


def get_task_by_item(item_id: str, status: Optional[str] = None) -> Optional[DownloadTask]:
    """Get the most recent task for an item, optionally filtered by status."""
    _init_db()
    conn = _get_connection()
    try:
        if status:
            row = conn.execute(
                "SELECT * FROM tasks WHERE item_id = ? AND status = ? ORDER BY created_at DESC LIMIT 1",
                (item_id, status),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM tasks WHERE item_id = ? ORDER BY created_at DESC LIMIT 1",
                (item_id,),
            ).fetchone()
        if row:
            return _row_to_task(row)
        return None
    finally:
        conn.close()


def list_tasks(
    status_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> list[DownloadTask]:
    """List tasks, optionally filtered by status."""
    _init_db()
    conn = _get_connection()
    try:
        if status_filter:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (status_filter, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_row_to_task(row) for row in rows]
    finally:
        conn.close()


def find_tasks_by_item_id(item_id: str) -> list[DownloadTask]:
    """Find all non-cancelled, non-failed tasks for a given item_id.

    Used to detect duplicate downloads for episodes/movies.
    Returns tasks in status: pending, preparing, downloading, paused, completed.
    Failed and cancelled tasks are excluded (they can be re-created).
    """
    _init_db()
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE item_id = ? AND status IN ('pending','preparing','downloading','paused','completed') "
            "ORDER BY created_at DESC",
            (item_id,),
        ).fetchall()
        return [_row_to_task(row) for row in rows]
    finally:
        conn.close()


def task_exists(item_id: str, status: str = "completed") -> bool:
    """Check if a completed task already exists for an item."""
    _init_db()
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM tasks WHERE item_id = ? AND status = ? LIMIT 1",
            (item_id, status),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def count_tasks(status_filter: Optional[str] = None) -> int:
    """Count tasks, optionally by status."""
    _init_db()
    conn = _get_connection()
    try:
        if status_filter:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM tasks WHERE status = ?",
                (status_filter,),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as cnt FROM tasks").fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


def delete_task(task_id: str) -> bool:
    """Delete a task by ID."""
    _init_db()
    conn = _get_connection()
    try:
        cursor = conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_tasks(task_ids: list[str]) -> int:
    """Delete multiple tasks by ID. Returns number of deleted rows."""
    if not task_ids:
        return 0
    _init_db()
    conn = _get_connection()
    try:
        placeholders = ",".join("?" for _ in task_ids)
        cursor = conn.execute(
            f"DELETE FROM tasks WHERE task_id IN ({placeholders})",
            task_ids,
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def _row_to_task(row: sqlite3.Row) -> DownloadTask:
    """Convert a database row to a DownloadTask.

    Old DB rows missing Stage 10D-4 columns are handled gracefully
    via ``row["col"]`` which returns ``None`` for missing columns
    (sqlite3.Row behaviour) and the dataclass defaults.
    """
    return DownloadTask(
        task_id=row["task_id"],
        item_id=row["item_id"],
        title=row["title"],
        download_url=row["download_url"],
        save_path=row["save_path"],
        temp_path=row["temp_path"],
        total_bytes=row["total_bytes"],
        downloaded_bytes=row["downloaded_bytes"],
        status=row["status"],
        error_message=row["error_message"],
        media_source_id=row["media_source_id"],
        container=row["container"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        # Stage 10D-4 fields (safe on old DBs - defaults kick in)
        media_type=row["media_type"] if "media_type" in row.keys() else "",
        series_id=row["series_id"] if "series_id" in row.keys() else "",
        season_id=row["season_id"] if "season_id" in row.keys() else "",
        episode_id=row["episode_id"] if "episode_id" in row.keys() else "",
        season_number=row["season_number"] if "season_number" in row.keys() else None,
        episode_number=row["episode_number"] if "episode_number" in row.keys() else None,
        parent_title=row["parent_title"] if "parent_title" in row.keys() else "",
        display_title=row["display_title"] if "display_title" in row.keys() else "",
        download_method=row["download_method"] if "download_method" in row.keys() else "",
    )
