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
#        python harness/jev/jev_grade.py --guard rerank  (grade JEV-RERANK against the probes)
#        python harness/jev/jev_grade.py --guard harvest (grade JEV-HARVEST against Joe's answer key)
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


# --------------------------------------------------------------------------- #
#  --guard rerank: grade JEV-RERANK against the probes' expected outcomes       #
# --------------------------------------------------------------------------- #
def ledgered_rerank(wave):
    """query-prefix -> {hit_i: rel choice} from ok rerank rows; plus (ok, fallback) counts.
    Zero new Jev calls: it replays what jev_rerank already ledgered."""
    out, ok, fb = {}, 0, 0
    p = LEDGER / f"{wave}.rerank.jsonl"
    if not p.exists():
        return out, ok, fb
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("guard") != "rerank":
            continue
        if r.get("result") == "ok" and r.get("answers"):
            ok += 1
            leg = r.get("leg", "")
            if "#" in leg:
                qpref, hi = leg.rsplit("#", 1)
                rel = (r["answers"].get("choices", {}).get("rel_quality") or {}).get("choice")
                out.setdefault(qpref, {})[hi] = rel
        elif r.get("result") in ("fallback", "disabled"):
            fb += 1
    return out, ok, fb


def grade_rerank(waves):
    """Agreement of the ledgered rel judgments against each probe's expected outcome: a
    no-answer probe must return NO hit judged `answers`; an answerable probe's top hit should
    be `answers`/`on_topic`. Unjudged (no key) -> nothing to grade, reported honestly."""
    import jev_rerank as jr  # local import: only needed for this guard
    probes = jr.load_probes()
    policy = jc.load_questions()["guards"]["rerank"].get("policy", {})
    total_ok = total_fb = graded = agree = 0
    header_printed = False
    for w in waves:
        rels, ok, fb = ledgered_rerank(w)
        total_ok += ok
        total_fb += fb
        if not ok:
            continue
        if not header_printed:
            print(f"{'probe':46} {'expect':11} {'top rel':14} verdict")
            header_printed = True
        for p in probes:
            hits = rels.get(p["query"][:48])
            if not hits:
                continue
            graded += 1
            top = hits.get("0")
            ok_probe = (not any(v == "answers" for v in hits.values())) \
                if p["expect"] == "no_answer" else (top in ("answers", "on_topic"))
            agree += bool(ok_probe)
            print(f"{p['query'][:46]:46} {p['expect']:11} {str(top):14} {'agree' if ok_probe else 'MISS'}")
    if total_ok == 0:
        print(f"unjudged: {total_fb} fallback row(s), 0 judged answers in "
              f"{','.join(waves)}.rerank.jsonl -- nothing to grade "
              f"(run `python harness/jev/jev_rerank.py --shadow` with a TYPESAFE_API_KEY).")
        return 0
    print(f"\nagreement: {agree}/{graded} probes on their expected outcome "
          f"(answers_min={policy.get('answers_min')}). Evidence for a scope_weights edit, not a ruling.")
    return 0


# --------------------------------------------------------------------------- #
#  --guard harvest: grade JEV-HARVEST against Joe's answer_key.json             #
# --------------------------------------------------------------------------- #
ANSWER_KEY = jc.REPO / "harness" / "notes" / "harvest" / "answer_key.json"
# Jev's token_kind -> the fix-or-drop action it implies, for grading against Joe's decision.
_KIND_ACTION = {
    "node_type_renamed": "fix", "parameter_name": "fix", "attribute_name": "fix",
    "vex_or_expression_function": "fix", "generic_word": "drop", "cannot_tell": "read",
}


