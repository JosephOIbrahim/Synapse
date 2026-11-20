"""Bounded main-thread execution (BRAINSTEM-4).

``run_on_main``'s timeout bounds the WAIT, never the WORK: a payload that has
started runs to completion, and a caller already on the main thread (the
``/mcp`` Fast path 2) is not bounded at all — its ``timeout`` argument is
discarded by construction. A hung ``execute_python`` therefore captures
Houdini's main thread, and the GUI with it, for as long as the script runs.

This module adds the cooperative bound the harness can actually keep:

* :func:`run_under_deadline` arms ``sys.settrace`` for the duration of a
  payload. CPython calls the trace function on every executed LINE of a
  watched frame, so a pure-Python loop (``while True: pass``) is interrupted
  at the deadline by raising :class:`DeadlineExceeded` from the tracer.
  ``watch_filename`` limits line tracing to the payload's own compiled unit
  (``<synapse_exec>``), so library frames pay only one global-trace call per
  call/return, not per line — the interpreter cost stays close to normal for
  code the payload merely calls.
* :class:`Deadline` is the clock alone, for payloads whose long part is not
  Python (a VEX cook): check it before starting an uninterruptible call and
  report the overrun after.

Three residuals are documented rather than papered over:

1. **C calls are not interruptible.** A frame blocked inside a C extension
   (``hou.node.cook()``, a render, file I/O) emits no Python line events until
   it returns. The deadline fires the moment control comes back; it cannot
   fire inside the call.
2. **A swallowed interruption.** If the payload catches ``BaseException``
   around its loop, CPython unsets the trace function after the tracer raises,
   and a subsequent loop is not interrupted again. :func:`run_under_deadline`
   detects a payload that RETURNED after the deadline had already fired and
   raises then, so a swallowed deadline cannot read as a clean success. A loop
   that keeps running after swallowing is outside any in-process cooperative
   bound; the off-main caller's ``MainThreadTimeout`` still reports it.
3. **A CPython 3.11 line-event gap.** On 3.11 a loop whose body shares the
   header line (``while True: pass``) can emit no line events to a trace
   function, so the tracer cannot fire and that payload is not bounded there.
   The same payload fires on 3.12 and later, and Houdini 22 ships Python 3.13,
   so the product runtime is covered; the CI 3.11 leg pins the two-line form
   and the 3.12+ legs pin the one-line form.

Kill switch: ``SYNAPSE_EXEC_DEADLINE=0`` disarms the trace (read at call
time), for an artist who would rather pay a slow script than a slowed one.
"""

import os
import sys
import time


class DeadlineExceeded(TimeoutError):
    """A payload was stopped at its main-thread deadline.

    ``TimeoutError`` (not ``RuntimeError``) because the condition is a
    deadline, and the host-layer timeout class is a ``TimeoutError`` too.
    ``partial`` is True when the payload may have changed the scene before it
    stopped — the caller must say so rather than implying a clean rollback.
    """

    def __init__(self, label, budget_s, elapsed_s=0.0):
        self.label = label
        self.budget_s = float(budget_s)
        self.elapsed_s = float(elapsed_s)
        self.partial = True
        super().__init__(
            "%s exceeded its %.1fs main-thread deadline (ran %.1fs); it was "
            "stopped at the deadline and the scene may be partial."
            % (label, self.budget_s, self.elapsed_s)
        )


def deadlines_enabled():
    """SYNAPSE_EXEC_DEADLINE, ON by default (read at call time)."""
    return os.environ.get("SYNAPSE_EXEC_DEADLINE", "1").strip().lower() not in (
        "0", "false", "off", "no",
    )


class Deadline:
    """A wall-clock budget for one payload, checked at explicit points.

    For work the tracer cannot interrupt (a C cook): ``check()`` before
    starting it, ``expired()`` after it returns. Never claims to have stopped
    anything it did not.
    """

    def __init__(self, budget_s, label="payload"):
        self.budget_s = float(budget_s)
        self.label = label
        self.started = time.monotonic()

    def elapsed(self):
        return time.monotonic() - self.started

    def expired(self):
        return self.elapsed() >= self.budget_s

    def check(self):
        """Raise :class:`DeadlineExceeded` when the budget is already spent."""
        elapsed = self.elapsed()
        if elapsed >= self.budget_s:
            raise DeadlineExceeded(self.label, self.budget_s, elapsed)


def run_under_deadline(fn, budget_s, label="payload", watch_filename=None):
    """Run *fn* on THIS thread, raising :class:`DeadlineExceeded` at the deadline.

    The trace function is armed on the calling thread and restored on the way
    out, so it never leaks into the caller's frames. ``watch_filename`` limits
    line tracing to frames compiled from that filename (the exec'd payload's
    ``<synapse_exec>`` unit); ``None`` watches every Python frame.

    Returns fn()'s value. Raises whatever fn() raised, except that a payload
    which swallowed the tracer's interruption and then returned does not get
    to read as a success: the deadline has fired and the scene may be partial.
    """
    if budget_s is None or budget_s <= 0 or not deadlines_enabled():
        return fn()

    deadline = Deadline(budget_s, label)
    previous = sys.gettrace()
    fired = [False]

    def _local_trace(frame, event, arg):
        if event == "line" and not fired[0]:
            elapsed = deadline.elapsed()
            if elapsed >= deadline.budget_s:
                fired[0] = True
                raise DeadlineExceeded(deadline.label, deadline.budget_s, elapsed)
        return _local_trace

    def _global_trace(frame, event, arg):
        if watch_filename is not None and frame.f_code.co_filename != watch_filename:
            return None
        return _local_trace

    sys.settrace(_global_trace)
    try:
        result = fn()
    finally:
        # Restore unconditionally: the payload owns no trace function, and a
        # caller (coverage, a debugger) may have had one armed.
        sys.settrace(previous)

    if fired[0]:
        # The tracer raised, but the payload caught it and returned anyway.
        # Reporting success would hide both the interruption and the partial
        # state it left behind.
        raise DeadlineExceeded(label, deadline.budget_s, deadline.elapsed())
    return result
