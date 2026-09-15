# Probe 4: full widget-tree walk from the main window, skipping SynapsePanel internals.
# Goal: find every pane/tab content widget and any small/empty pane adjacent to Synapse.
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

mw = None
for w in QtWidgets.QApplication.topLevelWidgets():
    try:
        if w.windowTitle() and "Houdini" in w.windowTitle():
            mw = w
            break
    except Exception:
        pass
out["main_found"] = mw is not None

# Full recursive walk, depth-capped, skipping SynapsePanel subtree.
# Record every widget; mark the interesting ones.
results = []
SKIP_CLASSES = {"SynapsePanel"}

def walk(w, depth, path):
    if depth > 9:
        return
    cls = w.__class__.__name__
    name = w.objectName() or ""
    g = geo_of(w)
    try:
        vis = w.isVisible()
    except Exception:
        vis = None
    entry = {
        "class": cls,
        "name": name,
        "geo": g,
        "visible": vis,
        "path": path,
    }
    results.append(entry)
    if cls in SKIP_CLASSES:
        return
    for c in w.children():
        if isinstance(c, QtWidgets.QWidget):
            cname = c.objectName() or ""
            walk(c, depth + 1, path + "/" + (cname or c.__class__.__name__))

if mw is not None:
    walk(mw, 0, "/main")

out["walk_total"] = len(results)
# Keep the full list but it may be long; write it all.
out["walk"] = results

# Also: find the Log Viewer python panel content. Its pane tab is panetab15.
# Look for any widget whose class/name suggests a log viewer or text edit.
logish = []
for w in QtWidgets.QApplication.allWidgets():
    cls = w.__class__.__name__
    name = w.objectName() or ""
    if any(k in cls.lower() or k in name.lower() for k in ("log", "textedit", "plaintext", "console")):
        logish.append(info(w))
out["logish_widgets"] = logish

with open(r"C:\Users\User\SYNAPSE\docs\harness\notes\panel_diag_tree.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
