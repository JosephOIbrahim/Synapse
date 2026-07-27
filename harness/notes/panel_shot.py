"""H4 SCREENSHOT HARNESS — render every panel view offscreen to PNG.

The point is a BEFORE/AFTER diff across a token change, so the two runs must go
through the IDENTICAL code path. Run it once on the untouched tree, once after,
into two sibling directories, and diff.

Run (from the repo root, under the panel interpreter):

    QT_QPA_PLATFORM=offscreen SYNAPSE_REDUCED_MOTION=1 \
      hython3.13 harness/notes/panel_shot.py --out design/repair_h4/before

Exit 0 = every view in the manifest rendered. Exit 1 = at least one view failed.

HONESTY (Law 3): a view that cannot be constructed is recorded as FAILED with its
traceback in the sidecar manifest. It is never silently skipped and a placeholder
image is never written -- a missing PNG means "this did not render", which is the
only thing a reader may conclude from its absence.

DETERMINISM: reduced motion is forced on, every widget is given a fixed size, and
the only randomness in the panel (BucketGrid's per-cell edge inset) is a stable
integer hash of the cell index, so two runs of the same tree are byte-comparable.
"""

import argparse
import json
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

# Offscreen + reduced motion must be set BEFORE Qt or the panel is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")

for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# --------------------------------------------------------------------------
# The manifest. Each entry builds ONE view and returns a QWidget to grab.
# Panel width is the shipped PANEL_PREF_WIDTH so the shots match a real dock.
# --------------------------------------------------------------------------

def _panel(face=None, converse_page=None):
    """The whole SynapsePanel, optionally driven to a face / inner page."""
    from synapse.panel.synapse_panel import SynapsePanel
    p = SynapsePanel()
    if face is not None:
        p._set_face(face)
    if converse_page is not None:
        p._converse_stack.setCurrentIndex(converse_page)
    return p


def _gate_widget():
    """The consent gate carrying one proposal of each level it renders.

    Driven through the PUBLIC bridge entry point (``handle_ws_proposal``), not a
    private builder, so the shot exercises the same path a live proposal takes.
    Levels are lower-case because that is what ``_LEVEL_COLORS`` keys on
    (gate_widget.py:34) -- upper-case silently falls through to the default
    accent and the shot would show four identical cards.
    """
    from synapse.panel.gate_widget import GateWidget
    w = GateWidget()
    for i, (level, op) in enumerate((
        ("inform", "create_node"),
        ("review", "delete_node"),
        ("approve", "submit_render"),
        ("critical", "execute_python"),
    )):
        w.handle_ws_proposal({
            "proposal_id": "p%d" % i,
            "level": level,
            "operation": op,
            "summary": "%s :: %s" % (level.title(), op),
        })
    return w


def _face_review():
    """The Review face driven into its ALL-CLEAR state.

    Its resting state paints no status green at all, so a shot of the default
    would be blind to the OK_SOFT -> CONIFEROUS swap. Flags are set to the
    passing statuses precisely so the green under audit is on screen.
    """
    from synapse.panel.face_review import FaceReview
    w = FaceReview()
    w.set_verdict("looks right")
    w.set_flags([
        ("ok", "undo group closed"),
        ("pass", "composition valid"),
        ("warn", "1 cook warning"),
        ("fail", "no render receipt"),
    ])
    return w


def _face_work():
    from synapse.panel.face_work import FaceWork
    return FaceWork()


def _health():
    from synapse.panel.health_infographic import HealthInfographic
    return HealthInfographic()


def _integrity():
    """The integrity readout in its genuine ALL-CLEAR state — the ONLY state
    that is allowed to paint green (integrity_readout.py:41). Same reason as
    _face_review: the default paints no green, so it could not see the swap."""
    from synapse.panel.integrity_readout import IntegrityReadout
    w = IntegrityReadout()
    # Keys per integrity_readout._fidelity_color / _fidelity_text: has_data must
    # be truthy or the readout correctly refuses to go green (SLATE no-data).
    w.set_integrity({
        "has_data": True,
        "fidelity": 1.0,
        "verified": 12,
        "violations": 0,
        "should_warn": False,
    })
    return w


def _tool_palette():
    from synapse.panel.tool_palette import ToolPalette
    return ToolPalette()


def _command_palette():
    from synapse.panel.command_palette import CommandPaletteWidget
    return CommandPaletteWidget()


