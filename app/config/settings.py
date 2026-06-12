"""
Configuration management for EmbyD.

Handles:
- Reading/writing JSON config file
- Config location discovery (explicit > app directory)
- Validation
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

from app.config.schema import EmbyConfig

# Default config file name
CONFIG_FILENAME = "embyd_config.json"

# Legacy app data directory used by older builds.
LEGACY_APP_DATA_DIR = Path(os.environ.get("APPDATA", Path.home() / ".config")) / "embyD"


def get_app_dir() -> Path:
    """Return the directory where EmbyD should keep local app files."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def get_legacy_config_path() -> Path:
    """Return the pre-local-config AppData config path."""
    return LEGACY_APP_DATA_DIR / CONFIG_FILENAME


def find_config_path(config_path: Optional[str] = None) -> Path:
    """
    Find the configuration file path.
    Priority: explicit path > app directory ./embyd_config.json

    Args:
        config_path: Explicit path override.

    Returns:
        Path to config file.
    """
    if config_path:
        return Path(config_path)

    return get_app_dir() / CONFIG_FILENAME


def load_config(config_path: Optional[str] = None) -> EmbyConfig:
    """
    Load configuration from file. Returns defaults if file doesn't exist.

    Args:
        config_path: Explicit config file path.

    Returns:
        EmbyConfig instance.
    """
    path = find_config_path(config_path)

    if not path.exists():
        legacy_path = get_legacy_config_path()
        if not config_path and legacy_path.exists():
            try:
                with open(legacy_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                config = EmbyConfig.from_dict(data)
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
                return config
            except (json.JSONDecodeError, IOError):
                pass
        return EmbyConfig()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        config = EmbyConfig.from_dict(data)
        return config
    except (json.JSONDecodeError, IOError) as e:
        from app.utils.logger import get_logger
        get_logger().warning(f"Failed to load config from {path}: {e}")
        return EmbyConfig()


def save_config(config: EmbyConfig, config_path: Optional[str] = None) -> None:
    """
    Save configuration to file.

    Args:
        config: EmbyConfig instance to save.
        config_path: Explicit config file path. If None, uses the app directory.
    """
    if config_path:
        path = Path(config_path)
    else:
        path = get_app_dir() / CONFIG_FILENAME

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.to_dict()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    from app.utils.logger import get_logger
    get_logger().info(f"Config saved to {path}")


def get_config_path_display(config_path: Optional[str] = None) -> str:
    """Get the config file path for display purposes."""
    path = find_config_path(config_path)
    return str(path.absolute())


def config_exists(config_path: Optional[str] = None) -> bool:
    """Check if a config file exists."""
    return find_config_path(config_path).exists()
