"""Seeded-contrast pin — the CI-side mirror of audit_panel.py's A3 dense sweep.

The panel reseeds its surfaces from the host pane grey; the solved text ramp
(_derive_palette) must hold WCAG AA body contrast on every REALISTIC host grey
and a strong floor everywhere — so a future token edit that reintroduces the
mid-grey dip (the original 107-127 false-green) fails in CI, not just in the
offscreen audit. Pure / stdlib.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from synapse.panel.designsystem import tokens as t

_SURFACES = ("ground", "panel", "surface")


def _worst_body(v):
    surf, txt = t._derive_palette(v, v, v)
    return min(t._contrast(txt["primary"], surf[s]) for s in _SURFACES)


def _worst_secondary(v):
    surf, txt = t._derive_palette(v, v, v)
    return min(t._contrast(txt["secondary"], surf[s]) for s in _SURFACES)


def _realistic(v):
    return v <= 95 or v >= 150


def test_realistic_hosts_hold_AA_body():
    for v in range(0, 256):
        if _realistic(v):
            wb = _worst_body(v)
            assert wb >= 4.5, "grey %d: body %.2f < AA 4.5" % (v, wb)


def test_any_grey_holds_pragmatic_floor():
    worst = min(_worst_body(v) for v in range(0, 256))
    assert worst >= 3.5, "min body across all greys is %.2f < 3.5 floor" % worst
    worst_sec = min(_worst_secondary(v) for v in range(0, 256))
    assert worst_sec >= 3.0, "min secondary across all greys is %.2f < 3.0" % worst_sec


def test_houdini_dark_pane_is_crisp():
    # the actual Houdini dark pane grey (~46, UIDark.hcs) — comfortably AAA-ish
    assert _worst_body(46) >= 7.0
