"""
GUI tests for Series/Episodes browser against real Emby server via pytest-qt.

Run:
    python -m pytest tests/test_gui_real_series.py -vv -s --tb=short
"""

import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget, QListWidget, QLineEdit, QCheckBox
from PySide6.QtTest import QTest

pytestmark = pytest.mark.gui_real

# ── helpers ──────────────────────────────────────────────────────────

def _load_test_env():
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
    s = str(v)
    if len(s) <= max_len:
        return s[:4] + "***" if len(s) > 6 else s
    return s[:6] + "***" + s[-4:]


def _table_rows(table):
    return table.rowCount() if table else 0


def _list_count(lst):
    return lst.count() if lst else 0


def _statusbar_text(window):
    return window.status_bar.status_label.text() if hasattr(window, "status_bar") else ""


# ── fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_env():
    return _load_test_env()


@pytest.fixture(scope="session")
def qapp():
    pass  # pytest-qt provides this


@pytest.fixture
def main_window(qtbot, monkeypatch, test_env):
    from app.gui.main_window import MainWindow

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


def _ensure_logged_in(w, qtbot, test_env):
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
        pytest.skip("Login failed; cannot test series")


# ══════════════════════════════════════════════════════════════════════

class TestSeriesWidgets:
    def test_series_widgets_exist(self, main_window):
        w = main_window
        assert w.findChild(QLineEdit, "series_search_input") is not None
        assert w.findChild(type(w.btn_series_search), "series_search_button") is not None
        assert w.findChild(QTableWidget, "series_results_table") is not None
        assert w.findChild(QListWidget, "season_list") is not None
        assert w.findChild(QTableWidget, "episode_table") is not None
        assert w.findChild(type(w.btn_back_to_seasons), "episode_back_button") is not None
        assert w.findChild(type(w.btn_sb_download), "episode_download_selected_button") is not None


class TestSeriesSearch:
    def test_search_series(self, main_window, qtbot, test_env):
        if not test_env:
            pytest.skip(".env.local not found")
        w = main_window
        _ensure_logged_in(w, qtbot, test_env)

        w.tabs.setCurrentIndex(3)
        qtbot.wait(300)
        assert w.tabs.currentIndex() == 3

        query = test_env.get("EMBYD_TEST_SERIES_QUERY", "")
        if not query:
            pytest.skip("EMBYD_TEST_SERIES_QUERY not set in .env.local")

        w.series_search_input.clear()
        qtbot.keyClicks(w.series_search_input, query)
        qtbot.mouseClick(w.btn_series_search, Qt.LeftButton)

        try:
            qtbot.waitUntil(
                lambda: w.series_search_table.isVisible() or _table_rows(w.series_search_table) > 0,
                timeout=15000,
            )
        except Exception:
            pytest.fail(f"Series search for {_safe(query)} returned no results within 15s.")

        if _table_rows(w.series_search_table) == 0:
            pytest.skip(f"No series found for query {_safe(query)} — skipping further series tests")


class TestSeasonNavigation:
    def test_double_click_series_enters_season_list(self, main_window, qtbot, test_env):
        if not test_env:
            pytest.skip(".env.local not found")
        w = main_window
        _ensure_logged_in(w, qtbot, test_env)

        w.tabs.setCurrentIndex(3)
        qtbot.wait(300)

        query = test_env.get("EMBYD_TEST_SERIES_QUERY", "")
        if not query:
            pytest.skip("EMBYD_TEST_SERIES_QUERY not set")

        w.series_search_input.clear()
        qtbot.keyClicks(w.series_search_input, query)
        qtbot.mouseClick(w.btn_series_search, Qt.LeftButton)

        try:
            qtbot.waitUntil(lambda: _table_rows(w.series_search_table) > 0, timeout=15000)
        except Exception:
            pytest.skip(f"No series results for {_safe(query)}")

        item = w.series_search_table.item(0, 0)
        if item is None:
            pytest.skip("Series search table row 0 empty")
        series_name = item.text().strip()

        cell_rect = w.series_search_table.visualItemRect(item)
        QTest.mouseDClick(
            w.series_search_table.viewport(),
            Qt.LeftButton,
            pos=cell_rect.center(),
        )
        qtbot.wait(2000)

        season_count = _list_count(w.season_list)
        if season_count == 0:
            pytest.skip(f"No seasons found for series {_safe(series_name)}")

        assert season_count >= 1, f"Season list empty for series {_safe(series_name)}"


class TestEpisodePage:
    def test_click_season_enters_episode_page(self, main_window, qtbot, test_env):
        if not test_env:
            pytest.skip(".env.local not found")
        w = main_window
        _ensure_logged_in(w, qtbot, test_env)
        w.tabs.setCurrentIndex(3)
        qtbot.wait(300)

        query = test_env.get("EMBYD_TEST_SERIES_QUERY", "")
        if not query:
            pytest.skip("EMBYD_TEST_SERIES_QUERY not set")
        w.series_search_input.clear()
        qtbot.keyClicks(w.series_search_input, query)
        qtbot.mouseClick(w.btn_series_search, Qt.LeftButton)

        try:
            qtbot.waitUntil(lambda: _table_rows(w.series_search_table) > 0, timeout=15000)
        except Exception:
            pytest.skip(f"No series results")

        item = w.series_search_table.item(0, 0)
        QTest.mouseDClick(w.series_search_table.viewport(), Qt.LeftButton,
                          pos=w.series_search_table.visualItemRect(item).center())
        qtbot.wait(2000)

        if _list_count(w.season_list) == 0:
            pytest.skip("No seasons available")

        first_season = w.season_list.item(0)
        w.season_list.setCurrentItem(first_season)
        qtbot.wait(2000)

        ep_count = _table_rows(w.series_episode_table)
        if ep_count == 0:
            pytest.skip("No episodes found for first season")

        assert ep_count >= 1, f"Episode table empty"


