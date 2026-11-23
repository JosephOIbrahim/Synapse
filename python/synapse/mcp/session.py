"""
MCP Session Manager

Manages MCP client sessions with unique Mcp-Session-Id tokens.
Thread-safe for concurrent hwebserver requests.

Sessions track last_activity for TTL-based expiry. When a session ends
(DELETE /mcp, or the expiry/overflow sweep that every initialize runs), its
session-end record is written to the scene's agent.usd -- but never on the
thread that ended the session. ``_SessionEndRecorder`` below owns that work
and states which thread does what.
"""

import logging
import os
import queue
import threading
import time
from typing import Any, Dict, Iterable, Optional, Tuple

try:
    # Read ONLY inside _read_scene_facts, which runs on Houdini's main thread.
    import hou
except ImportError:
    hou = None


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
        "protocol_version", "initialized", "project_context", "preflight_due",
    )

    def __init__(self, session_id: str, client_info: dict):
        self.session_id = session_id
        self.client_info = client_info
        self.created_at = time.time()
        self.last_activity = self.created_at
        self.protocol_version = "2025-06-18"
        self.initialized = False
        self.project_context = None
        # Level 1, R-5: the session's next change is checked first (server/preflight_gate.py)
        self.preflight_due = True

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

        The removed sessions' end records are handed to the recorder; this
        thread (initialize's request thread) does no hou or file work for them.
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

        # Hand off OUTSIDE the lock to avoid blocking other callers
        _schedule_session_end([sid for sid, _s in expired + overflow])

    def get_session(self, session_id: str) -> Optional[MCPSession]:
        """Get a session by ID, or None if not found.

        Updates last_activity on hit so the session stays alive. A lookup
        never sweeps and never ends a session.
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
        """Remove a session (DELETE /mcp) and hand its end record to the recorder.

        Returns False if session not found. Returns without waiting for the
        record: this thread does no hou or file work for it.
        """
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is not None:
            _schedule_session_end([session.session_id])
            return True
        return False

    def reap_expired(self) -> int:
        """Reap sessions that exceeded TTL (inactivity-based).

        Returns the number of sessions reaped. Like the sweep, it only hands
        the end records to the recorder, so any thread may call it.
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

        _schedule_session_end([s.session_id for s in reaped])

        if reaped:
            logger.info("Reaped %d expired MCP session(s)", len(reaped))
        return len(reaped)

    @property
    def active_count(self) -> int:
        """Number of active sessions."""
        with self._lock:
            return len(self._sessions)


# ----------------------------------------------------------------------
# Session-end record
# ----------------------------------------------------------------------
#
# The record this writes is the one the WebSocket disconnect hook writes
# (server/websocket.py): suspend the scene's pending agent tasks and add a
# /SYNAPSE/agent/session_history entry to agent.usd. It used to run inline on
# the thread that ended the session -- an hwebserver worker for both
# initialize's sweep and DELETE /mcp -- calling hou.hipFile.path() and
# hou.getenv() off Houdini's main thread, then ensure_scene_structure (which
# creates folders and seed files, possibly on a synced drive, and itself reads
# hou: store.hip_is_unsaved and store._safe_unsaved_base) and the agent.usd
# writes, all inside the request.

_RECORDER_THREAD_NAME = "synapse-mcp-session-end"


class _SessionEndRecorder:
    """Writes MCP session-end records. Four hops, each on a thread allowed to do it.

    1. Request thread (initialize's sweep, DELETE /mcp): ``schedule`` puts a
       job on an unbounded queue. It never waits and calls no hou.
    2. Recorder thread (one daemon thread, FIFO): posts ``_capture`` with
       ``hdefereval.executeDeferred`` and does not wait for it. The post is made
       here, not on the request thread, because the vendor's registration calls
       ``hou.ui.addEventLoopCallback`` when no deferred callback is active, and
       that waits for the HOM lock the main thread may be holding
       (hdefereval.py, ``_queueDeferred``).
    3. Houdini's main thread: ``_capture`` reads the scene's hip path and, for
       an untitled hip, whether it was ever saved and this launch's unsaved
       notes folder. Reads only -- no filesystem work -- then queues the facts.
    4. Recorder thread: finds the scene's EXISTING ``claude/agent.usd`` and
       writes the record. No hou.

    One thread writes every MCP session-end record, so they never race each
    other. agent_state's writers take no file lock (none of its callers do),
    so this cannot serialize against agent.usd writers elsewhere -- the same
    as before, when these writes ran on concurrent request threads.

    If the main thread never runs the capture (frozen, or no event loop as in
    hython), no record is written and nothing waits for it.
    """

    def __init__(self):
        self._jobs: "queue.Queue[Tuple[Any, ...]]" = queue.Queue()
        self._thread_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    def schedule(self, session_ids: Tuple[str, ...], ended_at: str) -> None:
        """Request thread: queue the record. Never waits; calls no hou."""
        self._jobs.put(("post", session_ids, ended_at))
        self._ensure_thread()

    def wait_idle(self, timeout: float) -> bool:
        """True once every queued job has been handled; False on timeout.

        For tests and diagnostics only. A posted capture the main thread has
        not run yet is not a queued job.
        """
        deadline = time.monotonic() + timeout
        with self._jobs.all_tasks_done:
            while self._jobs.unfinished_tasks:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._jobs.all_tasks_done.wait(remaining)
        return True

    def _ensure_thread(self) -> None:
        with self._thread_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            thread = threading.Thread(
                target=self._run, name=_RECORDER_THREAD_NAME, daemon=True,
            )
            thread.start()
            self._thread = thread

    def _run(self) -> None:
        while True:
            job = self._jobs.get()
            try:
                if job[0] == "post":
                    self._post_capture(job[1], job[2])
                else:
                    _write_session_end(job[1], job[2], job[3])
            except Exception:
                logger.warning(
                    "MCP session-end record for %s was not written", job[1],
                    exc_info=True,
                )
            finally:
                self._jobs.task_done()

    def _post_capture(self, session_ids: Tuple[str, ...], ended_at: str) -> None:
        """Recorder thread: post the main-thread read. Does not wait for it."""
        import hdefereval

        detector, unsaved_base_of = _scene_fact_helpers()

        def _capture():
            # Houdini's main thread. hou reads only; no filesystem work.
            try:
                facts = _read_scene_facts(detector, unsaved_base_of)
            except Exception:
                logger.warning(
                    "MCP session-end record for %s skipped: could not read the "
                    "scene path", session_ids, exc_info=True,
                )
                return
            self._jobs.put(("write", session_ids, ended_at, facts))

        hdefereval.executeDeferred(_capture)


_RECORDER = _SessionEndRecorder()


def _schedule_session_end(session_ids: Iterable[str]) -> None:
    """Hand ended sessions to the recorder. Never waits; calls no hou.

    Outside Houdini (no ``hou``, or no ``hdefereval`` to reach the main thread)
    nothing is recorded, as before: there is no scene to record into.
    """
    session_ids = tuple(session_ids)
    if not session_ids or hou is None:
        return
    try:
        import hdefereval  # noqa: F401 -- presence only; posting is the recorder's
    except ImportError:
        logger.debug(
            "No hdefereval: MCP session-end record for %s skipped", session_ids,
        )
        return
    ended_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _RECORDER.schedule(session_ids, ended_at)


def _scene_fact_helpers():
    """Recorder thread: import what ``_read_scene_facts`` calls, so the main
    thread imports nothing. Either may be None when its module is missing."""
    try:
        from synapse.memory.store import hip_is_unsaved
    except ImportError:
        logger.debug("synapse.memory.store unavailable; untitled.hip means unsaved")
        hip_is_unsaved = None
    try:
        from synapse.host.memory_lifecycle import existing_unsaved_base
    except ImportError:
        logger.debug("synapse.host.memory_lifecycle unavailable; no unsaved notes folder")
        existing_unsaved_base = None
    return hip_is_unsaved, existing_unsaved_base


def _read_scene_facts(detector, unsaved_base_of) -> Dict[str, Any]:
    """Main thread only: the hou facts the record's address needs.

    ``hou.hipFile.path()``; for an untitled hip, ``store.hip_is_unsaved``
    (``hou.hipFile.isNewFile()``) and ``memory_lifecycle.existing_unsaved_base``
    (``hou.text.expandString``), which never creates a folder. The same
    detector and unsaved base ``scene_memory.resolve_hip_dir`` uses.
    """
    hip_path = str(hou.hipFile.path())
    if detector is not None:
        unsaved = bool(detector(hip_path, hou))
    else:
        unsaved = os.path.basename(hip_path) == "untitled.hip"
    unsaved_base = None
    if unsaved and unsaved_base_of is not None:
        base = unsaved_base_of()
        unsaved_base = str(base) if base is not None else None
    return {"hip_path": hip_path, "unsaved": unsaved, "unsaved_base": unsaved_base}


def _scene_memory_parent(facts: Dict[str, Any]) -> Optional[str]:
    """Recorder thread, no hou: the folder whose ``claude/`` holds this scene's memory.

    The read-only part of ``scene_memory.resolve_hip_dir``: an unsaved scene's
    notes live in this launch's unsaved folder; a saved scene's in the hip's
    folder when its ``claude/`` exists, else wherever this process recorded a
    relocation for it. The resolver's remaining steps only choose where to
    CREATE memory (a writability probe, then a fallback that reads hou), and a
    session end creates nothing.
    """
    if facts["unsaved"]:
        return facts["unsaved_base"]
    hip_path = os.path.normpath(facts["hip_path"] or ".")
    base = os.path.dirname(hip_path) if os.path.isfile(hip_path) else hip_path
    base = os.path.normpath(base)
    if os.path.isdir(os.path.join(base, "claude")):
        return base
    try:
        from synapse.memory import scene_memory
        relocated, relocated_lock = scene_memory._RELOCATED, scene_memory._RELOCATED_LOCK
    except (ImportError, AttributeError):
        logger.debug("scene_memory relocation map unavailable for %s", base, exc_info=True)
        return None
    with relocated_lock:
        return relocated.get(base)


def _existing_agent_usd(facts: Dict[str, Any]) -> Optional[str]:
    """Recorder thread, no hou: the scene's agent.usd if it already exists."""
    parent = _scene_memory_parent(facts)
    if not parent:
        return None
    agent_usd = os.path.join(parent, "claude", "agent.usd")
    return agent_usd if os.path.isfile(agent_usd) else None


def _write_session_end(session_ids: Tuple[str, ...], ended_at: str,
                       facts: Dict[str, Any]) -> None:
    """Recorder thread, no hou: suspend pending tasks and log the session end.

    Writes only into an agent.usd that already exists. It no longer runs
    ensure_scene_structure, so a session end creates no claude/ folder,
    project.md, memory.md or agent.usd. It no longer calls write_session_end
    either: with only a timestamp that call wrote nothing (scene_memory skips
    bodyless session ends, Mile 1 / C-2).
    """
    agent_usd = _existing_agent_usd(facts)
    if agent_usd is None:
        logger.debug(
            "MCP session end %s: no agent.usd for %s, nothing to record",
            session_ids, facts.get("hip_path"),
        )
        return
    from synapse.memory.agent_state import log_session, suspend_all_tasks

    suspend_all_tasks(agent_usd)
    if len(session_ids) == 1:
        summary_text = "MCP session ended (id: {})".format(session_ids[0])
    else:
        summary_text = "MCP sessions ended (ids: {})".format(", ".join(session_ids))
    log_session(agent_usd, {"end_time": ended_at, "summary_text": summary_text})
