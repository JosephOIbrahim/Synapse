"""Health-strip pins — pure / stdlib (no Qt, no hou), so they run under stock
``pytest -q`` AND hython. These are the FACT-sourcing + honesty guarantees the
P0.3 leg exists to hold:

  1. the strip renders connection / memory / project / job cells from live facts
  2. a moneta->jsonl fallback is LOUD (amber/red) and carries the doctor's
     one-line reason — the 384-vs-256 case displays, it does not hide
  3. any unmeasured / unreachable fact renders UNKNOWN — never green, never 0

An optional Qt-widget pin at the end builds the strip offscreen; it SKIPS when
PySide is absent (stock dev interpreter) and gives real signal under hython3.13.
"""

import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from synapse.panel import health_strip as hs  # noqa: E402
from synapse.panel.designsystem import tokens as t  # noqa: E402


# A producer-shaped fallback record, exactly as store._record_backend_fallback
# builds it (keys: requested / served / storage_dir / reason / at). The reason
# is the generic "init failed" string that the 384-vs-256 ValueError degrades to
# in store._make_store — this is precisely the report's observed case.
_FALLBACK_384_256 = {
    "requested": "moneta",
    "served": "jsonl",
    "storage_dir": "C:/Users/x/AppData/Local/Temp/synapse_mem",
    "reason": "init failed: ValueError: embedding dim mismatch: expected 384, got 256",
    "at": "2026-08-13 09:00:00",
}


# ── Predicate 1: four FACT-sourced cells ──────────────────────────────────

def test_build_cells_returns_four_keyed_cells():
    cells = hs.build_cells(hs.StripSnapshot())
    assert [c.key for c in cells] == ["connection", "memory", "project", "job"]


def test_cells_reflect_supplied_live_facts():
    snap = hs.StripSnapshot(
        connection="ok",
        memory={"fallback": None, "backend": "MonetaBackedStore", "moneta_live": True},
        project="shot_010_lighting.hip",
        active_job={"label": "karma_beauty"},
    )
    by_key = {c.key: c for c in hs.build_cells(snap)}
    assert by_key["connection"].verdict == hs.Verdict.OK
    assert by_key["connection"].value == "Houdini"
    assert by_key["memory"].verdict == hs.Verdict.OK
    assert by_key["memory"].value == "moneta"
    assert by_key["project"].verdict == hs.Verdict.OK
    assert by_key["project"].value == "shot_010_lighting.hip"
    assert by_key["job"].verdict == hs.Verdict.WORKING
    assert "karma_beauty" in by_key["job"].value


def test_measured_quiet_is_idle_not_unknown_and_not_green():
    # A saved-but-untitled scene with no render is MEASURED quiet: IDLE, which is
    # neither UNKNOWN (we did look) nor OK-green (nothing to assert healthy).
    snap = hs.StripSnapshot(connection="ok", project=None, active_job=None)
    by_key = {c.key: c for c in hs.build_cells(snap)}
    assert by_key["project"].verdict == hs.Verdict.IDLE
    assert by_key["job"].verdict == hs.Verdict.IDLE
    for k in ("project", "job"):
        assert by_key[k].color != t.GROW  # not green
        assert by_key[k].color != t.SLATE  # not the UNKNOWN grey either


# ── Predicate 2: fallback is loud, with the reason, and the 384/256 shows ──

def test_memory_fallback_renders_red_with_reason():
    cell = hs.cell_memory({"fallback": _FALLBACK_384_256, "backend": "JsonlStore",
                           "moneta_live": False})
    assert cell.verdict == hs.Verdict.RED
    assert cell.color == t.ERROR          # loud, not green
    assert cell.color != t.GROW
    assert "jsonl" in cell.value.lower()  # shows what is actually serving
    # the doctor's one-line reason is carried, and the 384/256 case is in it
    assert cell.reason
    assert "384" in cell.reason and "256" in cell.reason


def test_fallback_reason_is_inline_not_hidden():
    # "degraded is loud ... no click required to notice": the reason must be in
    # the rendered markup itself, not only the tooltip.
    cell = hs.cell_memory({"fallback": _FALLBACK_384_256})
    markup = hs.cell_html(cell)
    assert "384" in markup and "256" in markup
    assert t.ERROR in markup  # the red dot/value colour is present


def test_amber_or_red_fallback_never_green():
    for served in ("jsonl",):
        cell = hs.cell_memory({"fallback": {"requested": "moneta", "served": served,
                                            "reason": "init failed: X"}})
        assert cell.verdict in (hs.Verdict.AMBER, hs.Verdict.RED)
        assert cell.color != t.GROW


