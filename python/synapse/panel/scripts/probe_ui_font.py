"""probe_ui_font.py — MEASURE the Houdini UI font (BP4-PANELFONT, gui_required).

The panel type floor (``tokens.FONT_FLOOR_PX``) must be the Houdini **default UI
font size**, and that size is a GUI-only fact: ``QApplication.font()`` is only
meaningful when a real Qt application is up — interactive Houdini, NOT hython
(which has no ``QApplication``). So this script is pasted into the Houdini
22.0.400 **Python Shell** (``Windows ▸ Python Shell``) and its printout is the
``gui_required`` evidence that flips the floor's provenance from UNKNOWN to
measured. It NEVER mutates anything — it only reads and reports.

How to run (either works):
    1. Copy this whole file into the Python Shell and press Enter, OR
    2. exec(open(r"…/python/synapse/panel/scripts/probe_ui_font.py").read())
If nothing prints, call ``probe()`` once by hand.

It reads and reports:
  • QApplication.instance().font()  → .family() .pointSize() .pointSizeF()
                                       .pixelSize() .weight()
  • QFontInfo(app.font())           → the RESOLVED family + pixelSize actually in
                                       use. (Qt reports pointSize == -1 when a
                                       font is defined by pixel size, and
                                       pixelSize == -1 when defined by point size,
                                       so QFontInfo is the honest read of both.)
  • hou.ui.scaledSize(1)            → Houdini's global UI scale, if the accessor
                                       exists on this build.
Then it prints a one-line FLOOR CANDIDATE in px for the token module.
"""

import sys


def _w(line=""):
    sys.stdout.write(line + "\n")


def probe():
    """Print the live Houdini UI-font facts. Returns None (nothing to echo)."""
    _w("=" * 62)
    _w("SYNAPSE BP4-PANELFONT — Houdini UI font probe (read-only)")
    _w("=" * 62)

    # Houdini 22 ships PySide6; keep a PySide2 fallback for older seats.
    QtGui = QtWidgets = None
    binding = None
    try:
        from PySide6 import QtGui, QtWidgets  # noqa: F401
        binding = "PySide6"
    except Exception:
        try:
            from PySide2 import QtGui, QtWidgets  # noqa: F401
            binding = "PySide2"
        except Exception:
            _w("UNAVAILABLE: no PySide6/PySide2 import — not a Qt Houdini session.")
            _w("  A skipped probe is UNKNOWN, never a pass. Re-run in interactive")
            _w("  Houdini.")
            return
    _w("Qt binding : %s" % binding)

    app = QtWidgets.QApplication.instance()
    if app is None:
        _w("UNAVAILABLE: QApplication.instance() is None.")
        _w("  → You are almost certainly in hython (no GUI app). Run this in the")
        _w("    interactive Houdini Python Shell instead. Skip is NOT a pass.")
        return

    f = app.font()
    _w("")
    _w("QApplication.font():")
    _w("  family()     = %r" % f.family())
    _w("  pointSize()  = %s   (-1 ⇒ font is defined by pixelSize)" % f.pointSize())
    _w("  pointSizeF() = %s" % f.pointSizeF())
    _w("  pixelSize()  = %s   (-1 ⇒ font is defined by pointSize)" % f.pixelSize())
    _w("  weight()     = %s" % f.weight())

    fi = QtGui.QFontInfo(f)
    _w("")
    _w("QFontInfo(app.font())  — the RESOLVED values Qt lays the UI out at:")
    _w("  family()     = %r" % fi.family())
    _w("  pointSize()  = %s" % fi.pointSize())
    _w("  pixelSize()  = %s" % fi.pixelSize())

    # Houdini global UI scale, if the accessor exists on this build.
    try:
        import hou
        ui = getattr(hou, "ui", None)
        fn = getattr(ui, "scaledSize", None) if ui is not None else None
        if callable(fn):
            _w("")
            _w("hou.ui.scaledSize(1) = %s   (Houdini global UI scale, 1 device px)"
               % fn(1))
        else:
            _w("")
            _w("hou.ui.scaledSize: not present on this build.")
    except Exception as exc:
        _w("")
        _w("hou.ui.scaledSize(1): unavailable (%s)" % exc.__class__.__name__)

    # The floor candidate in PX (the token scale is px). The resolved QFontInfo
    # pixelSize is the size Qt actually renders the UI at — the honest floor.
    _w("")
    _w("-" * 62)
    _w("FLOOR CANDIDATE (px, for tokens.FONT_FLOOR_PX) = %s" % fi.pixelSize())
    _w("MEASURED FAMILY (for the family-token provenance) = %r" % fi.family())
    _w("")
    _w("Paste the two lines above into BP4_PANELFONT_AUDIT.md §Joe-hands so the")
    _w("floor provenance flips UNKNOWN → measured (H22.0.400, GUI). A follow-up")
    _w("leg then raises FONT_FLOOR_PX to this px and lifts any sub-floor role.")
    _w("-" * 62)


