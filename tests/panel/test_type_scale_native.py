"""SIZE_BODY is Houdini-native (9pt ≈ 12px) — the ratified body size the panel
matches the host with, and the size audit_panel.py's BODY_FLOOR comment cites.
Pure / stdlib (no Qt, no hou) so it runs under stock ``pytest -q`` AND hython.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from synapse.panel.designsystem import tokens as t


def test_body_size_is_houdini_native():
    # 9pt ≈ 12px, matched to Houdini's QApplication default UI font so the panel
    # sits IN the host UI rather than oversizing past it.
    assert t.SIZE_BODY == 12


def test_type_scale_monotonic_and_distinct():
    # AMENDED BY DECLARATION -- PNL-L4, ruling R3-A (2026-09-21). The floor was
    # >= 4 for the 11/12/15/19 ramp. R3-A folds SIZE_SMALL into SIZE_BODY: an
    # 11-vs-12 step is a rung no eye can read, so it was never hierarchy, and
    # counting it as one is what let a four-rung claim describe a three-rung
    # scale. The ramp is now 12 / 15 / 19 and the floor moves to >= 3. The
    # monotonic pin is UNCHANGED, and the <= 5 ceiling in
    # tests/test_panel_typography.py::test_type_scale_is_at_most_five_sizes is
    # untouched -- this leg lowers the floor, it does not raise the ceiling.
    sizes = [t.SIZE_SMALL, t.SIZE_UI, t.SIZE_BODY, t.SIZE_TITLE, t.SIZE_HERO]
    assert sizes == sorted(sizes), "type sizes must be non-decreasing"
    assert len(set(sizes)) >= 3, "need a real hierarchy (>=3 distinct steps, R3-A)"


def test_default_scale_at_least_native():
    # the startup scale never shrinks the body below the native 12px
    assert t.scaled(t.SIZE_BODY, 1.0) == 12
    assert t.scaled(t.SIZE_BODY, t.FONT_SCALE_DEFAULT) >= 12
    # the default must be one of the cycle steps so the Aa control can index it
    assert t.FONT_SCALE_DEFAULT in t.FONT_SCALE_STEPS


def test_wordmark_lockup_tokens():
    """Joe's addendum (2026-09-05): the wordmark is 15px (was 14) and sits
    WORDMARK_GAP (5px) farther from the mark than the identity row's stack
    gap. The size rides the widget's tracked_font call (F9 lists it as a
    literal); the gap is a token, never a literal in the widget."""
    assert t.WORDMARK_GAP == 5
    src = open(os.path.join(_ROOT, "python", "synapse", "panel", "synapse_panel.py"),
               encoding="utf-8").read()
    assert 'tracked_font("WORDMARK", 15' in src
    assert 'tracked_font("WORDMARK", 14' not in src
    assert "t.WORDMARK_GAP" in src
