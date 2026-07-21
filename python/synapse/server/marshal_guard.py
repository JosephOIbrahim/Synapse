"""Main-thread starvation guard — the structural half of the L8 marshal fix.

WHAT THIS DEFENDS AGAINST
-------------------------
``hdefereval.executeInMainThreadWithResult`` (vendor:
``Houdini 22.0.368/houdini/python3.13libs/hdefereval.py:43`` → ``_queueDeferred(
..., block=True)`` → ``_condition.wait()`` at ``:93``) performs an
**unconditional, untimed park with no thread check of any kind**. The condition
it waits on is notified only by ``_processDeferred()``, which the vendor
docstring states runs from Houdini's event-loop callback — i.e. ON THE MAIN
THREAD. Therefore a MAIN-thread caller enqueues work for itself and then parks
forever waiting for itself to become idle. Permanent, unrecoverable
self-deadlock. That is the freeze.

The fix is to route every marshal through ``synapse.server.main_thread.run_on_main``,
whose fast path 2 (``main_thread.py:240``) short-circuits main-thread callers to
a direct ``fn()`` call and so can never reach the blocking primitive. This module
is the *enforcement* layer that keeps the defect from coming back: a fail-fast
check, a typed error, an inline-overrun telemetry sink, and a thread-stack dump
for post-mortem.

THE SCOPING RULE (read before adding a call site)
-------------------------------------------------
``forbid_main_thread_block`` fires if and ONLY if **both** hold:

  1. the calling thread IS the process main thread
     (``threading.current_thread().ident == threading.main_thread().ident``); and
  2. the caller is about to enter a wait whose completion **requires main-thread
     progress** — a marshal-to-main, a Future resolved by a main-thread payload,
     a consent gate whose card only MAIN can draw. The caller asserts (2) by
     choosing to call this function; the guard cannot infer it.

It never fires off-main — an off-main thread blocking on MAIN is the *correct*
and intended pattern. It never fires on waits another thread can satisfy
(``queue.get`` on a worker feed, ``socket.recv``, ``subprocess.wait``, a
``Lock`` held by a worker). Those are benign main-thread blocking and are
explicitly OUT OF SCOPE.

Precision is the whole point. A guard that cries wolf on benign main-thread
blocking gets switched off by the first engineer it annoys, and then the
deadlock walks back in through the door someone propped open. If you are
tempted to add a call site "just to be safe", don't — a false positive here
costs more than a missed detection.

MODE (env flag)
---------------
``SYNAPSE_MARSHAL_GUARD``:

  * ``warn`` — **DEFAULT**. Log loudly at ERROR with a full stack, record a
    ledger entry, dump thread stacks. Does NOT raise. Zero behaviour change.
  * ``raise`` — additionally raise :class:`MainThreadStarvationError`.
  * ``off``  — record the ledger entry only; no log, no dump, no raise.

Warn-by-default is deliberate and is the same two-stage ratchet the repo uses
for the suite baseline: ship the instrument first, let it produce a ledger, and
flip to ``raise`` only once that ledger proves the guard is quiet on healthy
traffic. Escalating by default during a release freeze could convert a working
path into a hard failure, which is precisely the trade this sprint refuses to
make elsewhere (see the timeout-preservation rule for long render marshals).

WHAT THIS CANNOT DO — be honest
--------------------------------
Detection and graceful degradation is the entire contract. Once the main thread
is parked inside ``hdefereval._condition.wait()`` — or inside any native modal
loop — **nothing in Python can un-wedge it**. There is no interrupt, no timeout
parameter, and no other thread can notify that condition, because the only
notifier is the main thread's own event-loop callback. This module reports,
captures evidence, and keeps the server threads serving. It does NOT unfreeze
Houdini and must never be described as if it does.

RELATIONSHIP TO THE EXISTING FREEZE CHAIN
------------------------------------------
``synapse.server.freeze_chain`` already ships the detection ladder (1 s panel
beat → 5 s detect → 30 s sustained → breaker force_open + emergency halt, with
``freeze_dump_*.json`` evidence via ``telemetry_dump.flush_telemetry``). This
module does NOT build a second watchdog. It adds the two things that ladder
genuinely lacks for the starvation case:

  * **Thread stacks.** ``flush_telemetry`` captures counters, not frames. The
    discriminating observation for this defect is a MAIN frame stack ending in
    ``hdefereval._queueDeferred`` → ``threading.Condition.wait``; without stacks
    a post-mortem cannot tell that from a native modal loop or a heavy cook.
    :func:`dump_thread_stacks` supplies it.
  * **A non-beat-dependent trigger.** The chain arms only once something calls
    ``freeze_chain.beat()`` (the panel QTimer). Headless and ``/mcp``-only
    sessions never beat, so the ladder never arms there. A guard violation is a
    beat-independent starvation signal and reports on its own.

Zero ``hou`` at import. Zero Qt. Never raises from telemetry paths.
"""

