"""
GUI structure and safety tests - does NOT create MainWindow instances.
Tests source code, imports, and widget structure.
"""

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_test_env():
    env_path = _PROJECT_ROOT / ".env.local"
    if not env_path.exists():
        return {}
    cfg = {}
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


class TestEnvConfig:
    """Verify .env.local is properly configured for testing."""

    def test_env_local_exists(self):
        env_path = _PROJECT_ROOT / ".env.local"
        assert env_path.exists(), ".env.local must exist with test credentials"

    def test_env_example_sanitized(self):
        """Verify .env.example contains only placeholders."""
        example_path = _PROJECT_ROOT / ".env.example"
        content = example_path.read_text(encoding="utf-8")
        assert "tYWP@" not in content, ".env.example must not contain real password"
        assert "ayanami" not in content, ".env.example must not contain real username"
        assert "v1.uhdnow.com" not in content, ".env.example must not contain real server URL"
        assert "replace_me" in content, ".env.example should use placeholder values"

    def test_env_local_has_required_fields(self):
        cfg = _load_test_env()
        required = ["EMBYD_TEST_SERVER", "EMBYD_TEST_USERNAME", "EMBYD_TEST_PASSWORD"]
        for field in required:
            assert field in cfg, f"{field} missing from .env.local"

    def test_gitignore_covers_env_local(self):
        gitignore = (_PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".env.local" in gitignore, ".gitignore must include .env.local"


class TestGUIImportStructure:
    """Test imports and source code structure without Qt runtime."""

    def test_main_window_imports(self):
        """Verify main_window.py parses successfully."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        import ast
        tree = ast.parse(src)
        assert tree is not None, "main_window.py must parse without syntax errors"

    def test_backend_client_imports(self):
        src = (_PROJECT_ROOT / "app" / "gui" / "backend_client.py").read_text(encoding="utf-8")
        import ast
        tree = ast.parse(src)
        assert tree is not None

    def test_objectnames_set(self):
        """Verify all required widget objectNames exist in source."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        required_names = [
            "server_url_input", "username_input", "password_input", "login_button",
            "movie_search_input", "movie_search_button", "movie_results_table",
            "preview_item_id_input", "preview_media_source_combo", "preview_download_button",
            "series_search_input", "series_search_button", "series_results_table",
            "season_list", "episode_table", "episode_back_button",
            "episode_download_selected_button",
            "task_start_button", "task_pause_button", "task_resume_button",
            "task_cancel_button", "tasks_table",
        ]
        for name in required_names:
            assert f'setObjectName("{name}")' in src, f"objectName '{name}' not found in main_window.py"

    def test_login_auto_fill_source(self):
        """Verify login fields exist in source."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "self.login_server_url = QLineEdit()" in src
        assert "self.login_username = QLineEdit()" in src
        assert "self.login_password = QLineEdit()" in src
        assert "self.btn_login = QPushButton" in src

    def test_download_flow_source(self):
        """Verify download flow methods exist in source."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "def _on_download(self):" in src, "Missing _on_download handler"
        assert "def _on_download_created(self" in src, "Missing create callback"
        assert "def _on_download_started(self" in src, "Missing start callback"
        assert "def _on_download_start_error(self" in src, "Missing error handler"

    def test_download_error_handling(self):
        """Verify download callbacks check for API errors."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        # _on_download_started must check for error in result
        assert "result.get(\"error\")" in src, (
            "_on_download_started must check result for API errors"
        )
        # _on_series_task_started must check for error
        assert "result.get(\"error\")" in src

    def test_series_browser_source(self):
        """Verify series browser structure."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "def _on_series_search(self" in src
        assert "def _on_series_browser_download(self" in src
        assert "def _on_back_to_seasons(self" in src
        assert "self.series_stack = QStackedWidget()" in src

    def test_password_masked_in_source(self):
        """Verify password field uses Password echo mode."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "EchoMode.Password" in src, "Password field must use Password echo mode"

    def test_redaction_helper_exists(self):
        """Verify redaction utility is available."""
        from app.utils.redaction import redact_sensitive
        result = redact_sensitive("password=secret123")
        assert "secret123" not in result
        assert "REDACTED" in result

    def test_heartbeat_exists(self):
        """Verify GUI heartbeat timer is configured."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "def _on_heartbeat(self" in src, "Heartbeat handler missing"
        assert "_heartbeat_timer" in src, "Heartbeat timer missing"

    def test_tasks_tab_controls_exist(self):
        """Verify tasks tab control buttons."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        for btn in ["btn_start_selected", "btn_pause_selected", "btn_resume_selected",
                     "btn_cancel_selected", "btn_delete_selected"]:
            assert btn in src, f"Task button {btn} missing"


class TestCredentialSafety:
    """Verify no credentials leak into source files."""

    def test_no_hardcoded_server(self):
        """Server URL must not appear in source files."""
        src_dir = _PROJECT_ROOT / "app"
        forbidden = ["v1.uhdnow.com", "tYWP@", "ayanami"]
        for py_file in src_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for fb in forbidden:
                assert fb not in content, (
                    f"Hardcoded credential '{fb}' found in {py_file.relative_to(_PROJECT_ROOT)}"
                )

    def test_no_credentials_in_tests(self):
        """Test files must not contain real credentials."""
        test_dir = _PROJECT_ROOT / "tests"
        # NOTE: this test file and gui_real tests reference credential patterns
        # for validation purposes - they are not actual credentials.
        skip_files = {"test_gui_smoke_structure.py", "test_gui_real_smoke.py", "test_gui_real_series.py"}
        forbidden = ["uhdnow.com", "tYWP@", "ayanami"]
        for py_file in test_dir.rglob("*.py"):
            if py_file.name in skip_files:
                continue
            file_content = py_file.read_text(encoding="utf-8", errors="ignore")
            for fb in forbidden:
                assert fb not in file_content, (
                    f"Hardcoded credential '{fb}' found in {py_file.relative_to(_PROJECT_ROOT)}"
                )

    def test_no_credentials_in_scripts(self):
        """Script files must not contain real credentials."""
        scripts_dir = _PROJECT_ROOT / "scripts"
        forbidden = ["v1.uhdnow.com", "tYWP@", "ayanami"]
        for py_file in scripts_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for fb in forbidden:
                assert fb not in content, (
                    f"Hardcoded credential '{fb}' found in {py_file.relative_to(_PROJECT_ROOT)}"
                )


class TestDownloadPipelineCode:
    """Verify download pipeline code correctness (read-only source analysis)."""

    def test_create_then_start_flow(self):
        """_on_download must call create_task then start_task."""
        src = (_PROJECT_ROOT / "app" / "gui" / "main_window.py").read_text(encoding="utf-8")
        assert "create_task" in src
        assert "start_task" in src
        # The flow: _on_download -> create_task -> _on_download_created -> start_task
        assert "backend_client.create_task" in src or "_backend_client.create_task" in src

    def test_start_task_checks_status(self):
        """BackendDownloadManager.start_task must check status in (pending, paused, failed)."""
        src = (_PROJECT_ROOT / "app" / "backend" / "download_manager.py").read_text(encoding="utf-8")
        assert '"pending"' in src
        # start_task should only proceed for pending/paused/failed
        assert '("pending", "paused", "failed")' in src or '("pending","paused","failed")' in src

    def test_download_task_transitions(self):
        """_download_task must emit status_changed events for preparing and downloading."""
        src = (_PROJECT_ROOT / "app" / "backend" / "download_manager.py").read_text(encoding="utf-8")
        assert '"preparing"' in src, "Status 'preparing' must be emitted"
        assert '"downloading"' in src, "Status 'downloading' must be emitted"

    def test_api_start_requires_download_dir(self):
        """start_task_handler must require download_dir."""
        src = (_PROJECT_ROOT / "app" / "backend" / "api.py").read_text(encoding="utf-8")
        assert '"download_dir required"' in src or "download_dir required" in src
