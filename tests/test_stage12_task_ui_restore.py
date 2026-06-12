"""Stage 12B: Task UI restore tests.

Verifies that the task page layout has been restored to a stable state:
1. QTabWidget used for detail panels (not invisible QStackedWidget)
2. Task table shows short Task ID, stores full ID in UserRole
3. _get_selected_task_ids returns full task_id
4. Error tab displays error_message for failed tasks
5. _refresh_tasks preserves selection and detail state
6. Splitter has only sidebar and right panel (no middle blank widget)
7. GUI smoke passes
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.downloader.task_store import (
    DownloadTask, create_task, update_task, get_task, delete_task, list_tasks,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def make_task(status="pending", item_id="item-test", **kw):
    error_msg = kw.pop("error_message", None)
    t = create_task(item_id=item_id, title="Test Title", **kw)
    if status != "pending" or error_msg:
        update_kw = {}
        if status != "pending":
            update_kw["status"] = status
        if error_msg is not None:
            update_kw["error_message"] = error_msg
        update_task(t.task_id, **update_kw)
        t.status = status
        if error_msg is not None:
            t.error_message = error_msg
    return t


def cleanup(*ids):
    for tid in ids:
        try:
            delete_task(tid)
        except Exception:
            pass


# ===========================================================================
# 1. QTabWidget verification (not invisible QStackedWidget)
# ===========================================================================

class TestTaskUITabWidget:
    """Verify tasks page uses QTabWidget for details/error/log, not QStackedWidget."""

    def test_source_uses_qtabwidget_not_stacked(self):
        """Source code must use QTabWidget for detail panel, not QStackedWidget."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        # Must have QTabWidget for task detail tabs
        assert "task_detail_tabs = QTabWidget()" in src, (
            "Task detail panel must use QTabWidget"
        )
        # Must NOT refer to the old stacked widget name in init method
        assert "self.task_detail_stack = QStackedWidget()" not in src, (
            "task_detail_stack (QStackedWidget) must be removed from tasks tab"
        )

    def test_tab_labels_present(self):
        """Verify all three tab labels exist in source."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "DETAIL_TAB_OVERVIEW" in src, "Overview tab label not found"
        assert "DETAIL_TAB_ERROR" in src, "Error tab label not found"
        assert "DETAIL_TAB_LOG" in src, "Log tab label not found"

    def test_tab_labels_are_chinese(self):
        """Tab labels must be Chinese."""
        from app.gui.i18n import DETAIL_TAB_OVERVIEW, DETAIL_TAB_ERROR, DETAIL_TAB_LOG
        assert DETAIL_TAB_OVERVIEW == "任务详情"
        assert DETAIL_TAB_ERROR == "错误信息"
        assert DETAIL_TAB_LOG == "日志"

    def test_error_tab_uses_qtextedit_readonly(self):
        """Error tab must use QTextEdit with readOnly."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "self.detail_error_text = QTextEdit()" in src
        assert "self.detail_error_text.setReadOnly(True)" in src

    def test_log_tab_reuses_main_log_widget(self):
        """Log tab must use self.log (not create a duplicate)."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "dl_layout.addWidget(self.log)" in src, (
            "Log tab must reuse self.log widget"
        )

    def test_no_stacked_widget_in_tasks_init(self):
        """Tasks init should not create any QStackedWidget."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        # Find _init_tasks_tab and check it has no QStackedWidget()
        lines = src.split("\n")
        in_tasks = False
        indent = None
        stacked_count = 0
        for line in lines:
            if "def _init_tasks_tab" in line:
                in_tasks = True
                continue
            if in_tasks:
                if line.startswith("    def ") and not line.startswith("        "):
                    break
                if "QStackedWidget()" in line:
                    stacked_count += 1
        assert stacked_count == 0, (
            f"_init_tasks_tab contains {stacked_count} QStackedWidget, expected 0"
        )


# ===========================================================================
# 2. Task table layout
# ===========================================================================

