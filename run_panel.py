"""SYNAPSE panel harness — one file, drop it anywhere in your SYNAPSE folder.

    python run_panel.py            # open the panel in a window
    python run_panel.py --smoke    # build it offscreen, print OK/FAIL, exit

Press F5 in the window to hot-reload after editing any synapse.panel.* module.

It finds the repo by looking for python/synapse/panel/synapse_panel.py, walking up
from wherever this file lives (and from where you ran it), so it works in the
SYNAPSE root, in a subfolder, or run from anywhere inside the tree.
"""

import os
import sys
import traceback


# ----- find the SYNAPSE repo root, robustly --------------------------------
def _find_root(start):
    d = os.path.abspath(start)
    for _ in range(10):
        if os.path.isfile(os.path.join(d, "python", "synapse", "panel", "synapse_panel.py")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    return None


_ROOT = _find_root(os.path.dirname(os.path.abspath(__file__))) or _find_root(os.getcwd())

if not _ROOT:
    print("Couldn't find the SYNAPSE code (python/synapse/panel/synapse_panel.py).")
    print("Put this file inside your SYNAPSE folder, then run it again.")
    sys.exit(1)

for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ----- tiny hou stub so the panel renders 'alive' outside Houdini ----------
class _Node:
    def __init__(self, path, parent_path=None):
        self._path, self._parent_path = path, parent_path

    def path(self):
        return self._path

    def parent(self):
        return _Node(self._parent_path) if self._parent_path else None


class _Hou:
    class _HipFile:
        def basename(self):
            return "untitled.hip"

    class _PaneTab:
        def pwd(self):
            return _Node("/stage")

    class _UI:
        def paneTabOfType(self, *_a, **_k):
            return _Hou._PaneTab()

        def displayMessage(self, msg, *_a, **_k):
            print("[hou.ui]", msg)

    class _PaneTabType:
        NetworkEditor = "NetworkEditor"

    class _SeverityType:
        Message = "Message"
        Warning = "Warning"
        Error = "Error"

    hipFile = _HipFile()
    ui = _UI()
    paneTabType = _PaneTabType()
    severityType = _SeverityType()
    _selected = [_Node("/stage/crystal_glass", parent_path="/stage")]

    @staticmethod
    def frame():
        return 1

    @staticmethod
    def selectedNodes():
        return list(_Hou._selected)


sys.modules["hou"] = _Hou


# ----- Qt (Houdini ships PySide6); guide the user if it's missing ----------
_SMOKE = "--smoke" in sys.argv
if _SMOKE:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtWidgets
    from PySide6.QtGui import QShortcut, QKeySequence
except ImportError:
    try:
        from PySide2 import QtWidgets
        from PySide2.QtWidgets import QShortcut
        from PySide2.QtGui import QKeySequence
    except ImportError:
        print("PySide6 isn't available in this Python (%s)." % sys.executable)
        print("The panel needs Houdini's Python, which already includes it. Try:")
        print('  & "C:\\Program Files\\Side Effects Software\\Houdini 21.0.671\\bin\\hython.exe" run_panel.py')
        print("(or: pip install PySide6  — if there's a wheel for your Python version)")
        sys.exit(1)

_PANEL_BG = "#2B2B2B"  # Houdini pane grey, so the frame doesn't lie about the fit


def _flush_synapse():
    for name in sorted(k for k in sys.modules if k.startswith("synapse.")):
        del sys.modules[name]
    sys.modules.pop("synapse", None)


def build_panel():
    _flush_synapse()
    from synapse.panel.synapse_panel import createInterface
    return createInterface()


class Harness(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SYNAPSE — panel harness  ·  F5 to reload")
        self.resize(380, 940)
        self.setStyleSheet("QMainWindow{background:%s;}" % _PANEL_BG)
        self._mount()
        QShortcut(QKeySequence("F5"), self).activated.connect(self._reload)

    def _mount(self):
        self.setCentralWidget(build_panel())

    def _reload(self):
        old = self.centralWidget()
        if old is not None:
            old.setParent(None)
            old.deleteLater()
        self._mount()
        print("[harness] reloaded")


def main():
    app = QtWidgets.QApplication(sys.argv)
    if _SMOKE:
        try:
            w = build_panel()
            app.processEvents()
        except Exception:
            print("SMOKE FAIL:\n")
            traceback.print_exc()
            return 1
        print("SMOKE OK — %s instantiated" % type(w).__name__)
        return 0
    Harness().show()
    return app.exec() if hasattr(app, "exec") else app.exec_()


if __name__ == "__main__":
    sys.exit(main())
