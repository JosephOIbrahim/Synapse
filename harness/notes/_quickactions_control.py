"""Control for the quick-actions row breathing space.

Joe: the words in that menu feel claustrophobic, top and bottom.

They were: 4px of padding INSIDE each pill and 4px of margin OUTSIDE the row.
The type sat against the pill's own border with nothing beyond it either.

Asserts the vertical measurements changed and the horizontal ones did NOT - the
crowding was vertical, and widening the pills would have changed the row's
rhythm for no reason.
"""
import os, re, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "python")

from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from synapse.panel.quick_actions import QuickActionPills

bar = QuickActionPills()
css = bar._pill_stylesheet()

m = re.search(r"padding:\s*(\d+)px\s+(\d+)px", css)
vpad, hpad = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)

marg = bar._outer_layout.contentsMargins()
top, bottom = marg.top(), marg.bottom()
left, right = marg.left(), marg.right()

print("pill padding    : %dpx vertical / %dpx horizontal   (was 4 / 12)" % (vpad, hpad))
print("row margins     : %d top / %d bottom                (was 4 / 4)" % (top, bottom))
print("row h-margins   : %d left / %d right                (unchanged 8 / 8)" % (left, right))
print()
print("total breathing : %dpx per side  (was 8)" % (vpad + top))

ok_vpad = vpad > 4
ok_marg = top > 4 and bottom > 4
ok_h_untouched = hpad == 12 and left == 8 and right == 8
ok_modest = vpad <= 9 and top <= 8          # "a tiny bit more", not a redesign

print()
print("more vertical padding    :", ok_vpad)
print("more vertical margin     :", ok_marg)
print("horizontal UNTOUCHED     :", ok_h_untouched)
print("modest, not a redesign   :", ok_modest)

allok = ok_vpad and ok_marg and ok_h_untouched and ok_modest
print()
print("RESULT:", "PASS" if allok else "FAIL")
sys.exit(0 if allok else 1)
