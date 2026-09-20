# jev_edge.py - JEV-EDGE guard: which edge does the wave take after a builder receipt lands? (helm mile 3)
# orchestrate.ps1 re-reads its manifest on every poll, so a dynamic edge is a bounded edit to that
# manifest between polls. This file makes the edit; the orchestrator only calls it (one hook, inert
# unless SYNAPSE_JEV_EDGE is 'on' or 'shadow').
#   CLEAR / REFEREE -> continue. The screen's brief line already steers how deep CRUX reads.
#   FLAG            -> insert ONE repair leg, based on the flagged leg's branch, scoped to the flagged
#                      acceptance rows only, and make every dependent of the flagged leg wait for it.
# Bounds (code, not judgment): at most workflows.json caps.max_inserted_legs per wave; a repair leg
# never spawns a repair (no chains); referee/tidy legs are never screened here; a repair is charged
# through the budget rails like any other leg. DRY RUN unless --apply. Any error -> continue.
# Source: harness/battleplan/notes/JEV_HELM.md (mile 3).
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "battleplan"))
import jev_client as jc  # noqa: E402

REPO = jc.REPO
MISSIONS = REPO / "harness" / "battleplan" / "missions"
PROMPTS = REPO / "harness" / "battleplan" / "prompts"
TAG = "jev-edge"


def caps() -> dict:
    return json.loads((HERE / "workflows.json").read_text(encoding="utf-8"))["caps"]


def repair_mission(m: dict, decision: dict, rid: str) -> dict:
    """The repair brief: ONLY the flagged rows, the screen's reason, and an honest way out."""
    rows = [i for i in decision.get("rows", []) if 0 <= i < len(m["acceptance"])]
    flagged = [m["acceptance"][i] for i in rows]
    tier = m.get("tier") if m.get("tier") not in (None, "auto") else "reasoning"
    return {
        "id": rid, "band": "BUILD", "class": "build", "tier": tier, "readonly": False, "deps": [m["id"]],
        "name": f"Repair {m['id']}: acceptance row(s) {rows} - the receipt's evidence does not support the predicate",
        "note": (f"Tier: {tier}. Self-cap: 12 turns (progress every 4). Inserted by JEV-EDGE after JEV-SCREEN flagged "
                 f"{m['id']}: {decision.get('reason', '')}. You start on {m['id']}'s branch with its work in place. Fix ONLY "
                 "the flagged rows. If a row cannot be made true, say so: fail or UNKNOWN with the reason is a good "
                 "receipt; a pass with thin evidence is what got this leg flagged. Touch nothing outside `touches`. "
                 "Commit code BEFORE the receipt; the receipt is your final write."),
        "targets": [f"R{n}) Row {i}: make this true and show reproducible evidence (file + number, hash, or command "
                    f"exit code): {a['predicate']}" for n, (i, a) in enumerate(zip(rows, flagged), 1)],
        "touches": list(m.get("touches", [])),
        "acceptance": [dict(a) for a in flagged],
        "crucible_criteria": list(m.get("crucible_criteria", [])),
        "spawn_classes": [], "source": dict(m["source"]),
    }


