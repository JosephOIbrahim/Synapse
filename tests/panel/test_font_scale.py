"""Host-matched font scale + the "/" command affordance + tracked_font mono —
the Qt-dependent panel behaviors added in the redesign. Skips cleanly when real
PySide is unavailable (stock-Python CI); runs for real under hython.
"""
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# a minimal hou stub so the panel constructs headless-offscreen
_hou = types.ModuleType("hou")
sys.modules.setdefault("hou", _hou)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtWidgets, QtGui, QtCore
    _HAVE_QT = True
except ImportError:
    try:
        from PySide2 import QtWidgets, QtGui, QtCore
        _HAVE_QT = True
    except ImportError:
        _HAVE_QT = False

# Real Qt only — a sibling test's PySide stub (MagicMock / ModuleType) would
# otherwise flip _HAVE_QT True and fail on fake widgets (see test_panel_faces).
if _HAVE_QT:
    try:
        _qapp = getattr(QtWidgets, "QApplication", None)
        if not (isinstance(_qapp, type) and "PySide" in getattr(_qapp, "__module__", "")):
            _HAVE_QT = False
    except Exception:
        _HAVE_QT = False

import pytest

if not _HAVE_QT:
    pytestmark = pytest.mark.skip(reason="PySide unavailable — run via hython")

_APP = None
from synapse.panel.designsystem import tokens as t


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def _panel():
    _app()
    from synapse.panel.synapse_panel import SynapsePanel
    return SynapsePanel()


def test_host_scale_tracks_large_host_font():
    app = _app()
    saved = app.font()
    big = QtGui.QFont(saved)
    big.setPixelSize(20)
    app.setFont(big)
    try:
        p = _panel()
        assert abs(p._host_font_scale() - 20 / float(t.SIZE_BODY)) < 0.05
    finally:
        app.setFont(saved)


def test_host_scale_floored_for_small_host_font():
    app = _app()
    saved = app.font()
    small = QtGui.QFont(saved)
    small.setPixelSize(10)
    app.setFont(small)
    try:
        p = _panel()
        # a small host font must NOT shrink the panel below the readability floor
        assert p._host_font_scale() == t.FONT_SCALE_DEFAULT
    finally:
        app.setFont(saved)


def test_slash_on_empty_opens_palette_and_is_not_typed():
    p = _panel()
    fired = []
    p._input.slash.connect(lambda: fired.append(1))
    ev = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Slash,
                         QtCore.Qt.NoModifier, "/")
    p._input.keyPressEvent(ev)
    assert fired == [1]                 # palette opened
    assert p._input.toPlainText() == ""  # "/" was swallowed, not inserted


def test_slash_does_not_fire_when_input_nonempty():
    p = _panel()
    p._input.setPlainText("hello")
    fired = []
    p._input.slash.connect(lambda: fired.append(1))
    ev = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Slash,
                         QtCore.Qt.NoModifier, "/")
    p._input.keyPressEvent(ev)
    assert fired == []                  # mid-text "/" is a literal, not a trigger


def test_aa_cycle_steps_above_a_host_base_scale():
    # a host-derived base (not on the ladder) must step UP, never reset smaller
    p = _panel()
    p._font_scale = 1.33                # simulate a large-host base, off-ladder
    p._cycle_font_scale()
    assert p._font_scale > 1.33
    assert p._font_scale in t.FONT_SCALE_STEPS


def test_tracked_font_mono_branch_builds():
    _app()
    from synapse.panel.designsystem import fontload
    f = fontload.tracked_font("DATA", 12, mono=True)
    assert f.pixelSize() == 12          # built without error; mono family resolved
