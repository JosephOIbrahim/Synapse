"""
Synapse Multi-User Session Management

Per-user session tracking, user directory, and deployment configuration
for studio LAN/VPN deployments.

Local mode (default) does not create a SessionManager -- zero overhead
for existing single-user setups.
"""

import hashlib
import hmac
import json
import logging
import os
import ssl
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..core.determinism import deterministic_uuid
from .rbac import Role

logger = logging.getLogger("synapse.sessions")


# =========================================================================
# User Session
# =========================================================================


@dataclass
class UserSession:
    """A single authenticated user session."""
    session_id: str
    user_id: str
    role: Role
    display_name: str
    created_at: float       # time.monotonic()
    last_active: float      # Updated on each request
    client_id: str          # WebSocket client_id
    metadata: Dict = field(default_factory=dict)  # IP, user agent, etc.


# =========================================================================
# Session Manager
# =========================================================================


class SessionManager:
    """
    Thread-safe multi-user session tracker.

    One SessionManager per SynapseServer instance. Tracks active sessions,
    maps client IDs to sessions, and handles idle expiry.
    """

    def __init__(self, session_timeout: float = 3600.0):
        self._sessions: Dict[str, UserSession] = {}      # session_id -> UserSession
        self._client_map: Dict[str, str] = {}             # client_id -> session_id
        self._lock = threading.Lock()
        self._session_timeout = session_timeout
        # Monotonic counter for deterministic session IDs
        self._counter = 0

    def create_session(
        self,
        user_id: str,
        role: Role,
        client_id: str,
        display_name: str = "",
        metadata: Optional[Dict] = None,
    ) -> UserSession:
        """
        Create a new session for an authenticated user.

        Args:
            user_id: The user's ID from users.json
            role: The user's role
            client_id: WebSocket client_id
            display_name: Human-friendly name
            metadata: Optional metadata (IP, user agent, etc.)

        Returns:
            The created UserSession
        """
        now = time.monotonic()
        with self._lock:
            self._counter += 1
            session_id = deterministic_uuid(
                f"{user_id}:{self._counter}", namespace="session"
            )

            session = UserSession(
                session_id=session_id,
                user_id=user_id,
                role=role,
                display_name=display_name or user_id,
                created_at=now,
                last_active=now,
                client_id=client_id,
                metadata=metadata or {},
            )

            self._sessions[session_id] = session
            self._client_map[client_id] = session_id

            logger.info(
                "Session created: %s (user=%s, role=%s, client=%s)",
                session_id[:8], user_id, role.value, client_id,
            )
            return session

    def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get a session by its ID."""
        with self._lock:
            return self._sessions.get(session_id)

    def get_by_client(self, client_id: str) -> Optional[UserSession]:
        """Get a session by the WebSocket client_id."""
        with self._lock:
            session_id = self._client_map.get(client_id)
            if session_id:
                return self._sessions.get(session_id)
            return None

    def touch(self, session_id: str) -> None:
        """Update last_active timestamp for a session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.last_active = time.monotonic()

    def remove_session(self, session_id: str) -> None:
        """Remove a session (on disconnect or expiry)."""
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                self._client_map.pop(session.client_id, None)
                logger.info(
                    "Session removed: %s (user=%s)",
                    session_id[:8], session.user_id,
                )

    def remove_by_client(self, client_id: str) -> Optional[UserSession]:
        """Remove a session by client_id. Returns the removed session or None."""
        with self._lock:
            session_id = self._client_map.pop(client_id, None)
            if session_id:
                session = self._sessions.pop(session_id, None)
                if session:
                    logger.info(
                        "Session removed (by client): %s (user=%s)",
                        session_id[:8], session.user_id,
                    )
                    return session
            return None

    def expire_stale(self, max_idle: Optional[float] = None) -> int:
        """
        Remove sessions that have been idle longer than max_idle seconds.

        Args:
            max_idle: Override timeout (defaults to session_timeout from init)

        Returns:
            Number of sessions expired
        """
        timeout = max_idle if max_idle is not None else self._session_timeout
        now = time.monotonic()
        expired_count = 0

        with self._lock:
            to_remove = [
                sid for sid, s in self._sessions.items()
                if (now - s.last_active) > timeout
            ]
            for sid in to_remove:
                session = self._sessions.pop(sid, None)
                if session:
                    self._client_map.pop(session.client_id, None)
                    expired_count += 1
                    logger.info(
                        "Session expired: %s (user=%s, idle=%.0fs)",
                        sid[:8], session.user_id, now - session.last_active,
                    )

        return expired_count

    def active_sessions(self) -> List[UserSession]:
        """Return list of active sessions, sorted by user_id for determinism."""
        with self._lock:
            return sorted(
                self._sessions.values(),
                key=lambda s: s.user_id,
            )

    @property
    def count(self) -> int:
        """Number of active sessions."""
        with self._lock:
            return len(self._sessions)


# =========================================================================
# User Directory
# =========================================================================

