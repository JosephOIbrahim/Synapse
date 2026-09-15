"""M4/M5 transcript probes + M6 TEXT_ON_ACCENT counterfactual (isolated process)."""
import os, sys, json, types, tempfile, colorsys

_ROOT = r"C:\Users\User\SYNAPSE"
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.modules.setdefault("hou", types.ModuleType("hou"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["SYNAPSE_REDUCED_MOTION"] = "1"
os.environ["SYNAPSE_PANEL_SETTINGS"] = os.path.join(
    tempfile.mkdtemp(prefix="synapse_measure2_"), "panel_settings.json")

NEUTRAL = os.environ.get("MEASURE_TOA_NEUTRAL")  # set -> M6 counterfactual mode

from PySide6 import QtWidgets, QtGui, QtCore
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from synapse.panel.designsystem import fontload, tokens as t
if NEUTRAL:                      # patched BEFORE qss is ever imported/built
    t.TEXT_ON_ACCENT = NEUTRAL
from synapse.panel.designsystem import qss, rhythm
fontload.load_application_fonts()

W, H = 340, 760
PROFILES = ("curious", "expert", "ml")
OUT = {}


def panel(profile="expert"):
    from synapse.panel.synapse_panel import SynapsePanel
    p = SynapsePanel()
    p._recompose(profile)
    p.resize(W, H)
    p.show()
    APP.processEvents()
    p._set_face("direct")
    p._converse_stack.setCurrentIndex(0)
    APP.processEvents()
    return p


def hue_buckets(widget):
    img = widget.grab().toImage().convertToFormat(QtGui.QImage.Format.Format_RGB888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    raw = bytes(img.constBits())
    cols = set()
    for y in range(h):
        row = raw[y * bpl:y * bpl + 3 * w]
        cols.update(zip(row[0::3], row[1::3], row[2::3]))
    out = {}
    for r, g, b in cols:
        if max(r, g, b) - min(r, g, b) > 24:
            bk = int(colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[0] * 360) // 15
            out.setdefault(bk, []).append((r, g, b))
    return out


if NEUTRAL:
    OUT["TEXT_ON_ACCENT_in_sheet"] = NEUTRAL
    OUT["sheet_mentions_old_ink"] = "#0F1F2B" in qss.stylesheet()
    for prof in PROFILES:
        p = panel(prof)
        try:
            bk = hue_buckets(p)
            OUT.setdefault("boot_buckets", {})[prof] = {
                "count": len(bk),
                "buckets": {str(k): {"n": len(v), "sample": sorted(v)[:3]}
                            for k, v in sorted(bk.items())}}
        finally:
            p.close()
    print("@@@JSON@@@")
    print(json.dumps(OUT, indent=1, default=str))
    raise SystemExit(0)


def transcript_probe(prof, doc_margin=None):
    p = panel(prof)
    try:
        cd = None
        for c in p.findChildren(QtWidgets.QWidget):
            if c.__class__.__name__ == "ChatDisplay":
                cd = c
                break
        if cd is None:
            return {"error": "ChatDisplay not found"}
        if doc_margin is not None:
            cd.document().setDocumentMargin(doc_margin)
        cd.append_user_message("first line here")
        cd.append_user_message("second line same speaker")
        cd.append_synapse_message("a reply from the other speaker")
        cd.append_synapse_message("and its own second line")
        APP.processEvents()
        doc = cd.document()
        lay = doc.documentLayout()
        blocks = []
        b = doc.begin()
        prev = None
        while b.isValid():
            bf = b.blockFormat()
            r = lay.blockBoundingRect(b)
            bl = b.layout()
            entry = {
                "n": b.blockNumber(), "text": b.text()[:34],
                "role": bf.property(QtGui.QTextFormat.UserProperty),
                "topMargin": round(bf.topMargin(), 2),
                "bottomMargin": round(bf.bottomMargin(), 2),
                "y": round(r.y(), 2), "h": round(r.height(), 2),
                "x": round(r.x(), 2),
                "line0_x": round(bl.lineAt(0).x(), 2) if bl.lineCount() else None,
                "line0_h": round(bl.lineAt(0).height(), 2) if bl.lineCount() else None,
                "indent_px": round(bf.indent() * doc.indentWidth(), 2),
                "leftMargin": round(bf.leftMargin(), 2),
            }
            if prev is not None:
                entry["visual_gap_from_prev"] = round(r.y() - (prev["y"] + prev["h"]), 2)
                entry["sum_of_margins"] = round(prev["bottomMargin"] + bf.topMargin(), 2)
            blocks.append(entry)
            prev = entry
            b = b.next()
        first_text_x = None
        b = doc.begin()
        while b.isValid():
            if b.text().strip():
                bl = b.layout()
                if bl.lineCount():
                    first_text_x = round(lay.blockBoundingRect(b).x()
                                         + b.blockFormat().leftMargin()
                                         + bl.lineAt(0).x(), 2)
                break
            b = b.next()
        vp = cd.viewport()
        off = vp.mapTo(p, QtCore.QPoint(0, 0))
        return {
            "documentMargin": doc.documentMargin(),
            "doc_height": round(doc.size().height(), 2),
            "blocks": blocks,
            "first_text_x_in_doc": first_text_x,
            "viewport_x_in_panel": off.x(),
            "frameWidth": cd.frameWidth(),
            "body_x_in_panel": None if first_text_x is None
                               else round(off.x() + first_text_x, 2),
        }
    finally:
        p.close()


from synapse.panel import message_formatter as mf
OUT["_constants"] = {
    "_GROUP_MARGIN_Y": mf._GROUP_MARGIN_Y, "_MSG_MARGIN_Y": mf._MSG_MARGIN_Y,
    "ROLE_GAPS_group": rhythm.ROLE_GAPS["group"],
    "ROLE_GAPS_row": rhythm.ROLE_GAPS["row"],
    "gap_group": {d: t.gap(rhythm.ROLE_GAPS["group"], d)
                  for d in ("airy", "standard", "tight")},
    "gap_row": {d: t.gap(rhythm.ROLE_GAPS["row"], d)
                for d in ("airy", "standard", "tight")},
}
for label, dm in (("default", None), ("margin_0", 0), ("margin_4", 4)):
    try:
        OUT[label] = transcript_probe("expert", dm)
    except Exception as e:
        OUT[label] = {"error": "%s: %s" % (type(e).__name__, e)}

print("@@@JSON@@@")
print(json.dumps(OUT, indent=1, default=str))
