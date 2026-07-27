"""H4 ORACLE (rendered half): count ACCENT PIXELS per view in a panel_shot run.

The source-level oracle proves there is one token authority. This proves what the
artist actually sees. They are different claims and both are needed: a re-export
could be correct in source while a hardcoded literal at a call site still paints
the old accent, and only a pixel count catches that.

Run:
    hython3.13 harness/notes/panel_accent_census.py design/repair_h4/before \
                                                    design/repair_h4/after

With one directory it prints that directory's census. With two it prints the
DIFF, and exits non-zero if the "after" side still contains any legacy-cyan
pixel -- that is the assertable form. ``--selftest`` runs the reader control
alone.

WHY THIS CHECK CAN FAIL (Law 1): point any panel view at ``#00D4FF`` and the
widest-tolerance CYAN row goes non-zero and the exit code flips to 1. Proven by
``selftest()``, which paints synthetic frames and requires the reader to find
them -- a control, not a claim. The census refuses to report at all if that
control fails.

THE TOLERANCE LADDER, AND WHY A SINGLE TOLERANCE WAS WRONG
----------------------------------------------------------
The first version of this script counted exact matches at +-8 per channel and
asserted it would catch any view painting the legacy cyan. It would not, and
two views in the very first BEFORE set proved it: context_bar and hda_describe
were both bound to #00D4FF in source and both scored ZERO. Small antialiased
glyph strokes almost never reach the pure colour -- context_bar's cyan path
text had 0 pixels within +-8, 2 within +-24 and 31 within +-48.

So a single tight tolerance UNDERCOUNTS text, and a leg could have claimed a
clean sweep with cyan text still on screen. The census now reports a ladder
(8 / 24 / 48) and gates on the WIDEST band, because "no pixel is even close to
the legacy cyan" is the claim worth making. The tight bands are kept as a
saturation signal, not as the verdict.

WHAT THE WIDE BAND CANNOT DO
----------------------------
+-48 is the right band for the CYAN verdict and the wrong band for comparing
the two greens. LEGACY_CYAN (0,212,255) is 143 away from SIGNAL in red alone,
so nothing else can be mistaken for it at any band on this ladder -- the gate
is safe. But OK_SOFT (111,191,142) and CONIFEROUS (110,143,114) are 1 apart in
red and exactly 48 apart in green, so at +-48 they match each other's regions
and both rows inflate. Read the OK_SOFT -> CONIFEROUS migration off the +-8 row
(122 -> 0 and 0 -> 130), never off +-48.
"""

import os
import sys
import glob
import json

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

# The accents under audit. LEGACY_CYAN is the token the repair removes; SIGNAL is
# the single surviving accent; the two status greens are the CONIFEROUS swap.
TARGETS = {
    "LEGACY_CYAN": (0x00, 0xD4, 0xFF),
    "SIGNAL": (0x8F, 0xB3, 0xD9),
    "OK_SOFT": (0x6F, 0xBF, 0x8E),
    "CONIFEROUS": (0x6E, 0x8F, 0x72),
    "WARM": (0xFF, 0x77, 0x59),
}

TOLERANCES = (8, 24, 48)   # the ladder; the WIDEST band is the verdict
GATE_TOL = TOLERANCES[-1]


def _load(path):
    """A path -> (h, w, 3) int16 RGB array, scanline padding removed."""
    import numpy as np
    from PySide6 import QtGui
    img = QtGui.QImage(path).convertToFormat(QtGui.QImage.Format.Format_RGB888)
    h, w = img.height(), img.width()
    arr = np.frombuffer(img.constBits(), dtype=np.uint8, count=img.sizeInBytes())
    # Qt pads each scanline to a 4-byte boundary; index by bytesPerLine.
    return arr.reshape(h, img.bytesPerLine())[:, : w * 3].reshape(
        h, w, 3).astype(np.int16)


def _count(arr, rgb, tol):
    import numpy as np
    return int((np.abs(arr - np.array(rgb, dtype=np.int16)) <= tol).all(axis=2).sum())


def census(directory):
    """``{view: {accent: {tol: count}}}`` for every PNG in ``directory``."""
    from PySide6 import QtWidgets
    _ = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    out = {}
    for path in sorted(glob.glob(os.path.join(directory, "*.png"))):
        arr = _load(path)
        counts = {}
        for name, rgb in TARGETS.items():
            ladder = {t: _count(arr, rgb, t) for t in TOLERANCES}
            if ladder[GATE_TOL]:
                counts[name] = ladder
        out[os.path.basename(path)[:-4]] = counts
    return out


