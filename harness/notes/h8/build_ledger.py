"""H8 — build harness/notes/RULING_AUDIT.json from the sweep journals.

    python harness/notes/h8/build_ledger.py <sweep.jsonl> <adjudication.jsonl> <out.json>

Law 2: this is the producer path for every integer in RULING_AUDIT.json and in the H8 receipt.
Nothing downstream is hand-edited.

Three sources, resolved in this order (later wins):
  1. find lenses      — crucible evidence batches + sidefx-cto halves (2 lenses per ruling)
  2. adversarial verify — crucible attack on every ruling the lenses disagreed on
  3. final adjudication — crucible attack on cross-lens claims the verify pass never saw

The cross-lens consistency agents (h22-adjudicator) emit `pairs`, not verdicts. Their
non-NOT_AFFECTED calls are folded into `also_applies` — they are specialist secondary findings,
and they are the only source that answers "is the ORIGINAL marked in place".
"""
import json
import sys
from collections import defaultdict

PRECEDENCE = ["EVIDENCE_FAILS", "CONTRADICTED", "SUPERSEDED_UNMARKED", "SCOPE_ERROR",
              "UNFALSIFIABLE", "UNENFORCED", "SOUND"]
RANK = {v: i for i, v in enumerate(PRECEDENCE)}


def results(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("type") == "result" and isinstance(d.get("result"), dict):
                yield d["result"]


def demote(enf, anchor):
    if anchor and str(anchor).strip().upper().startswith("UNMERGED:"):
        return "unmerged_only"
    return enf


def main(sweep, adjud, out_path):
    find, verify, pairs, final = defaultdict(list), {}, [], {}

    for r in results(sweep):
        for v in r.get("verdicts", []) or []:
            find[v["ruling"]].append(v)
        for a in r.get("adjudications", []) or []:
            verify[a["ruling"]] = a
        for p in r.get("pairs", []) or []:
            pairs.append(p)

    for r in results(adjud):
        if "final_verdict" in r and "ruling" in r:
            final[r["ruling"]] = r

    # cross-lens secondary findings + the marked-in-place question
    cross = defaultdict(set)
    cross_ev = defaultdict(list)
    marked_any = False
    for p in pairs:
        if p.get("original_marked_in_place"):
            marked_any = True
        if p["verdict_for_earlier"] != "NOT_AFFECTED":
            cross[p["earlier"]].add(p["verdict_for_earlier"])
            cross_ev[p["earlier"]].append(f"R{p['later']} [{p['relation']}]")

    ledger = []
    for n in range(1, 79):
        lenses, adj, fin = find.get(n, []), verify.get(n), final.get(n)

        if fin:
            verdict, src = fin["final_verdict"], "final_adjudication"
            reason, evidence = fin.get("reason", ""), fin.get("evidence", "")
            enf = demote(fin.get("enforcement"), fin.get("enforcement_anchor"))
            anchor, also = fin.get("enforcement_anchor", ""), set(fin.get("also_applies") or [])
        elif adj:
            verdict, src = adj["final_verdict"], "adversarial_verify"
            reason, evidence = adj.get("reason", ""), adj.get("evidence", "")
            enf = demote(adj.get("enforcement"), adj.get("enforcement_anchor"))
            anchor, also = adj.get("enforcement_anchor", ""), set(adj.get("also_applies") or [])
        elif lenses:
            kinds = {v["primary_verdict"] for v in lenses}
            verdict = sorted(kinds, key=lambda k: RANK[k])[0]
            src = "unanimous_lenses" if len(kinds) == 1 else "precedence_of_split"
            best = sorted(lenses, key=lambda v: RANK[v["primary_verdict"]])[0]
            reason, evidence = best.get("reason", ""), best.get("evidence", "")
            enf = demote(best.get("enforcement"), best.get("enforcement_anchor"))
            anchor = best.get("enforcement_anchor", "")
            also = {a for v in lenses for a in (v.get("also_applies") or [])}
        else:
            verdict, src, reason, evidence = "MISSING", "no_lens", "", ""
            enf, anchor, also = "unknown", "", set()

        # fold cross-lens secondaries in, never displacing the adjudicated primary
        also |= {c for c in cross.get(n, set()) if c != verdict}
        also.discard(verdict)

        row = {
            "ruling": n,
            "verdict": verdict,
            "reason": reason,
            "evidence": evidence,
            "also_applies": sorted(also),
            "enforcement": enf,
            "enforcement_anchor": anchor,
            "resolved_by": src,
            "lenses": len(lenses) + (1 if adj else 0) + (1 if fin else 0),
        }
        if cross_ev.get(n):
            row["superseding_rulings"] = sorted(set(cross_ev[n]))
        ledger.append(row)

    counts = {k: sum(1 for r in ledger if r["verdict"] == k) for k in PRECEDENCE}
    missing = sum(1 for r in ledger if r["verdict"] == "MISSING")
    enf_counts = defaultdict(int)
    for r in ledger:
        enf_counts[r["enforcement"]] += 1

    any_basis = {
        k: sum(1 for r in ledger if r["verdict"] == k or k in r["also_applies"])
        for k in PRECEDENCE
    }
    no_mechanism = sum(1 for r in ledger if r["enforcement"] in ("none", "unmerged_only"))

    doc = {
        "counts": counts,
        "counts_total": sum(counts.values()) + missing,
        "missing": missing,
        "counts_any_basis": any_basis,
        "enforcement": dict(enf_counts),
        "rulings_with_no_mechanism_on_this_branch": no_mechanism,
        "any_original_marked_in_place": marked_any,
        "cross_lens_pair_rows": len(pairs),
        "verdicts": ledger,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)

    print(json.dumps({k: v for k, v in doc.items() if k != "verdicts"}, indent=1))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: build_ledger.py <sweep.jsonl> <adjudication.jsonl> <out.json>")
    main(*sys.argv[1:])
