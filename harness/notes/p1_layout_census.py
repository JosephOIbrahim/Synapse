"""P1 LAYOUT CENSUS — measure the panel surface BEFORE changing it (R104).

R104 exists because a brief undercounted its target by an order of magnitude,
having measured with a grep that answered a narrower question than the claim it
supported. This instrument answers the question P1 actually asks:

  1. At the SHIPPED dock width, which rail children do not fit?
  2. At the SHIPPED dock width, is the done-state VERDICT — the study's hero
     line — fully visible, or is it clipped?
  3. How many artist-reachable doors lead to the result surface?
  4. Which of the result surface's setters have a product caller?

WHY THE READER IS CALIBRATED FIRST (R60)
----------------------------------------
A layout reader that always reports "fits" is indistinguishable from a correct
one on a panel that happens to fit. So before any measurement is taken against
the tree, ``_selftest`` points the SAME two readers at synthetic widgets whose
answer is known in both directions:

  overflow reader  -> a box KNOWN to overflow must report overflow
                   -> a box KNOWN to fit must report fit
  clip reader      -> a label KNOWN to be clipped must report clipped
                   -> a label KNOWN to be whole must report whole

If a control fails the census REFUSES TO REPORT (Law 1 / Law 3): a number from a
blind reader is worse than no number, because it will be cited.

Run (repo root, shipping interpreter):

    QT_QPA_PLATFORM=offscreen SYNAPSE_REDUCED_MOTION=1 \
      hython3.13 harness/notes/p1_layout_census.py --out harness/notes/p1_layout_census.json

Exit 0 = census written. Exit 1 = a control failed; nothing was measured.
"""

import argparse
import ast
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")

for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PySide6 import QtWidgets, QtGui  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402


# ---------------------------------------------------------------------------
# READER 1 — does a laid-out row's content exceed the width it was given?
# ---------------------------------------------------------------------------

def row_overflow(container, width):
    """Lay ``container`` out at ``width`` and report per-child geometry.

    Returns ``{"width": w, "content_min": px, "overflow": px, "children": [...]}``.
    ``overflow`` is how many pixels the row's own minimum demands beyond what it
    was given — the honest measure of "this row does not fit", independent of
    whether Qt chose to clip, squeeze or elide any particular child.
    """
    container.setFixedWidth(width)
    container.adjustSize()
    lay = container.layout()
    content_min = lay.minimumSize().width() if lay is not None else container.minimumSizeHint().width()
    kids = []
    if lay is not None:
        for i in range(lay.count()):
            item = lay.itemAt(i)
            w = item.widget()
            if w is None:
                continue
            hint = w.sizeHint().width()
            got = w.width()
            kids.append({
                "name": w.objectName() or type(w).__name__,
                "text": (w.text()[:28] if hasattr(w, "text") else ""),
                "hint_w": hint,
                "actual_w": got,
                "starved_px": max(0, hint - got),
                "visible": w.isVisible(),
            })
    return {
        "width": width,
        "content_min": content_min,
        "overflow": max(0, content_min - width),
        "children": kids,
    }


# ---------------------------------------------------------------------------
# READER 2 — is a label's full text actually painted, or clipped?
# ---------------------------------------------------------------------------

def label_clip(lbl, width):
    """Report whether ``lbl`` can paint its whole text inside ``width``.

    Uses the label's OWN font metrics against its OWN wrap mode, so it measures
    what the artist sees rather than what the widget claims to want. A label
    whose required height exceeds the height it was allotted is CLIPPED even
    though ``text()`` still returns the full string — which is exactly the
    failure a text-only assertion cannot see.
    """
    lbl.setFixedWidth(width)
    lbl.adjustSize()
    fm = QtGui.QFontMetrics(lbl.font())
    avail = max(1, width - (lbl.contentsMargins().left() + lbl.contentsMargins().right()))
    flags = int(Qt.TextFlag.TextWordWrap) if lbl.wordWrap() else 0
    need = fm.boundingRect(0, 0, avail, 10_000, flags, lbl.text())
    return {
        "text": lbl.text(),
        "width": width,
        "need_w": need.width(),
        "need_h": need.height(),
        "actual_h": lbl.height(),
        "clipped": bool(need.height() > lbl.height() or
                        (not lbl.wordWrap() and need.width() > avail)),
    }


