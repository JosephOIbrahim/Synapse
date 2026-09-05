"""LENS SYSTEM probe. Same construction path as measure_regions.py. Read-only.
Run: SYNAPSE_PANEL_SETTINGS=<settings json> QT_QPA_PLATFORM=offscreen hython probe_system.py
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "python"))
from PySide6 import QtWidgets, QtGui
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
from synapse.panel.designsystem import qss, rhythm, tokens as t
from synapse.panel.synapse_panel import SynapsePanel
p = SynapsePanel(); p.setStyleSheet(qss.stylesheet()); p.resize(340, 760); p.show()
app.processEvents(); app.processEvents()
density = p.property("density")
out = {"density": density, "profile": os.environ.get("SYNAPSE_PANEL_SETTINGS")}
out["panel_minimumSizeHint"] = [p.minimumSizeHint().width(), p.minimumSizeHint().height()]
out["panel_minimumSize"] = [p.minimumWidth(), p.minimumHeight()]
# role census at runtime
roles = {}; nolayout = []; runtime_sheets = []; off_grid = []
for w in p.findChildren(QtWidgets.QWidget):
    r = w.property("rhythm_role")
    if r:
        roles[r] = roles.get(r, 0) + 1
        lay = w.layout()
        if lay is None:
            nolayout.append((r, w.objectName(), type(w).__name__))
    if w.styleSheet():
        runtime_sheets.append((w.objectName(), type(w).__name__, w.styleSheet()[:60]))
out["runtime_roles"] = roles; out["role_without_layout"] = nolayout; out["runtime_inline_sheets"] = runtime_sheets
# applied gaps per role
gaps = {}
for w in p.findChildren(QtWidgets.QWidget):
    r = w.property("rhythm_role")
    if r and w.layout() is not None:
        gaps.setdefault(r, set()).add(w.layout().spacing())
out["applied_gaps_by_role"] = {k: sorted(v) for k, v in gaps.items()}
# every layout spacing in the tree, grid check
for lay in p.findChildren(QtWidgets.QLayout):
    s = lay.spacing()
    if s > 0 and s not in t.SPACE_GRID and s not in {t.gap(g, density) for g in t.SPACE_GRID}:
        owner = lay.parentWidget().objectName() if lay.parentWidget() else "?"
        off_grid.append((owner, type(lay).__name__, s))
out["off_grid_layout_spacings"] = off_grid
# tab row pills
pills = []
tab = p.findChild(QtWidgets.QWidget, "DsTabRow")
for b in tab.findChildren(QtWidgets.QPushButton):
    f = b.font()
    pills.append({"text": b.text(), "role": b.property("rhythm_role"), "family": f.family(),
                  "px": f.pixelSize(), "spacing": round(f.letterSpacing(), 2),
                  "spacingType": f.letterSpacingType().value, "caps": f.capitalization().value,
                  "w": b.width(), "h": b.height(), "hint_h": b.sizeHint().height(), "active": b.property("active")})
out["tab_pills"] = pills
out["tab_row"] = {"h": tab.height(), "spacing": tab.layout().spacing(), "margins": [tab.layout().contentsMargins().left(), tab.layout().contentsMargins().top(), tab.layout().contentsMargins().right(), tab.layout().contentsMargins().bottom()]}
# verb rail
acts = p.findChild(QtWidgets.QWidget, "DsActs")
if acts is not None:
    out["verb_rail"] = {"h": acts.height(), "spacing": acts.layout().spacing() if acts.layout() else None,
        "role": acts.property("rhythm_role"), "minhint_w": acts.minimumSizeHint().width(),
        "verbs": [(v.text(), v.width(), v.minimumSizeHint().width()) for v in acts.findChildren(QtWidgets.QPushButton)]}
# recall card
rc = getattr(p, "_recall_card", None)
if rc is not None:
    hf = rc.header.font()
    out["recall_card"] = {"bands_spacing": rc.layout().spacing(), "header_role": rc.header.property("rhythm_role"),
        "header_spacing": round(hf.letterSpacing(), 2), "header_family": hf.family(), "visible": rc.isVisible(),
        "status_role": rc.status.property("rhythm_role"), "minhint_w": rc.minimumSizeHint().width()}
# bridge-down foot
fl = getattr(p, "_foot_label", None)
if fl is not None:
    out["foot"] = {"text": fl.text(), "visible": fl.isVisible(), "role": fl.property("rhythm_role")}
# header status
hs = getattr(p, "_header_status", None)
if hs is not None:
    out["header_status"] = {"text": hs.text(), "visible": hs.isVisible()}
# Aa: step the scale and see what moves
before = {"chat_scale": getattr(p, "_font_scale", None), "chrome": getattr(p, "_chrome_scale", None),
          "pill_px": pills[0]["px"] if pills else None, "group_gap": out["applied_gaps_by_role"].get("group")}
stepper = None
for name in ("_cycle_font_scale", "_on_font_scale", "_step_font_scale", "cycle_font_scale", "_bump_scale"):
    if hasattr(p, name): stepper = name; break
out["aa_stepper"] = stepper
if stepper:
    try:
        getattr(p, stepper)(); app.processEvents()
        b2 = tab.findChildren(QtWidgets.QPushButton)[0].font().pixelSize()
        out["aa_after"] = {"chat_scale": getattr(p, "_font_scale", None), "chrome": getattr(p, "_chrome_scale", None),
                           "pill_px": b2, "group_gap": sorted({w.layout().spacing() for w in p.findChildren(QtWidgets.QWidget) if w.property("rhythm_role")=="group" and w.layout()})}
    except Exception as e:
        out["aa_after"] = "ERR " + repr(e)
out["aa_before"] = before
# gate proposal card
try:
    from synapse.panel import gate_widget as gw
    cls = getattr(gw, "GateWidget", None) or getattr(gw, "HumanGateWidget", None)
    out["gate_widget_class"] = cls.__name__ if cls else None
except Exception as e:
    out["gate_widget_class"] = "ERR " + repr(e)
sys.stdout.write(json.dumps(out, default=str) + "\n")
p.close(); app.processEvents()
