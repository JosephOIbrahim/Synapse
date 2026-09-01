"""BP2-PANELTRUTH T1 — the density root property REPOLISHES DESCENDANTS.

The 08-04 finding (compositor.py:_repolish_tree docstring, J4.3 Defect A/B): a
Qt dynamic property set on a parent does NOT cascade to its children, so the
density QSS descendant rules (``#DsRoot[density="tight"] ...``) match on paper
and never repaint unless every child is repolished too. That bug made all three
profiles render identically. ``compose()`` fixes it by stamping ``density`` on
the panel root and then repolishing the WHOLE subtree (``_repolish_tree``).

``tests/test_rope_density.py`` pins the PLUMBING (manifest lever + QSS rules),
Qt-free. It cannot see the repaint. THIS file closes that: it observes, on a
recording duck-typed tree (no real Qt — matches the stock-CPython suite), that

  1. ``_repolish_tree`` actually walks every descendant (not a silent no-op,
     not root-only — the two shipped regressions), and
  2. ``compose()`` repolishes the panel ROOT + its descendants — an assertion
     that turns RED the instant the ``_repolish_tree(panel)`` call is removed
     (the panel root is repolished ONLY by that call; ``_apply_spec`` touches
     region/widget targets, never the root). The exact source mutation and its
     red run are recorded in ``harness/battleplan/notes/BP2-PANELTRUTH.md``.

Qt-free by construction: ``compositor.resolve`` / ``compose`` / ``_repolish_tree``
duck-type ``style()`` / ``children()`` and import no Qt, so a recording fake
tree exercises the real code paths verbatim.
"""

import pytest

from synapse.panel import compositor
from synapse.panel.manifests import get_manifest


# --------------------------------------------------------------------------- #
# Recording duck-typed Qt leaves — no logic, only the surface _repolish_tree /
# _apply_spec / compose reach for, plus a polish log keyed by widget name.
# --------------------------------------------------------------------------- #

class _RecStyle:
    def __init__(self, log):
        self._log = log

    def unpolish(self, w):
        self._log.append(("unpolish", w.nm))

    def polish(self, w):
        self._log.append(("polish", w.nm))


class _RecWidget:
    def __init__(self, nm, log, kids=()):
        self.nm = nm
        self._log = log
        self._kids = list(kids)
        self._props = {}

    # _repolish_tree surface
    def style(self):
        return _RecStyle(self._log)

    def children(self):
        return list(self._kids)

    def update(self):
        pass

    # _apply_spec surface
    def setVisible(self, v):
        pass

    def setMaximumHeight(self, h):
        pass

    def setProperty(self, k, v):
        self._props[k] = v

    def property(self, k):
        return self._props.get(k)

    def parentWidget(self):
        return None


class _RecLayout:
    def __init__(self):
        self.items = []

    def addWidget(self, w, stretch=0):
        self.items.append((w, stretch))


class _ComposePanel:
    """A panel-shaped recording target for ``compositor.compose``. Every region
    builder and every widget-id in the compositor registry resolves to a
    recording leaf (built from the real registry so it can never drift). Extra
    ``probes`` hang off ``children()`` as pre-existing descendants — the panel
    root's subtree at density-stamp time, i.e. a re-compose (profile switch)."""

    nm = "PANEL_ROOT"
    _BUILDERS = tuple(compositor.REGION_BUILDERS.values())

    def __init__(self, log, probes=()):
        self._log = log
        self._props = {}
        self._probes = list(probes)
        self._lay = _RecLayout()
        self._region_widgets = {b: _RecWidget(b, log) for b in self._BUILDERS}
        for wid, attrpath in compositor.WIDGET_ATTRS.items():
            attr, _, key = attrpath.partition(".")
            if key:
                holder = getattr(self, attr, None)
                if holder is None:
                    holder = {}
                    setattr(self, attr, holder)
                holder[key] = _RecWidget(wid, log)
            else:
                setattr(self, attr, _RecWidget(wid, log))

    # root duck-typing (_repolish_tree walks this first)
    def style(self):
        return _RecStyle(self._log)

    def children(self):
        return list(self._probes)

    def update(self):
        pass

    def setProperty(self, k, v):
        self._props[k] = v

    def property(self, k):
        return self._props.get(k)

    def layout(self):
        return self._lay

    # the four region builders compose() invokes by name
    def _build_rail(self):
        return self._region_widgets["_build_rail"]

    def _build_context_ribbon(self):
        return self._region_widgets["_build_context_ribbon"]

    def _build_mode_bar(self):
        return self._region_widgets["_build_mode_bar"]

    def _build_faces(self):
        return self._region_widgets["_build_faces"]


