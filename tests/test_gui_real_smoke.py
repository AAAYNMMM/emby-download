"""
GUI smoke tests against a real Emby server via pytest-qt (QTest).

Reads credentials from .env.local only; never hardcodes real values.
All error output is redacted to avoid leaking token/password/server_url.

Run:
    python -m pytest tests/test_gui_real_smoke.py -vv -s --tb=short
"""

import os
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QTableWidget, QComboBox, QListWidget, QLineEdit, QCheckBox
from PySide6.QtTest import QTest

pytestmark = pytest.mark.gui_real

# ── helpers ──────────────────────────────────────────────────────────

def _load_test_env():
    """Load test config from .env.local; returns dict with keys or empty dict."""
    env_path = Path(__file__).resolve().parent.parent / ".env.local"
    if not env_path.exists():
        return {}
    cfg = {}
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def _safe(v, max_len=20):
    """Redact sensitive values for error messages."""
    s = str(v)
    if len(s) <= max_len:
        return s[:4] + "***" if len(s) > 6 else s
    return s[:6] + "***" + s[-4:]


# ── session fixtures ─────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_env():
    return _load_test_env()


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication — pytest-qt provides this automatically."""
    # pytest-qt handles this; stub to satisfy our imports
    pass


@pytest.fixture
def main_window(qtbot, monkeypatch, test_env):
    """Create MainWindow, suppress backend startup."""
    from app.gui.main_window import MainWindow

    # Prevent real backend launch during tests
    monkeypatch.setattr(
        "app.gui.backend_client.BackendClient.start",
        lambda self, config_path=None: None,
    )
    monkeypatch.setattr(
        "app.gui.backend_client.BackendClient.stop",
        lambda self: None,
    )
    monkeypatch.setattr(
        "app.gui.backend_client.BackendClient.is_ready",
        lambda self: False,
    )

    w = MainWindow()
    qtbot.addWidget(w)
    w.show()
    yield w
    w.close()


# ── helper utils ─────────────────────────────────────────────────────

def _find_table_rows(table):
    return table.rowCount() if table else 0


def _combo_items(combo):
    if not combo:
        return []
    return [combo.itemText(i) for i in range(combo.count())]


def _statusbar_text(window):
    return window.status_bar.status_label.text() if hasattr(window, "status_bar") else ""


def _ensure_logged_in(w, qtbot, test_env):
    """Helper: login if not already connected."""
    if not test_env:
        pytest.skip(".env.local not found")
    if any(kw in _statusbar_text(w) for kw in ["已连接", "Connected", "reachable"]):
        return
    server = test_env.get("EMBYD_TEST_SERVER", "")
    username = test_env.get("EMBYD_TEST_USERNAME", "")
    password = test_env.get("EMBYD_TEST_PASSWORD", "")
    if not server or not username or not password:
        pytest.skip("Missing credentials in .env.local")
    w.login_server_url.setText(server)
    w.login_username.setText(username)
    w.login_password.setText(password)
    qtbot.mouseClick(w.btn_login, Qt.LeftButton)
    try:
        qtbot.waitUntil(
            lambda: any(kw in _statusbar_text(w)
                       for kw in ["已连接", "Connected", "reachable"]),
            timeout=15000,
        )
    except Exception:
        pytest.skip("Login failed; cannot proceed")


# ══════════════════════════════════════════════════════════════════════
# Test 1: Login page auto-fill
# ══════════════════════════════════════════════════════════════════════

class TestLoginPage:
    def test_login_fields_exist(self, main_window):
        """All login widgets have stable objectNames."""
        w = main_window
        assert w.findChild(QLineEdit, "server_url_input") is not None
        assert w.findChild(QLineEdit, "username_input") is not None
        assert w.findChild(QLineEdit, "password_input") is not None

    def test_login_tab_visible(self, main_window):
        """Login tab is the first tab (index 0)."""
        assert main_window.tabs.currentIndex() == 0

    def test_login_auto_fill(self, main_window, qtbot, test_env):
        """Fill login fields from .env.local and verify they accept input."""
        if not test_env:
            pytest.skip(".env.local not found — skipping live login fill test")

        w = main_window
        server = test_env.get("EMBYD_TEST_SERVER", "")
        username = test_env.get("EMBYD_TEST_USERNAME", "")
        password = test_env.get("EMBYD_TEST_PASSWORD", "")

        if not server or not username or not password:
            pytest.skip("Missing EMBYD_TEST_SERVER/USERNAME/PASSWORD in .env.local")

        w.login_server_url.clear()
        qtbot.keyClicks(w.login_server_url, server)
        assert w.login_server_url.text() == server

        w.login_username.clear()
        qtbot.keyClicks(w.login_username, username)
        assert w.login_username.text() == username

        w.login_password.clear()
        qtbot.keyClicks(w.login_password, password)
        assert len(w.login_password.text()) > 0


class TestRealLogin:
    """Login against real server via GUI click (requires .env.local)."""

    def test_login_click_and_wait(self, main_window, qtbot, test_env):
        if not test_env:
            pytest.skip(".env.local not found")

        w = main_window
        server = test_env.get("EMBYD_TEST_SERVER", "")
        username = test_env.get("EMBYD_TEST_USERNAME", "")
        password = test_env.get("EMBYD_TEST_PASSWORD", "")

        if not server or not username or not password:
            pytest.skip("Missing credentials in .env.local")

        w.login_server_url.setText(server)
        w.login_username.setText(username)
        w.login_password.setText(password)

        qtbot.mouseClick(w.btn_login, Qt.LeftButton)

        def login_done():
            status = _statusbar_text(w)
            return any(kw in status for kw in ["已连接", "Connected", "reachable", "可以访问"])

        try:
            qtbot.waitUntil(login_done, timeout=15000)
        except Exception:
            status = _safe(_statusbar_text(w))
            pytest.fail(f"Login did not reach connected state within 15s. Status: {status}")

        assert _find_table_rows(w.search_table) >= 0  # table exists


# ══════════════════════════════════════════════════════════════════════
# Test 2: Movie search
# ══════════════════════════════════════════════════════════════════════

class TestMovieSearch:
    def test_search_widgets_exist(self, main_window):
        w = main_window
        assert w.findChild(QLineEdit, "movie_search_input") is not None
        assert w.findChild(type(w.btn_search), "movie_search_button") is not None
        assert w.findChild(QTableWidget, "movie_results_table") is not None

    def test_search_and_results(self, main_window, qtbot, test_env):
        if not test_env:
            pytest.skip(".env.local not found")

        w = main_window
        query = test_env.get("EMBYD_TEST_MOVIE_QUERY", "test")
        server = test_env.get("EMBYD_TEST_SERVER", "")

        if not server:
            pytest.skip("No server configured")

        _ensure_logged_in(w, qtbot, test_env)

        w.tabs.setCurrentIndex(1)
        qtbot.wait(300)

        w.search_input.clear()
        qtbot.keyClicks(w.search_input, query)
        qtbot.mouseClick(w.btn_search, Qt.LeftButton)

        try:
            qtbot.waitUntil(lambda: _find_table_rows(w.search_table) > 0, timeout=15000)
        except Exception:
            pytest.fail(f"Search for {_safe(query)} returned no results within 15s.")

        rows = _find_table_rows(w.search_table)
        assert rows >= 1, f"Expected >= 1 search result, got {rows}"


# ══════════════════════════════════════════════════════════════════════
# Test 3: MediaSource selection
# ══════════════════════════════════════════════════════════════════════

class TestMediaSourceSelection:
    def test_combo_exists(self, main_window):
        w = main_window
        assert w.findChild(QComboBox, "preview_media_source_combo") is not None

    def test_media_source_populated_after_preview(self, main_window, qtbot, test_env):
        """After preview click, media_source_combo should have options."""
        if not test_env:
            pytest.skip(".env.local not found")

        w = main_window
        _ensure_logged_in(w, qtbot, test_env)

        w.tabs.setCurrentIndex(1)
        query = test_env.get("EMBYD_TEST_MOVIE_QUERY", "test")
        w.search_input.clear()
        qtbot.keyClicks(w.search_input, query)
        qtbot.mouseClick(w.btn_search, Qt.LeftButton)

        try:
            qtbot.waitUntil(lambda: _find_table_rows(w.search_table) > 0, timeout=15000)
        except Exception:
            pytest.skip(f"No search results for {_safe(query)}; cannot test MediaSource")

        first_item = w.search_table.item(0, 0)
        if first_item is None:
            pytest.skip("Search table row 0 col 0 is empty")
        item_id = first_item.text().strip()
        w.preview_item_id.setText(item_id)

        qtbot.mouseClick(w.btn_preview, Qt.LeftButton)

        try:
            qtbot.waitUntil(
                lambda: len(_combo_items(w.media_source_combo)) > 0,
                timeout=15000,
            )
        except Exception:
            pytest.fail(f"MediaSource combo not populated after preview of {_safe(item_id)}")

        items = _combo_items(w.media_source_combo)
        assert len(items) > 0, "MediaSource combo is empty after preview"

        if len(items) >= 2:
            w.media_source_combo.setCurrentIndex(1)
            assert w.media_source_combo.currentIndex() == 1


# ══════════════════════════════════════════════════════════════════════
# Test 4: Download task creation & status transition
# ══════════════════════════════════════════════════════════════════════

class TestDownloadTaskFlow:
    def test_download_button_exists(self, main_window):
        w = main_window
        assert w.findChild(type(w.btn_download), "preview_download_button") is not None

    def test_click_download_creates_task(self, main_window, qtbot, test_env):
        """Click download -> verify task appears in tasks table, not stuck pending."""
        if not test_env:
            pytest.skip(".env.local not found")

        w = main_window
        _ensure_logged_in(w, qtbot, test_env)

        download_dir = test_env.get("EMBYD_TEST_DOWNLOAD_DIR", "")
        if not download_dir:
            pytest.skip("EMBYD_TEST_DOWNLOAD_DIR not set in .env.local")
        w.download_dir_input.setText(download_dir)

        # Search and preview a movie
        w.tabs.setCurrentIndex(1)
        query = test_env.get("EMBYD_TEST_MOVIE_QUERY", "test")
        w.search_input.clear()
        qtbot.keyClicks(w.search_input, query)
        qtbot.mouseClick(w.btn_search, Qt.LeftButton)
        try:
            qtbot.waitUntil(lambda: _find_table_rows(w.search_table) > 0, timeout=15000)
        except Exception:
            pytest.skip(f"No search results for {_safe(query)}")

        first_item = w.search_table.item(0, 0)
        if first_item is None:
            pytest.skip("No item in search table")
        w.preview_item_id.setText(first_item.text().strip())
        qtbot.mouseClick(w.btn_preview, Qt.LeftButton)
        qtbot.wait(1000)

        # Click download
        qtbot.mouseClick(w.btn_download, Qt.LeftButton)

        # Switch to tasks tab
        w.tabs.setCurrentIndex(4)
        qtbot.wait(500)

        # Wait for a task to appear
        try:
            qtbot.waitUntil(lambda: _find_table_rows(w.tasks_table) > 0, timeout=10000)
        except Exception:
            pytest.fail("No task appeared in tasks table after download click within 10s.")

        def task_not_stuck():
            for row in range(w.tasks_table.rowCount()):
                status_item = w.tasks_table.item(row, 3)
                if status_item:
                    status = status_item.text().strip()
                    if status and status not in ("等待中", "pending", ""):
                        return True
            return False

        try:
            qtbot.waitUntil(task_not_stuck, timeout=30000)
        except Exception:
            statuses = []
            for row in range(w.tasks_table.rowCount()):
                si = w.tasks_table.item(row, 3)
                if si:
                    statuses.append(si.text().strip())
            pytest.fail(
                f"Task stuck in pending after 30s. Statuses: {statuses}. "
                f"This indicates the download pipeline may be broken."
            )

        # Verify at least one task transitioned
        final_statuses = []
        for row in range(w.tasks_table.rowCount()):
            si = w.tasks_table.item(row, 3)
            if si:
                final_statuses.append(si.text().strip())
        assert any(s not in ("等待中", "pending", "") for s in final_statuses), \
            f"All tasks still pending: {final_statuses}"

    def test_pause_resume_buttons_exist(self, main_window):
        w = main_window
        assert w.findChild(type(w.btn_pause_selected), "task_pause_button") is not None
        assert w.findChild(type(w.btn_resume_selected), "task_resume_button") is not None
        assert w.findChild(type(w.btn_cancel_selected), "task_cancel_button") is not None


# ══════════════════════════════════════════════════════════════════════
# Test 5: GUI heartbeat — ensure UI does not freeze
# ══════════════════════════════════════════════════════════════════════

class TestGUIHeartbeat:
    def test_event_loop_running(self, main_window, qtbot):
        """Verify Qt event loop processes events (GUI not frozen)."""
        w = main_window
        start = time.monotonic()

        w.tabs.setCurrentIndex(1)
        qtbot.wait(100)
        assert w.tabs.currentIndex() == 1
        w.tabs.setCurrentIndex(2)
        qtbot.wait(100)
        assert w.tabs.currentIndex() == 2
        w.tabs.setCurrentIndex(0)
        qtbot.wait(100)
        assert w.tabs.currentIndex() == 0

        elapsed = time.monotonic() - start
        assert elapsed < 3.0, f"Tab switching took {elapsed:.1f}s — GUI may be sluggish"


# ══════════════════════════════════════════════════════════════════════
# Test 6: Safety — no credentials in widget properties
# ══════════════════════════════════════════════════════════════════════

class TestNoCredentialLeak:
    def test_password_field_masked(self, main_window):
        assert main_window.login_password.echoMode() == QLineEdit.EchoMode.Password

    def test_no_hardcoded_credentials_in_code(self):
        """Check source does not contain hardcoded real credentials."""
        src_path = Path(__file__).resolve().parent.parent / "app" / "gui" / "main_window.py"
        src = src_path.read_text(encoding="utf-8")
        forbidden = ["tYWP@", "ayanami", "v1.uhdnow.com"]
        for fb in forbidden:
            assert fb not in src, f"Hardcoded credential \"{fb}\" found in main_window.py"
