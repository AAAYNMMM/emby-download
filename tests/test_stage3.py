"""
Stage 3 verification tests.
Run from project root: python tests/test_stage3.py
"""

import sys
import os
import pytest
import inspect

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.emby_api import EmbyApiClient
from app.config.schema import EmbyConfig


# ── Core API tests (retained) ────────────────────────────────────

def test_api_client_mock():
    """Verify API client methods exist with correct signatures."""
    client = EmbyApiClient('http://test:8096')

    # get_libraries
    sig = inspect.signature(client.get_libraries)
    params = list(sig.parameters.keys())
    assert 'user_id' in params, f'get_libraries missing user_id param: {params}'

    # search_items
    sig = inspect.signature(client.search_items)
    params = list(sig.parameters.keys())
    assert 'user_id' in params
    assert 'query' in params
    assert 'parent_id' in params
    assert 'limit' in params
    print('✓ API client methods have correct signatures')


# ── CLI tests (skipped — CLI control removed in Stage 12g) ───────

@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_imports():
    pass


@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_cmd_libraries_without_login():
    pass


@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_cmd_search_without_login():
    pass


@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_create_client_no_token():
    pass


@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_cli_libraries_help():
    pass


@pytest.mark.skip(reason="CLI control removed: EmbyD is GUI-only")
def test_cli_search_help():
    pass


if __name__ == '__main__':
    tests = [
        test_api_client_mock,
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

    print(f'\n=== Stage 3 Results: {passed}/{len(tests)} passed, {failed} failed ===')
    sys.exit(1 if failed > 0 else 0)
