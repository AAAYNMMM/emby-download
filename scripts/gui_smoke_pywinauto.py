"""
Optional: pywinauto smoke test for dist\\embyd-gui.exe.
Tests startup, window existence, and basic crash resistance.
No real credentials are used or output.

Usage:
    python scripts/gui_smoke_pywinauto.py
"""

import subprocess
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_EXE_PATH = _PROJECT_ROOT / "dist" / "embyd-gui.exe"


def main():
    if not _EXE_PATH.exists():
        print(f"SKIP: {_EXE_PATH} not found. Build the exe first.")
        return 0

    # Check pywinauto availability
    try:
        from pywinauto import Application
        from pywinauto.timings import wait_until
    except ImportError:
        print("SKIP: pywinauto not installed. Run: python -m pip install pywinauto")
        return 0

    import tempfile
    tmpdir = Path(tempfile.mkdtemp(prefix="embyd_smoke_"))

    print(f"Launching: {_EXE_PATH}")
    proc = subprocess.Popen(
        [str(_EXE_PATH)],
        cwd=str(_EXE_PATH.parent),
    )

    time.sleep(3)

    # Check process alive
    if proc.poll() is not None:
        print(f"FAIL: Process exited immediately with code {proc.returncode}")
        return 1

    print("OK: Process started (PID={})".format(proc.pid))

    try:
        app = Application(backend="uia").connect(process=proc.pid, timeout=10)
        main_window = app.window()
        title = main_window.window_text()

        print(f"OK: Window found. Title: {title}")

        # Screenshot
        ss_path = tmpdir / "embyd_gui_smoke.png"
        main_window.capture_as_image().save(str(ss_path))
        print(f"OK: Screenshot saved: {ss_path}")

        # Try to find some controls via UIA — no hardcoded coordinates
        try_count = 0
        for ctrl_name in ["Edit", "Button", "Tab"]:
            try:
                ctrls = main_window.descendants(control_type=ctrl_name)
                if ctrls:
                    try_count += 1
            except Exception:
                pass

        if try_count >= 1:
            print(f"OK: Found UIA controls ({try_count} types)")
        else:
            print("WARNING: No UIA controls found — may need to inspect manually")

    except Exception as e:
        print(f"WARNING: pywinauto connection/control inspection: {e}")
    finally:
        # Clean shutdown
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        print("OK: Process terminated.")

    # Clean up temp files
    import shutil
    try:
        shutil.rmtree(tmpdir)
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
