"""
Stage 4 verification tests.
"""
import sys, os, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.playback_info import parse_media_sources, select_best_source, format_size
from app.core.download_capability import check_download_capability, DownloadMethod, get_method_label, get_method_icon
from app.core.emby_api import EmbyApiClient

def test_parse_media_sources():
    playback_info = {
        "MediaSources": [
            {"Id": "ms-1", "Container": "mkv", "Size": 1000, "Path": "/media/1.mkv"},
        ]
    }
    result = parse_media_sources(playback_info)
    assert len(result) == 1
    assert result[0].id == "ms-1"
    print("[OK] Parsed media sources correctly")

def test_parse_media_sources_empty():
    result = parse_media_sources({})
    assert result == []
    print("[OK] Empty media sources returns empty list")

def test_parse_media_sources_missing_fields():
    playback_info = {"MediaSources": [{"Id": "ms-1"}, {}]}
    result = parse_media_sources(playback_info)
    assert len(result) == 2
    assert result[0].id == "ms-1"
    print("[OK] Missing fields handled")

def test_select_best_source():
    playback_info = {"MediaSources": [{"Id": "ms-1", "Size": 1000}, {"Id": "ms-2", "Size": 2000}]}
    sources = parse_media_sources(playback_info)
    best = select_best_source(sources)
    assert best is not None
    assert best.id in ("ms-1", "ms-2")
    print("[OK] select_best_source returns a valid source")

def test_select_best_source_empty():
    best = select_best_source([])
    assert best is None
    print("[OK] select_best_source returns None for empty list")

def test_format_size():
    assert "1.0 GB" in format_size(1073741824)
    print("[OK] format_size works")

def test_download_method_enum():
    assert DownloadMethod.DIRECT.value == "direct"
    assert DownloadMethod.STREAM.value == "stream"
    assert DownloadMethod.NONE.value == "none"
    print("[OK] DownloadMethod enum works")

def test_get_method_icon():
    assert isinstance(get_method_icon("direct"), str)
    print("[OK] get_method_icon returns strings")

def test_get_method_label():
    assert len(get_method_label("direct")) > 0
    print("[OK] get_method_label returns non-empty string")

def test_download_capability_check():
    client = EmbyApiClient("http://test:8096")
    result = check_download_capability(client, "item-1")
    assert result is not None
    print("[OK] download_capability called without permission returns result")

@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_cmd_info_without_login():
    pass

@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_cli_info_help():
    pass

def test_import_all():
    from app.core import playback_info, download_capability
    assert playback_info is not None
    print("[OK] All key Stage 4 modules importable")
