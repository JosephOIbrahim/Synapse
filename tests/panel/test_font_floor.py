"""W5-PANEL item 2/4 — the host-floored font-scale ladder MATH.

The live Aa switcher (synapse_panel._cycle_font_scale) cycles the raw,
host-agnostic FONT_SCALE_STEPS and wraps back to 1.0 = 12px, which is BELOW the
host default whenever the host UI font is larger than 12px — "the switcher only
shrinks below default" (Joe, live seat). The fix is a ladder floored at the host
default; this pins that pure math.

Pure — no Qt, no hou — so it runs in stock-Python CI, not only under hython. The
one-line wiring of this helper into the peer-claimed synapse_panel._cycle_font_scale
is a for_ruling handoff (that file is off-limits to this leg); the guarantee the
switcher must inherit — "no state below the floor is reachable" — is proven here.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from synapse.panel.designsystem import tokens as t


def test_default_host_leaves_the_raw_ladder():
    # host == the 12px default (scale 1.0): the ladder is the raw steps, floor 1.0.
    ladder = t.host_floored_steps(1.0)
    assert ladder[0] == 1.0
    assert ladder == tuple(float(s) for s in t.FONT_SCALE_STEPS)


def test_large_host_floors_at_host_and_only_scales_up():
    # A 15px host UI font -> host_scale 1.25. Floor is the host, and only raw steps
    # ABOVE it survive: the switcher can no longer land below the host default.
    hs = 15 / float(t.SIZE_BODY)          # 1.25
    ladder = t.host_floored_steps(hs)
    assert ladder[0] == hs
    assert min(ladder) == hs
    assert all(s >= hs for s in ladder)
    assert all(s > hs for s in ladder[1:])  # strictly increasing above the floor


def test_small_host_uses_host_as_floor_and_keeps_the_steps_up():
    # A 10px host font -> host_scale ~0.833. The host default is STILL the floor
    # ("default Houdini UI font size to start"), and the full ladder scales up.
    hs = 10 / float(t.SIZE_BODY)          # ~0.8333
    ladder = t.host_floored_steps(hs)
    assert abs(ladder[0] - hs) < 1e-9
    assert min(ladder) == ladder[0]
    # every raw step is above this small floor, so all are retained above it
    assert ladder[1:] == tuple(float(s) for s in t.FONT_SCALE_STEPS)


def test_ladder_is_monotonic_and_deduped():
    for hs in (0.6, 0.8333, 1.0, 1.1, 1.15, 1.25, 1.5, 2.0):
        ladder = t.host_floored_steps(hs)
        assert list(ladder) == sorted(ladder), (hs, ladder)
        assert len(set(ladder)) == len(ladder), ("duplicate step", hs, ladder)


def test_bad_host_scale_falls_back_to_default_not_empty():
    for bad in (0.0, -1.0, None):
        ladder = t.host_floored_steps(bad)
        assert ladder[0] == t.FONT_SCALE_DEFAULT
        assert len(ladder) >= 1


def test_next_scale_never_drops_below_the_host_floor():
    # THE core guarantee: for any host and any current scale, the next step is
    # never below the host floor. This is what "no state below floor reachable"
    # means once the switcher consumes next_font_scale.
    for hs in (0.8333, 1.0, 1.25, 1.5):
        current = 0.0
        for _ in range(12):               # cycle well past the top, many times
            current = t.next_font_scale(current, hs)
            assert current >= hs - 1e-9, (hs, current)


def test_cycle_reaches_top_then_wraps_to_the_floor():
    hs = 15 / float(t.SIZE_BODY)          # 1.25 -> ladder (1.25, 1.4, 1.6)
    ladder = t.host_floored_steps(hs)
    top = ladder[-1]
    # at the top, the wrap goes to the floor (host default), never below it
    assert t.next_font_scale(top, hs) == ladder[0]
    assert t.next_font_scale(top, hs) == hs


def test_off_ladder_base_steps_up_not_down():
    # A host-derived base sitting between raw steps must step UP to the next one,
    # never reset to a smaller value (the live-seat complaint).
    assert t.next_font_scale(1.33, 1.0) > 1.33
    # and from the host floor itself, the first press moves up
    hs = 1.25
    assert t.next_font_scale(hs, hs) > hs
