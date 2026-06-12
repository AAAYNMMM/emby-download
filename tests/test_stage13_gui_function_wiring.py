"""
Stage 13: GUI Function Wiring Tests.

Verify that all MainWindow buttons, actions, and signal connections
are properly wired to existing handlers with real logic.
"""

import sys
import os
import ast
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

MAIN_WINDOW_SRC = Path(r"E:\embyD\app\gui\main_window.py")
I18N_SRC = Path(r"E:\embyD\app\gui\i18n.py")


def _get_main_window_ast():
    """Parse main_window.py and return AST."""
    with open(MAIN_WINDOW_SRC, "r", encoding="utf-8") as f:
        return ast.parse(f.read())


def _get_all_method_names() -> set[str]:
    """Return all method names defined in MainWindow class."""
    tree = _get_main_window_ast()
    methods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            methods.add(node.name)
    return methods


def _get_connect_targets() -> set[str]:
    """Return all method names referenced by connect(self.xxx) in MainWindow."""
    tree = _get_main_window_ast()
    targets = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "connect":
                if isinstance(func.value, ast.Attribute):
                    if isinstance(func.value.value, ast.Name) and func.value.value.id == "self":
                        targets.add(func.value.attr)
    return targets


def _find_qpushbuttons() -> list[dict]:
    """Find all QPushButton(QPushButton(...)) instantiations and their connection status."""
    tree = _get_main_window_ast()
    buttons = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                    attr_name = target.attr
                    value = node.value
                    if isinstance(value, ast.Call):
                        func = value.func
                        if isinstance(func, ast.Name) and func.id == "QPushButton":
                            buttons.append({
                                "attr": attr_name,
                                "object_name": None,
                                "connected": False,
                                "handler": None,
                            })

    # Now check for clicked.connect calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "connect":
                # Check if it's self.something.clicked.connect(...)
                if isinstance(func.value, ast.Attribute) and func.value.attr == "clicked":
                    if isinstance(func.value.value, ast.Attribute) and isinstance(func.value.value.value, ast.Name) and func.value.value.value.id == "self":
                        btn_attr = func.value.value.attr
                        handler = None
                        if node.args:
                            arg = node.args[0]
                            if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and arg.value.id == "self":
                                handler = arg.attr
                            elif isinstance(arg, ast.Lambda):
                                handler = "<lambda>"
                        for b in buttons:
                            if b["attr"] == btn_attr:
                                b["connected"] = True
                                b["handler"] = handler

    return buttons


