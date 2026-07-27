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
pixel -- that is the assertable form.

WHY THIS CHECK CAN FAIL (Law 1): point any panel view at ``#00D4FF`` and the
CYAN row goes non-zero and the exit code flips to 1. Verified by mutation, not
asserted -- see H4's receipt.
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
TOL = 8  # per-channel tolerance: antialiasing moves an edge pixel a little


def census(directory):
    """{view: {accent: pixel_count}} for every PNG in ``directory``."""
    import numpy as np
    from PySide6 import QtGui, QtWidgets

    _ = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    out = {}
    for path in sorted(glob.glob(os.path.join(directory, "*.png"))):
        img = QtGui.QImage(path).convertToFormat(QtGui.QImage.Format.Format_RGB888)
        w, h = img.width(), img.height()
        ptr = img.constBits()
        arr = np.frombuffer(ptr, dtype=np.uint8, count=img.sizeInBytes())
        # Qt pads each scanline to a 4-byte boundary; index by bytesPerLine.
        arr = arr.reshape(h, img.bytesPerLine())[:, : w * 3].reshape(h, w, 3)
        arr = arr.astype(np.int16)
        counts = {}
        for name, rgb in TARGETS.items():
            hit = (np.abs(arr - np.array(rgb, dtype=np.int16)) <= TOL).all(axis=2)
            n = int(hit.sum())
            if n:
                counts[name] = n
        out[os.path.basename(path)[:-4]] = counts
    return out


def _totals(c):
    tot = {k: 0 for k in TARGETS}
    for counts in c.values():
        for k, v in counts.items():
            tot[k] += v
    return tot


def main(argv):
    if not argv:
        sys.stderr.write(__doc__)
        return 2
    dirs = [d if os.path.isabs(d) else os.path.join(_ROOT, d) for d in argv]
    censuses = [census(d) for d in dirs]

    for d, c in zip(dirs, censuses):
        sys.stdout.write("\n== %s ==\n" % os.path.relpath(d, _ROOT).replace("\\", "/"))
        for view in sorted(c):
            sys.stdout.write("  %-22s %s\n" % (view, c[view] or "-"))
        sys.stdout.write("  %-22s %s\n" % ("TOTAL", _totals(c)))

    rc = 0
    if len(dirs) == 2:
        before, after = _totals(censuses[0]), _totals(censuses[1])
        sys.stdout.write("\n== DIFF (after - before) ==\n")
        for k in TARGETS:
            sys.stdout.write("  %-12s %+d   (%d -> %d)\n"
                             % (k, after[k] - before[k], before[k], after[k]))
        if after["LEGACY_CYAN"] != 0:
            sys.stdout.write("\nFAIL: %d legacy-cyan pixels survive in the after set:\n"
                             % after["LEGACY_CYAN"])
            for view, counts in sorted(censuses[1].items()):
                if counts.get("LEGACY_CYAN"):
                    sys.stdout.write("   %s : %d\n" % (view, counts["LEGACY_CYAN"]))
            rc = 1
        else:
            sys.stdout.write("\nOK: zero legacy-cyan pixels in the after set.\n")

    with open(os.path.join(_ROOT, "harness", "notes",
                           "panel_accent_census.json"), "w", encoding="utf-8") as f:
        json.dump({"schema": "panel_accent_census/v1",
                   "tolerance_per_channel": TOL,
                   "targets": {k: "#%02X%02X%02X" % v for k, v in TARGETS.items()},
                   "sets": {os.path.relpath(d, _ROOT).replace("\\", "/"): c
                            for d, c in zip(dirs, censuses)}}, f, indent=2)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
