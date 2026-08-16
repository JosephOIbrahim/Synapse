"""W6-FLOWFIX — pin the two rig-measured reds of journey J4 green (regression fence).

Both fixes live in ``synapse.panel.compositor`` and were measured red→green
first-hand by the W6-FLOWRIG rig (harness/probes/flow/probe_flow.py:820-874;
flow_results.json J4.3/J4.4). These tests reproduce the rig's EXACT predicate
logic so the fix cannot silently regress:

  * J4.3 ``_repolish_tree`` — no ``qtpy`` import (Defect A: the seat has no
    qtpy, so the old import early-returned and density reached no child) and no
    ``findChildren(...))\\n break`` (Defect B: root-only repolish). Plus a
    duck-typed tree walk proving it now reaches EVERY descendant.
  * J4.4 ``_apply_spec`` — collapse is TWO-WAY: a spec with ``collapsed=False``
    restores maxHeight off 0 (the old code set 0 one-way and never restored, so
    a folded readout stayed collapsed through the next mode switch).

``compositor`` imports no Qt, so this runs under stock CPython in CI — no
PySide, no hython. The full live rig is the gold-standard proof; this is the
cheap always-on fence.
"""

import os
import re
import sys
from unittest.mock import MagicMock

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from synapse.panel import compositor  # noqa: E402


def _compositor_src():
    with open(compositor.__file__, "r", encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------------------------------- #
# J4.3 — _repolish_tree reaches every descendant, no qtpy                       #
# --------------------------------------------------------------------------- #
def test_j43_repolish_tree_has_no_qtpy_import():
    """Defect A fence: the seat has no qtpy; a qtpy import would early-return."""
    src = _compositor_src()
    body = src[src.index("def _repolish_tree"):src.index("def compose")]
    assert "from qtpy import QtWidgets" not in body, (
        "J4.3 Defect A regressed: _repolish_tree imports qtpy again — the "
        "Houdini seat has no qtpy, so this makes the whole function a no-op."
    )


def test_j43_repolish_tree_has_no_premature_break():
    """Defect B fence: no findChildren(...)) immediately followed by break."""
    src = _compositor_src()
    body = src[src.index("def _repolish_tree"):src.index("def compose")]
    assert not re.search(r"findChildren\([^\n]*\)\)\s*\n\s*break", body), (
        "J4.3 Defect B regressed: a break right after the descendant extend "
        "repolishes only the root."
    )


class _FakeStyle:
    def unpolish(self, w):
        w.polished = getattr(w, "polished", 0)

    def polish(self, w):
        w.polished = getattr(w, "polished", 0) + 1


class _FakeW:
    """Duck-typed QWidget: style()/update()/children() — no real Qt."""
    _style = _FakeStyle()

    def __init__(self, name, kids=None):
        self.name = name
        self._kids = kids or []
        self.polished = 0
        self.updated = 0

    def style(self):
        return self._style

    def update(self):
        self.updated += 1

    def children(self):
        return list(self._kids)


def test_j43_repolish_reaches_every_descendant():
    """The live half: density must reach root AND every descendant widget."""
    leaf_a, leaf_b = _FakeW("leaf_a"), _FakeW("leaf_b")
    mid_a, mid_b = _FakeW("mid_a", [leaf_a]), _FakeW("mid_b", [leaf_b])
    root = _FakeW("root", [mid_a, mid_b])
    every = [root, mid_a, mid_b, leaf_a, leaf_b]

    count = compositor._repolish_tree(root)

    assert count == len(every), "repolish must touch every widget, not just root"
    assert all(w.polished > 0 for w in every), "a descendant was left unstyled"


# --------------------------------------------------------------------------- #
# J4.4 — _apply_spec collapsed is two-way (switch-back restores)               #
# --------------------------------------------------------------------------- #
def test_j44_apply_spec_source_has_restore_branch():
    """Source-pin: a maxHeight restore (non-zero / QWIDGETSIZE_MAX) exists."""
    src = _compositor_src()
    body = src[src.index("def _apply_spec"):src.index("def _apply_widget_stretch")]
    restores = bool(re.search(r"setMaximumHeight\((?!0\))", body)) or "QWIDGETSIZE_MAX" in body
    assert restores, (
        "J4.4 regressed: _apply_spec has no maxHeight restore branch — collapse "
        "is one-way again and folded readouts never re-expand on switch-back."
    )


class _RecW:
    """Recording widget matching the rig's micro-probe fake (_W)."""
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


def test_j44_collapse_is_two_way():
    """Collapse then un-collapse: maxHeight must come back off 0 (two-way)."""
    w = _RecW()
    compositor._apply_spec(w, {"visible": True, "collapsed": True, "prominence": "standard"}, "probe")
    after_collapse = w.max_h
    compositor._apply_spec(w, {"visible": True, "collapsed": False, "prominence": "standard"}, "probe")
    after_uncollapse = w.max_h

    assert after_collapse == 0, "collapse should still pin maxHeight to 0"
    assert after_uncollapse != 0, (
        "un-collapse must restore maxHeight off 0 — a later profile that does "
        "not collapse the widget has to re-expand it."
    )
    assert after_uncollapse == compositor._QWIDGETSIZE_MAX
