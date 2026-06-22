"""Goalpost — design tokens must be SEEDED from hou.qt.color() at construction.

Contract: theme-seed-tokens (C1). Encodes Design §2.2 / Codebase §1.3:

    "you built a beautiful token table; it should be *seeded from
    hou.qt.color() at construction*, hardcoded values as headless fallback —
    not the reverse."

Today `designsystem/tokens.py` hardcodes the matched hex (the SURFACE-ELEVATION
block, ~lines 47-56, "Verified against $HFS/.../UIDark.hcs") and the comment
even concedes "the hex stays source of truth." That is the inversion: the
instant a user switches to a lighter scheme the panel is a dark hole again.

PURE PYTHON by design: tokens.py is stdlib-only (no PySide), so these run as
REAL assertions under stock CPython *and* hython — no QApplication required.
That is deliberate: the two other panel goalposts (failure-trail, docking)
need a live QWidget and therefore PySide; these do not, so they are the
goalposts that give a true pass/fail under the harness's stock `pytest -q`.
"""

import importlib
import os
import sys

# Make the package importable from a source checkout (no install), matching the
# sys.path bootstrap the existing panel tests use.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_TOKENS = "synapse.panel.designsystem.tokens"


def _luminance(hex_str):
    """Relative luminance 0..1 from '#RRGGBB' (Rec.709 coefficients)."""
    h = hex_str.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


class _FakeColor:
    """Quacks like the QtGui.QColor that ``hou.qt.color()`` returns. Every common
    accessor reports the SAME value, so the test is robust to whichever accessor
    the seeding implementation picks to read the host color."""

    def __init__(self, r, g, b, a=255):
        self._r, self._g, self._b, self._a = r, g, b, a

    def red(self):
        return self._r

    def green(self):
        return self._g

    def blue(self):
        return self._b

    def alpha(self):
        return self._a

    def getRgb(self):
        return (self._r, self._g, self._b, self._a)

    def redF(self):
        return self._r / 255.0

    def greenF(self):
        return self._g / 255.0

    def blueF(self):
        return self._b / 255.0

    def getRgbF(self):
        return (self._r / 255.0, self._g / 255.0, self._b / 255.0, self._a / 255.0)

    def name(self):
        return "#%02x%02x%02x" % (self._r, self._g, self._b)

    def __str__(self):
        return self.name()

    def __iter__(self):
        return iter((self._r, self._g, self._b))


def _make_light_hou():
    """A minimal fake `hou` exposing ``hou.qt.color()`` that returns a LIGHT grey
    for any requested role — i.e. the artist is on a light scheme. (The contract
    names hou.qt.color() specifically; hou.qt is a confirmed-live namespace —
    see panel/dnd.py's hou.qt.mimeType usage.)"""
    import types

    hou = types.ModuleType("hou")
    light = _FakeColor(200, 200, 200)

    class _Qt:
        def color(self, *_a, **_k):
            return light

        def styleSheet(self, *_a, **_k):  # paired API; harmless if read
            return ""

    hou.qt = _Qt()
    return hou


def _reload_tokens_with(hou_module):
    """Reload the tokens module with `hou_module` installed as `hou` (or removed
    when None). Returns (module, saved) — pass `saved` to `_restore`."""
    saved = {k: sys.modules.get(k) for k in ("hou", _TOKENS)}
    if hou_module is None:
        sys.modules.pop("hou", None)
    else:
        sys.modules["hou"] = hou_module
    sys.modules.pop(_TOKENS, None)
    mod = importlib.import_module(_TOKENS)
    return mod, saved


def _restore(saved):
    """Return sys.modules to its exact pre-test state (no re-execution), so this
    test never leaks a fake `hou` or a reloaded tokens module to its neighbours
    (the 46-file sys.modules['hou'] residency trap)."""
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v


def test_follows_host_scheme():
    # Design §2.2 / Codebase §1.3 — a LIGHT host scheme must make the panel
    # surface LIGHT. Today PANEL is hardcoded dark (#2E2E2E ≈ 0.18), so this
    # FAILS until tokens are seeded from hou.qt.color() at construction.
    mod, saved = _reload_tokens_with(_make_light_hou())
    try:
        lum = _luminance(mod.PANEL)
        assert lum > 0.5, (
            "PANEL must track the host's LIGHT scheme (seeded from "
            "hou.qt.color()); got %s (luminance %.2f) — still hardcoded dark hex"
            % (mod.PANEL, lum)
        )
    finally:
        _restore(saved)


def test_headless_fallback():
    # The 'don't break headless' guard — with hou unavailable, tokens fall back
    # to the hardcoded hex (a dark surface). PASSES today; it MUST keep passing
    # after the seeding inversion lands.
    mod, saved = _reload_tokens_with(None)
    try:
        assert (isinstance(mod.PANEL, str) and mod.PANEL.startswith("#")
                and len(mod.PANEL) == 7), (
            "headless PANEL must be a hardcoded hex string, got %r" % (mod.PANEL,))
        assert _luminance(mod.PANEL) < 0.5, (
            "headless fallback surface should be the dark hardcoded hex, got %s"
            % mod.PANEL)
    finally:
        _restore(saved)
