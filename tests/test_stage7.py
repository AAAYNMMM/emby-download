"""
Stage 7 verification tests.
"""
import sys, os, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.metadata.metadata import generate_nfo, format_runtime

def test_nfo_generation():
    nfo = generate_nfo({"Name": "Test Movie", "ProductionYear": 2024})
    assert "<title>Test Movie</title>" in nfo
    print("[OK] NFO generation works")

def test_format_runtime():
    result = format_runtime(121)
    assert isinstance(result, str)
    assert len(result) > 0
    print("[OK] format_runtime returns string for 121 min")

@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_cmd_download_without_login():
    pass

@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_cli_download_with_metadata_flags():
    pass

def test_subtitle_url():
    from app.core.emby_api import EmbyApiClient
    client = EmbyApiClient("http://server:8096", "test-token")
    url = client.get_subtitle_url("item-1", "ms-1", 0)
    assert "/Videos/item-1/ms-1/Subtitles/0/Stream" in url
    print("[OK] Subtitle URL construction works")

def test_subtitle_url_ass():
    from app.core.emby_api import EmbyApiClient
    client = EmbyApiClient("http://server:8096", "test-token")
    url = client.get_subtitle_url("item-1", "ms-1", 1, format="ass")
    assert "Stream.ass" in url
    print("[OK] ASS subtitle URL works")

def test_import_all():
    from app.metadata import metadata
    assert metadata is not None
    print("[OK] Metadata module importable")
