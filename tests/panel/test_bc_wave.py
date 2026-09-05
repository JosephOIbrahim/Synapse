"""design/bc-wave — direction B + C pins (Joe's ruling 2026-09-05).

One file, one test per spec item, each committed RED before its fix:

  BC-1  the verb rail retires; EXPLAIN / FIX / OPTIMIZE live in the slash
        palette, BUILD HDA in the overflow; the CHAT face is transcript ->
        composer with nothing clipped at 340.
  BC-2  the rail says one truth: a state sentence that never elides.
  BC-3  slash-palette rows breathe on the grid.
  BC-4  one signal per fact at boot; beats on the grid.
  BC-5  the profile row folds into the overflow; the conversation takes >= 50%.
  BC-6a consent card in the panel's own vocabulary; turn receipt offers revert.
  BC-6b consent surfaces inline on CHAT (gated on the human G3 edit).

Real Qt only (hython 22.0.400 offscreen); skips under stock Python. Builds
against a scratch settings file so the artist's real picks are never read
or written (settings.py honours SYNAPSE_PANEL_SETTINGS).
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

_hou = types.ModuleType("hou")
sys.modules.setdefault("hou", _hou)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")
if not os.environ.get("SYNAPSE_PANEL_SETTINGS"):
    os.environ["SYNAPSE_PANEL_SETTINGS"] = os.path.join(
        tempfile.mkdtemp(prefix="synapse_bc_"), "panel_settings.json")

try:
    from PySide6 import QtWidgets, QtGui, QtCore
    _HAVE_QT = True
except ImportError:
    try:
        from PySide2 import QtWidgets, QtGui, QtCore
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

import pytest

if not _HAVE_QT:
    pytestmark = pytest.mark.skip(reason="PySide unavailable - run via hython")

PROFILES = ("curious", "expert", "ml")
DENSITY = {"curious": "airy", "expert": "standard", "ml": "tight"}
W, H = 340, 760

_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        from synapse.panel.designsystem import fontload
        fontload.load_application_fonts()
    return _APP


def _panel(profile="expert"):
    """A composed panel at the docking pref width, driven to the CHAT face."""
    _app()
    from synapse.panel.synapse_panel import SynapsePanel
    p = SynapsePanel()
    p._recompose(profile)
    p.resize(W, H)
    p.show()
    _app().processEvents()
    p._set_face("direct")
    p._converse_stack.setCurrentIndex(0)
    _app().processEvents()
    return p


def _chat_face(panel):
    return panel._faces.widget(0)


def _visible_buttons(root):
    return [b for b in root.findChildren(QtWidgets.QAbstractButton) if b.isVisible()]


# --------------------------------------------------------------------- BC-1
def test_verb_rail_retired_and_verbs_reachable():
    from synapse.panel.synapse_panel import SynapsePanel, _QUICK_ACTIONS
    from synapse.panel.tool_palette import ToolPalette
    assert not hasattr(SynapsePanel, "_build_act"), "the verb rail builder must be gone"
    for profile in PROFILES:
        p = _panel(profile)
        try:
            assert not hasattr(p, "_font_btn"), "Aa duplicated the overflow's text-size entries"
            # The three quick actions are palette rows: title = label, send = prompt.
            pal = ToolPalette(p, scale=p._chrome_scale)
            sends = {pal._list.item(i).data(QtCore.Qt.ItemDataRole.UserRole)
                     for i in range(pal._list.count())}
            for _label, prompt in _QUICK_ACTIONS:
                assert prompt in sends, prompt
            pal.close()
            # BUILD HDA is an overflow action.
            menu = p._build_overflow_menu()
            texts = [a.text() for a in menu.actions()]
            assert any(t.startswith("Build HDA") for t in texts), texts
            # The CHAT face is [converse stack] ... [composer]; no act band, no divider.
            face = _chat_face(p)
            lay = face.layout()
            assert lay.itemAt(0).widget() is p._converse_stack
            assert lay.itemAt(lay.count() - 1).widget() is p._input.parentWidget()
            assert not face.findChildren(QtWidgets.QWidget, "DsDivider")
            # Nothing clipped at 340 (F1): every visible button holds its hint.
            clipped = [(b.objectName(), b.text(), b.width(), b.sizeHint().width())
                       for b in _visible_buttons(face) if b.width() < b.sizeHint().width()]
            assert not clipped, (profile, clipped)
        finally:
            p.close()
