"""
Stage 10D-4 tests: Series / Season / Episode API & task metadata.

Tests:
1. build_episode_filename
2. normalize_episode_item / normalize_season_item / normalize_series_item
3. sort_seasons
4. sort_episodes
5. task_store migration & episode fields
6. EmbyApiClient series/season/episode methods (mocked)
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.naming import build_episode_filename, sanitize_filename
from app.core.series import (
    normalize_series_item,
    normalize_season_item,
    normalize_episode_item,
    sort_seasons,
    sort_episodes,
    _safe_int,
)


# =============================================================================
# _safe_int
# =============================================================================

class TestSafeInt:
    def test_normal_int(self):
        assert _safe_int(5) == 5
        assert _safe_int("3") == 3

    def test_none_returns_default(self):
        assert _safe_int(None) == 0
        assert _safe_int(None, -1) == -1

    def test_invalid_returns_default(self):
        assert _safe_int("abc") == 0
        assert _safe_int({}) == 0


# =============================================================================
# build_episode_filename
# =============================================================================

class TestBuildEpisodeFilename:
    def test_normal_s01e02(self):
        result = build_episode_filename(
            "Breaking Bad", 1, 2, "Cat's in the Bag", "mkv"
        )
        assert result == "Breaking Bad - S01E02 - Cat's in the Bag.mkv"

    def test_season_zero_specials(self):
        result = build_episode_filename(
            "Doctor Who", 0, 1, "The Christmas Invasion", "mkv"
        )
        assert result == "Doctor Who - S00E01 - The Christmas Invasion.mkv"

    def test_illegal_chars_cleaned(self):
        result = build_episode_filename(
            'Star Trek: Voyager', 3, 5, 'Episode "Q" <test>', "mkv"
        )
        # : " < > should be replaced
        assert ":" not in result
        assert '"' not in result
        assert "<" not in result
        assert ">" not in result
        assert result.startswith("Star Trek")

    def test_extension_with_dot(self):
        result = build_episode_filename("Test", 1, 1, "Pilot", ".mkv")
        assert result == "Test - S01E01 - Pilot.mkv"

    def test_extension_without_dot(self):
        result = build_episode_filename("Test", 1, 1, "Pilot", "mp4")
        assert result == "Test - S01E01 - Pilot.mp4"

    def test_missing_episode_title(self):
        result = build_episode_filename("Test", 2, 3, "", "mkv")
        assert result == "Test - S02E03.mkv"

    def test_none_episode_title(self):
        result = build_episode_filename("Test", 2, 3, None, "mkv")
        assert result == "Test - S02E03.mkv"

    def test_missing_series_name(self):
        result = build_episode_filename("", 1, 1, "Pilot", "mkv")
        assert result == "Unknown Series - S01E01 - Pilot.mkv"

    def test_zero_episode_number(self):
        result = build_episode_filename("Show", 1, 0, "Special", "mkv")
        assert result == "Show - S01E00 - Special.mkv"

    def test_none_season_episode(self):
        result = build_episode_filename("Show", None, None, "Pilot", "mkv")
        assert result == "Show - S00E00 - Pilot.mkv"

    def test_negative_numbers(self):
        result = build_episode_filename("Show", -1, -5, "Bad Data", "mkv")
        assert "S00E00" in result  # clamped to 0


# =============================================================================
# normalize_episode_item
# =============================================================================

class TestNormalizeEpisodeItem:
    def test_normal_episode(self):
        item = {
            "Id": "ep123",
            "Name": "Pilot",
            "SeriesId": "s456",
            "SeriesName": "Test Show",
            "SeasonId": "sea789",
            "SeasonName": "Season 1",
            "ParentIndexNumber": 1,
            "IndexNumber": 1,
            "ProductionYear": 2024,
            "Overview": "A great start.",
            "RunTimeTicks": 24000000000,
        }
        result = normalize_episode_item(item)
        assert result["item_id"] == "ep123"
        assert result["name"] == "Pilot"
        assert result["series_id"] == "s456"
        assert result["series_name"] == "Test Show"
        assert result["season_id"] == "sea789"
        assert result["season_name"] == "Season 1"
        assert result["season_number"] == 1
        assert result["episode_number"] == 1
        assert result["production_year"] == 2024
        assert result["overview"] == "A great start."
        assert result["runtime_ticks"] == 24000000000
        assert result["media_type"] == "Episode"

    def test_missing_season_number(self):
        item = {"Id": "ep1", "Name": "Ep", "IndexNumber": 3}
        result = normalize_episode_item(item)
        assert result["season_number"] == 0

    def test_missing_episode_number(self):
        item = {"Id": "ep1", "Name": "Ep", "ParentIndexNumber": 2}
        result = normalize_episode_item(item)
        assert result["episode_number"] == 0

    def test_missing_series_name(self):
        item = {"Id": "ep1", "Name": "Ep"}
        result = normalize_episode_item(item)
        assert result["series_name"] == ""

    def test_series_name_fallback_to_series(self):
        item = {"Id": "ep1", "Name": "Ep", "Series": "Fallback Show"}
        result = normalize_episode_item(item)
        assert result["series_name"] == "Fallback Show"

    def test_season_zero(self):
        item = {
            "Id": "ep0",
            "Name": "Special Ep",
            "ParentIndexNumber": 0,
            "IndexNumber": 1,
        }
        result = normalize_episode_item(item)
        assert result["season_number"] == 0
        assert result["episode_number"] == 1

    def test_empty_item(self):
        result = normalize_episode_item({})
        assert result["item_id"] == ""
        assert result["name"] == "Unknown Episode"
        assert result["media_type"] == "Episode"

    def test_none_values(self):
        item = {
            "Id": None,
            "Name": None,
            "ParentIndexNumber": None,
            "IndexNumber": None,
        }
        result = normalize_episode_item(item)
        assert result["item_id"] == ""
        assert result["name"] == "Unknown Episode"
        assert result["season_number"] == 0
        assert result["episode_number"] == 0


# =============================================================================
# normalize_season_item
# =============================================================================

class TestNormalizeSeasonItem:
    def test_normal_season(self):
        item = {
            "Id": "sea1",
            "Name": "Season 1",
            "SeriesId": "s1",
            "SeriesName": "Show",
            "IndexNumber": 1,
        }
        result = normalize_season_item(item)
        assert result["item_id"] == "sea1"
        assert result["name"] == "Season 1"
        assert result["season_number"] == 1
        assert result["media_type"] == "Season"

    def test_missing_name(self):
        result = normalize_season_item({})
        assert result["name"] == "Unknown Season"


# =============================================================================
# normalize_series_item
# =============================================================================

class TestNormalizeSeriesItem:
    def test_normal_series(self):
        item = {
            "Id": "s1",
            "Name": "Test Show",
            "ProductionYear": 2023,
            "Overview": "A test show.",
        }
        result = normalize_series_item(item)
        assert result["item_id"] == "s1"
        assert result["name"] == "Test Show"
        assert result["production_year"] == 2023
        assert result["media_type"] == "Series"

    def test_missing_fields(self):
        result = normalize_series_item({})
        assert result["name"] == "Unknown Series"
        assert result["production_year"] is None


# =============================================================================
# sort_seasons
# =============================================================================

class TestSortSeasons:
    def test_multi_season_sort(self):
        seasons = [
            {"season_number": 3},
            {"season_number": 1},
            {"season_number": 2},
        ]
        result = sort_seasons(seasons)
        assert [s["season_number"] for s in result] == [1, 2, 3]

    def test_season_zero_first(self):
        seasons = [
            {"season_number": 2},
            {"season_number": 0},
            {"season_number": 1},
        ]
        result = sort_seasons(seasons)
        assert [s["season_number"] for s in result] == [0, 1, 2]

    def test_missing_index_number_last(self):
        seasons = [
            {"season_number": 2},
            {"season_number": None},
            {"season_number": 1},
            {},
        ]
        result = sort_seasons(seasons)
        nums = [s.get("season_number") for s in result]
        # None values should sort last
        assert nums[:2] == [1, 2]
        assert nums[2] is None
        assert nums[3] is None

    def test_empty_list(self):
        assert sort_seasons([]) == []

    def test_single_season(self):
        seasons = [{"season_number": 5}]
        result = sort_seasons(seasons)
        assert result[0]["season_number"] == 5


# =============================================================================
# sort_episodes
# =============================================================================

class TestSortEpisodes:
    def test_same_season_sort_by_episode(self):
        episodes = [
            {"season_number": 1, "episode_number": 3},
            {"season_number": 1, "episode_number": 1},
            {"season_number": 1, "episode_number": 2},
        ]
        result = sort_episodes(episodes)
        assert [(e["season_number"], e["episode_number"]) for e in result] == [
            (1, 1), (1, 2), (1, 3),
        ]

    def test_multi_season_sort(self):
        episodes = [
            {"season_number": 2, "episode_number": 1},
            {"season_number": 1, "episode_number": 2},
            {"season_number": 1, "episode_number": 1},
        ]
        result = sort_episodes(episodes)
        assert [(e["season_number"], e["episode_number"]) for e in result] == [
            (1, 1), (1, 2), (2, 1),
        ]

    def test_missing_episode_number_last(self):
        episodes = [
            {"season_number": 1, "episode_number": 2},
            {"season_number": 1, "episode_number": None},
            {"season_number": 1, "episode_number": 1},
        ]
        result = sort_episodes(episodes)
        nums = [(e["season_number"], e["episode_number"]) for e in result]
        assert nums == [(1, 1), (1, 2), (1, None)]

    def test_missing_season_number_last(self):
        episodes = [
            {"season_number": None, "episode_number": 1},
            {"season_number": 1, "episode_number": 1},
        ]
        result = sort_episodes(episodes)
        assert result[0]["season_number"] == 1
        assert result[1]["season_number"] is None

    def test_empty_list(self):
        assert sort_episodes([]) == []

    def test_season_zero_episodes(self):
        episodes = [
            {"season_number": 1, "episode_number": 1},
            {"season_number": 0, "episode_number": 2},
            {"season_number": 0, "episode_number": 1},
        ]
        result = sort_episodes(episodes)
        assert [(e["season_number"], e["episode_number"]) for e in result] == [
            (0, 1), (0, 2), (1, 1),
        ]


# =============================================================================
# task_store migration & episode fields
# =============================================================================

class TestTaskStoreEpisodeFields:
    """Test task_store handles episode metadata without breaking old DB."""

    @pytest.fixture(autouse=True)
    def _isolate_db(self, monkeypatch):
        """Use a temporary database so production tasks.db is untouched."""
        import app.downloader.task_store as ts

        fd, self._tmp_db = tempfile.mkstemp(suffix=".db", prefix="test_s10d4_")
        os.close(fd)
        monkeypatch.setattr(ts, "_DB_PATH", Path(self._tmp_db))

        # Clear any cached connection state
        yield

        # Cleanup
        try:
            os.unlink(self._tmp_db)
        except OSError:
            pass

    def test_old_schema_gets_new_columns(self):
        """Simulate an old tasks.db without episode columns."""
        import sqlite3
        from app.downloader.task_store import _init_db

        # Create an old-style schema manually
        conn = sqlite3.connect(str(self._tmp_db))
        conn.execute("""
            CREATE TABLE tasks (
                task_id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                download_url TEXT NOT NULL DEFAULT '',
                save_path TEXT NOT NULL DEFAULT '',
                temp_path TEXT NOT NULL DEFAULT '',
                total_bytes INTEGER NOT NULL DEFAULT 0,
                downloaded_bytes INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT NOT NULL DEFAULT '',
                media_source_id TEXT NOT NULL DEFAULT '',
                container TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

        # Run _init_db which should migrate
        _init_db()

        # Verify new columns exist
        conn = sqlite3.connect(str(self._tmp_db))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        for c in ("media_type", "series_id", "season_id", "episode_id",
                  "season_number", "episode_number", "parent_title",
                  "display_title", "download_method"):
            assert c in cols, f"Column {c} missing after migration"
        conn.close()

    def test_create_task_with_episode_metadata(self):
        from app.downloader.task_store import create_task, get_task

        task = create_task(
            item_id="ep001",
            title="Pilot",
            media_type="Episode",
            series_id="s1",
            season_id="sea1",
            episode_id="ep001",
            season_number=1,
            episode_number=2,
            parent_title="Test Show",
            display_title="Test Show - S01E02 - Pilot",
            download_method="direct",
        )
        assert task.media_type == "Episode"
        assert task.series_id == "s1"
        assert task.season_id == "sea1"
        assert task.episode_id == "ep001"
        assert task.season_number == 1
        assert task.episode_number == 2
        assert task.parent_title == "Test Show"
        assert task.display_title == "Test Show - S01E02 - Pilot"
        assert task.download_method == "direct"

        # Re-read from DB
        reloaded = get_task(task.task_id)
        assert reloaded is not None
        assert reloaded.media_type == "Episode"
        assert reloaded.series_id == "s1"
        assert reloaded.season_number == 1
        assert reloaded.episode_number == 2

    def test_row_to_task_reads_episode_metadata(self):
        from app.downloader.task_store import create_task, _row_to_task
        import sqlite3

        task = create_task(
            item_id="ep002",
            title="Episode 2",
            media_type="Episode",
            series_id="s2",
            season_id="sea2",
            season_number=2,
            episode_number=5,
            parent_title="Show 2",
        )

        conn = sqlite3.connect(str(self._tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task.task_id,)
        ).fetchone()
        conn.close()

        parsed = _row_to_task(row)
        assert parsed.media_type == "Episode"
        assert parsed.series_id == "s2"
        assert parsed.season_number == 2
        assert parsed.episode_number == 5
        assert parsed.parent_title == "Show 2"

    def test_old_task_row_does_not_crash(self):
        """Reading an old-style row (without episode columns) should not crash."""
        import sqlite3
        from app.downloader.task_store import _init_db, _row_to_task

        # Build an old-style row first, then migrate
        conn = sqlite3.connect(str(self._tmp_db))
        conn.execute("""
            CREATE TABLE tasks (
                task_id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                download_url TEXT NOT NULL DEFAULT '',
                save_path TEXT NOT NULL DEFAULT '',
                temp_path TEXT NOT NULL DEFAULT '',
                total_bytes INTEGER NOT NULL DEFAULT 0,
                downloaded_bytes INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT NOT NULL DEFAULT '',
                media_source_id TEXT NOT NULL DEFAULT '',
                container TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL DEFAULT 0
            )
        """)
        conn.execute(
            "INSERT INTO tasks (task_id, item_id, title, status) VALUES (?, ?, ?, ?)",
            ("old1", "movie1", "Old Movie", "completed"),
        )
        conn.commit()
        conn.close()

        # Migrate
        _init_db()

        # Read
        conn = sqlite3.connect(str(self._tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", ("old1",)).fetchone()
        conn.close()

        task = _row_to_task(row)
        assert task.task_id == "old1"
        assert task.title == "Old Movie"
        assert task.status == "completed"
        # New fields default safely
        assert task.media_type == ""
        assert task.series_id == ""
        assert task.season_number is None

    def test_update_task_with_episode_fields(self):
        from app.downloader.task_store import create_task, update_task, get_task

        task = create_task(item_id="ep003", title="Before")
        assert task.media_type == ""

        updated = update_task(
            task.task_id,
            media_type="Episode",
            series_id="s3",
            season_number=3,
            episode_number=7,
            parent_title="Series 3",
            display_title="Series 3 - S03E07 - Title",
            download_method="stream",
        )
        assert updated is not None
        assert updated.media_type == "Episode"
        assert updated.series_id == "s3"
        assert updated.season_number == 3
        assert updated.episode_number == 7
        assert updated.download_method == "stream"

        reloaded = get_task(task.task_id)
        assert reloaded.media_type == "Episode"

    def test_create_movie_task_unchanged(self):
        """Movie tasks (no episode metadata) still work."""
        from app.downloader.task_store import create_task, get_task

        task = create_task(
            item_id="movie1",
            title="Test Movie",
            media_source_id="ms1",
            container="mkv",
        )
        assert task.media_type == ""
        assert task.series_id == ""
        assert task.season_number is None

        reloaded = get_task(task.task_id)
        assert reloaded.title == "Test Movie"
        assert reloaded.media_source_id == "ms1"
        assert reloaded.container == "mkv"


# =============================================================================
# EmbyApiClient mocked series / season / episode methods
# =============================================================================

class TestEmbyApiSeriesMethods:
    """Mock-based tests for the three new Emby API methods."""

    def _make_client(self):
        from app.core.emby_api import EmbyApiClient
        return EmbyApiClient("http://127.0.0.1:8096", "fake-token")

    def test_get_series_seasons_returns_items(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Items": [
                {"Id": "s1", "Name": "Season 1", "IndexNumber": 1},
                {"Id": "s2", "Name": "Season 2", "IndexNumber": 2},
            ]
        }
        with patch.object(client, "_get", return_value=mock_response) as mock_get:
            result = client.get_series_seasons("show1", "user1")
            assert len(result) == 2
            assert result[0]["Name"] == "Season 1"
            mock_get.assert_called_once()

    def test_get_series_seasons_empty(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.json.return_value = {"Items": []}
        with patch.object(client, "_get", return_value=mock_response):
            result = client.get_series_seasons("show1", "user1")
            assert result == []

    def test_get_season_episodes_with_series_id(self):
        client = self._make_client()
        episodes = [
            {"Id": "e2", "IndexNumber": 2},
            {"Id": "e1", "IndexNumber": 1},
            {"Id": "e3", "IndexNumber": None},
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = {"Items": episodes}
        with patch.object(client, "_get", return_value=mock_response) as mock_get:
            result = client.get_season_episodes("sea1", "user1", series_id="show1")
            # Should be sorted by IndexNumber, None last
            assert result[0]["Id"] == "e1"
            assert result[1]["Id"] == "e2"
            assert result[2]["IndexNumber"] is None

    def test_get_season_episodes_without_series_id(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.json.return_value = {"Items": [{"Id": "e1"}]}
        with patch.object(client, "_get", return_value=mock_response) as mock_get:
            result = client.get_season_episodes("sea1", "user1")
            assert len(result) == 1
            # Verify fallback endpoint
            call_args = mock_get.call_args
            assert "ParentId" in str(call_args)

    def test_get_season_episodes_empty(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.json.return_value = {"Items": []}
        with patch.object(client, "_get", return_value=mock_response):
            result = client.get_season_episodes("sea1", "user1")
            assert result == []

    def test_get_series_episodes_all(self):
        client = self._make_client()
        episodes = [
            {"Id": "e1", "ParentIndexNumber": 1, "IndexNumber": 2},
            {"Id": "e2", "ParentIndexNumber": 1, "IndexNumber": 1},
            {"Id": "e3", "ParentIndexNumber": 2, "IndexNumber": 1},
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = {"Items": episodes}
        with patch.object(client, "_get", return_value=mock_response):
            result = client.get_series_episodes("show1", "user1")
            assert len(result) == 3
            # Sorted by ParentIndexNumber, IndexNumber
            assert result[0]["Id"] == "e2"  # S1E1
            assert result[1]["Id"] == "e1"  # S1E2
            assert result[2]["Id"] == "e3"  # S2E1

    def test_get_series_episodes_by_season(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Items": [{"Id": "e1", "IndexNumber": 1}]
        }
        with patch.object(client, "_get", return_value=mock_response):
            result = client.get_series_episodes("show1", "user1", season_id="sea1")
            assert len(result) == 1

    def test_get_series_episodes_empty(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.json.return_value = {"Items": []}
        with patch.object(client, "_get", return_value=mock_response):
            result = client.get_series_episodes("show1", "user1")
            assert result == []


# =============================================================================
# EmbyApiClient error paths
# =============================================================================

class TestEmbyApiSeriesErrors:
    """Test error handling in series/season/episode API methods."""

    def _make_client(self):
        from app.core.emby_api import EmbyApiClient
        return EmbyApiClient("http://127.0.0.1:8096", "fake-token")

    @staticmethod
    def _make_error(status_code):
        """Return an exception *instance* suitable for mock side_effect."""
        from app.core.emby_api import (
            EmbyAuthError,
            EmbyNotFoundError,
            EmbyServerError,
            EmbyApiError,
        )
        import requests
        resp = requests.Response()
        resp.status_code = status_code

        if status_code == 401:
            return EmbyAuthError("unauth", status_code=401, response=resp)
        elif status_code == 403:
            return EmbyAuthError("forbidden", status_code=403, response=resp)
        elif status_code == 404:
            return EmbyNotFoundError("not found", status_code=404, response=resp)
        elif status_code >= 500:
            return EmbyServerError("server error", status_code=500, response=resp)
        else:
            return EmbyApiError("other", status_code=status_code, response=resp)

    def test_get_series_seasons_404_raises(self):
        from app.core.emby_api import EmbyNotFoundError
        client = self._make_client()
        with patch.object(client, "_get", side_effect=self._make_error(404)):
            with pytest.raises(EmbyNotFoundError):
                client.get_series_seasons("bad_id", "user1")

    def test_get_series_seasons_403_raises(self):
        from app.core.emby_api import EmbyAuthError
        client = self._make_client()
        with patch.object(client, "_get", side_effect=self._make_error(403)):
            with pytest.raises(EmbyAuthError):
                client.get_series_seasons("bad_id", "user1")

    def test_get_season_episodes_401_raises(self):
        from app.core.emby_api import EmbyAuthError
        client = self._make_client()
        with patch.object(client, "_get", side_effect=self._make_error(401)):
            with pytest.raises(EmbyAuthError):
                client.get_season_episodes("s1", "user1")

    def test_get_series_episodes_500_raises(self):
        from app.core.emby_api import EmbyServerError
        client = self._make_client()
        with patch.object(client, "_get", side_effect=self._make_error(500)):
            with pytest.raises(EmbyServerError):
                client.get_series_episodes("s1", "user1")
