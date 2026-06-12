"""Release sanity checks for EmbyD GUI-only release.

Validates:
- Core modules are importable
- GUI entry point exists
- Build script exists
- .gitignore covers sensitive files
- .env.example is safe
- README has no real credentials
- CLI/backend code is removed
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def test_gui_main_window_importable():
    """MainWindow must be importable (core GUI smoke)."""
    from app.gui.main_window import MainWindow
    assert MainWindow is not None


def test_gui_app_importable():
    """GUI entry point module must be importable."""
    import app.gui.app
    assert app.gui.app is not None


def test_core_modules_importable():
    """Core business logic modules must be importable."""
    import app.core.emby_api
    import app.core.auth
    import app.core.playback_info
    import app.core.download_capability
    import app.core.naming
    import app.core.download_preview
    import app.core.series
    assert True


def test_downloader_modules_importable():
    """Downloader modules must be importable."""
    import app.downloader.range_downloader
    import app.downloader.direct_download
    import app.downloader.stream_download
    import app.downloader.task_store
    import app.downloader.base
    assert True


def test_config_modules_importable():
    """Config modules must be importable."""
    import app.config.settings
    import app.config.schema
    assert True


def test_gui_workers_importable():
    """GUI workers must be importable."""
    from app.gui.workers import DownloadItemWorker
    assert DownloadItemWorker is not None


def test_download_controller_importable():
    """DownloadController must be importable."""
    from app.gui.download_controller import DownloadController
    assert DownloadController is not None


def test_build_script_exists():
    """Build script must exist and be runnable."""
    build_path = os.path.join(PROJECT_ROOT, "scripts", "build_exe.py")
    assert os.path.exists(build_path), f"build script not found: {build_path}"
    with open(build_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "embyd-gui" in content
    assert "PyInstaller" in content


def test_gitignore_covers_sensitive_files():
    """.gitignore must prevent committing sensitive files."""
    gitignore_path = os.path.join(PROJECT_ROOT, ".gitignore")
    assert os.path.exists(gitignore_path)
    with open(gitignore_path, "r", encoding="utf-8") as f:
        content = f.read()
    required_patterns = [".env.local", "embyd_config.json", "tasks.db", "dist/", ".venv/", "*.log"]
    for pat in required_patterns:
        assert pat in content, f".gitignore missing: {pat}"


def test_env_example_no_real_credentials():
    """.env.example must not contain real credentials."""
    env_path = os.path.join(PROJECT_ROOT, ".env.example")
    assert os.path.exists(env_path)
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "example.com" in content or "replace_me" in content, "no placeholder found"
    assert "https://" in content
    assert "password" not in content.lower() or "replace_me" in content


def test_readme_no_real_credentials():
    """README must not contain real server URLs or credentials."""
    readme_path = os.path.join(PROJECT_ROOT, "README.md")
    assert os.path.exists(readme_path)
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    suspicious = ["duckdns.org", "uhdnow", "ayanami"]
    for s in suspicious:
        assert s not in content, f"README contains suspicious string: {s}"


def test_cli_code_removed():
    """CLI and backend code must be removed."""
    cli_path = os.path.join(PROJECT_ROOT, "app", "cli")
    backend_path = os.path.join(PROJECT_ROOT, "app", "backend")
    bc_path = os.path.join(PROJECT_ROOT, "app", "gui", "backend_client.py")
    assert not os.path.exists(cli_path), "app/cli should be removed"
    assert not os.path.exists(backend_path), "app/backend should be removed"
    assert not os.path.exists(bc_path), "backend_client.py should be removed"


def test_gui_entry_exists():
    """GUI entry point must exist."""
    entry = os.path.join(PROJECT_ROOT, "app", "gui", "app.py")
    assert os.path.exists(entry), f"GUI entry not found: {entry}"


def test_requirements_exist():
    """requirements.txt must exist."""
    req = os.path.join(PROJECT_ROOT, "requirements.txt")
    assert os.path.exists(req)
    with open(req, "r", encoding="utf-8") as f:
        content = f.read()
    assert "PySide6" in content
    assert "aiohttp" in content


def test_pyproject_toml_exists():
    """pyproject.toml must exist."""
    pp = os.path.join(PROJECT_ROOT, "pyproject.toml")
    assert os.path.exists(pp)
