"""JEV-SALIENCE shadow grader (BP11-SALIENCE / IDENTIFY_BLUEPRINT sec. 5).

Grades the Identify salience question against the MEASURED answer key
(``tests/fixtures/identify_salience_key_v1.json``, built by
``scripts/build_identify_salience_key.py`` under hython). For each node type with
more than two changed-parameter cases -- a real "which two of >2 does the bubble
show?" choice -- it asks Jev one Noul per parameter, ranks the parameters by the
returned salience probability, and compares Jev's top two AND code order's top two
against the key's ``matters`` truth. It prints an agreement table and writes
``harness/jev/ledger/bp11.salience.jsonl``.

One question text in one file: the Noul instructions and the state shape come from
the PRODUCT (``synapse.identify.salience``) -- this grader READS product data, so
it asks exactly what the product asks. The product never imports this harness
(invariant 5, ``tests/test_jev_product_boundary.py``).

Fail closed (JEV invariant 4): with ``SYNAPSE_JEV=off``, no key, or no TypeSafe
access, every ``ask()`` returns None, so the Jev side of the table reads UNKNOWN,
never 0. Code order is derived from the key alone, so its counts print regardless.

Usage:  python harness/jev/jev_salience.py --shadow
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import jev_client as jc  # noqa: E402

REPO = jc.REPO
if str(REPO / "python") not in sys.path:
    sys.path.insert(0, str(REPO / "python"))
from synapse.identify import salience as psal  # noqa: E402  (harness reads product data)

WAVE, GUARD = "bp11", "salience"
KEY = REPO / "tests" / "fixtures" / "identify_salience_key_v1.json"
MIN_GROUP = 3  # a top-2 choice needs more than two survivors
TOP_K = 2


def load_key() -> dict | None:
    try:
        return json.loads(KEY.read_text(encoding="utf-8"))
    except Exception:
        return None


def _group(cases):
    groups: dict = {}
    for case in cases:
        groups.setdefault((case["context"], case["node_type"]), []).append(case)
    return groups


def _code_top2(group):
    """First two parameters in template order — what the bubble shows today."""
    ordered = sorted(group, key=lambda c: (c.get("template_order", 1 << 30), c["parm"]))
    return [c["parm"] for c in ordered[:TOP_K]]


def _ask_jev(group, batch):
    """One Noul per parameter. Returns {parm: noul} or None if any ask fails."""
    scores = {}
    for case in group:
        state = psal.build_state(
            node_type=case["node_type"], node_category=case["node_category"],
            node_summary="", parm_label=case["parm_label"],
            parm_help=case.get("parm_help", ""), parm_type=case["parm_type"],
        )
        answers = jc.ask(state, batch, wave=WAVE, guard=GUARD, leg="BP11-SALIENCE")
        noul = None
        if answers:
            noul = (answers.get("nouls", {}).get(psal.QID) or {}).get("noul")
        if not isinstance(noul, (int, float)):
            return None  # fail closed: one missing answer -> the group is UNKNOWN
        scores[case["parm"]] = noul
    return scores


def grade(shadow: bool):
    key = load_key()
    if not key:
        print("SALIENCE: UNKNOWN - no answer key at", KEY)
        jc.ledger(WAVE, GUARD, {"result": "fallback", "reason": "no_key_file", "leg": "BP11-SALIENCE"})
        return 0
    have_access = bool(psal.adapter.resolve_key()) and jc.enabled()
    batch = psal.question_batch()
    groups = _group(key.get("cases", []))
    gradeable = {k: g for k, g in groups.items() if len(g) >= MIN_GROUP}

    rows = []
    code_total = jev_total = possible_total = 0
    jev_known = have_access
    jev_wins = jev_ties = jev_losses = 0
    for (ctx, tname), group in sorted(gradeable.items()):
        matters = {c["parm"] for c in group if c["matters"]}
        possible = min(TOP_K, len(matters))
        code2 = _code_top2(group)
        code_hits = sum(1 for p in code2 if p in matters)
        jev2, jev_hits = None, None
        if have_access:
            scores = _ask_jev(group, batch)
            if scores is None:
                jev_known = False
            else:
                jev2 = [p for p, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:TOP_K]]
                jev_hits = sum(1 for p in jev2 if p in matters)
        rows.append({"ctx": ctx, "type": tname, "n": len(group), "matters": len(matters),
                     "possible": possible, "code2": code2, "code_hits": code_hits,
                     "jev2": jev2, "jev_hits": jev_hits})
        code_total += code_hits
        possible_total += possible
        if jev_hits is not None:
            jev_total += jev_hits
            jev_wins += jev_hits > code_hits
            jev_ties += jev_hits == code_hits
            jev_losses += jev_hits < code_hits

    _print_table(key, rows, have_access, jev_known, code_total, jev_total,
                 possible_total, jev_wins, jev_ties, jev_losses)

    jev_agree = (f"{jev_total}/{possible_total}" if (have_access and jev_known) else "UNKNOWN")
    jc.ledger(WAVE, GUARD, {
        "result": "graded", "leg": "BP11-SALIENCE", "mode": "shadow" if shadow else "grade",
        "key_build": key.get("build"), "key_cases": key.get("summary", {}).get("n_cases"),
        "gradeable_groups": len(rows), "code_agree": f"{code_total}/{possible_total}",
        "jev_agree": jev_agree, "jev_wins": (jev_wins if jev_known and have_access else None),
        "access": have_access, "question_version": psal.question_version(),
    })
    return 0


def _print_table(key, rows, have_access, jev_known, code_total, jev_total,
                 possible_total, jev_wins, jev_ties, jev_losses):
    judged = "judged" if (have_access and jev_known) else "UNJUDGED (no TypeSafe access -> Jev columns UNKNOWN)"
    print("=" * 72)
    print("JEV-SALIENCE shadow grade  [%s]" % judged)
    print("key: %s  build=%s  cases=%s  question=%s"
          % (KEY.name, key.get("build"), key.get("summary", {}).get("n_cases"),
             psal.question_version()))
    print("-" * 72)
    print("%-18s %4s %7s | %-16s %5s | %-16s %5s"
          % ("node type", "parm", "matters", "code top-2", "hit", "jev top-2", "hit"))
    print("-" * 72)
    for r in rows:
        jev2 = ",".join(r["jev2"]) if r["jev2"] is not None else "UNKNOWN"
        jev_hit = str(r["jev_hits"]) if r["jev_hits"] is not None else "UNK"
        print("%-18s %4d %7d | %-16s %5d | %-16s %5s"
              % (r["type"][:18], r["n"], r["matters"],
                 ",".join(r["code2"])[:16], r["code_hits"], jev2[:16], jev_hit))
    print("-" * 72)
    jev_agree = (f"{jev_total}/{possible_total}" if (have_access and jev_known) else "UNKNOWN")
    print("TOTAL groups=%d   code-order agree=%d/%d   jev agree=%s"
          % (len(rows), code_total, possible_total, jev_agree))
    if have_access and jev_known:
        print("jev vs code (per group): wins=%d ties=%d losses=%d  (promotion bar R-2: jev wins overall)"
              % (jev_wins, jev_ties, jev_losses))
    else:
        print("jev vs code: UNKNOWN - run with SYNAPSE_JEV=on and a TypeSafe key to grade Jev live")
    print("ledger: harness/jev/ledger/%s.%s.jsonl" % (WAVE, GUARD))
    print("=" * 72)


def main(argv=None):
    ap = argparse.ArgumentParser(description="JEV-SALIENCE shadow grader (BP11-SALIENCE)")
    ap.add_argument("--shadow", action="store_true",
                    help="grade Jev top-2 and code-order top-2 against the measured key")
    args = ap.parse_args(argv)
    if not args.shadow:
        ap.print_help()
        return 0
    return grade(shadow=True)


if __name__ == "__main__":
    sys.exit(main())
