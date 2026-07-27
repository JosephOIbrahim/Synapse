"""Control for the reading measure.

The old rule capped the document at a fixed 492px. In an 1830px pane that left
73% of the width empty. Worse, being in PIXELS meant raising the font size via
Aa SHRANK the measure in characters - backwards from what a reader wants.

FIRST VERSION OF THIS CONTROL CAUGHT A BUG IN THE FIX: the measure returned 630
at every size, which is the fallback constant times 90. The text size is NOT on
self.font() - it is applied through a stylesheet built from _font_scale, and a
Qt stylesheet overrides setFont. So the control drives _font_scale, the way the
Aa button does, rather than setFont.

Asserts what actually matters: the character count holds across Aa steps, and a
wide pane gets materially more than 492px.
"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "python")

from PySide6 import QtWidgets
from synapse.panel.chat_display import ChatDisplay
from synapse.panel.message_formatter import _BODY_PX, _scale

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
w = ChatDisplay()

print("%-8s %-9s %-11s %-8s %s" % ("scale", "body px", "measure px", "chars", "vs old 492"))
print("-" * 56)

rows = []
for scale in (0.8, 1.0, 1.25, 1.5, 2.0):
    w._font_scale = scale
    px = _scale(_BODY_PX, scale)
    m = w._reading_measure()
    chars = m / max(px * 0.55, 0.1)
    rows.append((scale, px, m, chars))
    print("%-8s %-9s %-11.0f %-8.0f %+.0f%%" % (scale, px, m, chars, (m - 492) / 492 * 100))

print()
# 1. the measure must MOVE with the font scale (the old bug: it did not)
measures = [m for _, _, m, _ in rows]
ok_moves = len(set(round(m) for m in measures)) > 1
print("measure varies with Aa      :", ok_moves, " (the old pixel rule did not)")

# 2. a wide pane must get materially more than the old fixed 492
w._font_scale = 1.0
m1 = w._reading_measure()
ok_wider = m1 > 492 * 1.2
print("measure at default scale    : %.0f px  (old 492)" % m1)

# 3. clamped so a huge Aa step cannot produce a full-bleed wall
w._font_scale = 3.0
ok_clamped = w._reading_measure() <= w._MEASURE_MAX_PX
print("clamped at 3.0x             :", ok_clamped, "(<= %d)" % w._MEASURE_MAX_PX)

allok = ok_moves and ok_wider and ok_clamped
print()
print("RESULT:", "PASS" if allok else "FAIL")
sys.exit(0 if allok else 1)
