"""
MCP Session Manager

Manages MCP client sessions with unique Mcp-Session-Id tokens.
Thread-safe for concurrent hwebserver requests.

Sessions track last_activity for TTL-based expiry. When a session ends
(DELETE /mcp, or the expiry/overflow sweep that every initialize runs), its
session-end record is queued, never written on the thread that ended the
session. ``_SessionEndRecorder`` below owns that work and states which thread
does what. A record is written only in a graphical Houdini session (where
hdefereval imports; under hython nothing is recorded), only while
SYNAPSE_MCP_SESSION_END_RECORDS is on, and only into files that already
exist: the scene's ``claude/agent.usd`` and, for a WebSocket session that did
something, its ``claude/memory.md``. The fallback WebSocket server's
disconnect hook (server/websocket.py; the package starts that server only when
the hwebserver adapter cannot load) hands its session ends to the same
recorder through ``schedule_session_end``. The GUI's hwebserver /synapse
endpoint (server/hwebserver_adapter.py) records no session end.
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
        Each removed session ends at its last request (its ``last_activity``),
        not at this sweep: see ``_schedule_swept_ends``.
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
            # Read under the lock, as get_session writes it.
            swept = [(sid, s.last_activity) for sid, s in expired + overflow]

        # Hand off OUTSIDE the lock to avoid blocking other callers
        _schedule_swept_ends(swept)

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
            schedule_session_end([session.session_id], caller=MCP_SESSION)
            return True
        return False

    def reap_expired(self) -> int:
        """Reap sessions that exceeded TTL (inactivity-based).

        Returns the number of sessions reaped. Like the sweep, it only hands
        the end records to the recorder, so any thread may call it, and each
        reaped session ends at its last request (``last_activity``).
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
            swept = [(s.session_id, s.last_activity) for s in reaped]

        _schedule_swept_ends(swept)

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
# A session end suspends the scene's pending agent tasks and adds a
# /SYNAPSE/agent/session_history entry to agent.usd; for a WebSocket client
# that did something it also appends the session summary to memory.md.
# The recorder takes ends from two callers:
#
#   * MCP (MCPSessionManager above), on an hwebserver worker thread: DELETE
#     /mcp through ``schedule_session_end``, and the expiry/overflow sweep
#     every initialize runs through ``_schedule_swept_ends``;
#   * the WebSocket server's disconnect hook (server/websocket.py,
#     SynapseServer._handle_client), on the connection's own thread:
#     websockets.sync gives each connection one. That is the fallback
#     server, which the package starts only when the hwebserver adapter
#     cannot load (server/start_hwebserver.py). The GUI's hwebserver
#     /synapse endpoint (server/hwebserver_adapter.py) records no session end.
#
# Both used to write inline on that thread: hou.hipFile.path() and
# hou.getenv("JOB") off Houdini's main thread, then ensure_scene_structure
# (which creates folders and seed files, possibly on a synced drive, itself
# reads hou -- store.hip_is_unsaved and store._safe_unsaved_base -- and for an
# untitled hip waits up to 10 s on the main thread) and the agent.usd and
# memory.md writes, all before the request or the disconnect could finish.

_RECORDER_THREAD_NAME = "synapse-mcp-session-end"
# One main-thread read serves every end in a batch, MCP ends and WebSocket
# disconnects alike, so the label names the recorder rather than the caller.
_CAPTURE_LABEL = "mcp:session_end:capture"

#: The callers of ``schedule_session_end``. Each names its ends its own way in
#: the agent.usd record: (one end, several ends).
MCP_SESSION = "mcp"
WEBSOCKET_CLIENT = "websocket"
_RECORD_WORDING = {
    MCP_SESSION: ("MCP session ended (id: {})", "MCP sessions ended (ids: {})"),
    WEBSOCKET_CLIENT: ("Session ended (client: {})", "Sessions ended (clients: {})"),
}

# How long the recorder thread waits for its main-thread read, counted from
# when the read is posted. Only the recorder thread waits; no request does. A
# read that has not finished by then -- not started yet, or still running -- is
# dropped, and the record with it. Posting (hdefereval.executeDeferred, when
# run_on_main has no wake outstanding) can itself wait on Houdini's HOM lock
# before this clock starts, so a record can land well after 30 s. The value is
# the freeze chain's escalation age (server/freeze_chain.py ESCALATION_S);
# tests/test_mcp_initialize_main_thread.py pins the two equal.
_CAPTURE_TIMEOUT_S = 30.0

