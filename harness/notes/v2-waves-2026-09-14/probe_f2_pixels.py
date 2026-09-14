"""F2 rail-clip probe, IN PIXELS, under real Qt. argv[1] = tree path."""
import sys, os
TREE = sys.argv[1].rstrip("/\\")
sys.path.insert(0, TREE + "/python")
try:
    from PySide6 import QtWidgets
except ImportError:
    from PySide2 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])  # FIRST
from synapse.panel.designsystem import fontload
fontload.load_application_fonts()
import synapse.panel.synapse_panel as SP
assert os.path.normcase(os.path.abspath(SP.__file__)).startswith(
    os.path.normcase(os.path.abspath(TREE))), ("WRONG TREE: %s" % SP.__file__)
print("### TREE      :", TREE)
print("### module    :", SP.__file__)
print("### HALTING   :", hasattr(SP, "_HALTING_PHRASE"))
print("### fits gate :", hasattr(SP.SynapsePanel, "_sentence_fits"))
NODE = "/obj/geo1/topnet1"
LONG = "/stage/shot_010/fx_smoke/topnet_render1"
def cands(node):
    return [("busy halt", "Emergency halt\u2026"),
            ("busy cancel", "Cancelling the cook on %s\u2026" % node),
            ("reentry halt", "Still Emergency halt\u2026"),
            ("reentry cancel", "Still Cancelling the cook on %s\u2026" % node),
            ("failed", "Not cancelled"),
            ("done ok", "ok"), ("done noop", "noop"), ("done none", "Done"),
            ("done unmappable", "unmappable"),
            ("done qualified", "unmappable: no cooking node matched %s" % node),
            ("busy cancel LONG", "Cancelling the cook on %s\u2026" % LONG)]
W, H = 340, 760
for profile in ("expert", "curious", "ml"):
    try:
        p = SP.SynapsePanel()
        p._recompose(profile); p.resize(W, H); p.show(); app.processEvents()
        p._set_face("direct"); app.processEvents()
        lbl = p._header_status; fm = lbl.fontMetrics()
        floor = lbl.minimumWidth()
        phrases = SP._state_phrases()
        calc = max(fm.horizontalAdvance(x) for x in phrases)
        widest = max(phrases, key=fm.horizontalAdvance)
        print("\n=== profile=%s panel=%dx%d ===" % (profile, W, H))
        print("font family=%r pixelSize=%s pointSizeF=%s" % (
            lbl.font().family(), lbl.font().pixelSize(), lbl.font().pointSizeF()))
        print("FLOOR minimumWidth = %d px | recomputed max advance = %d px | widest=%r (%d glyphs)"
              % (floor, calc, widest, len(widest)))
        print("LIVE label width = %d px | contentsRect = %d px" % (lbl.width(), lbl.contentsRect().width()))
        print("-- floor members --")
        for ph in sorted(set(phrases), key=fm.horizontalAdvance, reverse=True):
            print("   %5d px %2dg %r" % (fm.horizontalAdvance(ph), len(ph), ph))
        print("-- candidate sentences --")
        for lab, txt in cands(NODE):
            a = fm.horizontalAdvance(txt)
            print("   %5d px %2dg over_floor=%-5s %-16s %r" % (a, len(txt), a > floor, lab, txt))
        print("-- DRIVEN --")
        for lab, txt in cands(NODE):
            st = "working" if txt.startswith(("Still ", "Emergency", "Cancelling")) else "done"
            p._set_header(st, txt); app.processEvents()
            shown = lbl.text(); a = fm.horizontalAdvance(shown); cw = lbl.contentsRect().width()
            print("   %-16s shown=%-22r adv=%4d cw=%4d CLIPPED=%-5s tip=%r"
                  % (lab, shown[:22], a, cw, a > cw, (lbl.toolTip() or "")[:38]))
        print("-- real failure handler --")
        p._on_direct_tool_failed("tops_cancel_cook", "server unreachable")
        app.processEvents()
        print("   rail=%r tip=%r" % (lbl.text(), (lbl.toolTip() or "")[:60]))
        if hasattr(p, "_sentence_fits"):
            for s in ("Not cancelled", "Result ready", "Emergency halt\u2026", "Halting\u2026"):
                print("   _sentence_fits(%r) = %s (adv %d <= floor %d)"
                      % (s, p._sentence_fits(s), fm.horizontalAdvance(s), lbl.minimumWidth()))
        p.close(); p.deleteLater(); app.processEvents()
    except Exception as e:
        import traceback; print("!!! profile %s FAILED: %s" % (profile, e)); traceback.print_exc()
print("\n### done")
