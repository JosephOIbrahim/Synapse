# jev_team.py - JEV-TEAM guard: how many subagents may ONE leg spawn? (helm mile 2)
# Called by compile_wave.py only for a mission carrying "team": "auto". A literal team object
# passes through untouched; a mission with no team field never reaches this file and compiles
# byte-identical to before. Jev scores how parallelizable the leg's targets are and whether the
# pieces would collide on a file; decide() maps that to 0 / 2 / 4 subagents.
# DOUBT ROUNDS DOWN: every subagent is tokens, so low confidence drops a band, a likely file
# collision means zero, and any failure means zero (a plain single-session leg, as today).
# The subagent tier is a code rule (policy.subagent_tier), never Jev's choice, and must be a
# rails_exec.json tier name - Jev still never names a model.
# Source: harness/battleplan/notes/JEV_HELM.md (mile 2).
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jev_client as jc  # noqa: E402

MISSIONS = jc.REPO / "harness" / "battleplan" / "missions"


def team_spec() -> dict:
    g = jc.load_questions()["guards"]["team"]["questions"]
    return {"parallelizable": {"type": "score", "instructions": g["parallelizable"]["instructions"],
                               "criteria": g["parallelizable"]["criteria"]},
            "shared_files": {"type": "noul", "instructions": g["shared_files"]["instructions"]}}


def _band(score: float, bands: list) -> int:
    for i, (upper, n) in enumerate(bands):
        if score < upper:
            return i
    return len(bands) - 1


def decide(m: dict, answers: dict | None, policy: dict) -> dict:
    """Plain code. Returns {max_subagents, subagent_tier, reason, jev}."""
    tier = policy["subagent_tier"]
    if tier not in jc.rails_tiers():
        return {"max_subagents": 0, "subagent_tier": None, "reason": f"fallback: subagent_tier {tier!r} not in rails", "jev": None}
    zero = {"max_subagents": policy["fallback_subagents"], "subagent_tier": tier}
    if m.get("class") in ("crucible", "tidy"):
        return {**zero, "reason": "rule: referee and tidy legs work alone", "jev": None}
    if answers is None:
        return {**zero, "reason": "fallback: no Jev answer (see ledger)", "jev": None}
    p = answers["scores"].get("parallelizable") or {}
    score, conf = p.get("score"), p.get("confidence")
    shared = (answers["nouls"].get("shared_files") or {}).get("noul")
    jev = {"parallelizable": score, "confidence": conf, "shared_files": shared}
    if score is None:
        return {**zero, "reason": "fallback: no parallelizable score", "jev": jev}
    if not m.get("readonly") and (shared is None or shared > policy["shared_files_max"]):
        return {**zero, "reason": f"round-down: writers would share files ({shared})", "jev": jev}
    bands = policy["bands"]
    i = _band(score, bands)
    why = f"jev: parallelizable {score:.2f}"
    if conf is None or conf < policy["min_confidence"]:
        i = max(0, i - 1)
        why = f"round-down: confidence {conf} < {policy['min_confidence']} (parallelizable {score:.2f})"
    n = min(bands[i][1], policy["hard_cap"])
    return {"max_subagents": n, "subagent_tier": tier, "reason": why, "jev": jev}


def resolve_team(m: dict, wave: str) -> dict:
    """Entry point for compile_wave.py. Only ever called for team == 'auto'."""
    g = jc.load_questions()["guards"]["team"]
    answers = None
    if m.get("class") not in ("crucible", "tidy"):
        state = {"mission": {k: m[k] for k in g["state_fields"] if k in m}}
        answers = jc.ask(state, team_spec(), wave=wave, guard="team", leg=m["id"])
    d = decide(m, answers, g["policy"])
    jc.ledger(wave, "team", {"leg": m["id"], "result": "decision", "decision": d})
    return d


def team_lines(team: dict) -> str:
    """The brief section a leg reads. Zero subagents renders nothing (byte-identical prompt)."""
    n = int(team.get("max_subagents") or 0)
    if n <= 0:
        return ""
    return ("\n## Team\n\n"
            f"You may spawn at most {n} subagents, tier `{team['subagent_tier']}`, for independent pieces only. "
            "Give each one a single target, the file paths it needs and nothing else - never this whole brief. "
            "You alone write the receipt, you verify every subagent result before citing it, and an unverified "
            "result is UNKNOWN. Fewer is fine; zero is fine. Report how many you spawned in the receipt.\n")


def shadow(wave: str) -> int:
    files = sorted(p for p in MISSIONS.glob("*.json") if p.stem.lower().startswith(wave.lower() + "-"))
    print(f"{'leg':14} {'subs':4} {'par':5} {'conf':5} {'shared':6}  reason")
    for f in files:
        m = json.loads(f.read_text(encoding="utf-8"))
        d = resolve_team(m, f"{wave}.shadow")
        j = d.get("jev") or {}
        fm = lambda v: f"{v:.2f}" if isinstance(v, (int, float)) else "-"  # noqa: E731
        print(f"{m['id']:14} {d['max_subagents']:<4} {fm(j.get('parallelizable')):5} {fm(j.get('confidence')):5} "
              f"{fm(j.get('shared_files')):6}  {d['reason']}")
    return 0 if files else 1


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", required=True)
    ap.add_argument("--shadow", action="store_true", help="the only mode: judge every mission of a wave, write no rows")
    sys.exit(shadow(ap.parse_args().wave))
