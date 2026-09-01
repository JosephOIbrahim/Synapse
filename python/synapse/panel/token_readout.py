"""token_readout — the rail TOKEN surfaces (token_meter, token_pill), fed from
the per-task usage receipt on TASK COMPLETION.

WHY THIS EXISTS (BP2-PANELTRUTH T2). ``usage_sink`` carries a real per-task token
receipt from the worker's tool loop, and ``face_token`` already reads it on
tab-open (``refresh_from_probe``). Two rail surfaces were still dead: the rail
meter (``_meter_lbl``, compositor id ``token_meter``) and the CHAT-row TOKEN pill
(``_face_pills['token']``, id ``token_pill``). This module is the one display
rule that turns a ``usage_sink`` snapshot into their text, and the one hop the
panel calls on completion.

TWO NON-NEGOTIABLE RULES, both inherited from the Token face:

  1. Event-driven, NEVER polled. The refresh fires from task completion
     (``synapse_panel._on_done`` -> ``_refresh_token_surfaces``), the same
     discipline as the face's open-refresh. V3 was explicit: a probe must never
     be the thing that trips the rate limit it reports on, so there is no timer.

  2. UNKNOWN stays UNKNOWN (R162). A task that reported no token field leaves the
     meter EMPTY and the pill at its BASE label — never a fabricated zero, and
     never a fuel-gauge bar / quota ratio (V3-F4: headroom is not obtainable, so
     ``18.0k / 200k`` cannot be produced honestly). Only a genuinely reported
     count is ever shown.

Pure Python: no Qt, no ``hou``. The widgets are duck-typed (``setText``), so the
display rules test headless and the panel supplies the live labels.
"""

from __future__ import annotations

# The Token-tab vocabulary the sink snapshot exposes (usage_sink.snapshot()).
_FIELDS = ("input_tokens", "output_tokens", "cache_read", "cache_creation")

_UNSET = object()


def task_total(snap):
    """The task's total measured token spend, or ``None`` if NOTHING was
    measured. A field the API never reported is absent (None) and contributes
    nothing; a real reported ``0`` counts. ``None`` in => ``None`` out (no task).
    bool is never a token count (the usage_sink / provider guard)."""
    if not snap:
        return None
    present = [
        snap.get(f) for f in _FIELDS
    ]
    ints = [v for v in present if isinstance(v, int) and not isinstance(v, bool)]
    return sum(ints) if ints else None


def format_tokens(n):
    """Rail token-count display rule — tokens only, never a ratio and never $:
    ``812`` · ``18.0k`` · ``1.2M``. Mirrors synapse_panel._format_tokens; lives
    here so the rule is pure and testable."""
    n = int(n)
    if n < 1000:
        return "%d" % n
    if n < 1_000_000:
        return "%.1fk" % (n / 1000.0)
    return "%.1fM" % (n / 1_000_000.0)


def meter_text(snap):
    """Rail meter text for a snapshot. Empty string when UNKNOWN — the meter's
    honest resting state (never a fake ``0``, never a bar)."""
    total = task_total(snap)
    return "" if total is None else format_tokens(total)


def pill_text(snap, base="TOKEN"):
    """TOKEN pill text for a snapshot: the base label alone when UNKNOWN, or the
    label plus the measured figure once a task has really spent."""
    total = task_total(snap)
    return base if total is None else "%s  %s" % (base, format_tokens(total))


def refresh_surfaces(face=None, meter=None, pill=None, snap=_UNSET,
                     pill_base="TOKEN"):
    """Push the last task's usage receipt onto the three TOKEN surfaces.

    ``face`` is refreshed via ``refresh_from_probe`` (it reads usage_sink and the
    probe layer itself, rendering its own UNKNOWN when nothing is measured).
    ``meter`` / ``pill`` are duck-typed widgets updated via ``setText`` from
    ``snap`` (defaulting to ``USAGE_SINK.snapshot()`` when not injected — tests
    inject a snapshot directly). Every argument optional and every call guarded,
    so a partially-built panel or a missing surface never raises. Returns the
    task total (or None) for callers that want it. Event-driven only — the
    caller is task completion, never a timer."""
    if snap is _UNSET:
        try:
            from synapse.panel.usage_sink import USAGE_SINK
            snap = USAGE_SINK.snapshot()
        except Exception:
            snap = None
    if face is not None:
        try:
            face.refresh_from_probe()
        except Exception:
            pass
    if meter is not None:
        try:
            meter.setText(meter_text(snap))
        except Exception:
            pass
    if pill is not None:
        try:
            pill.setText(pill_text(snap, base=pill_base))
        except Exception:
            pass
    return task_total(snap)
