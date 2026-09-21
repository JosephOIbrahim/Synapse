"""BP9 routing: Jev routes each wave-one leg (tier, team size, build agent, verify agent) with the
SHIPPED guards; code owns every decision and every call is ledgered under harness/jev/ledger/bp9.*.
Output: harness/notes/bp9/routing.json, consumed as args by the execution workflow.
Usage: python harness/notes/bp9/route_bp9.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "harness" / "jev"))
import jev_client as jc  # noqa: E402
import jev_route as jr  # noqa: E402
import jev_team as jt  # noqa: E402

WAVE = "bp9"
MISSIONS_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "missions.json"
OUT_PATH = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent / "routing.json"
MISSIONS = json.loads(MISSIONS_PATH.read_text(encoding="utf-8"))

# Code-listed rosters. Names are the Agent tool's registry names; descriptions are their charters, trimmed.
BUILD_ROSTER = {
    "general-purpose": "General-purpose builder with every tool: edits code, writes tests, runs pytest, commits on its worktree branch.",
    "h22-docsurgeon": "Docs-only surgeon: fixes doc drift on README.md and docs/ only. Never touches code, tests, or state files.",
}
VERIFY_ROSTER = {
    "crucible": "Adversarial reviewer of a finished change: reads the diff, reruns the named tests, hunts fabricated success and tests that cannot fail. Read-only plus test execution.",
    "seam-hunter": "Adversarial composition gate for SYNAPSE Solaris wiring on the live Houdini build (hython). Hunts the composed regression isolated tests hide.",
    "panel-design-warden": "Design-system enforcement for the Houdini Python panel: reviews panel/ changes against the vendored tokens and verifies via hython offscreen.",
    "assayer": "Live dir()/hasattr introspection on the live Houdini build to confirm an API exists. Answers one question only: does it exist on this build.",
    "memory-crucible": "Adversarial reviewer for the MEMORY board: attacks memory-store and Moneta changes for fabricated SUCCESS and third store authorities.",
}
EFFORT_FOR_TIER = {"mechanical": "low", "reasoning": "medium", "referee": "high"}
PICK_MIN_CONFIDENCE = 0.60


def pick_spec(roster: dict, role: str) -> dict:
    crit = {name: {"what": desc} for name, desc in roster.items()}
    return {
        "agent": {"type": "choice",
                  "instructions": f"Read `mission` (name, note, targets, acceptance, touches). Choose the ONE {role} agent from `roster` whose charter covers this mission's files and checks. An agent whose charter forbids the mission's work (docs-only for a code change, Solaris-only for a hooks change) must not be chosen.",
                  "criteria": crit},
        "needs_live_houdini": {"type": "noul",
                               "instructions": "Read `mission`. Can its acceptance only be proven with a live Houdini or hython process (a hou.* call, a panel drawn offscreen, a live node)? Plain pytest on a stock interpreter counts as NOT needing Houdini.",
                               "criteria": {"true": "at least one acceptance line or crucible criterion requires hou, hython, a viewport, or a drawn panel", "false": "every acceptance line runs on a stock Python interpreter or a shell"}},
    }


def pick(m: dict, roster: dict, role: str, default: str) -> dict:
    state = {"mission": {k: m[k] for k in ("id", "name", "note", "targets", "acceptance", "crucible_criteria", "touches", "readonly") if k in m},
             "roster": {n: d for n, d in roster.items()}}
    ans = jc.ask(state, pick_spec(roster, role), wave=WAVE, guard=f"pick_{role}", leg=m["id"])
    out = {"agent": default, "reason": "fallback: no Jev answer", "jev": None}
    if not ans:
        return out
    ch = (ans.get("choices") or {}).get("agent") or {}
    live = ((ans.get("nouls") or {}).get("needs_live_houdini") or {}).get("noul")
    choice, conf = ch.get("choice"), ch.get("confidence")
    out["jev"] = {"agent": choice, "confidence": conf, "probabilities": ch.get("probabilities"), "needs_live_houdini": live}
    if choice not in roster:
        out["reason"] = f"fallback: Jev chose unknown agent {choice!r}"
    elif conf is None or conf < PICK_MIN_CONFIDENCE:
        out["reason"] = f"round-to-default: confidence {conf} < {PICK_MIN_CONFIDENCE}"
    else:
        out["agent"], out["reason"] = choice, f"jev: {choice} @ {conf:.2f}"
    return out


def team(m: dict) -> dict:
    g = jc.load_questions()["guards"]["team"]
    state = {"mission": {k: m[k] for k in g["state_fields"] if k in m}}
    ans = jc.ask(state, jt.team_spec(), wave=WAVE, guard="team", leg=m["id"])
    return jt.decide(m, ans, g["policy"])


rows = []
for m in MISSIONS:
    r = jr.route_mission(m, WAVE)
    t = team(m)
    b = pick(m, BUILD_ROSTER, "build", "general-purpose")
    v = pick(m, VERIFY_ROSTER, "verify", "crucible")
    rows.append({
        "id": m["id"], "name": m["name"], "targets": m["targets"], "acceptance": m["acceptance"],
        "crucible_criteria": m["crucible_criteria"], "note": m["note"],
        "tier": r["tier"], "tier_reason": r["reason"], "effort": EFFORT_FOR_TIER.get(r["tier"], "medium"),
        "team_max_subagents": t["max_subagents"], "team_reason": t["reason"],
        "build_agent": b["agent"], "build_reason": b["reason"],
        "verify_agent": v["agent"], "verify_reason": v["reason"],
        "jev": {"route": r.get("jev"), "team": t.get("jev"), "build_pick": b["jev"], "verify_pick": v["jev"]},
    })
    print(f"{m['id']:12} tier={r['tier']:10} ({r['reason'][:48]}) team={t['max_subagents']} build={b['agent']:16} ({b['reason'][:40]}) verify={v['agent']:20} ({v['reason'][:40]})")

out = OUT_PATH
out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
print("wrote", out, "| ledger: harness/jev/ledger/bp9.{route,team,pick_build,pick_verify}.jsonl")
