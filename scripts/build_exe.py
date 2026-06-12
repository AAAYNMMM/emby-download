"""EmbyD - PyInstaller build script.

Builds embyd-gui.exe (GUI only).
EmbyD is GUI-only; CLI control has been removed.

Usage:
    python scripts/build_exe.py
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

HIDDEN_IMPORTS = [
    "app.config.settings", "app.config.schema",
    "app.core.emby_api", "app.core.auth",
    "app.core.playback_info", "app.core.download_capability",
    "app.core.naming", "app.core.download_preview", "app.core.series",
    "app.downloader.range_downloader", "app.downloader.direct_download",
    "app.downloader.stream_download", "app.downloader.task_store",
    "app.metadata.metadata",
    "app.utils.logger",
    "app.gui.app", "app.gui.main_window",
    "app.gui.workers", "app.gui.widgets",
    "app.gui.i18n", "app.gui.download_controller",
    "aiohttp", "aiofiles", "cryptography", "keyring",
]

# PySide6 modules actually used by the app
PYSIDE_MODULES = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]

# PySide6 modules NOT used — exclude to save ~150 MB
PYSIDE_EXCLUDES = [
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.QtBluetooth",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtWebSockets",
    "PySide6.QtTest",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtConcurrent",
    "PySide6.QtPositioning",
    "PySide6.QtPrintSupport",
    "PySide6.QtDBus",
    "PySide6.QtSql",
    "PySide6.QtXml",
    "PySide6.QtHelp",
    "PySide6.QtUiTools",
    "PySide6.QtTextToSpeech",
    "PySide6.QtSerialPort",
    "PySide6.QtNfc",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DLogic",
]


def build_gui():
    print("=" * 60)
    print("  Building embyd-gui.exe (GUI)...")
    print("=" * 60)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--windowed", "--clean", "--noconfirm",
        "--name", "embyd-gui",
        "--distpath", str(PROJECT_ROOT / "dist"),
        "--workpath", str(PROJECT_ROOT / "build"),
    ]

    # Collect only the Qt modules we actually use
    for mod in PYSIDE_MODULES:
        cmd += ["--collect-all", mod]

    # Exclude unused Qt modules to save ~150 MB
    for mod in PYSIDE_EXCLUDES:
        cmd += ["--exclude-module", mod]

    for mod in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", mod]

    cmd += [str(PROJECT_ROOT / "app/gui/app.py")]

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.stdout:
        last_lines = result.stdout[-1500:] if len(result.stdout) > 1500 else result.stdout
        print(last_lines)
    if result.returncode != 0:
        if result.stderr:
            print("[STDERR]", result.stderr[-1000:])
        print("[ERROR] Build failed.")
        return False

    exe = PROJECT_ROOT / "dist" / "embyd-gui.exe"
    if exe.exists():
        size = exe.stat().st_size / (1024 * 1024)
        print(f"[OK] embyd-gui.exe ({size:.1f} MB)")
        return True
    print("[ERROR] embyd-gui.exe not found!")
    return False


def clean():
    build_dir = PROJECT_ROOT / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    for spec in PROJECT_ROOT.glob("*.spec"):
        spec.unlink()


def main():
    success = build_gui()
    clean()

    print("\n" + "=" * 60)
    if success:
        print("  Build completed: dist/embyd-gui.exe")
    else:
        print("  Build failed. Check errors above.")
        return 1
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
