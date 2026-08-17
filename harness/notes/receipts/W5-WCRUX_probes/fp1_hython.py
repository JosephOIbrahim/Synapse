"""W5-WCRUX FP1 live re-read - runs INSIDE hython (fresh Houdini 22.0.400).

Uses the CANONICAL extraction (build_node_catalog._type_record) - the exact
function that produced the committed catalog - so the comparison is method-fair:
any residual difference is a real catalog defect, not an extraction-method
artifact. (First cut used raw entriesWithoutFolders()/minNumInputs() and produced
false mismatches on multiparm instance templates + VOP arity; corrected here.)

Reads a picks file, emits each type's FULL live base record (minus doc +
wire_signature, matching audit_node_catalog's base_match), for comparison in
probe_fp1.py.
"""
import json, sys, os

# the canonical extraction lives in the catalog leg's scripts dir
CAT = "C:/Users/User/SYNAPSE/.claude/worktrees/w5-catalog"
sys.path.insert(0, os.path.join(CAT, "scripts"))
import build_node_catalog as bnc  # noqa: E402
import hou  # noqa: E402

picks = json.load(open(sys.argv[1], encoding="utf-8"))["picks"]
cats = hou.nodeTypeCategories()
out = {}
for pick in picks:
    cat, tn = pick["category"], pick["type"]
    key = f"{cat}/{tn}"
    c = cats.get(cat)
    if c is None:
        out[key] = {"error": "category absent on live build"}
        continue
    nt = c.nodeTypes().get(tn)
    if nt is None:
        out[key] = {"error": "type absent on live build (DRIFT)"}
        continue
    try:
        rec = bnc._type_record(nt, tn, [])
        # drop fields not present in the base record comparison
        rec.pop("doc", None)
        rec.pop("wire_signature", None)
        out[key] = rec
    except Exception as e:  # noqa: BLE001
        out[key] = {"error": f"live _type_record failed: {type(e).__name__}: {e}"}

json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), indent=1)
print("FP1_HYTHON_DONE types=%d" % len(out))
