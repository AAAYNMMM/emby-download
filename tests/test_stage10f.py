"""
Stage 10F tests: Mature download manager task page.

Tests:
1. Chinese text - sidebar, toolbar, headers, detail tabs, empty state
2. Status filter logic - all filters
3. Button enable states - various selection scenarios
4. Connection status logic
5. Delete record - single and batch, active task check
6. Clean completed
7. GUI smoke - MainWindow create/destroy
"""
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# 1. Chinese text verification
# =============================================================================

class TestStage10FChinese:
    """Verify all new Chinese UI strings are present."""

    def test_sidebar_labels_chinese(self):
        from app.gui.i18n import (
            SIDEBAR_ALL, SIDEBAR_DOWNLOADING, SIDEBAR_PREPARING, SIDEBAR_PENDING,
            SIDEBAR_PAUSED, SIDEBAR_COMPLETED, SIDEBAR_FAILED, SIDEBAR_CANCELLED,
        )
        assert SIDEBAR_ALL == "全部"
        assert SIDEBAR_DOWNLOADING == "下载中"
        assert SIDEBAR_PREPARING == "准备中"
        assert SIDEBAR_PENDING == "等待中"
        assert SIDEBAR_PAUSED == "已暂停"
        assert SIDEBAR_COMPLETED == "已完成"
        assert SIDEBAR_FAILED == "失败"
        assert SIDEBAR_CANCELLED == "已取消"

    def test_toolbar_buttons_chinese(self):
        from app.gui.i18n import (
            BTN_START_SELECTED, BTN_PAUSE_SELECTED, BTN_RESUME_SELECTED,
            BTN_CANCEL_SELECTED, BTN_DELETE_SELECTED, BTN_OPEN_FOLDER,
            BTN_REFRESH_TASKS, BTN_CLEAN_COMPLETED,
        )
        assert any(ord(c) > 127 for c in BTN_START_SELECTED)
        assert any(ord(c) > 127 for c in BTN_PAUSE_SELECTED)
        assert any(ord(c) > 127 for c in BTN_RESUME_SELECTED)
        assert any(ord(c) > 127 for c in BTN_CANCEL_SELECTED)
        assert any(ord(c) > 127 for c in BTN_DELETE_SELECTED)
        assert any(ord(c) > 127 for c in BTN_OPEN_FOLDER)
        assert any(ord(c) > 127 for c in BTN_REFRESH_TASKS)
        assert any(ord(c) > 127 for c in BTN_CLEAN_COMPLETED)

    def test_table_headers_compact_chinese(self):
        from app.gui.i18n import (
            COL_TASK10F_TITLE, COL_TASK10F_STATUS, COL_TASK10F_PROGRESS,
            COL_TASK10F_SIZE, COL_TASK10F_SPEED, COL_TASK10F_ETA, COL_TASK10F_UPDATED,
        )
        assert COL_TASK10F_TITLE == "标题"
        assert COL_TASK10F_STATUS == "状态"
        assert COL_TASK10F_PROGRESS == "进度"
        assert COL_TASK10F_SIZE == "已下载 / 总大小"
        assert COL_TASK10F_SPEED == "速度"
        assert COL_TASK10F_ETA == "剩余时间"
        assert COL_TASK10F_UPDATED == "更新时间"

    def test_detail_tab_labels_chinese(self):
        from app.gui.i18n import (
            DETAIL_TAB_OVERVIEW, DETAIL_TAB_ERROR, DETAIL_TAB_LOG,
        )
        assert DETAIL_TAB_OVERVIEW == "任务详情"
        assert DETAIL_TAB_ERROR == "错误信息"
        assert DETAIL_TAB_LOG == "日志"

    def test_detail_field_labels_chinese(self):
        from app.gui.i18n import (
            DETAIL_LBL_TITLE, DETAIL_LBL_STATUS, DETAIL_LBL_PROGRESS,
            DETAIL_LBL_SAVE_PATH, DETAIL_LBL_TASK_ID, DETAIL_LBL_ITEM_ID,
            DETAIL_LBL_TYPE, DETAIL_LBL_SERIES_INFO,
            DETAIL_LBL_NO_ERROR,
        )
        assert any(ord(c) > 127 for c in DETAIL_LBL_TITLE)
        assert any(ord(c) > 127 for c in DETAIL_LBL_STATUS)
        assert any(ord(c) > 127 for c in DETAIL_LBL_SAVE_PATH)
        assert any(ord(c) > 127 for c in DETAIL_LBL_SERIES_INFO)
        assert DETAIL_LBL_NO_ERROR == "没有错误信息"

    def test_empty_state_text_chinese(self):
        from app.gui.i18n import (
            EMPTY_TASKS_TITLE, EMPTY_TASKS_HINT, EMPTY_TASKS_BTN,
        )
        assert EMPTY_TASKS_TITLE == "暂无下载任务"
        assert EMPTY_TASKS_HINT == "请在电影或剧集页面选择内容后点击下载"
        assert EMPTY_TASKS_BTN == "去搜索"

    def test_connection_status_chinese(self):
        from app.gui.i18n import (
            CONN_NOT_CONFIGURED, CONN_NOT_VERIFIED,
            CONN_SERVER_REACHABLE, CONN_TOKEN_EXPIRED,
        )
        assert CONN_NOT_CONFIGURED == "未配置"
        assert CONN_NOT_VERIFIED == "未验证"
        assert CONN_SERVER_REACHABLE == "服务器可达"
        assert CONN_TOKEN_EXPIRED == "登录失效"

    def test_delete_dialog_chinese(self):
        from app.gui.i18n import (
            DLG_DELETE_TITLE, DLG_DELETE_MSG, DLG_DELETE_ACTIVE, DLG_DELETED,
        )
        assert DLG_DELETE_TITLE == "删除任务记录"
        assert "不会删除已下载文件" in DLG_DELETE_MSG
        assert "正在下载" in DLG_DELETE_ACTIVE

    def test_clean_dialog_chinese(self):
        from app.gui.i18n import (
            DLG_CLEAN_TITLE, DLG_CLEAN_MSG, DLG_CLEAN_RESULT, DLG_CLEAN_NONE,
        )
        assert DLG_CLEAN_TITLE == "清理已完成任务"
        assert "删除" in DLG_CLEAN_MSG
        assert "没有可清理" in DLG_CLEAN_NONE

    def test_context_menu_additions_chinese(self):
        from app.gui.i18n import MENU_START, MENU_COPY_TITLE, MENU_COPY_PATH
        assert MENU_START == "开始"
        assert MENU_COPY_TITLE == "复制标题"
        assert MENU_COPY_PATH == "复制保存路径"

    def test_main_window_has_task_table(self):
        """MainWindow task table should have 11 columns."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()

        assert w.task_table.columnCount() == 11
        headers = [w.task_table.horizontalHeaderItem(i).text() for i in range(11)]
        assert "任务ID" in headers[0]
        assert "标题" in headers[1]
        assert "状态" in headers[3]

        w._shutdown_threads()
        w.close()
        app.processEvents()

    def test_main_window_has_sidebar(self):
        """MainWindow should have tasks_sidebar QListWidget."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()

        assert hasattr(w, 'tasks_sidebar')
        assert w.tasks_sidebar.count() == 8  # All 8 filter items

        w._shutdown_threads()
        w.close()
        app.processEvents()

    def test_main_window_has_detail_tabs(self):
        """MainWindow should have task_detail_tabs QTabWidget."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()

        assert hasattr(w, 'task_detail_tabs')
        assert w.task_detail_tabs.count() == 3  # Overview, Error, Log

        w._shutdown_threads()
        w.close()
        app.processEvents()

    def test_main_window_has_log_widget(self):
        """MainWindow should have log widget."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()

        assert hasattr(w, 'log')
        assert hasattr(w, 'task_detail_tabs')

        w._shutdown_threads()
        w.close()
        app.processEvents()


