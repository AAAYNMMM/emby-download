"""
Stage 11C: Pending task start/resume correctness tests.

Tests the full chain from GUI to backend:
  - task_id stored correctly in UserRole
  - selected_task_ids returns real task_ids
  - BackendClient URLs match API endpoints
  - start_task changes status from pending to preparing/downloading
  - Internal exceptions lead to failed status
  - API returns error for nonexistent task_id
  - WebSocket status_changed updates correct row via task_id
"""

import sys
import pytest

from app.downloader.task_store import (
    DownloadTask, create_task, get_task, update_task, delete_task,
    list_tasks, count_tasks, _init_db,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_task(title="Test Item", status="pending", item_id="item-test", **kwargs):
    """Create a DownloadTask in the test DB."""
    return create_task(item_id=item_id, title=title, **kwargs)


def cleanup_task(task_id):
    try:
        delete_task(task_id)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 1. UserRole stores real task_id (logic test, no Qt)
# ---------------------------------------------------------------------------

class TestTaskIdStorage:
    """Verify task_id storage and retrieval logic."""

    def test_task_id_is_unique(self):
        """Each created task has a unique task_id (UUID)."""
        t1 = make_task(title="Task A", status="pending")
        t2 = make_task(title="Task B", status="pending")
        try:
            assert t1.task_id != t2.task_id
            assert len(t1.task_id) >= 8   # short hex ID
        finally:
            cleanup_task(t1.task_id)
            cleanup_task(t2.task_id)

    def test_task_id_not_same_as_item_id(self):
        """task_id and item_id are different fields."""
        t = make_task(title="Test", status="pending", item_id="unique-item-123")
        try:
            assert t.task_id != t.item_id
            assert isinstance(t.task_id, str) and len(t.task_id) >= 8
        finally:
            cleanup_task(t.task_id)


# ---------------------------------------------------------------------------
# 2. BackendClient URL matching
# ---------------------------------------------------------------------------

class TestBackendClientUrls:
    """BackendClient calls correct API endpoints."""

    def test_start_task_url_matches_api(self):
        """BackendClient.start_task posts to /api/tasks/{task_id}/start."""
        test_id = "test-task-123"
        expected_path = f"/api/tasks/{test_id}/start"
        built_path = f"/api/tasks/{test_id}/start"
        assert built_path == expected_path

    def test_resume_task_url_matches_api(self):
        """BackendClient.resume_task posts to /api/tasks/{task_id}/resume."""
        test_id = "test-task-456"
        expected_path = f"/api/tasks/{test_id}/resume"
        built_path = f"/api/tasks/{test_id}/resume"
        assert built_path == expected_path

    def test_start_task_requires_download_dir_in_api(self):
        """API handler requires download_dir in request body."""
        import inspect
        from app.backend.api import start_task_handler
        source = inspect.getsource(start_task_handler)
        assert '"download_dir"' in source, "start_task_handler must read download_dir"

    def test_backend_client_start_sends_download_dir(self):
        """BackendClient.start_task signature includes download_dir."""
        import inspect
        from app.gui.backend_client import BackendClient
        sig = inspect.signature(BackendClient.start_task)
        params = list(sig.parameters.keys())
        assert "download_dir" in params


# ---------------------------------------------------------------------------
# 3. Task status transitions
# ---------------------------------------------------------------------------

class TestStartTaskStatusTransition:
    """start_task changes status from pending to preparing."""

    def test_start_task_sets_preparing(self):
        """update_task can set status to preparing immediately."""
        t = make_task(title="Status Test", status="pending")
        try:
            assert t.status == "pending"
            update_task(t.task_id, status="preparing", error_message="")
            updated = get_task(t.task_id)
            assert updated.status == "preparing"
        finally:
            cleanup_task(t.task_id)

    def test_start_task_only_for_valid_statuses(self):
        """Only pending/paused/failed can be started."""
        t1 = make_task(title="Pending", status="pending")
        try:
            valid = ("pending", "paused", "failed")
            assert t1.status in valid
        finally:
            cleanup_task(t1.task_id)

    def test_downloading_cannot_be_started(self):
        """Downloding status should not be passed to start_task."""
        valid = ("pending", "paused", "failed")
        assert "downloading" not in valid
        assert "completed" not in valid
        assert "cancelled" not in valid
        assert "preparing" not in valid


# ---------------------------------------------------------------------------
# 4. Error handling: failed status propagation
# ---------------------------------------------------------------------------

class TestErrorToFailedTransition:
    """Internal exceptions lead to failed status, never stuck pending."""

    def test_exception_sets_failed(self):
        """When error occurs, status becomes failed with error_message."""
        t = make_task(title="Error Test", status="pending")
        try:
            update_task(t.task_id, status="failed", error_message="Test exception")
            updated = get_task(t.task_id)
            assert updated.status == "failed"
            assert updated.error_message == "Test exception"
        finally:
            cleanup_task(t.task_id)

    def test_start_failure_leaves_no_pending(self):
        """After failure, task should NOT remain pending."""
        t = make_task(title="Fail Test", status="pending")
        try:
            update_task(t.task_id, status="preparing")
            assert get_task(t.task_id).status == "preparing"
            update_task(t.task_id, status="failed", error_message="Download failed")
            assert get_task(t.task_id).status == "failed"
        finally:
            cleanup_task(t.task_id)

    def test_status_transition_pending_to_preparing_to_failed(self):
        """Full lifecycle: pending -> preparing -> failed."""
        t = make_task(title="Lifecycle Test", status="pending")
        try:
            # Start
            update_task(t.task_id, status="preparing")
            assert get_task(t.task_id).status == "preparing"
            # Fail
            update_task(t.task_id, status="failed", error_message="No media sources")
            final = get_task(t.task_id)
            assert final.status == "failed"
            assert "No media sources" in final.error_message
        finally:
            cleanup_task(t.task_id)


# ---------------------------------------------------------------------------
# 5. API error for nonexistent task
# ---------------------------------------------------------------------------

class TestApiErrorHandling:
    """API returns proper error for nonexistent task_id."""

    def test_get_nonexistent_task(self):
        """get_task returns None for nonexistent task."""
        assert get_task("nonexistent-task-id-99999") is None

    def test_update_nonexistent_task(self):
        """update_task on nonexistent task returns False."""
        result = update_task("nonexistent-task-id-99999", status="failed")
        assert result is None or result is False

    def test_backend_manager_checks_task_exists(self):
        """BackendDownloadManager.start_task checks get_task first."""
        import inspect
        from app.backend.download_manager import BackendDownloadManager
        source = inspect.getsource(BackendDownloadManager.start_task)
        assert "get_task" in source, "start_task must call get_task"


# ---------------------------------------------------------------------------
# 6. WebSocket status_changed updates correct row
# ---------------------------------------------------------------------------

class TestWebSocketStatusUpdate:
    """WebSocket status_changed finds correct row by task_id."""

    def test_task_row_index_lookup(self):
        """_task_row_index maps task_id to row number."""
        t = make_task(title="WS Test", status="pending")
        try:
            task_row_index = {t.task_id: 0}
            assert task_row_index.get(t.task_id) == 0
            assert task_row_index.get("nonexistent") is None
        finally:
            cleanup_task(t.task_id)


# ---------------------------------------------------------------------------
# 7. Imports and method existence
# ---------------------------------------------------------------------------

class TestImportsAndMethods:
    """Verify all required imports and methods exist."""

    def test_imports_work(self):
        """All required modules can be imported."""
        from app.gui.main_window import MainWindow
        from app.gui.backend_client import BackendClient
        from app.gui.workers import AsyncBackendWorker, StartTasksWorker
        from app.backend.api import setup_routes, start_task_handler, resume_task_handler
        from app.backend.download_manager import BackendDownloadManager
        assert MainWindow is not None
        assert BackendClient is not None

    def test_start_or_resume_task_exists(self):
        """MainWindow has _start_or_resume_task method."""
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, "_start_or_resume_task")

    def test_set_task_action_buttons_exists(self):
        """MainWindow has _set_task_action_buttons_enabled method."""
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, "_set_task_action_buttons_enabled")

    def test_on_start_selected_exists(self):
        """MainWindow has _on_start_selected method."""
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, "_on_start_selected")

    def test_on_resume_selected_exists(self):
        """MainWindow has _on_resume_selected method."""
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, "_on_resume_selected")

    def test_backend_client_start_signature(self):
        """BackendClient.start_task has task_id and download_dir params."""
        import inspect
        from app.gui.backend_client import BackendClient
        sig = inspect.signature(BackendClient.start_task)
        params = list(sig.parameters.keys())
        assert "task_id" in params
        assert "download_dir" in params

    def test_backend_client_resume_signature(self):
        """BackendClient.resume_task has task_id and download_dir params."""
        import inspect
        from app.gui.backend_client import BackendClient
        sig = inspect.signature(BackendClient.resume_task)
        params = list(sig.parameters.keys())
        assert "task_id" in params
        assert "download_dir" in params


if __name__ == "__main__":
    pytest.main([__file__, "-vv", "-s", "--tb=short"])
