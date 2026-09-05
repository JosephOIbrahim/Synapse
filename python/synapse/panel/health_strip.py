"""Panel health strip — the always-visible status surface (P0.3).

The doctor is honest; the panel was not. An artist mid-show had no way to know
the memory backend fell back to jsonl, that vector recall was off, or that the
bridge was unreachable — the tool *looked* healthy and quietly did less. This
module closes that gap with a slim, always-visible strip of four FACT-sourced
cells:

    ● connection   ● memory backend   ● project / show   ● active job

Two rules govern every cell, and they are the whole point of the file:

1. **FACT-sourced or UNKNOWN.** A cell is green (OK) only when a real producer
   said so. There is no default-healthy path. If a fact was not measured or
   could not be read, the cell renders UNKNOWN (a calm grey) — never green,
   never a fabricated ``0``. (This is why every ``StripSnapshot`` field defaults
   to the ``UNMEASURED`` sentinel rather than to ``None`` or a healthy value:
   ``None`` is a *measured* "nothing here" and reads differently from "never
   looked".)

2. **Degraded is loud.** A backend fallback (moneta → jsonl) renders amber/red
   with the doctor's one-line reason inline — no click required to notice. The
   ``384 vs 256`` embedding-dim mismatch that silently dropped memory to jsonl
   is shown verbatim, because it arrives inside that reason string.

Producer paths (one per cell — a green cell without one is a BLOCK):
  - connection    ← the panel's own live derivation (hou reachable / gate not
                    stale), passed in from ``_update_context``.
  - memory backend← ``synapse.memory.store.backend_fallback()`` (a process-global
                    read, never a store construction) + a non-constructing peek
                    at the ``_global_synapse`` singleton for the "moneta is live"
                    positive. NEVER ``synapse_health.healthy`` — that field is a
                    hardcoded ``True`` liveness echo (handlers.py) and would pin
                    the cell green forever.
  - project       ← the current hip / show name the panel already reads.
  - active job    ← ``synapse.server.render_session.active_session()`` (in-process,
                    no hou, no main thread). NEVER ``render_farm_status["running"]``
                    — it defaults ``False`` when no farm object exists and masks a
                    live render.

Threading: the strip performs NO main-thread I/O. It renders a snapshot the
panel's existing 2 s timer hands it; ``gather_snapshot`` reads only O(1)
in-process module state. It must never become the next ``synapse_doctor``
648 ms main-thread hold — so it never calls the doctor or ``get_health``.

Colour comes entirely from the design system's one STATUS vocabulary
(``designsystem.tokens.STATUS``); this module declares no colour of its own,
inheriting H4's single-authority token state.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any, List, Optional

from synapse.panel.designsystem import tokens as t

# ── Qt imports (PySide6 primary, PySide2 fallback, None standalone) ──────
# Mirrors context_bar.py: the pure-data core below imports with none of these,
# so state/format logic is testable under stock CPython with no PySide.
_QT_AVAILABLE = False
try:
    from PySide6 import QtWidgets, QtCore  # noqa: F401
    _QT_AVAILABLE = True
except ImportError:
    try:
        from PySide2 import QtWidgets, QtCore  # noqa: F401
        _QT_AVAILABLE = True
    except ImportError:
        QtWidgets = None
        QtCore = None


# ======================================================================
# 1. Verdict vocabulary  (mapped onto the design system's STATUS grammar)
# ======================================================================

class Verdict:
    """The five states a cell can hold. Plain strings, not an Enum, so a cell
    round-trips through json/dict trivially and a test reads literally.

    OK / AMBER / RED / UNKNOWN are the health verdicts the brief names. IDLE and
    WORKING are the *measured-but-not-a-problem* states — a saved scene with no
    render running is IDLE, not UNKNOWN (we looked; it is genuinely quiet) and
    not OK-green (nothing to celebrate). Keeping them distinct is what lets
    UNKNOWN mean strictly "we could not measure this", which is the honesty the
    strip exists to protect.
    """

    OK = "ok"
    AMBER = "amber"
    RED = "red"
    UNKNOWN = "unknown"
    IDLE = "idle"
    WORKING = "working"


# Verdict → a key in tokens.STATUS. We borrow the design system's ONE status
# vocabulary rather than declaring colour here (H4: exactly one colour
# authority under panel/). UNKNOWN maps to "disconnected" — the calm SLATE grey,
# never a green — which is the visual guarantee behind rule 1.
_VERDICT_STATUS = {
    Verdict.OK: "connected",       # GROW  — verified / serving
    Verdict.AMBER: "warning",      # WARN  — degraded, worth a look
    Verdict.RED: "error",          # ERROR — degraded, loud
    Verdict.UNKNOWN: "disconnected",  # SLATE — not measured (NOT green)
    Verdict.IDLE: "idle",          # SIGNAL — measured, standing by
    Verdict.WORKING: "working",    # FIRE  — a job is in flight
}


def verdict_color(verdict: str) -> str:
    """The design-system hex for a verdict, via the STATUS grammar. UNKNOWN is
    grey, never green — the property the anti-silent-degradation contract rests
    on."""
    key = _VERDICT_STATUS.get(verdict, "disconnected")
    return t.STATUS.get(key, t.STATUS["idle"])[0]


# ======================================================================
# 2. Cell + snapshot data model
# ======================================================================

class _Unmeasured:
    """Sentinel: this fact was never read. Distinct from ``None`` (a measured
    absence). A field still holding this renders UNKNOWN."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return "UNMEASURED"

    def __bool__(self) -> bool:
        return False


