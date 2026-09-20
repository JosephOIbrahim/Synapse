# jev_shape.py - JEV-SHAPE guard: objective -> wave graph template, at author time.
# Jev chooses among the shape NAMES in workflows.json; decide() turns four judgments into one
# shape and falls back to "manual" (author the wave by hand, the pre-Jev behaviour) on doubt or
# on disagreement between independent judgments. expand() turns a shape into mission SKELETONS
# (id/band/class/tier/deps/readonly); note, targets and acceptance stay the CTO seat's job.
# Nothing here writes into missions/ - skeletons go to stdout or to --out.
# Source: harness/battleplan/notes/JEV_HELM.md (mile 1).
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jev_client as jc  # noqa: E402

REPO = jc.REPO
WORKFLOWS = HERE / "workflows.json"
CASES = HERE / "shape_shadow_cases.json"
MISSIONS = REPO / "harness" / "battleplan" / "missions"
MANUAL = "manual"


def load_workflows() -> dict:
    return json.loads(WORKFLOWS.read_text(encoding="utf-8"))


def _shape_descriptions() -> dict:
    """workflows.json names x questions.json descriptions. Names come from workflows.json;
    a shape without a description falls back to its `why`; a description without a shape is dropped."""
    q = jc.load_questions()["guards"]["shape"]["questions"]["shape"]["criteria_by_shape"]
    return {name: (q.get(name) or {"what": entry.get("why", name)})
            for name, entry in load_workflows()["shapes"].items()}


def shape_state(objective: str, evidence: list[str] | None = None) -> dict:
    return {"objective": " ".join(objective.split()), "evidence": list(evidence or []),
            "shapes": _shape_descriptions()}


def shape_spec(criteria: dict) -> dict:
    g = jc.load_questions()["guards"]["shape"]["questions"]
    return {
        "shape": {"type": "choice", "instructions": g["shape"]["instructions"], "criteria": criteria},
        "cause_known": {"type": "noul", "instructions": g["cause_known"]["instructions"]},
        "deterministic": {"type": "noul", "instructions": g["deterministic"]["instructions"]},
        "breadth": {"type": "score", "instructions": g["breadth"]["instructions"], "criteria": g["breadth"]["criteria"]},
    }


def decide(answers: dict | None, policy: dict, shapes: dict) -> dict:
    """Plain code. Returns {shape, reason, jev}. `manual` means: author by hand, as before Jev.
    Every build/scout shape needs a second, independent judgment to agree with the Choice."""
    fb = policy["fallback_shape"]
    if answers is None:
        return {"shape": fb, "reason": "fallback: no Jev answer (see ledger)", "jev": None}
    s = answers["choices"].get("shape", {})
    choice, conf = s.get("choice"), s.get("confidence")
    known = (answers["nouls"].get("cause_known") or {}).get("noul")
    det = (answers["nouls"].get("deterministic") or {}).get("noul")
    br = (answers["scores"].get("breadth") or {}).get("score")
    jev = {"shape": choice, "confidence": conf, "probabilities": s.get("probabilities"),
           "cause_known": known, "deterministic": det, "breadth": br}
    if choice not in shapes:
        return {"shape": fb, "reason": f"fallback: Jev chose unknown shape {choice!r}", "jev": jev}
    if conf is None or conf < policy["min_shape_confidence"]:
        return {"shape": fb, "reason": f"manual: shape confidence {conf} < {policy['min_shape_confidence']}", "jev": jev}
    split = policy["cause_known_split"]
    if choice == "scout-synth" and known is not None and known > split:
        return {"shape": fb, "reason": f"manual: scout-synth but cause_known {known:.2f} > {split}", "jev": jev}
    if choice in ("solo", "fix-crux", "build-screen-crux") and known is not None and known < split:
        return {"shape": fb, "reason": f"manual: {choice} but cause_known {known:.2f} < {split}", "jev": jev}
    if choice == "probe-only" and (det is None or det < policy["probe_only_min_deterministic"]):
        return {"shape": fb, "reason": f"manual: probe-only but deterministic {det} < {policy['probe_only_min_deterministic']}", "jev": jev}
    if choice in ("solo", "fix-crux") and br is not None and br > policy["solo_max_breadth"]:
        return {"shape": fb, "reason": f"manual: {choice} but breadth {br:.2f} > {policy['solo_max_breadth']}", "jev": jev}
    return {"shape": choice, "reason": f"jev: {choice} @ {conf:.2f}", "jev": jev}


def choose(objective: str, wave: str, evidence: list[str] | None = None) -> dict:
    g = jc.load_questions()["guards"]["shape"]
    state = shape_state(objective, evidence)
    answers = jc.ask(state, shape_spec(state["shapes"]), wave=wave, guard="shape", leg="objective")
    d = decide(answers, g["policy"], load_workflows()["shapes"])
    jc.ledger(wave, "shape", {"leg": "objective", "result": "decision", "decision": d})
    return d