def hash_api_key(key: str) -> str:
    """
    Hash an API key for storage in users.json.

    Returns 'sha256:<hex_digest>' format.
    """
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def load_user_directory(path: Optional[Path] = None) -> Dict[str, dict]:
    """
    Load users.json, return dict keyed by user_id.

    Expected format:
    {
        "users": [
            {"id": "alice", "name": "Alice Chen", "role": "lead", "key_hash": "sha256:abc..."},
            ...
        ]
    }

    Returns:
        Dict mapping user_id -> user record
    """
    if path is None:
        path = Path.home() / ".synapse" / "users.json"

    if not path.exists():
        logger.info("No user directory found at %s -- anonymous access only", path)
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Couldn't load user directory %s: %s", path, e)
        return {}

    users = {}
    for entry in data.get("users", []):
        uid = entry.get("id", "")
        if uid:
            users[uid] = entry

    logger.info("Loaded %d users from %s", len(users), path)
    return users


def lookup_user_by_key(token: str, users: Dict[str, dict]) -> Optional[dict]:
    """
    Find user whose key_hash matches SHA-256 of the provided token.

    Uses hmac.compare_digest for constant-time comparison.

    Args:
        token: The raw API key from the client
        users: User directory (from load_user_directory)

    Returns:
        User record dict if found, None otherwise
    """
    if not token or not users:
        return None

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    for user in sorted(users.values(), key=lambda u: u.get("id", "")):
        stored_hash = user.get("key_hash", "")
        # Strip "sha256:" prefix if present
        if stored_hash.startswith("sha256:"):
            stored_hash = stored_hash[7:]

        if hmac.compare_digest(token_hash, stored_hash):
            return user

    return None


# =========================================================================
# Deployment Configuration
# =========================================================================


@dataclass
class DeployConfig:
    """
    Deployment configuration for Synapse server.

    Modes:
    - local: Single user, localhost only, no auth, no RBAC (default)
    - studio-lan: Multi-user, LAN-accessible, auth required, RBAC enabled
    - studio-vpn: Same as LAN + TLS encryption
    """
    mode: str = "local"               # "local" | "studio-lan" | "studio-vpn"
    bind: str = "127.0.0.1"           # "0.0.0.0" for studio modes
    port: int = 9999
    auth_required: bool = False       # True for studio modes
    users_file: str = ""              # Path to users.json
    tls_enabled: bool = False
    tls_certfile: str = ""
    tls_keyfile: str = ""
    default_role: str = "artist"      # Fallback role if user not in directory
    session_timeout: float = 3600.0   # 1 hour idle timeout

    def __post_init__(self):
        # Defaults based on mode
        if self.mode == "studio-lan":
            if self.bind == "127.0.0.1":
                self.bind = "0.0.0.0"
            self.auth_required = True
        elif self.mode == "studio-vpn":
            if self.bind == "127.0.0.1":
                self.bind = "0.0.0.0"
            self.auth_required = True
            self.tls_enabled = True

        # Default users file
        if not self.users_file:
            self.users_file = str(Path.home() / ".synapse" / "users.json")


def load_deploy_config(path: Optional[str] = None) -> DeployConfig:
    """
    Load deployment configuration.

    Sources (in priority order):
    1. SYNAPSE_DEPLOY_CONFIG env var (path to JSON file)
    2. Explicit path parameter
    3. ~/.synapse/deploy.json
    4. Default (local mode)

    Returns:
        DeployConfig instance
    """
    config_path = path or os.environ.get("SYNAPSE_DEPLOY_CONFIG", "")
    if not config_path:
        default_path = Path.home() / ".synapse" / "deploy.json"
        if default_path.exists():
            config_path = str(default_path)

    if not config_path or not Path(config_path).exists():
        # Check SYNAPSE_DEPLOY_MODE env var for mode-only config
        mode = os.environ.get("SYNAPSE_DEPLOY_MODE", "local").strip().lower()
        return DeployConfig(mode=mode)

    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Couldn't load deploy config %s: %s -- using defaults", config_path, e)
        return DeployConfig()

    return DeployConfig(
        mode=data.get("mode", "local"),
        bind=data.get("bind", "127.0.0.1"),
        port=data.get("port", 9999),
        auth_required=data.get("auth_required", False),
        users_file=data.get("users_file", ""),
        tls_enabled=data.get("tls_enabled", False),
        tls_certfile=data.get("tls_certfile", ""),
        tls_keyfile=data.get("tls_keyfile", ""),
        default_role=data.get("default_role", "artist"),
        session_timeout=data.get("session_timeout", 3600.0),
    )


# =========================================================================
# TLS Helper
# =========================================================================


def create_tls_context(certfile: str, keyfile: str) -> ssl.SSLContext:
    """
    Create a TLS context for secure WebSocket connections.

    Args:
        certfile: Path to PEM certificate file
        keyfile: Path to PEM private key file

    Returns:
        Configured ssl.SSLContext
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile, keyfile)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx
