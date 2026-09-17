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
                    positive, PLUS (B6) that same store object's own write-health
                    contract (``is_degraded`` / ``degraded_reason``, falling back
                    to ``health()``) — because a backend identity cannot report a
                    backend failure, and for two days in 2026-09 it did not.
                    NEVER ``synapse_health.healthy`` — that field is a
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
                                  "moneta_live": <bool|None>,
                                  "write_health": <dict|None>}
                   ``write_health`` is ``{"sick": bool, "reason": str}`` when a
                   store could answer, and None when a store is live but none
                   could — which renders UNKNOWN, never OK. It is a SEPARATE
                   fact from ``backend``/``moneta_live``: those name which
                   backend is serving, this one says whether it still accepts
                   writes, and for two days in 2026-09 the first was green while
                   the second was false.
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

    A store that is refusing writes is the loudest thing this cell can say: RED,
    with a sentence an artist can act on. A recorded fallback (moneta → jsonl)
    is next, also RED, carrying the doctor's one-line reason — which holds the
    ``384 vs 256`` mismatch text when that is the cause. A live backend that
    ALSO confirmed it is accepting writes is OK. Everything we could NOT read —
    including "a store is live but could not report its write health" — is
    UNKNOWN, never a default green.

    B6 ORDERING, and why write-health goes first. On 2026-09-15 this cell
    returned OK for two days while the store refused every write, because
    ``moneta_live is True`` short-circuited to green before anything asked the
    store how it was doing. The write verdict is therefore evaluated BEFORE the
    identity positives, not after them: a backend being live is not evidence
    that it works, and the cell must not be able to reach a green return while
    holding a sick reading. It is also ranked above the fallback case, because
    "writes are being discarded right now" is more urgent and more actionable
    than "we are serving a different backend than you asked for".
    """
    if not isinstance(memory, dict):
        return StripCell("memory", "mem", Verdict.UNKNOWN, "unknown")

    # Measured and sick: the loudest state, and the one this lane exists for.
    write_health = memory.get("write_health")
    if isinstance(write_health, dict) and write_health.get("sick"):
        detail = str(write_health.get("reason") or "").strip()
        reason = (
            "memory is not accepting writes — anything you ask to be remembered "
            "is being discarded. Recover the store file, then reopen the scene."
        )
        if detail:
            reason += " (%s)" % detail
        return StripCell("memory", "mem", Verdict.RED, "not saving", reason=reason)

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
    backend = memory.get("backend")

    # A store is live, but nothing could tell us whether it is accepting writes
    # (no health contract on the object, or the reading was uninterpretable).
    # That is rule 1 of this module applied to the fact that actually matters:
    # a producer for "which backend" is NOT a producer for "does it work", so
    # the cell cannot go green on the identity alone. It renders grey and keeps
    # the backend name in the value, so the artist still sees WHAT is serving
    # alongside the honest admission that we cannot vouch for it.
    #
    # This is a reachable, clearable state, not a permanent amber: a MemoryStore
    # carrying Lane B3's contract answers, and a Moneta store answers through
    # its `_jsonl_net` safety net whenever dual-write is on (the default when
    # SYNAPSE_MEMORY_BACKEND == "moneta"). It fires for a store object that
    # predates the contract, a stub, or a backend that never grew one — exactly
    # the cases where reporting OK would be a lie.
    #
    # The test is "not a dict", not "is None": a write_health of some other
    # shape is a reading we cannot interpret, and an uninterpretable reading is
    # UNKNOWN. Letting it fall through to the OK returns below would rebuild the
    # exact collapse this lane removes.
    if (moneta_live is not None or backend) and not isinstance(write_health, dict):
        return StripCell(
            "memory", "mem", Verdict.UNKNOWN,
            str(backend) if backend else "unknown",
            reason="a memory store is live but could not report whether it is "
                   "accepting writes — treat saved memories as unconfirmed",
        )

    if moneta_live is True:
        return StripCell("memory", "mem", Verdict.OK, "moneta")
    if moneta_live is False:
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

# ── Store write-health (B6) ──────────────────────────────────────────────
#
# The 2026-09-15 incident in one line: a store sat DEGRADED and refused EVERY
# write for ~2 days, and THIS CELL stayed green the whole time, because
# ``cell_memory`` returned OK on ``moneta_live is True`` without ever asking the
# store whether it was working. "Moneta is the live class" and "memory is
# accepting writes" are different facts, and only the first was being read.
#
# Rule 1 of this module ("FACT-sourced or UNKNOWN") was never violated — the
# cell did have a producer. The bug is narrower and meaner: it had a producer
# for the WRONG FACT. A backend identity cannot report a backend failure.
#
# WHY THE PROPERTIES FIRST, AND ``health()`` ONLY AS FALLBACK
# -----------------------------------------------------------
# Lane B3's contract gives the store all three of ``is_degraded``,
# ``degraded_reason`` and ``health()``, and all three are cheap by design
# (``health()`` deliberately reads ``len(self._memories)`` WITHOUT the read
# lock, precisely so a health probe cannot queue behind a writer and freeze this
# panel). So this ordering is not a latency rescue — it is the smallest read
# that answers the question, on a surface whose stated contract is O(1)
# in-process reads on a 2 s tick that "must never become the next
# synapse_doctor 648 ms main-thread hold".
#
# The ``health()`` fallback is what makes the check portable: it catches any
# object that implements the dict form without the properties. Both report the
# same degradation, so preferring the cheaper one costs no fidelity. An object
# with NEITHER stays unanswered, which is UNKNOWN — never OK.
#
# Wrappers: the serving object is usually a facade. ``MonetaBackedStore``
# carries the JSONL dual-write safety net at ``_jsonl_net`` (the object that
# actually died in the incident) and ``ShadowMemoryStore`` carries ``primary`` /
# ``shadow``. We ask the facade and those members, one level deep over a fixed
# name list.
_WRITE_HEALTH_MEMBERS = ("_jsonl_net", "primary", "shadow")


def _read_write_health(live_store: Any) -> Any:
    """Ask the live store, and the stores it wraps, if writes are landing.

    Returns ``None`` when nothing could answer — a *measured* "we asked and got
    no answer", which ``cell_memory`` must render UNKNOWN rather than OK. That
    distinction is the whole fix: "we could not determine health" and "healthy"
    are different answers, and collapsing them is what produced the outage.

    Returns ``{"sick": bool, "reason": str}`` when something did answer. Never
    raises and never blocks: property reads first, ``health()`` only as the
    fallback for an object that lacks them.
    """
    candidates = [live_store]
    for member in _WRITE_HEALTH_MEMBERS:
        try:
            inner = getattr(live_store, member, None)
        except Exception:
            continue
        if inner is not None and not any(inner is c for c in candidates):
            candidates.append(inner)

    answered = False
    sick = False
    sick_reason = ""
    for obj in candidates:
        try:
            # health() IS THE CONTRACT, so it is asked FIRST -- not as a fallback.
            # An earlier version read the is_degraded property first and `continue`d
            # on it, which made the dict branch unreachable for every real
            # MemoryStore (it has the property). Signals that live only in the dict
            # -- writable, overwrote_prior -- could therefore never reach a verdict,
            # and a store that had overwritten stored data still rendered green.
            # A guard the real object cannot reach is not a guard.
            reading = None
            probe = getattr(obj, "health", None)
            if callable(probe):
                candidate = probe()
                if isinstance(candidate, dict):
                    reading = candidate

            if reading is not None:
                degraded = reading.get("degraded")
                writable = reading.get("writable")
                overwrote = reading.get("overwrote_prior") or 0
                if not isinstance(degraded, bool) or not isinstance(writable, bool):
                    continue  # a reading we cannot interpret is not an answer
                answered = True
                overwrote_n = overwrote if isinstance(overwrote, int) and overwrote > 0 else 0
                if degraded or not writable or overwrote_n:
                    # SICKNESS IS THE BOOLEAN, NEVER THE TEXT. An earlier version
                    # returned {"sick": bool(sick_reason)}, so a store reporting
                    # degraded with an EMPTY reason rendered green -- the cell
                    # inferring health from whether anyone had written a sentence
                    # about it. Also covers non-degraded-but-unwritable (a store
                    # still loading): not sick for the incident's reason, but
                    # definitively not green.
                    sick = True
                    if not sick_reason:
                        sick_reason = str(reading.get("reason") or "")
                    if not sick_reason and overwrote_n:
                        sick_reason = ("%d write(s) overwrote data already stored -- "
                                       "tags and scene context were replaced" % overwrote_n)
                continue

            # No health(): an older store, a stub or a different backend. The
            # property form is the fallback, and an object with neither stays
            # UNANSWERED -- which is UNKNOWN, never OK.
            degraded = getattr(obj, "is_degraded", None)
            if isinstance(degraded, bool):
                answered = True
                if degraded:
                    sick = True
                    if not sick_reason:
                        sick_reason = str(getattr(obj, "degraded_reason", "") or "")
        except Exception:
            continue  # one unreadable object never decides the cell

    if not answered:
        return None
    return {"sick": sick, "reason": sick_reason}


def _gather_memory() -> Any:
    """Read the memory-backend fact without constructing anything or blocking.

    ``backend_fallback()`` is a process-global read. The "is Moneta live"
    positive peeks the ``_global_synapse`` singleton directly — it does NOT call
    ``get_synapse_memory()``, which would build the store (the very act that can
    fall back / block). Returns UNMEASURED if the store module is not importable,
    which renders UNKNOWN rather than a fabricated green.

    B6: also reads ``write_health`` from that same already-resolved store object
    — whether it is still ACCEPTING writes, which the backend identity above
    cannot report. ``None`` means nothing could answer, and renders UNKNOWN.
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
    write_health: Any = None
    try:
        singleton = getattr(_store, "_global_synapse", None)
        if singleton is not None:
            live_store = getattr(singleton, "store", None)
            if live_store is not None:
                cls = type(live_store).__name__
                backend = cls
                moneta_live = (cls == "MonetaBackedStore")
                write_health = _read_write_health(live_store)
    except Exception:
        moneta_live = None
        backend = None
        write_health = None

    return {"fallback": fallback, "backend": backend, "moneta_live": moneta_live,
            "write_health": write_health}


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
