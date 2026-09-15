# Qt widget-tree walk: locate SynapsePanel instance(s) and everything adjacent.
# Uses the SAME import idiom as the panel itself (PySide6, PySide2 fallback).
import json, sys, io

try:
    from PySide6 import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore

out = {}

def widget_info(w, depth):
    geo = None
    try:
        g = w.geometry()
        geo = [g.x(), g.y(), g.width(), g.height()]
    except Exception as e:
        geo = ["ERR", str(e)[:40]]
    vis = None
    try:
        vis = w.isVisible()
    except Exception as e:
        vis = "ERR"
    return {
        "class": w.__class__.__name__,
        "objname": w.objectName() or "",
        "geo": geo,
        "visible": vis,
        "children": len(w.findChildren(QtCore.QObject)) if False else None,
    }

def walk(w, depth, path, results):
    cls = w.__class__.__name__
    name = w.objectName() or ""
    info = widget_info(w, depth)
    info["path"] = path
    # classify interesting widgets
    is_synapse = "Synapse" in cls or "synapse" in name.lower() or "Synapse" in name
    is_panel_holder = cls in ("QStackedWidget", "QTabWidget", "QTabBar", "QSplitter", "Pane", "QScrollArea")
    results.append(info)
    # recurse into children (limit depth to avoid explosion)
    try:
        kids = w.findChildren(QtWidgets.QWidget)
    except Exception:
        kids = []
    # We only recurse into immediate children of interest to keep output bounded
    for child in w.children():
        if isinstance(child, QtWidgets.QWidget):
            child_cls = child.__class__.__name__
            child_name = child.objectName() or ""
            interesting = (
                is_synapse or
                "Synapse" in child_cls or "synapse" in child_name.lower() or
                "PythonPanel" in child_cls or "Pane" in child_cls or
                "Tab" in child_cls or "Splitter" in child_cls or
                child_cls in ("QStackedWidget", "QWidget", "QFrame", "QScrollArea", "QToolButton")
            )
            if interesting and depth < 6:
                walk(child, depth + 1, path + "/" + (child_name or child_cls), results)

tops = []
try:
    for w in QtWidgets.QApplication.topLevelWidgets():
        wd = widget_info(w, 0)
        wd["path"] = "/" + (w.objectName() or w.__class__.__name__)
        tops.append(wd)
except Exception as e:
    out["toplevel_err"] = str(e)[:200]

out["top_level_count"] = len(tops)

# Find the main window, then do a bounded walk for Synapse + panel-holder widgets
main_win = None
for w in QtWidgets.QApplication.topLevelWidgets():
    try:
        if w.windowTitle() and "Houdini" in w.windowTitle():
            main_win = w
            break
    except Exception:
        pass

walked = []
if main_win is not None:
    out["main_window_title"] = main_win.windowTitle()
    walk(main_win, 0, "/main", walked)
else:
    out["main_window_title"] = None

# Also search ALL widgets app-wide for SynapsePanel class instances
synapse_found = []
for w in QtWidgets.QApplication.allWidgets():
    cls = w.__class__.__name__
    name = w.objectName() or ""
    if "Synapse" in cls or "synapse" in name.lower():
        info = widget_info(w, 0)
        par = w.parent()
        info["parent"] = par.__class__.__name__ if par is not None else None
        info["parent_name"] = par.objectName() if par is not None else None
        info["objname"] = name
        synapse_found.append(info)

out["synapse_widgets"] = synapse_found
out["walk_summary"] = walked[:80]
out["walk_total"] = len(walked)

with open(r"C:\Users\User\SYNAPSE\docs\harness\notes\panel_diag_qtwalk.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