def _totals(c, tol):
    tot = {k: 0 for k in TARGETS}
    for counts in c.values():
        for k, ladder in counts.items():
            tot[k] += ladder[tol]
    return tot


def _fmt(counts, tol):
    shown = {k: v[tol] for k, v in counts.items() if v[tol]}
    return shown or "-"


def selftest():
    """CONTROL (R60 / Law 1): paint a synthetic frame in each target colour and
    require the reader to find it. A reader that cannot see a painted accent
    reports zero for the right reason and the wrong one identically.

    Also asserts the ladder is MONOTONIC (a wider tolerance never finds less)
    and that a colour far from every target scores zero at the gate band -- the
    negative direction, without which "found it" proves nothing.
    """
    import numpy as np
    ok = True
    for name, rgb in TARGETS.items():
        frame = np.tile(np.array(rgb, dtype=np.int16), (4, 4, 1))
        ladder = [_count(frame, rgb, t) for t in TOLERANCES]
        if ladder[-1] != 16:
            sys.stdout.write(
                "  CONTROL FAIL: %s painted but not found (%r)\n" % (name, ladder))
            ok = False
        if sorted(ladder) != ladder:
            sys.stdout.write(
                "  CONTROL FAIL: %s ladder not monotonic %r\n" % (name, ladder))
            ok = False
    far = np.tile(np.array((255, 0, 255), dtype=np.int16), (4, 4, 1))
    for name, rgb in TARGETS.items():
        if _count(far, rgb, GATE_TOL):
            sys.stdout.write(
                "  CONTROL FAIL: magenta matched %s at the gate band\n" % name)
            ok = False
    sys.stdout.write("reader control: %s\n" % ("PASS" if ok else "FAIL"))
    return ok


def main(argv):
    if "--selftest" in argv:
        return 0 if selftest() else 3
    if not argv:
        sys.stderr.write(__doc__)
        return 2
    if not selftest():
        sys.stdout.write("refusing to report: the reader failed its own control\n")
        return 3

    dirs = [d if os.path.isabs(d) else os.path.join(_ROOT, d) for d in argv]
    censuses = [census(d) for d in dirs]

    for d, c in zip(dirs, censuses):
        sys.stdout.write("\n== %s   (counts at tol +-%d) ==\n"
                         % (os.path.relpath(d, _ROOT).replace("\\", "/"), GATE_TOL))
        for view in sorted(c):
            sys.stdout.write("  %-22s %s\n" % (view, _fmt(c[view], GATE_TOL)))
        sys.stdout.write("  %-22s %s\n" % ("TOTAL", _totals(c, GATE_TOL)))

    rc = 0
    if len(dirs) == 2:
        sys.stdout.write("\n== DIFF (before -> after), per tolerance band ==\n")
        for tol in TOLERANCES:
            before, after = _totals(censuses[0], tol), _totals(censuses[1], tol)
            sys.stdout.write("  tol +-%-3d  " % tol)
            sys.stdout.write("   ".join(
                "%s %d->%d" % (k, before[k], after[k]) for k in TARGETS))
            sys.stdout.write("\n")

        after_gate = _totals(censuses[1], GATE_TOL)
        if after_gate["LEGACY_CYAN"]:
            sys.stdout.write(
                "\nFAIL: %d pixels within +-%d of the legacy cyan survive:\n"
                % (after_gate["LEGACY_CYAN"], GATE_TOL))
            for view, counts in sorted(censuses[1].items()):
                n = counts.get("LEGACY_CYAN", {}).get(GATE_TOL, 0)
                if n:
                    sys.stdout.write("   %s : %d\n" % (view, n))
            rc = 1
        else:
            sys.stdout.write("\nOK: no pixel within +-%d of the legacy cyan in the "
                             "after set.\n" % GATE_TOL)

    with open(os.path.join(_ROOT, "harness", "notes",
                           "panel_accent_census.json"), "w", encoding="utf-8") as f:
        json.dump({"schema": "panel_accent_census/v2",
                   "tolerance_ladder": list(TOLERANCES),
                   "gate_tolerance": GATE_TOL,
                   "reader_control": "passed",
                   "targets": {k: "#%02X%02X%02X" % v for k, v in TARGETS.items()},
                   "sets": {os.path.relpath(d, _ROOT).replace("\\", "/"): c
                            for d, c in zip(dirs, censuses)}}, f, indent=2)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
