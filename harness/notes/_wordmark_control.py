import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "python")

from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from synapse.panel.designsystem import tokens as t
from synapse.panel.designsystem import fontload

print("WORDMARK tracking em :", t.TRACKING_EM.get("WORDMARK"))
print("  at 14px            : %.2f px" % t.tracking_px("WORDMARK", 14))
print("BRAND (others keep)  :", t.TRACKING_EM.get("BRAND"),
      "-> %.2f px" % t.tracking_px("BRAND", 14))

f = fontload.tracked_font("WORDMARK", 14, scale=1.0, weight=600)
print("font weight          :", f.weight())
print("font letterSpacing   : %.2f" % f.letterSpacing())
print("TEXT_BRIGHT          :", t.TEXT_BRIGHT)
print("TEXT_PRIMARY (was)   :", t.TEXT_PRIMARY)

# The property that matters: heavier AND denser than what shipped.
old = fontload.tracked_font("BRAND", 14, scale=1.0, weight=400)
heavier = f.weight() > old.weight()
denser = f.letterSpacing() < old.letterSpacing()
print()
print("heavier than shipped :", heavier, "(%s -> %s)" % (old.weight(), f.weight()))
print("denser than shipped  :", denser, "(%.2f -> %.2f px)" % (old.letterSpacing(), f.letterSpacing()))
print("brighter             :", t.TEXT_BRIGHT != t.TEXT_PRIMARY)
print()
print("RESULT:", "PASS" if (heavier and denser) else "FAIL")
sys.exit(0 if (heavier and denser) else 1)
