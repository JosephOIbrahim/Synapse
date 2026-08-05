#!/usr/bin/env python
"""AUTORESEARCH scout — the stochastic side: triages evidence, authors the next mission.

Constitutional line: the model may author QUESTIONS; only probes produce ANSWERS.
The scout never touches hou and never executes probes. Its proposed missions land
in missions/proposed/ — runnable only by an explicit Start-AutoResearch call.

Model resolution: tiers.json ONLY — model names never appear in code, only tiers.
Ollama dialect mounts rope/exec_ollama.py conventions: OLLAMA_URL env,
/api/chat, stream:false, stdlib urllib, num_ctx in options.

Two deterministic gates sit on the stochastic output:
    1. literal fence — proposed parm_probe / chain_hash questions may only use
       type literals the evidence proved ALIVE (exists:true or discovery match).
       type_discovery / type_existence questions are inherently safe: asking
       about a dead name IS a valid question.
    2. mission_schema.validate_mission — structure, coordinates on failure.

Runs under plain system Python. Same sentinel contract as runner.py:
state.json heartbeat (identical field shape), DONE/FAILED written last.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runner import atomic_write, atomic_write_json, utc_now, log  # noqa: E402
from mission_schema import MissionError, validate_mission  # noqa: E402

SCOUT_VERSION = "1.0.0"
OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
AR_ROOT = Path(__file__).resolve().parent
PHASES = ["load", "condense", "model", "gate", "write"]


def load_tier(name: str) -> str:
    tiers_path = AR_ROOT / "tiers.json"
    try:
        tiers = json.loads(tiers_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RuntimeError(f"tiers.json not found at {tiers_path}")
    if name not in tiers:
        raise RuntimeError(f"tier '{name}' not in tiers.json (have: {sorted(k for k in tiers if not k.startswith('_'))})")
    return tiers[name]


def beat(out: Path, phase: str, question: str, done: int) -> None:
    """Heartbeat with the exact field shape Get-AutoResearchState expects."""
    total = len(PHASES)
    atomic_write_json(out / "state.json", {
        "mission": "scout",
        "phase": phase,
        "question": question,
        "done": done,
        "total": total,
        "pct": round(100 * done / total),
        "ts": utc_now(),
        "pid": os.getpid(),
    })


# ---------------------------------------------------------------- evidence

def condense(evidence: dict) -> dict:
    """Shrink evidence for the prompt: full parm dumps become counts +
    highlight hits; discovery lists are capped. Nothing is invented."""
    out = {"meta": evidence.get("meta", {}), "entries": []}
    for e in evidence.get("entries", []):
        v = e.get("value")
        ce = {"claim": e.get("claim"), "probe": e.get("probe")}
        if e.get("note"):
            ce["note"] = e["note"]
        if isinstance(v, dict):
            if e.get("probe") == "parm_probe" and "all" in v:
                ce["value"] = {k: v[k] for k in
                               ("all_count", "highlight", "decoded", "decoder") if k in v}
            elif e.get("probe") == "type_discovery":
                m = v.get("matches", [])
                ce["value"] = {"count": v.get("count"), "matches": m[:60]}
            elif e.get("probe") == "chain_hash":
                ce["value"] = {k: v[k] for k in
                               ("chain", "stable", "sha256", "line_count",
                                "name_drift", "candidate", "error", "missing")
                               if k in v}
            else:
                ce["value"] = v
        else:
            ce["value"] = v
        out["entries"].append(ce)
    return out


def alive_literals(evidence: dict) -> set:
    """Every LOP type name the evidence proved alive."""
    alive = set()
    for e in evidence.get("entries", []):
        v = e.get("value")
        if not isinstance(v, dict):
            continue
        if e.get("probe") == "type_existence" and v.get("exists") is True:
            claim = e.get("claim", "")
            if ":" in claim:
                alive.add(claim.split(":", 1)[1])
        elif e.get("probe") == "type_discovery":
            alive.update(v.get("matches", []))
    return alive


# ---------------------------------------------------------------- model call

PROMPT_TEMPLATE = """You are the AUTORESEARCH scout for SYNAPSE. You author probe QUESTIONS \
about Houdini's LOP (Solaris) context. You never answer Houdini questions from memory — \
probes answer them against the live runtime.

