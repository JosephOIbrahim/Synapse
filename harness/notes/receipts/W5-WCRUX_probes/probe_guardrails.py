#!/usr/bin/env python3
"""W5-WCRUX probe 7 - guardrail_violations on the combined tree (predicate 3).

Runs the harness's OWN deterministic guardrails (harness/verify/checks.py) over
the staged combined scratch tree. A guardrail returning ok:False is a VIOLATION;
ok:None is gate-down/WARN (never counted as a violation - honest, not laundered).

Guardrails run (the cross-cutting, static, code-staging-relevant set):
  check_phantom_clean          - introduced phantom hou/pdg/pxr API on added lines
  check_provenance_not_bypassed- every mutation routes through the FloorGate
  check_clean_install          - no hardcoded user path in the shipped surface
  check_no_rigging_drift       - authoring-domain allowlist stays off rigging
  check_version_single_source  - VERSION == pyproject
"""
import sys, os, json

WT = "C:/Users/User/SYNAPSE/.claude/worktrees"
TARGETS = {"base": f"{WT}/wcrux-base", "scratch": f"{WT}/wcrux-scratch"}
HYTHON = r"C:\Program Files\Side Effects Software\Houdini 22.0.400\bin\hython.exe"

# import the harness guardrails (identical logic in every tree; none of the legs
# touches checks.py) from the scratch tree, with its synapse on path
sys.path.insert(0, os.path.join(TARGETS["scratch"], "harness", "verify"))
sys.path.insert(0, os.path.join(TARGETS["scratch"], "python"))
import checks  # noqa: E402

GUARDRAILS = [
    "check_phantom_clean",
    "check_provenance_not_bypassed",
    "check_clean_install",
    "check_no_rigging_drift",
    "check_version_single_source",
]


def run_all(wt):
    ctx = {"wt": wt, "hython": HYTHON, "mode": "A"}
    res, violations, warns = {}, 0, 0
    for name in GUARDRAILS:
        fn = getattr(checks, name, None)
        if fn is None:
            res[name] = {"ok": None, "detail": "guardrail absent in checks.py"}
            warns += 1
            continue
        try:
            r = fn(ctx)
        except Exception as e:  # noqa: BLE001
            res[name] = {"ok": None, "detail": f"raised {type(e).__name__}: {e}"}
            warns += 1
            continue
        res[name] = {"ok": r.get("ok"), "detail": (r.get("detail") or "")[:400]}
        if r.get("ok") is False:
            violations += 1
        elif r.get("ok") is None:
            warns += 1
    return res, violations, warns


rep = {"probe": "guardrails", "per_target": {}}
for tname, wt in TARGETS.items():
    res, v, w = run_all(wt)
    rep["per_target"][tname] = {"results": res, "violations": v, "warns": w}

# attribution delta: a violation the legs INTRODUCED = ok False in scratch but not base
leg_introduced = []
for name in GUARDRAILS:
    b = rep["per_target"]["base"]["results"][name]["ok"]
    s = rep["per_target"]["scratch"]["results"][name]["ok"]
    if s is False and b is not False:
        leg_introduced.append(name)
rep["leg_introduced_violations"] = leg_introduced
rep["preexisting_violations"] = [n for n in GUARDRAILS
                                 if rep["per_target"]["base"]["results"][n]["ok"] is False
                                 and rep["per_target"]["scratch"]["results"][n]["ok"] is False]
rep["PASS_legs_add_no_guardrail_violation"] = (len(leg_introduced) == 0)
print(json.dumps(rep, indent=2))