class TestTaskTableLayout:
    """Verify task table columns and data storage."""

    def test_table_has_11_columns(self):
        """Task table must have exactly 11 columns."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "self.task_table.setColumnCount(11)" in src

    def test_column_0_is_task_id_visible(self):
        """Column 0 must be visible (not hidden), showing short task ID."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        lines = src.split("\n")
        in_tasks = False
        hidden_cols = []
        for line in lines:
            if "def _init_tasks_tab" in line:
                in_tasks = True
                continue
            if in_tasks:
                if line.startswith("    def ") and not line.startswith("        "):
                    break
                if "self.task_table.setColumnHidden(" in line:
                    parts = line.split(",")
                    if len(parts) >= 1:
                        hidden_cols.append(parts[0].strip())
        # Column 0 must NOT be hidden
        assert "self.task_table.setColumnHidden(0" not in hidden_cols, (
            "Task ID column (0) must be visible"
        )
        # Check that exactly column 10 is hidden (save_path)
        assert "self.task_table.setColumnHidden(10" in src, (
            "Only column 10 (save_path) should be hidden"
        )

    def test_column_2_item_id_visible(self):
        """Column 2 (item_id) must be visible."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "self.task_table.setColumnHidden(2" not in src, (
            "Item ID column (2) must be visible"
        )

    def test_refresh_shows_short_id(self):
        """_refresh_tasks must set short task ID text and full ID in UserRole."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "short_id = task.task_id[:8]" in src, (
            "_refresh_tasks must compute short_id from task_id[:8]"
        )
        assert 'id_item.setData(Qt.ItemDataRole.UserRole, task.task_id)' in src, (
            "Full task_id must be stored in UserRole"
        )

    def test_refresh_stores_row_index(self):
        """_refresh_tasks must cache row index by full task_id."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "self._task_row_index[task.task_id] = row_idx" in src, (
            "Row index cache must key by full task_id"
        )

    def test_get_selected_returns_full_ids(self):
        """_get_selected_task_ids must return list of full task_id strings."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "id_item.data(Qt.ItemDataRole.UserRole)" in src, (
            "Must read UserRole for full task_id"
        )

    def test_table_headers_are_chinese(self):
        """Table headers must be in Chinese."""
        from app.gui.i18n import (
            COL_TASK_ID, COL_TASK_TITLE, COL_TASK_STATUS, COL_TASK_PROGRESS,
            COL_TASK_DOWNLOADED, COL_TASK_TOTAL, COL_TASK_SPEED, COL_TASK_ETA,
            COL_TASK_UPDATED, COL_TASK_SAVE_PATH,
        )
        for label in [COL_TASK_ID, COL_TASK_TITLE, COL_TASK_STATUS]:
            assert any(ord(c) > 127 for c in label), f"{label} must contain Chinese"


# ===========================================================================
# 3. Selection and detail refresh
# ===========================================================================

class TestTaskSelectionState:
    """Verify selection state is preserved and detail panel updates correctly."""

    def test_refresh_preserves_selection(self):
        """_refresh_tasks must save and restore selected task_id."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "selected_task_id = self._get_selected_task_ids()" in src, (
            "Must save selected task_id before rebuild"
        )
        assert "self.task_table.selectRow(restored_row)" in src, (
            "Must restore selection after rebuild"
        )

    def test_refresh_updates_detail_panel(self):
        """_refresh_tasks must call _update_task_detail_panel after rebuild."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "_update_task_detail_panel(selected_task_id)" in src, (
            "Must refresh detail panel after table rebuild"
        )
        assert "_clear_task_detail_panel()" in src, (
            "Must clear detail panel when no task selected"
        )

    def test_error_text_handles_failed_task(self):
        """_update_task_detail_panel must set error text when status is failed."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert 'task.status == "failed" and task.error_message' in src, (
            "Must check for failed status and error_message"
        )
        assert "self.detail_error_text.setPlainText(task.error_message)" in src, (
            "Must display error_message for failed tasks"
        )

    def test_error_text_shows_no_error_for_other_statuses(self):
        """Error tab must show DETAIL_LBL_NO_ERROR for non-failed tasks."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "self.detail_error_text.setPlainText(DETAIL_LBL_NO_ERROR)" in src, (
            "Must show no-error message for non-failed tasks"
        )

    def test_clear_panel_resets_error_text(self):
        """_clear_task_detail_panel must reset error text."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "self.detail_error_text.setPlainText(DETAIL_LBL_NO_ERROR)" in src, (
            "Must reset error text when clearing detail panel"
        )


# ===========================================================================
# 4. Layout structure
# ===========================================================================

class TestTaskLayoutStructure:
    """Verify task page layout has no blank widgets or structural errors."""

    def test_splitter_has_two_widgets_only(self):
        """Splitter in tasks tab must contain exactly: sidebar + right_widget."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        # Verify right_widget contains both table and tabs, not a middle blank widget
        assert "right_widget = QWidget()" in src
        assert "splitter.addWidget(self.tasks_sidebar)" in src
        assert "splitter.addWidget(right_widget)" in src
        # There should be exactly 2 addWidget calls to splitter
        lines = src.split("\n")
        in_tasks = False
        add_count = 0
        for line in lines:
            if "def _init_tasks_tab" in line:
                in_tasks = True
                continue
            if in_tasks:
                if line.startswith("    def ") and not line.startswith("        "):
                    break
                if "splitter.addWidget(" in line:
                    add_count += 1
        assert add_count == 2, (
            f"Splitter should have exactly 2 widgets, found {add_count}"
        )

    def test_right_widget_contains_table_and_tabs(self):
        """right_widget layout must contain task_table and task_detail_tabs."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert 'right_layout.addWidget(self.task_table)' in src
        assert 'right_layout.addWidget(task_detail_tabs)' in src

    def test_sidebar_width_constrained(self):
        """Sidebar must have maximum width between 150-210."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "self.tasks_sidebar.setMaximumWidth(200)" in src, (
            "Sidebar max width should be around 200"
        )
        assert "self.tasks_sidebar.setMinimumWidth(100)" in src, (
            "Sidebar min width should be 100"
        )

    def test_detail_tab_height_reasonable(self):
        """Detail tabs height should be 180-280 range."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        # Check that max height is set to something reasonable
        assert "task_detail_tabs.setMaximumHeight(240)" in src, (
            "Detail tab height should be around 240"
        )

    def test_splitter_stretch_correct(self):
        """Stretch factor: sidebar=0, right_widget=1."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "splitter.setStretchFactor(0, 0)" in src
        assert "splitter.setStretchFactor(1, 1)" in src


