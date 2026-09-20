# jev_grade.py - grade the SCREEN guard against CRUX, with ZERO new Jev calls.
# Every raw probability Jev returned is in harness/jev/ledger/<wave>[.shadow].screen.jsonl. CRUX's
# verdicts are in harness/battleplan/notes/<WAVE>-CRUX_verdicts.md. This replays jev_screen.decide()
# over the ledgered answers under the CURRENT policy and under candidate policies, and reports how
# each would have agreed with the referee. A policy change is a text diff; it never needs
# re-inference when the questions and evidence are unchanged (TypeSafe: judgments are reusable data).
# Grading rule: BROKEN -> FLAG is a hit, REFEREE is safe, CLEAR is a MISS (the only dangerous cell).
#               SOUND  -> CLEAR is ideal, REFEREE is over-caution (a full read that was not needed).
# Usage: python harness/jev/jev_grade.py                 (all waves with both a ledger and verdicts)
#        python harness/jev/jev_grade.py --wave bp4
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jev_client as jc  # noqa: E402
import jev_screen as js  # noqa: E402

LEDGER = jc.LEDGER_DIR
CANDIDATES = {
    "current": {},
    "flag-on-contradiction": {"_rule": "self_contradiction >= 0.6 and crux_need >= 1.5 -> FLAG"},
    "flag-dns-0.4": {"flag_does_not_support_min": 0.4},
    "clear-need-0.9": {"clear_max_crux_need": 0.9},
    "clear-conf-0.7": {"clear_min_support_confidence": 0.7},
}


def ledgered_answers(wave: str) -> dict:
    """leg -> the LAST raw `ok` screen answer for that leg, from the live ledger or the shadow one."""
    out = {}
    for name in (f"{wave}.screen.jsonl", f"{wave}.shadow.screen.jsonl"):
        p = LEDGER / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("guard") == "screen" and r.get("result") == "ok" and r.get("answers"):
                out[r["leg"]] = r["answers"]
    return out


def replay(answers: dict, policy: dict, cand: dict) -> str:
    n = sum(1 for k in answers.get("choices", {}) if k.startswith("acc_"))
    d = js.decide(n, answers, {**policy, **{k: v for k, v in cand.items() if not k.startswith("_")}})
    if cand.get("_rule") and d["verdict"] != "FLAG":
        sc = (answers["nouls"].get("self_contradiction") or {}).get("noul") or 0.0
        cn = (answers["scores"].get("crux_need") or {}).get("score") or 0.0
        if sc >= 0.6 and cn >= 1.5:
            return "FLAG"
    return d["verdict"]


def grade(waves: list[str]) -> int:
    policy = jc.load_questions()["guards"]["screen"]["policy"]
    pairs = []  # (wave, leg, crux_verdict, answers)
    for w in waves:
        crux = js._crux_verdicts(w)
        ans = ledgered_answers(w)
        for leg, a in sorted(ans.items()):
            if leg in crux and not leg.endswith("-CRUX"):
                pairs.append((w, leg, crux[leg], a))
    if not pairs:
        print("nothing to grade: no leg has both a ledgered screen answer and a CRUX verdict")
        return 1
    print(f"{'leg':16} {'CRUX':16} " + " ".join(f"{c:24}" for c in CANDIDATES))
    for w, leg, v, a in pairs:
        print(f"{leg:16} {v:16} " + " ".join(f"{replay(a, policy, c):24}" for c in CANDIDATES.values()))
    print()
    print(f"{'policy':24} {'n':>3} {'BROKEN->FLAG':>13} {'BROKEN->CLEAR(miss)':>20} {'SOUND->CLEAR':>13} {'SOUND->REFEREE':>15}")
    for name, cand in CANDIDATES.items():
        hit = miss = ideal = over = 0
        for w, leg, v, a in pairs:
            s = replay(a, policy, cand)
            if v == "BROKEN":
                hit += s == "FLAG"; miss += s == "CLEAR"
            elif v.startswith("SOUND"):  # SOUND and SOUND-WITH-NITS both mean the builder was right
                ideal += s == "CLEAR"; over += s == "REFEREE"
        print(f"{name:24} {len(pairs):>3} {hit:>13} {miss:>20} {ideal:>13} {over:>15}")
    print("\nn is small; this is evidence for a ruling, not a ruling. Re-run after every wave with CRUX verdicts.")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", action="append", help="grade one wave (repeatable); default: every wave with a screen ledger")
    a = ap.parse_args()
    waves = a.wave or sorted({p.name.split(".")[0] for p in LEDGER.glob("*screen.jsonl")})
    sys.exit(grade(waves))