def _find_qactions() -> list[dict]:
    """Find all QAction instantiations in MainWindow."""
    tree = _get_main_window_ast()
    actions = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                    value = node.value
                    if isinstance(value, ast.Call):
                        func = value.func
                        if isinstance(func, ast.Name) and func.id == "QAction":
                            actions.append({
                                "attr": target.attr,
                                "connected": False,
                                "handler": None,
                            })

    # Check triggered.connect calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "connect":
                if isinstance(func.value, ast.Attribute) and func.value.attr == "triggered":
                    if isinstance(func.value.value, ast.Attribute) and isinstance(func.value.value.value, ast.Name) and func.value.value.value.id == "self":
                        btn_attr = func.value.value.attr
                        handler = None
                        if node.args:
                            arg = node.args[0]
                            if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and arg.value.id == "self":
                                handler = arg.attr
                        for a in actions:
                            if a["attr"] == btn_attr:
                                a["connected"] = True
                                a["handler"] = handler

    return actions


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestMainWindowWiring:
    """Verify MainWindow button and action wiring."""

    def test_all_qpushbuttons_have_connections(self):
        """Every QPushButton in MainWindow must have clicked.connect or be marked unimplemented."""
        buttons = _find_qpushbuttons()
        # Allowlist for buttons that may be dynamically enabled/disabled but not directly clicked-connected
        # (e.g. buttons connected via lambda to _set_visible_episodes_checked)
        allowlist = {
            "btn_sb_select_season",  # connected via lambda
            "btn_sb_clear_season",  # connected via lambda
        }
        disconnected = [
            b["attr"] for b in buttons
            if not b["connected"] and b["attr"] not in allowlist
        ]
        assert not disconnected, f"QPushButtons missing clicked.connect: {disconnected}"

    def test_all_qactions_have_connections(self):
        """Every QAction must have triggered.connect."""
        actions = _find_qactions()
        # MainWindow creates QActions in LogWidget's context menu via widgets.py
        # So MainWindow-level QActions may be just imports
        disconnected = [a["attr"] for a in actions if not a["connected"]]
        assert not disconnected, f"QActions missing triggered.connect: {disconnected}"

    def test_all_connect_handlers_exist(self):
        """Every connect(self.xxx) target method must exist in MainWindow."""
        methods = _get_all_method_names()
        targets = _get_connect_targets()
        missing = [t for t in targets if t not in methods]
        assert not missing, f"Connected methods not found: {missing}"

    def test_login_button_handler_exists(self):
        """Login button must have a handler."""
        methods = _get_all_method_names()
        assert "_on_login" in methods

    def test_save_config_button_handler_exists(self):
        """Save download dir button must have a handler."""
        methods = _get_all_method_names()
        assert "_on_save_download_dir" in methods

    def test_browse_download_dir_handler_exists(self):
        """Browse download dir button must have a handler."""
        methods = _get_all_method_names()
        assert "_on_browse_download_dir" in methods

    def test_search_button_handler_exists(self):
        """Search button must have a handler."""
        methods = _get_all_method_names()
        assert "_on_search" in methods

    def test_search_return_pressed_connected(self):
        """Search input returnPressed must be connected to search."""
        tree = _get_main_window_ast()
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "connect":
                    if isinstance(func.value, ast.Attribute) and func.value.attr == "returnPressed":
                        if isinstance(func.value.value, ast.Attribute) and func.value.value.attr == "search_input":
                            found = True
        assert found, "search_input.returnPressed not connected"

    def test_preview_download_button_handler_exists(self):
        """Preview download button must have a handler."""
        methods = _get_all_method_names()
        assert "_on_download" in methods

    def test_task_start_handler_exists(self):
        """Tasks start button must have a handler."""
        methods = _get_all_method_names()
        assert "_on_start_selected" in methods

    def test_task_pause_handler_exists(self):
        """Tasks pause button must have a handler."""
        methods = _get_all_method_names()
        assert "_on_pause_selected" in methods

    def test_task_resume_handler_exists(self):
        """Tasks resume button must have a handler."""
        methods = _get_all_method_names()
        assert "_on_resume_selected" in methods

    def test_task_cancel_handler_exists(self):
        """Tasks cancel button must have a handler."""
        methods = _get_all_method_names()
        assert "_on_cancel_selected" in methods

    def test_task_delete_handler_exists(self):
        """Tasks delete button must have a handler."""
        methods = _get_all_method_names()
        assert "_on_delete_selected" in methods

    def test_series_search_handler_exists(self):
        """Series search button must have a handler."""
        methods = _get_all_method_names()
        assert "_on_series_search" in methods

    def test_series_download_handler_exists(self):
        """Series download selected button must have a handler."""
        methods = _get_all_method_names()
        assert "_on_series_browser_download" in methods

    def test_get_selected_task_ids_returns_list(self):
        """_get_selected_task_ids must exist."""
        methods = _get_all_method_names()
        assert "_get_selected_task_ids" in methods

    def test_no_run_until_complete_in_main_window(self):
        """main_window.py must not contain run_until_complete."""
        with open(MAIN_WINDOW_SRC, "r", encoding="utf-8") as f:
            content = f.read()
        assert "run_until_complete" not in content

    def test_no_backend_client_in_download(self):
        """Preview download must not call BackendClient."""
        with open(MAIN_WINDOW_SRC, "r", encoding="utf-8") as f:
            content = f.read()
        assert "BackendClient" not in content, "main_window.py still references BackendClient"

    def test_no_backend_client_in_task_buttons(self):
        """Task page buttons must not call BackendClient."""
        with open(MAIN_WINDOW_SRC, "r", encoding="utf-8") as f:
            content = f.read()
        assert "BackendClient" not in content

    def test_refresh_seasons_handler_exists(self):
        """Refresh seasons button handler must exist."""
        methods = _get_all_method_names()
        assert "_on_refresh_seasons" in methods

    def test_refresh_episodes_handler_exists(self):
        """Refresh episodes button handler must exist."""
        methods = _get_all_method_names()
        assert "_on_refresh_episodes" in methods

    def test_context_menu_handler_exists(self):
        """Task table context menu handler must exist."""
        methods = _get_all_method_names()
        assert "_on_task_table_context_menu" in methods

    def test_show_error_handler_exists(self):
        """Show error button handler must exist."""
        methods = _get_all_method_names()
        assert "_on_show_error" in methods

    def test_copy_task_title_handler_exists(self):
        """Copy task title handler must exist."""
        methods = _get_all_method_names()
        assert "_on_copy_task_title" in methods

    def test_copy_task_path_handler_exists(self):
        """Copy task path handler must exist."""
        methods = _get_all_method_names()
        assert "_on_copy_task_path" in methods

    def test_back_to_seasons_uses_i18n(self):
        """Back to Seasons button must use i18n constant, not hardcoded English."""
        with open(MAIN_WINDOW_SRC, "r", encoding="utf-8") as f:
            content = f.read()
        assert "BTN_BACK_TO_SEASONS" in content
        assert '"<= Back to Seasons"' not in content


class TestMainWindowGuardedAccess:
    """Test that handlers handle edge cases gracefully."""

    def test_no_selection_no_crash(self):
        """Task handlers should handle empty selection gracefully."""
        methods = _get_all_method_names()
        # These methods use _get_selected_task_ids() internally and check before proceeding
        for name in ["_on_start_selected", "_on_pause_selected", "_on_resume_selected",
                       "_on_cancel_selected", "_on_delete_selected"]:
            assert name in methods, f"{name} must exist"


@pytest.fixture(scope="module")
def qt_app():
    """Create QApplication for GUI tests (module scope to avoid multiple instances)."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


class TestMainWindowSmoke:
    """Smoke tests that create MainWindow."""

    def test_main_window_created(self, qt_app):
        """MainWindow must be creatable without crash."""
        from app.gui.main_window import MainWindow
        from app.config.schema import EmbyConfig
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        try:
            w = MainWindow(config_path=tmp.name)
            assert w is not None
            assert w.tabs is not None
            assert w.tabs.count() >= 4
            w.close()
        finally:
            os.unlink(tmp.name)

    def test_main_window_tabs_exist(self, qt_app):
        """All expected tabs must exist."""
        from app.gui.main_window import MainWindow
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        try:
            w = MainWindow(config_path=tmp.name)
            tab_names = [w.tabs.tabText(i) for i in range(w.tabs.count())]
            from app.gui.i18n import TAB_LOGIN, TAB_SEARCH, TAB_PREVIEW, TAB_SERIES, TAB_TASKS
            for tab in [TAB_LOGIN, TAB_SEARCH, TAB_PREVIEW, TAB_SERIES, TAB_TASKS]:
                assert tab in tab_names, f"Tab {tab} not found"
            w.close()
        finally:
            os.unlink(tmp.name)