def _polished(log):
    return {nm for kind, nm in log if kind == "polish"}


# --------------------------------------------------------------------------- #
# 1. _repolish_tree walks the WHOLE subtree (pins J4.3 Defect A + B).
# --------------------------------------------------------------------------- #

def test_repolish_tree_reaches_every_descendant():
    log = []
    grand = _RecWidget("gc", log)
    child = _RecWidget("child", log, kids=[grand])
    root = _RecWidget("root", log, kids=[child])
    n = compositor._repolish_tree(root)
    assert n == 3, "must repolish root + child + grandchild (not a no-op)"
    assert _polished(log) == {"root", "child", "gc"}


def test_repolish_tree_is_not_root_only():
    # J4.3 Defect B: a `break` after the root repolished only the root; the
    # siblings below must both be reached.
    log = []
    root = _RecWidget("root", log, kids=[_RecWidget("a", log), _RecWidget("b", log)])
    compositor._repolish_tree(root)
    assert {"root", "a", "b"} <= _polished(log)


# --------------------------------------------------------------------------- #
# 2. compose() stamps density AND repolishes root + descendants (mutation net).
# --------------------------------------------------------------------------- #

def test_compose_stamps_density_and_repolishes_root_and_descendants():
    log = []
    grand = _RecWidget("PROBE_GRANDCHILD", log)
    probe = _RecWidget("PROBE_CHILD", log, kids=[grand])
    panel = _ComposePanel(log, probes=[probe])

    compositor.compose(panel, panel.layout(), get_manifest("ml"))

    # density root property set (tight for ml)
    assert panel.property("density") == "tight"
    polished = _polished(log)
    # the ROOT is repolished ONLY by the _repolish_tree(panel) call under test
    assert "PANEL_ROOT" in polished, (
        "compose() must repolish the panel ROOT so the density property takes")
    # ...and it reaches DESCENDANTS, not just the root (the J4.3 fix)
    assert {"PROBE_CHILD", "PROBE_GRANDCHILD"} <= polished, (
        "compose() must repolish DESCENDANTS, not just the root")


def test_compose_repolish_call_is_load_bearing(monkeypatch):
    """Prove the assertion above is not vacuous: neuter ``_repolish_tree`` (the
    exact mutation recorded in the notes) and the panel ROOT + descendants are
    no longer repolished — density never reaches them. This is the RED state the
    real call prevents."""
    log = []
    probe = _RecWidget("PROBE_CHILD", log, kids=[_RecWidget("PROBE_GRANDCHILD", log)])
    monkeypatch.setattr(compositor, "_repolish_tree", lambda w: 0)
    panel = _ComposePanel(log, probes=[probe])

    compositor.compose(panel, panel.layout(), get_manifest("ml"))

    polished = _polished(log)
    assert panel.property("density") == "tight"   # property still stamped...
    assert "PANEL_ROOT" not in polished           # ...but NOTHING repolished it
    assert "PROBE_CHILD" not in polished
    assert "PROBE_GRANDCHILD" not in polished


@pytest.mark.parametrize("profile,expected", [
    ("curious", "airy"), ("expert", "standard"), ("ml", "tight")])
def test_compose_stamps_the_profiles_density(profile, expected):
    log = []
    panel = _ComposePanel(log)
    compositor.compose(panel, panel.layout(), get_manifest(profile))
    assert panel.property("density") == expected
