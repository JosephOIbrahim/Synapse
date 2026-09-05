"""bc-wave evidence grabs: the three surfaces Joe's ruling changed, per profile.

  panel_direct_chat.png      the CHAT face at rest (340x760, first-run composer)
  slash_palette.png          the '/' palette as the panel opens it (ToolPalette,
                             grown toward the opener until six rungs show)
  consent_review_inline.png  a REVIEW-level consent card inline on CHAT
                             (BC-6b: no face switch; '<- REVERT' is the verb)

Same construction path as harness/notes/panel_shot.py (SynapsePanel +
qss.stylesheet(), resize, show, processEvents). Read-only on the product;
writes only PNGs under --out.

Run:  SYNAPSE_PANEL_SETTINGS=<json with {"profile": "<p>"}> QT_QPA_PLATFORM=offscreen
      hython harness/notes/panel_shot_bc.py --out design/rhythm_pd/after_bc/<p>
"""
import argparse
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.modules.setdefault("hou", types.ModuleType("hou"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = args.out if os.path.isabs(args.out) else os.path.join(_ROOT, args.out)
    os.makedirs(out, exist_ok=True)

    from PySide6 import QtWidgets
    from synapse.panel.designsystem import qss, fontload
    from synapse.panel.synapse_panel import SynapsePanel
    from synapse.panel.tool_palette import ToolPalette

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    fontload.load_application_fonts()
    p = SynapsePanel()
    p.setStyleSheet(qss.stylesheet())
    p.resize(340, 760)
    p.show()
    app.processEvents()
    p._set_face("direct")
    p._converse_stack.setCurrentIndex(0)
    app.processEvents()
    written = []

    def grab(widget, name):
        pix = widget.grab()
        path = os.path.join(out, name)
        assert not pix.isNull() and pix.save(path, "PNG"), name
        written.append((name, pix.width(), pix.height()))

    grab(p, "panel_direct_chat.png")

    pal = ToolPalette(p, scale=getattr(p, "_chrome_scale", 1.0))
    p._position_popup(pal, getattr(p, "_input", None))
    pal.show()
    app.processEvents()
    grab(pal, "slash_palette.png")
    pal.close()
    app.processEvents()

    prop = {"proposal_id": "shot-review", "level": "review", "operation": "delete_node",
            "agent_id": "HANDS", "description": "Remove /obj/geo1/scatter1 (unused)"}
    p._gate._add_proposal_card(prop)
    p._on_gate_raised(prop)
    app.processEvents()
    grab(p, "consent_review_inline.png")
    p.close()
    for name, w, h in written:
        print("  %-28s %dx%d" % (name, w, h))
    print("profile=%s density=%s face=%d" % (
        getattr(p, "_layout_profile", None), p.property("density"), p._faces.currentIndex()))


if __name__ == "__main__":
    main()