def plan_edge(manifest: dict, m: dict, decision: dict | None, cap: int) -> dict:
    """PURE. Returns {action, reason, manifest?, mission?, dependents?}. Never mutates its inputs."""
    leg = next((x for x in manifest["legs"] if x["id"] == m["id"]), None)
    if leg is None:
        return {"action": "continue", "reason": f"{m['id']} not in manifest"}
    if m.get("class") in ("crucible", "tidy"):
        return {"action": "continue", "reason": "rule: referee and tidy receipts are not screened for edges"}
    if leg.get("inserted_by") == TAG:
        return {"action": "continue", "reason": "rule: a repair leg never spawns a repair (no chains)"}
    if decision is None:
        return {"action": "continue", "reason": "fallback: no screen decision"}
    if decision.get("verdict") != "FLAG" or not decision.get("rows"):
        return {"action": "continue", "reason": f"screen {decision.get('verdict')}: no edge change"}
    inserted = [x for x in manifest["legs"] if x.get("inserted_by") == TAG]
    if any(x.get("repairs") == m["id"] for x in inserted):
        return {"action": "continue", "reason": f"{m['id']} already has a repair leg"}
    if len(inserted) >= cap:
        return {"action": "cap_reached", "reason": f"FLAG on {m['id']} but {len(inserted)}/{cap} inserted legs used - CRUX takes it from the screen line"}
    wave = m["id"].split("-", 1)[0]
    rid = f"{wave}-RPR{len(inserted) + 1}"
    rm = repair_mission(m, decision, rid)
    new = copy.deepcopy(manifest)
    tag = rid.split("-", 1)[1].lower()
    row = {"id": rid, "name": rm["name"], "state": "ready", "receipt": f"{rid}.json",
           "branch": f"{wave.lower()}/{tag}", "base": leg["branch"],          # builds ON the flagged leg's work
           "worktree": f".claude/worktrees/{rid.lower()}", "prompt": f"harness/battleplan/prompts/{rid}.md",
           "deps": [m["id"]], "readonly": False, "touches": rm["touches"],
           "note": f"JEV-EDGE repair of {m['id']} rows {decision['rows']}", "tier": rm["tier"],
           "inserted_by": TAG, "repairs": m["id"]}
    dependents = []
    for x in new["legs"]:
        if m["id"] in x.get("deps", []) and rid not in x["deps"]:
            x["deps"] = list(x["deps"]) + [rid]
            dependents.append(x["id"])
    at = next(i for i, x in enumerate(new["legs"]) if x["id"] == m["id"]) + 1
    new["legs"].insert(at, row)
    return {"action": "insert_repair", "reason": f"FLAG rows {decision['rows']} -> {rid} (base {leg['branch']})",
            "manifest": new, "mission": rm, "row": row, "dependents": dependents}


def apply(plan: dict, manifest_path: Path) -> None:
    import mission_schema as ms
    import compile_wave as cw
    errs = ms.validate_mission(plan["mission"])
    if errs:
        raise ValueError("; ".join(errs))
    rm, row = plan["mission"], plan["row"]
    (MISSIONS / f"{rm['id']}.json").write_text(json.dumps(rm, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (PROMPTS / f"{rm['id']}.md").write_text(cw.fill_prompt(rm, row), encoding="utf-8")
    for dep in plan["dependents"]:  # dependents have not dispatched (their deps were unmet), so their brief can still learn
        p = PROMPTS / f"{dep}.md"
        if p.exists():
            with p.open("a", encoding="utf-8") as f:
                f.write(f"\n## Inserted leg\n\n{rm['id']} was inserted by JEV-EDGE to repair {row['repairs']} "
                        f"({plan['reason']}). Treat its receipt `{row['receipt']}` as part of {row['repairs']}'s work.\n")
    tmp = manifest_path.with_suffix(manifest_path.suffix + ".edge.tmp")
    tmp.write_text(json.dumps(plan["manifest"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, manifest_path)  # atomic: the orchestrator's next poll sees the old file or the new one, never half


def run(manifest_path: Path, leg_id: str, receipt_path: Path, do_apply: bool) -> dict:
    wave = leg_id.split("-", 1)[0].lower()
    try:
        import jev_screen
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        m = json.loads((MISSIONS / f"{leg_id}.json").read_text(encoding="utf-8"))
        leg = next((x for x in manifest["legs"] if x["id"] == leg_id), {})
        skip = m.get("class") in ("crucible", "tidy") or leg.get("inserted_by") == TAG
        decision = None if skip else jev_screen.screen_leg(m, json.loads(receipt_path.read_text(encoding="utf-8-sig")), wave)
        plan = plan_edge(manifest, m, decision, caps()["max_inserted_legs"])
        applied = False
        if plan["action"] == "insert_repair" and do_apply:
            apply(plan, manifest_path)
            applied = True
        out = {"action": plan["action"], "reason": plan["reason"], "applied": applied,
               "inserted": plan.get("row", {}).get("id"), "dependents": plan.get("dependents", [])}
    except Exception as e:  # noqa: BLE001 - an edge failure must never stop a wave
        out = {"action": "continue", "reason": f"fallback: {type(e).__name__}: {e}"[:300], "applied": False}
    jc.ledger(wave, "edge", {"leg": leg_id, "result": "decision", "mode": "apply" if do_apply else "shadow", "decision": out})
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True); ap.add_argument("--leg", required=True)
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--apply", action="store_true", help="write the repair leg into the manifest (default: dry run)")
    a = ap.parse_args()
    o = run(Path(a.manifest), a.leg, Path(a.receipt), a.apply)
    print(f"{o['action']}{' (applied)' if o.get('applied') else ''}: {o['reason']}")
    sys.exit(0)