def leg_count(lo: int, hi: int, breadth: float | None, legs: int | None = None) -> int:
    """How many legs of a fan-out role. An explicit author count wins (clamped to the template's
    bounds): Jev judges breadth, it does not count. Otherwise the breadth LEVEL picks a band:
    One -> lo, Few -> lo+1, Many -> hi. Unknown breadth -> lo: more legs cost more tokens, so
    doubt rounds DOWN here (the opposite of tier routing)."""
    if hi <= lo:
        return lo
    if legs is not None:
        return max(lo, min(hi, legs))
    if breadth is None or breadth < 0.5:
        return lo
    return min(hi, lo + 1) if breadth < 1.5 else hi


def expand(shape: str, wave: str, breadth: float | None = None, legs: int | None = None) -> list[dict]:
    """Template -> mission skeletons. Bounded by workflows.json caps. Never writes missions/."""
    wf = load_workflows()
    if shape == MANUAL or shape not in wf["shapes"]:
        return []
    cap = wf["caps"]["max_legs_per_wave"]
    ids: dict[str, list[str]] = {}
    out: list[dict] = []
    for leg in wf["shapes"][shape]["legs"]:
        lo, hi = leg["count"]
        n = leg_count(lo, hi, breadth, legs)
        ids[leg["role"]] = []
        for i in range(n):
            if len(out) >= cap:
                break
            mid = f"{wave.upper()}-{leg['role']}" + (f"{i + 1}" if hi > 1 else "")
            ids[leg["role"]].append(mid)
            deps = [d for role in leg["deps_on"] for d in ids.get(role, [])]
            out.append({"id": mid, "band": leg["band"], "class": leg["class"], "tier": leg["tier"],
                        "readonly": leg["readonly"], "deps": deps, "_skeleton": True,
                        "_todo": ["name", "note", "targets", "acceptance", "touches"]})
    return out


def derive_shape(missions: list[dict]) -> str:
    """What shape did a hand-authored wave actually have? Pure code, no labels by hand."""
    if len(missions) == 1:
        return "solo"
    if any(m.get("class") == "crucible" for m in missions):
        return "fix-crux" if len(missions) == 2 else "build-screen-crux"
    roots = [m for m in missions if not m.get("deps")]
    sinks = [m for m in missions if m.get("deps")]
    if len(sinks) == 1 and len(roots) >= 2 and set(sinks[0]["deps"]) == {m["id"] for m in roots}:
        return "scout-synth"
    return "unclassified"


def shadow() -> int:
    """For each past wave in shape_shadow_cases.json: Jev's shape beside the authored shape."""
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    rows, agree, n = [], 0, 0
    for c in cases:
        wave = c["wave"]
        ms = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(MISSIONS.glob("*.json"))
              if p.stem.lower().startswith(wave.lower() + "-")]
        authored = derive_shape(ms) if ms else "no-missions"
        d = choose(c["objective"], f"{wave}.shadow", c.get("evidence"))
        j = d.get("jev") or {}
        same = authored == d["shape"]
        if authored not in ("unclassified", "no-missions"):
            n += 1
            agree += int(same)
        f = lambda v: f"{v:.2f}" if isinstance(v, (int, float)) else "-"  # noqa: E731
        rows.append((wave, authored, d["shape"], "=" if same else "≠", f(j.get("confidence")),
                     f(j.get("cause_known")), f(j.get("deterministic")), f(j.get("breadth")), d["reason"]))
    print(f"{'wave':5} {'authored':18} {'jev':18} {'':2} {'conf':5} {'known':5} {'det':5} {'brdth':5}  reason")
    for r in rows:
        print(f"{r[0]:5} {r[1]:18} {r[2]:18} {r[3]:2} {r[4]:5} {r[5]:5} {r[6]:5} {r[7]:5}  {r[8]}")
    print(f"-- agreement {agree}/{n} on classified waves; ledger: harness/jev/ledger/<wave>.shadow.shape.jsonl")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--shadow", action="store_true", help="Jev's shape beside each past wave's authored shape")
    ap.add_argument("--objective", help="choose a shape for this objective text")
    ap.add_argument("--wave", default="adhoc")
    ap.add_argument("--expand", action="store_true", help="print mission skeletons for the chosen shape")
    ap.add_argument("--legs", type=int, help="author's count for the fan-out role (clamped to template bounds)")
    ap.add_argument("--out", help="write skeletons here (never missions/)")
    a = ap.parse_args()
    if a.shadow:
        sys.exit(shadow())
    if not a.objective:
        ap.error("--shadow or --objective")
    d = choose(a.objective, a.wave)
    print(f"shape: {d['shape']}  ({d['reason']})")
    if a.expand:
        sk = expand(d["shape"], a.wave, (d.get("jev") or {}).get("breadth"), a.legs)
        txt = json.dumps(sk, indent=1)
        if a.out:
            Path(a.out).write_text(txt, encoding="utf-8")
        print(txt)
