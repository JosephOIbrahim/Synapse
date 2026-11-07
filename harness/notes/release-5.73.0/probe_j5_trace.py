"""One-shot: log what `_ShortcutLayout._arrange` actually sees for the wrap cases."""
import os, sys, tempfile, types
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.modules.setdefault("hou", types.ModuleType("hou"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")
if not os.environ.get("SYNAPSE_PANEL_SETTINGS"):
    os.environ["SYNAPSE_PANEL_SETTINGS"] = os.path.join(
        tempfile.mkdtemp(prefix="synapse_j5trace_"), "panel_settings.json")

from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from synapse.panel.designsystem import fontload
fontload.load_application_fonts()
from synapse.panel.designsystem import tokens as t, components as c, qss
import synapse.panel.synapse_panel as sp

_ORIG = sp._ShortcutLayout._arrange
_LOG = []

def traced(self, rect, place):
    hint = [it.sizeHint().width() for it in self._items]
    _LOG.append((rect.width(), self._horizontal_gap, hint,
                 [it.widget().text() for it in self._items]))
    return _ORIG(self, rect, place)

sp._ShortcutLayout._arrange = traced

_KEEP = []
def build(label, gap):
    host = QtWidgets.QWidget()
    host.setStyleSheet(qss.stylesheet(1.0))
    lay = sp._ShortcutLayout(t.scaled(gap, 1.0), t.scaled(t.SPACE_XS, 1.0))
    host.setLayout(lay)
    for text in ("Commands", "Render", "Saved networks", label):
        b = c.Button(text, variant="ghost")
        b.setObjectName("DsFooterLink")
        c.apply_font_role(b, "caption", scale=1.0)
        b.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)
        lay.addWidget(b)
    host.resize(280, 200)
    host.ensurePolished()
    lay.activate()
    _KEEP.append((host, lay))
    return lay

for label in ("Updates (999)", "Updates \u00b7 quiet", "Updates"):
    for gap in (12, 4):
        _LOG.clear()
        lay = build(label, gap)
        h = lay.heightForWidth(280)
        mine = [lay.itemAt(i).sizeHint().width() for i in range(lay.count())]
        print("label=%-16s gap=%-3d h=%d  mine=%s  greedy_sum=%d"
              % (label, gap, h, mine, sum(mine) + gap * 3))
        for w, g, hint, texts in _LOG:
            print("    _arrange(rect.width=%d, hgap=%d, hints=%s)  greedy=%d"
                  % (w, g, hint, sum(hint) + g * (len(hint) - 1)))
