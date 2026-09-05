"""TYPE lens census: every visible text widget of the landed panel, per face,
at a docked width, offscreen. Same construction path as measure_regions.py.
Writes only type_census_<profile>_<width>.json beside this file.
Run: SYNAPSE_PANEL_SETTINGS=settings_<p>.json QT_QPA_PLATFORM=offscreen hython type_census.py <profile> <width>
"""
import json, os, sys, collections
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for p in (ROOT, os.path.join(ROOT, "python")):
    if p not in sys.path:
        sys.path.insert(0, p)
profile, width = sys.argv[1], int(sys.argv[2])
from PySide6 import QtWidgets, QtCore, QtGui
from synapse.panel.designsystem import qss, fontload, tokens as t
from synapse.panel.synapse_panel import SynapsePanel
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
fonts = fontload.load_application_fonts()
host_font = app.font()
p = SynapsePanel()
p.setStyleSheet(qss.stylesheet())
p.resize(width, 760)
p.show(); app.processEvents()

def enum_int(v):
    return int(v.value) if hasattr(v, "value") else int(v)

def fdesc(w):
    f = w.font(); fi = QtGui.QFontInfo(f)
    return {"family": fi.family(), "px": fi.pixelSize(), "weight": fi.weight(),
            "bold": fi.bold(), "italic": fi.italic(),
            "spacing_type": enum_int(f.letterSpacingType()),
            "spacing": round(f.letterSpacing(), 2),
            "caps": enum_int(f.capitalization())}

TEXTBOX = (QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)

def wtext(w):
    if isinstance(w, QtWidgets.QLabel): return w.text()
    if isinstance(w, QtWidgets.QAbstractButton): return w.text()
    if isinstance(w, QtWidgets.QLineEdit): return w.text() or w.placeholderText()
    if isinstance(w, TEXTBOX): return w.placeholderText() or w.toPlainText()
    if isinstance(w, QtWidgets.QComboBox): return w.currentText()
    return ""

def census(face):
    rows, seen = [], set()
    for w in p.findChildren(QtWidgets.QWidget):
        if not w.isVisible(): continue
        txt = wtext(w)
        if not txt or not txt.strip(): continue
        key = (type(w).__name__, w.objectName(), txt[:40])
        if key in seen: continue
        seen.add(key)
        d = fdesc(w)
        fm = QtGui.QFontMetrics(w.font())
        adv = fm.horizontalAdvance(txt.split(chr(10))[0])
        if isinstance(w, TEXTBOX):
            df = w.document().defaultFont(); dfi = QtGui.QFontInfo(df)
            d.update({"doc_family": dfi.family(), "doc_px": dfi.pixelSize()})
        editor = isinstance(w, TEXTBOX + (QtWidgets.QLineEdit,))
        row = {"face": face, "cls": type(w).__name__, "id": w.objectName(),
               "role": w.property("role"), "rhythm_role": w.property("rhythm_role"),
               "text": txt[:28], "text_upper": txt.isupper()}
        row.update(d)
        row.update({"w": w.width(), "hint_w": w.sizeHint().width(),
                    "min_hint_w": w.minimumSizeHint().width(), "advance": adv,
                    "clipped": (not editor) and (w.sizeHint().width() > w.width())})
        rows.append(row)
    return rows

rows = []
p._set_face("direct"); p._converse_stack.setCurrentIndex(0); app.processEvents(); rows += census("direct_chat")
try:
    p._converse_stack.setCurrentIndex(1); app.processEvents(); rows += census("direct_hda")
except Exception as e:
    rows.append({"face": "direct_hda", "error": repr(e)})
p._converse_stack.setCurrentIndex(0)
try:
    p._set_face("work"); app.processEvents(); rows += census("work")
except Exception as e:
    rows.append({"face": "work", "error": repr(e)})
try:
    p._show_token_face(); app.processEvents(); rows += census("token")
except Exception as e:
    rows.append({"face": "token", "error": repr(e)})
p._set_face("direct"); app.processEvents()

good = [r for r in rows if "error" not in r]
def hist(key):
    return dict(collections.Counter(str(r[key]) for r in good).most_common())
def caps_kind(r):
    if r["caps"] == 1: return "QFont.AllUppercase"
    if r["text_upper"] and any(c.isalpha() for c in r["text"]): return "literal_upper"
    return "mixed"
