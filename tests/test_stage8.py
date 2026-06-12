"""
Stage 8 verification tests (GUI-only mode).
CLI embyd.exe is no longer built by default.
"""
import sys, os, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@pytest.mark.skip(reason="CLI removed: embyd.exe no longer built by default")
def test_exe_exists():
    pass

@pytest.mark.skip(reason="CLI removed: embyd.exe no longer built by default")
def test_exe_help():
    pass

@pytest.mark.skip(reason="CLI removed: embyd.exe no longer built by default")
def test_exe_version():
    pass

@pytest.mark.skip(reason="CLI removed: embyd.exe no longer built by default")
def test_exe_config_show():
    pass

@pytest.mark.skip(reason="CLI removed: embyd.exe no longer built by default")
def test_exe_search_without_login():
    pass

@pytest.mark.skip(reason="CLI removed: embyd.exe no longer built by default")
def test_exe_download_without_login():
    pass

def test_build_script_exists():
    assert os.path.exists(os.path.join(PROJECT_ROOT, "scripts", "build_exe.py")), "build script must exist"
    print("build_exe.py exists")

@pytest.mark.skip(reason="CLI removed: no commands to list")
def test_all_commands_listed():
    pass

def test_gui_build_reference():
    """Verify build_exe.py references GUI build as default."""
    src = open(os.path.join(PROJECT_ROOT, "scripts", "build_exe.py"), encoding="utf-8").read()
    assert "build_gui()" in src, "build_exe must build GUI"
    assert "--legacy-cli" in src, "CLI build must be behind --legacy-cli flag"
    print("build_exe.py defaults to GUI-only")
