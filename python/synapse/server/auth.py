"""
Synapse Authentication

API key authentication for WebSocket and hwebserver transports.
Provides a simple shared-secret model suitable for localhost and
studio LAN deployments.

Key sources (checked in order):
1. SYNAPSE_API_KEY environment variable
2. ~/.synapse/auth.key file (first non-empty line)
3. No key configured -> authentication disabled (backward compat)

Usage in transport:
    from .auth import get_auth_key, authenticate

    key = get_auth_key()          # None means auth disabled
    ok  = authenticate(token, key)  # True if key is None OR token matches
"""

import hashlib
import hmac
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("synapse.auth")

# Auth protocol constants
AUTH_COMMAND_TYPE = "authenticate"
AUTH_REQUIRED_TYPE = "auth_required"

# Cached key (module-level, loaded once)
_cached_key: Optional[str] = None
_key_loaded: bool = False


def _load_key_from_file() -> Optional[str]:
    """Load API key from ~/.synapse/auth.key (first non-empty line)."""
    key_path = Path.home() / ".synapse" / "auth.key"
    try:
        if key_path.exists():
            text = key_path.read_text(encoding="utf-8").strip()
            # First non-empty, non-comment line
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    except (OSError, PermissionError) as e:
        logger.warning("Couldn't read auth key file %s: %s", key_path, e)
    return None


def get_auth_key() -> Optional[str]:
    """
    Get the configured API key, or None if authentication is disabled.

    Priority: SYNAPSE_API_KEY env var > ~/.synapse/auth.key file > None
    """
    global _cached_key, _key_loaded
    if _key_loaded:
        return _cached_key

    # 1. Environment variable
    env_key = os.environ.get("SYNAPSE_API_KEY", "").strip()
    if env_key:
        _cached_key = env_key
        _key_loaded = True
        logger.info("Authentication enabled (source: environment variable)")
        return _cached_key

    # 2. Key file
    file_key = _load_key_from_file()
    if file_key:
        _cached_key = file_key
        _key_loaded = True
        logger.info("Authentication enabled (source: ~/.synapse/auth.key)")
        return _cached_key

    # 3. No key = auth disabled
    _cached_key = None
    _key_loaded = True
    logger.info("Authentication disabled (no SYNAPSE_API_KEY or auth.key found)")
    return None


def reset_auth_cache():
    """Reset the cached key (for testing or key rotation)."""
    global _cached_key, _key_loaded
    _cached_key = None
    _key_loaded = False


def authenticate(token: str, expected_key: Optional[str] = None) -> bool:
    """
    Authenticate a client token against the expected key.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        token: The client-provided API key
        expected_key: The server's expected key. If None, uses get_auth_key().

    Returns:
        True if authenticated (or if auth is disabled)
    """
    if expected_key is None:
        expected_key = get_auth_key()

    # No key configured = auth disabled = always pass
    if expected_key is None:
        return True

    if not token:
        return False

    # Constant-time comparison via hmac.compare_digest
    return hmac.compare_digest(token.encode("utf-8"), expected_key.encode("utf-8"))


def hash_key_for_log(key: str) -> str:
    """Hash an API key for safe logging (first 8 chars of SHA-256)."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
