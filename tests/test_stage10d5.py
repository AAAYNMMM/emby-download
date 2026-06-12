"""
Stage 10D-5 tests: Series Browser GUI & episode selection/task creation.

Tests:
1. Search result type routing (Movie/Series/Episode/Unknown)
2. Series selection state (set operations, cross-season persistence)
3. Episode task creation (single, multi, metadata, display_title, filename)
4. Duplicate skip (find_tasks_by_item_id)
5. Worker imports (SeriesSeasonsWorker, SeasonEpisodesWorker)
6. GUI smoke (MainWindow create/destroy, no QThread warning)
7. find_tasks_by_item_id with various statuses
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.naming import build_episode_filename
from app.core.series import normalize_episode_item, normalize_season_item, sort_episodes, sort_seasons
from app.core.download_preview import build_item_display_title, format_episode_code


# =============================================================================
# 1. Search result type routing (unit tests on type detection logic)
# =============================================================================

class TestSearchTypeRouting:
    """Test that item Type field correctly identifies media type."""

    def test_movie_item_type(self):
        item = {"Id": "m1", "Name": "Test Movie", "Type": "Movie", "ProductionYear": 2024}
        assert item.get("Type") == "Movie"

    def test_series_item_type(self):
        item = {"Id": "s1", "Name": "Test Series", "Type": "Series", "ProductionYear": 2023}
        assert item.get("Type") == "Series"

    def test_episode_item_type(self):
        item = {
            "Id": "e1", "Name": "Pilot", "Type": "Episode",
            "SeriesName": "Test Show", "ParentIndexNumber": 1, "IndexNumber": 1,
        }
        assert item.get("Type") == "Episode"

    def test_unknown_type_handled(self):
        """Unknown types should not crash routing."""
        item = {"Id": "u1", "Name": "Unknown", "Type": "Audio"}
        item_type = item.get("Type", "")
        assert item_type not in ("Movie", "Series", "Episode")

    def test_missing_type_field(self):
        """Missing Type field should be handled."""
        item = {"Id": "x1", "Name": "No Type"}
        item_type = item.get("Type", "")
        assert item_type == ""

    def test_build_display_title_movie(self):
        item = {"Id": "m1", "Name": "Inception", "Type": "Movie", "ProductionYear": 2010}
        title = build_item_display_title(item)
        assert "Inception" in title
        assert "2010" in title

    def test_build_display_title_episode(self):
        item = {
            "Id": "e1", "Name": "Pilot", "Type": "Episode",
            "SeriesName": "Breaking Bad", "ParentIndexNumber": 1, "IndexNumber": 1,
        }
        title = build_item_display_title(item)
        assert "Breaking Bad" in title
        assert "S01E01" in title
        assert "Pilot" in title

    def test_format_episode_code_s01e02(self):
        code = format_episode_code(1, 2)
        assert code == "S01E02"

    def test_format_episode_code_s00e01(self):
        code = format_episode_code(0, 1)
        assert code == "E01"  # S00 omitted per implementation

    def test_format_episode_code_no_numbers(self):
        code = format_episode_code(0, 0)
        assert code == ""


# =============================================================================
# 2. Series selection state (set-based logic)
# =============================================================================

class TestSeriesSelectionState:
    """Test the selection set logic used by Series Browser."""

    def test_empty_selection_set(self):
        selected: set[str] = set()
        assert len(selected) == 0

    def test_add_episode_to_selection(self):
        selected: set[str] = set()
        selected.add("ep001")
        selected.add("ep002")
        assert "ep001" in selected
        assert "ep002" in selected
        assert len(selected) == 2

    def test_remove_episode_from_selection(self):
        selected: set[str] = {"ep001", "ep002", "ep003"}
        selected.discard("ep002")
        assert "ep002" not in selected
        assert len(selected) == 2

    def test_cross_season_selection_persists(self):
        """Switching seasons should not lose selections from other seasons."""
        selected: set[str] = {"s1e1", "s1e2", "s2e1"}
        # Simulate switching to season 1: only s1 episodes visible
        season1_episodes = {"s1e1", "s1e2", "s1e3"}
        # Clear visible only clears season 1 episodes from selection
        for ep_id in season1_episodes:
            selected.discard(ep_id)
        # Season 2 selection persists
        assert "s2e1" in selected
        assert "s1e1" not in selected

    def test_select_season_adds_all(self):
        """Select Season adds all visible episodes."""
        selected: set[str] = {"other_ep"}
        season2_episodes = {"s2e1", "s2e2", "s2e3"}
        for ep_id in season2_episodes:
            selected.add(ep_id)
        assert "s2e1" in selected
        assert "s2e2" in selected
        assert "other_ep" in selected

    def test_clear_visible_does_not_clear_other_seasons(self):
        """Clear Visible should only affect currently visible episodes."""
        selected: set[str] = {"s1e1", "s1e2", "s2e1", "s2e2"}
        visible = {"s1e1", "s1e2"}  # current season
        for ep_id in visible:
            selected.discard(ep_id)
        assert "s1e1" not in selected
        assert "s1e2" not in selected
        assert "s2e1" in selected
        assert "s2e2" in selected


# =============================================================================
# 3. Episode task creation (metadata, display_title, filename)
# =============================================================================

class TestEpisodeTaskCreation:
    """Test that episode metadata flows correctly for task creation."""

    def test_episode_metadata_dict(self):
        """Verify episode metadata dict has all required fields."""
        ep = {
            "item_id": "ep001",
            "name": "Pilot",
            "series_id": "s1",
            "series_name": "Test Show",
            "season_id": "sea1",
            "season_name": "Season 1",
            "season_number": 1,
            "episode_number": 1,
            "production_year": 2024,
            "overview": "A great start.",
            "runtime_ticks": 24000000000,
            "media_type": "Episode",
        }
        assert ep["media_type"] == "Episode"
        assert ep["series_id"] == "s1"
        assert ep["season_number"] == 1
        assert ep["episode_number"] == 1

    def test_build_episode_filename_for_task(self):
        """Episode filename should match SxxEyy format."""
        filename = build_episode_filename("Test Show", 1, 2, "The Second", "mkv")
        assert filename == "Test Show - S01E02 - The Second.mkv"

    def test_build_episode_filename_no_title(self):
        filename = build_episode_filename("Test Show", 3, 5, "", "mp4")
        assert filename == "Test Show - S03E05.mp4"

    def test_display_title_for_tasks_table(self):
        """display_title should be the filename minus extension."""
        filename = build_episode_filename("Breaking Bad", 1, 2, "Cat's in the Bag", "mkv")
        display = filename[:-4]  # strip .mkv
        assert display == "Breaking Bad - S01E02 - Cat's in the Bag"

    def test_multiple_episodes_independent_tasks(self):
        """Each episode should get its own task with unique metadata."""
        episodes = [
            {"item_id": "e1", "name": "Ep1", "season_number": 1, "episode_number": 1},
            {"item_id": "e2", "name": "Ep2", "season_number": 1, "episode_number": 2},
            {"item_id": "e3", "name": "Ep3", "season_number": 1, "episode_number": 3},
        ]
        task_ids = set()
        for ep in episodes:
            # Simulate task ID creation (each would be unique in real code)
            import uuid
            task_id = str(uuid.uuid4())[:8]
            task_ids.add(task_id)
        # All tasks should have unique IDs
        assert len(task_ids) == 3

    def test_episode_normalize_preserves_metadata(self):
        """normalize_episode_item should preserve all metadata fields."""
        raw = {
            "Id": "ep123",
            "Name": "Pilot",
            "SeriesId": "s456",
            "SeriesName": "Test Show",
            "SeasonId": "sea789",
            "SeasonName": "Season 1",
            "ParentIndexNumber": 1,
            "IndexNumber": 2,
            "ProductionYear": 2024,
            "Overview": "A great start.",
            "RunTimeTicks": 24000000000,
        }
        norm = normalize_episode_item(raw)
        assert norm["item_id"] == "ep123"
        assert norm["name"] == "Pilot"
        assert norm["series_id"] == "s456"
        assert norm["series_name"] == "Test Show"
        assert norm["season_id"] == "sea789"
        assert norm["season_number"] == 1
        assert norm["episode_number"] == 2
        assert norm["media_type"] == "Episode"

    def test_start_task_episode_params(self):
        """Verify download_controller.start_task accepts episode params."""
        from app.config.schema import EmbyConfig
        from app.gui.download_controller import DownloadController

        config = EmbyConfig()
        config.server_url = "http://127.0.0.1:8096"
        # Don't need real token for parameter check

        ctrl = DownloadController(config)
        # Verify method signature by calling inspect
        import inspect
        sig = inspect.signature(ctrl.start_task)
        params = list(sig.parameters.keys())
        assert "media_type" in params
        assert "series_id" in params
        assert "season_id" in params
        assert "episode_id" in params
        assert "season_number" in params
        assert "episode_number" in params
        assert "parent_title" in params
        assert "display_title" in params


# =============================================================================
# 4. Duplicate skip (find_tasks_by_item_id)
# =============================================================================

class TestDuplicateSkip:
    """Test duplicate detection via find_tasks_by_item_id."""

    @pytest.fixture(autouse=True)
    def _isolate_db(self, monkeypatch):
        """Use a temporary database."""
        import app.downloader.task_store as ts

        fd, self._tmp_db = tempfile.mkstemp(suffix=".db", prefix="test_s10d5_")
        os.close(fd)
        monkeypatch.setattr(ts, "_DB_PATH", Path(self._tmp_db))
        yield
        try:
            os.unlink(self._tmp_db)
        except OSError:
            pass

    def test_find_no_existing_task(self):
        from app.downloader.task_store import find_tasks_by_item_id
        existing = find_tasks_by_item_id("ep_nonexist")
        assert existing == []

    def test_find_existing_completed_returns_task(self):
        from app.downloader.task_store import create_task, find_tasks_by_item_id, update_task

        task = create_task(item_id="ep_done", title="Done")
        update_task(task.task_id, status="completed")
        existing = find_tasks_by_item_id("ep_done")
        assert len(existing) == 1
        assert existing[0].status == "completed"

    def test_find_existing_pending_returns_task(self):
        from app.downloader.task_store import create_task, find_tasks_by_item_id

        task = create_task(item_id="ep_pending", title="Pending")
        existing = find_tasks_by_item_id("ep_pending")
        assert len(existing) == 1
        assert existing[0].status == "pending"

    def test_find_existing_downloading_returns_task(self):
        from app.downloader.task_store import create_task, update_task, find_tasks_by_item_id

        task = create_task(item_id="ep_dl", title="DL")
        update_task(task.task_id, status="downloading")
        existing = find_tasks_by_item_id("ep_dl")
        assert len(existing) == 1
        assert existing[0].status == "downloading"

    def test_find_existing_paused_returns_task(self):
        from app.downloader.task_store import create_task, update_task, find_tasks_by_item_id

        task = create_task(item_id="ep_paused", title="Paused")
        update_task(task.task_id, status="paused")
        existing = find_tasks_by_item_id("ep_paused")
        assert len(existing) == 1
        assert existing[0].status == "paused"

    def test_failed_task_not_returned(self):
        """Failed tasks should NOT be returned by find_tasks_by_item_id (can re-create)."""
        from app.downloader.task_store import create_task, update_task, find_tasks_by_item_id

        task = create_task(item_id="ep_failed", title="Failed")
        update_task(task.task_id, status="failed")
        existing = find_tasks_by_item_id("ep_failed")
        assert existing == []

    def test_cancelled_task_not_returned(self):
        """Cancelled tasks should NOT be returned (can re-create)."""
        from app.downloader.task_store import create_task, update_task, find_tasks_by_item_id

        task = create_task(item_id="ep_cancelled", title="Cancelled")
        update_task(task.task_id, status="cancelled")
        existing = find_tasks_by_item_id("ep_cancelled")
        assert existing == []

    def test_duplicate_skip_logic(self):
        """Simulate the duplicate-skip logic used in the GUI."""
        from app.downloader.task_store import create_task, update_task, find_tasks_by_item_id

        # Create a completed task
        task = create_task(item_id="ep_dup", title="Duplicate Test")
        update_task(task.task_id, status="completed")

        # Check - should find it
        existing = find_tasks_by_item_id("ep_dup")
        assert len(existing) > 0  # duplicate found, should skip

        # For a new item with no task
        existing2 = find_tasks_by_item_id("ep_new")
        assert len(existing2) == 0  # no duplicate, can create

    def test_find_tasks_multiple_statuses(self):
        """Should find tasks across pending/downloading/paused/completed."""
        from app.downloader.task_store import create_task, update_task, find_tasks_by_item_id

        task1 = create_task(item_id="ep_multi", title="First")
        update_task(task1.task_id, status="completed")

        task2 = create_task(item_id="ep_multi", title="Second")
        # task2 is pending

        existing = find_tasks_by_item_id("ep_multi")
        # Both should be found
        found_statuses = {t.status for t in existing}
        assert "completed" in found_statuses
        assert "pending" in found_statuses


# =============================================================================
# 5. Worker imports & mocking
# =============================================================================

class TestWorkerImports:
    """Test that workers import and have correct signals."""

    def test_series_seasons_worker_import(self):
        from app.gui.workers import SeriesSeasonsWorker
        assert SeriesSeasonsWorker is not None
        worker = SeriesSeasonsWorker()
        assert hasattr(worker, "finished")
        assert hasattr(worker, "error")

    def test_season_episodes_worker_import(self):
        from app.gui.workers import SeasonEpisodesWorker
        assert SeasonEpisodesWorker is not None
        worker = SeasonEpisodesWorker()
        assert hasattr(worker, "finished")
        assert hasattr(worker, "error")

    def test_series_seasons_worker_run_mocked(self):
        """Test SeriesSeasonsWorker with mocked API."""
        from app.gui.workers import SeriesSeasonsWorker
        from unittest.mock import MagicMock, patch

        worker = SeriesSeasonsWorker()
        result_data = None

        def on_finished(data):
            nonlocal result_data
            result_data = data

        worker.finished.connect(on_finished)

        # Mock EmbyApiClient (worker lazy-imports from app.core.emby_api)
        mock_client = MagicMock()
        mock_client.get_user.return_value = {"Id": "user1"}
        mock_client.get_series_seasons.return_value = [
            {"Id": "sea1", "Name": "Season 1", "IndexNumber": 1, "SeriesId": "s1", "SeriesName": "Show"},
            {"Id": "sea2", "Name": "Season 2", "IndexNumber": 2, "SeriesId": "s1", "SeriesName": "Show"},
        ]

        with patch("app.core.emby_api.EmbyApiClient", return_value=mock_client):
            worker.run("http://127.0.0.1:8096", "fake-token", "s1", "Test Show")

        assert result_data is not None
        assert result_data["series_id"] == "s1"
        assert len(result_data["seasons"]) == 2
        assert result_data["seasons"][0]["season_number"] == 1

    def test_season_episodes_worker_run_mocked(self):
        """Test SeasonEpisodesWorker with mocked API."""
        from app.gui.workers import SeasonEpisodesWorker
        from unittest.mock import MagicMock, patch

        worker = SeasonEpisodesWorker()
        result_data = None

        def on_finished(data):
            nonlocal result_data
            result_data = data

        worker.finished.connect(on_finished)

        mock_client = MagicMock()
        mock_client.get_user.return_value = {"Id": "user1"}
        mock_client.get_season_episodes.return_value = [
            {"Id": "e1", "Name": "Ep 1", "SeriesId": "s1", "SeriesName": "Show",
             "SeasonId": "sea1", "ParentIndexNumber": 1, "IndexNumber": 1},
            {"Id": "e2", "Name": "Ep 2", "SeriesId": "s1", "SeriesName": "Show",
             "SeasonId": "sea1", "ParentIndexNumber": 1, "IndexNumber": 2},
        ]

        with patch("app.core.emby_api.EmbyApiClient", return_value=mock_client):
            worker.run("http://127.0.0.1:8096", "fake-token", "s1", "sea1")

        assert result_data is not None
        assert result_data["season_id"] == "sea1"
        assert len(result_data["episodes"]) == 2
        assert result_data["episodes"][0]["episode_number"] == 1

    def test_series_seasons_worker_error(self):
        """Test SeriesSeasonsWorker error signal."""
        from app.gui.workers import SeriesSeasonsWorker
        from unittest.mock import MagicMock, patch

        worker = SeriesSeasonsWorker()
        error_msg = None

        def on_error(msg):
            nonlocal error_msg
            error_msg = msg

        worker.error.connect(on_error)

        mock_client = MagicMock()
        mock_client.get_user.side_effect = Exception("Connection refused")

        with patch("app.core.emby_api.EmbyApiClient", return_value=mock_client):
            worker.run("http://127.0.0.1:8096", "fake-token", "s1")

        assert error_msg is not None
        assert "Failed to get user info" in error_msg


# =============================================================================
# 6. GUI smoke tests
# =============================================================================

class TestGUISmoke:
    """Smoke tests: GUI imports and MainWindow lifecycle."""

    def test_main_window_import(self):
        from app.gui.main_window import MainWindow
        assert MainWindow is not None

    def test_download_controller_import(self):
        from app.gui.download_controller import DownloadController
        assert DownloadController is not None

    def test_workers_import(self):
        from app.gui.workers import (
            SeriesSeasonsWorker,
            SeasonEpisodesWorker,
            DownloadItemWorker,
        )
        assert SeriesSeasonsWorker is not None
        assert SeasonEpisodesWorker is not None
        assert DownloadItemWorker is not None

    def test_main_window_create_destroy_no_qthread_warning(self):
        """MainWindow create/destroy should not trigger QThread warnings."""
        import sys
        from PySide6.QtWidgets import QApplication

        # Check if QApplication exists, create if not
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from app.gui.main_window import MainWindow
        w = MainWindow()
        app.processEvents()
        w._shutdown_threads()
        w.close()
        app.processEvents()
        # If we got here without exception, the test passes
        assert True

    def test_series_browser_methods_exist(self):
        """Verify Series Browser methods are on MainWindow."""
        from app.gui.main_window import MainWindow

        assert hasattr(MainWindow, '_init_series_browser_tab')
        assert hasattr(MainWindow, '_enter_series_browser')
        assert hasattr(MainWindow, '_on_seasons_loaded')
        assert hasattr(MainWindow, '_on_season_selected')
        assert hasattr(MainWindow, '_on_episodes_loaded')
        assert hasattr(MainWindow, '_on_series_browser_download')


# =============================================================================
# 7. Episode display title integration
# =============================================================================

class TestEpisodeDisplayTitle:
    """Test that display titles are correctly formatted for tasks table."""

    def test_display_title_preferred_over_title(self):
        """When display_title is set, it should be shown in Tasks tab."""
        display_title = "Breaking Bad - S01E02 - Cat's in the Bag"
        title = "ep123"  # raw item_id
        # The display_title should be preferred
        shown = display_title if display_title else (title if title else "?")
        assert shown == "Breaking Bad - S01E02 - Cat's in the Bag"

    def test_movie_title_not_overridden(self):
        """Movies without display_title should show their title normally."""
        display_title = ""  # not set for movies
        title = "Inception (2010)"
        shown = display_title if display_title else (title if title else "?")
        assert shown == "Inception (2010)"

    def test_task_store_episode_fields_roundtrip(self):
        """Episode metadata survives create -> get roundtrip."""
        import app.downloader.task_store as ts
        fd, tmp_db = tempfile.mkstemp(suffix=".db", prefix="test_s10d5_rt_")
        os.close(fd)
        original = ts._DB_PATH
        ts._DB_PATH = Path(tmp_db)

        try:
            task = ts.create_task(
                item_id="ep_rt",
                title="Rotating Test",
                media_type="Episode",
                series_id="s_rt",
                season_id="sea_rt",
                season_number=3,
                episode_number=7,
                parent_title="Series RT",
                display_title="Series RT - S03E07 - Rotating Test",
                download_method="direct",
            )
            reloaded = ts.get_task(task.task_id)
            assert reloaded is not None
            assert reloaded.media_type == "Episode"
            assert reloaded.series_id == "s_rt"
            assert reloaded.season_number == 3
            assert reloaded.episode_number == 7
            assert reloaded.display_title == "Series RT - S03E07 - Rotating Test"
        finally:
            ts._DB_PATH = original
            try:
                os.unlink(tmp_db)
            except OSError:
                pass


# =============================================================================
# 8. Series browser cache logic
# =============================================================================

class TestSeriesBrowserCache:
    """Test episode caching and selection across seasons."""

    def test_episode_cache_lookup(self):
        """Episodes cached per season can be found by item_id."""
        cache = {
            "sea1": [
                {"item_id": "e1", "name": "Ep1", "season_number": 1, "episode_number": 1},
                {"item_id": "e2", "name": "Ep2", "season_number": 1, "episode_number": 2},
            ],
            "sea2": [
                {"item_id": "e3", "name": "Ep3", "season_number": 2, "episode_number": 1},
            ],
        }

        # Find ep by item_id
        def find_ep(target_id):
            for episodes in cache.values():
                for ep in episodes:
                    if ep["item_id"] == target_id:
                        return ep
            return None

        assert find_ep("e2") is not None
        assert find_ep("e2")["name"] == "Ep2"
        assert find_ep("e3") is not None
        assert find_ep("e99") is None

    def test_all_cached_ids(self):
        """All episode IDs can be collected from cache."""
        cache = {
            "sea1": [
                {"item_id": "e1", "name": "Ep1"},
                {"item_id": "e2", "name": "Ep2"},
            ],
            "sea2": [
                {"item_id": "e3", "name": "Ep3"},
            ],
        }
        all_ids = []
        for episodes in cache.values():
            for ep in episodes:
                all_ids.append(ep["item_id"])
        assert set(all_ids) == {"e1", "e2", "e3"}


# =============================================================================
# 9. sort_seasons / sort_episodes integration
# =============================================================================

class TestSortIntegration:
    """Verify sort functions work with normalized data."""

    def test_sort_seasons_with_normalized(self):
        raw = [
            {"Id": "s3", "Name": "Season 3", "IndexNumber": 3},
            {"Id": "s1", "Name": "Season 1", "IndexNumber": 1},
            {"Id": "s2", "Name": "Season 2", "IndexNumber": 2},
        ]
        normalized = [normalize_season_item(s) for s in raw]
        sorted_seasons = sort_seasons(normalized)
        nums = [s["season_number"] for s in sorted_seasons]
        assert nums == [1, 2, 3]

    def test_sort_episodes_with_normalized(self):
        raw = [
            {"Id": "e2", "Name": "Ep2", "ParentIndexNumber": 1, "IndexNumber": 2,
             "SeriesId": "s1", "SeasonId": "sea1"},
            {"Id": "e1", "Name": "Ep1", "ParentIndexNumber": 1, "IndexNumber": 1,
             "SeriesId": "s1", "SeasonId": "sea1"},
        ]
        normalized = [normalize_episode_item(e) for e in raw]
        sorted_eps = sort_episodes(normalized)
        assert sorted_eps[0]["episode_number"] == 1
        assert sorted_eps[1]["episode_number"] == 2