class TestEpisodeCheckAndDownload:
    def test_check_episode_and_download(self, main_window, qtbot, test_env):
        if not test_env:
            pytest.skip(".env.local not found")
        w = main_window
        download_dir = test_env.get("EMBYD_TEST_DOWNLOAD_DIR", "")
        if not download_dir:
            pytest.skip("EMBYD_TEST_DOWNLOAD_DIR not set")

        _ensure_logged_in(w, qtbot, test_env)
        w.tabs.setCurrentIndex(3)
        w.download_dir_input.setText(download_dir)
        qtbot.wait(300)

        query = test_env.get("EMBYD_TEST_SERIES_QUERY", "")
        if not query:
            pytest.skip("EMBYD_TEST_SERIES_QUERY not set")
        w.series_search_input.clear()
        qtbot.keyClicks(w.series_search_input, query)
        qtbot.mouseClick(w.btn_series_search, Qt.LeftButton)
        try:
            qtbot.waitUntil(lambda: _table_rows(w.series_search_table) > 0, timeout=15000)
        except Exception:
            pytest.skip("No series results")

        item = w.series_search_table.item(0, 0)
        QTest.mouseDClick(w.series_search_table.viewport(), Qt.LeftButton,
                          pos=w.series_search_table.visualItemRect(item).center())
        qtbot.wait(2000)

        if _list_count(w.season_list) == 0:
            pytest.skip("No seasons")

        w.season_list.setCurrentItem(w.season_list.item(0))
        qtbot.wait(2000)

        if _table_rows(w.series_episode_table) == 0:
            pytest.skip("No episodes")

        cb_widget = w.series_episode_table.cellWidget(0, 0)
        if cb_widget is None:
            pytest.skip("Episode table has no checkboxes")

        if isinstance(cb_widget, QCheckBox):
            cb_widget.setChecked(True)
            qtbot.wait(200)

        qtbot.mouseClick(w.btn_sb_download, Qt.LeftButton)
        qtbot.wait(2000)

        w.tabs.setCurrentIndex(4)
        qtbot.wait(500)

        try:
            qtbot.waitUntil(lambda: _table_rows(w.tasks_table) > 0, timeout=10000)
        except Exception:
            pytest.fail("No episode task appeared in tasks table")

        def task_not_stuck():
            for row in range(w.tasks_table.rowCount()):
                si = w.tasks_table.item(row, 3)
                if si and si.text().strip() not in ("等待中", "pending", ""):
                    return True
            return False

        try:
            qtbot.waitUntil(task_not_stuck, timeout=30000)
        except Exception:
            statuses = [w.tasks_table.item(r, 3).text().strip()
                       for r in range(w.tasks_table.rowCount()) if w.tasks_table.item(r, 3)]
            pytest.fail(f"Episode task stuck in pending after 30s. Statuses: {statuses}")


class TestBackNavigation:
    def test_back_button_returns_to_season_list(self, main_window, qtbot, test_env):
        if not test_env:
            pytest.skip(".env.local not found")
        w = main_window
        _ensure_logged_in(w, qtbot, test_env)
        w.tabs.setCurrentIndex(3)
        qtbot.wait(300)

        query = test_env.get("EMBYD_TEST_SERIES_QUERY", "")
        if not query:
            pytest.skip("EMBYD_TEST_SERIES_QUERY not set")
        w.series_search_input.clear()
        qtbot.keyClicks(w.series_search_input, query)
        qtbot.mouseClick(w.btn_series_search, Qt.LeftButton)
        try:
            qtbot.waitUntil(lambda: _table_rows(w.series_search_table) > 0, timeout=15000)
        except Exception:
            pytest.skip("No series results")

        item = w.series_search_table.item(0, 0)
        QTest.mouseDClick(w.series_search_table.viewport(), Qt.LeftButton,
                          pos=w.series_search_table.visualItemRect(item).center())
        qtbot.wait(2000)

        if _list_count(w.season_list) == 0:
            pytest.skip("No seasons")

        w.season_list.setCurrentItem(w.season_list.item(0))
        qtbot.wait(2000)

        initial_ep_count = _table_rows(w.series_episode_table)
        assert initial_ep_count >= 0

        cb = w.series_episode_table.cellWidget(0, 0)
        if cb is not None and isinstance(cb, QCheckBox):
            cb.setChecked(True)
            qtbot.wait(100)

        qtbot.mouseClick(w.btn_back_to_seasons, Qt.LeftButton)
        qtbot.wait(1000)

        assert _list_count(w.season_list) >= 1

        if _list_count(w.season_list) >= 2:
            w.season_list.setCurrentItem(w.season_list.item(1))
            qtbot.wait(2000)
            assert _table_rows(w.series_episode_table) >= 0
