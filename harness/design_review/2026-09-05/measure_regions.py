"""Design-review measurement: region geometry of the landed panel at 340x760,
offscreen, per profile. Same construction path as harness/notes/panel_shot.py
(SynapsePanel + qss.stylesheet(), resize, show, processEvents). Read-only on
the product; writes only regions_<profile>.json beside this file.

Run:  SYNAPSE_PANEL_SETTINGS=<json with {"profile": "<p>"}> QT_QPA_PLATFORM=offscreen
      hython measure_regions.py <profile>
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
fonts = fontload.load_application_fonts()
p = SynapsePanel()
p.setStyleSheet(qss.stylesheet())
p.resize(340, 760)
p.show()
app.processEvents()
# J4 (harness/cto/runs/2026-09-05/RULING_JOE_FIVE.md): the UI profile switch is
# retired and SynapsePanel() composes `expert` whatever the persisted profile
# says, so the probe recomposes explicitly - the machinery path
# tests/panel/test_bc_wave.py::_panel uses - to measure curious / ml.
if profile != getattr(p, "_layout_profile", profile):
    p._recompose(profile)
    app.processEvents()
p._set_face("direct"); p._converse_stack.setCurrentIndex(0)
app.processEvents()

def geo(w):
    if w is None:
        return None
    tl = w.mapTo(p, QtCore.QPoint(0, 0))
    return {"x": tl.x(), "y": tl.y(), "w": w.width(), "h": w.height(),
            "visible": w.isVisible(), "objectName": w.objectName(),
            "rhythm_role": w.property("rhythm_role")}

cache = p._region_cache
rail = cache.get("_build_rail"); ribbon = cache.get("_build_context_ribbon")
consent_slot = getattr(p, "_consent_slot", None)   # bc-wave BC-6a
composer = p._input.parentWidget()           # the _build_input section (DsSection)
face = composer.parentWidget()               # direct face shell (bc-wave BC-1: no act band)
out = {
    "profile": getattr(p, "_layout_profile", None),
    "density": p.property("density"),
    "panel": {"w": p.width(), "h": p.height()},
    "fonts": {"ok": fonts.get("ok"), "families": fonts.get("families"), "build_mismatch": fonts.get("build_mismatch")},
    "wordmark": dict(geo(p._wordmark), text=p._wordmark.text(),
                     pixelSize=p._wordmark.font().pixelSize(), bold=p._wordmark.font().bold(),
                     weight=p._wordmark.font().weight(), family=p._wordmark.font().family(),
                     letterSpacing=p._wordmark.font().letterSpacing(),
                     sizeHint_w=p._wordmark.sizeHint().width()),
    "mark": geo(p._mark),
    "rail": geo(rail), "ribbon": geo(ribbon), "consent_slot": geo(consent_slot),
    "author": dict(geo(p._author_lbl), text=p._author_lbl.text(), hint_w=p._author_lbl.sizeHint().width()),
    "state": dict(geo(p._header_status), text=p._header_status.text(), hint_w=p._header_status.sizeHint().width()),
    "direct_face": geo(face), "chat": geo(p._chat),
    "composer": geo(composer), "input": geo(p._input), "send": geo(p._send_btn), "khint": geo(p._khint),
    "pills": {k: geo(v) for k, v in p._face_pills.items()},
    # bc-wave: every visible text widget on the CHAT face with its hint - the
    # no-elide predicate (the one permitted elision is DsContextLabel).
    "labels": [dict(objectName=w.objectName(), text=w.text(), w=w.width(), hint_w=w.sizeHint().width())
               for w in (p.findChildren(QtWidgets.QLabel) + p.findChildren(QtWidgets.QAbstractButton))
               if w.isVisible() and w.text().strip()],
    "chrome_scale": getattr(p, "_chrome_scale", None),
}
with open(os.path.join(HERE, "regions_%s.json" % profile), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
sys.stdout.write(json.dumps({k: out[k] for k in ("profile", "density", "rail", "ribbon", "chat", "composer", "wordmark")}) + "\n")
p.close(); app.processEvents()
