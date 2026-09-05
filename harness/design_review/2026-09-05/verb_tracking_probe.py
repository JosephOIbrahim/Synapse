"""TYPE lens: exact verb-rail demand at each tracking role (11px Space Mono),
hint = advance + 1 (measured: EXPLAIN adv 56 -> hint 57), gaps 4 x 16 (measured x
positions 30/103/144/219/293 at expert 340). Writes verb_tracking.json."""
import json, os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for p in (ROOT, os.path.join(ROOT, "python")):
    sys.path.insert(0, p)
from PySide6 import QtWidgets, QtGui
from synapse.panel.designsystem import fontload, tokens as t
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
fontload.load_application_fonts()
verbs = ("EXPLAIN", "FIX", "OPTIMIZE", "BUILD HDA", "Aa")
out = {}
for role in ("BODY", "DATA", "SEND", "LABEL_SM", "LABEL"):
    fm = QtGui.QFontMetrics(fontload.tracked_font(role, 11, mono=True))
    adv = {v: fm.horizontalAdvance(v) for v in verbs}
    demand = sum(a + 1 for a in adv.values()) + 4 * 16
    out[role] = {"em": t.TRACKING_EM[role], "advance": adv, "demand_px": demand, "content_w": 280, "fits": demand <= 280}
# sentence-case sans alternative, same 11px and 12px, no tracking
for px in (11, 12):
    fm = QtGui.QFontMetrics(fontload.tracked_font("BODY", px, mono=False))
    adv = {v: fm.horizontalAdvance(v.title() if v != "Aa" else v) for v in verbs}
    out["sans_%dpx_titlecase" % px] = {"advance": adv, "demand_px": sum(a + 1 for a in adv.values()) + 64, "fits": sum(a + 1 for a in adv.values()) + 64 <= 280}
json.dump(out, open(os.path.join(HERE, "verb_tracking.json"), "w"), indent=1)
print(json.dumps(out))