Read the probe evidence below. Then output a SINGLE JSON object, nothing else:

{{
  "triage": {{
    "dead_literals_confirmed": ["..."],
    "successors": {{"dead_name": ["live candidate from discovery lists", "..."]}},
    "chain_verdict": "one sentence on the chain_hash results",
    "surprises": ["..."],
    "gaps": ["what the evidence does not yet answer"]
  }},
  "proposed_mission": {{
    "mission": "next_<short_slug>",
    "version": "0.1.0",
    "target_build": "{build}",
    "phases": [
      {{"id": "P0", "kind": "type_discovery", "questions": [{{"pattern": "..."}}]}},
      {{"id": "P1", "kind": "type_existence", "questions": [{{"name": "..."}}]}},
      {{"id": "P2", "kind": "parm_probe", "questions": [{{"type": "...", "highlight": ["..."]}}]}},
      {{"id": "P3", "kind": "chain_hash", "questions": [{{"name": "...", "chain": ["...", "..."], "repeat": 2}}]}}
    ]
  }}
}}

HARD RULES for proposed_mission:
- Only these question kinds: type_discovery, type_existence, parm_probe, chain_hash.
- Every type literal in parm_probe or chain_hash MUST appear in this evidence as
  exists:true or inside a discovery matches list. Do not invent literals.
