"""Goalpost — the host-theme read has exactly ONE home: ``theme_source``.

The redesign seeded the panel surface from the live Houdini Color Scheme (the
``.hcs`` / ``UIDark.hcs`` greys) via ``hou.qt.color()``, formerly read inline in
``designsystem/tokens.py``. That read now routes through ``theme_source`` behind
a backend selector so an H22 Theme Editor (QML) source can replace it without
touching the token table. This pin proves three things:

  (a) the 'hcs' backend is BYTE-IDENTICAL to the pre-refactor inline read — it
      returns the exact host tuple for a fake color, ``None`` headless, and the
      module-level tokens tokens.py produces are unchanged (pinned hexes);
  (b) the 'qml_theme' backend is a stub that raises ``NotImplementedError``
      (MODE A must not switch to it);
  (c) NO panel module reads the host color scheme (``hou.qt.color(``) directly —
      exactly one file owns it: ``theme_source.py``.

PURE PYTHON by design: tokens.py + theme_source.py are stdlib-only (no PySide),
so these run as REAL assertions under stock CPython and hython — no
QApplication. Matches the sibling panel goalposts (test_token_seeding,
test_seeded_contrast).
"""

import importlib
import os
import sys

import pytest

# Source-checkout importability, matching the sibling panel tests' bootstrap.
# ``tests/`` is on the list so ``pkgbootstrap`` imports from this subdirectory
# without depending on pytest's conftest-driven sys.path insertion.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python"), os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pkgbootstrap  # noqa: E402
from synapse.panel.designsystem import theme_source  # noqa: E402

_TOKENS = "synapse.panel.designsystem.tokens"
_PANEL_DIR = os.path.join(_ROOT, "python", "synapse", "panel")

# The mechanical host color-scheme read. ``hou.qt.color()`` reads the ACTIVE
# Houdini Color Scheme (.hcs); ``UIDark.hcs`` is the stock dark scheme. This
# substring IS "reading UIDark.hcs" in code terms.
_HCS_READ_MARKER = "hou.qt.color("

# Pinned token values tokens.py produced BEFORE the refactor, headless (no hou)
# — captured from the pre-refactor module. Byte-identical output means every one
# of these still matches after routing the read through theme_source.
_PINNED_HEADLESS = {
    "PANEL": "#2A2A2A", "GROUND": "#1F1F1F", "FIELD_INSET": "#1F1F1F",
    "SURFACE": "#363636", "RAISED": "#323232", "BORDER": "#363636",
    "BORDER_STRONG": "#3C3C3C", "HAIR": "#303030",
    "TEXT_PRIMARY": "#C5C5C5", "TEXT_SECONDARY": "#A0A0A0",
    "TEXT_TERTIARY": "#868686", "TEXT_BRIGHT": "#DEDEDE",
    "TEXT_DISABLED": "#636363",
}


class _FakeColor:
    """Quacks like the QtGui.QColor that ``hou.qt.color()`` returns — every common
    accessor reports the SAME value, robust to whichever accessor the backend
    picks (matches test_token_seeding._FakeColor)."""

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

    def name(self):
        return "#%02x%02x%02x" % (self._r, self._g, self._b)


def _make_hou(color):
    """A minimal fake ``hou`` exposing ``hou.qt.color()`` returning ``color`` for
    any requested role."""
    import types

    hou = types.ModuleType("hou")

    class _Qt:
        def color(self, *_a, **_k):
            return color

    hou.qt = _Qt()
    return hou


def _install_hou(hou_module):
    """Install (or mark ABSENT, when None) a fake ``hou`` in sys.modules.

    Returns the prior value so the caller can restore it and never leak to
    neighbours (the 46-file sys.modules['hou'] residency trap).

    Absence is expressed as ``sys.modules["hou"] = None``, never as a pop.
    CPython raises ImportError on a None entry WITHOUT consulting the import
    machinery, so the module under test sees a deterministic absent ``hou``;
    popping instead lets `hou.py` RE-EXECUTE under hython, which re-registers
    the SWIG type map to a half-built `Parm` class and leaves every subsequent
    `node.parm(...).set(...)` in the process raising AttributeError. Restoring
    the original object afterwards does not undo it — the damage is in the C
    extension. See the HOU_REIMPORT_GUARD note in tests/conftest.py."""
    saved = sys.modules.get("hou")
    sys.modules["hou"] = hou_module  # None => deterministic ImportError
    return saved


def _restore_hou(saved):
    """Restore the prior resident BY OBJECT (never by re-import — see
    ``_install_hou``). ``saved is None`` means there was no resident, which we
    re-express as the deterministic-absent marker rather than a pop."""
    sys.modules["hou"] = saved


def _reload_tokens_with(hou_module):
    """Reload the tokens module with ``hou_module`` installed as ``hou`` (or
    marked ABSENT when None). Returns (module, saved) — pass ``saved`` to
    ``_restore``.

    Absence is ``sys.modules["hou"] = None``, never a pop — see ``_install_hou``
    above for why. ``theme_source._hcs_surface_rgb`` does a lazy ``import hou``,
    so a popped `hou` here re-executes hou.py under hython and half-builds the
    SWIG `Parm` class for the rest of the process.

    R310: ``_TOKENS`` is snapshotted through ``pkgbootstrap`` because the
    ``importlib.import_module`` below is a REAL import — it binds the throwaway
    module on ``synapse.panel.designsystem`` — and putting the original back in
    ``sys.modules`` alone leaves that binding pointing at the throwaway. See
    ``_restore``. ``hou`` keeps its own handling: it is top-level (no parent to
    bind) and its restore rule forbids the pop that a generic restore performs.
    """
    saved_hou = sys.modules.get("hou")
    saved_tokens = pkgbootstrap.snapshot_modules([_TOKENS])
    sys.modules["hou"] = hou_module  # None => deterministic ImportError
    sys.modules.pop(_TOKENS, None)
    mod = importlib.import_module(_TOKENS)
    return mod, (saved_hou, saved_tokens)


