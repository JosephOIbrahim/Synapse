"""Graph-synth /mcp-fix LIVE verification on 21.0.671 — real hou validator + one
shared store, IN the Houdini process. Drives the runtime + propose tool + builder
directly (the functions the propose_graph / instantiate_graph handlers dispatch to),
so it exercises the REAL HouExistenceOracle/ConnectivityOracle validator — the thing
that could NOT construct in the hou-less mcp_server process — plus the single shared
ProposalStore. Does NOT evict synapse.server.handlers (the live bridge's handler).

Run via:  exec(open(<this>).read(), {"__name__":"__gs__"})  with atomic=False."""
import sys, json, traceback
sys.path.insert(0, r"C:\Users\User\SYNAPSE\python")
for _m in list(sys.modules):
    if (_m.startswith("synapse.host.graph") or _m.startswith("synapse.cognitive.graph")
            or _m.startswith("synapse.cognitive.tools.propose_graph")
            or _m.startswith("synapse.host.existence") or _m == "synapse.host.proposal_store"
            or _m == "synapse.cognitive.interfaces"):
        del sys.modules[_m]
import hou
import synapse.host.graph_synth_runtime as runtime
from synapse.cognitive.tools import propose_graph

runtime.reset()
runtime.wire_propose()   # builds the REAL hou-backed validator in the Houdini process

def _pdict(pid, ntype, parent):
    return {"proposal_id": pid, "network_type": "SOP", "parent_path": parent,
            "nodes": [{"node_id": "a", "kind": "new", "node_category": "Sop",
                       "node_type": ntype, "friendly_name": "livebox"}],
            "edges": [], "natural_language_intent": "live box",
            "model_id": "glm", "houdini_version_stamp": "21.0.671"}

R = {"houdini": hou.applicationVersionString()}
probe = hou.node("/obj").createNode("geo", "SYN_GS_PROBE")
PP = probe.path()
try:
    # the real validator built in THIS process, bound to the ONE shared store
    R["wire_ok"] = (propose_graph._STORE is runtime._get_store()) and (propose_graph._VALIDATOR is not None)
    # 1. propose a VALID box -> real validator -> VALID + parked, scene unmutated
    out = propose_graph.synapse_propose_graph(_pdict("live-share", "box", PP))
    R["propose_status"] = out.get("status")
    R["propose_id"] = out.get("proposal_id")
    R["parked"] = runtime._get_store().get("live-share") is not None
    R["scene_unmutated_after_propose"] = hou.node(PP + "/livebox") is None
    # 2. instantiate by id -> the shared store resolves it -> real build
    res = runtime.instantiate("live-share")
    R["build_status"] = res.status.value
    R["box_exists"] = hou.node(PP + "/livebox") is not None
    # 3. single undo reverts the whole build
    hou.undos.performUndo()
    R["undo_reverts"] = (hou.node(PP + "/livebox") is None and hou.node(PP) is not None)
    # 4. unknown id rejects (proves cross-process store identity, not a fresh 2nd store)
    R["unknown_status"] = runtime.instantiate("never-proposed-xyz").status.value
    # 5. phantom node type rejected by the REAL oracle (not the CI _AlwaysValid stub)
    out2 = propose_graph.synapse_propose_graph(_pdict("live-phantom", "frobnicate_zzz", PP))
    R["phantom_status"] = out2.get("status")
    R["phantom_errors"] = json.dumps(out2.get("errors"))[:220]
    R["phantom_not_parked"] = runtime._get_store().get("live-phantom") is None
    R["ALL_PASS"] = bool(
        R.get("wire_ok") and R.get("propose_status") == "valid" and R.get("parked")
        and R.get("scene_unmutated_after_propose") and R.get("build_status") == "built"
        and R.get("box_exists") and R.get("undo_reverts")
        and R.get("unknown_status") == "rejected"
        and R.get("phantom_status") == "invalid" and R.get("phantom_not_parked"))
except Exception as e:
    R["error"] = "%s: %s" % (type(e).__name__, e)
    R["trace"] = traceback.format_exc()[-900:]
finally:
    try: probe.destroy()
    except Exception: pass
    R["scene_clean"] = hou.node("/obj/SYN_GS_PROBE") is None
open(r"C:\Users\User\SYNAPSE\harness\notes\_gs_mcp_live.json", "w").write(json.dumps(R, indent=2, default=str))