chrome = [r for r in good if r["face"] == "direct_chat"]
summary = {
    "profile": profile, "density": p.property("density"), "width": width, "chrome_scale": p._chrome_scale,
    "host_font": {"family": QtGui.QFontInfo(host_font).family(), "px": QtGui.QFontInfo(host_font).pixelSize()},
    "fonts": fonts, "n_text_widgets": len(good),
    "px_hist": hist("px"), "family_hist": hist("family"), "weight_hist": hist("weight"),
    "spacing_hist": dict(collections.Counter("%s:%s" % (r["spacing_type"], r["spacing"]) for r in good).most_common()),
    "caps_hist": dict(collections.Counter(caps_kind(r) for r in good).most_common()),
    "italic": sum(1 for r in good if r["italic"]),
    "clipped": [{k: r[k] for k in ("face", "cls", "id", "text", "w", "hint_w", "px", "spacing")} for r in good if r["clipped"]],
    "wordmark": dict({"w": p._wordmark.width(), "hint_w": p._wordmark.sizeHint().width(),
                      "min_w": p._wordmark.minimumWidth(), "text": p._wordmark.text()}, **fdesc(p._wordmark)),
    "styles_registered": {fam: QtGui.QFontDatabase.styles(fam) for fam in ("Space Grotesk", "Space Mono")},
}

probe = {}
l1 = QtWidgets.QLabel("OPTIMIZE"); l2 = QtWidgets.QLabel("OPTIMIZE"); l2.setStyleSheet("letter-spacing: 5px;")
for l in (l1, l2):
    l.setFont(fontload.tracked_font("BODY", 11, mono=True)); l.ensurePolished()
probe["qss_letter_spacing"] = {"plain_hint_w": l1.sizeHint().width(), "qss_5px_hint_w": l2.sizeHint().width(),
                               "font_spacing_after_qss": l2.font().letterSpacing()}
doc1, doc2 = QtGui.QTextDocument(), QtGui.QTextDocument()
doc1.setHtml("<span style=\"font-size:11px;\">OPTIMIZE</span>")
doc2.setHtml("<span style=\"font-size:11px; letter-spacing:5px;\">OPTIMIZE</span>")
def frag_spacing(doc):
    out = []
    b = doc.begin()
    while b.isValid():
        it = b.begin()
        while not it.atEnd():
            out.append(it.fragment().charFormat().fontLetterSpacing()); it += 1
        b = b.next()
    return out
probe["html_letter_spacing"] = {"plain_ideal_w": doc1.idealWidth(), "html_5px_ideal_w": doc2.idealWidth(),
                                "fragment_spacing": frag_spacing(doc2)}
def adv(role, px, txt, mono=True, weight=400):
    return QtGui.QFontMetrics(fontload.tracked_font(role, px, mono=mono, weight=weight)).horizontalAdvance(txt)
probe["tracking_cost_px"] = {role: {txt: adv(role, 11, txt) for txt in ("OPTIMIZE", "BUILD HDA", "CURIOUS", "EXPLAIN")}
                             for role in ("BODY", "DATA", "SEND", "LABEL_SM", "LABEL", "WORDMARK", "EYEBROW", "BRAND")}
probe["verb_rail_demand"] = {"sum_verb_hints": sum(r["hint_w"] for r in chrome if r["id"] == "DsVerb"),
                             "sum_verb_widths": sum(r["w"] for r in chrome if r["id"] == "DsVerb"),
                             "content_w": width - 2 * t.GUTTER}
wres = {}
for name, fn in (("600_demibold", lambda f: f.setWeight(QtGui.QFont.Weight.DemiBold)),
                 ("setBold", lambda f: f.setBold(True)),
                 ("500_medium", lambda f: f.setWeight(QtGui.QFont.Weight.Medium)),
                 ("400", lambda f: f.setWeight(QtGui.QFont.Weight.Normal))):
    f = QtGui.QFont(); fontload.apply_family(f); f.setPixelSize(14); fn(f); fi = QtGui.QFontInfo(f)
    wres[name] = {"requested": f.weight(), "resolved": fi.weight(), "style": fi.styleName(), "family": fi.family()}
probe["weight_resolution_space_grotesk"] = wres
summary["probes"] = probe
out = {"summary": summary, "rows": rows}
with open(os.path.join(HERE, "type_census_%s_%d.json" % (profile, width)), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
sys.stdout.write(json.dumps(summary, default=str) + chr(10))
p.close(); app.processEvents()
