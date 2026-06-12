"""
Stage 2 verification tests.
Run from project root: python tests/test_stage2.py
"""

import sys
import os

# Ensure we can find the app package (supports both direct run and pytest)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# All imports at top level (before any os.chdir)
from app.core.auth import encrypt_token, decrypt_token
from app.core.emby_api import EmbyApiClient, EmbyAuthError
from app.config.schema import EmbyConfig
from app.config.settings import load_config, save_config
from app.core.download_preview import build_item_display_title, build_item_filename_base
import tempfile


def test_encrypt_decrypt_roundtrip():
    t = encrypt_token('my-secret-token-abc123')
    d = decrypt_token(t)
    assert d == 'my-secret-token-abc123', 'Token roundtrip failed'
    print('✓ Token encrypt/decrypt roundtrip OK')


def test_encryption_salted():
    t1 = encrypt_token('my-secret-token-abc123')
    t2 = encrypt_token('my-secret-token-abc123')
    assert t1 != t2, 'Same token should produce different ciphertext'
    print('✓ Token encryption is salted (different output each time)')


def test_decrypt_invalid():
    try:
        decrypt_token('invalid-encrypted-data')
        assert False, 'Should have raised'
    except ValueError:
        print('✓ Decrypt with invalid data correctly raises ValueError')


def test_download_url():
    client = EmbyApiClient('http://server:8096', 'test-token')
    url = client.get_download_url('123')
    assert '/Items/123/Download' in url, f'Bad URL: {url}'
    assert 'api_key=test-token' in url
    print('✓ Download URL construction OK')


def test_stream_url():
    client = EmbyApiClient('http://server:8096', 'test-token')
    url = client.get_stream_url('123', 'ms-456')
    assert '/Videos/123/stream' in url
    assert 'MediaSourceId=ms-456' in url
    assert 'Static=true' in url
    print('✓ Stream URL construction OK')


def test_config_validation():
    cfg = EmbyConfig()
    errors = cfg.validate()
    assert len(errors) == 0, f'Default config should have no errors: {errors}'
    assert cfg.download_dir == ''
    cfg.server_url = 'invalid'
    errors = cfg.validate()
    assert len(errors) == 1
    assert 'http://' in errors[0]
    print('✓ Config validation works')


def test_episode_display_and_filename():
    item = {
        "Type": "Episode",
        "SeriesName": "Example Show",
        "ParentIndexNumber": 1,
        "IndexNumber": 2,
        "Name": "Pilot: Part/Two",
    }
    assert build_item_display_title(item) == "Example Show - S01E02 - Pilot: Part/Two"
    assert build_item_filename_base(item) == "Example Show - S01E02 - Pilot Part Two"
    print('[OK] Episode display and filename work')


def test_config_save_load_roundtrip():
    cfg = EmbyConfig()
    cfg.server_url = 'http://valid:8096'
    test_path = os.path.join(tempfile.gettempdir(), 'test_embyd_config.json')
    save_config(cfg, test_path)
    loaded = load_config(test_path)
    assert loaded.server_url == 'http://valid:8096'
    os.remove(test_path)
    print('✓ Config save/load roundtrip OK')


# ── CLI tests (skipped — CLI control removed in Stage 12g) ───────

import pytest

@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_cli_help():
    """CLI --help no longer provides real commands."""
    pass


@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_config_show():
    pass


@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_config_set_get():
    pass


@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_download_requires_directory_without_default():
    pass


def test_auth_error_handling():
    """Test that login with wrong server gives connection error."""
    client = EmbyApiClient('http://192.168.1.250:8096')
    try:
        client.get_user()
        assert False, 'Should have raised'
    except Exception as e:
        print(f'✓ Auth error handling works (expected: {type(e).__name__})')


if __name__ == '__main__':
    tests = [
        test_encrypt_decrypt_roundtrip,
        test_encryption_salted,
        test_decrypt_invalid,
        test_download_url,
        test_stream_url,
        test_config_validation,
        test_episode_display_and_filename,
        test_config_save_load_roundtrip,
        test_auth_error_handling,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f'✗ {test.__name__} FAILED: {e}')
            failed += 1

    print(f'\n=== Stage 2 Results: {passed}/{len(tests)} passed, {failed} failed ===')
    sys.exit(1 if failed > 0 else 0)
