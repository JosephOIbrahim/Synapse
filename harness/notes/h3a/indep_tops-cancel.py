"""INDEPENDENT ASSAYER probe -- pdg.GraphContext.cancelCook on the live build.

Deliberately does NOT import or reuse harness/notes/h3a_probe.py.
Second, independent producer path. Throwaway.
"""
import json
import sys

OUT = {}

# ---- build identity, derived from the probe itself (never assumed) ----
try:
    import hou
    OUT["hou_import"] = "OK"
    OUT["applicationVersionString"] = hou.applicationVersionString()
    OUT["applicationVersion"] = list(hou.applicationVersion())
except Exception as e:  # pragma: no cover
    OUT["hou_import"] = "FAIL: %r" % (e,)
    print(json.dumps(OUT, indent=2))
    sys.exit(1)

# ---- CONTROLS (resolver sanity) ----
pos = hasattr(hou, "node")                              # must be True
neg1 = hasattr(hou, "zzz_indep_control_must_not_exist")  # must be False
neg2 = hasattr(hou, "lopNetworks")                       # must be False
OUT["control_positive_hou_node"] = pos
OUT["control_negative_zzz_indep_control_must_not_exist"] = neg1
OUT["control_negative_hou_lopNetworks"] = neg2
controls_ok = (pos is True) and (neg1 is False) and (neg2 is False)
OUT["controls_ok"] = controls_ok

# ---- target import ----
try:
    import pdg
    OUT["pdg_import"] = "OK"
    OUT["pdg_module_file"] = getattr(pdg, "__file__", None)
except Exception as e:
    OUT["pdg_import"] = "FAIL: %r" % (e,)
    print(json.dumps(OUT, indent=2))
    sys.exit(1)

# ---- segment-by-segment resolution: pdg.GraphContext.cancelCook ----
SYMBOL = "pdg.GraphContext.cancelCook"
segments = ["GraphContext", "cancelCook"]
cur = pdg
cur_path = "pdg"
walk = []
resolved = True
for seg in segments:
    present_hasattr = hasattr(cur, seg)
    present_dir = seg in dir(cur)
    walk.append({
        "parent": cur_path,
        "segment": seg,
        "hasattr": present_hasattr,
        "in_dir_of_parent": present_dir,
    })
    if not (present_hasattr and present_dir):
        resolved = False
        break
    cur = getattr(cur, seg)
    cur_path = cur_path + "." + seg

OUT["symbol"] = SYMBOL
OUT["segment_walk"] = walk
OUT["resolved"] = resolved
if resolved:
    OUT["final_repr"] = repr(cur)
    OUT["final_type"] = type(cur).__name__
    OUT["final_callable"] = callable(cur)
    OUT["final_doc"] = (getattr(cur, "__doc__", None) or "")[:400]

# ---- enumerate related names on pdg.GraphContext ----
KEYS = ("cancel", "stop", "abort", "interrupt", "cook")
try:
    gc_dir = dir(pdg.GraphContext)
    OUT["GraphContext_dir_len"] = len(gc_dir)
    OUT["related_names_present"] = sorted(
        n for n in gc_dir if any(k in n.lower() for k in KEYS)
    )
except Exception as e:
    OUT["related_names_present"] = "FAIL: %r" % (e,)

# ---- the literal brief name, probed as a fact (not a suggestion) ----
OUT["literal_tops_cancel_cook_on_GraphContext"] = hasattr(pdg.GraphContext, "tops_cancel_cook")

print(json.dumps(OUT, indent=2, default=str))