- chain_hash questions must have repeat >= 2.
- 24 questions maximum total. Prefer questions that close the gaps you listed.
- Omit phases you do not need. Every phase id must be unique.
{objective_block}
EVIDENCE:
{evidence_json}
"""


def call_ollama(model: str, prompt: str, timeout: int = 600) -> str:
    req = urllib.request.Request(
        OLLAMA + "/api/chat", method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "model": model,
            "stream": False,
            "format": "json",
            "options": {"num_ctx": 32768, "temperature": 0},
            "messages": [{"role": "user", "content": prompt}],
        }).encode())
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)["message"]["content"]


def parse_model_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        a, b = content.find("{"), content.rfind("}")
        if a >= 0 and b > a:
            return json.loads(content[a:b + 1])
        raise


# ---------------------------------------------------------------- gates

def literal_fence(mission: dict, alive: set) -> tuple:
    """Strip parm_probe / chain_hash questions that use literals the evidence
    never proved alive. Returns (fenced_mission, rejected_questions)."""
    rejected = []
    fenced_phases = []
    for phase in mission.get("phases", []):
        kind = phase.get("kind")
        if kind not in ("parm_probe", "chain_hash"):
            fenced_phases.append(phase)
            continue
        kept = []
        for q in phase.get("questions", []):
            if kind == "parm_probe":
                bad = [] if q.get("type") in alive else [q.get("type")]
            else:
                bad = [t for t in q.get("chain", []) if t not in alive]
            if bad:
                rejected.append({"phase": phase.get("id"), "question": q,
                                 "unproven_literals": bad})
            else:
                kept.append(q)
        if kept:
            fenced_phases.append({**phase, "questions": kept})
    return {**mission, "phases": fenced_phases}, rejected


# ---------------------------------------------------------------- main

def run_scout(evidence_path: Path, out: Path, tier: str, objective: str) -> None:
    beat(out, "load", str(evidence_path), 0)
    evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    build = evidence.get("meta", {}).get("build", "unknown")
    model = load_tier(tier)
    log(f"scout v{SCOUT_VERSION} | tier '{tier}' | evidence build {build}")

    beat(out, "condense", "shrinking evidence", 1)
    condensed = condense(evidence)
    alive = alive_literals(evidence)
    log(f"condensed {len(condensed['entries'])} entries | {len(alive)} literals proven alive")

    objective_block = ""
    if objective:
        objective_block = f"- OPERATOR OBJECTIVE (weigh heavily): {objective}\n"
    prompt = PROMPT_TEMPLATE.format(
        build=build,
        objective_block=objective_block,
        evidence_json=json.dumps(condensed, indent=1),
    )

    beat(out, "model", "waiting on ollama", 2)
    content = call_ollama(model, prompt)
    atomic_write(out / "raw_model_output.json", content)
    parsed = parse_model_json(content)

    beat(out, "gate", "literal fence + schema", 3)
    triage = parsed.get("triage", {})
    proposed_names = []
    rejected = []
    mission = parsed.get("proposed_mission")

    if isinstance(mission, dict) and mission.get("phases"):
        mission["target_build"] = build  # deterministic field — never the model's
        mission.setdefault("version", "0.1.0")
        if not str(mission.get("mission", "")).startswith("next_"):
            mission["mission"] = "next_" + str(mission.get("mission", "scout")).strip()

        mission, rejected = literal_fence(mission, alive)
        if mission["phases"]:
            try:
                validate_mission(mission, source="proposed")
                dest = AR_ROOT / "missions" / "proposed" / f"{mission['mission']}.json"
                n = 2
                while dest.exists():
                    dest = dest.with_name(f"{mission['mission']}_{n}.json")
                    n += 1
                atomic_write_json(dest, mission)
                proposed_names.append(dest.stem)
                log(f"proposed mission written: {dest}")
            except MissionError as e:
                rejected.append({"phase": "*", "question": "whole mission",
                                 "unproven_literals": [], "schema_error": str(e)})
                log(f"proposed mission REJECTED by schema: {e}")
        else:
            log("literal fence removed every stochastic question — triage-only run")

    beat(out, "write", "triage artifacts", 4)
    atomic_write_json(out / "triage.json", {
        "triage": triage,
        "proposed": proposed_names,
        "rejected_questions": rejected,
        "alive_literal_count": len(alive),
        "tier": tier,
        "evidence": str(evidence_path),
    })

    md = ["# Scout triage", "",
          f"evidence  `{evidence_path}`  ·  build `{build}`  ·  tier `{tier}`", ""]
    for k, v in triage.items():
        md.append(f"**{k}**")
        md.append("```json")
        md.append(json.dumps(v, indent=1))
        md.append("```")
        md.append("")
    if proposed_names:
        md.append(f"**proposed mission** → `missions/proposed/{proposed_names[0]}.json`")
        md.append("")
        md.append(f"run it: `Start-AutoResearch -Mission proposed/{proposed_names[0]}`")
    else:
        md.append("**no runnable mission survived the gates** — triage only")
    if rejected:
        md.append("")
        md.append(f"**rejected questions** ({len(rejected)}) — unproven literals or schema failures; see triage.json")
    atomic_write(out / "triage.md", "\n".join(md) + "\n")

    atomic_write_json(out / "DONE", {
        "finished": utc_now(),
        "entries": len(proposed_names),
        "failures": len(rejected),
        "evidence": "triage.json",
        "kind": "scout",
    })
    log(f"DONE — proposed={len(proposed_names)} rejected={len(rejected)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AUTORESEARCH scout")
    ap.add_argument("--evidence", required=True, help="path to lop_truth_*.json")
    ap.add_argument("--out", required=True, help="scout run output directory")
    ap.add_argument("--tier", default="scout", help="tier name in tiers.json")
    ap.add_argument("--objective", default="", help="operator objective, weighed by the author")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        run_scout(Path(args.evidence), out, args.tier, args.objective)
        return 0
    except Exception:
        tb = traceback.format_exc()
        log("FAILED")
        atomic_write(out / "FAILED",
                     f"{utc_now()}\n\n{tb}\n\nIs ollama serving? Check {OLLAMA} "
                     f"(ollama serve) and that the tier's model is pulled (ollama list).")
        print(tb, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
