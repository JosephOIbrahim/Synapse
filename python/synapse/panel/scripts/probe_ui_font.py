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


if __name__ == "__main__":
    probe()
