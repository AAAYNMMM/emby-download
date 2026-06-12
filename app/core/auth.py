"""
Authentication module for EmbyD.

Handles:
- Login to Emby server
- Token encryption/decryption for secure storage
- Token validation
- Windows Credential Manager integration (via keyring)
"""

import os
import sys
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from app.config.schema import EmbyConfig
from app.config.settings import load_config, save_config
from app.core.emby_api import EmbyApiClient, EmbyAuthError, EmbyApiError
from app.utils.logger import get_logger

# Key file location: %APPDATA%/embyD/master.key
MASTER_KEY_PATH = Path(os.environ.get("APPDATA", Path.home() / ".config")) / "embyD" / "master.key"

# Key derivation salt (hardcoded for reproducibility on same machine)
# In production, this should be stored separately
_KEY_SALT = b"embyD_token_salt_v1"

_logger = get_logger()


def _derive_key(machine_id: str) -> bytes:
    """
    Derive an encryption key from the machine ID.

    Uses PBKDF2-HMAC-SHA256 to derive a Fernet-compatible key.

    Args:
        machine_id: A unique machine identifier

    Returns:
        32-byte URL-safe base64 encoded key
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_KEY_SALT,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(machine_id.encode("utf-8")))
    return key


def _get_machine_id() -> str:
    """
    Get a unique identifier for the current machine.

    Uses Windows MachineGUID from registry, falling back to hostname.
    """
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            machine_guid, _ = winreg.QueryValueEx(key, "MachineGUID")
            return machine_guid
    except Exception:
        # Fallback: use hostname + username
        import socket
        return f"{socket.gethostname()}-{os.environ.get('USERNAME', 'unknown')}"


def _get_fernet() -> Fernet:
    """Get a Fernet instance for encryption/decryption."""
    machine_id = _get_machine_id()
    key = _derive_key(machine_id)
    return Fernet(key)


def encrypt_token(token: str) -> str:
    """
    Encrypt an access token for secure storage.

    Uses Fernet symmetric encryption with a key derived from the machine ID.

    Args:
        token: Plain text access token

    Returns:
        Encrypted token string (URL-safe base64)
    """
    fernet = _get_fernet()
    encrypted = fernet.encrypt(token.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt a previously encrypted access token.

    Args:
        encrypted_token: Encrypted token string

    Returns:
        Plain text access token

    Raises:
        ValueError: If decryption fails (wrong machine or corrupted data)
    """
    try:
        fernet = _get_fernet()
        decrypted = fernet.decrypt(encrypted_token.encode("utf-8"))
        return decrypted.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Failed to decrypt token: {e}")


def save_token_to_keyring(server_url: str, username: str, token: str) -> None:
    """
    Save token to Windows Credential Manager via keyring.

    Args:
        server_url: Emby server URL
        username: Emby username
        token: Access token
    """
    try:
        import keyring
        service_name = f"embyD_{server_url}"
        keyring.set_password(service_name, username, token)
        _logger.info(f"Token saved to Windows Credential Manager (service: {service_name})")
    except ImportError:
        _logger.warning("keyring not available, falling back to encrypted file storage")
        raise
    except Exception as e:
        _logger.warning(f"Failed to save token to keyring: {e}")
        raise


def load_token_from_keyring(server_url: str, username: str) -> Optional[str]:
    """
    Load token from Windows Credential Manager.

    Args:
        server_url: Emby server URL
        username: Emby username

    Returns:
        Access token, or None if not found
    """
    try:
        import keyring
        service_name = f"embyD_{server_url}"
        token = keyring.get_password(service_name, username)
        return token
    except ImportError:
        return None
    except Exception:
        return None


def delete_token_from_keyring(server_url: str, username: str) -> None:
    """
    Delete token from Windows Credential Manager.

    Args:
        server_url: Emby server URL
        username: Emby username
    """
    try:
        import keyring
        service_name = f"embyD_{server_url}"
        try:
            keyring.delete_password(service_name, username)
        except keyring.errors.PasswordDeleteError:
            pass
    except Exception:
        pass


