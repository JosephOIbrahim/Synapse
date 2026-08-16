"""W6-FLOWFIX red->green probe for the two rig-measured reds (journey J4).

Self-contained: it does NOT import W6-FLOWRIG's probe_flow.py. It reproduces
FLOWRIG's EXACT J4.3 and J4.4 predicate logic (harness/probes/flow/probe_flow.py
:820-874 on wave6/flowrig, product 9a78ad30) against THIS worktree's copy of
``synapse.panel.compositor`` so the fix is proven first-hand with the same
measurement the rig used.

Both predicates are headless by construction:
  * J4.3 - source-grep for the ``from qtpy import QtWidgets`` early-return
    (Defect A) and the ``findChildren(...))\\n break`` premature break
    (Defect B); PASS iff neither is present. A bonus duck-typed tree walk
    then proves ``_repolish_tree`` actually reaches every descendant.
  * J4.4 - source-grep for a maxHeight restore branch, plus a micro-probe on a
    fake recording widget: collapse then un-collapse; two-way iff the second
    apply restores maxHeight off 0.

No real Qt and no hython are required - exactly like the rig's own checks.
Run:  python harness/probes/flow/probe_j4_flowfix.py
Exit code 0 iff both predicates hold their EXPECTED verdict for the mode
($FLOWFIX_MODE = "red" before the fix, "green" after; default "green").
"""

import json
import os
import re
import sys
from unittest.mock import MagicMock

# Import THIS worktree's synapse.panel.compositor, whatever cwd we run from.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PYROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "python"))
if _PYROOT not in sys.path:
    sys.path.insert(0, _PYROOT)

from synapse.panel import compositor  # noqa: E402


def _mod_src():
    """Source text of the compositor module actually imported (this worktree)."""
    with open(compositor.__file__, "r", encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------------------------------- #
# J4.3 - _repolish_tree reaches every descendant via the panel binding, no qtpy
# (verbatim predicate logic from FLOWRIG probe_flow.py:820-833)
# --------------------------------------------------------------------------- #
def j4_3():
    src = _mod_src()
    body = src[src.index("def _repolish_tree"):src.index("def compose")]
    has_qtpy = ("from qtpy import QtWidgets" in body)
    premature_break = bool(re.search(r"findChildren\([^\n]*\)\)\s*\n\s*break", body))
    try:
        import qtpy  # noqa: F401
        qtpy_present = True
    except Exception:                                            # noqa: BLE001
        qtpy_present = False
    reaches_all = (not has_qtpy) and (not premature_break)

    # Bonus, beyond the rig's source-pin: prove the walk actually reaches every
    # descendant on a duck-typed tree (no real Qt). RED early-returns -> reach 0.
    reached = _live_reach_count()

    verdict = "PASS" if reaches_all else "FAIL"
    return verdict, {
        "imports_qtpy_defectA": has_qtpy,
        "premature_break_defectB": premature_break,
        "qtpy_importable_in_seat": qtpy_present,
        "dominant_defect": ("qtpy-early-return (no repolish at all)"
                            if (has_qtpy and not qtpy_present)
                            else ("premature break (root-only repolish)"
                                  if premature_break else "none")),
        "live_tree_reached": reached["reached"],
        "live_tree_total": reached["total"],
        "reaches_every_descendant": reached["reached"] == reached["total"],
    }


class _FakeStyle(object):
    def unpolish(self, w):
        w._polished = w.__dict__.get("_polished", 0)

    def polish(self, w):
        w._polished = w.__dict__.get("_polished", 0) + 1


class _FakeW(object):
    """Minimal duck-typed QWidget: style()/update()/children()."""
    _style = _FakeStyle()

    def __init__(self, name, kids=None):
        self.name = name
        self._kids = kids or []
        self._polished = 0
        self._updated = 0

    def style(self):
        return self._style

    def update(self):
        self._updated += 1

    def children(self):
        return list(self._kids)


def _live_reach_count():
    """Build root+2*(1 child) = 5 widgets, count how many _repolish_tree touches."""
    leaf_a, leaf_b = _FakeW("leaf_a"), _FakeW("leaf_b")
    mid_a = _FakeW("mid_a", [leaf_a])
    mid_b = _FakeW("mid_b", [leaf_b])
    root = _FakeW("root", [mid_a, mid_b])
    all_w = [root, mid_a, mid_b, leaf_a, leaf_b]
    ret = compositor._repolish_tree(root)
    reached = sum(1 for w in all_w if w._polished > 0)
    return {"reached": reached, "total": len(all_w), "return_value": ret}


# --------------------------------------------------------------------------- #
# J4.4 - _apply_spec collapsed/visible is two-way (switch-back restores)
# (verbatim predicate logic from FLOWRIG probe_flow.py:844-866)
# --------------------------------------------------------------------------- #
def j4_4():
    src = _mod_src()
    body = src[src.index("def _apply_spec"):src.index("def _apply_widget_stretch")]
    collapses = "widget.setMaximumHeight(0)" in body
    restores = bool(re.search(r"setMaximumHeight\((?!0\))", body)) or "QWIDGETSIZE_MAX" in body

    class _W(object):
        def __init__(self):
            self.max_h = None
            self.props = {}
            self.visible = True

        def setVisible(self, v):
            self.visible = v

        def setMaximumHeight(self, h):
            self.max_h = h

        def setProperty(self, k, v):
            self.props[k] = v

        def style(self):
            return MagicMock()

    w = _W()
    compositor._apply_spec(w, {"visible": True, "collapsed": True, "prominence": "standard"}, "probe")
    after_collapse = w.max_h
    compositor._apply_spec(w, {"visible": True, "collapsed": False, "prominence": "standard"}, "probe")
    after_uncollapse = w.max_h
    one_way = (after_collapse == 0 and after_uncollapse == 0)
    two_way = restores and not one_way

    verdict = "PASS" if two_way else "FAIL"
    return verdict, {
        "collapse_sets_maxheight0": collapses,
        "has_restore_branch": restores,
        "probe_maxh_after_collapse": after_collapse,
        "probe_maxh_after_uncollapse": after_uncollapse,
        "one_way_confirmed": one_way,
    }


def main():
    mode = os.environ.get("FLOWFIX_MODE", "green").lower()
    expected = "FAIL" if mode == "red" else "PASS"
    results = {}
    for sid, fn in (("J4.3", j4_3), ("J4.4", j4_4)):
        verdict, measure = fn()
        results[sid] = {"verdict": verdict, "measure": measure}
    ok = all(results[s]["verdict"] == expected for s in results)
    out = {
        "leg": "W6-FLOWFIX",
        "mode": mode,
        "expected_each": expected,
        "compositor_source": compositor.__file__,
        "results": results,
        "all_as_expected": ok,
    }
    print(json.dumps(out, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
