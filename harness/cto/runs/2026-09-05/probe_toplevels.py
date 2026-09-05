import os, sys, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_PANEL_SETTINGS", os.path.join(os.environ.get("TEMP","."), "probe_toplevel_settings.json"))
sys.path[:0] = [os.getcwd(), os.path.join(os.getcwd(), "python")]
import run_panel
from PySide6 import QtWidgets, QtCore
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
def dump(tag):
    tops = [w for w in QtWidgets.QApplication.topLevelWidgets()]
    print(f"== {tag}: {len(tops)} top-level widgets")
    for w in tops:
        print(f"   {type(w).__module__}.{type(w).__name__:28} name={w.objectName()!r:26} visible={w.isVisible()!s:5} flags={int(w.windowFlags()) & 0xff:#x} geom={w.geometry().width()}x{w.geometry().height()} title={w.windowTitle()!r} parent={type(w.parent()).__name__ if w.parent() else None}")
dump("before build")
panel = run_panel.build_panel()
dump("after build (not shown)")
panel.show(); app.processEvents()
dump("after show")
panel.resize(340, 760); app.processEvents(); time.sleep(0.5); app.processEvents()
dump("after resize+settle")
print("PROBE DONE", flush=True)
