"""J5 gap probe — the MEASURED share for each candidate footer gap.

Read-only. `_build_shortcut_footer` reads `t.SPACE_LG` at build time and it is
the ONLY `SPACE_LG` consumer in synapse_panel.py, so patching the module global
before constructing the panel changes exactly the footer gap and nothing else.

For each candidate it rebuilds the panel exactly the way
tests/panel/test_j5_rail_air.py does and reports the real chat share.

    "<HFS>/bin/hython.exe" harness/notes/release-5.73.0/probe_j5_gap.py
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
        tempfile.mkdtemp(prefix="synapse_j5gap_"), "panel_settings.json")

from PySide6 import QtWidgets, QtCore   # noqa: E402

W, H = 340, 760

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from synapse.panel.designsystem import fontload              # noqa: E402
fontload.load_application_fonts()
from synapse.panel.designsystem import tokens as t           # noqa: E402
import synapse.panel.synapse_panel as sp                     # noqa: E402


def measure(gap):
    """Build a panel with the footer's inter-link gap forced to `gap`."""
    orig = t.SPACE_LG
    t.SPACE_LG = gap
    try:
        p = sp.SynapsePanel()
        p._recompose("expert")
        p.resize(W, H)
        p.show()
        app.processEvents()
        p._set_face("direct")
        p._converse_stack.setCurrentIndex(0)
        app.processEvents()

        # the test's own pre-measure beat, verbatim
        p._input.set_user_height(p._input._floor)
        app.processEvents()
        p._faces.widget(0).layout().activate()
        app.processEvents()

        btns = (p._commands_btn, p._render_btn,
                p._recipes_btn, p._events_btn)
        rows = sorted({b.mapTo(p, QtCore.QPoint(0, 0)).y() for b in btns})
        section = btns[0].parentWidget().parentWidget()
        rail = p._region_cache["_build_rail"]
        ribbon = p._region_cache["_build_context_ribbon"]
        return {
            "chat": p._chat.height(),
            "share": p._chat.height() / H,
            "rows": len(rows),
            "composer": p._input.height(),
            "section": section.height(),
            "rail": rail.height(),
            "ribbon": ribbon.height(),
            "need": sum(b.sizeHint().width() for b in btns) + gap * 3,
        }
    finally:
        t.SPACE_LG = orig
        p.deleteLater()
        app.processEvents()


GAPS = [(24, "SPACE_LG (current)"), (16, "SPACE_MD"),
        (12, "SPACE_GRID[2]"), (8, "SPACE_SM")]
if len(sys.argv) > 1:                       # one gap per process = no cross-talk
    want = {int(a) for a in sys.argv[1:]}
    GAPS = [g for g in GAPS if g[0] in want]

print("panel %dx%d   chat must be >= %.0f for share >= 0.5" % (W, H, 0.5 * H))
print("ladder: SPACE_XS=4 SPACE_SM=8 SPACE_12=12 SPACE_MD=16 SPACE_LG=24")
print("declared role gaps: 0/4/12/16 only -- 24 is used by NO role")
print()
print("%-6s %-7s %-8s %-6s %-6s %-6s %-6s %-7s %s" % (
    "gap", "need", "chat", "share", "rows", "input", "section", "rail/rib", "verdict"))
for gap, label in GAPS:
    r = measure(gap)
    print("%-6d %-7d %-8d %-6.4f %-6d %-6d %-6d %-7s %s  %s" % (
        gap, r["need"], r["chat"], r["share"], r["rows"],
        r["composer"], r["section"], "%d/%d" % (r["rail"], r["ribbon"]),
        "PASS" if r["share"] >= 0.5 else "FAIL (short %d)" % (int(0.5 * H) - r["chat"]),
        label))