# Operator switch: "0", "false" or "off" turns session-end records off
# (nothing is queued, posted or written), for MCP session ends and WebSocket
# disconnects alike; the name predates the WebSocket caller. Read on every
# session end, and again by the recorder thread when it takes a batch and
# before it writes one: ends already queued when it goes off are dropped, and
# a scene read already posted then still runs on the main thread but its
# record is not written. tests/conftest.py sets it to "0" for the whole test
# session; a test that wants records turns it back on.
_RECORDS_ENV = "SYNAPSE_MCP_SESSION_END_RECORDS"
_STAMP = "%Y-%m-%dT%H:%M:%SZ"  # the record's end time, as agent_state stamps tasks


def _records_enabled() -> bool:
    """False when the operator, or the test suite, has turned the records off."""
    return os.environ.get(_RECORDS_ENV, "1").strip().lower() not in ("0", "false", "off")


class _SessionEnd(NamedTuple):
    """Ends one caller handed over together, as that caller saw them end."""

    ids: Tuple[str, ...]  # MCP session ids, or the WebSocket client id
    ended_at: str  # ended_epoch as UTC "%Y-%m-%dT%H:%M:%SZ": the record's end time
    # When the session ended, in epoch seconds: the task cutoff. The call time
    # for DELETE /mcp and a WebSocket disconnect; for a session the sweep
    # removed, its last request (MCPSession.last_activity), not the sweep.
    ended_epoch: float
    caller: str  # MCP_SESSION or WEBSOCKET_CLIENT: how the record names the ids
    memory_text: str  # appended to an EXISTING memory.md; "" appends nothing


def _batch_ids(batch: Sequence[_SessionEnd]) -> Tuple[str, ...]:
    return tuple(end_id for end in batch for end_id in end.ids)


