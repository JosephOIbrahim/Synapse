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
import threading
import time
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

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
        "protocol_version", "initialized", "preflight_due",
    )

    def __init__(self, session_id: str, client_info: dict):
        self.session_id = session_id
        self.client_info = client_info
        self.created_at = time.time()
        self.last_activity = self.created_at
        self.protocol_version = "2025-06-18"
        self.initialized = False
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
_CAPTURE_LABEL = "mcp:session_end:capture"

# How long the recorder thread waits for Houdini's main thread to run its read.
# Only the recorder thread waits; no request does. It is the freeze chain's
# escalation age (server/freeze_chain.py ESCALATION_S): a read that has not
# started by then is dropped, and the record with it.
_CAPTURE_TIMEOUT_S = 30.0

# Operator switch, read per call: "0", "false" or "off" turns MCP session-end
# records off (nothing is queued, posted or written). tests/conftest.py sets it
# to "0" for the whole test session; a test that wants records turns it back on.
_RECORDS_ENV = "SYNAPSE_MCP_SESSION_END_RECORDS"


def _records_enabled() -> bool:
    """False when the operator, or the test suite, has turned the records off."""
    return os.environ.get(_RECORDS_ENV, "1").strip().lower() not in ("0", "false", "off")


class _SessionEnd(NamedTuple):
    """Sessions that ended together, as the request thread saw them end."""

    session_ids: Tuple[str, ...]
    ended_at: str  # UTC "%Y-%m-%dT%H:%M:%SZ": the record's end time
    ended_epoch: float  # the same moment in epoch seconds: the task cutoff


def _batch_ids(batch: Sequence[_SessionEnd]) -> Tuple[str, ...]:
    return tuple(sid for end in batch for sid in end.session_ids)


class _SessionEndRecorder:
    """Writes MCP session-end records. Four hops, each on a thread allowed to do it.

    1. Request thread (initialize's sweep, DELETE /mcp): ``schedule`` appends
       the end under a lock and wakes the recorder. It never waits on Houdini,
       posts nothing to the main thread and calls no hou.
    2. Recorder thread (one daemon thread): takes every end queued so far and
       asks the main thread for the scene facts through ``run_on_main``
       (label ``mcp:session_end:capture``). The dispatch is in run_on_main's
       pending-dispatch registry, so the emergency halt can cancel it, and its
       hold is labelled in the main-thread telemetry. ``record_stall=False``
       and ``record_wait=False``: a background read that sits through a stall
       must not trip the stall detector or skew the command-wait histogram.
       The post is made here, not on the request thread, because the vendor's
       registration calls ``hou.ui.addEventLoopCallback`` when no deferred
       callback is active, and that waits for the HOM lock the main thread may
       be holding (hdefereval.py, ``_queueDeferred``). This thread waits for
       the read, at most ``capture_timeout`` seconds.
    3. Houdini's main thread: reads the scene's hip path and, for an untitled
       hip, whether it was ever saved and this launch's unsaved notes folder.
       Reads only -- no filesystem work.
    4. Recorder thread: adds every end that queued while it waited for the
       read, then writes ONE record for all of them into the scene's EXISTING
       ``claude/agent.usd``. No hou. Ends that bunch up behind a stalled main
       thread therefore become one write: ``log_session`` names its prim by
       the second it is written, so separate writes in one second would
       overwrite each other. The task suspension is limited to tasks created
       by the latest of those ends, so a record that lands after the next
       session started cannot suspend that session's tasks.

    If the main thread does not start the read within ``capture_timeout``
    (a freeze), or the emergency halt cancels it, the batch is dropped with a
    warning and no record is written. Under hython nothing reaches this
    class: ``hou`` imports but ``hdefereval`` raises ImportError, so
    ``_schedule_session_end`` posts nothing and no session-end record is
    written (the code before this recorder wrote one inline).

    One thread writes every MCP session-end record, so they never race each
    other. agent_state's writers take no file lock (none of its callers do),
    so this cannot serialize against agent.usd writers elsewhere -- the same
    as before, when these writes ran on concurrent request threads.
    """

    def __init__(self, capture_timeout: float = _CAPTURE_TIMEOUT_S):
        self._capture_timeout = capture_timeout
        self._cond = threading.Condition()
        self._pending: List[_SessionEnd] = []
        self._busy = False
        self._stopping = False
        self._thread: Optional[threading.Thread] = None

    def schedule(self, end: _SessionEnd) -> None:
        """Request thread: queue the end and wake the recorder. Never waits on Houdini."""
        with self._cond:
            if self._stopping:
                logger.warning(
                    "MCP session-end recorder is stopped; %s not recorded", end.session_ids,
                )
                return
            self._pending.append(end)
            self._cond.notify_all()
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(
                    target=self._run, name=_RECORDER_THREAD_NAME, daemon=True,
                )
                self._thread.start()

    def wait_idle(self, timeout: float) -> bool:
        """True once nothing is queued and no batch is in hand; False on timeout.

        For tests and diagnostics only. A batch whose main-thread read has not
        run yet is in hand, so this waits for the read too.
        """
        deadline = time.monotonic() + timeout
        with self._cond:
            while self._pending or self._busy:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._cond.wait(remaining)
        return True

    def stop(self, timeout: float) -> bool:
        """Stop the recorder thread; True once it has exited.

        Ends still queued are dropped. A batch in hand finishes first, so this
        can wait for its main-thread read (``capture_timeout``) and its write.
        For tests and diagnostics: the process-wide recorder is never stopped.
        """
        with self._cond:
            self._stopping = True
            self._cond.notify_all()
            thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    def _run(self) -> None:
        dropped: List[_SessionEnd] = []
        while True:
            with self._cond:
                while not self._pending and not self._stopping:
                    self._cond.wait()
                if self._stopping:
                    dropped, self._pending = self._pending, []
                    self._cond.notify_all()
                    break
                batch, self._pending = self._pending, []
                self._busy = True
            try:
                self._record(batch)
            except Exception:
                logger.warning(
                    "MCP session-end record for %s was not written", _batch_ids(batch),
                    exc_info=True,
                )
            finally:
                with self._cond:
                    self._busy = False
                    self._cond.notify_all()
        if dropped:
            logger.warning(
                "MCP session-end recorder stopped; %s not recorded", _batch_ids(dropped),
            )

    def _record(self, batch: List[_SessionEnd]) -> None:
        """Recorder thread: read the scene on main, then write one record.

        Extends *batch* in place with the ends that queued during the read.
        """
        from ..server.main_thread import MainThreadTimeout, run_on_main

        detector, unsaved_base_of = _scene_fact_helpers()
        try:
            facts = run_on_main(
                lambda: _read_scene_facts(detector, unsaved_base_of),
                timeout=self._capture_timeout,
                record_stall=False,
                record_wait=False,
                label=_CAPTURE_LABEL,
            )
        except MainThreadTimeout as exc:
            logger.warning(
                "MCP session-end record for %s skipped: Houdini's main thread did not "
                "run the scene read within %.1f s (started: %s)",
                _batch_ids(batch), self._capture_timeout, exc.started,
            )
            return
        with self._cond:
            batch.extend(self._pending)
            self._pending = []
        _write_session_end(batch, facts)