# ── Predicate 3: unmeasured/unreachable → UNKNOWN, never green, never 0 ────

def test_unmeasured_snapshot_is_all_unknown_and_grey():
    cells = hs.build_cells(hs.StripSnapshot())  # every field defaults UNMEASURED
    for c in cells:
        assert c.verdict == hs.Verdict.UNKNOWN, c.key
        assert c.color == hs.verdict_color(hs.Verdict.UNKNOWN) == t.SLATE
        assert c.color != t.GROW           # never green
        assert c.value not in ("0", "ok", "0 issues", "0 jobs", "")  # never a fake 0


def test_no_cell_is_green_without_a_producing_fact():
    # The whole leg's contract: OK/GROW only from a real producer reading.
    cells = hs.build_cells(hs.StripSnapshot())
    assert not [c for c in cells if c.color == t.GROW]


def test_memory_absence_of_fallback_is_not_health():
    # No fallback recorded is NOT proof moneta is serving. Without a confirmed
    # live store, the cell is UNKNOWN — not a default green.
    cell = hs.cell_memory({"fallback": None, "backend": None, "moneta_live": None})
    assert cell.verdict == hs.Verdict.UNKNOWN
    assert cell.color != t.GROW


def test_connection_unmeasured_is_unknown_not_connected():
    assert hs.cell_connection(hs.UNMEASURED).verdict == hs.Verdict.UNKNOWN
    assert hs.cell_connection(None).verdict == hs.Verdict.UNKNOWN
    assert hs.cell_connection("ok").verdict == hs.Verdict.OK  # only a fact → green


def test_gate_stale_connection_is_amber():
    cell = hs.cell_connection("warning")
    assert cell.verdict == hs.Verdict.AMBER
    assert cell.color == t.WARN


# ── gather_snapshot is total + non-blocking (never raises) ────────────────

def test_gather_snapshot_never_raises_and_is_total():
    snap = hs.gather_snapshot()
    assert isinstance(snap, hs.StripSnapshot)
    # memory/active_job come back as UNMEASURED, None, or a dict — always a
    # shape build_cells can render, and build_cells never raises.
    cells = hs.build_cells(snap)
    assert len(cells) == 4


def test_gather_respects_passed_connection_and_project():
    snap = hs.gather_snapshot(connection="ok", project="my_show.hip")
    assert snap.connection == "ok"
    assert snap.project == "my_show.hip"


# ── Optional Qt-widget pin (offscreen; skips without PySide) ──────────────

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HAVE_QT = False
try:
    from PySide6 import QtWidgets as _QtW
    _HAVE_QT = True
except ImportError:
    try:
        from PySide2 import QtWidgets as _QtW
        _HAVE_QT = True
    except ImportError:
        _HAVE_QT = False
if _HAVE_QT:
    _qapp = getattr(_QtW, "QApplication", None)
    if not (isinstance(_qapp, type) and "PySide" in getattr(_qapp, "__module__", "")):
        _HAVE_QT = False

_APP = None


@pytest.mark.skipif(not _HAVE_QT, reason="PySide unavailable — run via hython3.13")
def test_widget_builds_offscreen_and_shows_visible_cells():
    global _APP
    if _APP is None:
        _APP = _QtW.QApplication.instance() or _QtW.QApplication([])
    snap = hs.StripSnapshot(
        connection="ok",
        memory={"fallback": _FALLBACK_384_256},
        project="shot_010.hip",
        active_job=None,
    )
    widget = hs.build_health_strip_widget(hs.build_cells(snap))
    widget.show()
    labels = [w for w in widget.findChildren(_QtW.QLabel) if w.isVisible()]
    assert len(labels) == 4
    # the degraded memory cell shows its reason inline (loud, no click)
    mem = widget.findChild(_QtW.QLabel, "hs_memory")
    assert mem is not None
    assert "384" in mem.text() and "256" in mem.text()


@pytest.mark.skipif(not _HAVE_QT, reason="PySide unavailable — run via hython3.13")
def test_widget_update_in_place_flips_verdict():
    global _APP
    if _APP is None:
        _APP = _QtW.QApplication.instance() or _QtW.QApplication([])
    widget = hs.build_health_strip_widget(hs.build_cells(hs.StripSnapshot()))
    # start UNKNOWN, then a fallback arrives → the memory cell must go loud
    hs.update_health_strip_widget(
        widget, hs.build_cells(hs.StripSnapshot(memory={"fallback": _FALLBACK_384_256})))
    mem = widget.findChild(_QtW.QLabel, "hs_memory")
    assert t.ERROR in mem.text()