def _restore(saved):
    """Undo ``_reload_tokens_with``.

    THE DEFECT THIS FIXES (R310, reproduced at base): the old body restored
    only ``sys.modules[_TOKENS]``. The reload had already bound its throwaway
    copy on the parent package, so afterwards
    ``synapse.panel.designsystem.tokens`` (the attribute) and
    ``sys.modules['synapse.panel.designsystem.tokens']`` named two DIFFERENT
    module objects with the same name — resolution that succeeds and returns
    the wrong one, rather than the loud R307 AttributeError.

    Victim, base-verified: ``pytest tests/panel/test_theme_source.py
    tests/test_hda_panel.py`` failed
    ``TestRegression::test_tokens_import_cleanly`` with
    ``'#1F1F1F' != '#BDBDBD'`` — ``import synapse.panel.designsystem.tokens as
    ds`` walked the parent attribute to the headless reload while
    ``synapse.panel.tokens`` re-exported from the host-seeded resident.
    """
    saved_hou, saved_tokens = saved
    # Always restore `hou` BY OBJECT — never pop. A pop here would re-open the
    # eviction window that ``_reload_tokens_with`` exists to avoid, one line
    # after closing it.
    sys.modules["hou"] = saved_hou
    pkgbootstrap.restore_modules(saved_tokens)


# ── (a) the 'hcs' backend is byte-identical to the former inline read ─────────

def test_hcs_backend_reads_host_tuple_identically():
    # With a live-ish host (fake hou.qt.color), the hcs backend returns the exact
    # (r, g, b) the former inline _host_surface_rgb() returned — same accessors.
    saved = _install_hou(_make_hou(_FakeColor(200, 200, 200)))
    try:
        assert theme_source.host_surface_rgb(backend="hcs") == (200, 200, 200)
        # default backend is 'hcs' — must behave the same without the kwarg
        assert theme_source.host_surface_rgb() == (200, 200, 200)
        # the getRgb() accessor fallback path is honored too
        saved2 = _install_hou(_make_hou(_FakeColor(37, 42, 51)))
        try:
            assert theme_source.host_surface_rgb() == (37, 42, 51)
        finally:
            _restore_hou(saved2)
    finally:
        _restore_hou(saved)


def test_hcs_backend_headless_is_none():
    # No hou -> the former inline read returned None; the backend must too, so
    # the caller falls back to the hardcoded grey. (Any failure -> None.)
    saved = _install_hou(None)
    try:
        assert theme_source.host_surface_rgb() is None
        assert theme_source.host_surface_rgb(backend="hcs") is None
    finally:
        _restore_hou(saved)


def test_tokens_output_byte_identical_headless():
    # The end-to-end proof: reloading tokens headless (the CI/test path) must
    # produce the SAME hexes it produced before the read moved to theme_source.
    mod, saved = _reload_tokens_with(None)
    try:
        for name, expected in _PINNED_HEADLESS.items():
            got = getattr(mod, name)
            assert got == expected, (
                "tokens.%s changed: %s != pinned %s — the theme_source refactor "
                "must be byte-identical" % (name, got, expected))
    finally:
        _restore(saved)


def test_tokens_still_route_through_theme_source_when_seeded():
    # A LIGHT host scheme must still flip the panel light — proving tokens read
    # the host color VIA theme_source (not a stale inline path). Mirrors
    # test_token_seeding.test_follows_host_scheme through the new seam.
    mod, saved = _reload_tokens_with(_make_hou(_FakeColor(200, 200, 200)))
    try:
        h = mod.PANEL.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
        assert lum > 0.5, (
            "PANEL must track the seeded LIGHT host through theme_source; got "
            "%s (lum %.2f)" % (mod.PANEL, lum))
    finally:
        _restore(saved)


# ── (b) the 'qml_theme' backend is a NotImplementedError stub ─────────────────

def test_qml_theme_backend_not_implemented():
    with pytest.raises(NotImplementedError):
        theme_source.host_surface_rgb(backend="qml_theme")
    # the underlying backend raises directly too
    with pytest.raises(NotImplementedError):
        theme_source._qml_theme_surface_rgb(theme_source.SURFACE_ROLE)


def test_unknown_backend_rejected():
    with pytest.raises(ValueError):
        theme_source.host_surface_rgb(backend="does_not_exist")


def test_backend_registry_shape():
    # 'hcs' is active under MODE A; both backends are registered.
    assert theme_source.ACTIVE_BACKEND == "hcs"
    assert set(theme_source.AVAILABLE_BACKENDS) == {"hcs", "qml_theme"}


# ── (c) exactly ONE panel module owns the host color-scheme read ──────────────

def test_only_theme_source_reads_the_hcs_host_theme():
    offenders = []
    seam_owns_read = False
    for root, _dirs, files in os.walk(_PANEL_DIR):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            with open(path, "r", encoding="utf-8") as fh:
                src = fh.read()
            if _HCS_READ_MARKER not in src:
                continue
            if os.path.basename(path) == "theme_source.py":
                seam_owns_read = True
            else:
                offenders.append(os.path.relpath(path, _ROOT))
    assert not offenders, (
        "these panel modules read the host color scheme (%s → the .hcs / "
        "UIDark.hcs greys) directly instead of routing through theme_source: %s"
        % (_HCS_READ_MARKER, offenders))
    assert seam_owns_read, (
        "theme_source.py must OWN the host-scheme read (%s) — the seam is empty, "
        "so the test would pass vacuously" % _HCS_READ_MARKER)
