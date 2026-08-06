"""M5 diagnostic: apply_fixture leaves 2 residual ops on a clean build.

The reconciler self-verifies by re-observing and re-planning. That plan must
be empty. It is not. Print the whole residual plan and the observed snapshot
so the divergence names itself.

Run:  hython harness/notes/_m5_residual_diag.py
"""
import json
import sys
from pathlib import Path

import hou

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python"))

from synapse.blocks.fixtures import box_name_for, load_fixture  # noqa: E402
from synapse.blocks.plan import build_plan                      # noqa: E402
from synapse.blocks.runtime import apply_fixture, observe       # noqa: E402

hou.putenv("HIP", "C:/Users/User/SYNAPSE")

fx = load_fixture("solaris.basic")
box = box_name_for(fx, "solaris.basic")

res = apply_fixture("solaris.basic", "/stage")
snap = observe(fx, box, "/stage")
plan = build_plan(fx, snap, box_name=box)

print("SYNAPSE_PROBE_JSON_START")
print(json.dumps({
    "status": res["status"],
    "applied": res["applied"],
    "ops_planned": res["ops"],
    "residual_ops": res.get("residual_ops"),
    "residual_plan": res.get("residual_plan"),
    "verdict": res["verdict"],
    "missing_parms": res["missing_parms"],
    "unmanaged_inputs": res["unmanaged_inputs"],
    "fresh_plan": plan.to_dict(),
    "observed": snap,
}, indent=2, sort_keys=True, default=str))
print("SYNAPSE_PROBE_JSON_END")
