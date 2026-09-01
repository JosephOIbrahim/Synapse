"""BP2-PANELTRUTH T2 — TOKEN refresh on task completion, from the real receipt.

Layers, most of them pure (they run in the stock-CPython suite):

  1. token_readout (PURE): the display rule that turns a usage_sink snapshot into
     the rail meter + pill text, with the R162 honesty rules — UNKNOWN => empty
     meter + base pill (never a fake zero, never a fuel-gauge bar/ratio).
  2. refresh_surfaces (duck-typed): feeds face + meter + pill; a fed sink changes
     the meter and pill text and refreshes the face; an unfed sink leaves them at
     UNKNOWN.
  3. completion wiring (stub-Qt): the REAL SynapsePanel._on_done -> the REAL
     _refresh_token_surfaces fires the refresh on task completion — driven on a
     fake self (the tests/test_panel_stop_honest.py idiom, under qt_stub_window).
  4. source pins: _on_done calls it, it rides token_readout, and it is NEVER on a
     timer (V3 rule) — the wire cannot regress into a poll.
  5. Qt-gated end-to-end (hython): a real FaceToken + real Pill actually change
     text on a fed completion, and read UNKNOWN unfed. Skips in stock CPython.

The "emit completion -> face and pill text changed" acceptance runs headless via
layers 2+3; layer 5 is the live-seat confirmation (skip != pass).
"""

import os
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qt_stub_window import qt_stub_window  # noqa: E402

with qt_stub_window():
    from synapse.panel.synapse_panel import SynapsePanel  # noqa: E402

from synapse.panel import token_readout  # noqa: E402
from synapse.panel.usage_sink import USAGE_SINK, UsageSink  # noqa: E402

_PANEL_SRC = (Path(__file__).resolve().parents[1]
              / "python" / "synapse" / "panel" / "synapse_panel.py")


def _snap(**over):
    s = {"input_tokens": 100, "output_tokens": 20,
         "cache_read": 30, "cache_creation": 5, "model": "claude-x", "runs": 1}
    s.update(over)
    return s


# --------------------------------------------------------------------------- #
# 1. token_readout pure rules
# --------------------------------------------------------------------------- #

def test_task_total_sums_reported_fields():
    assert token_readout.task_total(_snap()) == 155        # 100+20+30+5


def test_task_total_none_when_nothing_measured():
    assert token_readout.task_total(None) is None
    # begun task, no add: all spend fields None -> UNKNOWN, never 0
    assert token_readout.task_total(
        {"input_tokens": None, "output_tokens": None,
         "cache_read": None, "cache_creation": None, "model": "m"}) is None


def test_task_total_bool_is_never_a_count():
    assert token_readout.task_total(
        {"input_tokens": True, "output_tokens": False, "cache_read": 12}) == 12


def test_task_total_keeps_a_real_reported_zero():
    assert token_readout.task_total({"cache_read": 0}) == 0


def test_meter_text_unknown_is_empty_never_zero_never_a_bar():
    assert token_readout.meter_text(None) == ""
    assert "/" not in token_readout.meter_text(_snap())     # a count, not a ratio
    assert token_readout.meter_text(_snap()) == "155"


def test_pill_text_base_when_unknown_else_carries_the_figure():
    assert token_readout.pill_text(None) == "TOKEN"
    assert token_readout.pill_text(_snap()).startswith("TOKEN")
    assert "155" in token_readout.pill_text(_snap())


# --------------------------------------------------------------------------- #
# 2. refresh_surfaces on duck-typed leaves
# --------------------------------------------------------------------------- #

class _Rec:
    def __init__(self, text=""):
        self._t = text

    def text(self):
        return self._t

    def setText(self, t):
        self._t = t


class _FaceRec:
    def __init__(self):
        self.refreshed = 0

    def refresh_from_probe(self):
        self.refreshed += 1


def test_refresh_surfaces_fed_changes_meter_pill_and_refreshes_face():
    face, meter, pill = _FaceRec(), _Rec(""), _Rec("TOKEN")
    total = token_readout.refresh_surfaces(
        face=face, meter=meter, pill=pill, snap=_snap())
    assert total == 155
    assert face.refreshed == 1
    assert meter.text() == "155"            # meter text changed
    assert pill.text() != "TOKEN"           # pill text changed
    assert "155" in pill.text()


def test_refresh_surfaces_unfed_is_unknown_no_bar():
    face, meter, pill = _FaceRec(), _Rec("stale"), _Rec("TOKEN")
    token_readout.refresh_surfaces(face=face, meter=meter, pill=pill, snap=None)
    assert meter.text() == ""               # UNKNOWN -> empty, never 0
    assert pill.text() == "TOKEN"           # base label, no fabricated figure
    assert "/" not in meter.text()          # no quota bar/ratio (V3-F4)
    assert face.refreshed == 1              # face still refreshed -> shows its UNKNOWN


def test_refresh_surfaces_is_all_best_effort():
    # A missing surface (None) and a raising one must never propagate.
    class _Boom:
        def setText(self, t):
            raise RuntimeError("boom")
    token_readout.refresh_surfaces(face=None, meter=_Boom(), pill=None, snap=_snap())


# --------------------------------------------------------------------------- #
# 3. completion wiring: real _on_done -> real _refresh_token_surfaces
# --------------------------------------------------------------------------- #

