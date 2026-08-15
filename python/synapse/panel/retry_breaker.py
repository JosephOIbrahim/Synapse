"""F2 retry cascade circuit-breaker (2026-08-14) — pure decision half.

Background: a 179s inline (fast-path-2) ``execute_python`` hold became a
3-minute lockup because the panel re-issued the same command 5x at 30s while
zombies were still running — retries are new tool-use iterations, so they
bypassed the WS stall gate's judgment entirely.

The breaker consults the F4 in-flight register
(``server.main_thread.current_main_thread_holder()`` → ``(label, start_ts)``),
NEVER ``stall_state()``. ``stall_state()`` counts DEFERRED-path timeouts only
(``_record_timeout``); fast path 2 has no timeout by design, so the inline
class — exactly the class this breaker polices — never moves it. The register
covers both dispatch paths and carries ``start_ts``, which is what lets the
artist-facing sentence date the CURRENT hold.

This module is pure (no Qt, no hou) so the decision logic is testable
standalone; the worker wiring lives in ``claude_worker.py``.
"""

from __future__ import annotations

import time

ABANDON_THRESHOLD = 2  # consecutive abandoned attempts of the SAME command


def breaker_message(holder, consecutive_abandons, now=None):
    """Return the circuit-breaker sentence, or None when retrying is allowed.

    Args:
        holder: ``(label, start_ts)`` from ``current_main_thread_holder()``,
            or None when the main thread is idle between payloads.
        consecutive_abandons: count of consecutive main-thread timeout/abandon
            outcomes recorded for this exact command (tool + input).
        now: injectable clock (seconds epoch) for tests; defaults to
            ``time.time()``.

    The breaker opens only when BOTH: the abandon count has reached
    ``ABANDON_THRESHOLD`` AND a holder exists right now — an idle main thread
    means the prior hold cleared between iterations and a retry is safe.
    """
    if consecutive_abandons < ABANDON_THRESHOLD or holder is None:
        return None
    label, start_ts = holder
    elapsed = int((time.time() if now is None else now) - start_ts)
    return (
        "Houdini is busy — a {} operation has held the UI for {}s. "
        "Try again when it finishes.".format(label, elapsed)
    )