UNMEASURED = _Unmeasured()


@dataclass
class StripCell:
    """One rendered cell. ``value`` is the short display string; ``reason`` is
    the one-line detail shown inline (loud) for degraded states."""

    key: str          # "connection" | "memory" | "project" | "job"
    label: str        # short human title, e.g. "mem"
    verdict: str      # Verdict.*
    value: str        # short display text — never a fabricated "0"/"ok"
    reason: str = ""  # one-line detail (degraded cells render this without a click)

    @property
    def color(self) -> str:
        return verdict_color(self.verdict)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "verdict": self.verdict,
            "value": self.value,
            "reason": self.reason,
            "color": self.color,
        }


@dataclass
class StripSnapshot:
    """The raw facts the four cells are built from. Every field defaults to
    ``UNMEASURED`` — a producer must overwrite it with a real reading, or the
    corresponding cell is UNKNOWN. That default is the anti-silent-degradation
    guarantee expressed as a data shape.

    Field shapes:
      connection : UNMEASURED | "ok" | "warning"
                   ("ok" = hou reachable + gate fresh; "warning" = gate stale)
      memory     : UNMEASURED | {"fallback": <dict|None>,
                                  "backend": <str|None>,
                                  "moneta_live": <bool|None>}
      project    : UNMEASURED | <str name> | None  (None = measured "untitled")
      active_job : UNMEASURED | <dict>            | None  (None = measured "idle")
    """

    connection: Any = UNMEASURED
    memory: Any = UNMEASURED
    project: Any = UNMEASURED
    active_job: Any = UNMEASURED


# ======================================================================
# 3. Pure cell builders  (the tested core — no Qt, no hou, no I/O)
# ======================================================================

def cell_connection(connection: Any) -> StripCell:
    """connection cell. UNMEASURED / anything not a known live state → UNKNOWN
    (never green from absence)."""
    if connection == "ok":
        return StripCell("connection", "link", Verdict.OK, "Houdini")
    if connection == "warning":
        return StripCell(
            "connection", "link", Verdict.AMBER, "API gate stale",
            reason="Houdini reachable but the phantom-API gate is stale",
        )
    # UNMEASURED, standalone (no hou), or any unrecognised value: we cannot
    # assert a connection, so we say so.
    return StripCell("connection", "link", Verdict.UNKNOWN, "unknown")


def cell_memory(memory: Any) -> StripCell:
    """memory-backend cell — the heart of the leg.

    A recorded fallback (moneta → jsonl) is loud: RED with the doctor's one-line
    reason, which carries the ``384 vs 256`` mismatch text when that is the
    cause. A confirmed live Moneta store is OK. Everything we could NOT read —
    including the ambiguous "no fallback recorded but no live store confirmed" —
    is UNKNOWN, never a default green.
    """
    if not isinstance(memory, dict):
        return StripCell("memory", "mem", Verdict.UNKNOWN, "unknown")

    fallback = memory.get("fallback")
    if isinstance(fallback, dict):
        served = fallback.get("served") or "jsonl"
        requested = fallback.get("requested") or "moneta"
        reason = fallback.get("reason") or (
            "backend %r fell back to %s" % (requested, served)
        )
        return StripCell(
            "memory", "mem", Verdict.RED,
            "%s (fell back)" % served,
            reason=reason,
        )

    moneta_live = memory.get("moneta_live")
    if moneta_live is True:
        return StripCell("memory", "mem", Verdict.OK, "moneta")
    if moneta_live is False:
        backend = memory.get("backend")
        if backend:
            # A measured, live, non-fallen-back backend (e.g. jsonl by config):
            # real and not a degradation, so shown plainly — not alarmed, not
            # faked green-with-no-producer.
            return StripCell("memory", "mem", Verdict.OK, str(backend))
        return StripCell("memory", "mem", Verdict.UNKNOWN, "unknown")

    # moneta_live is None / missing: we could not confirm the live backend.
    # Absence of a fallback record is NOT proof of health.
    return StripCell("memory", "mem", Verdict.UNKNOWN, "unknown")


def cell_project(project: Any) -> StripCell:
    """project / show cell. A name → OK. A measured-untitled scene → IDLE
    (standing by), which is honest and distinct from UNKNOWN. UNMEASURED →
    UNKNOWN."""
    if isinstance(project, str) and project.strip():
        return StripCell("project", "show", Verdict.OK, project.strip())
    if project is None:
        return StripCell("project", "show", Verdict.IDLE, "untitled")
    return StripCell("project", "show", Verdict.UNKNOWN, "unknown")


def cell_job(active_job: Any) -> StripCell:
    """active-job cell. A running session → WORKING. A measured "no active
    session" → IDLE. UNMEASURED → UNKNOWN (never a fake ``0 jobs``)."""
    if isinstance(active_job, dict):
        label = active_job.get("label") or active_job.get("rop") or "rendering"
        return StripCell("job", "job", Verdict.WORKING, str(label))
    if active_job is None:
        return StripCell("job", "job", Verdict.IDLE, "idle")
    return StripCell("job", "job", Verdict.UNKNOWN, "unknown")


def build_cells(snapshot: StripSnapshot) -> List[StripCell]:
    """The four cells, in strip order, from a snapshot. Pure and total: every
    input shape yields exactly four cells and never raises."""
    return [
        cell_connection(snapshot.connection),
        cell_memory(snapshot.memory),
        cell_project(snapshot.project),
        cell_job(snapshot.active_job),
    ]


# ======================================================================
# 4. Non-blocking gather  (lazy, guarded, O(1) in-process reads only)
# ======================================================================

def _gather_memory() -> Any:
    """Read the memory-backend fact without constructing anything or blocking.

    ``backend_fallback()`` is a process-global read. The "is Moneta live"
    positive peeks the ``_global_synapse`` singleton directly — it does NOT call
    ``get_synapse_memory()``, which would build the store (the very act that can
    fall back / block). Returns UNMEASURED if the store module is not importable,
    which renders UNKNOWN rather than a fabricated green.
    """
    try:
        from synapse.memory import store as _store
    except Exception:
        return UNMEASURED

    fallback = None
    try:
        fallback = _store.backend_fallback()
    except Exception:
        fallback = None

    moneta_live: Optional[bool] = None
    backend: Optional[str] = None
    try:
        singleton = getattr(_store, "_global_synapse", None)
        if singleton is not None:
            live_store = getattr(singleton, "store", None)
            if live_store is not None:
                cls = type(live_store).__name__
                backend = cls
                moneta_live = (cls == "MonetaBackedStore")
    except Exception:
        moneta_live = None
        backend = None

    return {"fallback": fallback, "backend": backend, "moneta_live": moneta_live}


def _gather_active_job() -> Any:
    """Read the active-render fact from the in-process render-session registry
    (no hou, no main thread). Returns UNMEASURED if unreadable, None for a
    measured "nothing running", or a small dict for a running session."""
    try:
        from synapse.server import render_session as _rs
    except Exception:
        return UNMEASURED
    try:
        active = _rs.active_session()
    except Exception:
        return UNMEASURED
    if not active:
        return None  # measured: no running session
    _token, sess = active
    meta = sess.get("meta") or {}
    label = meta.get("rop") or meta.get("label") or "rendering"
    return {"token": sess.get("token"), "label": label, "meta": meta}


def gather_snapshot(
    connection: Any = UNMEASURED,
    project: Any = UNMEASURED,
) -> StripSnapshot:
    """Assemble a snapshot from cheap in-process facts. ``connection`` and
    ``project`` are handed in by the panel (facts it already reads on its 2 s
    tick — no new hou I/O); memory and active-job are read here from O(1) module
    state. Never raises; any unreadable fact stays UNMEASURED → UNKNOWN."""
    return StripSnapshot(
        connection=connection,
        memory=_gather_memory(),
        project=project,
        active_job=_gather_active_job(),
    )


