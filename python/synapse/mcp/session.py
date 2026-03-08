"""
MCP Session Manager

Manages MCP client sessions with unique Mcp-Session-Id tokens.
Thread-safe for concurrent hwebserver requests.

Sessions track last_activity for TTL-based expiry. On session end
(explicit destroy or reaper sweep), Living Memory hooks run to
persist context — mirroring the WebSocket disconnect behavior.
"""

import logging
import threading
import time
from typing import Dict, Optional


logger = logging.getLogger("synapse.mcp.session")

_MAX_SESSIONS = 100
_DEFAULT_SESSION_TTL = 1800  # 30 minutes in seconds

# He2025: deterministic session IDs (sequential counter, not uuid4)
_session_counter = 0
_counter_lock = threading.Lock()


def _next_session_id() -> str:
    """Generate a sequential, deterministic session ID."""
    global _session_counter
    with _counter_lock:
        _session_counter += 1
        return f"mcp-session-{_session_counter:06d}"


class MCPSession:
    """Single MCP session state."""

    __slots__ = (
        "session_id", "client_info", "created_at", "last_activity",
        "protocol_version", "initialized", "project_context",
    )

    def __init__(self, session_id: str, client_info: dict):
        self.session_id = session_id
        self.client_info = client_info
        self.created_at = time.time()
        self.last_activity = self.created_at
        self.protocol_version = "2025-06-18"
        self.initialized = False
        self.project_context = None

    def to_dict(self) -> dict:
        return {
            "client_info": self.client_info,
            "created_at": self.created_at,
            "initialized": self.initialized,
            "protocol_version": self.protocol_version,
            "session_id": self.session_id,
        }


class MCPSessionManager:
    """Manages MCP client sessions. Thread-safe.

    Args:
        session_ttl_seconds: Inactivity timeout before a session is reaped.
            Defaults to 1800 (30 minutes).
    """

    def __init__(self, session_ttl_seconds: int = _DEFAULT_SESSION_TTL):
        self._sessions: Dict[str, MCPSession] = {}
        self._lock = threading.Lock()
        self._ttl = session_ttl_seconds

    def create_session(self, client_info: Optional[dict] = None) -> str:
        """Create a new session. Sweeps expired sessions first."""
        self._sweep_expired()
        session_id = _next_session_id()
        session = MCPSession(session_id, client_info or {})
        with self._lock:
            self._sessions[session_id] = session
        return session_id

    def _sweep_expired(self):
        """Remove sessions past TTL (by last_activity) and enforce max count.

        Living Memory cleanup hooks run for every removed session.
        """
        now = time.time()
        with self._lock:
            # Collect expired sessions (inactivity-based)
            expired = [
                (sid, s) for sid, s in self._sessions.items()
                if (now - s.last_activity) > self._ttl
            ]
            for sid, session in expired:
                del self._sessions[sid]

            # Enforce max count (remove oldest-activity first)
            overflow: list = []
            if len(self._sessions) > _MAX_SESSIONS:
                by_activity = sorted(
                    self._sessions.items(), key=lambda x: x[1].last_activity,
                )
                excess = len(self._sessions) - _MAX_SESSIONS
                for sid, session in by_activity[:excess]:
                    overflow.append((sid, session))
                    del self._sessions[sid]

        # Run cleanup OUTSIDE the lock to avoid blocking other callers
        for _sid, session in expired:
            self._run_session_cleanup(session)
        for _sid, session in overflow:
            self._run_session_cleanup(session)

    def get_session(self, session_id: str) -> Optional[MCPSession]:
        """Get a session by ID, or None if not found.

        Updates last_activity on hit so the session stays alive.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.last_activity = time.time()
            return session

    def mark_initialized(self, session_id: str) -> bool:
        """Mark a session as initialized. Returns False if session not found."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.initialized = True
                return True
            return False

    def destroy_session(self, session_id: str) -> bool:
        """Remove a session. Runs Living Memory cleanup before removal.

        Returns False if session not found.
        """
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is not None:
            self._run_session_cleanup(session)
            return True
        return False

    def reap_expired(self) -> int:
        """Reap sessions that exceeded TTL (inactivity-based).

        Returns the number of sessions reaped. Safe to call from a
        periodic timer or external health-check loop.
        """
        now = time.time()
        reaped: list = []
        with self._lock:
            expired_ids = [
                sid for sid, s in self._sessions.items()
                if (now - s.last_activity) > self._ttl
            ]
            for sid in expired_ids:
                reaped.append(self._sessions.pop(sid))

        # Cleanup outside lock
        for session in reaped:
            self._run_session_cleanup(session)

        if reaped:
            logger.info("Reaped %d expired MCP session(s)", len(reaped))
        return len(reaped)

    # ------------------------------------------------------------------
    # Living Memory cleanup (mirrors WebSocket disconnect hooks)
    # ------------------------------------------------------------------

    @staticmethod
    def _run_session_cleanup(session: MCPSession) -> None:
        """Run Living Memory hooks on session end.

        Best-effort: failures are logged but never propagate. The method
        mirrors the WebSocket disconnect handler in websocket.py so that
        MCP sessions leave the same context trail as interactive ones.
        """
        try:
            import os
            import time as _time

            try:
                import hou
            except ImportError:
                return  # Not inside Houdini -- skip cleanup

            from synapse.memory.scene_memory import (
                ensure_scene_structure,
                write_session_end,
            )
            from synapse.memory.agent_state import log_session, suspend_all_tasks

            hip_path = hou.hipFile.path()
            job_path = hou.getenv("JOB", os.path.dirname(hip_path))
            paths = ensure_scene_structure(hip_path, job_path)

            # Suspend pending agent tasks
            agent_usd = paths.get("agent_usd", "")
            if agent_usd and os.path.exists(agent_usd):
                suspend_all_tasks(agent_usd)
                log_session(agent_usd, {
                    "end_time": _time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", _time.gmtime(),
                    ),
                    "summary_text": "MCP session ended (id: {})".format(
                        getattr(session, "session_id", "unknown"),
                    ),
                })

            # Write session end to memory.md
            write_session_end(paths["scene_dir"], {
                "stopped_at": _time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", _time.gmtime(),
                ),
            })
        except ImportError:
            pass  # Memory modules not available
        except Exception as exc:
            logger.warning("Living Memory cleanup error: %s", exc)

    @property
    def active_count(self) -> int:
        """Number of active sessions."""
        with self._lock:
            return len(self._sessions)
