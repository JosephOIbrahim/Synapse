"""Bundled-font loader + tracked-font factory (v9 type pass).

Loads the vendored Space Grotesk + Space Mono ``.ttf`` (designsystem/fonts/) into
QFontDatabase once, and exposes ``tracked_font(role, px)`` — the only correct way
to apply per-role tracking in Qt, because Qt QSS has **no** ``letter-spacing``.
Tracking is set on the QFont via ``setLetterSpacing(AbsoluteSpacing, em × px)``,
with the em values living in ``tokens.TRACKING_EM``.

Locked call #3: bundle via QFontDatabase, and **flag if a family is absent** —
``load_application_fonts()`` returns a status whose ``build_mismatch`` is True
when either expected family failed to register; the panel logs it and falls back
to the documented fallback families in ``tokens``. Kept Qt-only so ``tokens.py``
stays stdlib-only.
"""

import os

try:
    from PySide6 import QtGui, QtWidgets
except ImportError:  # pragma: no cover - Houdini ships PySide6
    from PySide2 import QtGui, QtWidgets

from . import tokens as t

# The bundled files and the families they must register.
_FILES = ("SpaceGrotesk-Variable.ttf", "SpaceMono-Regular.ttf", "SpaceMono-Bold.ttf")
_EXPECTED = ("Space Grotesk", "Space Mono")

_STATUS = None   # cached load result (idempotent across panel instances)


def _fonts_dir():
    return os.path.join(os.path.dirname(__file__), "fonts")


def load_application_fonts():
    """Load the bundled .ttf into QFontDatabase once. Returns a status dict:
    ``{ok, families, missing, loaded, build_mismatch}``. Idempotent — the first
    call does the work; later calls return the cached status. Safe with no
    QApplication (returns a not-loaded status without raising)."""
    global _STATUS
    if _STATUS is not None:
        return _STATUS

    loaded, families = [], set()
    app = None
    try:
        app = QtWidgets.QApplication.instance()
    except Exception:
        app = None

    if app is not None:
        fdir = _fonts_dir()
        for fn in _FILES:
            path = os.path.join(fdir, fn)
            try:
                fid = QtGui.QFontDatabase.addApplicationFont(path)
                if fid != -1:
                    loaded.append(fn)
                    for fam in QtGui.QFontDatabase.applicationFontFamilies(fid):
                        families.add(fam)
            except Exception:
                pass

    missing = [e for e in _EXPECTED if e not in families]
    _STATUS = {
        "ok": app is not None and not missing,
        "families": sorted(families),
        "missing": missing,
        "loaded": loaded,
        "build_mismatch": bool(missing),
    }

    if missing:
        # Build-mismatch flag — log; the panel falls back to the documented
        # tokens.FONT_*_FALLBACKS family (graceful, never a hard crash).
        try:
            import logging
            logging.getLogger("synapse.panel").warning(
                "SYNAPSE panel: bundled font family missing %s — falling back to "
                "a system family (designsystem/fonts).", missing)
        except Exception:
            pass

    return _STATUS


def font_status():
    """The last load status, or None if load_application_fonts() hasn't run."""
    return _STATUS


def tracked_font(role, px, scale=1.0, mono=False, bold=False):
    """Build a QFont for a tracking role: family from tokens, size in PIXELS, and
    AbsoluteSpacing = ``tokens.TRACKING_EM[role] × px`` (the only way to track in
    Qt). ``role`` ∈ BRAND/LABEL/LABEL_SM/DATA/DISPLAY/BODY. ``mono`` selects the
    Space Mono family; otherwise Space Grotesk. Falls back gracefully via the
    family fallbacks when the bundle didn't register."""
    fam = t.FONT_MONO if mono else t.FONT_SANS
    spx = t.scaled(px, scale)
    f = QtGui.QFont(fam)
    f.setPixelSize(spx)
    if bold:
        f.setBold(True)
    em = t.TRACKING_EM.get(role, 0.0)
    if em:
        try:
            f.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, em * spx)
        except Exception:
            pass
    return f
