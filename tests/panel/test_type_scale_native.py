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
    sizes = [t.SIZE_MICRO, t.SIZE_SMALL, t.SIZE_UI, t.SIZE_BODY, t.SIZE_TITLE, t.SIZE_HERO]
    assert sizes == sorted(sizes), "type sizes must be non-decreasing"
    assert len(set(sizes)) >= 4, "need a real hierarchy (>=4 distinct steps)"


def test_default_scale_at_least_native():
    # the startup scale never shrinks the body below the native 12px
    assert t.scaled(t.SIZE_BODY, 1.0) == 12
    assert t.scaled(t.SIZE_BODY, t.FONT_SCALE_DEFAULT) >= 12
    # the default must be one of the cycle steps so the Aa control can index it
    assert t.FONT_SCALE_DEFAULT in t.FONT_SCALE_STEPS