def _completion_self():
    """A fake panel self carrying only what _on_done + _refresh_token_surfaces
    touch, with the two REAL methods bound to it."""
    s = types.SimpleNamespace()
    s._stream_buf = []
    s._streaming_started = False
    s._worker = None
    s._messages = []
    s._author_token = lambda: ""
    s._set_thinking = lambda *a, **k: None
    s._set_busy = lambda *a, **k: None
    s._chat = types.SimpleNamespace(
        end_stream=lambda *a, **k: None,
        append_synapse_message=lambda *a, **k: None)
    s._token_face = _FaceRec()
    s._meter_lbl = _Rec("")
    s._face_pills = {"token": _Rec("TOKEN")}
    s._refresh_token_surfaces = SynapsePanel._refresh_token_surfaces.__get__(s)
    s._on_done = SynapsePanel._on_done.__get__(s)
    return s


def test_on_done_refreshes_token_surfaces_from_the_sink():
    USAGE_SINK.clear()
    USAGE_SINK.begin_task("claude-complete")
    USAGE_SINK.add({"input_tokens": 100, "output_tokens": 20,
                    "cache_read_input_tokens": 30,
                    "cache_creation_input_tokens": 5})
    s = _completion_self()
    try:
        s._on_done()                                   # emit completion
        assert s._token_face.refreshed == 1            # face refreshed on completion
        assert s._meter_lbl.text() == "155"            # rail meter changed
        assert s._face_pills["token"].text() != "TOKEN"
        assert "155" in s._face_pills["token"].text()  # pill changed
    finally:
        USAGE_SINK.clear()


def test_on_done_unfed_sink_leaves_surfaces_unknown():
    USAGE_SINK.clear()                                 # no task ran
    s = _completion_self()
    s._on_done()
    assert s._meter_lbl.text() == ""                   # UNKNOWN, no fake zero
    assert s._face_pills["token"].text() == "TOKEN"    # base label, no bar
    assert s._token_face.refreshed == 1


# --------------------------------------------------------------------------- #
# 4. source pins — the wire is on completion, NEVER a timer (V3), and rides
#    token_readout. claude_worker gains no hou.* (crucible).
# --------------------------------------------------------------------------- #

def test_on_done_invokes_the_refresh():
    src = _PANEL_SRC.read_text(encoding="utf-8")
    done = src[src.index("def _on_done"):src.index("def _refresh_token_surfaces")]
    assert "self._refresh_token_surfaces()" in done, (
        "_on_done must fire the token refresh on completion")


def test_refresh_rides_token_readout_and_is_not_timer_driven():
    src = _PANEL_SRC.read_text(encoding="utf-8")
    body = src[src.index("def _refresh_token_surfaces"):src.index("def _on_error")]
    assert "token_readout" in body and "refresh_surfaces" in body
    # V3 rule: the refresh must never be wired to a timer's timeout.
    assert "timeout.connect(self._refresh_token_surfaces" not in src
    assert "QTimer" not in body


def test_claude_worker_stays_houdini_free():
    worker = (_PANEL_SRC.parent / "claude_worker.py").read_text(encoding="utf-8")
    # crucible: T2 introduces no `hou.` into the worker. The worker's load-bearing
    # invariant (its own module docstring: "No hou.* imports") is that it never
    # imports hou and uses no hou.* in code — the only "hou." occurrences are in
    # comments/docstrings. Pin the true invariant, not the prose.
    import re
    assert "import hou" not in worker
    code = "\n".join(
        ln for ln in worker.splitlines() if not ln.lstrip().startswith("#"))
    # strip triple-quoted blocks (docstrings) before scanning for real code use
    code = re.sub(r'""".*?"""', "", code, flags=re.S)
    assert not re.search(r"\bhou\.\w", code), "worker must use no hou.* in code"


# --------------------------------------------------------------------------- #
# 5. Qt-gated end-to-end — real FaceToken + real Pill (runs under hython)
# --------------------------------------------------------------------------- #

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("hou", types.ModuleType("hou"))

try:
    from PySide6 import QtWidgets  # noqa: F401
    _HAVE_QT = isinstance(getattr(QtWidgets, "QApplication", None), type) and \
        "PySide" in getattr(QtWidgets.QApplication, "__module__", "")
except Exception:
    _HAVE_QT = False

_qt = pytest.mark.skipif(not _HAVE_QT, reason="PySide unavailable — run via hython")
_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


@_qt
def test_real_face_and_pill_change_on_fed_completion():
    _app()
    from synapse.panel.face_token import FaceToken
    from synapse.panel.designsystem import components as c
    USAGE_SINK.clear()
    USAGE_SINK.begin_task("claude-real")
    USAGE_SINK.add({"input_tokens": 100, "output_tokens": 20,
                    "cache_read_input_tokens": 30,
                    "cache_creation_input_tokens": 5})
    face = FaceToken()
    pill = c.Pill("TOKEN")
    meter = c.label("", role="caption")
    before_prefix = face._rows["prefix"].text()
    before_pill = pill.text()
    token_readout.refresh_surfaces(face=face, meter=meter, pill=pill,
                                   snap=USAGE_SINK.snapshot())
    assert face._rows["prefix"].text() != before_prefix   # real cache_read receipt
    assert pill.text() != before_pill and "155" in pill.text()
    assert "/" not in meter.text()                        # no quota bar
    USAGE_SINK.clear()


@_qt
def test_real_surfaces_unknown_when_no_task():
    _app()
    from synapse.panel.face_token import FaceToken, UNKNOWN
    from synapse.panel.designsystem import components as c
    USAGE_SINK.clear()
    face = FaceToken()
    pill = c.Pill("TOKEN")
    meter = c.label("", role="caption")
    token_readout.refresh_surfaces(face=face, meter=meter, pill=pill, snap=None)
    assert face._rows["prefix"].text() == UNKNOWN
    assert pill.text() == "TOKEN"
    assert meter.text() == ""
