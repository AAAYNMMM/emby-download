"""
Configuration schema for EmbyD.

Defines the EmbyConfig dataclass with all configurable fields,
their default values, types, and validation rules.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class EmbyConfig:
    """EmbyD configuration dataclass."""

    # Emby server connection
    server_url: str = ""
    username: str = ""

    # Token (stored encrypted, not in plain text JSON)
    token_encrypted: str = ""
    token_storage: str = "file"  # "file" | "keyring"

    # Download settings
    download_dir: str = ""
    chunk_size_mb: int = 8
    retry_count: int = 3
    retry_delay_seconds: int = 5
    timeout_seconds: int = 600  # 10 minutes (was 30s, too short for large files)
    max_concurrent_downloads: int = 5

    # Naming
    filename_template: str = "{Name} ({Year})"

    # Metadata
    save_metadata: bool = False

    # Logging
    log_level: str = "INFO"

    # Internal
    config_version: str = "1"

    def validate(self) -> list[str]:
        """
        Validate configuration values.

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors: list[str] = []

        if self.server_url and not self.server_url.startswith(("http://", "https://")):
            errors.append("server_url must start with http:// or https://")

        if self.chunk_size_mb < 1:
            errors.append("chunk_size_mb must be >= 1")

        if self.retry_count < 0:
            errors.append("retry_count must be >= 0")

        if self.retry_delay_seconds < 0:
            errors.append("retry_delay_seconds must be >= 0")

        if self.timeout_seconds < 5:
            errors.append("timeout_seconds must be >= 5")

        if self.max_concurrent_downloads < 1:
            errors.append("max_concurrent_downloads must be >= 1")

        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if self.log_level.upper() not in valid_levels:
            errors.append(f"log_level must be one of {', '.join(valid_levels)}")

        return errors

    def to_dict(self) -> dict:
        """Convert to dictionary, excluding internal fields."""
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "EmbyConfig":
        """Create config from dictionary, applying defaults for missing fields."""
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered)


# Field metadata for display and CLI help
CONFIG_FIELD_META: dict[str, dict] = {
    "server_url": {
        "description": "Emby server URL",
        "example": "http://192.168.1.100:8096",
        "sensitive": False,
    },
    "username": {
        "description": "Emby username",
        "example": "myuser",
        "sensitive": False,
    },
    "token_encrypted": {
        "description": "Encrypted access token (auto-managed)",
        "example": "",
        "sensitive": True,
    },
    "token_storage": {
        "description": "Token storage method",
        "example": "file",
        "sensitive": False,
    },
    "download_dir": {
        "description": "Download directory path (required for downloads)",
        "example": r"C:\Users\YourName\Videos\EmbyD",
        "sensitive": False,
    },
    "chunk_size_mb": {
        "description": "Download chunk size in MB",
        "example": "8",
        "sensitive": False,
    },
    "retry_count": {
        "description": "Number of retry attempts on failure",
        "example": "3",
        "sensitive": False,
    },
    "retry_delay_seconds": {
        "description": "Base delay between retries in seconds",
        "example": "5",
        "sensitive": False,
    },
    "timeout_seconds": {
        "description": "HTTP request timeout in seconds",
        "example": "30",
        "sensitive": False,
    },
    "max_concurrent_downloads": {
        "description": "Maximum concurrent downloads (MVP: fixed to 1)",
        "example": "1",
        "sensitive": False,
    },
    "filename_template": {
        "description": "Template for output filenames",
        "example": "{Name} ({Year})",
        "sensitive": False,
    },
    "save_metadata": {
        "description": "Save NFO metadata alongside the movie",
        "example": "false",
        "sensitive": False,
    },
    "log_level": {
        "description": "Log level (DEBUG/INFO/WARNING/ERROR)",
        "example": "INFO",
        "sensitive": False,
    },
}
