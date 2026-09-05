"""LENS SUBTRACT census: every widget in the landed panel at 340x760 offscreen,
per profile. Read-only on the product; writes only census_<profile>.json here.
Run: SYNAPSE_PANEL_SETTINGS=settings_<p>.json QT_QPA_PLATFORM=offscreen hython census_subtract.py <p>
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

def path_of(w):
    parts = []
    cur = w
    while cur is not None and cur is not p:
        nm = cur.objectName() or type(cur).__name__
        parts.append(nm)
        cur = cur.parentWidget()
    return "/".join(reversed(parts))

rows = []
for w in p.findChildren(QtWidgets.QWidget):
    if not w.isVisible():
        continue
    g = geo(w)
    if g[1] >= 760 or g[0] >= 340:
        continue
    text = None
    for attr in ("text", "placeholderText", "toolTip"):
        if hasattr(w, attr):
            try:
                v = getattr(w, attr)()
                if v:
                    text = (attr, v[:60]); break
            except Exception:
                pass
    is_btn = isinstance(w, QtWidgets.QAbstractButton)
    entry = {"path": path_of(w), "cls": type(w).__name__, "obj": w.objectName(),
             "geo": g, "text": text, "button": is_btn,
             "sizeHint": [w.sizeHint().width(), w.sizeHint().height()],
             "role": w.property("rhythm_role")}
    if isinstance(w, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
        try:
            entry["font"] = [w.font().family(), w.font().pixelSize(), round(w.font().letterSpacing(), 1)]
        except Exception:
            pass
    rows.append(entry)

btns = [w for w in p.findChildren(QtWidgets.QAbstractButton)]
under = [{"path": path_of(b), "text": b.text(), "sizeHint_h": b.sizeHint().height(),
          "actual": geo(b), "visible": b.isVisible()}
         for b in btns if 0 < b.sizeHint().height() < 26]
zero_w = [{"path": path_of(w), "cls": type(w).__name__, "text": (w.text() if hasattr(w, "text") else None),
           "geo": geo(w)} for w in p.findChildren(QtWidgets.QWidget)
          if w.isVisible() and (w.width() == 0 or w.height() == 0)]
act = p._font_btn.parentWidget()
verbs = [{"text": b.text(), "w": b.width(), "hint_w": b.sizeHint().width(),
          "clipped": b.width() < b.sizeHint().width()}
         for b in act.findChildren(QtWidgets.QPushButton) if b.objectName() == "DsVerb"]
hs = getattr(p, "_health_strip", None)
health = None
if hs is not None:
    health = {"geo": geo(hs), "visible": hs.isVisible(),
              "cells": [{"cls": type(c).__name__, "text": (c.text() if hasattr(c, "text") else None),
                         "geo": geo(c), "visible": c.isVisible()} for c in hs.findChildren(QtWidgets.QLabel)]}
rail_labels = {}
for name in ("_header_status", "_meter_lbl", "_palette_hint", "_author_lbl", "_foot_label", "_ctx_label", "_khint"):
    w = getattr(p, name, None)
    if w is not None:
        rail_labels[name] = {"text": w.text(), "geo": geo(w), "visible": w.isVisible(),
                             "hint_w": w.sizeHint().width()}
out = {"profile": profile, "density": p.property("density"),
       "visible_widgets": len(rows), "visible_buttons": sum(1 for r in rows if r["button"]),
       "visible_labels": sum(1 for r in rows if r["cls"] == "QLabel"),
       "under26": under, "zero_size_visible": zero_w, "verbs": verbs, "health_strip": health,
       "rail_labels": rail_labels, "rows": rows}
with open(os.path.join(HERE, "census_%s.json" % profile), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1)
print(json.dumps({k: out[k] for k in ("profile", "density", "visible_widgets", "visible_buttons", "visible_labels", "under26", "zero_size_visible", "verbs", "health_strip", "rail_labels")}, indent=1))
p.close(); app.processEvents()
