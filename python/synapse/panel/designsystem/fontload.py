"""Bundled-font loader + tracked-font factory (v9 type pass).

Loads the vendored Space Grotesk + Space Mono ``.ttf`` (designsystem/fonts/) into
QFontDatabase once, and exposes ``tracked_font(role, px)`` — the only correct way
to apply per-role tracking in Qt, because Qt QSS has **no** ``letter-spacing``.
Tracking is set on the QFont via ``setLetterSpacing(PercentageSpacing,
100 + em × 100)``, with the em values living in ``tokens.TRACKING_EM``.

Ratified v9 call: the factory's default family IS the bundled Space Grotesk
(``mono=True`` → Space Mono), applied via QFont only (never QSS). Locked call
#3: bundle via QFontDatabase, and **flag if a family is absent** —
``load_application_fonts()`` returns a status whose ``build_mismatch`` is True
when either expected family failed to register; the panel logs it and the
factory gracefully keeps the host's native family instead. Kept Qt-only so
``tokens.py`` stays stdlib-only.
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

# QApplication dynamic-property key for the load status. The panel loader
# purges ``synapse.*`` from sys.modules on every reopen (fresh-reload
# contract), which resets ``_STATUS`` — but the QApplication (and its
# QFontDatabase registrations) survive the purge. Stashing the status on the
# app makes the load idempotent PER PROCESS, not per import: without it every
# panel reopen re-registers the same 3 .ttf into the process-wide database.
_APP_STATUS_PROP = "_synapse_fonts_status_v1"


def _fonts_dir():
    return os.path.join(os.path.dirname(__file__), "fonts")


def load_application_fonts():
    """Load the bundled .ttf into QFontDatabase once. Returns a status dict:
    ``{ok, families, missing, loaded, build_mismatch}``. Idempotent per
    PROCESS — the first call does the work; later calls (including after a
    panel-reload sys.modules purge) return the cached status. Safe with no
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

    if app is None:
        # No QApplication yet — report not-loaded WITHOUT caching, so an early
        # caller (e.g. tracked_font before the panel boots) can never poison
        # the idempotent cache and block the real load later.
        return {"ok": False, "families": [], "missing": list(_EXPECTED),
                "loaded": [], "build_mismatch": True}

    try:
        prior = app.property(_APP_STATUS_PROP)
        if isinstance(prior, dict) and "build_mismatch" in prior:
            # A previous import in THIS process already registered the bundle
            # (the fonts outlive the panel-loader purge) — adopt, don't re-add.
            _STATUS = prior
            return _STATUS
    except Exception:
        pass

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
    try:
        app.setProperty(_APP_STATUS_PROP, _STATUS)   # survives the reload purge
    except Exception:
        pass

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


# The bundled family chains (QFont.setFamilies order — Qt walks them until one
# resolves). Families land via QFont ONLY, never QSS (the audit pins that).
_SANS_CHAIN = ("Space Grotesk", "DM Sans", "Segoe UI")
_MONO_CHAIN = ("Space Mono", "JetBrains Mono", "Consolas")


def _bundle_registered():
    """True when both bundled families registered (loads on first use — safe
    pre-QApplication: that path returns a non-cached not-loaded status)."""
    st = load_application_fonts()
    return bool(st.get("ok")) and not st.get("build_mismatch")


def apply_family(f, mono=False):
    """Set the ratified v9 family on a QFont: the bundled Space Grotesk (sans)
    or Space Mono (``mono=True``), with the documented fallback chain. Graceful
    native fallback: when the bundle failed to register (``build_mismatch``),
    the font keeps the host family (mono → the host fixed-pitch face)."""
    if _bundle_registered():
        chain = _MONO_CHAIN if mono else _SANS_CHAIN
        try:
            f.setFamilies(list(chain))          # PySide6 / Qt ≥ 5.13
        except Exception:
            f.setFamily(chain[0])               # PySide2: first registered family
    elif mono:
        try:
            f.setFamily(
                QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont).family())
        except Exception:
            f.setFamily("monospace")
    return f


def tracked_font(role, px, scale=1.0, mono=False, bold=False, weight=400):
    """Build a QFont for a tracking role: size in PIXELS + PercentageSpacing =
    ``100 + tokens.TRACKING_EM[role] × 100`` (the only way to track in Qt).
    ``role`` ∈ EYEBROW/BRAND/LABEL/LABEL_SM/DATA/SEND/DISPLAY/BODY.

    v9 ratified call: the family is the bundled Space Grotesk (``mono=True`` →
    Space Mono) with the graceful native-family fallback when the bundle didn't
    register (``font_status()['build_mismatch']``). ``weight`` 500 maps to
    QFont Medium (never ``setBold``); ≥600 (or ``bold=True``) is bold."""
    spx = t.scaled(px, scale)
    try:
        f = QtGui.QFont(QtWidgets.QApplication.font())   # inherit host attrs
    except Exception:
        f = QtGui.QFont()
    apply_family(f, mono=mono)
    f.setPixelSize(spx)
    if bold or weight >= 600:
        f.setBold(True)
    elif weight == 500:
        try:
            f.setWeight(QtGui.QFont.Weight.Medium)       # Qt6
        except Exception:
            try:
                f.setWeight(QtGui.QFont.Medium)          # Qt5 / PySide2
            except Exception:
                pass
    em = t.TRACKING_EM.get(role, 0.0)
    if em:
        try:
            f.setLetterSpacing(QtGui.QFont.PercentageSpacing, 100.0 + em * 100.0)
        except Exception:
            pass
    return f
