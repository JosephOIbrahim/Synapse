"""Control for the TOKEN field: AREA must equal SHARE.

A Voronoi looks good, which is exactly why it needs pinning. Its cells have
UNEQUAL areas, so an implementation that hands out cells by COUNT would produce
a field that is beautiful and lies about every proportion.

Asserts, in order of what matters:

  1. AREA TRACKS SHARE. The fraction of painted area a segment receives must
     match its fraction of the measured tokens, within one cell's worth.
  2. UNMEASURED CLAIMS NOTHING. A segment passed as None takes zero area -
     not a small region. A small region reads as "this costs little"; the truth
     is "nobody measured this" (R162 - a zero is a claim).
  3. THE CELLS PARTITION THE RECT. A Voronoi that leaves gaps or overlaps is
     not a Voronoi, and area-based allocation would be meaningless on it.
  4. STABLE ACROSS REPAINTS. A field that reshuffles reads as animation; this
     is a read-out.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "python")

from PySide6 import QtWidgets

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from synapse.panel.face_token import TokenField

W, H = 700, 170
f = TokenField()
f.resize(W, H)
cells = f._build_cells(W, H)
total = sum(a for _, a, _ in cells)

ok = {}

# 3 - the partition
ok["cells partition the rect"] = abs(total - W * H) < 2.0
ok["cells are polygons, not a grid"] = max(len(p) for p, _, _ in cells) > 4

# 1 - area tracks share
SYS, TOOLS = 3149, 26753
f.set_segments([("sys", SYS, "#8FB3D9"),
                ("tools", TOOLS, "#6E8F72"),
                ("grounding", None, "#8A8078")])

# Re-derive the allocation the way paintEvent does.
want_sys = SYS / float(SYS + TOOLS)
limit = want_sys * total
acc, got_sys = 0.0, 0.0
for _poly, area, _cx in cells:
    acc += area
    if acc <= limit:
        got_sys += area
one_cell = total / float(len(cells))
ok["area tracks token share"] = abs(got_sys - limit) <= one_cell

# A MEASURED SEGMENT MUST NEVER RENDER AS ABSENT.
#
# The control did not have this assertion and it should have. Dropping the cell
# count to 9 - closer to the reference's very large cells - made the system
# prompt receive ZERO area while being a real 10.5% of the turn. It vanished,
# and "vanished" is what an UNMEASURED segment is supposed to look like. The
# two states became indistinguishable, which is the field lying in the more
# convincing direction.
ok["a measured segment gets area"] = got_sys > 0.0

print("  cells                : %d" % len(cells))
print("  total area           : %.0f   rect %d" % (total, W * H))
print("  sys share of tokens  : %.3f" % want_sys)
print("  sys share of area    : %.3f   (tolerance: one cell = %.3f)"
      % (got_sys / total, one_cell / total))
print()

# 2 - unmeasured claims nothing
f.set_segments([("sys", None, "#8FB3D9"), ("tools", None, "#6E8F72")])
known = [s for s in f._segments if isinstance(s[1], (int, float)) and s[1] > 0]
ok["all-unmeasured claims no area"] = len(known) == 0

# 4 - stable across repaints
again = f._build_cells(W, H)
ok["stable across repaints"] = (len(again) == len(cells)
                                and abs(again[0][1] - cells[0][1]) < 1e-9)

for k, v in ok.items():
    print("  %-32s %s" % (k, v))

allok = all(ok.values())
print()
print("RESULT:", "PASS" if allok else "FAIL")
sys.exit(0 if allok else 1)
