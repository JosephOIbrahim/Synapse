import os, sys, traceback
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_PANEL_SETTINGS", os.path.join(os.environ.get("TEMP","."), "probe_toplevel_settings.json"))
sys.path[:0] = [os.getcwd(), os.path.join(os.getcwd(), "python")]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
_orig_setVisible = QtWidgets.QWidget.setVisible
_orig_show = QtWidgets.QWidget.show
def _sv(self, v):
    if v and self.objectName() == "DsRailMeter" and self.parent() is None:
        print("== DsRailMeter.setVisible(True) from:", flush=True); traceback.print_stack(limit=8)
    return _orig_setVisible(self, v)
def _sh(self):
    if self.objectName() == "DsRailMeter" and self.parent() is None:
        print("== DsRailMeter.show() from:", flush=True); traceback.print_stack(limit=8)
    return _orig_show(self)
QtWidgets.QWidget.setVisible = _sv; QtWidgets.QWidget.show = _sh
import run_panel
panel = run_panel.build_panel(); app.processEvents()
print("visible after build:", panel._observe.isVisible(), "parent:", panel._observe.parent(), flush=True)
