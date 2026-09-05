"""J2 - the TOKEN face counts (RULING_JOE_FIVE.md J2, 2026-09-05).

Real Qt only (hython 22.0.400 offscreen); skips under stock Python. The pure
half of J2 - parsers, sink, share arithmetic, list prices - is pinned in
tests/test_j2_token_wire.py; this file pins what lands on the face:

  1. an Ollama task the daemon reported (11 prompt / 4 completion, window
     4096 from /api/show) reads prompt 11 · completion 4 · total 15 ·
     context "11 / 4096 · 0.3%" and the session note says "$0 · local";
  2. a provider that reported nothing keeps prompt / completion UNKNOWN
     (R162, never a zero) and the note says so by name:
     "prompt/completion not reported by nemotron".

Every value cell stays a ``_kv_block`` DsParmValue in a parm_row (the camera
pins: tests/test_panel_camera_rhythm_qt.py width 64, census 0 spacing /
0 inline sheets / 0 hex in face_token.py).
"""
import os
import sys
import tempfile
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

sys.modules.setdefault("hou", types.ModuleType("hou"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")
if not os.environ.get("SYNAPSE_PANEL_SETTINGS"):
    os.environ["SYNAPSE_PANEL_SETTINGS"] = os.path.join(
        tempfile.mkdtemp(prefix="synapse_j2_"), "panel_settings.json")

try:
    from PySide6 import QtWidgets
    _HAVE_QT = True
except ImportError:
    try:
        from PySide2 import QtWidgets
        _HAVE_QT = True
    except ImportError:
        _HAVE_QT = False

if _HAVE_QT:
    try:
        _qapp = getattr(QtWidgets, "QApplication", None)
        if not (isinstance(_qapp, type) and "PySide" in getattr(_qapp, "__module__", "")):
            _HAVE_QT = False
    except Exception:
        _HAVE_QT = False

import pytest  # noqa: E402

if not _HAVE_QT:
    pytestmark = pytest.mark.skip(reason="PySide unavailable - run via hython")

_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def _sink():
    from synapse.panel.usage_sink import USAGE_SINK
    USAGE_SINK.clear()
    return USAGE_SINK


def _camera_rows(face):
    for key, value in face._rows.items():
        assert value.objectName() == "DsParmValue", key
        assert value.parentWidget().property("rhythm_role") == "parm_row", key


def test_face_counts_an_ollama_task():
    _app()
    from synapse.panel.face_token import FaceToken
    sink = _sink()
    try:
        sink.begin_task("nemotron-mini:latest", provider="ollama")
        sink.add({"input_tokens": 11, "output_tokens": 4})       # the daemon's receipt
        sink.set_context_window(4096, "ollama /api/show")        # nemotron.context_length
        face = FaceToken()
        face.refresh_from_probe()
        rows = {k: v.text() for k, v in face._rows.items()}
        assert rows["prompt"] == "11"
        assert rows["completion"] == "4"
        assert rows["total"] == "15"
        assert rows["context"] == "11 / 4096 · 0.3%"
        assert rows["session prompt"] == "11"
        assert rows["session completion"] == "4"
        assert rows["session total"] == "15"
        assert rows["turns"] == "1"
        assert rows["session cost"] == "$0"
        assert "$0 · local" in face._session_note.text()
        assert not face._session_note.isHidden()
        assert "not reported" not in face._spend_note.text()
        assert "ollama /api/show" in face._spend_note.text()
        assert rows["model"] == "nemotron-mini:latest"
        _camera_rows(face)
    finally:
        sink.clear()


def test_face_says_not_reported_for_a_silent_provider():
    _app()
    from synapse.panel.face_token import FaceToken, UNKNOWN
    sink = _sink()
    try:
        sink.begin_task("nvidia/nemotron-3-super-120b-a12b", provider="nemotron")
        sink.add(None)                                            # the stream carried no usage
        face = FaceToken()
        face.refresh_from_probe()
        rows = {k: v.text() for k, v in face._rows.items()}
        assert rows["prompt"] == UNKNOWN
        assert rows["completion"] == UNKNOWN
        assert rows["total"] == UNKNOWN
        assert rows["context"] == UNKNOWN
        assert rows["session cost"] == UNKNOWN
        assert "prompt/completion not reported by nemotron" in face._spend_note.text()
        assert "context window not reported by nemotron" in face._spend_note.text()
        assert "price unknown for nvidia/nemotron-3-super-120b-a12b" in face._session_note.text()
        # the existing cache rows keep their own UNKNOWN (test_token_tab_usage.py)
        assert rows["prefix"] == UNKNOWN and rows["last turn"] == UNKNOWN
        _camera_rows(face)
    finally:
        sink.clear()
