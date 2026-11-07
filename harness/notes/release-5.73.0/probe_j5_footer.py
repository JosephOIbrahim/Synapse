"""J5 footer probe — how wide is the four-link strip, and by how much?
Read-only.
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
        tempfile.mkdtemp(prefix="synapse_j5f_"), "panel_settings.json")

from PySide6 import QtWidgets   # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from synapse.panel.designsystem import fontload      # noqa: E402
fontload.load_application_fonts()
from synapse.panel.designsystem import tokens as t   # noqa: E402
from synapse.panel.synapse_panel import SynapsePanel, _ShortcutLayout  # noqa: E402

p = SynapsePanel()
p._recompose("expert")
p.resize(340, 760)
p.show()
app.processEvents()
p._set_face("direct")
p._converse_stack.setCurrentIndex(0)
app.processEvents()

btns = (p._commands_btn, p._render_btn, p._recipes_btn, p._events_btn)
lay = btns[0].parentWidget().layout()
print("layout=%s  hgap=%r  vgap=%r" % (type(lay).__name__,
                                       getattr(lay, "_horizontal_gap", None),
                                       getattr(lay, "_vertical_gap", None)))
m = lay.contentsMargins()
print("margins L/R = %d/%d" % (m.left(), m.right()))
total = 0
for b in btns:
    w = b.sizeHint().width()
    total += w
    print("  %-18r w=%-4d h=%d" % (b.text(), w, b.sizeHint().height()))
gap = getattr(lay, "_horizontal_gap", 0)
need = total + gap * 3
print("sum(w)=%d  +3*gap=%d  == %d" % (total, gap * 3, need))

parent = btns[0].parentWidget()
print("footer host %s width=%d  (rect the layout gets)" % (
    type(parent).__name__, parent.width()))
print("chrome_scale=%r  SPACE_LG=%d SPACE_MD=%d SPACE_XS=%d" % (
    getattr(p, "_chrome_scale", None), t.SPACE_LG, t.SPACE_MD, t.SPACE_XS))
for name in ("SPACE_MD", "SPACE_SM"):
    print("  if gap were %s (%d): need=%d  fits=%s" % (
        name, getattr(t, name), total + getattr(t, name) * 3,
        total + getattr(t, name) * 3 <= parent.width()))
