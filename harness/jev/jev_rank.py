# jev_rank.py - JEV-RANK guard: rank hypotheses against evidence before spawning scouts.
# Comparable per-item Scores (plausibility) plus a per-item Noul (does the evidence already
# refute it). Code decides which hypotheses get a scout: score >= spawn_min and not refuted.
# Fail closed: no answer -> every hypothesis gets a scout (spend, never skip blind).
# Usage: python harness/jev/jev_rank.py --doc harness/battleplan/notes/SCOUT_CHAT_STALL.md --wave bp7
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jev_client as jc  # noqa: E402

REPO = jc.REPO
LEVELS = ["Unlikely: the evidence or the symptom shape points elsewhere.",
          "Possible: consistent with the symptom, nothing in the evidence supports or excludes it.",
          "Likely: at least one evidence line directly supports the mechanism.",
          "Strong: two or more evidence lines support it, or one names the exact code path."]


def parse(doc: str) -> tuple[list[str], list[dict]]:
    ev = re.search(r"## Evidence.*?\n(.*?)\n## Hypotheses", doc, re.S).group(1)
    evidence = [" ".join(p.split()) for p in re.split(r"\n- ", "\n" + ev) if p.strip()]
    hyp_block = re.search(r"## Hypotheses.*?\n(.*?)\n## ", doc, re.S).group(1)
    hyps = []
    for m in re.finditer(r"^(H\d+)\s+(\S+)\s+(.*?)(?=^H\d+\s|\Z)", hyp_block, re.S | re.M):
        hyps.append({"id": m.group(1), "name": m.group(2), "text": " ".join(m.group(3).split())})
    return evidence, hyps


def rank(doc_path: Path, wave: str) -> list[dict]:
    doc = doc_path.read_text(encoding="utf-8")
    symptom = re.search(r"Symptom as reported.*?:\s*(.*?)\n\n", doc, re.S).group(1)
    evidence, hyps = parse(doc)
    state = {"symptom": " ".join(symptom.split()), "evidence": evidence,
             "hypotheses": [{"id": h["id"], "name": h["name"], "mechanism": h["text"]} for h in hyps]}
    spec = {}
    for i, h in enumerate(hyps):
        spec[f"p_{h['id']}"] = {"type": "score", "criteria": LEVELS, "instructions":
            f"How plausible is `hypotheses[{i}]` as the cause of `symptom`, judged against `evidence` only? "
            "Judge the mechanism, not the prose. Use the same scale for every hypothesis so they compare."}
        spec[f"r_{h['id']}"] = {"type": "noul", "instructions":
            f"Does any line of `evidence` already REFUTE `hypotheses[{i}]` - show its mechanism cannot occur here?"}
    pol = jc.load_questions()["guards"].get("rank", {}).get("policy", {"spawn_min": 1.0, "refuted_min": 0.75})
    a = jc.ask(state, spec, wave=wave, guard="rank", leg="hypotheses")
    out = []
    for h in hyps:
        if a is None:
            out.append({**h, "score": None, "refuted": None, "spawn": True, "why": "fallback: no Jev answer"})
            continue
        s = (a["scores"].get(f"p_{h['id']}") or {}).get("score")
        r = (a["nouls"].get(f"r_{h['id']}") or {}).get("noul")
        spawn = (s is not None and s >= pol["spawn_min"]) and not (r is not None and r >= pol["refuted_min"])
        out.append({**h, "score": s, "refuted": r, "spawn": spawn,
                    "why": f"plausibility {s:.2f} refuted {r:.2f}" if s is not None else "no score"})
    out.sort(key=lambda x: -(x["score"] or 0))
    jc.ledger(wave, "rank", {"leg": "hypotheses", "result": "decision", "ranking": out})
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True); ap.add_argument("--wave", required=True)
    ap.add_argument("--json", help="write ranking here")
    a = ap.parse_args()
    r = rank(REPO / a.doc, a.wave)
    for h in r:
        print(f"{'SCOUT' if h['spawn'] else 'skip ':5} {h['id']:3} {h['name']:12} {h['why']}")
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=1), encoding="utf-8")