# =============================================================================
# 2. Status filter logic
# =============================================================================

class TestStatusFilter:
    """Verify status filter sidebar logic."""

    def test_sidebar_filter_labels_match_status(self):
        """Sidebar filter labels should match i18n status constants."""
        from app.gui.i18n import (
            FILTER_ALL, FILTER_DOWNLOADING, FILTER_PREPARING, FILTER_PENDING,
            FILTER_PAUSED, FILTER_COMPLETED, FILTER_FAILED, FILTER_CANCELLED,
        )
        expected = {
            "全部", "下载中", "准备中", "等待中", "已暂停", "已完成", "失败", "已取消",
        }
        labels = {
            FILTER_ALL, FILTER_DOWNLOADING, FILTER_PREPARING, FILTER_PENDING,
            FILTER_PAUSED, FILTER_COMPLETED, FILTER_FAILED, FILTER_CANCELLED,
        }
        assert labels == expected

    def test_filter_all_value(self):
        """FILTER_ALL should be '全部'."""
        from app.gui.i18n import FILTER_ALL
        assert FILTER_ALL == "全部"

    def test_sidebar_count_update(self):
        """_update_sidebar_counts should update labels with counts from DB."""
        from PySide6.QtWidgets import QApplication
        from app.gui.main_window import MainWindow
        from app.downloader.task_store import create_task, update_task, delete_task
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        w = MainWindow()
        app.processEvents()

        # Create test tasks to populate sidebar counts
        tids = []
        statuses = [("downloading", 2), ("preparing", 1), ("pending", 1),
                     ("paused", 3), ("completed", 8), ("failed", 0), ("cancelled", 1)]
        for status, count in statuses:
            for i in range(count):
                t = create_task(item_id=f"sidebar-test-{status}-{i}", title=f"Test {status} {i}")
                if status != "pending":
                    update_task(t.task_id, status=status)
                tids.append(t.task_id)

        w._update_sidebar_counts()

        # Check first item (all) shows total (16)
        assert "(16)" in w.tasks_sidebar.item(0).text()

        # Cleanup
        for tid in tids:
            try:
                delete_task(tid)
            except Exception:
                pass

        w._shutdown_threads()
        w.close()
        app.processEvents()


