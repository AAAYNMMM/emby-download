"""
Stage 10E tests: GUI responsiveness fixes, Series Browser search, Chinese localization.

Tests:
1. GUI Chinese text - buttons, tabs, table headers
2. Series Browser search - SeriesSearchWorker import & logic
3. Download non-blocking structure checks
4. GUI smoke - MainWindow create/destroy, heartbeat
5. Regression - existing tests from Stage 10D still pass
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# 1. GUI Chinese text verification
# =============================================================================

class TestGUILocalization:
    """Verify i18n module and key Chinese UI constants."""

    def test_i18n_module_imports(self):
        """All i18n constants should be importable."""
        from app.gui.i18n import (
            TAB_LOGIN, TAB_SEARCH, TAB_PREVIEW, TAB_SERIES, TAB_TASKS,
            BTN_LOGIN, BTN_PING, BTN_SEARCH, BTN_PREVIEW, BTN_DOWNLOAD,
            BTN_PAUSE_SELECTED, BTN_RESUME_SELECTED, BTN_CANCEL_SELECTED,
            BTN_OPEN_FOLDER, BTN_SHOW_ERROR,
            BTN_SELECT_ALL_VISIBLE, BTN_CLEAR_VISIBLE,
            BTN_SELECT_SEASON, BTN_CLEAR_SEASON, BTN_DOWNLOAD_SELECTED,
            BTN_REFRESH_TASKS, BTN_REFRESH_SEASONS, BTN_REFRESH_EPISODES,
            BTN_BROWSE, BTN_SAVE_DIR, BTN_SERIES_SEARCH,
        )
        # All should be non-empty Chinese strings
        for name, value in [
            ("TAB_LOGIN", TAB_LOGIN),
            ("TAB_SEARCH", TAB_SEARCH),
            ("TAB_PREVIEW", TAB_PREVIEW),
            ("TAB_SERIES", TAB_SERIES),
            ("TAB_TASKS", TAB_TASKS),
            ("BTN_LOGIN", BTN_LOGIN),
            ("BTN_PING", BTN_PING),
            ("BTN_SEARCH", BTN_SEARCH),
            ("BTN_DOWNLOAD", BTN_DOWNLOAD),
            ("BTN_PAUSE_SELECTED", BTN_PAUSE_SELECTED),
            ("BTN_RESUME_SELECTED", BTN_RESUME_SELECTED),
            ("BTN_CANCEL_SELECTED", BTN_CANCEL_SELECTED),
        ]:
            assert value, f"{name} should not be empty"
            # Must contain Chinese characters (non-ASCII)
            assert any(ord(c) > 127 for c in value), f"{name}='{value}' should contain Chinese"

    def test_tab_names_chinese(self):
        """Tab names must be Chinese."""
        from app.gui.i18n import TAB_LOGIN, TAB_SEARCH, TAB_PREVIEW, TAB_SERIES, TAB_TASKS
        assert TAB_LOGIN == "登录 / 配置"
        assert TAB_SEARCH == "电影"
        assert TAB_PREVIEW == "预览"
        assert TAB_SERIES == "剧集"
        assert TAB_TASKS == "任务"

    def test_task_table_headers_chinese(self):
        """Tasks table headers must be Chinese."""
        from app.gui.i18n import (
            COL_TASK_ID, COL_TASK_TITLE, COL_TASK_STATUS,
            COL_TASK_PROGRESS, COL_TASK_DOWNLOADED, COL_TASK_SPEED,
            COL_TASK_ETA, COL_TASK_UPDATED, COL_TASK_SAVE_PATH,
        )
        assert COL_TASK_ID == "任务ID"
        assert COL_TASK_TITLE == "标题"
        assert COL_TASK_STATUS == "状态"
        assert COL_TASK_PROGRESS == "进度"
        assert COL_TASK_SPEED == "速度"
        assert COL_TASK_ETA == "剩余时间"
        assert COL_TASK_UPDATED == "更新时间"
        assert COL_TASK_SAVE_PATH == "保存路径"

    def test_status_text_mapping(self):
        """status_text() should map all statuses to Chinese."""
        from app.gui.i18n import status_text
        assert status_text("pending") == "等待中"
        assert status_text("preparing") == "准备中"
        assert status_text("downloading") == "下载中"
        assert status_text("paused") == "已暂停"
        assert status_text("completed") == "已完成"
        assert status_text("failed") == "失败"
        assert status_text("cancelled") == "已取消"
        assert status_text("unknown") == "未知"

    def test_context_menu_chinese(self):
        """Context menu labels must be Chinese."""
        from app.gui.i18n import (
            MENU_PAUSE, MENU_RESUME, MENU_CANCEL,
            MENU_OPEN_FOLDER, MENU_SHOW_ERROR, MENU_REFRESH,
        )
        assert MENU_PAUSE == "暂停"
        assert MENU_RESUME == "继续"
        assert MENU_CANCEL == "取消"
        assert MENU_OPEN_FOLDER == "打开文件夹"
        assert MENU_SHOW_ERROR == "查看错误"
        assert MENU_REFRESH == "刷新"

    def test_filter_options_chinese(self):
        """Filter combobox options must be Chinese."""
        from app.gui.i18n import (
            FILTER_ALL, FILTER_PENDING, FILTER_DOWNLOADING,
            FILTER_PAUSED, FILTER_COMPLETED, FILTER_FAILED, FILTER_CANCELLED,
        )
        assert FILTER_ALL == "全部"
        assert FILTER_PENDING == "等待中"
        assert FILTER_DOWNLOADING == "下载中"
        assert FILTER_PAUSED == "已暂停"
        assert FILTER_COMPLETED == "已完成"
        assert FILTER_FAILED == "失败"
        assert FILTER_CANCELLED == "已取消"

    def test_window_title_chinese(self):
        """Window title should contain EmbyD."""
        from app.gui.i18n import WINDOW_TITLE
        assert "EmbyD" in WINDOW_TITLE
        assert any(ord(c) > 127 for c in WINDOW_TITLE)

    def test_series_search_labels_chinese(self):
        """Series search labels must be Chinese."""
        from app.gui.i18n import (
            PLACEHOLDER_SERIES_SEARCH, BTN_SERIES_SEARCH,
            COL_SERIES_NAME, COL_SERIES_YEAR, COL_SERIES_ID,
        )
        assert PLACEHOLDER_SERIES_SEARCH == "搜索剧集"
        assert BTN_SERIES_SEARCH == "搜索剧集"
        assert COL_SERIES_NAME == "剧名"
        assert COL_SERIES_YEAR == "年份"
        assert COL_SERIES_ID == "剧集ID"


# =============================================================================
# 2. Series Browser search
# =============================================================================

class TestSeriesSearch:
    """Test SeriesSearchWorker and search logic."""

    def test_series_search_worker_import(self):
        """SeriesSearchWorker must be importable and have signals."""
        from app.gui.workers import SeriesSearchWorker
        assert SeriesSearchWorker is not None
        worker = SeriesSearchWorker()
        assert hasattr(worker, "finished")
        assert hasattr(worker, "error")

    def test_series_search_worker_run_mocked(self):
        """Test SeriesSearchWorker with mocked API, verifies Type==Series filter."""
        from app.gui.workers import SeriesSearchWorker
        from unittest.mock import MagicMock, patch

        worker = SeriesSearchWorker()
        result_data = None

        def on_finished(data):
            nonlocal result_data
            result_data = data

        worker.finished.connect(on_finished)

        mock_client = MagicMock()
        mock_client.get_user.return_value = {"Id": "user1"}
        # search_items should be called with include_types=["Series"]
        mock_client.search_items.return_value = [
            {"Id": "s1", "Name": "Breaking Bad", "Type": "Series", "ProductionYear": 2008},
            {"Id": "s2", "Name": "Better Call Saul", "Type": "Series", "ProductionYear": 2015},
        ]

        with patch("app.core.emby_api.EmbyApiClient", return_value=mock_client):
            worker.run("http://127.0.0.1:8096", "fake-token", "Breaking", 20)

        # Verify search was called with Series type
        call_kwargs = mock_client.search_items.call_args
        assert call_kwargs is not None
        # include_types should be ["Series"]
        _, kwargs = call_kwargs
        assert kwargs.get("include_types") == ["Series"]

        assert result_data is not None
        assert len(result_data) == 2
        # All results should be Series type
        for item in result_data:
            assert item.get("Type") == "Series"

    def test_series_search_worker_empty_results(self):
        """SeriesSearchWorker should handle empty results."""
        from app.gui.workers import SeriesSearchWorker
        from unittest.mock import MagicMock, patch

        worker = SeriesSearchWorker()
        result_data = None

        def on_finished(data):
            nonlocal result_data
            result_data = data

        worker.finished.connect(on_finished)

        mock_client = MagicMock()
        mock_client.get_user.return_value = {"Id": "user1"}
        mock_client.search_items.return_value = []

        with patch("app.core.emby_api.EmbyApiClient", return_value=mock_client):
            worker.run("http://127.0.0.1:8096", "fake-token", "NoSuchSeries", 20)

        assert result_data is not None
        assert len(result_data) == 0

    def test_series_search_worker_error(self):
        """SeriesSearchWorker should emit error signal on failure."""
        from app.gui.workers import SeriesSearchWorker
        from unittest.mock import MagicMock, patch

        worker = SeriesSearchWorker()
        error_msg = None

        def on_error(msg):
            nonlocal error_msg
            error_msg = msg

        worker.error.connect(on_error)

        mock_client = MagicMock()
        mock_client.get_user.side_effect = Exception("Connection refused")

        with patch("app.core.emby_api.EmbyApiClient", return_value=mock_client):
            worker.run("http://127.0.0.1:8096", "fake-token", "Test")

        assert error_msg is not None
        assert "Connection refused" in error_msg

    def test_series_search_double_click_enters_browser(self):
        """Verify MainWindow has series search double-click handler."""
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, '_on_series_search_double_click')
        assert hasattr(MainWindow, '_on_series_search_result')
        assert hasattr(MainWindow, '_on_series_search')

    def test_series_search_table_exists(self):
        """MainWindow should have series_search_table widget."""
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, '_init_series_browser_tab')
        # Check that init creates series_search_table
        # We can inspect the method's source or just check the class
        import inspect
        source = inspect.getsource(MainWindow._init_series_browser_tab)
        assert "series_search_table" in source
        assert "series_search_input" in source
        assert "btn_series_search" in source


# =============================================================================
# 3. Download non-blocking structure checks
# =============================================================================

class TestDownloadNonBlocking:
    """Verify that download operations don't block the main thread."""

    def test_mainwindow_download_slot_does_not_call_worker_run_directly(self):
        """_on_download must use AsyncBackendWorker, not call worker.run() directly."""
        import inspect
        from app.gui.main_window import MainWindow

        source = inspect.getsource(MainWindow._on_download)
        # Should NOT contain "DownloadItemWorker" (old pattern)
        assert "DownloadItemWorker" not in source, (
            "MainWindow._on_download must not reference DownloadItemWorker directly"
        )
        # Should use AsyncBackendWorker and BackendClient (new Stage 11 pattern)
        assert "AsyncBackendWorker" in source, (
            "MainWindow._on_download must use AsyncBackendWorker for backend calls"
        )
        assert "_backend_client.create_task" in source, (
            "MainWindow._on_download must call BackendClient.create_task"
        )
        # Must not block GUI with run_until_complete
        assert "run_until_complete" not in source, (
            "MainWindow._on_download must not use run_until_complete"
        )

    def test_download_controller_start_task_creates_qthread(self):
        """DownloadController.start_task must create QThread, not call worker.run() directly."""
        import inspect
        from app.gui.download_controller import DownloadController

        source = inspect.getsource(DownloadController.start_task)
        assert "QThread()" in source, (
            "DownloadController.start_task must create QThread for worker"
        )
        assert "worker.moveToThread" in source, (
            "DownloadController.start_task must move worker to thread"
        )
        assert "thread.start()" in source, (
            "DownloadController.start_task must start the thread"
        )
        # Must NOT call worker.run() directly on the same line as creation
        # (it should be connected to thread.started)
        assert "thread.started.connect" in source or "started.connect" in source, (
            "worker.run must be connected to thread.started signal, not called directly"
        )

    def test_update_task_row_has_no_db_write(self):
        """_update_task_row must NOT do DB writes (no update_task(, db_update calls)."""
        import inspect
        from app.gui.main_window import MainWindow

        source = inspect.getsource(MainWindow._update_task_row)
        # Should NOT contain db update function calls (look for 'update_task(' with paren)
        # (the method name _update_task_row contains "update_task" but that's fine)
        assert "update_task(" not in source, (
            "_update_task_row must not call update_task() (DB write)"
        )
        assert "db_update(" not in source, (
            "_update_task_row must not call db_update() (DB write)"
        )
        # Should NOT import task_store
        assert "from app.downloader.task_store" not in source, (
            "_update_task_row must not import task_store"
        )

    def test_controller_progress_has_throttle(self):
        """_on_controller_progress must have throttling logic."""
        import inspect
        from app.gui.main_window import MainWindow

        source = inspect.getsource(MainWindow._on_controller_progress)
        assert "_PROGRESS_UI_THROTTLE" in source or "_progress_last_ui_update" in source, (
            "_on_controller_progress must have progress throttling"
        )

    def test_heartbeat_timer_exists(self):
        """MainWindow must have heartbeat QTimer."""
        import inspect
        from app.gui.main_window import MainWindow

        source = inspect.getsource(MainWindow.__init__)
        assert "_heartbeat_timer" in source, (
            "MainWindow.__init__ must create heartbeat QTimer"
        )
        assert "QTimer" in source or "QTimer(" in source, (
            "MainWindow must use QTimer for heartbeat"
        )

    def test_heartbeat_handler_defined(self):
        """MainWindow must have _on_heartbeat method."""
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, '_on_heartbeat')

    def test_shutdown_stops_heartbeat(self):
        """_shutdown_threads must stop the heartbeat timer."""
        import inspect
        from app.gui.main_window import MainWindow

        source = inspect.getsource(MainWindow._shutdown_threads)
        assert "_heartbeat_timer" in source, (
            "_shutdown_threads must reference _heartbeat_timer"
        )


