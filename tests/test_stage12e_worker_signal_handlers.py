"""Stage 12E: Worker signal handler verification.

Tests that all worker.error / worker.finished / worker.log / worker.result
connections in MainWindow reference real, callable methods.

Regression test for:
  AttributeError: 'MainWindow' object has no attribute '_on_worker_error'

Test strategy:
1. Source-code analysis (ast) to find all connect(self.xxx) patterns
   and verify each referenced method exists in the MainWindow class.
2. Direct smoke test: instantiate MainWindow (with monkeypatches), call
   _on_worker_error, verify it does not crash.
3. GUI smoke: MainWindow create / destroy works.
"""

import ast
import inspect
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Project root (two levels up from tests/)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helper: extract all connect(self.<method>) targets from main_window.py
# ---------------------------------------------------------------------------

def _get_connect_targets(source: str) -> set[str]:
    """Return the set of method names referenced as `self.<name>` in
    `.connect(self.<name>`) calls found in *source*.

    Only extracts **single-level** self.xxx patterns (e.g. self._on_search).
    Multi-level chains like self.log.append_log are skipped because they
    reference methods on sub-objects, not on MainWindow itself.
    Includes both direct and lambda-wrapped references.
    """
    targets: set[str] = set()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        # Match:  foo.connect(self.xxx)
        if isinstance(node, ast.Call):
            fn = node.func
            # foo.connect(...)
            if isinstance(fn, ast.Attribute) and fn.attr == "connect":
                if node.args:
                    arg = node.args[0]
                    # self.xxx  (single-level only — multi-level chains like
                    # self.log.append_log are skipped)
                    if (isinstance(arg, ast.Attribute)
                            and isinstance(arg.value, ast.Name)
                            and arg.value.id == "self"
                            # Ensure it's NOT a multi-level chain:
                            and not (isinstance(arg.value, ast.Attribute))):
                        targets.add(arg.attr)
                    # lambda ...: self.xxx(...)   or   lambda ...: self.xxx
                    elif isinstance(arg, ast.Lambda):
                        _extract_self_attrs_from_expr(arg.body, targets)
    return targets


def _extract_self_attrs_from_expr(node, targets: set[str]):
    """Recursively extract self.xxx from an AST expression node.
    Only single-level self.xxx patterns are collected.
    """
    if isinstance(node, ast.Call):
        fn = node.func
        if (isinstance(fn, ast.Attribute)
                and isinstance(fn.value, ast.Name)
                and fn.value.id == "self"
                # single level only
                and not isinstance(fn.value, ast.Attribute)):
            targets.add(fn.attr)
    elif isinstance(node, ast.Attribute):
        if (isinstance(node.value, ast.Name)
                and node.value.id == "self"
                and isinstance(node.ctx, ast.Load)
                # single level only
                and not isinstance(node.value, ast.Attribute)):
            targets.add(node.attr)
    elif isinstance(node, ast.Tuple):
        for elt in node.elts:
            _extract_self_attrs_from_expr(elt, targets)


def _get_class_method_names(source: str) -> set[str]:
    """Return the set of method names defined directly on MainWindow."""
    names: set[str] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow":
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.add(item.name)
                # Also handle decorated methods
            break
    return names


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWorkerSignalExistence:
    """Static source-code verification of signal handler connections."""

    @classmethod
    def setup_class(cls):
        cls.src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(
            encoding="utf-8"
        )
        cls.methods = _get_class_method_names(cls.src)

    def test_on_worker_error_exists(self):
        """MainWindow must define _on_worker_error."""
        assert "_on_worker_error" in self.methods, (
            "MainWindow._on_worker_error() is missing. "
            "It is referenced by 9 worker.error.connect() calls."
        )

    def test_all_connect_targets_exist(self):
        """Every `connect(self.<method>)` target must be a real method."""
        targets = _get_connect_targets(self.src)

        # Filter out non-handler targets (Qt built-in slots, properties)
        # such as thread.quit, worker.deleteLater, etc. are in _run_worker
        # and connect to Qt methods directly, not self.xxx
        blacklist: set[str] = set()

        missing = sorted(
            name for name in targets
            if name not in self.methods
            and not name.startswith("__")  # dunder
            and name not in blacklist
        )

        assert not missing, (
            f"connect(self.{missing[0]}) references non-existent method. "
            f"All missing: {missing}"
        )

    def test_on_search_worker_error_connected(self):
        """Verify _on_search connects worker.error to a real handler."""
        assert "SearchWorker" in self.src
        # The key line: worker.error.connect(self._on_worker_error)
        assert "worker.error.connect(self._on_worker_error)" in self.src, (
            "Search flow must connect worker.error to self._on_worker_error"
        )
        assert "_on_worker_error" in self.methods

    def test_all_worker_error_connections_exist(self):
        """All 9 references to _on_worker_error must now resolve."""
        # Count references
        count = self.src.count("self._on_worker_error")
        # There are 9 connect calls referencing _on_worker_error,
        # plus the new method definition = 10 occurrences
        assert count >= 9, (
            f"Expected at least 9 references to self._on_worker_error, "
            f"found {count}. Some worker.error.connect() calls may be missing."
        )


