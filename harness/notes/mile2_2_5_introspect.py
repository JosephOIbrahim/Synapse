"""Mile-2 §2.5 preflight: dir()-introspect the IConnectivityOracle backing
symbols against LIVE Houdini 21.0.671 (headless hython), and read-only exercise
the introspection LOGIC against real node types. Read-only: builds a throwaway
/obj network in this isolated hython process; nothing is saved, the user's
session is untouched. Emits JSON to stdout for harness/notes capture.

Run:  & $env:HYTHON harness/notes/mile2_2_5_introspect.py
"""
from __future__ import annotations

import json
import hou

R: dict = {"houdini": hou.applicationVersionString(), "symbols": {}, "values": {}, "errors": []}


def probe(name, fn):
    try:
        R["symbols"][name] = bool(fn())
    except Exception as e:  # noqa: BLE001 — probe must never crash the run
        R["symbols"][name] = False
        R["errors"].append(f"symbol {name}: {type(e).__name__}: {e}")


# --- module-level callables ---
probe("hou.node", lambda: callable(hou.node))
probe("hou.nodeType", lambda: callable(hou.nodeType))
probe("hou.nodeTypeCategories", lambda: callable(hou.nodeTypeCategories))

# --- category-string -> category object resolution ---
try:
    cats = hou.nodeTypeCategories()
    R["values"]["nodeTypeCategories_keys_sample"] = sorted(cats.keys())
except Exception as e:  # noqa: BLE001
    cats = {}
    R["errors"].append(f"nodeTypeCategories(): {type(e).__name__}: {e}")

# --- NodeType members (the type-level introspection surface) ---
NT_METHODS = ["maxNumInputs", "minNumInputs", "maxNumOutputs", "name",
              "category", "nameComponents", "inputLabels", "outputLabels"]
sop = cats.get("Sop")
box_nt = None
if sop is not None:
    try:
        box_nt = hou.nodeType(sop, "box")
    except Exception as e:  # noqa: BLE001
        R["errors"].append(f"hou.nodeType(Sop, box): {type(e).__name__}: {e}")
for m in NT_METHODS:
    probe(f"hou.NodeType.{m}", lambda m=m: hasattr(box_nt, m))

# --- real arity/output values for representative SOP types ---
def arity(cat_name, type_name):
    try:
        cat = cats[cat_name]
        nt = hou.nodeType(cat, type_name)
        return {
            "min": nt.minNumInputs(),
            "max": nt.maxNumInputs(),
            "outs": nt.maxNumOutputs(),
            "type_name": nt.name(),
            "cat_name": nt.category().name(),
        }
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}

R["values"]["box_Sop"] = arity("Sop", "box")        # expect 0 inputs
R["values"]["xform_Sop"] = arity("Sop", "xform")    # expect 1 input
R["values"]["merge_Sop"] = arity("Sop", "merge")    # expect variadic (sentinel max)
R["values"]["add_Vop"] = arity("Vop", "add")        # typed category
R["values"]["constant_Vop"] = arity("Vop", "constant")

# --- instance-level surface + the occupied-input logic, on a throwaway net ---
try:
    obj = hou.node("/obj")
    geo = obj.createNode("geo", "geo_probe")
    b = geo.createNode("box", "box1")
    m = geo.createNode("merge", "merge1")
    m.setInput(0, b)   # wire box -> merge.input0 (occupies input 0)
    R["values"]["instance"] = {
        "Node.type": hasattr(m, "type"),
        "Node.inputs": hasattr(m, "inputs"),
        "Node.inputConnections": hasattr(m, "inputConnections"),
        "Node.inputLabels": hasattr(m, "inputLabels"),
        "resolve_box": (b.type().name(), b.type().category().name()),
        "merge_inputConnections_indices": [c.inputIndex() for c in m.inputConnections()],
        "NodeConnection.inputIndex": all(hasattr(c, "inputIndex") for c in m.inputConnections()),
        "merge_inputs_len_nonNone": sum(1 for x in m.inputs() if x is not None),
    }
    # VOP instance data-type surface (type-compat feasibility)
    matnet = obj.createNode("matnet", "mat_probe")
    addv = matnet.createNode("add", "add1")
    R["values"]["vop_instance"] = {
        "VopNode.inputDataTypes": hasattr(addv, "inputDataTypes"),
        "VopNode.outputDataTypes": hasattr(addv, "outputDataTypes"),
        "inputDataTypes_sample": list(addv.inputDataTypes())[:4],
        "outputDataTypes_sample": list(addv.outputDataTypes())[:4],
    }
except Exception as e:  # noqa: BLE001
    R["errors"].append(f"instance probe: {type(e).__name__}: {e}")

print("SYNAPSE_M2_25_JSON_START")
print(json.dumps(R, indent=2, default=str))
print("SYNAPSE_M2_25_JSON_END")
