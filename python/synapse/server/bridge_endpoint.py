"""Discoverable bridge endpoint — self-healing port discovery.

The SYNAPSE server PREFERS port 9999 but fails over to another port when
:9999 is held (e.g. a stale 26h-old Houdini zombie). When that happens the
live server tracks its real bound port in ``SynapseServer._actual_port`` — but
every client is hardcoded to 9999, so clients connect to the dead zombie
instead of the live server.

This module closes that gap. The server PUBLISHES its real bound port to a
sidecar JSON file under the user's home directory; clients RESOLVE the sidecar
to find the live port (falling back to 9999 / $SYNAPSE_PORT when no sidecar
exists, so behavior with no sidecar is EXACTLY today's behavior).

Design invariants:
  * Zero ``hou`` — pure Python, importable in any process.
  * The sidecar path resolves IDENTICALLY in the Houdini server process and
    the separate MCP-server process (both run as the same OS user), so the
    anchor is the user's HOME directory, never a repo-relative path.
  * Best-effort: a sidecar read/write failure must NEVER break server startup
    or a client connect. Every public function swallows its own errors and
    falls back to current behavior.
  * Backward-compatible: with no sidecar present, ``resolve_endpoint`` returns
    exactly ``(localhost, 9999 / $SYNAPSE_PORT)``.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Optional, Tuple

__all__ = [
    "bridge_file",
    "publish_endpoint",
    "resolve_endpoint",
    "clear_endpoint",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
]

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9999

# Env overrides
_ENV_BRIDGE_FILE = "SYNAPSE_BRIDGE_FILE"
_ENV_PORT = "SYNAPSE_PORT"


def _default_port() -> int:
    """Resolve the fallback port from $SYNAPSE_PORT, else 9999.

    Never raises — a malformed $SYNAPSE_PORT falls back to 9999.
    """
    raw = os.environ.get(_ENV_PORT, "").strip()
    if raw:
        try:
            return int(raw)
        except (ValueError, TypeError):
            pass
    return DEFAULT_PORT


def bridge_file() -> str:
    """Return the sidecar path.

    ``$SYNAPSE_BRIDGE_FILE`` if set, else
    ``~/.synapse/bridge.json``. The user-home anchor is deliberate: the
    Houdini server process and the separate MCP-server process share the same
    OS user but have different cwds, so a repo-relative path would not resolve
    to the same file in both. ``~/.synapse/`` is already the shared SYNAPSE
    config dir (auth.key lives there too).
    """
    override = os.environ.get(_ENV_BRIDGE_FILE, "").strip()
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".synapse", "bridge.json")


def _pid_alive(pid: Optional[int]) -> bool:
    """Best-effort liveness check for a pid. Unknown => treat as alive.

    Returns True when ``pid`` is None (no pid recorded — can't disprove
    liveness, so don't strand a valid sidecar). Returns False only when the
    pid is recorded AND we can positively determine it is not running.
    """
    if pid is None:
        return True
    try:
        pid = int(pid)
    except (ValueError, TypeError):
        # Malformed pid — can't disprove liveness.
        return True
    if pid <= 0:
        return False
    if os.name == "nt":
        # Windows has NO signal delivery. CPython implements os.kill() on nt
        # via TerminateProcess(), passing the signal number as the process
        # EXIT CODE — so os.kill(pid, 0) does not probe liveness, it KILLS
        # pid with exit code 0. The previous implementation did exactly that
        # to whatever process the sidecar named, including a live Houdini,
        # and self-terminated the pytest runner in tests/test_bridge_endpoint.py.
        # Probe with OpenProcess/GetExitCodeProcess. Never signal on nt.
        try:
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000  # Vista+
            STILL_ACTIVE = 259
            ERROR_ACCESS_DENIED = 5

            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            # restype MUST be HANDLE — the default c_int truncates on 64-bit.
            k32.OpenProcess.restype = wintypes.HANDLE
            k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            k32.GetExitCodeProcess.restype = wintypes.BOOL
            k32.GetExitCodeProcess.argtypes = (
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.DWORD),
            )
            k32.CloseHandle.restype = wintypes.BOOL
            k32.CloseHandle.argtypes = (wintypes.HANDLE,)

            handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                # ACCESS_DENIED => the process exists, we just cannot query it
                # => alive. Anything else (typically ERROR_INVALID_PARAMETER)
                # => no such pid => dead.
                return ctypes.get_last_error() == ERROR_ACCESS_DENIED
            try:
                code = wintypes.DWORD()
                if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    # Cannot determine — do not strand a valid sidecar.
                    return True
                # Known caveat: a process that legitimately exited with code
                # 259 reads as alive. That direction matches this function's
                # documented contract (unknown => treat as alive).
                return code.value == STILL_ACTIVE
            finally:
                k32.CloseHandle(handle)
        except Exception:
            return True
    else:
        # POSIX: signal 0 probes existence without delivering a signal.
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            return True
        except (OSError, ProcessLookupError):
            return False
        except Exception:
            return True


def publish_endpoint(
    host: str,
    port: int,
    *,
    pid: Optional[int] = None,
    protocol: str = "4.0.0",
) -> bool:
    """Atomically publish the live endpoint to the sidecar.

    Writes ``{host, port, pid, ts, protocol}`` as JSON via a temp-file +
    ``os.replace`` so a concurrent reader never sees a partial file and no
    ``.tmp`` is left behind on success.

    Best-effort: returns True on success, False on any failure. NEVER raises —
    a publish failure must not break server startup.
    """
    try:
        path = bridge_file()
        directory = os.path.dirname(path) or "."
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError:
            pass

        payload = {
            "host": host,
            "port": int(port),
            "pid": int(pid) if pid is not None else None,
            "ts": datetime.now(timezone.utc).isoformat(),
            "protocol": protocol,
        }
        data = json.dumps(payload, sort_keys=True).encode("utf-8")

        # Write to a temp file in the SAME directory (os.replace is only
        # atomic within a filesystem), then atomically swap into place.
        fd, tmp_path = tempfile.mkstemp(
            prefix=".bridge-", suffix=".tmp", dir=directory
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
            os.replace(tmp_path, path)
        except Exception:
            # Clean up the temp file on any failure so no .tmp is left behind.
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            return False
        return True
    except Exception:
        return False


def resolve_endpoint(default_port: Optional[int] = None) -> Tuple[str, int]:
    """Resolve the live endpoint, falling back to current behavior.

    Reads the sidecar; if it parses AND its pid is still alive (or no pid was
    recorded), returns its ``(host, port)``. Otherwise — no sidecar, malformed
    sidecar, dead pid, or ANY error — returns the fallback
    ``(localhost, default_port or int($SYNAPSE_PORT or 9999))``.

    This is the load-bearing backward-compat guarantee: with no sidecar
    present the result is EXACTLY today's behavior. NEVER raises.
    """
    fallback_port = default_port if default_port is not None else _default_port()
    fallback = (DEFAULT_HOST, fallback_port)

    try:
        path = bridge_file()
        if not os.path.exists(path):
            return fallback

        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        if not raw.strip():
            return fallback

        data = json.loads(raw)
        if not isinstance(data, dict):
            return fallback

        host = data.get("host")
        port = data.get("port")
        if not host or port is None:
            return fallback
        try:
            port = int(port)
        except (ValueError, TypeError):
            return fallback

        # Stale-pid guard: if the sidecar names a dead pid, treat as stale.
        if not _pid_alive(data.get("pid")):
            return fallback

        return (str(host), port)
    except Exception:
        return fallback


def clear_endpoint(pid: Optional[int] = None) -> bool:
    """Remove the sidecar IF it belongs to this pid.

    When ``pid`` is provided, the sidecar is removed only if its recorded pid
    matches — so a server tearing down can't clobber another live server's
    entry. When ``pid`` is None, the sidecar is removed unconditionally
    (explicit caller intent).

    Best-effort: returns True if the sidecar was removed, False otherwise.
    NEVER raises.
    """
    try:
        path = bridge_file()
        if not os.path.exists(path):
            return False

        if pid is not None:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                recorded = data.get("pid") if isinstance(data, dict) else None
                # If the sidecar belongs to a different live server, don't
                # clobber it. A None/unreadable recorded pid is treated as
                # "ours" only when it equals our pid (i.e. never) — so an
                # entry with no pid is left in place to be safe.
                if recorded is None or int(recorded) != int(pid):
                    return False
            except Exception:
                # Can't confirm ownership — don't remove someone else's entry.
                return False

        try:
            os.remove(path)
            return True
        except OSError:
            return False
    except Exception:
        return False
