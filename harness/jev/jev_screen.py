# jev_screen.py - JEV-SCREEN guard: builder receipt -> one line in the CRUX brief.
# Runs after a builder's receipt lands and before CRUX flips ready. Jev judges, per
# acceptance row, whether the receipt's EVIDENCE TEXT supports the PREDICATE; plus whether
# the receipt contradicts itself and how deep the referee must read. decide() turns that
# into CLEAR | REFEREE | FLAG. The verdict never removes the crucible - it sets where the
# crucible starts reading. Fail closed = REFEREE (full read), ledgered.
# Source: harness/battleplan/notes/JEV_BLUEPRINT.md sec.3.2. Policy calibrated 2026-09-29 on 20
# CRUX-judged legs (BP4, BP8, BP10, BP11) by calibrate_screen.py: no BROKEN leg clears, and 6 of
# 15 sound legs do, where the first policy cleared none (BP12 item 8).
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jev_client as jc  # noqa: E402

REPO = jc.REPO
MISSIONS = REPO / "harness" / "battleplan" / "missions"
RECEIPTS = REPO / "harness" / "notes" / "receipts"
NOTES = REPO / "harness" / "battleplan" / "notes"


def screen_state(m: dict, r: dict, fields: dict) -> dict:
    return {"mission": {k: m[k] for k in fields["mission"] if k in m},
            "receipt": {k: r[k] for k in fields["receipt"] if k in r}}


def screen_spec(n_rows: int) -> dict:
    g = jc.load_questions()["guards"]["screen"]["questions"]
    row = g["acceptance_row"]
    spec = {}
    for i in range(n_rows):
        instr = json.loads(json.dumps(row["instructions"]).replace("{i}", str(i)))
        spec[f"acc_{i}"] = {"type": "choice", "instructions": instr, "criteria": row["criteria"]}
    spec["self_contradiction"] = {"type": "noul", "instructions": g["self_contradiction"]["instructions"]}
    spec["crux_need"] = {"type": "score", "instructions": g["crux_need"]["instructions"], "criteria": g["crux_need"]["criteria"]}
    return spec


def decide(n_rows: int, answers: dict | None, policy: dict) -> dict:
    """CLEAR | REFEREE | FLAG from Jev's answers under the calibrated policy.

    A row is FLAGged when Jev puts ``flag_does_not_support_min`` or more on
    does_not_support. A row the receipt marks UNKNOWN (``claims_unknown``, a
    GUI row say) is neutral: the referee records it UNKNOWN too, so it neither
    blocks CLEAR nor counts as weak. Any other row is weak unless Jev chose
    ``supports`` with at least ``weak_below_support`` probability on it. CLEAR
    needs no weak row, self-contradiction at most ``clear_max_self_contradiction``
    and crux need at most ``clear_max_crux_need``. The thresholds were fitted to
    CRUX's own verdicts by ``calibrate_screen.py`` (BP12 item 8).
    """
    fb = policy["fallback_verdict"]
    if answers is None:
        return {"verdict": fb, "reason": "fallback: no Jev answer (see ledger)", "rows": [],
                "unknown": [], "jev": None}
    rows, flags, weak, unknown = [], [], [], []
    for i in range(n_rows):
        a = answers["choices"].get(f"acc_{i}") or {}
        p = a.get("probabilities") or {}
        choice = a.get("choice")
        rows.append({"i": i, "choice": choice, "confidence": a.get("confidence"), "p": p})
        if p.get("does_not_support", 0.0) >= policy["flag_does_not_support_min"]:
            flags.append(i)
        elif choice == "claims_unknown":
            unknown.append(i)
        elif not (choice == "supports" and p.get("supports", 0.0) >= policy["weak_below_support"]):
            weak.append(i)
    sc = (answers["nouls"].get("self_contradiction") or {}).get("noul")
    cn = (answers["scores"].get("crux_need") or {}).get("score")
    jev = {"rows": rows, "self_contradiction": sc, "crux_need": cn}
    if flags:
        return {"verdict": "FLAG", "reason": f"row(s) {flags} evidence does not support predicate",
                "rows": flags, "unknown": unknown, "jev": jev}
    clear = (not weak and sc is not None and sc <= policy["clear_max_self_contradiction"]
             and cn is not None and cn <= policy["clear_max_crux_need"])
    if clear:
        return {"verdict": "CLEAR",
                "reason": f"every checkable row supported; self_contradiction {sc:.2f}; crux_need {cn:.2f}",
                "rows": [], "unknown": unknown, "jev": jev}
    why = []
    if weak:
        why.append(f"weak rows {weak}")
    if sc is not None and sc > policy["clear_max_self_contradiction"]:
        why.append(f"self_contradiction {sc:.2f}")
    if cn is not None and cn > policy["clear_max_crux_need"]:
        why.append(f"crux_need {cn:.2f}")
    return {"verdict": "REFEREE", "reason": "; ".join(why) or "no clear signal", "rows": weak,
            "unknown": unknown, "jev": jev}