from __future__ import annotations

import faulthandler
import logging
import os
import sys
import threading
import time
import traceback
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger("synapse.marshal_guard")

# Cached at import, matching main_thread._MAIN_THREAD_ID. Reading it here rather
# than importing main_thread keeps this module free of an import cycle
# (main_thread imports us lazily, inside a function).
_MAIN_THREAD_ID = threading.main_thread().ident

#: Env flag name. Documented in the module docstring; exported so tests and the
#: doctor can reference the single spelling rather than duplicating a literal.
GUARD_ENV_VAR = "SYNAPSE_MARSHAL_GUARD"

#: Env override for the inline-overrun budget, in seconds.
INLINE_BUDGET_ENV_VAR = "SYNAPSE_MAIN_INLINE_BUDGET_S"

MODE_WARN = "warn"
MODE_RAISE = "raise"
MODE_OFF = "off"
_VALID_MODES = (MODE_WARN, MODE_RAISE, MODE_OFF)

#: Default budget for a payload executing inline on the main thread via
#: run_on_main's fast path 2. Set to the freeze_chain detection threshold
#: (resilience.Watchdog.freeze_threshold default = 5.0 s): an inline payload
#: that outruns the freeze detector IS the freeze, by definition. Anything
#: shorter would flag ordinary cooks as pathological.
DEFAULT_INLINE_BUDGET_S = 5.0

#: Bounded ledger — this is telemetry, not a leak. FIFO eviction, same posture
#: as RecommendationHistory.DEFAULT_CAPACITY.
LEDGER_CAPACITY = 200

_ledger_lock = threading.Lock()
_ledger: Deque[Dict[str, Any]] = deque(maxlen=LEDGER_CAPACITY)
_counters = {
    "violations": 0,          # forbid_main_thread_block fired
    "inline_overruns": 0,     # note_main_thread_inline_overrun fired
    "stack_dumps": 0,
}

#: Rate limit for stack dumps. A starved main thread can produce a burst of
#: violations; writing a multi-megabyte dump per violation would turn a freeze
#: into a disk incident. One dump per this many seconds is enough for a
#: post-mortem (the frames do not change while the thread is parked).
_DUMP_MIN_INTERVAL_S = 30.0
_last_dump_ts = 0.0

FREEZE_STACK_PREFIX = "freeze_stacks_"


class MainThreadStarvationError(RuntimeError):
    """The main thread is about to block on something only it can complete.

    Raised by :func:`forbid_main_thread_block` when the guard is in ``raise``
    mode. Typed (not a bare ``RuntimeError``) so callers and tests can
    distinguish a structural starvation violation from ``run_on_main``'s
    ordinary "main thread didn't respond in time" timeout, which is a different
    condition with a different remedy.
    """


def guard_mode() -> str:
    """Current mode from the environment. Unknown values degrade to ``warn``.

    Read per call, not cached: a live session must be able to flip the guard
    without a restart, and the read is one ``os.environ`` lookup.
    """
    raw = (os.environ.get(GUARD_ENV_VAR) or MODE_WARN).strip().lower()
    return raw if raw in _VALID_MODES else MODE_WARN


def inline_budget_s() -> float:
    """Inline-execution budget in seconds; env-overridable, never raises."""
    try:
        return float(os.environ.get(INLINE_BUDGET_ENV_VAR, DEFAULT_INLINE_BUDGET_S))
    except (TypeError, ValueError):
        return DEFAULT_INLINE_BUDGET_S


def on_main_thread() -> bool:
    """True when the calling thread is the process main thread."""
    return threading.current_thread().ident == _MAIN_THREAD_ID


def _record(kind: str, payload: Dict[str, Any]) -> None:
    entry = {
        "kind": kind,
        "ts": time.time(),
        "thread": threading.current_thread().name,
        **payload,
    }
    with _ledger_lock:
        _ledger.append(entry)
        if kind in _counters:
            _counters[kind] += 1


