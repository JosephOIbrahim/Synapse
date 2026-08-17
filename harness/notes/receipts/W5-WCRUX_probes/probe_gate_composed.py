#!/usr/bin/env python3
"""W5-WCRUX probe 8 - the KEYSTONE: PARMGATE's rejection power PROVEN in
composition with the REAL CATALOG (completeness-lens gap).

On the parmgate branch alone the gate is degraded/permissive (no catalog data ->
authority 'none'), so its rejection power is DORMANT (its own R1). The combined
tree stages BOTH validation/parm_gate.py + validation/catalog.py AND the real
rag/catalog/h22.0.400 data - the first place the gate can be authoritative. This
proves, against the real catalog:

  1. the catalog reader resolves the REAL opencl COP row (kernelcode present,
     'code' absent - the exact phantom the RD hedge used to paper over);
  2. gated_set REJECTS a phantom name with a nearest-match suggestion, BEFORE
     any mutation (authority=catalog, not permissive);
  3. gated_set ACCEPTS the real name and reports authority=catalog.

Run inside the combined scratch tree's package. No hou needed (fake node).
"""
import sys, os, json

SCRATCH = "C:/Users/User/SYNAPSE/.claude/worktrees/wcrux-scratch"
sys.path.insert(0, os.path.join(SCRATCH, "python"))
os.chdir(SCRATCH)

from synapse.validation import catalog as cat_mod
from synapse.validation.parm_gate import gated_set, ParmGateError

rep = {"probe": "gate_composed"}

default = cat_mod.default_catalog()
opencl = default.parms("Cop", "opencl")
rep["catalog_authority"] = {
    "resolved": opencl is not None,
    "kernelcode_present": bool(opencl) and "kernelcode" in opencl,
    "code_absent": bool(opencl) and "code" not in opencl,
    "n_parms": len(opencl) if opencl else 0,
}


class FakeParm:
    def __init__(self): self.value = None
    def set(self, v): self.value = v


class FakeNode:
    """Minimal node: parm(name) exists only for the real cataloged names."""
    def __init__(self, valid): self._valid = set(valid or [])
    def parm(self, name): return FakeParm() if name in self._valid else None
    def parmTuple(self, name): return None


# 2. REJECT a phantom name (raises BEFORE any mutation)
reject = {}
try:
    gated_set(None, {"code": "kernel body"}, category="Cop", node_type="opencl")
    reject = {"raised": False, "PASS": False, "why": "phantom 'code' was NOT rejected"}
except ParmGateError as e:
    sug = [u.get("suggestions") for u in e.unknown]
    reject = {
        "raised": True,
        "unknown_names": [u["name"] for u in e.unknown],
        "suggestions": sug,
        "kernelcode_suggested": any("kernelcode" in (s or []) for s in sug),
        "message": str(e)[:200],
        "PASS": any("kernelcode" in (s or []) for s in sug),
    }
except Exception as e:  # noqa: BLE001
    reject = {"raised": True, "PASS": False, "why": f"wrong error {type(e).__name__}: {e}"}
rep["reject_phantom"] = reject

# 3. ACCEPT the real name (authority=catalog)
node = FakeNode(opencl or [])
res = gated_set(node, {"kernelcode": "@KERNEL void k(){}"}, category="Cop", node_type="opencl")
rep["accept_real"] = {
    "authority": res.get("authority"),
    "gated": res.get("gated"),
    "set": res.get("set"),
    "PASS": (res.get("authority") == "catalog" and "kernelcode" in (res.get("set") or [])),
}

rep["GATE_COMPOSED_PASS"] = (
    rep["catalog_authority"]["resolved"]
    and rep["catalog_authority"]["kernelcode_present"]
    and rep["catalog_authority"]["code_absent"]
    and rep["reject_phantom"].get("PASS")
    and rep["accept_real"].get("PASS")
)
print(json.dumps(rep, indent=2))