def brief_line(leg: str, d: dict, n_rows: int) -> str:
    """The one line that goes into the CRUX prompt for this leg."""
    unknown = d.get("unknown") or []
    tail = f"; rows {unknown} claim UNKNOWN and stay UNKNOWN" if unknown else ""
    if d["verdict"] == "CLEAR":
        spot = min(2, n_rows)
        return f"screen {leg}: CLEAR - spot-check {spot} of {n_rows} rows, then author mutations as usual{tail}"
    if d["verdict"] == "FLAG":
        return f"screen {leg}: FLAG rows {d['rows']} - start there; {d['reason']}{tail}"
    return f"screen {leg}: REFEREE - full read; {d['reason']}{tail}"


# Count check in CODE (2026-09-20, docs.typesafe.ai/model-jaggedness/jev-1.13: "Jev is not a calculator
# ... does not count reliably"; workaround: "move arithmetic, counting ... to code"). Screen rule 2 asked
# Jev to notice a reported count differing from the expected one; on BP4-RULINGS (22 expected, 21
# reported, CRUX: BROKEN) it put only 0.25 on does_not_support. Code does this exactly.
_COUNT_NOUNS = r"(?:rows?|items?|entries|receipts?|files?|legs?|tests?|records?|hypotheses|missions?|verdicts?|mutations?)"
_COUNT_RE = re.compile(r"\b(\d{1,5})\s+" + _COUNT_NOUNS + r"\b", re.IGNORECASE)


def count_mismatch_rows(m: dict, r: dict) -> list[dict]:
    """Rows whose evidence reports a '<n> <count-noun>' that matches NO count named in the mission
    note or predicates. Turn caps, line windows and the like never match the noun list. Pure code."""
    expected = set(_COUNT_RE.findall(str(m.get("note", "")) + " " + " ".join(a.get("predicate", "") for a in m.get("acceptance", []))))
    if not expected:
        return []
    out = []
    for i, a in enumerate(r.get("acceptance") or []):
        reported = set(_COUNT_RE.findall(str((a or {}).get("evidence", ""))))
        if reported and reported.isdisjoint(expected):
            out.append({"i": i, "reported": sorted(reported), "expected": sorted(expected)})
    return out


def screen_leg(m: dict, r: dict, wave: str) -> dict:
    g = jc.load_questions()["guards"]["screen"]
    n = len(m.get("acceptance") or [])
    if n == 0 or not r.get("acceptance"):
        d = {"verdict": g["policy"]["fallback_verdict"], "reason": "no acceptance rows to screen", "rows": [], "jev": None}
    else:
        state = screen_state(m, r, g["state_fields"])
        answers = jc.ask(state, screen_spec(n), wave=wave, guard="screen", leg=m["id"])
        d = decide(n, answers, g["policy"])
        cm = count_mismatch_rows(m, r)
        if cm:  # code outranks judgment here: a count is a fact, and the referee re-counts anyway
            rows = sorted(set(d["rows"]) | {c["i"] for c in cm}) if d["verdict"] == "FLAG" else [c["i"] for c in cm]
            why = "; ".join(f"row {c['i']} reports {'/'.join(c['reported'])} but the mission expects {'/'.join(c['expected'])}" for c in cm)
            d = {**d, "verdict": "FLAG", "rows": rows, "reason": f"code: count mismatch - {why}" + (f" | jev: {d['reason']}" if d.get("jev") else ""), "code_flags": cm}
    d["brief_line"] = brief_line(m["id"], d, n)
    jc.ledger(wave, "screen", {"leg": m["id"], "result": "decision", "decision": d, "crux": "pending"})
    return d