def forbid_main_thread_block(where: str) -> None:
    """Assert that the caller is not about to starve the main thread.

    Call this immediately BEFORE entering a wait whose completion requires
    main-thread progress (see the module docstring's scoping rule — both
    conditions must hold, and condition 2 is the caller's assertion).

    Off-main callers return immediately: an off-main thread waiting on MAIN is
    the correct pattern and must stay silent, or the guard becomes noise.

    :param where: a stable, greppable identifier for the call site, e.g.
        ``"handlers_render._handle_render:render_marshal"``. It lands in the
        log line, the ledger entry, and the stack-dump filename metadata, so
        make it specific enough to locate without a debugger.
    :raises MainThreadStarvationError: only when ``SYNAPSE_MARSHAL_GUARD=raise``.
    """
    if not on_main_thread():
        return

    mode = guard_mode()
    stack = "".join(traceback.format_stack()[:-1])
    _record("violations", {"where": where, "mode": mode})

    if mode == MODE_OFF:
        return

    logger.error(
        "MAIN-THREAD STARVATION at %s — this thread is about to block on a "
        "result that only the main thread can produce, which is an "
        "unrecoverable self-deadlock (hdefereval._condition.wait has no "
        "timeout and no thread check). Route the call through "
        "synapse.server.main_thread.run_on_main, whose fast path 2 executes "
        "inline on the main thread instead of parking. Guard mode=%s "
        "(set %s=raise to make this fatal).\nStack:\n%s",
        where, mode, GUARD_ENV_VAR, stack,
    )
    dump_thread_stacks(reason="marshal_guard_violation", where=where)

    if mode == MODE_RAISE:
        raise MainThreadStarvationError(
            f"{where}: main thread would block on a main-thread-dependent "
            f"result (self-deadlock). Route through run_on_main."
        )


def note_main_thread_inline_overrun(
    where: str,
    elapsed_s: float,
    budget_s: Optional[float] = None,
    **extra: Any,
) -> None:
    """Record that an inline main-thread payload exceeded its budget.

    STABLE SIGNATURE — ``handlers_core`` and ``main_thread.run_on_main``'s fast
    path 2 both call this by exact name. Positional order is
    ``(where, elapsed_s, budget_s)``; ``**extra`` absorbs future keyword
    metadata (tool name, node path, …) without breaking existing callers. Do
    not reorder or rename the first three parameters.

    This is the honest counterpart to :func:`forbid_main_thread_block`.
    Migrating a marshal onto ``run_on_main`` makes a main-thread caller *run*
    the payload inline instead of deadlocking — strictly better, but it does
    NOT make the payload fast. A 90 s inline render still freezes the GUI for
    90 s; it simply recovers afterward instead of never. This sink measures
    exactly that residual so it stops being invisible.

    Pure telemetry: never raises, never blocks, never mutates control flow.

    :param where: stable call-site identifier (see ``forbid_main_thread_block``).
    :param elapsed_s: measured wall-clock duration of the inline payload.
    :param budget_s: the budget that was exceeded; defaults to
        :func:`inline_budget_s`.
    """
    try:
        budget = inline_budget_s() if budget_s is None else float(budget_s)
        elapsed = float(elapsed_s)
        _record("inline_overruns", {
            "where": where,
            "elapsed_s": elapsed,
            "budget_s": budget,
            **extra,
        })
        if guard_mode() == MODE_OFF:
            return
        logger.warning(
            "Main-thread inline payload at %s ran %.2fs (budget %.2fs) — the "
            "GUI was unresponsive for that whole window. Not a deadlock (it "
            "completed), but it is the residual freeze that only an "
            "out-of-process execution path can remove.%s",
            where, elapsed, budget,
            (" extra=%r" % (extra,)) if extra else "",
        )
    except Exception:  # pragma: no cover — telemetry must never break a caller
        logger.debug("note_main_thread_inline_overrun failed", exc_info=True)


