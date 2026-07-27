"""Control for the reading-size selector.

It was ONE "Aa" button cycling five hidden steps, with a tooltip as the only
feedback: the options were invisible, the live state was invisible, and finding
a size meant clicking until it looked right and then overshooting.

Now three A's on a line, each drawn at the size it sets.

Asserts what the change was FOR - not that three widgets exist, but that the
control shows its state and that clicking one actually changes the reading size.
"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "python")

from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from synapse.panel.chat_panel import SynapseChatPanel
from synapse.panel.designsystem import tokens as t


p = SynapseChatPanel()
p.createInterface()   # Houdini calls this when the tab opens; the widgets are built here
btns = p._font_btns
print("size buttons        :", len(btns))
for (b, scale), (px, _, name) in zip(btns, p._SIZE_STEPS):
    print("   %-7s scale=%-5s label=%dpx  tip=%r" % (name, scale, b.font().pixelSize(), b.toolTip()))

def live_index():
    for i, (b, _) in enumerate(btns):
        if t.TEXT_BRIGHT in b.styleSheet():
            return i
    return -1

print()
start = live_index()
print("live at start       :", start, "(default scale %s)" % p._font_scale)

# click LARGE
p._set_font_scale(btns[-1][1])
after_large = live_index()
scale_large = p._font_scale
chat_large = p._chat.font_scale

# click SMALL
p._set_font_scale(btns[0][1])
after_small = live_index()
chat_small = p._chat.font_scale

print("after click LARGE   : live=%d  scale=%s  chat=%s" % (after_large, scale_large, chat_large))
print("after click SMALL   : live=%d  scale=%s  chat=%s" % (after_small, p._font_scale, chat_small))

ok_three   = len(btns) == 3
ok_sizes   = [b.font().pixelSize() for b, _ in btns] == [11, 14, 18]
ok_state   = start >= 0 and after_large == 2 and after_small == 0
ok_applies = chat_large != chat_small
ok_named   = all(n in b.toolTip() for (b, _), (_, _, n) in zip(btns, p._SIZE_STEPS))

print()
print("three targets            :", ok_three)
print("each drawn at its size   :", ok_sizes)
print("live one is marked       :", ok_state)
print("clicking changes reading :", ok_applies)
print("each names its size      :", ok_named)

allok = ok_three and ok_sizes and ok_state and ok_applies and ok_named
print()
print("RESULT:", "PASS" if allok else "FAIL")
sys.exit(0 if allok else 1)
