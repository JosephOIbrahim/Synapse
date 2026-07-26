# ASSAYER independent probe -- H3a leg. Single symbol: hou.Node.getPDGGraphContext
# Written from scratch; does NOT import or reuse harness/notes/h3a_probe.py.
import json
import sys

out = {}

try:
    import hou
except Exception as e:
    print(json.dumps({"IMPORT_FAILED": "%s: %s" % (type(e).__name__, e)}))
    sys.exit(2)

out["build"] = hou.applicationVersionString()
out["python"] = sys.version.split()[0]

# ---------- controls ----------
pos = hasattr(hou, "node")
neg1 = hasattr(hou, "zzz_indep_control_must_not_exist")
neg2 = hasattr(hou, "lopNetworks")
out["control_positive_hou_node"] = pos
out["control_negative_zzz"] = neg1
out["control_negative_hou_lopNetworks"] = neg2
out["controls_ok"] = bool(pos is True and neg1 is False and neg2 is False)

# ---------- resolver: walk dotted path segment by segment ----------
def resolve(dotted):
    """Walk 'hou.A.B' one segment at a time. Returns (verdict, detail)."""
    parts = dotted.split(".")
    assert parts[0] == "hou"
    cur = hou
    walked = "hou"
    for seg in parts[1:]:
        parent_dir = dir(cur)
        has = hasattr(cur, seg)
        in_dir = seg in parent_dir
        if not has and not in_dir:
            return ("ABSENT", "segment %r cleanly absent from dir(%s) (len=%d) and hasattr False"
                    % (seg, walked, len(parent_dir)))
        if not has and in_dir:
            return ("UNVERIFIABLE", "segment %r in dir(%s) but hasattr False -- not a clean absence"
                    % (seg, walked))
        try:
            cur = getattr(cur, seg)
        except Exception as e:
            return ("UNVERIFIABLE", "getattr(%s, %r) raised %s: %s" % (walked, seg, type(e).__name__, e))
        walked = walked + "." + seg
    return ("CONFIRMED", "resolved to %r" % (repr(cur)[:200],))

TARGET = "hou.Node.getPDGGraphContext"
v, d = resolve(TARGET)
out["target"] = TARGET
out["target_verdict"] = v
out["target_detail"] = d
out["hasattr_hou_Node"] = hasattr(hou, "Node")
if hasattr(hou, "Node"):
    nd = dir(hou.Node)
    out["hou_Node_dir_len"] = len(nd)
    out["getPDGGraphContext_in_dir_hou_Node"] = "getPDGGraphContext" in nd
    out["hasattr_hou_Node_getPDGGraphContext"] = hasattr(hou.Node, "getPDGGraphContext")
    out["hou_Node_related"] = sorted(
        a for a in nd
        if any(k in a.lower() for k in ("pdg", "cook", "task", "dirty", "cancel"))
    )

# ---------- hou.TopNode ----------
out["hasattr_hou_TopNode"] = hasattr(hou, "TopNode")
out["TopNode_in_dir_hou"] = "TopNode" in dir(hou)
if hasattr(hou, "TopNode"):
    td = dir(hou.TopNode)
    out["hou_TopNode_dir_len"] = len(td)
    out["hasattr_hou_TopNode_getPDGGraphContext"] = hasattr(hou.TopNode, "getPDGGraphContext")
    out["getPDGGraphContext_in_dir_hou_TopNode"] = "getPDGGraphContext" in td
    out["hou_TopNode_related"] = sorted(
        a for a in td
        if any(k in a.lower() for k in ("pdg", "cook", "task", "dirty", "cancel"))
    )
    try:
        out["hou_TopNode_mro"] = [c.__name__ for c in hou.TopNode.__mro__]
    except Exception as e:
        out["hou_TopNode_mro"] = "ERR %s" % e

# ---------- provenance of the attribute (which class actually defines it) ----------
if hasattr(hou, "Node") and hasattr(hou.Node, "getPDGGraphContext"):
    owners = []
    try:
        for c in hou.Node.__mro__:
            if "getPDGGraphContext" in c.__dict__:
                owners.append(c.__name__)
    except Exception as e:
        owners = ["ERR %s" % e]
    out["defining_classes_for_hou_Node"] = owners

print(json.dumps(out, indent=2, sort_keys=True))