# ---------------------------------------------------------------------------
# CONTROLS — both readers, both directions, KNOWN answers (R60)
# ---------------------------------------------------------------------------

def _selftest():
    """Exercise both readers against synthetic widgets with known answers.

    Returns ``(ok, [lines])``. A reader that cannot tell overflow from fit, or
    clipped from whole, invalidates every number below it.
    """
    out = []
    ok = True

    # --- overflow reader, positive control: three 200px boxes in 100px ---
    box = QtWidgets.QWidget()
    lay = QtWidgets.QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    for _ in range(3):
        k = QtWidgets.QLabel("x")
        k.setMinimumWidth(200)
        lay.addWidget(k)
    pos = row_overflow(box, 100)
    hit = pos["overflow"] > 0
    ok &= hit
    out.append("  overflow reader  POSITIVE (600px of boxes in 100px) -> overflow=%d  %s"
               % (pos["overflow"], "OK" if hit else "BLIND"))

    # --- overflow reader, negative control: three 10px boxes in 400px ---
    box2 = QtWidgets.QWidget()
    lay2 = QtWidgets.QHBoxLayout(box2)
    lay2.setContentsMargins(0, 0, 0, 0)
    lay2.setSpacing(0)
    for _ in range(3):
        k = QtWidgets.QLabel("x")
        k.setFixedWidth(10)
        lay2.addWidget(k)
    neg = row_overflow(box2, 400)
    miss = neg["overflow"] == 0
    ok &= miss
    out.append("  overflow reader  NEGATIVE (30px of boxes in 400px)  -> overflow=%d  %s"
               % (neg["overflow"], "OK" if miss else "FALSE POSITIVE"))

    # --- clip reader, positive control: a long unwrapped line in 40px ---
    l1 = QtWidgets.QLabel("a sentence far too long to fit in forty pixels")
    l1.setWordWrap(False)
    c1 = label_clip(l1, 40)
    ok &= c1["clipped"]
    out.append("  clip reader      POSITIVE (long line in 40px)       -> clipped=%s  %s"
               % (c1["clipped"], "OK" if c1["clipped"] else "BLIND"))

    # --- clip reader, negative control: one short word in 400px ---
    l2 = QtWidgets.QLabel("ok")
    l2.setWordWrap(False)
    c2 = label_clip(l2, 400)
    ok &= not c2["clipped"]
    out.append("  clip reader      NEGATIVE (short word in 400px)     -> clipped=%s  %s"
               % (c2["clipped"], "OK" if not c2["clipped"] else "FALSE POSITIVE"))

    return bool(ok), out


# ---------------------------------------------------------------------------
# READER 3 — static: how many artist-reachable doors reach the Work face?
# ---------------------------------------------------------------------------

def result_surface_doors():
    """Every product call to ``_set_face("work")``, with its enclosing function.

    A door is artist-reachable only if the enclosing function is driven by an
    artist action or by consent. The census reports the callers; the reading is
    made in the receipt, not here.
    """
    src_path = os.path.join(_ROOT, "python", "synapse", "panel", "synapse_panel.py")
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src, filename=src_path)
    doors = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if not (isinstance(f, ast.Attribute) and f.attr == "_set_face"):
                continue
            if not node.args:
                continue
            arg = node.args[0]
            val = arg.value if isinstance(arg, ast.Constant) else None
            if val == "work":
                doors.append({"in_function": fn.name, "line": node.lineno})
    return doors


# ---------------------------------------------------------------------------
# READER 4 — static: which FaceReview setters have a product caller?
# ---------------------------------------------------------------------------

