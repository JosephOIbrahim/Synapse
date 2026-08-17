#!/usr/bin/env python3
"""W5-WCRUX probe 3 - FP2 audit (target 3): run the broken/healthy golden pair
MYSELF and prove the tier ladder cannot promote without a measurement.

Independent of the builder's tests. Loads the committed goldens, runs
detect_explosion + the measure() dispatcher + the exposure_rung/tier projection
directly, and asserts:

  A. healthy golden  -> STABLE (and a REAL stable: a gap-free KE window was
     actually evaluated, so this is measured-stable, not a laundered UNKNOWN).
  B. exploding golden-> EXPLODING, signal=ke_growth, offending_frame=5 (anchored).
  C. TIER LADDER cannot promote without measurement: for EVERY output kind, an
     unmeasured obs -> UNKNOWN -> rung V0_membership (NOT V1_output/foreground);
     only a MEASURED result reaches V1_output. If exposure.highest_tier resolves,
     assert the projected panel tiers differ (measured foreground vs unknown not).

Reports facts as JSON. Run in the MEASURES worktree's package.
"""
import sys, os, json

MEAS = "C:/Users/User/SYNAPSE/.claude/worktrees/w5-measures"
sys.path.insert(0, os.path.join(MEAS, "python"))
os.chdir(MEAS)

from synapse.validation.explosion import detect_explosion, STABLE, EXPLODING as X_EXPLODING, UNKNOWN as X_UNKNOWN
from synapse.validation.measures import (
    measure, exposure_rung, exposure_tier, OUTPUT_KINDS,
    MEASURED, UNKNOWN, FAIL, EXPLODING,
)

rep = {"probe": "fp2"}


def load(name):
    with open(os.path.join(MEAS, "rulebook/goldens/sim", name), encoding="utf-8") as f:
        return json.load(f)

healthy = load("healthy_sim.json")
exploding = load("exploding_sim.json")


def frames_of(g):
    # committed golden shape: {"kind","obs":{"frames":[...]},"expect":{...}}
    if isinstance(g, dict):
        return g.get("obs", {}).get("frames") or g.get("frames")
    return g

hf, xf = frames_of(healthy), frames_of(exploding)
rep["golden_expect"] = {"healthy": healthy.get("expect"), "exploding": exploding.get("expect")}
rep["golden_shapes"] = {
    "healthy_top_keys": list(healthy.keys()) if isinstance(healthy, dict) else "list",
    "exploding_top_keys": list(exploding.keys()) if isinstance(exploding, dict) else "list",
    "healthy_frame_count": len(hf) if isinstance(hf, list) else None,
    "exploding_frame_count": len(xf) if isinstance(xf, list) else None,
}

# A. healthy -> STABLE (real measured-stable)
hv = detect_explosion(hf)
rep["A_healthy"] = {
    "verdict": hv.verdict, "signal": hv.signal, "offending_frame": hv.offending_frame,
    "unknown_reason": hv.unknown_reason,
    "PASS": hv.verdict == STABLE,   # STABLE (not UNKNOWN) => a window was really judged
}

# B. exploding -> EXPLODING, ke_growth, frame 5
xv = detect_explosion(xf)
rep["B_exploding"] = {
    "verdict": xv.verdict, "signal": xv.signal, "offending_frame": xv.offending_frame,
    "detail": xv.detail,
    "PASS": (xv.verdict == X_EXPLODING and xv.signal == "ke_growth" and xv.offending_frame == 5),
}

# also route through measure("sim", ...) - the production dispatcher
rep["A_measure_sim"] = {"verdict": measure("sim", {"frames": hf}).verdict}
rep["B_measure_sim"] = {"verdict": measure("sim", {"frames": xf}).verdict}

# C. tier ladder cannot promote without measurement
# unmeasured obs (empty dict) per kind -> UNKNOWN -> V0_membership, never foreground
promote_violations = []
per_kind = {}
for kind in OUTPUT_KINDS:
    r = measure(kind, {})              # nothing measured
    rung = exposure_rung(r)
    tier = exposure_tier(r)
    per_kind[kind] = {"verdict": r.verdict, "rung": rung, "tier": tier}
    if r.verdict != UNKNOWN:
        promote_violations.append(f"{kind}: unmeasured obs -> {r.verdict}, expected UNKNOWN")
    if rung == "V1_output":
        promote_violations.append(f"{kind}: UNKNOWN promoted to V1_output rung")
rep["C_unmeasured_per_kind"] = per_kind

# a MEASURED result MUST reach V1_output (the ladder is not merely refusing everything)
measured_res = measure("sim", {"frames": hf})
measured_rung = exposure_rung(measured_res)
unknown_res = measure("sim", {})
unknown_rung = exposure_rung(unknown_res)
rep["C_ladder"] = {
    "measured_verdict": measured_res.verdict, "measured_rung": measured_rung,
    "measured_tier": exposure_tier(measured_res),
    "unknown_verdict": unknown_res.verdict, "unknown_rung": unknown_rung,
    "unknown_tier": exposure_tier(unknown_res),
    "measured_reaches_V1_output": measured_rung == "V1_output",
    "unknown_stays_below_output": unknown_rung != "V1_output",
    "tiers_differ": exposure_tier(measured_res) != exposure_tier(unknown_res),
}
rep["C_promote_violations"] = promote_violations
rep["C_PASS"] = (
    not promote_violations
    and measured_rung == "V1_output"
    and unknown_rung != "V1_output"
)

rep["FP2_PASS"] = rep["A_healthy"]["PASS"] and rep["B_exploding"]["PASS"] and rep["C_PASS"]
print(json.dumps(rep, indent=2))
