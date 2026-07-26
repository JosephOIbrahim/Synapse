"""H8 — merge the sweep's per-agent results into one verdict per ruling.

Producer for every count in RULING_AUDIT.json and in the H8 receipt. Run:

    python harness/notes/h8/merge_verdicts.py <sweep_journal.jsonl> [<verify_journal.jsonl> ...]

Law 2: this file IS the producer path. Every integer the audit reports comes out of here, and
the resolution rules below are the whole method — there is no hand-adjustment step.

Resolution order for a ruling's FINAL verdict:
  1. an adversarial `verify` adjudication, if one exists  (it is the last word by design)
  2. otherwise, unanimous agreement across the find lenses
  3. otherwise, highest-precedence verdict among the lenses, flagged `split: true`

`enforcement` is resolved separately and deliberately pessimistically: an anchor prefixed
"UNMERGED:" does NOT protect this branch and is demoted to `unmerged_only`.
"""
import json
import sys
from collections import defaultdict

PRECEDENCE = [
    "EVIDENCE_FAILS", "CONTRADICTED", "SUPERSEDED_UNMARKED", "SCOPE_ERROR",
    "UNFALSIFIABLE", "UNENFORCED", "SOUND",
]
RANK = {v: i for i, v in enumerate(PRECEDENCE)}


def load_results(paths):
    """Yield every {'type':'result'} payload across the given journals."""
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                if d.get("type") == "result" and isinstance(d.get("result"), dict):
                    yield d["result"]


def demote_unmerged(enf, anchor):
    """A mechanism on an unmerged branch does not protect this tree (sweep rule 4b)."""
    if anchor and str(anchor).strip().upper().startswith("UNMERGED:"):
        return "unmerged_only"
    return enf


def main(paths):
    find = defaultdict(list)   # ruling -> [verdict dicts from evidence/cto lenses]
    verify = {}                # ruling -> adjudication dict

    for res in load_results(paths):
        for v in res.get("verdicts", []) or []:
            find[v["ruling"]].append(v)
        for a in res.get("adjudications", []) or []:
            verify[a["ruling"]] = a

    out = []
    for n in range(1, 79):
        lenses = find.get(n, [])
        adj = verify.get(n)

        if adj:
            verdict = adj["final_verdict"]
            source = "adversarial_verify"
            reason = adj.get("reason", "")
            evidence = adj.get("evidence", "")
            enf = demote_unmerged(adj.get("enforcement"), adj.get("enforcement_anchor"))
            anchor = adj.get("enforcement_anchor", "")
            also = adj.get("also_applies", []) or []
            split = False
        elif lenses:
            kinds = {v["primary_verdict"] for v in lenses}
            split = len(kinds) > 1
            verdict = sorted(kinds, key=lambda k: RANK[k])[0]
            source = "unanimous" if not split else "precedence_of_split"
            best = sorted(lenses, key=lambda v: RANK[v["primary_verdict"]])[0]
            reason = best.get("reason", "")
            evidence = best.get("evidence", "")
            enf = demote_unmerged(best.get("enforcement"), best.get("enforcement_anchor"))
            anchor = best.get("enforcement_anchor", "")
            also = sorted({a for v in lenses for a in (v.get("also_applies") or [])})
        else:
            verdict, source, reason, evidence = "MISSING", "no_lens_returned", "", ""
            enf, anchor, also, split = "unknown", "", [], False

        out.append({
            "ruling": n, "verdict": verdict, "resolved_by": source, "split_lenses": split,
            "reason": reason, "evidence": evidence,
            "enforcement": enf, "enforcement_anchor": anchor,
            "also_applies": also, "lens_count": len(lenses),
        })

    counts = defaultdict(int)
    for r in out:
        counts[r["verdict"]] += 1

    enf_counts = defaultdict(int)
    for r in out:
        enf_counts[r["enforcement"]] += 1

    # The headline number, both ways — primary verdict, and "applies at all".
    unenforced_primary = counts["UNENFORCED"]
    unenforced_any = sum(
        1 for r in out
        if r["verdict"] == "UNENFORCED"
        or "UNENFORCED" in r["also_applies"]
        or r["enforcement"] in ("none", "unmerged_only")
    )

    print(json.dumps({
        "counts": {k: counts.get(k, 0) for k in PRECEDENCE + ["MISSING"]},
        "total": sum(counts.values()),
        "enforcement": dict(enf_counts),
        "unenforced_primary_verdict": unenforced_primary,
        "unenforced_any_basis": unenforced_any,
        "split_lenses": sum(1 for r in out if r["split_lenses"]),
        "verdicts": out,
    }, indent=1))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: merge_verdicts.py <journal.jsonl> [...]")
    main(sys.argv[1:])
