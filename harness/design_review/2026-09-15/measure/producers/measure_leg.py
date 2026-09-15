"""M1/M4/M5/M6 measurement leg - hython offscreen, no window shown."""
import os, sys, re, json, types, tempfile, colorsys

_ROOT = r"C:\Users\User\SYNAPSE"
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.modules.setdefault("hou", types.ModuleType("hou"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["SYNAPSE_REDUCED_MOTION"] = "1"
os.environ["SYNAPSE_PANEL_SETTINGS"] = os.path.join(
    tempfile.mkdtemp(prefix="synapse_measure_"), "panel_settings.json")

from PySide6 import QtWidgets, QtGui, QtCore

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from synapse.panel.designsystem import fontload, tokens as t, qss, rhythm
fontload.load_application_fonts()

W, H = 340, 760
PROFILES = ("curious", "expert", "ml")
DENSITY = {"curious": "airy", "expert": "standard", "ml": "tight"}
OUT = {}


def panel(profile="expert"):
    from synapse.panel.synapse_panel import SynapsePanel
    p = SynapsePanel()
    p._recompose(profile)
    p.resize(W, H)
    p.show()                      # offscreen platform: no on-screen window
    APP.processEvents()
    p._set_face("direct")
    p._converse_stack.setCurrentIndex(0)
    APP.processEvents()
    return p


def repolish(w):
    for c in [w] + w.findChildren(QtWidgets.QWidget):
        c.style().unpolish(c)
        c.style().polish(c)
    w.updateGeometry()
    APP.processEvents()


# ------------------------------------------------------------------ M1
HDR_RE = re.compile(r"[^\n]*QWidget#DsHeader\s*\{[^}]*margin-bottom[^}]*\}[^\n]*\n?")
m1 = {}
for prof in PROFILES:
    p = panel(prof)
    try:
        hdr = p.findChild(QtWidgets.QWidget, "DsHeader")
        sheet = p.styleSheet() or ""
        owner = p
        if "DsHeader" not in sheet or "margin-bottom" not in sheet:
            for c in [p] + p.findChildren(QtWidgets.QWidget):
                s = c.styleSheet() or ""
                if "DsHeader" in s and "margin-bottom" in s:
                    owner, sheet = c, s
                    break
        rail_h = hdr.height()
        rail_hint = hdr.sizeHint().height()
        rail_geo = (hdr.x(), hdr.y(), hdr.width(), hdr.height())
        par = hdr.parentWidget()
        sibs = [(c.objectName() or c.__class__.__name__, c.y(), c.height())
                for c in par.findChildren(QtWidgets.QWidget,
                                          options=QtCore.Qt.FindDirectChildrenOnly)
                if c.isVisible()]
        stripped, nsub = HDR_RE.subn("", sheet)
        owner.setStyleSheet(stripped)
        repolish(p)
        hdr2 = p.findChild(QtWidgets.QWidget, "DsHeader")
        rail_h2 = hdr2.height()
        rail_hint2 = hdr2.sizeHint().height()
        sibs2 = [(c.objectName() or c.__class__.__name__, c.y(), c.height())
                 for c in par.findChildren(QtWidgets.QWidget,
                                           options=QtCore.Qt.FindDirectChildrenOnly)
                 if c.isVisible()]
        verbs = p.findChildren(QtWidgets.QPushButton, "DsVerb")
        vinfo = []
        for b in verbs[:8]:
            fm = QtGui.QFontMetricsF(b.font())
            cm = b.contentsMargins()
            vinfo.append({
                "text": b.text(), "visible": b.isVisible(),
                "height": b.height(), "sizeHint_h": b.sizeHint().height(),
                "minSizeHint_h": b.minimumSizeHint().height(),
                "font_px": b.font().pixelSize(),
                "fm_height": round(fm.height(), 2),
                "fm_lineSpacing": round(fm.lineSpacing(), 2),
                "fm_ascent": round(fm.ascent(), 2),
                "fm_descent": round(fm.descent(), 2),
                "contentsMargins_tb": [cm.top(), cm.bottom()],
            })
        m1[prof] = {
            "density": DENSITY[prof],
            "sheet_rules_removed": nsub,
            "rail_height_with_rule": rail_h, "rail_height_without_rule": rail_h2,
            "rail_sizeHint_with_rule": rail_hint,
            "rail_sizeHint_without_rule": rail_hint2,
            "rail_geometry": rail_geo,
            "siblings_with_rule": sibs, "siblings_without_rule": sibs2,
            "DsVerb": vinfo,
            "SPACE_SM": t.SPACE_SM,
            "gap_SPACE_SM_at_density": t.gap(t.SPACE_SM, DENSITY[prof]),
        }
    except Exception as e:
        m1[prof] = {"error": "%s: %s" % (type(e).__name__, e)}
    finally:
        p.close()
OUT["M1"] = m1

# ------------------------------------------------------------------ M4 + M5
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
        api = None
        for name in ("append_message", "add_message", "append_turn", "add_turn"):
            if hasattr(cd, name):
                api = name
                break
        if api is None:
            return {"error": "no append api; methods=%s"
                             % [m for m in dir(cd) if "mess" in m or "append" in m]}
        for spk, msg in (("YOU", "first line here"),
                         ("YOU", "second line same speaker"),
                         ("SYNAPSE", "a reply from the other speaker"),
                         ("SYNAPSE", "and its own second line")):
            getattr(cd, api)(spk, msg)
        APP.processEvents()
        doc = cd.document()
        lay = doc.documentLayout()
        blocks = []
        b = doc.begin()
        prev = None
        while b.isValid():
            bf = b.blockFormat()
            r = lay.blockBoundingRect(b)
            entry = {
                "n": b.blockNumber(), "text": b.text()[:38],
                "role": bf.property(QtGui.QTextFormat.UserProperty),
                "topMargin": round(bf.topMargin(), 2),
                "bottomMargin": round(bf.bottomMargin(), 2),
                "y": round(r.y(), 2), "h": round(r.height(), 2),
                "x": round(r.x(), 2),
            }
            if prev is not None:
                entry["visual_gap_from_prev"] = round(r.y() - (prev["y"] + prev["h"]), 2)
            blocks.append(entry)
            prev = entry
            b = b.next()
        first_text_x = None
        b = doc.begin()
        while b.isValid():
            if b.text().strip():
                bl = b.layout()
                if bl.lineCount():
                    first_text_x = round(lay.blockBoundingRect(b).x() + bl.lineAt(0).x(), 2)
                break
            b = b.next()
        vp = cd.viewport()
        off = vp.mapTo(p, QtCore.QPoint(0, 0))
        cm = cd.contentsMargins()
        return {
            "api_used": api,
            "documentMargin": doc.documentMargin(),
            "doc_height": round(doc.size().height(), 2),
            "blocks": blocks,
            "first_text_block_x_in_doc": first_text_x,
            "viewport_x_in_panel": off.x(),
            "frameWidth": cd.frameWidth(),
            "contentsMargins_l": cm.left(),
            "body_x_in_panel": None if first_text_x is None
                               else round(off.x() + first_text_x, 2),
        }
    finally:
        p.close()

from synapse.panel import message_formatter as mf
OUT["M4_M5"] = {
    "_constants": {
        "_GROUP_MARGIN_Y": mf._GROUP_MARGIN_Y, "_MSG_MARGIN_Y": mf._MSG_MARGIN_Y,
        "ROLE_GAPS_group": rhythm.ROLE_GAPS["group"],
        "ROLE_GAPS_row": rhythm.ROLE_GAPS["row"],
        "gap_group": {d: t.gap(rhythm.ROLE_GAPS["group"], d)
                      for d in ("airy", "standard", "tight")},
        "gap_row": {d: t.gap(rhythm.ROLE_GAPS["row"], d)
                    for d in ("airy", "standard", "tight")},
    },
    "default_margin": transcript_probe("expert", None),
    "margin_0": transcript_probe("expert", 0),
    "margin_4": transcript_probe("expert", 4),
}

# ------------------------------------------------------------------ M6
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


def chroma(hexs):
    r, g, b = int(hexs[1:3], 16), int(hexs[3:5], 16), int(hexs[5:7], 16)
    d = max(r, g, b) - min(r, g, b)
    hue = int(colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[0] * 360)
    return {"hex": hexs, "rgb": [r, g, b], "chroma_maxmin": d,
            "chromatic_over_24": d > 24, "hue_deg": hue, "bucket": hue // 15}


TOA = t.TEXT_ON_ACCENT
m6 = {"TEXT_ON_ACCENT_value_used": TOA,
      "TEXT_ON_ACCENT_arith": chroma(TOA),
      "tokens": {n: chroma(getattr(t, n)) for n in
                 ("SIGNAL", "SIGNAL_DEEP", "WARM", "CONIFEROUS",
                  "HOUDINI_TAB_YELLOW", "TEXT_BRIGHT")
                 if isinstance(getattr(t, n, None), str)
                 and str(getattr(t, n)).startswith("#")}}
for prof in PROFILES:
    p = panel(prof)
    try:
        bk = hue_buckets(p)
        m6.setdefault("boot_buckets_live", {})[prof] = {
            "count": len(bk),
            "buckets": {str(k): {"n_colours": len(v), "sample": sorted(v)[:3]}
                        for k, v in sorted(bk.items())},
        }
    except Exception as e:
        m6.setdefault("boot_buckets_live", {})[prof] = {
            "error": "%s: %s" % (type(e).__name__, e)}
    finally:
        p.close()

NEUTRAL = "#1B1B1B"
t.TEXT_ON_ACCENT = NEUTRAL
try:
    import importlib
    importlib.reload(qss)
except Exception as e:
    m6["reload_note"] = str(e)
m6["neutral_stand_in_used"] = NEUTRAL
for prof in PROFILES:
    p = panel(prof)
    try:
        bk = hue_buckets(p)
        m6.setdefault("boot_buckets_TOA_neutral", {})[prof] = {
            "count": len(bk), "buckets": sorted(bk.keys())}
    except Exception as e:
        m6.setdefault("boot_buckets_TOA_neutral", {})[prof] = {
            "error": "%s: %s" % (type(e).__name__, e)}
    finally:
        p.close()
OUT["M6"] = m6

print("@@@JSON@@@")
print(json.dumps(OUT, indent=1, default=str))