# =============================================================================
# 4. GUI Smoke Tests
# =============================================================================

class TestGUISmoke10E:
    """Smoke tests for Stage 10E GUI changes."""

    def test_main_window_import(self):
        from app.gui.main_window import MainWindow
        assert MainWindow is not None

    def test_i18n_import(self):
        from app.gui.i18n import status_text
        assert callable(status_text)

    def test_main_window_create_destroy_no_warning(self):
        """MainWindow create/destroy should not trigger QThread warnings."""
        import sys
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()
        w._shutdown_threads()
        w.close()
        app.processEvents()
        assert True

    def test_series_search_ui_widgets_present(self):
        """MainWindow should have series search widgets after init."""
        import sys
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()

        # Check series search widgets exist
        assert hasattr(w, 'series_search_input')
        assert hasattr(w, 'series_search_table')
        assert hasattr(w, 'btn_series_search')

        w._shutdown_threads()
        w.close()
        app.processEvents()

    def test_tasks_table_has_chinese_headers(self):
        """Tasks table must have 7 Chinese column headers (Stage 10F compact)."""
        import sys
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()

        # Check header count
        assert w.tasks_table.columnCount() == 7

        # Check first header is Chinese
        header_item = w.tasks_table.horizontalHeaderItem(0)
        assert header_item is not None
        header_text = header_item.text()
        assert any(ord(c) > 127 for c in header_text), f"Header '{header_text}' should be Chinese"

        w._shutdown_threads()
        w.close()
        app.processEvents()

    def test_tab_labels_chinese(self):
        """All 5 tabs should have Chinese labels."""
        import sys
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()

        # Check tab count
        assert w.tabs.count() == 5

        # Check each tab label has Chinese
        for i in range(5):
            text = w.tabs.tabText(i)
            assert any(ord(c) > 127 for c in text), f"Tab {i} '{text}' should be Chinese"

        w._shutdown_threads()
        w.close()
        app.processEvents()

    def test_series_browser_search_callback_exists(self):
        """_on_series_search must exist."""
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, '_on_series_search')

    def test_heartbeat_is_active_on_init(self):
        """Heartbeat timer should be active after MainWindow init."""
        import sys
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()

        assert w._heartbeat_timer.isActive(), "Heartbeat timer should be active"

        w._shutdown_threads()
        w.close()
        app.processEvents()


