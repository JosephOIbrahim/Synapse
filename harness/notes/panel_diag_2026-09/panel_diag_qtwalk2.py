# Probe 2: parent chain + siblings of the SynapsePanel, plus all pane/tab/splitter geometry app-wide.
import json

try:
    from PySide6 import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore

out = {}

def geo_of(w):
    try:
        g = w.geometry()
        return [g.x(), g.y(), g.width(), g.height()]
    except Exception as e:
        return ["ERR", str(e)[:40]]

def info(w):
    return {
        "class": w.__class__.__name__,
        "name": w.objectName() or "",
        "geo": geo_of(w),
        "visible": w.isVisible(),
    }

# 1. Find SynapsePanel instance
syn = None
for w in QtWidgets.QApplication.allWidgets():
    if w.__class__.__name__ == "SynapsePanel":
        syn = w
        break
out["synapse_found"] = syn is not None
if syn is not None:
    chain = []
    node = syn
    depth = 0
    while node is not None and depth < 12:
        chain.append(info(node))
        node = node.parent() if hasattr(node, "parent") else None
        depth += 1
    out["synapse_parent_chain"] = chain

    # 2. Siblings: widgets sharing the SynapsePanel's parent
    par = syn.parent()
    sibs = []
    if par is not None:
        for c in par.children():
            if isinstance(c, QtWidgets.QWidget):
                sibs.append(info(c))
    out["synapse_parent_children"] = sibs

    # 3. Full subtree of the panel's grandparent (the pane host region)
    if par is not None and par.parent() is not None:
        gp = par.parent()
        gkids = []
        for c in gp.children():
            if isinstance(c, QtWidgets.QWidget):
                gkids.append(info(c))
        out["synapse_grandparent_children"] = gkids

# 4. All Pane / QTabWidget / QStackedWidget / QSplitter / QDockWidget app-wide
holders = []
for w in QtWidgets.QApplication.allWidgets():
    cls = w.__class__.__name__
    if cls in ("Pane", "QTabWidget", "QStackedWidget", "QSplitter", "QDockWidget", "QScrollArea", "QToolBox"):
        holders.append(info(w))
out["holder_widgets"] = holders
out["holder_count"] = len(holders)

# 5. Any visible widget with a small geometry (< 220px in either dimension) inside the main window
small = []
mw = None
for w in QtWidgets.QApplication.topLevelWidgets():
    try:
        if w.windowTitle() and "Houdini" in w.windowTitle():
            mw = w
            break
    except Exception:
        pass
if mw is not None:
    for w in QtWidgets.QApplication.allWidgets():
        if w.isVisible():
            try:
                g = w.geometry()
                if g.width() > 0 and g.height() > 0 and (g.width() < 220 or g.height() < 220):
                    small.append(info(w))
            except Exception:
                pass
out["small_visible_widgets"] = small
out["small_count"] = len(small)

with open(r"C:\Users\User\SYNAPSE\docs\harness\notes\panel_diag_qtwalk2.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
