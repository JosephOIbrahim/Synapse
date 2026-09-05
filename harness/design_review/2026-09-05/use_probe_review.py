"""LENS USE round-2 follow-up: Work face in the done sub-state, REVIEW vs APPROVE cards.
Writes use_review_<profile>.json + use_review_<profile>.png here only."""
import json, os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for p in (ROOT, os.path.join(ROOT, "python")):
    if p not in sys.path:
        sys.path.insert(0, p)
profile = sys.argv[1]
from PySide6 import QtWidgets, QtCore
from synapse.panel.designsystem import qss, fontload
from synapse.panel.synapse_panel import SynapsePanel
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
fontload.load_application_fonts()
p = SynapsePanel(); p.setStyleSheet(qss.stylesheet()); p.resize(340, 760); p.show(); app.processEvents()
def geo(w):
    tl = w.mapTo(p, QtCore.QPoint(0, 0)); return [tl.x(), tl.y(), w.width(), w.height()]
out = {"profile": profile}
# simulate the v9.1 Option-A path: a REVIEW proposal arrives
g = p._gate
prop = {"proposal_id": "r2-review", "level": "review", "operation": "delete_node", "created_at": "now"}
g._add_proposal_card(prop)   # what the HumanGate callback does (gate_widget.py:494-507)
p._on_gate_raised(prop)       # what the panel relay does (synapse_panel.py:2007-2021)
app.processEvents()
out["face_after_review_gate"] = p._face if hasattr(p, "_face") else None
out["stack_index"] = p._faces.currentIndex() if hasattr(p, "_faces") else None
out["gate_expanded"] = g._expanded
out["fold_toggle"] = {"text": g._header.text(), "geo": geo(g._header), "hint_h": g._header.sizeHint().height(), "visible": g._header.isVisible()}
card = g._cards.get("r2-review")
out["review_card"] = {"geo": geo(card), "buttons": [b.text() for b in card.findChildren(QtWidgets.QAbstractButton)],
                      "labels": [l.text() for l in card.findChildren(QtWidgets.QLabel)]}
rev = [b for b in p.findChildren(QtWidgets.QAbstractButton) if "REVERT" in b.text().upper()]
out["revert"] = [{"text": b.text(), "visible": b.isVisible(), "geo": geo(b)} for b in rev]
acc = [b for b in p.findChildren(QtWidgets.QAbstractButton) if b.text().upper().startswith("ACCEPT")]
out["accept"] = [{"text": b.text(), "visible": b.isVisible(), "geo": geo(b)} for b in acc]
# add an APPROVE card for comparison
g._add_proposal_card({"proposal_id": "r2-approve", "level": "approve", "operation": "submit_render", "created_at": "now"})
app.processEvents()
c2 = g._cards.get("r2-approve")
out["approve_card"] = {"geo": geo(c2), "buttons": [{"text": b.text(), "geo": geo(b)} for b in c2.findChildren(QtWidgets.QAbstractButton)]}
# header state text while the gate is up
out["header_status"] = {"text": p._header_status.text(), "geo": geo(p._header_status)}
out["mark_state"] = getattr(p._mark, "_state", None)
p.grab().save(os.path.join(HERE, "use_review_%s.png" % profile))
json.dump(out, open(os.path.join(HERE, "use_review_%s.json" % profile), "w"), indent=1)
print(json.dumps(out, indent=1))