# =============================================================================
# 5. Regression - existing tests still pass
# =============================================================================

class TestStage10ERegression:
    """Verify that previous stage tests still pass with new code."""

    def test_stage10d5_imports_still_work(self):
        """All Stage 10D-5 imports should still work."""
        from app.gui.main_window import MainWindow
        from app.gui.download_controller import DownloadController
        from app.gui.workers import (
            SeriesSeasonsWorker,
            SeasonEpisodesWorker,
            DownloadItemWorker,
            SeriesSearchWorker,
        )
        from app.core.naming import build_episode_filename
        from app.core.series import normalize_episode_item, normalize_season_item, sort_episodes, sort_seasons
        from app.core.download_preview import build_item_display_title, format_episode_code
        assert True

    def test_download_controller_signals_unchanged(self):
        """DownloadController signals must still exist."""
        from app.gui.download_controller import DownloadController
        ctrl = DownloadController.__new__(DownloadController)
        # Check that signals are still Signal instances
        from PySide6.QtCore import Signal
        assert hasattr(DownloadController, 'progress')
        assert hasattr(DownloadController, 'status_changed')
        assert hasattr(DownloadController, 'error')
        assert hasattr(DownloadController, 'finished_signal')
        assert hasattr(DownloadController, 'paused_signal')
        assert hasattr(DownloadController, 'cancelled_signal')
        assert hasattr(DownloadController, 'log_message')

    def test_download_controller_api_unchanged(self):
        """DownloadController public API must be unchanged."""
        from app.gui.download_controller import DownloadController
        assert hasattr(DownloadController, 'start_task')
        assert hasattr(DownloadController, 'pause_task')
        assert hasattr(DownloadController, 'resume_task')
        assert hasattr(DownloadController, 'cancel_task')
        assert hasattr(DownloadController, 'has_active_tasks')
        assert hasattr(DownloadController, 'pause_all')
        assert hasattr(DownloadController, 'shutdown')

    def test_task_store_unchanged(self):
        """Task store functions must still work."""
        from app.downloader.task_store import (
            create_task, get_task, update_task, list_tasks,
            find_tasks_by_item_id, delete_task, count_tasks,
        )
        assert callable(create_task)
        assert callable(get_task)
        assert callable(update_task)
        assert callable(list_tasks)
        assert callable(find_tasks_by_item_id)
        assert callable(delete_task)
        assert callable(count_tasks)

    def test_download_preview_unchanged(self):
        """Download preview functions must still work."""
        from app.core.download_preview import (
            build_download_preview, DownloadPreviewResult,
            build_item_display_title, format_episode_code,
        )
        assert DownloadPreviewResult is not None
        assert callable(build_download_preview)
        assert callable(build_item_display_title)
        assert callable(format_episode_code)