def _context_bar():
    from synapse.panel.context_bar import ContextChips
    w = ContextChips()
    w.set_connected(True)
    w.set_network_path("/stage/karma_render")
    w.set_frame(1001)
    w.set_selection_count(3)
    w.set_project_context("SHOT_010", "charmeleon")
    return w


def _hda(view):
    from synapse.panel import hda_views
    return getattr(hda_views, view)()


def _chat_with(html_fn):
    """The chat transcript carrying agent-authored HTML.

    This is the view the collision is VISIBLE in: recipe_book / apex_recipes
    author their headings from the bridge's accent while the transcript chrome
    around them renders the design system's, so one surface shows two different
    accent blues at once. A shot of the chat in its empty resting state cannot
    see that -- the transcript has to have content in it.
    """
    from synapse.panel.chat_display import ChatDisplay
    w = ChatDisplay()
    w.append_user_message("show me the recipes")
    w.append_synapse_message(html_fn())
    return w


def _chat_recipe_book():
    from synapse.panel.recipe_book import format_categories_html
    return _chat_with(format_categories_html)


def _chat_apex_recipes():
    from synapse.panel.apex_recipes import format_apex_recipes_html
    return _chat_with(format_apex_recipes_html)


VIEWS = [
    # name                      builder                              (w, h)
    ("panel_direct_chat", lambda: _panel("direct", 0), (340, 760)),
    ("panel_direct_hda", lambda: _panel("direct", 1), (340, 760)),
    ("panel_work", lambda: _panel("work"), (340, 760)),
    ("gate_widget", _gate_widget, (340, 520)),
    ("face_review", _face_review, (340, 520)),
    ("face_work", _face_work, (340, 420)),
    ("health_infographic", _health, (340, 360)),
    ("integrity_readout", _integrity, (340, 120)),
    ("tool_palette", _tool_palette, (340, 520)),
    # --- the surfaces the accent collision is actually VISIBLE on -----------
    ("command_palette", _command_palette, (340, 520)),
    ("context_bar", _context_bar, (340, 60)),
    ("hda_describe", lambda: _hda("DescribeView"), (340, 420)),
    ("hda_building", lambda: _hda("BuildingView"), (340, 420)),
    ("hda_result", lambda: _hda("ResultView"), (340, 420)),
    ("chat_recipe_book", _chat_recipe_book, (340, 520)),
    ("chat_apex_recipes", _chat_apex_recipes, (340, 620)),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output directory for the PNGs")
    args = ap.parse_args()

    out = args.out if os.path.isabs(args.out) else os.path.join(_ROOT, args.out)
    os.makedirs(out, exist_ok=True)

    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    results = []
    failed = 0
    for name, build, (w, h) in VIEWS:
        entry = {"view": name, "png": name + ".png", "size": [w, h]}
        widget = None
        try:
            widget = build()
            widget.resize(w, h)
            widget.show()
            app.processEvents()
            pix = widget.grab()
            if pix.isNull():
                raise RuntimeError("QWidget.grab() returned a null pixmap")
            path = os.path.join(out, name + ".png")
            if not pix.save(path, "PNG"):
                raise RuntimeError("QPixmap.save returned False for %s" % path)
            entry["status"] = "ok"
            entry["bytes"] = os.path.getsize(path)
            entry["pixels"] = [pix.width(), pix.height()]
        except Exception:
            failed += 1
            entry["status"] = "failed"
            entry["traceback"] = traceback.format_exc()
            # No placeholder image. An absent PNG means it did not render.
        finally:
            if widget is not None:
                try:
                    widget.close()
                    widget.deleteLater()
                except Exception:
                    pass
            app.processEvents()
        results.append(entry)

    manifest = {
        "schema": "panel_shot/v1",
        "out": os.path.relpath(out, _ROOT).replace("\\", "/"),
        "platform": app.platformName(),
        "python": sys.version.split()[0],
        "reduced_motion": os.environ.get("SYNAPSE_REDUCED_MOTION"),
        "views_total": len(VIEWS),
        "views_ok": len(VIEWS) - failed,
        "views_failed": failed,
        "results": results,
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    sys.stdout.write("panel_shot -> %s\n" % out)
    for r in results:
        sys.stdout.write("  %-22s %s%s\n" % (
            r["view"], r["status"],
            "" if r["status"] == "ok" else "  (see manifest.json)",
        ))
    sys.stdout.write("%d/%d views rendered\n" % (manifest["views_ok"], len(VIEWS)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