# ======================================================================
# 5. Rendering helpers (pure string — testable without Qt)
# ======================================================================

_REASON_INLINE_MAX = 72


def _truncate(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def cell_html(cell: StripCell) -> str:
    """Rich-text for one cell: a status dot in the verdict colour + label:value,
    with the degraded reason appended INLINE (not hidden in a tooltip) so it is
    loud without a click. Pure — exercised by the widget and directly testable.
    """
    loud = cell.verdict in (Verdict.RED, Verdict.AMBER)
    val_color = cell.color if loud else t.TEXT_SECONDARY
    body = "%s: %s" % (escape(cell.label), escape(cell.value))
    if loud and cell.reason:
        body += " — " + escape(_truncate(cell.reason, _REASON_INLINE_MAX))
    dot = '<span style="color:%s;">&#9679;</span>' % cell.color
    return '%s <span style="color:%s;">%s</span>' % (dot, val_color, body)


def cell_tooltip(cell: StripCell) -> str:
    """Full, untruncated detail for hover — the reason in full, or the value."""
    return cell.reason or "%s: %s" % (cell.label, cell.value)


# ======================================================================
# 6. Qt widget  (guarded — Qt only; standalone imports get a clear raise)
# ======================================================================

if _QT_AVAILABLE:

    class HealthStrip(QtWidgets.QWidget):
        """Slim always-visible health strip. Renders a list of ``StripCell`` and
        nothing else — it performs no I/O and holds no producers, so it can never
        become a main-thread stall. ``set_cells`` updates text in place (no
        rebuild), mirroring context_bar's refresh discipline."""

        def __init__(self, cells: List[StripCell], parent=None, on_click=None):
            super().__init__(parent)
            self.setObjectName("health_strip")
            # Landing r3 (RULING-1b / RULING-2B): the group role owns the strip's
            # rhythm (gap SPACE_GRID[3] = 16, margins 0 - today's values at
            # standard); the cell sheet moved to the designsystem sheet
            # (#health_strip QLabel) and the family travels by QFont.
            self.setProperty("rhythm_role", "group")
            self._on_click = on_click
            self._labels: dict = {}
            row = QtWidgets.QHBoxLayout(self)
            from synapse.panel.designsystem import fontload
            for cell in cells:
                lbl = QtWidgets.QLabel()
                lbl.setObjectName("hs_%s" % cell.key)
                lbl.setTextFormat(QtCore.Qt.TextFormat.RichText)
                lbl.setFont(fontload.apply_family(lbl.font(), mono=True))
                # Ignored horizontally: four rich-text cells at 101-165px with
                # a 16px gap never fit the 380 bound, and the full text already
                # lives in the tooltip (cell_tooltip). The strip elides; the
                # panel keeps its declared floor.
                lbl.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                                  QtWidgets.QSizePolicy.Preferred)
                self._labels[cell.key] = lbl
                row.addWidget(lbl)
            row.addStretch(1)
            self.set_cells(cells)
            if on_click is not None:
                self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        def set_cells(self, cells: List[StripCell]) -> None:
            for cell in cells:
                lbl = self._labels.get(cell.key)
                if lbl is None:
                    continue
                lbl.setText(cell_html(cell))
                lbl.setToolTip(cell_tooltip(cell))

        def mouseReleaseEvent(self, event):  # pragma: no cover - GUI-only
            if self._on_click is not None:
                try:
                    self._on_click()
                except Exception:
                    pass
            super().mouseReleaseEvent(event)

    def build_health_strip_widget(cells, parent=None, on_click=None):
        """Create the strip widget from cells."""
        return HealthStrip(cells, parent=parent, on_click=on_click)

    def update_health_strip_widget(widget, cells) -> None:
        """Refresh an existing strip in place. Accepts a HealthStrip (fast path)
        or any widget carrying the ``hs_<key>`` labels."""
        setter = getattr(widget, "set_cells", None)
        if callable(setter):
            setter(cells)
            return
        for cell in cells:
            lbl = widget.findChild(QtWidgets.QLabel, "hs_%s" % cell.key)
            if lbl is not None:
                lbl.setText(cell_html(cell))
                lbl.setToolTip(cell_tooltip(cell))

else:  # no Qt — pure-data core still imports; widgets raise honestly.

    def build_health_strip_widget(cells, parent=None, on_click=None):
        raise RuntimeError("Qt (PySide6/PySide2) is required for the health strip widget")

    def update_health_strip_widget(widget, cells) -> None:
        raise RuntimeError("Qt (PySide6/PySide2) is required for the health strip widget")