class TestWorkerErrorRuntime:
    """Verify _on_worker_error can be called without crashing."""

    def test_on_worker_error_does_not_crash(self):
        """Directly calling _on_worker_error with a string must not raise."""
        with patch.object(Path, "exists", return_value=True):
            with patch("app.gui.main_window.load_config") as mock_load:
                mock_load.return_value = MagicMock(
                    server_url="http://test.local",
                    username="test_user",
                    download_dir="C:/Downloads",
                    token_encrypted="",
                    token_storage="",
                )
                # Avoid importing Qt classes prematurely
                from PySide6.QtWidgets import QApplication
                app = QApplication.instance() or QApplication(sys.argv)

                from app.gui.main_window import MainWindow
                w = MainWindow()
                try:
                    # This must not raise
                    w._on_worker_error("test error message")
                    w._on_worker_error("token: X-Emby-Token abc123")
                    w._on_worker_error("password: mysecret!")
                finally:
                    w.close()
                    app.processEvents()

    def test_on_worker_error_logs_error(self):
        """_on_worker_error must append to the log widget."""
        with patch.object(Path, "exists", return_value=True):
            with patch("app.gui.main_window.load_config") as mock_load:
                mock_load.return_value = MagicMock(
                    server_url="http://test.local",
                    username="test_user",
                    download_dir="C:/Downloads",
                    token_encrypted="",
                    token_storage="",
                )
                from PySide6.QtWidgets import QApplication
                app = QApplication.instance() or QApplication(sys.argv)

                from app.gui.main_window import MainWindow
                w = MainWindow()
                try:
                    initial_text = w.log.toPlainText()
                    w._on_worker_error("something went wrong")
                    app.processEvents()
                    # Log is HTML-based; check plain text for the message
                    current_text = w.log.toPlainText()
                    assert "something went wrong" in current_text, (
                        "Expected error text in log after _on_worker_error"
                    )
                    assert len(current_text) > len(initial_text), (
                        "Expected log content to grow after _on_worker_error"
                    )
                finally:
                    w.close()
                    app.processEvents()

    def test_on_worker_error_redacts_sensitive(self):
        """Sensitive info must not appear in log output."""
        with patch.object(Path, "exists", return_value=True):
            with patch("app.gui.main_window.load_config") as mock_load:
                mock_load.return_value = MagicMock(
                    server_url="http://test.local",
                    username="test_user",
                    download_dir="C:/Downloads",
                    token_encrypted="",
                    token_storage="",
                )
                from PySide6.QtWidgets import QApplication
                app = QApplication.instance() or QApplication(sys.argv)

                from app.gui.main_window import MainWindow
                w = MainWindow()
                try:
                    # Use properly formatted sensitive values that match
                    # the redaction patterns in app/utils/redaction.py
                    w._on_worker_error("X-Emby-Token: secret123")
                    app.processEvents()
                    current_text = w.log.toPlainText()
                    assert "[REDACTED]" in current_text, (
                        "Sensitive token should be redacted; "
                        f"got: {current_text!r}"
                    )
                    assert "secret123" not in current_text, (
                        "Raw token must not appear in log"
                    )
                finally:
                    w.close()
                    app.processEvents()


class TestGuiSmoke:
    """Minimal GUI smoke test for MainWindow creation."""

    def test_main_window_create_and_destroy(self):
        """MainWindow must create and close without error."""
        with patch.object(Path, "exists", return_value=True):
            with patch("app.gui.main_window.load_config") as mock_load:
                mock_load.return_value = MagicMock(
                    server_url="http://test.local",
                    username="test_user",
                    download_dir="C:/Downloads",
                    token_encrypted="",
                    token_storage="",
                )
                from PySide6.QtWidgets import QApplication
                app = QApplication.instance() or QApplication(sys.argv)

                from app.gui.main_window import MainWindow
                w = MainWindow()
                try:
                    app.processEvents()
                    assert w.windowTitle() != ""
                finally:
                    w.close()
                    app.processEvents()


# ---------------------------------------------------------------------------
# Direct import & integration test (requires full GUI stack)
# ---------------------------------------------------------------------------

class TestDirectImports:
    """Verify the module can be imported without ImportError."""

    def test_import_main_window(self):
        """app.gui.main_window can be imported (no syntax/import errors)."""
        from app.gui import main_window
        assert hasattr(main_window, "MainWindow")

    def test_import_workers(self):
        """app.gui.workers can be imported."""
        from app.gui import workers
        assert hasattr(workers, "SearchWorker")
        assert hasattr(workers, "LoginWorker")
        assert hasattr(workers, "PingWorker")

    def test_import_download_controller(self):
        """app.gui.download_controller can be imported."""
        from app.gui import download_controller
        assert hasattr(download_controller, "DownloadController")
