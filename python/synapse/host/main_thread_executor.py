"""Main-thread executor for Houdini (Sprint 3 Spike 1 + 2.1 bugfix).

Implements the ``main_thread_executor`` callable contract consumed by
``synapse.cognitive.dispatcher.Dispatcher``.

Runtime mode detection (three-state)
------------------------------------
Stock Python, graphical Houdini, and headless Houdini are three
distinct runtime contexts. Collapsing them to a binary
"hdefereval importable or not" produced a real bug (Spike 2.1):
the deferred ``test_inspect_live.py`` gate run under ``hython``
would raise ``RuntimeError`` with the message "use is_testing=True" —
wrong advice for a live-tool invocation — because the headless path
was misclassified.

The modes:

- ``stock``    — no ``hou`` at all. Raise ``RuntimeError``; caller
                  must use ``Dispatcher(is_testing=True)`` for
                  stock-Python / CI work.
- ``gui``      — ``hou`` present AND ``hou.isUIAvailable()`` True.
                  Marshal through ``hdefereval.executeDeferred`` plus
                  our own Event with a hard timeout — the Qt event loop
                  is running, the caller is typically on a background
                  thread (agent daemon or WS handler). A caller that IS
                  the main thread takes the inline fast path.
- ``headless`` — ``hou`` present AND ``hou.isUIAvailable()`` False.
                  No Qt event loop to marshal to. The caller IS on
                  the only Python thread — execute the tool body
                  synchronously on the calling thread.

``hou.isUIAvailable()`` is the same primitive the daemon boot gate
uses (``synapse.host.daemon.SynapseDaemon._check_boot_gate``). One
detection primitive, two call sites — symmetry keeps the host layer
coherent.

Design notes
------------
- To impose a timeout in GUI mode we post with the non-blocking
  ``hdefereval.executeDeferred`` and wait on our own Event. A payload
  that has already STARTED keeps executing after the timeout; Python
  can't safely interrupt it mid-op. (A payload that has not started
  yet is suppressed — see the C4 zombie-kill flag in ``_exec_gui``.)
  Spike 2 Phase 2 pairs this with
  ``threading.Event('cancel_requested')`` inside tool bodies so
  cooperative cancellation actually lands.

Why this site does NOT self-deadlock (verified, not assumed)
------------------------------------------------------------
``hdefereval._queueDeferred(block=True)`` -- which is what
``executeInMainThreadWithResult`` is -- performs NO thread check. It
appends to ``_queue`` and then parks in ``_condition.wait()``. The only
notifier is ``_processDeferred``, which runs from Houdini's event-loop
callback, i.e. ON THE MAIN THREAD. So a MAIN-thread caller of that
primitive waits forever on itself: permanent, unrecoverable deadlock.

HISTORICAL NOTE — how ``_exec_gui`` used to dodge that: it issued the
blocking call from a **freshly spawned** worker thread, never from the
caller's thread. A brand-new ``threading.Thread`` is by definition not
``threading.main_thread()``, so the blocking primitive was never
reached on MAIN whatever thread called ``main_thread_exec`` (marshal
audit ``docs/sprint_freeze/marshal_map.md`` row 26, "structurally never
MAIN"). That worker thread is GONE — see below. Do not read the rest of
this section as a description of the live code path; ``_exec_gui`` no
longer contains a blocking marshal or a worker thread at all.

The second defect in the same primitive -- and why we left it entirely
----------------------------------------------------------------------
``_queueDeferred`` reads its result back out of MODULE GLOBALS
(``_last_result`` / ``_last_exc_info``). Two blocking marshals in
flight concurrently anywhere in the process can therefore hand each
other's results back to the wrong caller -- silent cross-thread data
corruption, not a hang. Serializing our own marshals would only have
closed our contribution to that race, leaving us exposed to blocking
marshals issued elsewhere in the process.

So ``_exec_gui`` no longer uses the blocking primitive at all. It now
uses the same shape ``synapse.server.main_thread.run_on_main`` uses and
is immune to BOTH defects by construction:

- ``hdefereval.executeDeferred`` -- the NON-blocking post. Nothing ever
  parks in ``_condition.wait()``, so no caller can wait on itself.
- Its own ``result_holder`` / ``error_holder`` closure cells. No module
  globals are read, so no concurrent marshal can swap our result.
- Its own ``threading.Event`` + timeout, preserving the exact
  ``MainThreadTimeoutError`` contract.
- A C4 ``abandoned`` flag, so a payload whose caller has already timed
  out cannot mutate the scene late (zombie-kill).
- A main-thread fast path, so a GUI-mode caller that IS the main thread
  executes inline instead of stalling for the full timeout waiting for
  an event loop it is itself blocking.

The worker thread the old implementation spawned is gone: it existed
only to keep the blocking primitive off the main thread, and there is
no longer a blocking primitive to keep off it. That also removes the
thread leak the old timeout path left behind (marshal audit row 26,
"worker leaks forever on caller timeout").
- Headless mode does NOT apply the timeout. The caller IS on the
  main thread; spawning a worker to enforce timeout would move tool
  execution off the main thread, which breaks Houdini API
  thread-safety. Tool bodies running in headless that need to bound
  themselves can wrap their own work.
- Testing path: ``synapse.cognitive.dispatcher.Dispatcher(
  is_testing=True)``. This module has no test-mode — it exists to
  touch ``hou`` and ``hdefereval``.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Optional

try:
    import hdefereval  # type: ignore[import-not-found]
    _HDEFEREVAL_AVAILABLE = True
except ImportError:
    hdefereval = None  # type: ignore[assignment]
    _HDEFEREVAL_AVAILABLE = False


DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS: float = 30.0
"""Spike 2 lock. Change in coordination with Crucible deadlock budget."""




class MainThreadTimeoutError(TimeoutError):
    """GUI-mode main-thread dispatch exceeded the timeout budget.

    Subclass of the stdlib ``TimeoutError`` so callers can catch
    either the specific class or the broader category. Only ever
    raised from the GUI-mode path — headless mode executes
    synchronously on the calling thread without a timeout wrapper.
    """


# -- Runtime mode detection -------------------------------------------------


RUNTIME_STOCK: str = "stock"
RUNTIME_GUI: str = "gui"
RUNTIME_HEADLESS: str = "headless"


def detect_runtime_mode() -> str:
    """Return ``RUNTIME_STOCK``, ``RUNTIME_GUI``, or ``RUNTIME_HEADLESS``.

    Detection rules:
      - No ``hou`` import  → stock.
      - ``hou`` but no ``isUIAvailable`` attr → raises; we don't
        guess against unsupported Houdini builds.
      - ``hou.isUIAvailable()`` True  → gui.
      - ``hou.isUIAvailable()`` False → headless.

    Called every ``main_thread_exec`` invocation rather than cached
    because ``hou.isUIAvailable()`` can legitimately change across
    a session (rare, but possible when UI is dynamically torn down).

    Raises:
        RuntimeError: ``hou`` is present but ``hou.isUIAvailable``
            is missing. We don't guess — file a bug instead.
    """
    try:
        import hou  # type: ignore[import-not-found]
    except ImportError:
        return RUNTIME_STOCK

    is_ui_available = getattr(hou, "isUIAvailable", None)
    if is_ui_available is None:
        raise RuntimeError(
            "hou is importable but hou.isUIAvailable is missing — this "
            "Houdini build pre-dates the API synapse.host relies on. "
            "File a bug with the Houdini version and hython launch mode."
        )
    return RUNTIME_GUI if is_ui_available() else RUNTIME_HEADLESS


# -- Execution paths --------------------------------------------------------


def _exec_gui(
    fn: Callable[..., Dict[str, Any]],
    kwargs: Dict[str, Any],
    effective_timeout: float,
) -> Dict[str, Any]:
    """GUI-mode execution: marshal to Houdini's main thread via hdefereval.

    Posts the payload with the NON-blocking ``hdefereval.executeDeferred``
    and waits on our own Event, so a stuck main-thread payload returns
    control to the caller after ``effective_timeout``. See the module
    docstring for why the blocking ``executeInMainThreadWithResult``
    primitive is not used here.

    TIMEOUT: unchanged. ``effective_timeout`` is whatever the caller
    passed, defaulting to ``DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS`` (30s,
    the Spike 2 lock). This migration deliberately does NOT retune the
    budget — the old code already enforced exactly this timeout at
    exactly this boundary, so preserving it keeps every existing caller's
    behaviour byte-for-byte apart from the deadlock and result-race
    removals.
    """
    if not _HDEFEREVAL_AVAILABLE:
        raise RuntimeError(
            "hou.isUIAvailable() returned True but hdefereval is not "
            "importable. This state is inconsistent — file a bug "
            "with the Houdini version, hython launch mode, and "
            "full sys.path."
        )

    # Fast path: the caller IS the main thread. Posting and then waiting
    # would block the very event loop that has to run the payload, so the
    # caller would stall for the whole timeout and then fail — despite the
    # main thread being perfectly able to do the work right now. Run it
    # inline. Mirrors run_on_main's fast path 2 (server/main_thread.py:240).
    #
    # ``effective_timeout`` is DISCARDED on this path, and that is correct:
    # you cannot bound synchronous work on the thread you are standing on,
    # and no mechanism exists by which Python could interrupt it. Imposing a
    # "timeout" here would be a lie. But an unbounded inline payload still
    # freezes the GUI for its whole duration — a residual this sprint made
    # possible (previously this shape self-deadlocked instead) and which is
    # otherwise completely invisible. So: no bounding, pure observation.
    #
    # This is the THIRD of three inline main-thread paths wired this sprint.
    # The siblings — ``main_thread.run_on_main`` fast path 2 and
    # ``handlers.run_on_main_observed`` — both report through
    # ``marshal_guard.note_main_thread_inline_overrun`` on its pinned
    # positional contract ``(where, elapsed_s, budget_s)``. This one now does
    # too, with a distinct ``where`` so the three records stay separable in
    # the ledger rather than being conflated.
    #
    # THE IMPORT IS GUARDED, and must stay guarded. ``marshal_guard`` lives in
    # ``synapse.server``; this module is host-layer and its contract (see the
    # module docstring's tri-state section) is that it works with no ``hou``,
    # no ``hdefereval``, and no ``synapse.server`` present. That seam is what
    # gives the whole sprint headless test coverage, so telemetry is a
    # best-effort add-on here, never a dependency. Any failure — module
    # absent, sink raising — is swallowed: the payload's return value and its
    # exception propagation are unaffected either way.
    if threading.current_thread() is threading.main_thread():
        _t_inline = time.perf_counter()
        try:
            return fn(**kwargs)
        finally:
            _elapsed_s = time.perf_counter() - _t_inline
            try:
                from ..server.marshal_guard import (
                    note_main_thread_inline_overrun,
                    inline_budget_s,
                )
                _budget_s = inline_budget_s()
                if _elapsed_s > _budget_s:
                    note_main_thread_inline_overrun(
                        "host.main_thread_executor._exec_gui:inline_main",
                        _elapsed_s,
                        _budget_s,
                    )
            except Exception:
                # Telemetry must never break the payload's return or its
                # exception propagation. Swallow deliberately.
                pass

    result_holder: list[Any] = []
    error_holder: list[BaseException] = []
    done = threading.Event()

    # C4 zombie-kill. On timeout the caller is told the dispatch failed and
    # will typically retry; if the payload then runs anyway, that mutation
    # lands AFTER the failure report and the retry double-applies it.
    # Checking `abandoned` under a lock immediately before calling fn makes a
    # not-yet-started payload a no-op once the caller has given up. A payload
    # already inside fn() when the timeout fires is the accepted residual
    # race — the lock serializes the check-vs-set, not fn() itself. Same
    # semantics as server/main_thread.run_on_main.
    state_lock = threading.Lock()
    abandoned = [False]

    def _on_main() -> None:
        with state_lock:
            if abandoned[0]:
                return  # caller already timed out — do not touch the scene
        try:
            result_holder.append(fn(**kwargs))
        except BaseException as exc:  # noqa: BLE001 - propagate faithfully
            error_holder.append(exc)
        finally:
            done.set()

    hdefereval.executeDeferred(_on_main)

    if not done.wait(timeout=effective_timeout):
        with state_lock:
            abandoned[0] = True
        raise MainThreadTimeoutError(
            f"Main-thread dispatch of {getattr(fn, '__name__', repr(fn))!r} "
            f"exceeded {effective_timeout:g}s timeout. The dispatched "
            f"callable may still be running on Houdini's main thread."
        )

    if error_holder:
        raise error_holder[0]
    return result_holder[0]


def _exec_headless(
    fn: Callable[..., Dict[str, Any]],
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    """Headless-mode execution: direct call on the calling thread.

    Headless hython runs on a single Python thread. There is no Qt
    event loop to marshal through, and no other thread that would be
    the "main" thread. Spawning a worker to enforce a timeout would
    move tool execution off the main thread, breaking Houdini API
    thread-safety. Tool bodies that need to bound themselves in
    headless must wrap their own timing.
    """
    return fn(**kwargs)


def main_thread_exec(
    fn: Callable[..., Dict[str, Any]],
    kwargs: Dict[str, Any],
    *,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Execute ``fn(**kwargs)`` on Houdini's main thread when marshaling
    is needed; otherwise run it directly.

    Args:
        fn: Callable returning a JSON-serializable dict.
        kwargs: Keyword arguments passed to ``fn``.
        timeout: Hard timeout in seconds — honoured only in GUI mode
            (see module docstring). ``None`` uses
            ``DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS``.

    Returns:
        Whatever ``fn`` returned.

    Raises:
        RuntimeError: running in stock Python (no ``hou``), or in a
            Houdini build that lacks ``hou.isUIAvailable``, or in GUI
            mode where ``hdefereval`` is inexplicably unavailable.
        MainThreadTimeoutError: GUI-mode dispatch took longer than
            ``timeout`` seconds.
        BaseException: any exception ``fn`` raised propagates through.
    """
    mode = detect_runtime_mode()

    if mode == RUNTIME_STOCK:
        raise RuntimeError(
            "main_thread_exec requires a Houdini process "
            "(hython graphical or headless). For stock-Python / CI "
            "test work, construct Dispatcher(is_testing=True) to "
            "bypass host-thread marshaling entirely."
        )

    if mode == RUNTIME_HEADLESS:
        return _exec_headless(fn, kwargs)

    # GUI mode.
    effective_timeout: float = (
        timeout if timeout is not None
        else DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS
    )
    return _exec_gui(fn, kwargs, effective_timeout)
