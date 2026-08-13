"""Result-path main-thread instrumentation — the Qt half of the freeze attribution.

WHAT THIS MEASURES, AND WHY IT DID NOT EXIST
--------------------------------------------
Every existing main-thread instrument sits in the *dispatch* or *marshal* layer:

  * ``main_thread.dispatch_wait_stats``  — enqueue→start wake latency (worker path)
  * ``main_thread.main_thread_direct_stats`` — ``fn()`` duration on run_on_main fast path 2
  * ``main_thread.main_thread_hold_stats``   — ``fn()`` duration inside the deferred ``_on_main``
  * ``tool_executor.panel_inline_stats``     — full inline TOOL dispatch cost

Not one of them covers the Qt slots that render a reply. The panel's result path —
``_on_token`` → ``ChatDisplay.stream_chunk``, ``_on_done`` → ``end_stream`` →
``format_synapse_message`` → ``insertHtml``, and the end-of-turn Review rebuild — runs
entirely on Houdini's main thread (Qt AutoConnection from the ClaudeWorker QThread
resolves to QueuedConnection, so the slot body executes on main) and carried **zero**
timing. A stall there is indistinguishable, from telemetry alone, from a stall anywhere
else — which is exactly why the residual freeze has stayed unattributed.

This module is the missing sink. It is measurement only: it creates no bound, no
timeout and no bail-out, and it changes no control flow. It cannot make the panel
faster; it can only make the cost *visible*, which is the precondition for deciding
whether anything should be done about it.

THREAD ATTRIBUTION IS MEASURED, NEVER ASSUMED
---------------------------------------------
``on_main`` is derived from a real ``threading`` identity check at record time, never
from a proxy such as "this is a Qt slot so it must be main". That proxy is precisely
what corrupted the 2026-07-31 tool-attribution numbers (see
``tool_executor._record_panel_inline`` and FREEZE_FORENSICS_20260731.md §2), and
off-main samples are counted separately here for the same reason: a phase that ran off
the main thread stalled no Qt event loop, and folding it into main-thread hold time
sends the next investigator at the wrong mechanism.

RELATIONSHIP TO marshal_guard
-----------------------------
Convention-matched to ``server.marshal_guard``: it honours the same
``SYNAPSE_MARSHAL_GUARD`` mode (``warn`` default → record + log; ``off`` → record
only), and a main-thread phase that outruns ``marshal_guard.inline_budget_s()``
additionally reports through the existing
``marshal_guard.note_main_thread_inline_overrun`` sink so Qt-side holds land in the
same ledger a freeze post-mortem already reads. Reusing that sink rather than adding a
second one is deliberate — a parallel ledger would split the evidence.

Zero ``hou`` at import. Zero Qt at import. Never raises from a telemetry path. The
zero-Qt property is load-bearing: it lets the headless metrics surface import this
accessor, unlike ``tool_executor.panel_inline_stats`` whose import pulls in Qt and is
therefore ``None`` in a headless server.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("synapse.panel.result_telemetry")

#: A single main-thread result-path phase over this is logged and counted "slow".
#: Deliberately far below ``marshal_guard``'s 5.0 s inline budget: that budget marks
#: "this IS the freeze", whereas a result-render phase over a quarter second is already
#: a visible hitch in a GUI the artist is typing into. Two thresholds, two questions.
PANEL_RESULT_SLOW_MS = 250.0

#: The phases of the result path, in data-flow order. Fixed set — this dict never
#: grows at runtime, so the telemetry surface is bounded by construction.
#:
#: ``payload_chars`` is a per-phase SIZE PROXY, not a universal character count.
#: Every call site is required to pick a proxy that is O(1) to obtain: an
#: instrument that costs as much as the work it measures corrupts its own reading.
#: Current meanings — ``send``: conversation MESSAGE COUNT (summing the history's
#: characters would be O(conversation) on the measured thread); ``stream``: token
#: length; ``finalize``: reply length; ``append``: formatted-HTML length;
#: ``review``: unused (0). ``doc_chars`` is always the QTextDocument character
#: count, which Qt stores and returns in O(1).
PHASES = (
    "send",             # _start_worker: tools + system prompt + ClaudeWorker(deepcopy)
    "stream",           # _on_token → ChatDisplay.stream_chunk (once per SSE delta)
    "finalize",         # _on_done → ChatDisplay.end_stream (remove span + reformat)
    "append",           # ChatDisplay.append_synapse_message (formatter + insertHtml)
    "review",           # _set_busy not-busy edge → _populate_review widget rebuild
)


def _blank() -> Dict[str, Any]:
    return {
        # MAIN-THREAD samples only. These mean "the Qt loop was stalled this long";
        # nothing else may be added to them.
        "count": 0,
        "sum_ms": 0.0,
        "max_ms": 0.0,
        "slow_count": 0,
        # Payload-size context, so a duration can be read against what produced it.
        # Without these a 6 s sample is a number; with them it is a scaling law.
        "max_payload_chars": 0,
        "max_doc_chars": 0,
        "payload_chars_at_max_ms": 0,
        "doc_chars_at_max_ms": 0,
        # OFF-MAIN samples, counted separately and never mixed in (see module
        # docstring). An off-main phase stalls no Qt loop.
        "offmain_count": 0,
        "offmain_sum_ms": 0.0,
        "offmain_max_ms": 0.0,
    }


_result_lock = threading.Lock()
_result_stats: Dict[str, Dict[str, Any]] = {p: _blank() for p in PHASES}


def record_result_phase(
    phase: str,
    ms: float,
    payload_chars: int = 0,
    doc_chars: int = 0,
    on_main: Optional[bool] = None,
) -> None:
    """Record one result-path phase duration, attributed by REAL thread identity.

    Pure telemetry: never raises, never blocks, never changes control flow.

    :param phase: one of :data:`PHASES`. An unknown phase is dropped rather than
        silently creating a key — the phase set is a contract with the metrics
        renderer, and a typo must not invent a series that nothing reads.
    :param ms: measured wall-clock duration in milliseconds.
    :param payload_chars: size of the content this phase processed (reply text,
        token, formatted HTML). 0 when not meaningful.
    :param doc_chars: size of the QTextDocument at the time, so the O(document)
        scaling of Qt rich-text layout is readable from the sample itself.
    :param on_main: leave ``None`` to measure thread identity here (the correct
        default). Pass explicitly only when the caller already computed it at
        execution time — never pass a proxy flag.
    """
    try:
        if phase not in _result_stats:
            return
        if on_main is None:
            on_main = threading.current_thread() is threading.main_thread()
        ms = float(ms)

        with _result_lock:
            slot = _result_stats[phase]
            if not on_main:
                slot["offmain_count"] += 1
                slot["offmain_sum_ms"] += ms
                if ms > slot["offmain_max_ms"]:
                    slot["offmain_max_ms"] = ms
                return
            slot["count"] += 1
            slot["sum_ms"] += ms
            if payload_chars > slot["max_payload_chars"]:
                slot["max_payload_chars"] = int(payload_chars)
            if doc_chars > slot["max_doc_chars"]:
                slot["max_doc_chars"] = int(doc_chars)
            if ms > slot["max_ms"]:
                slot["max_ms"] = ms
                slot["payload_chars_at_max_ms"] = int(payload_chars)
                slot["doc_chars_at_max_ms"] = int(doc_chars)
            is_slow = ms >= PANEL_RESULT_SLOW_MS
            if is_slow:
                slot["slow_count"] += 1

        if not is_slow:
            return

        # Mode-aware logging, matching marshal_guard: `off` records but stays silent.
        try:
            from ..server.marshal_guard import (
                guard_mode, inline_budget_s, note_main_thread_inline_overrun,
                MODE_OFF,
            )
        except Exception:
            return

        if guard_mode() == MODE_OFF:
            return

        logger.warning(
            "Result-path phase %r held the Qt main thread %.0fms "
            "(payload=%d chars, document=%d chars) — the GUI was unresponsive for "
            "that window. Measurement only; this instrument imposes no bound.",
            phase, ms, payload_chars, doc_chars,
        )

        # A Qt-side hold that outruns the inline budget IS the freeze by the same
        # definition marshal_guard uses. Report it into the existing ledger rather
        # than a second one, so a post-mortem reads one surface.
        budget_s = inline_budget_s()
        if ms / 1000.0 > budget_s:
            note_main_thread_inline_overrun(
                "panel.result_telemetry:%s" % phase,
                ms / 1000.0,
                budget_s,
                payload_chars=payload_chars,
                doc_chars=doc_chars,
            )
    except Exception:  # pragma: no cover — telemetry must never break the caller
        logger.debug("record_result_phase failed", exc_info=True)


class timed_phase:
    """Context manager timing one result-path phase. Records on the way out.

    Records even when the body raises, then lets the exception propagate untouched —
    a phase that blew up still occupied the main thread for however long it ran, and
    swallowing the error would change behaviour. Sizes may be supplied after entry
    via :meth:`set_sizes`, for call sites where the payload is only known inside the
    block.

    Usage::

        with timed_phase("finalize", payload_chars=len(text)):
            self._chat.end_stream(text, signed=signed)
    """

    __slots__ = ("phase", "payload_chars", "doc_chars", "_t0")

    def __init__(self, phase: str, payload_chars: int = 0, doc_chars: int = 0) -> None:
        self.phase = phase
        self.payload_chars = payload_chars
        self.doc_chars = doc_chars
        self._t0 = 0.0

    def set_sizes(self, payload_chars: Optional[int] = None,
                  doc_chars: Optional[int] = None) -> None:
        if payload_chars is not None:
            self.payload_chars = payload_chars
        if doc_chars is not None:
            self.doc_chars = doc_chars

    def __enter__(self) -> "timed_phase":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        record_result_phase(
            self.phase,
            (time.perf_counter() - self._t0) * 1000.0,
            payload_chars=self.payload_chars,
            doc_chars=self.doc_chars,
        )
        return False  # never suppress


def result_render_stats() -> Dict[str, Dict[str, Any]]:
    """Snapshot of the result-path phase counters (deep copy — safe to serialize).

    Complements the marshal-layer histograms: those answer "how long did a *tool*
    hold main", this answers "how long did *rendering the reply* hold main".
    """
    with _result_lock:
        return {p: dict(s) for p, s in _result_stats.items()}


def reset_result_render_stats() -> None:
    """Test/diagnostic helper — zero every phase counter."""
    with _result_lock:
        for p in PHASES:
            _result_stats[p] = _blank()


# ---------------------------------------------------------------------------
# GUI-evidence gate (W1-MTFIX) — headless timing is NOT evidence
# ---------------------------------------------------------------------------
#
# The result-path phase durations, and the deferred-path main-thread hold, mean
# "the Qt GUI event loop was stalled this long" ONLY in a GUI Houdini session. In a
# headless session (hython / husk batch) there is no GUI loop to stall, so a 0.0 is
# "nothing ran", not "nothing stalled" — and a 0.0 read as an improvement is exactly
# the bug class this repo documents (the lastCookTime vendor contract: a timing the
# vendor only populates under a GUI is not evidence when measured headless). These
# helpers let a reader — the FRZ probe, the metrics surface, a receipt — stamp the
# gui_required metrics UNKNOWN off-GUI instead of reporting a misleading zero.
#
# The hou import is LAZY, inside the gate: this module's zero-hou / zero-Qt-at-import
# property is load-bearing (the headless server imports these accessors) and pinned
# by test_module_imports_without_qt. Never introduce a module-level hou/Qt import.

#: Result phases whose value is evidence only in a GUI session — the two the
#: W1-MTFIX acceptance marks gui_required (append, finalize). ``send``/``stream``/
#: ``review`` are not gated here: the acceptance is specifically about these two.
GUI_REQUIRED_PHASES = ("append", "finalize")


def gui_timing_is_evidence() -> Optional[bool]:
    """Is result-path / main-thread-hold timing in THIS process valid GUI evidence?

    ``True``  — a GUI Houdini session (``hou.isUIAvailable()``): the Qt loop the
                result phases stall is real, so their durations mean what the
                gui_required acceptance predicates read them to mean.
    ``False`` — a Houdini session with no UI (hython / husk batch): the loop is
                absent, so a 0.0 is "nothing ran", not "nothing stalled".
    ``None``  — no ``hou`` at all (standalone / CI / the sidecar brain): GUI timing
                is not even defined; there is no GUI to stall.

    Lazy ``hou`` import (see section note). Never raises.
    """
    try:
        import hou
    except Exception:
        return None
    try:
        return bool(hou.isUIAvailable())
    except Exception:
        return None


def gui_metric_verdict(value: Any) -> Any:
    """Stamp one gui_required metric: return ``value`` in a GUI session, else the
    string ``"UNKNOWN"``.

    The single primitive behind the headless-is-not-evidence contract. A headless
    0.0 is "unmeasured", never "fast", and must never read as a pass — so off-GUI
    this returns ``"UNKNOWN"`` rather than the raw number (which is typically 0.0
    because nothing rendered). Used for BOTH the panel phases (below) and the
    ``main_thread_hold_slowest_ms{synapse_doctor}`` reading, so the two GUI-gated
    surfaces share one rule.
    """
    return value if gui_timing_is_evidence() is True else "UNKNOWN"


def result_evidence_verdict(stats: Optional[Dict[str, Dict[str, Any]]] = None
                            ) -> Dict[str, Dict[str, Any]]:
    """Per-phase evidence verdict for the gui_required result phases.

    Returns ``{phase: {"gui_evidence": bool, "max_ms": float|"UNKNOWN",
    "count": int}}``. Off-GUI every ``max_ms`` is ``"UNKNOWN"`` (never 0.0), so a
    headless reader cannot mistake "unmeasured" for "fast"; in a GUI session it is
    the recorded number. Pure telemetry: no hou beyond the lazy gate, never raises.
    """
    if stats is None:
        stats = result_render_stats()
    is_gui = gui_timing_is_evidence() is True
    out: Dict[str, Dict[str, Any]] = {}
    for phase in GUI_REQUIRED_PHASES:
        slot = stats.get(phase) or {}
        out[phase] = {
            "gui_evidence": is_gui,
            "max_ms": gui_metric_verdict(float(slot.get("max_ms", 0.0) or 0.0)),
            "count": int(slot.get("count", 0) or 0),
        }
    return out
