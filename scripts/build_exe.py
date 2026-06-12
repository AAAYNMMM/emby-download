"""
EmbyD - PyInstaller build script.

Default: builds embyd-gui.exe only (GUI).

CLI control functionality has been removed. EmbyD now only supports GUI mode.

Usage:
    python scripts/build_exe.py              # Build GUI only (default)
    python scripts/build_exe.py --legacy-cli # Also build embyd.exe (CLI stub that shows GUI prompt)
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


COMMON_HIDDEN = [
    "app.config.settings", "app.config.schema",
    "app.core.emby_api", "app.core.auth",
    "app.core.playback_info", "app.core.download_capability",
    "app.core.naming", "app.core.download_preview",
    "app.downloader.range_downloader", "app.downloader.direct_download",
    "app.downloader.stream_download", "app.downloader.task_store",
    "app.metadata.metadata",
    "app.cli.commands",
    "app.utils.logger",
    "app.backend.server", "app.backend.download_manager", "app.backend.api",
    "aiohttp", "aiofiles", "tqdm", "cryptography", "keyring",
]

LEGACY_CLI_EXCLUDE = [
    # CLI stub only needs print + sys.exit, no real modules required
]


def build_legacy_cli_stub():
    """Build embyd.exe as a stub that just prints the GUI prompt.

    This is optional — the main build target is embyd-gui.exe.
    """
    print("=" * 60)
    print("  Building embyd.exe (CLI stub - GUI prompt only)...")
    print("=" * 60)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--console", "--clean", "--noconfirm",
        "--name", "embyd",
        "--distpath", str(PROJECT_ROOT / "dist"),
        "--workpath", str(PROJECT_ROOT / "build"),
    ]
    for mod in COMMON_HIDDEN:
        cmd += ["--hidden-import", mod]
    cmd += [str(PROJECT_ROOT / "app/cli/main.py")]

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.stdout:
        last_lines = result.stdout[-1500:] if len(result.stdout) > 1500 else result.stdout
        try:
            print(last_lines)
        except UnicodeEncodeError:
            print(last_lines.encode("ascii", errors="replace").decode("ascii"))
    if result.returncode != 0:
        if result.stderr:
            print("[STDERR]", result.stderr[-1000:].encode("ascii", errors="replace").decode("ascii"))
        print("[ERROR] CLI stub build failed.")
        return False

    exe = PROJECT_ROOT / "dist" / "embyd.exe"
    if exe.exists():
        size = exe.stat().st_size / (1024 * 1024)
        print(f"[OK] embyd.exe (CLI stub) ({size:.1f} MB)")
        return True
    print("[ERROR] embyd.exe not found!")
    return False


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
        "--collect-all", "PySide6",
    ]
    gui_hidden = COMMON_HIDDEN + [
        "app.gui.app", "app.gui.main_window",
        "app.gui.workers", "app.gui.widgets",
        "app.gui.backend_client", "app.gui.i18n",
        "app.gui.download_controller",
        "app.core.series",
    ]
    for mod in gui_hidden:
        cmd += ["--hidden-import", mod]
    cmd += [str(PROJECT_ROOT / "app/gui/app.py")]

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.stdout:
        last_lines = result.stdout[-1500:] if len(result.stdout) > 1500 else result.stdout
        try:
            print(last_lines)
        except UnicodeEncodeError:
            print(last_lines.encode("ascii", errors="replace").decode("ascii"))
    if result.returncode != 0:
        if result.stderr:
            print("[STDERR]", result.stderr[-1000:].encode("ascii", errors="replace").decode("ascii"))
        print("[ERROR] GUI build failed.")
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
    parser = argparse.ArgumentParser(description="Build EmbyD executables")
    parser.add_argument("--legacy-cli", action="store_true",
                        help="Also build embyd.exe (CLI stub that only shows GUI prompt)")
    args = parser.parse_args()

    success = True

    # Always build GUI (default)
    gui_ok = build_gui()
    if not gui_ok:
        success = False

    # Optionally build legacy CLI stub
    if args.legacy_cli:
        if not build_legacy_cli_stub():
            success = False

    clean()

    print("\n" + "=" * 60)
    if success:
        print("  Build completed successfully!")
        if args.legacy_cli:
            print("  - embyd-gui.exe (GUI)")
            print("  - embyd.exe (CLI stub - GUI prompt only)")
        else:
            print("  - embyd-gui.exe (GUI)")
            print()
            print("  Tip: pass --legacy-cli to also build embyd.exe stub")
    else:
        print("  Some builds failed. Check errors above.")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
