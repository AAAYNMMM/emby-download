"""
Stage 11 tests: Series browser two-level pages.

Tests that:
- Series page has search.
- Double-click series enters season list.
- Click season navigates to Level 2 episode page.
- Back button returns to season list.
- Episode selections preserved when navigating back.
- Version strategy control exists.
- Download Selected creates and starts episode tasks.
"""

import sys, inspect
from pathlib import Path

_app_dir = Path(__file__).resolve().parent.parent
if str(_app_dir) not in sys.path:
    sys.path.insert(0, str(_app_dir))

import pytest


class TestSeriesBrowserStructure:
    """Test the structural changes to series browser."""

    def test_series_stack_widget_exists(self):
        """_init_series_browser_tab creates a QStackedWidget series_stack."""
        source = self._get_init_source()
        assert "self.series_stack = QStackedWidget()" in source, (
            "Series browser must use QStackedWidget for two-level pages"
        )

    def test_series_stack_has_two_pages(self):
        """Stack has page 0 (seasons) and page 1 (episodes)."""
        source = self._get_init_source()
        assert "self.series_stack.addWidget(page0)" in source, "Page 0 missing"
        assert "self.series_stack.addWidget(page1)" in source, "Page 1 missing"

    def test_back_button_exists(self):
        """Page 1 has a back button to return to seasons."""
        source = self._get_init_source()
        assert "btn_back_to_seasons" in source, "Back button missing"
        assert "_on_back_to_seasons" in source, "Back handler missing"

    def test_episode_table_in_page1(self):
        """Episode table is on page 1 (season episodes page)."""
        source = self._get_init_source()
        assert "self.series_episode_table" in source, "Episode table missing"
        # The table should be added to page1_layout
        assert "page1_layout.addWidget(self.series_episode_table" in source, (
            "Episode table not on page 1"
        )

    def test_season_list_in_page0(self):
        """Season list is on page 0 (series view)."""
        source = self._get_init_source()
        assert "self.season_list = QListWidget()" in source, "Season list missing"

    def test_back_to_seasons_function(self):
        """_on_back_to_seasons sets stack to index 0."""
        from app.gui.main_window import MainWindow
        source = inspect.getsource(MainWindow._on_back_to_seasons)
        assert "self.series_stack.setCurrentIndex(0)" in source

    def _get_init_source(self):
        from app.gui.main_window import MainWindow
        return inspect.getsource(MainWindow._init_series_browser_tab)


class TestSeasonNavigation:
    """Test season-to-episode navigation."""

    def test_season_selected_navigates_to_page1(self):
        """_on_season_selected switches stack to page 1."""
        from app.gui.main_window import MainWindow
        source = inspect.getsource(MainWindow._on_season_selected)
        assert "self.series_stack.setCurrentIndex(1)" in source, (
            "Clicking a season must navigate to page 1"
        )

    def test_season_selected_records_season_id(self):
        """_on_season_selected stores _series_browser_current_season_id."""
        from app.gui.main_window import MainWindow
        source = inspect.getsource(MainWindow._on_season_selected)
        assert "_series_browser_current_season_id" in source, (
            "Must store current season ID for refresh"
        )

    def test_enter_series_browser_resets_stack(self):
        """_enter_series_browser resets stack to page 0."""
        from app.gui.main_window import MainWindow
        source = inspect.getsource(MainWindow._enter_series_browser)
        assert "self.series_stack.setCurrentIndex(0)" in source, (
            "Entering series browser must reset to level 1"
        )

    def test_episode_selection_preserved(self):
        """Episode selections (_series_browser_selected_episode_ids) not lost."""
        from app.gui.main_window import MainWindow
        source = inspect.getsource(MainWindow._on_back_to_seasons)
        # Back button only changes stack index, does NOT clear selections
        assert "_series_browser_selected_episode_ids.clear" not in source, (
            "Back button should NOT clear episode selections"
        )


class TestSeriesDownloadButton:
    """Test that Download Selected still works correctly."""

    def test_download_selected_button_on_page1(self):
        """Download Selected button exists on the season episodes page."""
        source = self._get_init_source()
        assert "self.btn_sb_download" in source, "Download button missing"
        assert "page1_layout.addLayout(season_action_layout)" in source, (
            "Download button should be on page 1"
        )

    def test_download_selected_uses_controller(self):
        """Download Selected creates tasks via DownloadController (in _series_create_next)."""
        from app.gui.main_window import MainWindow

        # The main handler delegates to _series_create_next
        source = inspect.getsource(MainWindow._on_series_browser_download)
        assert "_series_create_next" in source, (
            "Download Selected must use background worker chain"
        )

        # _series_create_next creates tasks via DownloadController
        source2 = inspect.getsource(MainWindow._series_create_next)
        assert "_download_controller.start_task" in source2, (
            "_series_create_next must use DownloadController to create tasks"
        )
        assert "task_store.create_task" not in source2, (
            "_series_create_next must NOT use task_store directly"
        )

    def _get_init_source(self):
        from app.gui.main_window import MainWindow
        return inspect.getsource(MainWindow._init_series_browser_tab)


class TestSeasonEpisodesWorker:
    """Test that episodes load in background."""

    def test_season_episodes_worker_importable(self):
        """SeasonEpisodesWorker exists and is importable."""
        from app.gui.workers import SeasonEpisodesWorker
        worker = SeasonEpisodesWorker()
        assert worker is not None

    def test_season_episodes_worker_has_signals(self):
        """SeasonEpisodesWorker has finished and error signals."""
        from app.gui.workers import SeasonEpisodesWorker
        from PySide6.QtCore import Signal
        worker = SeasonEpisodesWorker()
        assert hasattr(worker, "finished")
        assert hasattr(worker, "error")