def _crux_verdicts(wave: str) -> dict:
    """Best-effort parse of BP<n>-CRUX_verdicts.md -> {leg: SOUND|SOUND-WITH-NITS|BROKEN}."""
    out = {}
    for p in sorted(NOTES.glob(f"{wave.upper()}-CRUX*_verdicts.md")):
        txt = p.read_text(encoding="utf-8", errors="replace")
        for leg, v in re.findall(r"(BP\d+-[A-Z0-9]+)\b[^\n]{0,80}?\b(SOUND-WITH-NITS|SOUND|BROKEN)\b", txt):
            out.setdefault(leg, v)
    return out


def record_crux(wave: str) -> int:
    """Append each screened leg's CRUX verdict to the wave's screen ledger.

    The ledger then carries its own answer key: ``calibrate_screen.py`` joins
    every ``decision`` row with the ``crux_reading`` row for the same leg. Run it
    once CRUX has written its verdicts. Returns how many readings were added.
    """
    crux = _crux_verdicts(wave)
    path = jc.LEDGER_DIR / f"{wave}.screen.jsonl"
    screened = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("result") == "decision" and row.get("leg"):
                screened.append(row["leg"])
    added = 0
    for leg in dict.fromkeys(screened):
        if leg in crux:
            jc.ledger(wave, "screen", {"leg": leg, "result": "crux_reading", "crux": crux[leg]})
            added += 1
    print(f"-- {added} crux reading(s) added to {path.name}")
    return added


def shadow(wave: str) -> int:
    files = sorted(p for p in MISSIONS.glob("*.json") if p.stem.lower().startswith(wave.lower() + "-"))
    crux = _crux_verdicts(wave)
    rows = []
    for f in files:
        m = json.loads(f.read_text(encoding="utf-8"))
        if m.get("class") == "crucible":
            continue
        rp = RECEIPTS / m.get("receipt", f"{m['id']}.json")
        if not rp.exists():
            rows.append((m["id"], "-", "no receipt", "-", ""))
            continue
        r = json.loads(rp.read_text(encoding="utf-8", errors="replace"))
        d = screen_leg(m, r, f"{wave}.shadow")
        rows.append((m["id"], r.get("status", "-"), d["verdict"], crux.get(m["id"], "-"), d["reason"]))
    w = max(len(r[0]) for r in rows) if rows else 12
    print(f"{'leg':{w}}  {'receipt':8} {'screen':8} {'crux':16} reason")
    for r in rows:
        print(f"{r[0]:{w}}  {str(r[1])[:8]:8} {r[2]:8} {r[3]:16} {r[4]}")
    print(f"-- ledger: harness/jev/ledger/{wave}.shadow.screen.jsonl")
    print("-- read: a FLAG beside a crux BROKEN, and CLEAR/REFEREE beside SOUND*, is agreement")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", required=True)
    ap.add_argument("--leg", help="screen one leg and print its brief line")
    ap.add_argument("--record-crux", action="store_true",
                    help="append CRUX's verdicts to the wave's screen ledger (the answer key)")
    a = ap.parse_args()
    if a.record_crux:
        record_crux(a.wave)
        sys.exit(0)
    if a.leg:
        m = json.loads((MISSIONS / f"{a.leg}.json").read_text(encoding="utf-8"))
        r = json.loads((RECEIPTS / m.get("receipt", f"{a.leg}.json")).read_text(encoding="utf-8", errors="replace"))
        d = screen_leg(m, r, a.wave)
        print(d["brief_line"])
        sys.exit(0)
    sys.exit(shadow(a.wave))
