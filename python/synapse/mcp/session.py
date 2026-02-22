"""
MCP Session Manager

Manages MCP client sessions with unique Mcp-Session-Id tokens.
Thread-safe for concurrent hwebserver requests.
"""

import threading
import time
from typing import Dict, Optional


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
        "session_id", "client_info", "created_at",
        "protocol_version", "initialized", "project_context",
    )

    def __init__(self, session_id: str, client_info: dict):
        self.session_id = session_id
        self.client_info = client_info
        self.created_at = time.time()
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
    """Manages MCP client sessions. Thread-safe."""

    def __init__(self):
        self._sessions: Dict[str, MCPSession] = {}
        self._lock = threading.Lock()

    def create_session(self, client_info: Optional[dict] = None) -> str:
        """Create a new session and return its ID."""
        session_id = _next_session_id()
        session = MCPSession(session_id, client_info or {})
        with self._lock:
            self._sessions[session_id] = session
        return session_id

    def get_session(self, session_id: str) -> Optional[MCPSession]:
        """Get a session by ID, or None if not found."""
        with self._lock:
            return self._sessions.get(session_id)

    def mark_initialized(self, session_id: str) -> bool:
        """Mark a session as initialized. Returns False if session not found."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.initialized = True
                return True
            return False

    def destroy_session(self, session_id: str) -> bool:
        """Remove a session. Returns False if session not found."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    @property
    def active_count(self) -> int:
        """Number of active sessions."""
        with self._lock:
            return len(self._sessions)