def get_token(config: EmbyConfig) -> Optional[str]:
    """
    Retrieve the access token from the configured storage.

    Priority:
    1. keyring (Windows Credential Manager)
    2. Encrypted file storage

    Args:
        config: Current EmbyConfig

    Returns:
        Access token, or None if not available
    """
    # Try keyring first
    if config.token_storage == "keyring" and config.server_url and config.username:
        token = load_token_from_keyring(config.server_url, config.username)
        if token:
            return token

    # Fall back to encrypted file storage
    if config.token_encrypted:
        try:
            return decrypt_token(config.token_encrypted)
        except ValueError as e:
            _logger.error(f"Failed to decrypt token: {e}")
            return None

    return None


def save_token(config: EmbyConfig, token: str, method: str = "file") -> EmbyConfig:
    """
    Save token to the configured storage and update config.

    Args:
        config: Current EmbyConfig
        token: Plain text access token
        method: Storage method ("file" or "keyring")

    Returns:
        Updated EmbyConfig
    """
    config.token_storage = method

    if method == "keyring":
        try:
            save_token_to_keyring(config.server_url, config.username, token)
            # Clear encrypted field since we're using keyring
            config.token_encrypted = ""
        except Exception:
            _logger.warning("Falling back to encrypted file storage")
            method = "file"

    if method == "file":
        encrypted = encrypt_token(token)
        config.token_encrypted = encrypted

    return config


def login(
    server_url: str,
    username: str,
    password: str,
    storage_method: str = "file",
) -> tuple[EmbyConfig, str]:
    """
    Login to Emby server and get an access token.

    This is the main entry point for authentication.

    Args:
        server_url: Emby server URL (e.g., http://192.168.1.100:8096)
        username: Emby username
        password: Emby password
        storage_method: How to store the token ("file" or "keyring")

    Returns:
        Tuple of (EmbyConfig with token saved, user_id)

    Raises:
        EmbyAuthError: If authentication fails
        EmbyApiError: Other API errors
        ConnectionError: If server is unreachable
    """
    # Clean server URL
    server_url = server_url.rstrip("/")

    _logger.info(f"Connecting to Emby server: {server_url}")

    # Create client and authenticate
    client = EmbyApiClient(server_url)
    try:
        token = client.authenticate(username, password)
    except EmbyAuthError:
        raise
    except EmbyApiError as e:
        if "Connection failed" in str(e) or "timed out" in str(e):
            raise ConnectionError(
                f"Cannot connect to Emby server at {server_url}. "
                "Please check the URL and ensure the server is running."
            ) from e
        raise

    # Set token on client and get user info
    client.set_token(token)
    try:
        user = client.get_user()
        user_id = user.get("Id", "")
    except EmbyApiError as e:
        _logger.warning(f"Logged in but failed to get user info: {e}")
        user_id = ""
    finally:
        client.close()

    # Save token
    config = EmbyConfig()
    config.server_url = server_url
    config.username = username
    config = save_token(config, token, storage_method)

    _logger.info(f"Successfully logged in as {username} (user_id: {user_id})")

    return config, user_id


def validate_token(server_url: str, token: str) -> bool:
    """
    Validate an access token by making a test API call.

    Args:
        server_url: Emby server URL
        token: Access token

    Returns:
        True if token is valid, False otherwise
    """
    client = EmbyApiClient(server_url, token)
    try:
        client.get_user()
        return True
    except EmbyAuthError:
        return False
    except Exception:
        return False
    finally:
        client.close()


def clear_token(config: EmbyConfig) -> EmbyConfig:
    """
    Clear the stored token from all storage backends.

    Args:
        config: Current EmbyConfig

    Returns:
        Updated EmbyConfig with token fields cleared
    """
    if config.server_url and config.username:
        delete_token_from_keyring(config.server_url, config.username)

    config.token_encrypted = ""
    return config