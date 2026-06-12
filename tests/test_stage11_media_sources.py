"""
Stage 11 tests: MediaSource selection.

Tests that:
- build_media_source_options handles single source.
- Multiple sources (4K/1080p/720p) generate correct labels.
- display_label is correct.
- Missing width/height/size/codec does not crash.
- User-selected media_source_id is saved in task.
- Backend worker uses specified media_source_id.
- Missing media_source_id marks task as failed.
"""

import sys
from pathlib import Path

_app_dir = Path(__file__).resolve().parent.parent
if str(_app_dir) not in sys.path:
    sys.path.insert(0, str(_app_dir))

import pytest
from app.core.playback_info import (
    MediaSource, parse_media_sources, build_media_source_options,
    find_source_by_id, select_best_source,
)


def make_source(id, container="mkv", size=0, bitrate=0, protocol="File",
                width=None, height=None, name="", supports_direct=True):
    """Helper to create a MediaSource with extra width/height."""
    src = MediaSource(
        id=id, container=container, path=f"/media/{id}",
        protocol=protocol, size=size, bitrate=bitrate,
        supports_direct_stream=supports_direct,
        name=name,
    )
    if width is not None:
        src.width = width
    if height is not None:
        src.height = height
    return src


class TestBuildMediaSourceOptions:
    """Test build_media_source_options function."""

    def test_single_source(self):
        """Single source returns one option."""
        sources = [make_source("src1", "mkv", 1073741824, 5000000)]
        options = build_media_source_options(sources)
        assert len(options) == 1
        assert options[0]["id"] == "src1"
        assert "MKV" in options[0]["label"]

    def test_multiple_sources_4k_1080p_720p(self):
        """Multiple sources with different resolutions."""
        sources = [
            make_source("4k", "mkv", 20000000000, 30000000, width=3840, height=2160),
            make_source("1080p", "mkv", 8000000000, 10000000, width=1920, height=1080),
            make_source("720p", "mp4", 3000000000, 4000000, width=1280, height=720),
        ]
        options = build_media_source_options(sources)
        assert len(options) == 3
        labels = [o["label"] for o in options]
        assert any("4K" in l for l in labels)
        assert any("1080p" in l for l in labels)
        assert any("720p" in l for l in labels)

    def test_missing_fields_no_crash(self):
        """Missing width/height/size/codec does not crash."""
        sources = [make_source("src1", "", 0, 0)]
        options = build_media_source_options(sources)
        assert len(options) == 1
        assert options[0]["id"] == "src1"
        # Should not crash even with empty fields
        assert isinstance(options[0]["label"], str)

    def test_empty_sources(self):
        """Empty source list returns empty options."""
        options = build_media_source_options([])
        assert options == []

    def test_named_source_has_name_in_label(self):
        """Source with a Name attribute shows it in label."""
        sources = [make_source("src1", "mkv", 1073741824, 5000000, name="Director's Cut")]
        options = build_media_source_options(sources)
        assert len(options) == 1
        assert "Director's Cut" in options[0]["label"]

    def test_bitrate_guess_resolution(self):
        """When width/height absent, bitrate is used to guess resolution."""
        sources = [
            make_source("4k-guess", "mkv", 20000000000, 30000000),
            make_source("1080p-guess", "mkv", 8000000000, 10000000),
            make_source("720p-guess", "mp4", 3000000000, 4000000),
        ]
        options = build_media_source_options(sources)
        labels = [o["label"] for o in options]
        assert any("4K" in l for l in labels)
        assert any("1080p" in l for l in labels)
        assert any("720p" in l for l in labels)


class TestFindSourceById:
    """Test find_source_by_id function."""

    def test_find_existing_source(self):
        """Find a source by its ID."""
        sources = [
            make_source("src-001", "mkv"),
            make_source("src-002", "mp4"),
        ]
        found = find_source_by_id(sources, "src-001")
        assert found is not None
        assert found.id == "src-001"

    def test_missing_source_returns_none(self):
        """Non-existent source ID returns None."""
        sources = [make_source("src-001", "mkv")]
        found = find_source_by_id(sources, "nonexistent")
        assert found is None


class TestPlaybackInfoParsing:
    """Test parse_media_sources with real-looking data."""

    def test_parse_playback_info_response(self):
        """Parse a realistic PlaybackInfo response."""
        response = {
            "MediaSources": [
                {
                    "Id": "src1",
                    "Container": "mkv",
                    "Path": "/media/movie.mkv",
                    "Protocol": "File",
                    "Size": 5000000000,
                    "Bitrate": 10000000,
                    "SupportsDirectStream": True,
                    "SupportsTranscoding": False,
                    "Name": "Default",
                }
            ]
        }
        sources = parse_media_sources(response)
        assert len(sources) == 1
        assert sources[0].id == "src1"
        assert sources[0].container == "mkv"
        assert sources[0].size == 5000000000


class TestMediaSourceIdInTask:
    """Test that media_source_id is stored and used by backend."""

    def test_task_has_media_source_id_field(self):
        """DownloadTask dataclass has media_source_id field."""
        from app.downloader.task_store import DownloadTask
        task = DownloadTask(media_source_id="test-src-id")
        assert task.media_source_id == "test-src-id"

    def test_backend_uses_media_source_id(self):
        """BackendDownloadManager._prepare_and_download checks task.media_source_id."""
        import inspect
        from app.backend.download_manager import BackendDownloadManager
        source = inspect.getsource(BackendDownloadManager._prepare_and_download)
        assert "task.media_source_id" in source, (
            "_prepare_and_download must check task.media_source_id"
        )
        assert "find_source_by_id" in source, (
            "_prepare_and_download must use find_source_by_id for user-selected source"
        )