def ledgered_harvest(wave):
    """token -> {"kind": token_kind choice, "suggest_any": bool}; plus (ok, fallback) counts.
    Zero new Jev calls: replays what jev_harvest already ledgered."""
    out, ok, fb = {}, 0, 0
    p = LEDGER / f"{wave}.harvest.jsonl"
    if not p.exists():
        return out, ok, fb
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("guard") != "harvest":
            continue
        if r.get("result") == "ok" and r.get("answers"):
            ok += 1
            leg = r.get("leg", "")
            if not leg.startswith("tok:"):
                continue
            tok = leg[4:]
            ans = r["answers"]
            kind = (ans.get("choices", {}).get("token_kind") or {}).get("choice")
            suggest_any = any((ans.get("nouls", {}).get(k) or {}).get("noul", 0) and
                              (ans["nouls"][k]["noul"] or 0) >= 0.5
                              for k in ("rename_target_0", "rename_target_1", "rename_target_2"))
            out[tok] = {"kind": kind, "suggest_any": suggest_any}
        elif r.get("result") in ("fallback", "disabled"):
            fb += 1
    return out, ok, fb


def grade_harvest(waves):
    """Agreement of Jev's implied fix/drop action against Joe's decision in answer_key.json. The
    key is an EMPTY template until Joe fills it: with no filled decision there is nothing to grade,
    reported honestly (never a fabricated agreement)."""
    key = {}
    if ANSWER_KEY.exists():
        try:
            key = json.loads(ANSWER_KEY.read_text(encoding="utf-8"))
        except ValueError:
            key = {}
    joe = {}  # token -> decision
    for _guide, g in (key.get("quarantined_guides") or {}).items():
        for tok, cell in (g.get("tokens") or {}).items():
            if (cell.get("decision") or "").strip():
                joe[tok] = cell["decision"].strip().lower()
    total_ok = total_fb = graded = agree = 0
    rows = []
    for w in waves:
        judged, ok, fb = ledgered_harvest(w)
        total_ok += ok
        total_fb += fb
        for tok, j in judged.items():
            implied = "fix" if j["suggest_any"] else _KIND_ACTION.get(j["kind"], "read")
            if tok in joe:
                graded += 1
                ok_row = (implied == joe[tok]) or (implied == "fix" and joe[tok] in ("fix", "keep"))
                agree += bool(ok_row)
                rows.append((tok, j["kind"], implied, joe[tok], "agree" if ok_row else "MISS"))
            else:
                rows.append((tok, j["kind"], implied, "—", "(no decision)"))
    if total_ok == 0:
        print(f"unjudged: {total_fb} fallback row(s), 0 judged answers in "
              f"{','.join(waves)}.harvest.jsonl -- nothing to grade "
              f"(run `python harness/jev/jev_harvest.py --shadow` with a TYPESAFE_API_KEY).")
        return 0
    print(f"{'token':26} {'jev token_kind':30} {'implied':8} {'joe':6} verdict")
    for tok, kind, implied, jd, v in sorted(rows):
        print(f"{tok:26} {str(kind):30} {implied:8} {jd:6} {v}")
    if graded == 0:
        print(f"\n{total_ok} judged token(s); answer_key.json has 0 filled decisions -- nothing to "
              f"grade yet. Fill `decision` per token in {ANSWER_KEY.name}, then re-run.")
    else:
        print(f"\nagreement: {agree}/{graded} tokens where Joe filled a decision. Evidence for a "
              f"fix-or-drop pass, not a ruling; the guard never promotes a guide.")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--guard", default="screen", choices=["screen", "rerank", "harvest"],
                    help="which guard to grade (default: screen)")
    ap.add_argument("--wave", action="append", help="grade one wave (repeatable); default: "
                    "every wave with a screen ledger, or bp10 for rerank/harvest")
    a = ap.parse_args()
    if a.guard == "rerank":
        sys.exit(grade_rerank(a.wave or ["bp10"]))
    if a.guard == "harvest":
        sys.exit(grade_harvest(a.wave or ["bp10"]))
    waves = a.wave or sorted({p.name.split(".")[0] for p in LEDGER.glob("*screen.jsonl")})
    sys.exit(grade(waves))