# ─────────────────────────────────────────────────────────────
# PNL-L6 — the HOST-FLOOR ASSERTION (ruling R3-C)
# ─────────────────────────────────────────────────────────────
# `probe()` above is the GUI paste that produced the floor's provenance. What
# it never did is ASSERT: it printed a candidate and left a human to compare.
# The Aa ladder itself has been host-floored since W5-PANEL
# (`tokens.host_floored_steps`, already called from `tokens.next_font_scale`,
# already wired at the panel's Aa cycle) — so NO new wiring belongs here. The
# gap ruling R3-C names is the missing check, and this is it, runnable headless:
#
#     QT_QPA_PLATFORM=offscreen hython python/synapse/panel/scripts/probe_ui_font.py
#
# host_px       = QFontInfo(QApplication.font()).pixelSize() — the host UI size.
# min_chrome_px = the SMALLEST size any chrome font actually RENDERS at, read
#                 off the BUILT WIDGETS (QFontInfo of widget.font()), never off
#                 the token module. Token values are authored PRE-scale numbers;
#                 the live panel multiplies them by the host ratio, so "is any
#                 chrome smaller than the host?" can only be answered by the
#                 fonts Qt resolved on the real widgets.
# Exits 1 when min_chrome_px < host_px. Read-only: it builds a panel offscreen
# and reads it; it mutates no file and no scene.

#: (report name, attribute on SynapsePanel) — the chrome the ruling names: the
#: composer key hint, the rail's author token and token meter, and the footer
#: links. The face pills are collected separately (they live in a dict).
CHROME_WIDGETS = (
    ("khint",           "_khint"),
    ("palette_hint",    "_palette_hint"),
    ("rail_author",     "_author_lbl"),
    ("rail_meter",      "_meter_lbl"),
    ("footer_commands", "_commands_btn"),
    ("footer_render",   "_render_btn"),
    ("footer_recipes",  "_recipes_btn"),
    ("footer_events",   "_events_btn"),
)


def chrome_font_pixels(panel, QtGui):
    """Rendered pixel size of every chrome font on a BUILT panel.

    Returns ``[(name, px), ...]`` where each ``px`` is
    ``QFontInfo(widget.font()).pixelSize()`` — what Qt resolved for that widget.
    """
    out = []
    for name, attr in CHROME_WIDGETS:
        w = getattr(panel, attr, None)
        if w is None:
            continue
        out.append((name, QtGui.QFontInfo(w.font()).pixelSize()))
    for face, pill in sorted(getattr(panel, "_face_pills", {}).items()):
        if pill is None:
            continue
        out.append(("pill_%s" % face, QtGui.QFontInfo(pill.font()).pixelSize()))
    return out


def measure_host_floor():
    """Build the panel offscreen; return ``(host_px, min_chrome_px, rows)``.

    Raises when Qt is unavailable or the panel cannot be built — a skip is
    UNKNOWN, never a pass.
    """
    try:
        from PySide6 import QtGui, QtWidgets
    except Exception:      # pragma: no cover - PySide2 seats
        from PySide2 import QtGui, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    host_px = QtGui.QFontInfo(app.font()).pixelSize()

    from synapse.panel.synapse_panel import SynapsePanel
    panel = SynapsePanel()
    rows = chrome_font_pixels(panel, QtGui)
    if not rows:
        raise RuntimeError("no chrome widgets found on the built panel")
    return host_px, min(px for _n, px in rows), rows


def _use_the_tree_this_file_lives_in():
    """Put THIS checkout's ``python/`` first on ``sys.path``.

    Measured 2026-09-21 (PNL-L6): run as a script under hython with
    ``HOUDINI_PACKAGE_DIR`` and ``PYTHONPATH`` both pointed at a worktree, the
    probe still imported ``synapse`` from the MAIN tree — Houdini's deployed
    package prepends its own tree in-process and beats both — and reported that
    tree's token values as this branch's. Same failure class
    harness/notes/bp9/panel_gate.py exists to defeat. A probe that cannot say
    which tree it measured is not evidence, so the path is derived from
    ``__file__`` rather than from the environment.
    """
    import os
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))   # …/python
    if sys.path[:1] != [root]:
        sys.path.insert(0, root)
    return root


def main():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _w("importing synapse from: %s" % _use_the_tree_this_file_lives_in())
    try:
        host_px, min_chrome_px, rows = measure_host_floor()
    except Exception as exc:
        _w("UNAVAILABLE: could not build the panel offscreen (%s: %s)."
           % (exc.__class__.__name__, exc))
        _w("  A skipped probe is UNKNOWN, never a pass.")
        return 2

    _w("=" * 62)
    _w("PNL-L6 host-floor assertion (read-only)")
    _w("=" * 62)
    for name, px in rows:
        _w("  %-18s %s px" % (name, px))
    _w("")
    _w("host_px       = %s" % host_px)
    _w("min_chrome_px = %s" % min_chrome_px)
    if min_chrome_px < host_px:
        _w("FAIL: chrome renders BELOW the host UI font "
           "(min_chrome_px %s < host_px %s)." % (min_chrome_px, host_px))
        return 1
    _w("PASS: no chrome font renders below the host UI font.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
