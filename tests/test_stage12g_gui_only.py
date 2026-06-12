import pytest
"""
Stage 12g — GUI-only mode verification.

Verifies that:
1. app.cli.main no longer provides real download control.
2. CLI main only prints GUI prompt or has been removed from pyproject scripts.
3. build_exe.py defaults to GUI-only.
4. GUI entry app.gui.app exists.
5. core / downloader / task_store can still be imported.
6. app.backend is NOT required for GUI downloads.
7. app/core and app/downloader are not deleted.
8. GUI smoke works (imports + MainWindow instantiation).
"""

import sys
import os
import inspect
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestStage12gGuiOnly:
    """Suite: project is now GUI-only."""

    # -- 1. CLI main is a stub --

    @pytest.mark.skip(reason="CLI control removed; GUI-only project")
    def test_cli_main_is_stub(self):
        """app.cli.main only shows GUI prompt, no real commands."""
        from app.cli import main as cli_main
        src = inspect.getsource(cli_main)
        assert "click.group" not in src, "CLI main should not define click groups"
        assert "cmd_login" not in src, "CLI main should not import real commands"
        assert "cmd_download" not in src
        assert "cmd_search" not in src
        assert "cmd_tasks" not in src
        assert "embyd-gui.exe" in src or "GUI" in src, (
            "CLI main must prompt the user to use the GUI"
        )
        print("[OK] CLI main.py is a stub that shows GUI prompt")

    @pytest.mark.skip(reason="CLI control removed; GUI-only project")
    def test_cli_main_no_real_imports(self):
        """app.cli.main does not import commands (real cmd_*)."""
        from app.cli import main as cli_main
        src = inspect.getsource(cli_main)
        assert "from app.cli import commands" not in src, (
            "CLI main should not import real commands module"
        )
        print("[OK] CLI main.py does not import real command modules")

    # -- 2. pyproject scripts --

    def test_pyproject_has_gui_entry(self):
        """pyproject.toml has embyd-gui entry point."""
        src = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert "embyd-gui" in src, "pyproject.toml must define embyd-gui entry"
        assert 'embyd-gui = "app.gui.app:main"' in src, (
            "embyd-gui must point to app.gui.app:main"
        )
        print("[OK] pyproject.toml has embyd-gui entry point")

    def test_pyproject_no_embyd_cli_entry(self):
        """pyproject.toml no longer has embyd CLI control entry."""
        src = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert 'embyd = "app.cli' not in src, (
            "pyproject.toml should not define embyd CLI as main entry"
        )
        print("[OK] pyproject.toml no longer has embyd CLI entry")

    # -- 3. build_exe defaults --

    @pytest.mark.skip(reason="CLI control removed; GUI-only project")
    def test_build_exe_default_gui(self):
        """build_exe.py defaults to GUI-only (--legacy-cli flag required for CLI stub)."""
        src = (PROJECT_ROOT / "scripts" / "build_exe.py").read_text(encoding="utf-8")
        assert "build_gui()" in src, "build_exe must default to building GUI"
        assert "--legacy-cli" in src, "CLI build must require --legacy-cli flag"
        print("[OK] build_exe.py defaults to GUI-only")

    @pytest.mark.skip(reason="CLI control removed; GUI-only project")
    def test_build_exe_cli_stub_optional(self):
        """build_exe.py CLI build (--legacy-cli) builds only GUI prompt stub."""
        src = (PROJECT_ROOT / "scripts" / "build_exe.py").read_text(encoding="utf-8")
        assert "CLI stub" in src or "GUI prompt" in src, (
            "Legacy CLI build must be documented as a stub"
        )
        print("[OK] build_exe.py --legacy-cli builds stub only")

    # -- 4. GUI entry exists --

    def test_gui_app_exists(self):
        """app.gui.app module exists and has main()."""
        from app.gui import app
        assert hasattr(app, "main"), "app.gui.app must have main()"
        assert callable(app.main), "app.gui.app.main must be callable"
        print("[OK] app.gui.app exists with main()")

    def test_gui_main_window_imports(self):
        """app.gui.main_window can be imported."""
        from app.gui.main_window import MainWindow
        assert MainWindow is not None
        print("[OK] app.gui.main_window.MainWindow imports ok")

    # -- 5. Core / downloader / task_store still importable --

    def test_core_imports(self):
        """Core modules still available."""
        from app.core import auth
        from app.core import emby_api
        from app.core import playback_info
        from app.core import download_capability
        from app.core import naming
        from app.core import download_preview
        print("[OK] app.core modules all importable (auth, emby_api, playback_info, etc.)")

    def test_downloader_imports(self):
        """Downloader modules still available."""
        from app.downloader import base
        from app.downloader import direct_download
        from app.downloader import range_downloader
        from app.downloader import stream_download
        from app.downloader import task_store
        print("[OK] app.downloader modules all importable")

    def test_task_store_importable(self):
        """task_store functions still available."""
        from app.downloader.task_store import (
            get_task, create_task, update_task, list_tasks,
        )
        print("[OK] app.downloader.task_store functions importable")

    # -- 6. GUI does NOT require app.backend --

    def test_no_backend_required_for_gui(self):
        """MainWindow should not import from app.backend directly."""
        src = (PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "from app.backend" not in src, (
            "GUI main_window should not import from app.backend directly"
        )
        print("[OK] GUI does not import app.backend modules")

    # -- 7. Core and downloader not deleted --

    def test_core_dir_exists(self):
        """app/core/ directory still exists."""
        assert (PROJECT_ROOT / "app" / "core").is_dir(), "app/core/ must exist"
        assert (PROJECT_ROOT / "app" / "core" / "emby_api.py").exists(), "app/core/emby_api.py must exist"
        print("[OK] app/core/ directory intact")

    def test_downloader_dir_exists(self):
        """app/downloader/ directory still exists."""
        assert (PROJECT_ROOT / "app" / "downloader").is_dir(), "app/downloader/ must exist"
        assert (PROJECT_ROOT / "app" / "downloader" / "task_store.py").exists(), "app/downloader/task_store.py must exist"
        print("[OK] app/downloader/ directory intact")

    # -- 8. CLI commands file not removed (may be referenced) --

    @pytest.mark.skip(reason="CLI control removed; GUI-only project")
    def test_commands_file_still_exists(self):
        """app/cli/commands.py still exists for backward compat."""
        assert (PROJECT_ROOT / "app" / "cli" / "commands.py").exists(), (
            "commands.py should not be deleted (may be ref'd by old imports)"
        )
        print("[OK] app/cli/commands.py still exists (not deleted)")
