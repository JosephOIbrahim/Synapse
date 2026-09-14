"""BC-5's headroom at the SHIPPED density, in pixels.

The crit records BC-5 as passing at standard but prints no margin. D4 costs +8px
there and SYSTEM's shell base move costs another +8 on the faces. If the margin is
under 16, the spacing wave is blocked at the density artists actually run.

Reuses test_bc_wave's own helpers so the method cannot drift from the assertion.
No .exec() anywhere: a standalone script has no modal guard.
"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")
ROOT = "C:/Users/User/SYNAPSE"
for p in (ROOT, os.path.join(ROOT, "python")):
    if p not in sys.path:
        sys.path.insert(0, p)

from tests.panel import test_bc_wave as bc       # noqa: E402
from PySide6 import QtWidgets                    # noqa: E402

app = bc._app()                                  # QApplication BEFORE any QWidget
print("fonts loaded:", len(__import__("PySide6.QtGui", fromlist=["QFontDatabase"])
                            .QFontDatabase.families()))
H = bc.H
print("pane height H =", H, "| floor = 50% =", H * 0.5)

for profile in bc.PROFILES:
    p = bc._panel(profile)
    try:
        before = p._chat.height()
        p._input.set_user_height(p._input._floor)
        app.processEvents()
        bc._chat_face(p).layout().activate()
        app.processEvents()
        chat = p._chat.height()
        share = chat / H
        head = chat - (H * 0.5)
        print("%-8s density=%-8s chat=%4dpx  share=%.5f  headroom=%+.1fpx  %s"
              % (profile, p.property("density"), chat, share, head,
                 "PASS" if share >= 0.5 else "FAIL"))
    finally:
        p.close()
