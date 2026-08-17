"""W5-WCRUX FP1b live re-read (A3) - runs INSIDE hython.

Re-derives VOP wire signatures (re-instantiate) + APEX callback ports (re-read
the Signature) via the CANONICAL build_node_catalog helpers, for types/callbacks
DIFFERENT from the builder's audit stride. Closes the CATALOG A3 acceptance
(typed VOP/APEX ports) with a fresh-binary re-sample, not an inherited test.
"""
import json, sys, os

CAT = "C:/Users/User/SYNAPSE/.claude/worktrees/w5-catalog"
sys.path.insert(0, os.path.join(CAT, "scripts"))
import build_node_catalog as bnc  # noqa: E402
import hou  # noqa: E402

req = json.load(open(sys.argv[1], encoding="utf-8"))
out = {"vop": {}, "apex": {}}

# VOP wire signatures - re-instantiate in a throwaway matnet
container, disposable = bnc._make_matnet(hou)
vcat = hou.nodeTypeCategories()["Vop"]
for tn in req.get("vop", []):
    try:
        node = container.createNode(tn)
        sig = bnc._vop_signature(node, [], tn)
        node.destroy()
        out["vop"][tn] = {k: sig.get(k) for k in
                          ("input_names", "output_names", "input_data_types", "output_data_types")}
    except Exception as e:  # noqa: BLE001
        out["vop"][tn] = {"error": f"{type(e).__name__}: {e}"}
if disposable and container is not None:
    try: container.destroy()
    except Exception: pass

# APEX callback ports - re-read the live Signature
try:
    import apex
    reg = apex.callbackRegistry()
    for name in req.get("apex", []):
        try:
            sig = reg.getSignature(name)
            out["apex"][name] = {
                "inputs": [bnc._port_record(p) for p in sig.inputs()],
                "outputs": [bnc._port_record(p) for p in sig.outputs()],
            }
        except Exception as e:  # noqa: BLE001
            out["apex"][name] = {"error": f"{type(e).__name__}: {e}"}
except Exception as e:  # noqa: BLE001
    out["apex"]["_import_error"] = f"{type(e).__name__}: {e}"

json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), indent=1)
print("FP1B_HYTHON_DONE vop=%d apex=%d" % (len(out["vop"]), len(out["apex"])))
