# Probe 3: pin the DsRailMeter — parent chain, panel attrs, who shows it.
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

def find_by_objname(name):
    for w in QtWidgets.QApplication.allWidgets():
        if w.objectName() == name:
            return w
    return None

rail = find_by_objname("DsRailMeter")
out["rail_found"] = rail is not None
if rail is not None:
    out["rail_geo"] = geo_of(rail)
    out["rail_visible"] = rail.isVisible()
    out["rail_isHidden"] = rail.isHidden()
    # parent chain
    chain = []
    node = rail
    d = 0
    while node is not None and d < 10:
        chain.append({
            "class": node.__class__.__name__,
            "name": node.objectName() or "",
            "geo": geo_of(node),
            "visible": node.isVisible(),
        })
        node = node.parent() if hasattr(node, "parent") else None
        d += 1
    out["rail_parent_chain"] = chain
    # Python attrs if it's the panel's _observe
    try:
        out["rail_prop_busy"] = rail.property("busy")
    except Exception as e:
        out["rail_prop_busy"] = str(e)[:60]

# Find the SynapsePanel instance and dump its key attrs + immediate children geometry
syn = None
for w in QtWidgets.QApplication.allWidgets():
    if w.__class__.__name__ == "SynapsePanel":
        syn = w
        break
if syn is not None:
    out["syn_geo"] = geo_of(syn)
    kids = []
    for c in syn.children():
        if isinstance(c, QtWidgets.QWidget):
            kids.append({
                "class": c.__class__.__name__,
                "name": c.objectName() or "",
                "geo": geo_of(c),
                "visible": c.isVisible(),
            })
    out["syn_children"] = kids
    # _region_cache
    try:
        rc = getattr(syn, "_region_cache", None)
        if rc:
            out["region_cache"] = {k: geo_of(v) for k, v in rc.items()}
        else:
            out["region_cache"] = None
    except Exception as e:
        out["region_cache"] = str(e)[:120]
    # _observe attr
    try:
        ob = getattr(syn, "_observe", None)
        out["syn_observe"] = {
            "same_as_rail": ob is rail,
            "geo": geo_of(ob) if ob else None,
            "visible": ob.isVisible() if ob else None,
            "isHidden": ob.isHidden() if ob else None,
        }
    except Exception as e:
        out["syn_observe"] = str(e)[:120]

with open(r"C:\Users\User\SYNAPSE\docs\harness\notes\panel_diag_rail.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
