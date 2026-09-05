"""LENS USE round-2 probe: artist-seat measurements at 340x760, per profile.
Read-only on the product; writes only use_<profile>.json here.
Run: SYNAPSE_PANEL_SETTINGS=settings_<p>.json QT_QPA_PLATFORM=offscreen hython use_probe.py <p>
"""
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
p = SynapsePanel()
p.setStyleSheet(qss.stylesheet())
p.resize(340, 760)
p.show(); app.processEvents()
p._set_face("direct"); p._converse_stack.setCurrentIndex(0); app.processEvents()

def geo(w):
    tl = w.mapTo(p, QtCore.QPoint(0, 0))
    return [tl.x(), tl.y(), w.width(), w.height()]

out = {"profile": profile, "density": p.property("density"),
       "min_hint": [p.minimumSizeHint().width(), p.minimumSizeHint().height()]}
# rail state labels + boot truth (SYS-8)
out["rail_labels"] = {n: {"text": getattr(p, n).text(), "geo": geo(getattr(p, n)),
                          "hint_w": getattr(p, n).sizeHint().width()}
                      for n in ("_header_status", "_meter_lbl", "_palette_hint", "_author_lbl", "_foot_label")}
out["boot_truth"] = {"header": p._header_status.text(), "foot": p._foot_label.text(),
                     "mark_state": getattr(p._mark, "_state", None)}
# verbs
act = p._font_btn.parentWidget()
verbs = [b for b in act.findChildren(QtWidgets.QPushButton) if b.objectName() == "DsVerb"]
out["verbs"] = [{"text": b.text(), "w": b.width(), "hint_w": b.sizeHint().width(), "geo": geo(b)} for b in verbs]
out["verb_rail"] = {"geo": geo(act), "spacing": act.layout().spacing() if act.layout() else None,
                    "natural": sum(b.sizeHint().width() for b in verbs) + (act.layout().spacing() if act.layout() else 0) * (len(verbs) - 1)}
# composer
attach = [b for b in p.findChildren(QtWidgets.QPushButton) if b.toolTip().startswith("Attach")]
out["composer"] = {"attach": geo(attach[0]) if attach else None,
                   "attach_icon": [attach[0].iconSize().width(), attach[0].iconSize().height()] if attach else None,
                   "send": geo(p._send_btn), "input": geo(p._input),
                   "placeholder": p._input.placeholderText(), "khint": {"text": p._khint.text(), "geo": geo(p._khint),
                   "px": p._khint.font().pixelSize()}}
# pills / chrome
pills = [b for b in p.findChildren(QtWidgets.QPushButton) if b.objectName() == "DsPill"]
out["pills"] = [{"text": b.text(), "w": b.width(), "hint_w": b.sizeHint().width(), "geo": geo(b), "px": b.font().pixelSize()} for b in pills]
out["chat_top_y"] = geo(p._chat)[1]
# small targets (visible, min side < 26)
out["small_targets"] = [{"text": b.text(), "geo": geo(b)} for b in p.findChildren(QtWidgets.QAbstractButton)
                        if b.isVisible() and 0 < min(b.width(), b.height()) < 26]
# gate: fold toggle geometry on the work face + REVIEW-card control count
p._set_face("work"); app.processEvents()
g = getattr(p, "_gate", None)
gate = {}
if g is not None:
    gate["fold_toggle"] = {"text": g._header.text(), "geo": geo(g._header), "hint_h": g._header.sizeHint().height()}
    g._add_proposal_card({"proposal_id": "use-r2-review", "level": "review", "operation": "delete_node",
                          "created_at": "now"})
    app.processEvents()
    card = g._cards.get("use-r2-review")
    gate["review_card_buttons"] = [b.text() for b in card.findChildren(QtWidgets.QAbstractButton)] if card else None
    g._add_proposal_card({"proposal_id": "use-r2-approve", "level": "approve", "operation": "submit_render",
                          "created_at": "now"})
    app.processEvents()
    card2 = g._cards.get("use-r2-approve")
    gate["approve_card_buttons"] = [b.text() for b in card2.findChildren(QtWidgets.QAbstractButton)] if card2 else None
    gate["fold_toggle_after"] = geo(g._header)
out["gate"] = gate
# revert control reachability: which face holds a REVERT verb
rev = [b for b in p.findChildren(QtWidgets.QAbstractButton) if "REVERT" in b.text().upper()]
out["revert_controls"] = [{"text": b.text(), "visible_on_work": b.isVisible()} for b in rev]
p._set_face("direct"); app.processEvents()
out["revert_visible_on_chat"] = [b.isVisible() for b in rev]
# SYS-9: does the HDA describe view see the profile's density? (layout spacing of DescribeView)
dv = [w for w in p.findChildren(QtWidgets.QWidget) if w.objectName() == "DescribeView"]
out["hda_describe"] = {"spacing": dv[0].layout().spacing(), "margins": list(dv[0].layout().contentsMargins().getCoords()),
                       "role": dv[0].property("rhythm_role")} if dv else None
tr = p._chat if hasattr(p, "_chat") else None
out["chat_group_spacing"] = None
json.dump(out, open(os.path.join(HERE, "use_%s.json" % profile), "w"), indent=1)
print(json.dumps(out, indent=1))
