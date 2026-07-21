"""LIVE PROBE -- requires hython on the target build; not part of `pytest tests/`.

    "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe"         scripts/live_probes/probe_b1_fix_is_real.py

B1 FIX_IS_REAL companion: restores the pre-fix ranking and proves the defect
reproduces, so the probe above cannot pass vacuously. Exit 0 = defect confirmed
under the old behaviour.
"""

import os, sys
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO, "python"))

import hou
import synapse.server.handlers_solaris_assemble as mod
from synapse.server.handlers_solaris_assemble import SolarisAssembleMixin

mod._UNRANKED_RANK = 800                       # == usdrender_rop's own rank
for name in ("plane", "shadowcatcher", "backgroundplate"):
    mod._SOLARIS_NODE_ORDER.pop(name, None)    # back to unranked


class _Harness(SolarisAssembleMixin):
    pass


stage = hou.node("/stage")
for c in list(stage.children()):
    c.destroy()
geo = stage.createNode("sopcreate", "asset")
krs = stage.createNode("karmarendersettings", "rendersettings")
rop = stage.createNode("usdrender_rop", "render")
krs.setInput(0, geo)
rop.setInput(0, krs)
stage.createNode("plane", "ground")

print("usdrender_rop max_outputs :", rop.type().maxNumOutputs())
try:
    result = _Harness()._handle_solaris_assemble_chain({"mode": "all", "parent": "/stage"})
except Exception as e:
    print("DEFECT REPRODUCED : %s: %s" % (type(e).__name__, e))
    wired_after = [n.name() for n in stage.children() if n.inputs() and any(n.inputs())]
    print("half-wired state  :", sorted(wired_after))
    print()
    print("PROBE VALID: with the old default restored, assemble_chain FAILS.")
    print("The failure is a hard hou.InvalidInput -- usdrender_rop has ZERO")
    print("outputs, so nothing can be wired downstream of it. Combined with B2")
    print("(no undo group) the network is left half-rewired with no rollback.")
    raise SystemExit(0)

names = [p.rsplit("/", 1)[-1] for p in result["chain"]]
print("CHAIN:", names)
if "ground" in names and "render" in names and names.index("ground") > names.index("render"):
    print("PROBE VALID: ground placed downstream of the ROP")
    raise SystemExit(0)
print("PROBE INVALID: defect did not reproduce")
raise SystemExit(1)
