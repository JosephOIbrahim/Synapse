"""J5 fit probe — which footer gap holds, at each real "Updates (n)" label.

Read-only. Builds the panel with the REAL code, then sets the footer layout's
own `_horizontal_gap` and the Updates link's text AFTER construction, so
nothing outside the footer is perturbed (patching `tokens.SPACE_12` would move
the wordmark rail and every other SPACE_12 read in the panel).

    "<HFS>/bin/hython.exe" harness/notes/release-5.73.0/probe_j5_fit.py
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
        tempfile.mkdtemp(prefix="synapse_j5fit_"), "panel_settings.json")

from PySide6 import QtWidgets, QtCore   # noqa: E402

W, H = 340, 760

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from synapse.panel.designsystem import fontload      # noqa: E402
fontload.load_application_fonts()
import synapse.panel.synapse_panel as sp             # noqa: E402


def measure(gap, updates_text):
    p = sp.SynapsePanel()
    p._recompose("expert")
    p.resize(W, H)
    p.show()
    app.processEvents()
    p._set_face("direct")
    p._converse_stack.setCurrentIndex(0)
    app.processEvents()

    btns = (p._commands_btn, p._render_btn, p._recipes_btn, p._events_btn)
    p._events_btn.setText(updates_text)
    lay = btns[0].parentWidget().layout()
    lay._horizontal_gap = gap
    lay.invalidate()
    p._input.set_user_height(p._input._floor)
    app.processEvents()
    p._faces.widget(0).layout().activate()
    app.processEvents()

    host = btns[0].parentWidget().width()
    need = sum(b.sizeHint().width() for b in btns) + gap * 3
    rows = len({b.mapTo(p, QtCore.QPoint(0, 0)).y() for b in btns})
    out = {"gap": gap, "label": updates_text, "host": host, "need": need,
           "rows": rows, "chat": p._chat.height(), "share": p._chat.height() / H}
    p.deleteLater()
    app.processEvents()
    return out


print("panel %dx%d  host must hold the strip in ONE row for share >= 0.5" % (W, H))
print("design ladder: 4 . 8 . 12 . 16 . 24 . 32 . 48   (role gaps: 0/4/12/16)")
print()
print("%-5s %-16s %-6s %-6s %-6s %-6s %-6s %s" % (
    "gap", "Updates link", "host", "need", "rows", "chat", "share", "verdict"))
for gap in (12, 8, 4):
    for label in ("Updates", "Updates (1)", "Updates (12)", "Updates (999)"):
        r = measure(gap, label)
        print("%-5d %-16s %-6d %-6d %-6d %-6d %-6.4f %s" % (
            r["gap"], r["label"], r["host"], r["need"], r["rows"],
            r["chat"], r["share"],
            "PASS (%d spare)" % (r["host"] - r["need"]) if r["rows"] == 1
            else "FAIL by %d" % (r["need"] - r["host"])))