def dump_thread_stacks(
    reason: str = "starvation",
    where: str = "",
    dir_path: Optional[str] = None,
) -> Optional[str]:
    """Write every thread's stack to a ``freeze_stacks_<UTC>.txt`` evidence file.

    This is the piece ``telemetry_dump.flush_telemetry`` does not provide: it
    captures counters, not frames. The discriminating observation for this
    defect class is a MAIN frame stack terminating in
    ``hdefereval._queueDeferred`` → ``threading.Condition.wait``. Without
    frames a post-mortem cannot separate that from a native modal loop or an
    ordinary heavy cook.

    Uses BOTH capture mechanisms deliberately:

    * ``faulthandler.dump_traceback(all_threads=True)`` — C-level, works even
      when the interpreter is in a bad way, and is the only one that can
      render a thread parked in a native frame.
    * ``sys._current_frames()`` + ``traceback`` — Python-level, gives thread
      names and richer formatting that faulthandler omits.

    Rate-limited to one dump per ``_DUMP_MIN_INTERVAL_S``: a starved main
    thread produces bursts, and the frames do not change while it is parked.

    Best-effort and non-raising by contract — it is called from error paths and
    daemon threads where an exception would mask the original problem. Returns
    the path written, or ``None`` if suppressed or failed.
    """
    global _last_dump_ts
    try:
        now = time.monotonic()
        with _ledger_lock:
            if now - _last_dump_ts < _DUMP_MIN_INTERVAL_S:
                return None
            _last_dump_ts = now
            _counters["stack_dumps"] += 1

        if dir_path is None:
            try:
                from ..core.logfile import log_dir
                dir_path = log_dir()
            except Exception:
                dir_path = os.path.join(os.path.expanduser("~"), ".synapse", "logs")
        os.makedirs(dir_path, exist_ok=True)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        target = os.path.join(dir_path, f"{FREEZE_STACK_PREFIX}{stamp}.txt")

        names = {t.ident: t.name for t in threading.enumerate()}
        with open(target, "w", encoding="utf-8") as f:
            f.write(f"# SYNAPSE thread-stack dump\n")
            f.write(f"# utc={datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"# reason={reason}\n")
            f.write(f"# where={where}\n")
            f.write(f"# main_thread_ident={_MAIN_THREAD_ID}\n")
            f.write(
                "# NOTE: this dump DIAGNOSES a starved main thread. It cannot\n"
                "# un-wedge one: a thread parked in hdefereval._condition.wait()\n"
                "# or in a native modal loop is unreachable from Python.\n\n"
            )

            f.write("=" * 72 + "\n== sys._current_frames() (named)\n" + "=" * 72 + "\n")
            for ident, frame in sys._current_frames().items():
                label = names.get(ident, "?")
                marker = "  <<< MAIN" if ident == _MAIN_THREAD_ID else ""
                f.write(f"\n--- thread {ident} ({label}){marker}\n")
                try:
                    f.write("".join(traceback.format_stack(frame)))
                except Exception as exc:
                    f.write(f"  <unformattable: {exc!r}>\n")

            f.write("\n" + "=" * 72 + "\n== faulthandler (C-level)\n" + "=" * 72 + "\n")
            f.flush()
            try:
                faulthandler.dump_traceback(file=f, all_threads=True)
            except Exception as exc:
                f.write(f"  <faulthandler unavailable: {exc!r}>\n")

        _prune_stack_dumps(dir_path)
        logger.error("Thread stacks dumped: %s", target)
        return target
    except Exception:
        logger.debug("dump_thread_stacks failed (best-effort)", exc_info=True)
        return None


def _prune_stack_dumps(directory: str, keep: int = 5) -> None:
    """Keep the newest *keep* dumps — mirrors telemetry_dump._prune_freeze_dumps."""
    try:
        dumps = [
            os.path.join(directory, name)
            for name in os.listdir(directory)
            if name.startswith(FREEZE_STACK_PREFIX) and name.endswith(".txt")
        ]
        dumps.sort(key=lambda p: (os.path.getmtime(p), p), reverse=True)
        for stale in dumps[keep:]:
            try:
                os.remove(stale)
            except OSError:
                pass
    except Exception:
        pass


def guard_events(n: int = 50) -> List[Dict[str, Any]]:
    """Newest-last copy of up to *n* ledger entries — safe to serialize."""
    with _ledger_lock:
        return list(_ledger)[-n:]


def guard_stats() -> Dict[str, Any]:
    """Snapshot of the guard counters (copy — safe to serialize).

    Surfaced for the doctor / telemetry dump. ``mode`` is included so a dump
    answers "was the guard even armed?" without a second lookup.
    """
    with _ledger_lock:
        return {
            "mode": guard_mode(),
            "inline_budget_s": inline_budget_s(),
            "ledger_size": len(_ledger),
            "ledger_capacity": LEDGER_CAPACITY,
            **_counters,
        }


def reset_guard_state() -> None:
    """Test/diagnostic helper — clear the ledger, counters, and dump throttle."""
    global _last_dump_ts
    with _ledger_lock:
        _ledger.clear()
        for key in _counters:
            _counters[key] = 0
        _last_dump_ts = 0.0