def result_setter_callers():
    """For every public setter on FaceReview, count callers OUTSIDE the class.

    A setter with zero external callers is a surface the product cannot fill —
    the widget exists and nothing ever puts anything in it.
    """
    fr_path = os.path.join(_ROOT, "python", "synapse", "panel", "face_review.py")
    with open(fr_path, encoding="utf-8") as fh:
        fr_src = fh.read()
    fr_tree = ast.parse(fr_src, filename=fr_path)
    setters = []
    for cls in [n for n in ast.walk(fr_tree) if isinstance(n, ast.ClassDef)]:
        if cls.name != "FaceReview":
            continue
        for fn in cls.body:
            if isinstance(fn, ast.FunctionDef) and not fn.name.startswith("_"):
                setters.append(fn.name)

    panel_dir = os.path.join(_ROOT, "python", "synapse", "panel")
    counts = {s: [] for s in setters}
    for root, _dirs, files in os.walk(panel_dir):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            path = os.path.join(root, fname)
            rel = os.path.relpath(path, _ROOT).replace("\\", "/")
            with open(path, encoding="utf-8") as fh:
                try:
                    tree = ast.parse(fh.read(), filename=path)
                except SyntaxError:
                    continue
            in_face_review = fname == "face_review.py"
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                f = node.func
                if isinstance(f, ast.Attribute) and f.attr in counts:
                    # a call on `self` inside FaceReview is internal plumbing
                    if in_face_review and isinstance(f.value, ast.Name) and f.value.id == "self":
                        continue
                    counts[f.attr].append("%s:%d" % (rel, node.lineno))
    return counts


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(_HERE, "p1_layout_census.json"))
    args = ap.parse_args()

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    print("P1 LAYOUT CENSUS")
    print("-- reader controls (R60) " + "-" * 44)
    ok, lines = _selftest()
    for ln in lines:
        print(ln)
    if not ok:
        print("\nREFUSING TO REPORT: a reader control failed. The control is the finding.")
        return 1

    from synapse.panel.designsystem import tokens as t
    from synapse.panel.synapse_panel import SynapsePanel
    from synapse.panel.face_review import FaceReview

    dock_w = t.PANEL_PREF_WIDTH
    print("\n-- measured at the SHIPPED dock width: %dpx " % dock_w + "-" * 24)

    panel = SynapsePanel()
    panel.setFixedWidth(dock_w)
    panel.adjustSize()

    # rail line 1 — the identity + state + controls row
    rail = panel._mark.parent()
    rail_top = row_overflow(rail, dock_w)
    # the layout of `rail` is the outer VBox; measure the inner HBox children
    inner = rail.layout().itemAt(0).layout() if rail.layout() is not None else None
    rail_children = []
    if inner is not None:
        for i in range(inner.count()):
            it = inner.itemAt(i)
            w = it.widget()
            if w is None:
                continue
            rail_children.append({
                "name": w.objectName() or type(w).__name__,
                "text": (w.text()[:28] if hasattr(w, "text") else ""),
                "hint_w": w.sizeHint().width(),
                "actual_w": w.width(),
                "starved_px": max(0, w.sizeHint().width() - w.width()),
                "visible": w.isVisible(),
            })
        rail_top["children"] = rail_children
        rail_top["content_min"] = inner.minimumSize().width()
        rail_top["overflow"] = max(0, rail_top["content_min"] - dock_w)

    print("  rail row 1: needs %dpx in %dpx -> overflow %dpx"
          % (rail_top["content_min"], dock_w, rail_top["overflow"]))
    for k in rail_top["children"]:
        if k["starved_px"]:
            print("     starved: %-14s %-22r wants %d got %d (-%d)"
                  % (k["name"], k["text"], k["hint_w"], k["actual_w"], k["starved_px"]))

    # the verdict — the study's hero line — at the same width
    fr = FaceReview()
    fr.set_verdict("Dark_Glass bound to /materials/glass and the frame rendered clean.")
    margins = fr.layout().contentsMargins()
    verdict_w = dock_w - margins.left() - margins.right()
    verdict = label_clip(fr._verdict, verdict_w)
    print("  verdict at %dpx: need %dpx tall, got %dpx -> clipped=%s"
          % (verdict_w, verdict["need_h"], verdict["actual_h"], verdict["clipped"]))

    doors = result_surface_doors()
    print("  doors to the result surface: %d" % len(doors))
    for d in doors:
        print("     %s (line %d)" % (d["in_function"], d["line"]))

    callers = result_setter_callers()
    print("  FaceReview setters and their product callers:")
    for name in sorted(callers):
        sites = callers[name]
        print("     %-22s %d  %s" % (name, len(sites), ", ".join(sites) or "NONE"))

    payload = {
        "producer": "harness/notes/p1_layout_census.py",
        "dock_width": dock_w,
        "controls_passed": True,
        "rail_row1": rail_top,
        "verdict": verdict,
        "result_surface_doors": doors,
        "result_setter_callers": callers,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print("\nwrote %s" % args.out)
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
