"""In-flight render session registry — the bounded half of the Indie render fix.

When a tool-level render exceeds its bounded wait, the WS/bridge caller is
released with a ``render_in_progress`` token while the render keeps running
on Houdini's main thread. This registry is where the running job records its
outcome and where later ``{"poll": token}`` calls read it back.

Pure Python, thread-safe, bounded (finished sessions beyond the cap are
evicted oldest-first; running sessions are never evicted). No ``hou`` import.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Dict, Optional, Tuple

_MAX_SESSIONS = 32

_lock = threading.Lock()
_sessions: Dict[str, Dict] = {}
_order: list = []  # insertion order, for active_session() recency + eviction


def start_session(meta: Optional[Dict] = None) -> str:
    """Register a new running render session; returns its token."""
    token = uuid.uuid4().hex[:12]
    with _lock:
        _sessions[token] = {
            "token": token,
            "state": "running",
            "started_at": time.time(),
            "finished_at": None,
            "meta": dict(meta or {}),
            "result": None,
            "error": None,
            "error_type": None,
        }
        _order.append(token)
        _evict_finished_locked()
    return token


def _evict_finished_locked() -> None:
    while len(_order) > _MAX_SESSIONS:
        for i, tok in enumerate(_order):
            if _sessions[tok]["state"] != "running":
                _order.pop(i)
                _sessions.pop(tok, None)
                break
        else:
            break  # every session is running (pathological) — keep them all


def complete_session(token: str, result: Dict) -> None:
    with _lock:
        s = _sessions.get(token)
        if s is None:
            return
        s["state"] = "done"
        s["result"] = result
        s["finished_at"] = time.time()


def fail_session(token: str, exc: BaseException) -> None:
    """Record a failed render. Only the message + type NAME are kept — the
    exception OBJECT would pin its traceback (worker frames, payload) in the
    registry until eviction (crucible F6). The bounded caller that needs a
    faithful re-raise gets the object from the wrapper's local outcome
    holder, never from here."""
    with _lock:
        s = _sessions.get(token)
        if s is None:
            return
        s["state"] = "error"
        s["error"] = str(exc)
        s["error_type"] = type(exc).__name__
        s["finished_at"] = time.time()


def get_session(token: str) -> Optional[Dict]:
    with _lock:
        s = _sessions.get(token)
        return dict(s) if s else None


def active_session() -> Optional[Tuple[str, Dict]]:
    """Most recent still-running session, or None."""
    with _lock:
        for tok in reversed(_order):
            s = _sessions.get(tok)
            if s is not None and s["state"] == "running":
                return tok, dict(s)
    return None


def summary() -> list:
    """Lightweight list for status surfaces (no results, no exceptions)."""
    with _lock:
        return [
            {
                "token": _sessions[t]["token"],
                "state": _sessions[t]["state"],
                "started_at": _sessions[t]["started_at"],
                "finished_at": _sessions[t]["finished_at"],
                "meta": dict(_sessions[t]["meta"]),
            }
            for t in _order
            if t in _sessions
        ]


def as_status_payload(sess: Dict) -> Dict:
    """Shape a session snapshot for the poll response."""
    state = sess["state"]
    out = {
        "status": "render_in_progress" if state == "running" else state,
        "render_token": sess["token"],
        "started_at": sess["started_at"],
        "elapsed_s": round(
            (sess["finished_at"] or time.time()) - sess["started_at"], 2
        ),
        "meta": dict(sess.get("meta") or {}),
    }
    if state == "done":
        out["result"] = sess["result"]
    elif state == "error":
        out["error"] = sess["error"]
        out["error_type"] = sess.get("error_type")
    else:
        out["note"] = (
            "Render still holding Houdini's main thread — poll again with "
            '{"poll": "%s"}.' % sess["token"]
        )
    return out


def reset() -> None:
    """Test helper — clear the registry."""
    with _lock:
        _sessions.clear()
        _order.clear()
