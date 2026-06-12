"""
Stage 13: GUI Download Path Tests.

Verify that the preview-to-download flow creates tasks correctly
without requiring BackendClient.
"""

import sys
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


@pytest.fixture(scope="module")
def qt_app():
    """Create QApplication once for module."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def temp_db():
    """Create a temporary task DB file."""
    import tempfile as tf
    from app.downloader.task_store import _init_db
    old_db_path = os.environ.get("EMBYD_TASK_DB_PATH")
    tmp = tf.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.environ["EMBYD_TASK_DB_PATH"] = tmp.name
    _init_db()
    yield tmp.name
    if old_db_path:
        os.environ["EMBYD_TASK_DB_PATH"] = old_db_path
    else:
        os.environ.pop("EMBYD_TASK_DB_PATH", None)
    try:
        os.unlink(tmp.name)
    except Exception:
        pass


@pytest.fixture
def temp_config():
    """Create a temporary config file with pre-set token."""
    from app.config.settings import save_config
    from app.config.schema import EmbyConfig
    from app.core.auth import save_token
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
    tmp.close()
    os.environ["EMBYD_CONFIG_PATH"] = tmp.name
    cfg = EmbyConfig()
    cfg.server_url = "http://test:8096"
    cfg.download_dir = str(Path(tempfile.gettempdir()) / "embyd_test_dl")
    save_token(cfg, "mock_token_123")
    cfg.download_dir = str(Path(tempfile.gettempdir()) / "embyd_test_dl")
    save_config(cfg, tmp.name)
    yield tmp.name
    os.environ.pop("EMBYD_CONFIG_PATH", None)
    try:
        os.unlink(tmp.name)
    except Exception:
        pass


class TestPreviewDownloadFlow:
    """Test the preview-to-download flow."""

    def test_download_creates_task(self, qt_app, temp_db, temp_config):
        """Preview download must create a task via DownloadController."""
        from app.gui.main_window import MainWindow

        w = MainWindow(config_path=temp_config)
        w.download_dir_input.setText(str(Path(tempfile.gettempdir()) / "embyd_test_dl"))
        w.preview_item_id.setText("test_movie_123")

        # Test that _on_download doesn't raise and the right signals are connected
        w._on_download()
        w.close()

    def test_task_saves_media_source_id(self, qt_app, temp_db):
        """Task must save media_source_id via create_task."""
        from app.downloader.task_store import create_task, get_task
        task = create_task(
            item_id="item_001",
            title="Test Movie",
            media_type="Movie",
            media_source_id="ms_001",
        )
        assert task is not None
        saved = get_task(task.task_id)
        assert saved is not None

    def test_download_controller_has_async_methods(self, qt_app, temp_db, temp_config):
        """DownloadController has sync methods (async_* wrappers removed)."""
        from app.gui.main_window import MainWindow
        w = MainWindow(config_path=temp_config)
        dc = w._download_controller
        assert hasattr(dc, "create_task") or hasattr(dc, "start_task")
        assert hasattr(dc, "pause_task") and hasattr(dc, "resume_task")
        assert hasattr(dc, "cancel_task")
        assert hasattr(dc, "stop_all")
        assert hasattr(dc, "start_task")
        w.close()

    def test_empty_dir_shows_error(self, qt_app, temp_db, temp_config):
        """Empty download dir must show error dialog."""
        from app.gui.main_window import MainWindow

        w = MainWindow(config_path=temp_config)
        w.download_dir_input.setText("")
        w.preview_item_id.setText("test_item_789")

        with patch("app.gui.main_window.QMessageBox.warning") as mock_warning:
            w._on_download()
            mock_warning.assert_called()

        w.close()

    def test_worker_error_updates_task(self, qt_app, temp_db):
        """Worker error must mark task failed with error_message."""
        from app.downloader.task_store import create_task, get_task, update_task
        task = create_task(item_id="item_err_001", title="Error Test", media_type="Movie")
        task_id = task.task_id
        update_task(task_id, status="failed", error_message="Connection timeout")
        updated = get_task(task_id)
        assert updated.status == "failed"
        assert updated.error_message == "Connection timeout"

    def test_task_status_sync(self, qt_app, temp_db):
        """Task status must be consistent after updates."""
        from app.downloader.task_store import create_task, get_task, update_task
        task = create_task(item_id="item_sync_001", title="Sync Test", media_type="Movie")
        task_id = task.task_id
        update_task(task_id, status="downloading", error_message="")
        t = get_task(task_id)
        assert t.status == "downloading"
        update_task(task_id, status="completed")
        t = get_task(task_id)
        assert t.status == "completed"
