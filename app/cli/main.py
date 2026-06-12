"""
EmbyD - CLI Entry Point (Deprecated)

CLI control functionality has been removed.
EmbyD now only supports GUI mode.
"""

import sys


def main():
    """Print GUI-only notice and exit."""
    print("=" * 60)
    print("  EmbyD \u73b0\u5728\u4ec5\u652f\u6301 GUI\uff0c\u8bf7\u8fd0\u884c embyd-gui.exe")
    print("  EmbyD now only supports GUI. Please run embyd-gui.exe")
    print("=" * 60)
    print()
    print("  GUI \u542f\u52a8\u65b9\u5f0f / How to start the GUI:")
    print("    python -m app.gui.app")
    print("    dist\\embyd-gui.exe")
    sys.exit(0)


if __name__ == "__main__":
    main()
