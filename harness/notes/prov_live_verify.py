"""agent.usd build-provenance LIVE verify on 21.0.671. Drives the REAL build
(runtime + real validator) with the REAL wired _agent_usd_provenance writer; the
path resolver (scene_memory.ensure_scene_structure) is redirected to a TEMP
agent.usd so the user's real scene memory is untouched (the hipFile->$HIP
resolution itself is session.py:200-201 established). Confirms log_decision writes
a /SYNAPSE/memory/decisions/decision_NNNN receipt that round-trips.

Run via: exec(open(<this>).read(), {"__name__":"__prov__"})."""
import sys, json, traceback, tempfile, os, shutil
sys.path.insert(0, r"C:\Users\User\SYNAPSE\python")
for _m in list(sys.modules):
    if (_m.startswith("synapse.host.graph") or _m.startswith("synapse.cognitive.graph")
            or _m.startswith("synapse.cognitive.tools.propose_graph")
            or _m.startswith("synapse.host.existence") or _m == "synapse.host.proposal_store"
            or _m == "synapse.cognitive.interfaces"
            or _m == "synapse.memory.agent_state" or _m == "synapse.memory.scene_memory"):
        del sys.modules[_m]
import hou
from pxr import Usd
import synapse.host.graph_synth_runtime as runtime
from synapse.cognitive.tools import propose_graph
import synapse.memory.agent_state as agent_state
import synapse.memory.scene_memory as scene_memory

R = {"houdini": hou.applicationVersionString()}
tmpdir = tempfile.mkdtemp(prefix="syn_prov_")
tmp_usd = os.path.join(tmpdir, "agent.usd")
probe = hou.node("/obj").createNode("geo", "SYN_PROV_PROBE")
PP = probe.path()
try:
    agent_state.initialize_agent_usd(tmp_usd)                       # v2 schema (incl. /SYNAPSE/memory/decisions)
    R["temp_initialized"] = os.path.exists(tmp_usd)
    scene_memory.ensure_scene_structure = lambda hip, job: {"agent_usd": tmp_usd}  # redirect writer to temp

    st0 = Usd.Stage.Open(tmp_usd)
    dp0 = st0.GetPrimAtPath("/SYNAPSE/memory/decisions")
    R["decisions_parent_valid"] = dp0.IsValid()
    R["decisions_before"] = len(list(dp0.GetChildren())) if dp0.IsValid() else -1
    del st0

    runtime.reset()
    runtime.wire_propose()                                          # real validator
    propose_graph.synapse_propose_graph({
        "proposal_id": "live-prov", "network_type": "SOP", "parent_path": PP,
        "nodes": [{"node_id": "a", "kind": "new", "node_category": "Sop",
                   "node_type": "box", "friendly_name": "provbox"}],
        "edges": [], "natural_language_intent": "a provenance box",
        "model_id": "glm", "houdini_version_stamp": "21.0.671"})
    res = runtime.instantiate("live-prov")                          # real build -> real _agent_usd_provenance
    R["build_status"] = res.status.value
    R["box_exists"] = hou.node(PP + "/provbox") is not None

    st1 = Usd.Stage.Open(tmp_usd)
    dp1 = st1.GetPrimAtPath("/SYNAPSE/memory/decisions")
    kids = list(dp1.GetChildren()) if dp1.IsValid() else []
    R["decisions_after"] = len(kids)
    if kids:
        last = kids[-1]
        R["decision_prim"] = last.GetName()
        for fld in ("decision", "reasoning", "revert", "createdPaths", "modelId", "timestamp"):
            at = last.GetAttribute("synapse:" + fld)
            R[fld] = at.Get() if (at and at.IsValid()) else None
    del st1

    R["receipt_ok"] = bool(
        R.get("decisions_after") == (R.get("decisions_before", 0) + 1)
        and R.get("decision") and "live-prov" in (R.get("decision") or "")
        and (R.get("reasoning") or "") == "a provenance box"
        and "undo" in (R.get("revert") or "")
        and "provbox" in (R.get("createdPaths") or ""))
    R["ALL_PASS"] = bool(R.get("build_status") == "built" and R.get("box_exists") and R.get("receipt_ok"))
except Exception as e:
    R["error"] = "%s: %s" % (type(e).__name__, e)
    R["trace"] = traceback.format_exc()[-1000:]
finally:
    try: probe.destroy()
    except Exception: pass
    try: shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception: pass
    R["scene_clean"] = hou.node("/obj/SYN_PROV_PROBE") is None
open(r"C:\Users\User\SYNAPSE\harness\notes\_prov_live.json", "w").write(json.dumps(R, indent=2, default=str))
