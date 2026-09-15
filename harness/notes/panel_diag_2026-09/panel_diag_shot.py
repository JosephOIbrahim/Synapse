# Probe 5: grab the main Houdini window to a PNG so we can SEE the layout.
import json

try:
    from PySide6 import QtWidgets, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtGui

out = {}

mw = None
for w in QtWidgets.QApplication.topLevelWidgets():
    try:
        if w.windowTitle() and "Houdini" in w.windowTitle():
            mw = w
            break
    except Exception:
        pass

if mw is None:
    out["error"] = "no main window"
else:
    try:
        pm = mw.grab()
        path = r"C:\Users\User\SYNAPSE\docs\harness\notes\panel_diag_shot.png"
        ok = pm.save(path, "PNG")
        out["saved"] = ok
        out["size"] = [pm.width(), pm.height()]
    except Exception as e:
        out["error"] = str(e)[:200]

# Also grab just the SynapsePanel region
syn = None
for w in QtWidgets.QApplication.allWidgets():
    if w.__class__.__name__ == "SynapsePanel":
        syn = w
        break
if syn is not None:
    try:
        pm2 = syn.grab()
        path2 = r"C:\Users\User\SYNAPSE\docs\harness\notes\panel_diag_synapse.png"
        ok2 = pm2.save(path2, "PNG")
        out["synapse_saved"] = ok2
        out["synapse_size"] = [pm2.width(), pm2.height()]
    except Exception as e:
        out["synapse_err"] = str(e)[:200]

with open(r"C:\Users\User\SYNAPSE\docs\harness\notes\panel_diag_shot.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
