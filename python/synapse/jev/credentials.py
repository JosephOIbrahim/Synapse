"""One memory-only session key, with the existing environment fallback.

Never serialize these values. Keep the owner outside reloadable panel modules so
refreshing the UI does not lose a key the artist saved for this Houdini process.
"""
import os
import sys
import threading
import types

_candidate = types.ModuleType("_synapse_jev_credentials_v1")
_candidate.lock = threading.Lock()
_candidate.key = None
_SESSION = sys.modules.setdefault(_candidate.__name__, _candidate)
del _candidate


def session_key():
    with _SESSION.lock:
        return _SESSION.key


def set_session_key(value):
    """Validate before replacing; this does not check service authentication."""
    if not isinstance(value, str):
        raise ValueError("Enter a TypeSafe API key.")
    key = value.strip()
    if not key:
        raise ValueError("Enter a TypeSafe API key.")
    if len(key) > 4096 or any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise ValueError("The key contains invalid characters. Paste only the API key.")
    with _SESSION.lock:
        _SESSION.key = key


def clear_session_key():
    with _SESSION.lock:
        _SESSION.key = None


def _configured_key():
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key:
        return key
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
                value, _ = winreg.QueryValueEx(handle, "TYPESAFE_API_KEY")
                return str(value or "").strip() or None
        except Exception:
            pass
    return None


def resolve_key():
    return session_key() or _configured_key()


def key_source():
    """Public status only; never return a key fragment to the interface."""
    if session_key():
        return "session"
    return "environment" if _configured_key() else "none"
