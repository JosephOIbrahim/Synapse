"""Mile-3 LIVE verification against graphical Houdini 21.0.671 (interactive bridge).

Drives the REAL GraphBuilder.instantiate through the production stack (HouExistence
Oracle + ConnectivityOracle + ProposalStore) on a self-cleaning throwaway /obj/geo.
Proves what the mock-hou DoD test cannot: the real build, that ONE hou.undos
.performUndo() reverts the whole build, the reject/TOCTOU-halt zero-mutation paths,
and the build-failure ROLLBACK (forced via an injected always-VALID validator + an
invalid 2nd node type so createNode actually raises mid-build).

Run via houdini_execute_python:  exec(open(<this>).read(), {"__name__": "__m3__"})
(single namespace -> nested validator factories see the module imports; the bridge's
split-scope exec(G != L) would otherwise hide them). Writes _mile3_live.json beside."""
import sys, json, traceback
sys.path.insert(0, r"C:\Users\User\SYNAPSE\python")
for _m in list(sys.modules):
    if (_m.startswith("synapse.host.graph") or _m.startswith("synapse.cognitive.graph")
            or _m.startswith("synapse.host.existence") or _m == "synapse.cognitive.interfaces"
            or _m == "synapse.host.proposal_store"):
        del sys.modules[_m]
import hou
from synapse.host.graph_builder import GraphBuilder
from synapse.host.proposal_store import ProposalStore
from synapse.host.graph_oracle import ConnectivityOracle
from synapse.host.existence_adapter import HouExistenceOracle
from synapse.cognitive.graph_validator import GraphValidator
from synapse.cognitive.graph_proposal import (
    GraphProposal, ProposedNode, ProposedEdge, NodeKind, ValidationStatus, ValidationReport)

R = {"houdini": hou.applicationVersionString()}
probe = hou.node("/obj").createNode("geo", "SYN_M3_PROBE")
try:
    pp = probe.path()
    merge = probe.createNode("merge", "merge1")
    mpath = merge.path()
    store = ProposalStore()

    def real_validator():
        return GraphValidator(HouExistenceOracle(), ConnectivityOracle())

    # 1. BUILD + single undo
    store.put(GraphProposal("m3-build", "SOP", pp,
        [ProposedNode("nx", NodeKind.NEW, "Sop", node_type="box", friendly_name="bx"),
         ProposedNode("ny", NodeKind.NEW, "Sop", node_type="xform", friendly_name="xf"),
         ProposedNode("ex", NodeKind.EXISTING, "Sop", scene_path=mpath)],
        [ProposedEdge("nx", 0, "ny", 0), ProposedEdge("ny", 0, "ex", 1)],
        "build", "glm", houdini_version_stamp="21.0.671"))
    b = GraphBuilder(store, validator_factory=real_validator)
    r1 = b.instantiate("m3-build")
    R["build_status"] = r1.status.value
    R["build_created"] = r1.created_paths
    R["merge_has_xf_after_build"] = any(n and n.path().endswith("/xf") for n in merge.inputs())
    hou.undos.performUndo()                                   # single Ctrl+Z reverts the build group
    R["single_undo_reverts"] = (hou.node(pp + "/bx") is None and hou.node(pp + "/xf") is None
                                and hou.node(mpath) is not None and not any(merge.inputs()))

    # 2. REJECT unknown id
    R["reject_status"] = b.instantiate("does-not-exist").status.value

    # 3. TOCTOU halt — delete an EXISTING node between propose and instantiate
    ghost = probe.createNode("box", "ghost_box")
    store.put(GraphProposal("m3-toctou", "SOP", pp,
        [ProposedNode("g", NodeKind.EXISTING, "Sop", scene_path=ghost.path()),
         ProposedNode("nn", NodeKind.NEW, "Sop", node_type="box", friendly_name="bx3")],
        [ProposedEdge("g", 0, "nn", 0)], "toctou", "glm", houdini_version_stamp="21.0.671"))
    ghost.destroy()
    n_before = len(probe.children())
    r3 = b.instantiate("m3-toctou")
    R["toctou_status"] = r3.status.value
    R["toctou_zero_mutation"] = (len(probe.children()) == n_before)

    # 4. ROLLBACK on a REAL build failure (always-VALID validator + invalid 2nd type)
    def always_valid():
        class _V:
            def validate(self, p):
                return ValidationReport(status=ValidationStatus.VALID, proposal_id=p.proposal_id)
        return _V()
    store.put(GraphProposal("m3-fail", "SOP", pp,
        [ProposedNode("ok", NodeKind.NEW, "Sop", node_type="box", friendly_name="okbox"),
         ProposedNode("bad", NodeKind.NEW, "Sop", node_type="frobnicate_zzz", friendly_name="badnode")],
        [ProposedEdge("ok", 0, "bad", 0)], "fail", "glm", houdini_version_stamp="21.0.671"))
    n_before_fail = len(probe.children())
    r4 = GraphBuilder(store, validator_factory=always_valid).instantiate("m3-fail")
    R["fail_status"] = r4.status.value
    R["fail_message"] = r4.message[:130]
    R["rollback_zero_net"] = (hou.node(pp + "/okbox") is None
                              and len(probe.children()) == n_before_fail)

    R["ALL_PASS"] = bool(R.get("build_status") == "built" and R.get("single_undo_reverts")
                         and R.get("reject_status") == "rejected"
                         and R.get("toctou_status") == "halted" and R.get("toctou_zero_mutation")
                         and R.get("fail_status") == "failed" and R.get("rollback_zero_net"))
except Exception as e:
    R["error"] = "%s: %s" % (type(e).__name__, e)
    R["trace"] = traceback.format_exc()[-800:]
finally:
    try: probe.destroy()
    except Exception: pass
    R["scene_clean"] = hou.node("/obj/SYN_M3_PROBE") is None
open(r"C:\Users\User\SYNAPSE\harness\notes\_mile3_live.json", "w").write(json.dumps(R, indent=2, default=str))
