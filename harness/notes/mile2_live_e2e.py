"""Mile-2 LIVE end-to-end verification against graphical Houdini 21.0.671 (the
interactive WS-bridge runtime). Drives the REAL ConnectivityOracle +
HouExistenceOracle through GraphValidator on a self-cleaning throwaway /obj net
(read-only w.r.t. the artist's work — the probe is created then destroyed).
Writes the verdict JSON beside this file.

Run via houdini_execute_python on the live bridge (NOT headless hython — the point
is the interactive runtime). Closes the Mile-2 'owed residual': graph_oracle.py /
existence_adapter.py were §2.5-grounded + verified headless; this proves the whole
pipeline interactive. Last run: all_pass=True (see mile2_live_e2e_result.json)."""
import sys, json
sys.path.insert(0, r"C:\Users\User\SYNAPSE\python")
# The long-running bridge may hold an EARLIER copy of these modules (Python returns
# the cached module on re-import) — evict so the on-disk version loads.
for _m in list(sys.modules):
    if (_m == "synapse.cognitive.interfaces"
            or _m.startswith("synapse.cognitive.graph")
            or _m.startswith("synapse.host.graph")
            or _m.startswith("synapse.host.existence")):
        del sys.modules[_m]
import hou
from synapse.host.graph_oracle import ConnectivityOracle
from synapse.host.existence_adapter import HouExistenceOracle
from synapse.cognitive.graph_validator import GraphValidator
from synapse.cognitive.graph_proposal import (
    GraphProposal, ProposedNode, ProposedEdge, NodeKind)

R = {}
probe = hou.node("/obj").createNode("geo", "SYN_M2_PROBE")
try:
    merge = probe.createNode("merge", "merge1")
    b0 = probe.createNode("box", "b0")
    merge.setInput(0, b0)  # occupy merge.input0 with live wiring
    v = GraphValidator(HouExistenceOracle(), ConnectivityOracle())  # REAL oracles
    mp, pp = merge.path(), probe.path()
    cases = [
        ("arity_overflow", pp,
         [ProposedNode("n1", NodeKind.NEW, "Sop", node_type="box", friendly_name="bx"),
          ProposedNode("n2", NodeKind.NEW, "Sop", node_type="xform", friendly_name="xf")],
         [ProposedEdge("n2", 0, "n1", 5)], "invalid"),
        ("hallucinated_type", pp,
         [ProposedNode("h", NodeKind.NEW, "Sop", node_type="frobnicate", friendly_name="fz")], [], "invalid"),
        ("occupied_halt", pp,
         [ProposedNode("nn", NodeKind.NEW, "Sop", node_type="box", friendly_name="bx2"),
          ProposedNode("ex", NodeKind.EXISTING, "Sop", scene_path=mp)],
         [ProposedEdge("nn", 0, "ex", 0)], "invalid"),
        ("ghost_resolve", pp,
         [ProposedNode("g", NodeKind.EXISTING, "Sop", scene_path=pp + "/ghost_zzz"),
          ProposedNode("nb", NodeKind.NEW, "Sop", node_type="box", friendly_name="bx3")],
         [ProposedEdge("g", 0, "nb", 0)], "invalid"),
        ("missing_parent", "/obj/NO_SUCH_PARENT_zzz",
         [ProposedNode("mp1", NodeKind.NEW, "Sop", node_type="box", friendly_name="bx5")], [], "invalid"),
        ("valid_extend", pp,
         [ProposedNode("nx", NodeKind.NEW, "Sop", node_type="box", friendly_name="bx4"),
          ProposedNode("em", NodeKind.EXISTING, "Sop", scene_path=mp)],
         [ProposedEdge("nx", 0, "em", 1)], "valid"),
    ]
    ok = True
    for cid, parent, nodes, edges, expect in cases:
        p = GraphProposal(cid, "SOP", parent, nodes, edges, "live e2e", "glm",
                          houdini_version_stamp="21.0.671")
        r = v.validate(p)
        passed = (r.status.value == expect)
        ok = ok and passed
        R[cid] = {"status": r.status.value, "expect": expect, "pass": passed,
                  "errors": [e.message for e in r.errors]}
    eo = HouExistenceOracle()
    ex = {"box": eo.node_type_exists("box", "Sop"),
          "frobnicate": eo.node_type_exists("frobnicate", "Sop"),
          "box.t": eo.parameter_exists("box", "Sop", "t"),
          "box.zzz_nope": eo.parameter_exists("box", "Sop", "zzz_nope")}
    R["existence"] = ex
    R["all_pass"] = bool(ok and ex == {"box": True, "frobnicate": False,
                                       "box.t": True, "box.zzz_nope": False})
finally:
    probe.destroy()  # leave the scene exactly as found
    R["scene_clean"] = hou.node("/obj/SYN_M2_PROBE") is None
with open(r"C:\Users\User\SYNAPSE\harness\notes\mile2_live_e2e_result.json", "w") as f:
    json.dump(R, f, indent=2)