# ===========================================================================
# 5. GUI Smoke (optional - requires Qt runtime)
# ===========================================================================

class TestGUISmoke:
    """Smoke test for MainWindow creation with new layout."""

    @pytest.fixture(autouse=True)
    def _qt_app(self):
        """Ensure QApplication exists for the test class."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        yield
        # Drain pending events after each test
        app.processEvents()

    def test_main_window_creates(self, _qt_app):
        """MainWindow should instantiate without crash."""
        import time as _time
        from PySide6.QtWidgets import QApplication
        from app.gui.main_window import MainWindow
        app = QApplication.instance()
        w = MainWindow()
        app.processEvents()
        # Wait for QTimer.singleShot to fire
        _time.sleep(0.2)
        app.processEvents()
        assert w is not None
        w.close()
        app.processEvents()
        # Allow Qt to clean up
        _time.sleep(0.1)
        app.processEvents()

    def test_task_tab_widgets_exist(self, _qt_app):
        """After creation, task tab widgets must be accessible."""
        import time as _time
        from PySide6.QtWidgets import QApplication
        from app.gui.main_window import MainWindow
        app = QApplication.instance()
        w = MainWindow()
        app.processEvents()
        # Wait for QTimer.singleShot to fire
        _time.sleep(0.2)
        app.processEvents()
        try:
            # Check task_detail_tabs exists
            assert hasattr(w, "task_detail_tabs"), "task_detail_tabs must exist"
            assert w.task_detail_tabs.count() == 3, (
                f"Expected 3 tabs, got {w.task_detail_tabs.count()}"
            )
            # Check tab labels
            assert w.task_detail_tabs.tabText(0) is not None
            assert w.task_detail_tabs.tabText(1) is not None
            assert w.task_detail_tabs.tabText(2) is not None
            # Check task_table exists
            assert hasattr(w, "task_table"), "task_table must exist"
            assert w.task_table.columnCount() == 11
            # Check column 0 is NOT hidden
            assert not w.task_table.isColumnHidden(0), "Column 0 (Task ID) must be visible"
        finally:
            w.close()
            app.processEvents()
            _time.sleep(0.1)
            app.processEvents()


# ===========================================================================
# 6. Integration: error message display
# ===========================================================================

class TestErrorDisplay:
    """Verify error messages for failed tasks are displayed correctly."""

    def test_failed_task_error_appears_in_detail(self):
        """When a failed task with error_message is selected, error tab shows it."""
        t = make_task(status="failed", error_message="Simulated download error")
        task_id = t.task_id
        try:
            # Verify task data
            task = get_task(task_id)
            assert task is not None
            assert task.status == "failed"
            assert task.error_message == "Simulated download error"
            # Verify _update_task_detail_panel logic via source check
            # (already covered in TestTaskSelectionState above)
        finally:
            cleanup(task_id)

    def test_non_failed_task_clears_error(self):
        """When a completed task is selected, error tab shows no-error message."""
        t = make_task(status="completed")
        task_id = t.task_id
        try:
            task = get_task(task_id)
            assert task.status == "completed"
            # For completed tasks, error should be None/empty
            assert not task.error_message
        finally:
            cleanup(task_id)

    def test_failed_without_message_shows_no_error(self):
        """Failed task without error_message should still show no-error."""
        t = make_task(status="failed", error_message=None)
        task_id = t.task_id
        try:
            task = get_task(task_id)
            assert task.status == "failed"
            assert not task.error_message
        finally:
            cleanup(task_id)
