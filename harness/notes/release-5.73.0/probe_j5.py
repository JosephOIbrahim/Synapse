"""J5 diagnostic probe — which widget ate the chat's 9px?

Read-only. Builds the composed panel exactly the way
tests/panel/test_j5_rail_air.py does, walks the visible widget tree, and
prints each widget's height + sizeHint + minimumSizeHint so the v5.72.0 and
HEAD layouts can be diffed directly.

    "<HFS>/bin/hython.exe" harness/notes/release-5.73.0/probe_j5.py
"""
import os
import sys
import tempfile
import types

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_hou = types.ModuleType("hou")
sys.modules.setdefault("hou", _hou)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")
if not os.environ.get("SYNAPSE_PANEL_SETTINGS"):
    os.environ["SYNAPSE_PANEL_SETTINGS"] = os.path.join(
        tempfile.mkdtemp(prefix="synapse_j5probe_"), "panel_settings.json")

from PySide6 import QtWidgets, QtCore   # noqa: E402

W, H = 340, 760

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from synapse.panel.designsystem import fontload      # noqa: E402
fontload.load_application_fonts()

from synapse.panel.synapse_panel import SynapsePanel  # noqa: E402

p = SynapsePanel()
p._recompose("expert")
p.resize(W, H)
p.show()
app.processEvents()
p._set_face("direct")
p._converse_stack.setCurrentIndex(0)
app.processEvents()

# the test's own pre-measure beat
p._input.set_user_height(p._input._floor)
app.processEvents()
p._faces.widget(0).layout().activate()
app.processEvents()


def dump(w, depth=0, out=None):
    out = out if out is not None else []
    vis = w.isVisible()
    try:
        sh = w.sizeHint().height()
    except Exception:
        sh = -1
    try:
        mh = w.minimumSizeHint().height()
    except Exception:
        mh = -1
    out.append("%s%-28s %-18s h=%-5d y=%-4d sh=%-5d mh=%-5d %s" % (
        "  " * depth,
        w.objectName() or "-",
        type(w).__name__,
        w.height(),
        w.mapTo(p, QtCore.QPoint(0, 0)).y(),
        sh, mh,
        "" if vis else "(hidden)",
    ))
    for c in w.children():
        if isinstance(c, QtWidgets.QWidget):
            dump(c, depth + 1, out)
    return out


lines = dump(p)
print("\n".join(lines))
chat = p._chat.height()
print("\nCHAT=%d  H=%d  share=%.6f  threshold=%.1f  short_by=%d" % (
    chat, H, chat / H, 0.5 * H, int(0.5 * H) - chat))
print("composer fixed height = %d  _floor=%d  _cap=%s  _user_h=%d" % (
    p._input.height(), p._input._floor, p._input._cap, p._input._user_h))
print("converse_stack=%d  faces=%d  faces_page0=%d" % (
    p._converse_stack.height(), p._faces.height(), p._faces.widget(0).height()))