_RECORDER = _SessionEndRecorder()


def _schedule_session_end(session_ids: Iterable[str]) -> None:
    """Hand ended sessions to the recorder. Never waits; calls no hou.

    Nothing is recorded, and no thread starts, when:

    * there is no ``hou`` (outside Houdini), as before;
    * the records are switched off (``SYNAPSE_MCP_SESSION_END_RECORDS=0``);
    * ``hdefereval`` does not import. Under hython ``hou`` imports but
      ``hdefereval`` raises ImportError (the vendor module refuses to load
      when ``hou.isUIAvailable()`` is False), so nothing is posted and no
      session-end record is written. The code before this recorder wrote
      those records inline, so an MCP server hosted in hython now writes none.
    """
    session_ids = tuple(session_ids)
    if not session_ids or hou is None:
        return
    if not _records_enabled():
        logger.debug(
            "%s is off: MCP session-end record for %s not written", _RECORDS_ENV, session_ids,
        )
        return
    try:
        import hdefereval  # noqa: F401 -- presence only; the recorder thread posts
    except ImportError:
        logger.debug(
            "No hdefereval: MCP session-end record for %s skipped", session_ids,
        )
        return
    ended_epoch = time.time()
    ended_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ended_epoch))
    _RECORDER.schedule(_SessionEnd(session_ids, ended_at, ended_epoch))


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


def _write_session_end(batch: Sequence[_SessionEnd], facts: Dict[str, Any]) -> None:
    """Recorder thread, no hou: suspend pending tasks and log the session end(s).

    One record for the whole batch. Writes only into an agent.usd that already
    exists. It no longer runs ensure_scene_structure, so a session end creates
    no claude/ folder, project.md, memory.md or agent.usd. It no longer calls
    write_session_end either: with only a timestamp that call wrote nothing
    (scene_memory skips bodyless session ends, Mile 1 / C-2).
    """
    session_ids = _batch_ids(batch)
    agent_usd = _existing_agent_usd(facts)
    if agent_usd is None:
        logger.debug(
            "MCP session end %s: no agent.usd for %s, nothing to record",
            session_ids, facts.get("hip_path"),
        )
        return
    from synapse.memory.agent_state import log_session, suspend_all_tasks

    last = max(batch, key=lambda end: end.ended_epoch)
    # Only tasks created by the last end: this record can land after the next
    # session's first writes, and must not suspend what that session started.
    suspend_all_tasks(agent_usd, created_at_or_before=last.ended_epoch)
    if len(session_ids) == 1:
        summary_text = "MCP session ended (id: {})".format(session_ids[0])
    else:
        summary_text = "MCP sessions ended (ids: {})".format(", ".join(session_ids))
    log_session(agent_usd, {"end_time": last.ended_at, "summary_text": summary_text})