class _SessionEndRecorder:
    """Writes session-end records. Four hops, each on a thread allowed to do it.

    1. Calling thread (initialize's sweep and DELETE /mcp on an hwebserver
       worker; a WebSocket disconnect on the connection's own thread):
       ``schedule`` appends the ends under one lock hold (a sweep's ends
       therefore share a batch) and wakes the recorder, starting its thread
       when none is running. It imports nothing, calls no hou, posts nothing
       to the main thread, touches no file but the log and never waits on
       Houdini. That covers the session-end record only: the
       WebSocket disconnect hook calls the session tracker's ``end_session``
       first, and with SYNAPSE_AUTO_MEMORY=1 that call writes the session
       summary row to the memory store through run_on_main from the
       connection thread (server/websocket.py says what that costs).
    2. Recorder thread (one daemon thread): first checks, once per recorder,
       that ``hdefereval`` imports. The check runs here, never on a calling
       thread: importing the vendor module runs its body, which calls
       ``hou.isUIAvailable()`` and raises ImportError when that is False
       (hdefereval.py), and Python does not cache a failed import. When it
       fails -- hython's ImportError, or any other error the module body
       raises, which is logged as a warning -- the recorder drops what is
       queued, remembers the answer and exits, and later ends queue nothing.
       Then it takes every end queued so far, drops them instead when the
       records switch has gone off since they queued (``_RECORDS_ENV``), and
       asks the main thread for the scene facts through
       ``run_on_main`` (label ``mcp:session_end:capture``). The dispatch is in
       run_on_main's pending-dispatch registry, so the emergency halt can
       cancel it, and its hold is labelled in the main-thread telemetry.
       ``record_stall=False`` and ``record_wait=False``: a background read that
       sits through a stall must not trip the stall detector or skew the
       command-wait histogram. The post is made here, not on the calling
       thread, because the vendor's registration calls
       ``hou.ui.addEventLoopCallback`` when no deferred callback is active,
       and that waits for the HOM lock the main thread may be holding
       (hdefereval.py, ``_queueDeferred``). Once the read is posted, this
       thread waits at most ``capture_timeout`` seconds for it to finish; the
       post itself can wait on that HOM lock before the clock starts.
    3. Houdini's main thread: reads the scene's hip path and, for an untitled
       hip, whether it was ever saved and this launch's unsaved notes folder.
       Reads only -- no filesystem work.
    4. Recorder thread: adds every end that queued while it waited for the
       read, drops the lot if the records switch is off by now, and otherwise
       writes ONE agent.usd record for all of them into the scene's EXISTING
       ``claude/agent.usd``, and appends each end's summary, if it carries
       one, to the scene's EXISTING ``claude/memory.md``. No hou. Ends that
       bunch up behind a stalled main thread therefore become one agent.usd
       write. The task suspension is limited to tasks created by the latest
       of those ends (``_SessionEnd.ended_epoch``): the moment DELETE /mcp or
       the disconnect ended the session, or, for a session the sweep removed,
       its last request (``last_activity``). However late the record lands,
       it leaves alone every task created after the latest end it names: one
       another client started after an MCP session went idle, and one that
       session's own last request started after the request arrived.

    If the read has not finished within ``capture_timeout`` of being posted
    (a freeze, or a read still running then), or the emergency halt cancels
    it, the batch is dropped with a warning and no record is written. Under
    hython ``hou`` imports but ``hdefereval`` does not, so no session-end
    record is written for an MCP session end or a WebSocket disconnect (the
    code before this recorder wrote both inline).

    Which scene gets the record: the one open when the main-thread read runs,
    not necessarily the one open when the session ended. The read can run up
    to ``capture_timeout`` after it is posted, and posting can wait on the HOM
    lock first. A File > Open in that window writes the ended session's
    history entry (and its memory.md summary) into the newly opened scene's
    files, when that scene has them, and suspends that scene's pending tasks
    created before the end (the cutoff in hop 4). A File > New usually drops
    the record: the new untitled scene's notes folder has no agent.usd until
    something writes one.

    Records written in the same second overwrite each other: ``log_session``
    names its prim by the second it is written, so the later summary replaces
    the earlier. The recorder merges only the ends that queue while a read is
    pending; ends that arrive after a read returns form the next batch, whose
    write can land in the same second. The inline writers before this
    recorder collided the same way.

    One thread writes every session-end record, so no two session-end writes
    run at once (the same-second overwrite above still applies).
    agent_state's writers take no file lock (none of its callers do), so this
    cannot serialize against agent.usd writers elsewhere -- the same as
    before, when these writes ran on concurrent request and connection
    threads. memory.md appends take scene_memory's per-file lock.
    """

    def __init__(self, capture_timeout: float = _CAPTURE_TIMEOUT_S):
        self._capture_timeout = capture_timeout
        self._cond = threading.Condition()
        self._pending: List[_SessionEnd] = []
        self._busy = False
        self._stopping = False
        # None until the recorder thread has tried to import hdefereval; then
        # whether it imported. Only the recorder thread sets it.
        self._can_post: Optional[bool] = None
        self._thread: Optional[threading.Thread] = None

    def schedule(self, ends: Sequence[_SessionEnd]) -> None:
        """Calling thread: queue the ends together and wake the recorder. Never waits on Houdini.

        One lock hold queues them all, so the recorder takes them in one batch
        and one record names them all.
        """
        with self._cond:
            if self._stopping:
                logger.warning(
                    "Session-end recorder is stopped; %s not recorded", _batch_ids(ends),
                )
                return
            if self._can_post is False:
                logger.debug(
                    "hdefereval did not import in this process: session-end record "
                    "for %s not written", _batch_ids(ends),
                )
                return
            self._pending.extend(ends)
            self._cond.notify_all()
            if self._thread is not None and self._thread.is_alive():
                return
            thread = threading.Thread(
                target=self._run, name=_RECORDER_THREAD_NAME, daemon=True,
            )
            try:
                thread.start()
            except BaseException:
                # No thread will take what is queued, so drop it here rather
                # than leave it where wait_idle would wait on it forever.
                dropped, self._pending = self._pending, []
                self._cond.notify_all()
                logger.warning(
                    "Session-end recorder thread did not start; %s not recorded",
                    _batch_ids(dropped),
                )
                raise
            self._thread = thread

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

        A batch in hand finishes first: ends queued before this call while its
        main-thread read is pending join that batch if the read succeeds, and
        are recorded with it (unless the records switch is off by then). Ends
        still queued after that, or queued while no batch is in hand, are
        dropped, and later ends are refused. So this can wait for the read
        (``capture_timeout`` once posted, after any wait to post it) and the
        write.
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

    def _hdefereval_imports(self) -> bool:
        """Recorder thread: whether hdefereval imports here; tried once per recorder.

        Never on a calling thread: importing the vendor module runs its body,
        which calls ``hou.isUIAvailable()`` (and, when that is False, raises
        ImportError, which Python does not cache, so each attempt runs it
        again). When the import fails, with ImportError or anything else the
        body raises, drop what is queued and remember it, so ``schedule``
        queues nothing from then on and no later end starts a thread that
        would fail the same way. Never raises an Exception.
        """
        if self._can_post:
            return True
        try:
            import hdefereval  # noqa: F401 -- presence only; run_on_main posts
        except ImportError:
            logger.debug(
                "hdefereval does not import (no graphical Houdini): session-end "
                "records are off for this process", exc_info=True,
            )
            can_post = False
        except Exception:
            # Not the vendor's hython refusal: its module body raised something
            # else. Same outcome, but unexpected, so a warning.
            logger.warning(
                "Importing hdefereval raised: session-end records are off for "
                "this process", exc_info=True,
            )
            can_post = False
        else:
            can_post = True
        with self._cond:
            self._can_post = can_post
            if can_post:
                return True
            dropped, self._pending = self._pending, []
            self._cond.notify_all()
        if dropped:
            logger.debug("hdefereval did not import: session-end record for %s not written",
                         _batch_ids(dropped))
        return False

    def _run(self) -> None:
        if not self._hdefereval_imports():
            return
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
                # The switch again: these ends may have queued before it went off.
                if _records_enabled():
                    self._record(batch)
                else:
                    logger.debug(
                        "%s is off: session-end record for %s not written",
                        _RECORDS_ENV, _batch_ids(batch),
                    )
            except Exception:
                # Reached only by a failure before log_session returned: the
                # memory.md part logs its own (_append_session_summaries).
                logger.warning(
                    "Session-end record for %s was not written", _batch_ids(batch),
                    exc_info=True,
                )
            finally:
                with self._cond:
                    self._busy = False
                    self._cond.notify_all()
        if dropped:
            logger.warning(
                "Session-end recorder stopped; %s not recorded", _batch_ids(dropped),
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
            # run_on_main raises this on its timeout whether the main thread was
            # busy or the emergency halt cancelled the queued read.
            logger.warning(
                "Session-end record for %s skipped: the scene read did not finish "
                "within %.1f s (Houdini's main thread busy, or the read cancelled "
                "by the emergency halt; started: %s)",
                _batch_ids(batch), self._capture_timeout, exc.started,
            )
            return
        with self._cond:
            batch.extend(self._pending)
            self._pending = []
        if not _records_enabled():  # switched off while the read was pending
            logger.debug(
                "%s is off: session-end record for %s not written",
                _RECORDS_ENV, _batch_ids(batch),
            )
            return
        _write_session_end(batch, facts)


_RECORDER = _SessionEndRecorder()


def schedule_session_end(ids: Iterable[str], *, caller: str, memory_text: str = "") -> None:
    """Hand ended sessions to the recorder and return. Any thread; never waits.

    The calling thread only queues the end: it imports nothing, calls no hou,
    posts nothing to Houdini's main thread, touches no file but the log and
    waits for nothing, so an hwebserver request or a WebSocket connection
    thread can end a session while the main thread is busy. The recorder
    (``_SessionEndRecorder``) does the rest, including the check that
    hdefereval imports. Past the ``caller`` check this never raises: a failure
    to queue (for example a recorder thread that cannot start) is logged as a
    warning and the session still ends, so initialize and DELETE /mcp answer.

    ``caller`` is ``MCP_SESSION`` or ``WEBSOCKET_CLIENT`` and picks the
    agent.usd record's wording: "MCP session ended (id: ...)" / "MCP sessions
    ended (ids: ...)", or "Session ended (client: ...)" / "Sessions ended
    (clients: ...)". Ends that share one write (queued behind a stalled main
    thread) are named together, each caller's in its own words, joined by
    "; ". ``memory_text`` is a summary for the scene's memory.md, appended
    only when that file already exists. Pass it only for a session that did
    something: an empty session writes no memory.md entry (Mile 1 / C-2).

    The ends are stamped with the time of this call: the record's end time
    and its task cutoff (``_write_session_end``). DELETE /mcp and a WebSocket
    disconnect come here. The MCP sweep does not: it stamps each session it
    removes with that session's last request (``_schedule_swept_ends``).

    Nothing is recorded, and nothing is queued, when:

    * there is no ``hou`` (outside Houdini), as before; no thread starts;
    * the records are switched off (``SYNAPSE_MCP_SESSION_END_RECORDS=0``);
      no thread starts;
    * ``hdefereval`` does not import. Under hython ``hou`` imports but
      ``hdefereval`` raises ImportError (the vendor module refuses to load
      when ``hou.isUIAvailable()`` is False). The first end starts the
      recorder thread once; that thread finds no hdefereval, drops the end
      and exits, and later ends queue nothing and start nothing. No
      session-end record is written. Any other error raised by importing it
      is handled the same way, and logged as a warning. The code before this
      recorder wrote those records inline, so an MCP server, or a headless
      WebSocket server, hosted in hython now writes none: the rule accepted
      for /mcp, kept for the WebSocket disconnect.
    """
    if caller not in _RECORD_WORDING:
        raise ValueError("unknown session-end caller: {!r}".format(caller))
    end_ids: Any = ids
    try:
        end_ids = tuple(ids)
        if end_ids:
            _queue_ends([(end_ids, time.time())], caller, memory_text or "")
    except Exception:
        # Session-end bookkeeping must never fail initialize or DELETE /mcp.
        logger.warning(
            "Session-end record for %s was not queued; the session still ended",
            end_ids, exc_info=True,
        )


def _schedule_swept_ends(swept: Sequence[Tuple[str, float]]) -> None:
    """MCP sweep: queue each removed session's end at its last request. Never raises.

    *swept* is ``(session_id, last_activity)`` for each session the expiry
    sweep or the overflow eviction removed (``MCPSessionManager``). Its end
    is its last request as the server saw it -- ``last_activity``, set when
    a request carrying its id was looked up -- not the sweep, which runs only
    when some client next initializes: for an expired session, more than the
    manager's TTL later (mcp/server.py's manager uses the default,
    ``_DEFAULT_SESSION_TTL``, 30 min). So the record's end time is that
    request, and its task cutoff leaves alone every task created after it:
    one another client started while the session sat idle, and one that last
    request started after it arrived. Queued together, so one record names
    them all. Otherwise as ``schedule_session_end``: any thread, never waits.
    """
    try:
        _queue_ends([((sid,), last) for sid, last in swept], MCP_SESSION, "")
    except Exception:
        # Session-end bookkeeping must never fail initialize.
        logger.warning(
            "Session-end record for %s was not queued; the sessions still ended",
            tuple(sid for sid, _last in swept), exc_info=True,
        )


def _queue_ends(stamped: Sequence[Tuple[Tuple[str, ...], float]], caller: str,
                memory_text: str) -> None:
    """Calling thread: queue ``(ids, ended_epoch)`` ends together, or none of them.

    Imports nothing, calls no hou, posts nothing, never waits on Houdini.
    """
    if not stamped or hou is None:
        return
    if not _records_enabled():
        logger.debug(
            "%s is off: session-end record for %s not written",
            _RECORDS_ENV, tuple(end_id for ids, _epoch in stamped for end_id in ids),
        )
        return
    _RECORDER.schedule([
        _SessionEnd(ids, time.strftime(_STAMP, time.gmtime(epoch)), epoch, caller, memory_text)
        for ids, epoch in stamped
    ])


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


def _existing_memory_md(facts: Dict[str, Any]) -> Optional[str]:
    """Recorder thread, no hou: the scene's memory.md if it already exists."""
    parent = _scene_memory_parent(facts)
    if not parent:
        return None
    memory_md = os.path.join(parent, "claude", "memory.md")
    return memory_md if os.path.isfile(memory_md) else None


def _record_summary(batch: Sequence[_SessionEnd]) -> str:
    """The session_history line for *batch*: each caller's ids, in the order they were queued."""
    ids_by_caller: Dict[str, List[str]] = {}
    for end in batch:
        ids_by_caller.setdefault(end.caller, []).extend(end.ids)
    parts = []
    for caller, ids in ids_by_caller.items():
        one, several = _RECORD_WORDING[caller]
        parts.append(one.format(ids[0]) if len(ids) == 1 else several.format(", ".join(ids)))
    return "; ".join(parts)


def _write_session_end(batch: Sequence[_SessionEnd], facts: Dict[str, Any]) -> None:
    """Recorder thread, no hou: the batch's record, written only into files that exist.

    agent.usd, when the scene's ``claude/agent.usd`` exists: suspend the
    pending tasks created by the batch's latest end (``ended_epoch``; see
    ``_SessionEnd``), then add ONE session_history entry naming every end in
    the batch, with that end's time. A failure before ``log_session`` returns
    propagates, and the recorder logs the record as not written (a task
    suspension already saved by then stays). memory.md, when the scene's
    ``claude/memory.md`` exists: append each end's ``memory_text`` with
    ``write_session_end`` (only the WebSocket disconnect of a session that
    did something carries one; MCP ends carry none). A failure there loses
    only that summary and is logged here as such (``_append_session_summaries``).
    Nothing here runs ensure_scene_structure, so a session end creates no
    claude/ folder, project.md, memory.md or agent.usd.
    """
    ids = _batch_ids(batch)
    agent_usd = _existing_agent_usd(facts)
    if agent_usd is None:
        logger.debug(
            "Session end %s: no agent.usd for %s, no session_history entry",
            ids, facts.get("hip_path"),
        )
    else:
        from synapse.memory.agent_state import log_session, suspend_all_tasks

        last = max(batch, key=lambda end: end.ended_epoch)
        # Only tasks created by the batch's latest end. The record lands later
        # -- behind a stalled main thread, or, for a swept session, at the
        # sweep after its last request (more than the TTL after it, for an
        # expired one) -- and leaves alone every task created after that end,
        # whichever client created it.
        suspend_all_tasks(agent_usd, created_at_or_before=last.ended_epoch)
        log_session(agent_usd, {"end_time": last.ended_at,
                                "summary_text": _record_summary(batch)})

    summaries = [end for end in batch if end.memory_text]
    if summaries:
        _append_session_summaries(summaries, facts, recorded=agent_usd is not None)


def _append_session_summaries(summaries: Sequence[_SessionEnd], facts: Dict[str, Any],
                              recorded: bool) -> None:
    """Recorder thread, no hou: each summary into the scene's EXISTING memory.md. Never raises.

    Runs after the agent.usd record, so a failure here -- a read-only
    memory.md (PermissionError), another OSError, scene_memory's file lock
    timing out -- costs only the summary. It is logged as that, naming the
    file and whether the agent.usd record was written (*recorded*: the scene
    has an agent.usd and log_session returned), never as an unwritten record.
    """
    kept = ("the agent.usd record was written" if recorded
            else "the scene has no agent.usd, so no record was written either")
    try:
        memory_md = _existing_memory_md(facts)
        if memory_md is None:
            logger.debug(
                "Session end %s: no memory.md for %s, session summary not kept",
                _batch_ids(summaries), facts.get("hip_path"),
            )
            return
        from synapse.memory.scene_memory import write_session_end
    except Exception:
        logger.warning(
            "Session end %s: session summary not appended to the scene's memory.md; %s",
            _batch_ids(summaries), kept, exc_info=True,
        )
        return
    for end in summaries:
        try:
            write_session_end(os.path.dirname(memory_md), {
                "stopped_at": end.ended_at,
                "summary_text": end.memory_text,
            })
        except Exception:
            logger.warning(
                "Session end %s: session summary not appended to %s; %s",
                end.ids, memory_md, kept, exc_info=True,
            )
