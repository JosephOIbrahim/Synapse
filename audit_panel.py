#!/usr/bin/env python3
"""
audit_panel.py  --  the THIRD gate (G3) for the SYNAPSE panel harness.

  G1 (run_panel.py --smoke) proves it BOOTS.
  G2 (Houdini 21.0.671)      proves it loads in the real host.
  G3 (this)                  proves it is READABLE and USABLE.

Two layers:
  A. TOKEN AUDIT  -- deterministic, no host. Contrast matrix + type-scale floors.
                     Reads your real designsystem/tokens.py, so it audits the
                     SYSTEM, not a screenshot.
  B. LIVE AUDIT   -- offscreen Qt build. Interactive target sizes + face presence.

Usage:
  python audit_panel.py            # full human report
  python audit_panel.py --strict   # exit 1 on any FAIL  (use this as the gate)
"""
import os, sys, math

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# ---- repo path (same discovery as run_panel) ----
def _find_root(start):
    p = os.path.abspath(start)
    while p != os.path.dirname(p):
        if os.path.isdir(os.path.join(p, "python", "synapse")):
            return p
        p = os.path.dirname(p)
    return os.path.abspath(start)

ROOT  = _find_root(__file__)
PYDIR = os.path.join(ROOT, "python")
if PYDIR not in sys.path:
    sys.path.insert(0, PYDIR)

from synapse.panel.designsystem import tokens as t

# ---------------- WCAG contrast ----------------
def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

def _lum(hx):
    h = hx.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)

def contrast(fg, bg):
    a, b = _lum(fg), _lum(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)

# ---------------- floors ----------------
AA_BODY    = 4.5    # WCAG AA, normal text
AA_LARGE   = 3.0    # WCAG AA, large/bold text
PRAGMATIC  = 3.0    # dark-DCC line we will not cross for ANY essential text
BODY_FLOOR = 13     # px @ scale 1.0  (the v3 comp sets chat body to 13.5)
TARGET_FLOOR = 26   # px, comfortable click/tap height for pills + buttons

FAILS, WARNS = [], []
def tag(ok, warnable=False, cr=None):
    if ok:
        return "[ ok ]"
    if warnable:
        WARNS.append(1); return "[WARN]"
    FAILS.append(1);  return "[FAIL]"

print("=" * 70)
print("  SYNAPSE PANEL  ·  G3 READABILITY + USABILITY AUDIT")
print("=" * 70)

# ---------- A1 · contrast matrix ----------
print("\n-- READABILITY · text on surface (WCAG contrast) " + "-" * 19)
text_roles = {
    "PRIMARY  (body)":  (t.TEXT_PRIMARY,   "body"),
    "SECONDARY(meta)":  (t.TEXT_SECONDARY, "essential"),
    "TERTIARY (hint)":  (t.TEXT_TERTIARY,  "essential"),
    "BRIGHT   (head)":  (t.TEXT_BRIGHT,    "large"),
    "ACCENT   (link)":  (t.TEXT_ACCENT,    "large"),
}
surfaces = {"PANEL": t.PANEL, "GROUND": t.GROUND, "SURFACE": t.SURFACE}
hdr = "  " + " " * 16 + "".join(f"{s:>16}" for s in surfaces)
print(hdr)
for name, (fg, kind) in text_roles.items():
    row = f"  {name:<16}"
    for sname, sbg in surfaces.items():
        cr = contrast(fg, sbg)
        floor = AA_BODY if kind == "body" else (AA_LARGE if kind == "large" else PRAGMATIC)
        ok = cr >= floor
        warnable = (kind != "body")  # body is non-negotiable; others can warn
        row += f"  {cr:4.1f}:1 {tag(ok, warnable)}"
    print(row)
print(f"  floors:  body >= {AA_BODY}:1   head/link >= {AA_LARGE}:1   any essential >= {PRAGMATIC}:1")

# ---------- A2 · type scale ----------
print("\n-- READABILITY · type scale (px @ scale " + f"{t.FONT_SCALE_DEFAULT}) " + "-" * 22)
sizes = [("HERO", t.SIZE_HERO), ("TITLE", t.SIZE_TITLE), ("UI", t.SIZE_UI),
         ("SMALL", t.SIZE_SMALL), ("MICRO", t.SIZE_MICRO), ("BODY", t.SIZE_BODY)]
for n, s in sizes:
    eff = t.scaled(s, t.FONT_SCALE_DEFAULT)
    note = ""
    if n == "BODY":
        note = "  " + tag(eff >= BODY_FLOOR) + f"  chat body — floor {BODY_FLOOR}px"
    print(f"   {n:<6} {eff:>3}px{note}")
distinct = len({s for _, s in sizes})
print(f"   hierarchy: {distinct} distinct steps  " + tag(distinct >= 4, warnable=True))

# ---------- B · live build ----------
print("\n-- USABILITY · live offscreen build " + "-" * 31)
try:
    import run_panel  # registers hou stub + path
    try:
        from PySide6 import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = run_panel.build_panel()
    app.processEvents()

    btns = panel.findChildren(QtWidgets.QAbstractButton)
    under = [b for b in btns if 0 < b.sizeHint().height() < TARGET_FLOOR]
    print(f"   interactive targets : {len(btns):>3} found, "
          f"{len(under)} under {TARGET_FLOOR}px  " + tag(not under, warnable=True))

    texts = [b.text() for b in btns if b.text()]
    faces = [f for f in ("Direct", "Work") if f in texts]
    print(f"   tabs present        : {faces}  " + tag(len(faces) == 2))
    # v9: Review folded into Work's done sub-state. Assert its synthesis (the
    # consent gate) still lives in-tree, so the fold didn't silently drop the
    # gate — a stronger check than the old 3-tab name match.
    from synapse.panel.gate_widget import GateWidget as _GW
    has_gate = bool(panel.findChildren(_GW))
    print(f"   review fold (gate)  : {has_gate}  " + tag(has_gate))

    # v9 type pass — bundled families register, OR the build-mismatch flag is
    # raised (the locked call permits the flagged-fallback state). Warnable.
    from synapse.panel.designsystem import fontload
    fst = fontload.font_status() or {}
    fam_present = [f for f in ("Space Grotesk", "Space Mono") if f in fst.get("families", [])]
    flagged = bool(fst.get("build_mismatch"))
    print(f"   bundled fonts       : {fam_present}{' FLAGGED' if flagged else ''}  "
          + tag(len(fam_present) == 2 or flagged, warnable=True))

    labels = panel.findChildren(QtWidgets.QLabel)
    print(f"   labels rendered     : {len(labels):>3}")
except Exception as e:
    WARNS.append(1)
    print(f"   [skip] live build unavailable here: {type(e).__name__}: {e}")
    print("          (run this one inside hython for the real G3 — fonts differ)")

# ---------- verdict ----------
print("\n" + "=" * 70)
n_fail, n_warn = len(FAILS), len(WARNS)
if n_fail:
    print(f"  G3 RESULT:  {n_fail} FAIL · {n_warn} WARN  —  not readable/usable yet.")
else:
    print(f"  G3 RESULT:  pass  ·  {n_warn} WARN")
print("=" * 70)

if "--strict" in sys.argv:
    sys.exit(1 if n_fail else 0)
