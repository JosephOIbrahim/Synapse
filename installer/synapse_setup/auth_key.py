"""Mint the local API key at install time (SIDEFXCTO-1 / R-011).

``server/auth.py`` reads ``SYNAPSE_API_KEY`` then ``~/.synapse/auth.key``; with
neither, authentication is off. No installer used to create the key, so a fresh
seat ran the ``/synapse`` and ``/mcp`` surfaces authentication-less. Setup mints
one here. The key is user data: an existing key is never rotated or rewritten,
and uninstall never removes it.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from .safety import atomic_write

AUTH_KEY_RELPATH = Path(".synapse") / "auth.key"


def _has_key(path: Path) -> bool:
    """True when the file holds at least one non-empty, non-comment line."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return True
    except (OSError, UnicodeDecodeError):
        return False
    return False


def ensure_auth_key(home) -> dict:
    """Create ``<home>/.synapse/auth.key`` when no key exists.

    Returns ``{"status": "CREATED"|"PRESENT", "path": str(path)}``. Never
    rotates or rewrites an existing key — rotation is an operator action, and
    overwriting it would silently break every configured client.
    """
    path = Path(home) / AUTH_KEY_RELPATH
    if path.exists() and _has_key(path):
        return {"status": "PRESENT", "path": str(path)}
    key = secrets.token_urlsafe(32)
    atomic_write(path, (key + "\n").encode("ascii"))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows only maps the read-only bit; the file is per-user data.
    return {"status": "CREATED", "path": str(path)}