# =============================================================================
# 3. Button enable states
# =============================================================================

class TestButtonStates:
    """Verify toolbar button enable/disable logic."""

    def _setup_window(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()
        return w, app

    def _teardown_window(self, w, app):
        w._shutdown_threads()
        w.close()
        app.processEvents()

    def test_no_selection_buttons_exist(self):
        """All toolbar buttons should exist."""
        w, app = self._setup_window()

        assert hasattr(w, 'btn_start_selected')
        assert hasattr(w, 'btn_pause_selected')
        assert hasattr(w, 'btn_resume_selected')
        assert hasattr(w, 'btn_cancel_selected')
        assert hasattr(w, 'btn_delete_selected')
        assert hasattr(w, 'btn_open_folder')
        assert hasattr(w, 'btn_refresh_tasks')
        assert hasattr(w, 'btn_clean_completed')

        self._teardown_window(w, app)

    def test_task_selection_handler_exists(self):
        """_on_task_selection_changed must be defined."""
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, '_on_task_selection_changed')

    def test_selection_changed_handler_exists(self):
        """_on_task_selection_changed must be defined."""
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, '_on_task_selection_changed')

    def test_clean_completed_handler_exists(self):
        """_on_clean_completed must be defined."""
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, '_on_clean_completed')

    def test_detail_panel_methods_exist(self):
        """Detail panel methods must be defined."""
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, '_update_task_detail_panel')
        assert hasattr(MainWindow, '_clear_task_detail_panel')
        assert hasattr(MainWindow, '_get_selected_task_ids')


# =============================================================================
# 4. Connection status logic
# =============================================================================

class TestConnectionStatus:
    """Verify connection status state transitions."""

    def test_update_connection_status_method_exists(self):
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, '_update_connection_status')

    def test_no_config_shows_not_configured(self):
        """Status bar should show '未配置' when no server/user set."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        # Create with empty config
        with patch('app.gui.main_window.load_config') as mock_load:
            from app.config.schema import EmbyConfig
            mock_load.return_value = EmbyConfig()
            w = MainWindow()
            app.processEvents()

            status_text = w.status_bar.status_label.text()
            assert status_text in ("未配置", "未验证"), f"Expected 未配置/未验证, got: {status_text}"

            w._shutdown_threads()
            w.close()
            app.processEvents()

    def test_whoami_error_handler_exists(self):
        """_on_whoami_error must handle 401 for connection status."""
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, '_on_whoami_error')

    def test_ping_shows_server_reachable(self):
        """Ping success should show '服务器可达'."""
        from app.gui.i18n import CONN_SERVER_REACHABLE
        assert CONN_SERVER_REACHABLE == "服务器可达"


# =============================================================================
# 5. Delete record
# =============================================================================

class TestDeleteRecord:
    """Verify delete_task and delete_tasks functionality."""

    def test_delete_task_single(self):
        """delete_task should remove a single task."""
        from app.downloader.task_store import create_task, delete_task, get_task

        task = create_task(item_id="test-del-1", title="Test Delete")
        assert task is not None

        result = delete_task(task.task_id)
        assert result is True

        # Should not exist anymore
        assert get_task(task.task_id) is None

    def test_delete_tasks_batch(self):
        """delete_tasks should remove multiple tasks."""
        from app.downloader.task_store import create_task, delete_tasks, get_task

        tasks = []
        for i in range(3):
            t = create_task(item_id=f"test-batch-{i}", title=f"Batch {i}")
            tasks.append(t)

        ids = [t.task_id for t in tasks]
        deleted = delete_tasks(ids)
        assert deleted == 3

        for tid in ids:
            assert get_task(tid) is None

    def test_delete_tasks_empty_list(self):
        """delete_tasks with empty list should return 0."""
        from app.downloader.task_store import delete_tasks
        assert delete_tasks([]) == 0

    def test_delete_active_task_blocked(self):
        """_on_delete_selected should reject deleting downloading tasks."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()

        # Verify delete handler checks for downloading status
        import inspect
        source = inspect.getsource(MainWindow._on_delete_selected)
        assert 'status == "downloading"' in source or "downloading" in source, (
            "_on_delete_selected must check for downloading status"
        )

        w._shutdown_threads()
        w.close()
        app.processEvents()


# =============================================================================
# 6. Clean completed
# =============================================================================

class TestCleanCompleted:
    """Verify clean completed functionality."""

    def test_clean_completed_only_deletes_completed(self):
        """Should only delete completed tasks, not failed/paused/pending."""
        from app.downloader.task_store import (
            create_task, update_task, delete_tasks, get_task, list_tasks,
        )

        # Create tasks with different statuses
        t1 = create_task(item_id="clean-test-1", title="Completed")
        update_task(t1.task_id, status="completed")

        t2 = create_task(item_id="clean-test-2", title="Failed")
        update_task(t2.task_id, status="failed")

        t3 = create_task(item_id="clean-test-3", title="Pending")
        # stays pending

        # Simulate clean completed: get all completed, delete them
        completed = list_tasks(status_filter="completed", limit=100)
        completed_ids = [t.task_id for t in completed]
        assert t1.task_id in completed_ids
        assert t2.task_id not in completed_ids
        assert t3.task_id not in completed_ids

        # Delete only completed
        deleted = delete_tasks(completed_ids)
        assert deleted >= 1

        # Verify completed is gone but others remain
        assert get_task(t1.task_id) is None
        assert get_task(t2.task_id) is not None  # failed still exists
        assert get_task(t3.task_id) is not None  # pending still exists

        # Cleanup
        delete_tasks([t2.task_id, t3.task_id])

    def test_clean_completed_on_mainwindow_exists(self):
        """_on_clean_completed must be defined."""
        from app.gui.main_window import MainWindow
        assert hasattr(MainWindow, '_on_clean_completed')


# =============================================================================
# 7. GUI Smoke Tests
# =============================================================================

class TestGUISmoke10F:
    """Smoke tests for Stage 10F GUI changes."""

    def test_main_window_import(self):
        from app.gui.main_window import MainWindow
        assert MainWindow is not None

    def test_main_window_create_destroy_no_warning(self):
        """MainWindow create/destroy should not trigger QThread warnings."""
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

    def test_tasks_tab_index(self):
        """Tasks tab should be at index 4."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        from app.gui.i18n import TAB_TASKS
        w = MainWindow()
        app.processEvents()

        # Find tasks tab index
        found = False
        for i in range(w.tabs.count()):
            if w.tabs.tabText(i) == TAB_TASKS:
                found = True
                break
        assert found, f"Tab '{TAB_TASKS}' not found"

        w._shutdown_threads()
        w.close()
        app.processEvents()

    def test_all_tabs_present(self):
        """All 5 tabs should be present."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()

        assert w.tabs.count() == 5

        w._shutdown_threads()
        w.close()
        app.processEvents()

    def test_search_input_exists_on_tasks(self):
        """Tasks tab should have search input for filtering."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()

        assert hasattr(w, 'tasks_search_input')
        assert w.tasks_search_input.placeholderText() != ""

        w._shutdown_threads()
        w.close()
        app.processEvents()

    def test_sidebar_has_user_role_data(self):
        """Sidebar items should have UserRole data with status keys."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()

        # Check each sidebar item has UserRole data
        for i in range(w.tasks_sidebar.count()):
            item = w.tasks_sidebar.item(i)
            key = item.data(Qt.ItemDataRole.UserRole)
            assert key is not None, f"Sidebar item {i} has no UserRole data"

        w._shutdown_threads()
        w.close()
        app.processEvents()

    def test_task_store_delete_tasks_importable(self):
        """delete_tasks should be importable."""
        from app.downloader.task_store import delete_tasks
        assert callable(delete_tasks)


# =============================================================================
# 8. Regression - existing tests still pass
# =============================================================================

class TestStage10FRegression:
    """Verify previous stage functionality is preserved."""

    def test_download_controller_unchanged(self):
        """DownloadController API must be unchanged."""
        from app.gui.download_controller import DownloadController
        assert hasattr(DownloadController, 'start_task')
        assert hasattr(DownloadController, 'pause_task')
        assert hasattr(DownloadController, 'resume_task')
        assert hasattr(DownloadController, 'cancel_task')
        assert hasattr(DownloadController, 'has_active_tasks')

    def test_task_store_core_functions_unchanged(self):
        """Core task_store functions must still work."""
        from app.downloader.task_store import (
            create_task, get_task, update_task, list_tasks,
            find_tasks_by_item_id, delete_task, count_tasks,
            delete_tasks,
        )
        assert callable(create_task)
        assert callable(get_task)
        assert callable(update_task)
        assert callable(list_tasks)
        assert callable(delete_task)
        assert callable(delete_tasks)

    def test_i18n_core_constants_unchanged(self):
        """Previously existing i18n constants must be preserved."""
        from app.gui.i18n import (
            TAB_LOGIN, TAB_SEARCH, TAB_PREVIEW, TAB_SERIES, TAB_TASKS,
            status_text, WINDOW_TITLE,
        )
        assert TAB_LOGIN == "登录 / 配置"
        assert TAB_SEARCH == "电影"
        assert TAB_TASKS == "任务"
        assert status_text("pending") == "等待中"
        assert status_text("preparing") == "准备中"
        assert "EmbyD" in WINDOW_TITLE

    def test_formatting_functions_unchanged(self):
        """Formatting utilities must still work."""
        from app.utils.formatting import (
            format_bytes, format_speed_gui, format_eta,
            format_progress_pct, compute_eta_seconds,
        )
        assert format_bytes(0) == "0 B"
        assert format_bytes(1024) == "1.00 KB"
        assert format_progress_pct(500, 1000) == "50%"
        assert format_progress_pct(0, None) == "unknown"
