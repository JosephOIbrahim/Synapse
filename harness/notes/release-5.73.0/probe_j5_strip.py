"""J5 strip probe — does the four-link strip fit in `host` at each gap?

Read-only, and it touches ONLY the footer machinery: it builds the same four
`DsFooterLink` buttons with the same font role, in the same `_ShortcutLayout`,
and asks the layout itself (`heightForWidth`) how many rows it would take at a
given width. No panel, no token patching -- patching `tokens.SPACE_*` moves
other machinery (the rail reads SPACE_12 too), which is what made the first gap
probe's numbers unusable.

    "<HFS>/bin/hython.exe" harness/notes/release-5.73.0/probe_j5_strip.py
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
        tempfile.mkdtemp(prefix="synapse_j5strip_"), "panel_settings.json")

from PySide6 import QtWidgets   # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from synapse.panel.designsystem import fontload                        # noqa: E402
fontload.load_application_fonts()
from synapse.panel.designsystem import tokens as t                     # noqa: E402
from synapse.panel.designsystem import components as c                 # noqa: E402
from synapse.panel.designsystem import qss                             # noqa: E402
from synapse.panel.synapse_panel import _ShortcutLayout                # noqa: E402

HOST = 280          # 340 panel - 2x GUTTER(30): the pref dock width
SCALE = 1.0         # _chrome_scale when the host font is Houdini's 12px body

UPDATES = ["Updates", "Updates (1)", "Updates (12)", "Updates (999)",
           "Updates · quiet"]

_KEEP = []          # hosts must outlive each measurement or Qt frees them


def build(updates_label, gap):
    """The footer's strip, on a real host widget so the buttons stay parented."""
    host = QtWidgets.QWidget()
    host.setStyleSheet(qss.stylesheet(SCALE))     # the panel root's own sheet
    lay = _ShortcutLayout(t.scaled(gap, SCALE), t.scaled(t.SPACE_XS, SCALE))
    host.setLayout(lay)
    for text in ("Commands", "Render", "Saved networks", updates_label):
        b = c.Button(text, variant="ghost")
        b.setObjectName("DsFooterLink")
        c.apply_font_role(b, "caption", scale=SCALE)
        b.setSizePolicy(QtWidgets.QSizePolicy.Maximum,
                        QtWidgets.QSizePolicy.Preferred)
        lay.addWidget(b)                          # reparents to `host`
    host.resize(HOST, 200)
    host.ensurePolished()
    lay.activate()
    _KEEP.append((host, lay))      # hold the C++ host alive for the run
    return lay


print("host = %d px (340 panel - 2 x GUTTER 30); _chrome_scale = %.2f" % (HOST, SCALE))
print("ladder 4 . 8 . 12 . 16 . 24 . 32 . 48   |  role gaps declared: 0/4/12/16")
print()
print("%-6s %-16s %-6s %-6s %-6s %s" % ("gap", "Updates label", "sum_w", "need", "rows", "verdict"))
for label in UPDATES:
    for gap in (24, 16, 12, 8, 4):
        lay = build(label, gap)
        widths = [lay.itemAt(i).sizeHint().width() for i in range(lay.count())]
        row_h = max(lay.itemAt(i).sizeHint().height() for i in range(lay.count()))
        h = lay.heightForWidth(HOST)
        cm = lay.contentsMargins()
        rows = 1 if h <= row_h else 2
        need = sum(widths) + gap * (len(widths) - 1)
        print("   trace gap=%d %-16s inner_w=%d cm=%s geom_w=%d vgap=%s" % (
            gap, label, HOST - cm.left() - cm.right(),
            (cm.left(), cm.top(), cm.right(), cm.bottom()),
            lay.geometry().width(), lay._vertical_gap))
        if rows > 1:
            acc = widths[0]
            for i in range(1, len(widths)):
                nxt = acc + gap + widths[i]
                if nxt > HOST - cm.left() - cm.right():
                    print("      row 2 starts at item %d (%s): %d + %d + %d = %d"
                          % (i, lay.itemAt(i).widget().text(), acc, gap, widths[i], nxt))
                    break
                acc = nxt
        print("%-6d %-16s %-6d %-6d %-6d %-6d %-4d %s   %s" % (
            gap, label, sum(widths), need, h, row_h, rows,
            "PASS (%d spare)" % (HOST - need) if rows == 1
            else "WRAPS (over by %d)" % (need - HOST),
            widths))
    print()
