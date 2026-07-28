"""I0 — cross-validate _i0_reader against H9's helpdoc, two independent parsers.

R60 asks for calibration against a KNOWN answer. The strongest available "known"
here is a second instrument built by a different leg, on the same archive, whose
own defects are documented. Where they agree, both numbers get stronger. Where
they disagree, the disagreement is the finding — not something to average away.

Both are run with includes RESOLVED so the comparison is like-for-like.

Run: python -c "exec(open('harness/notes/ingest/_i0_xvalidate.py',encoding='utf-8').read())"
"""

from __future__ import annotations

import json
import os
import statistics
import sys

_HERE = os.path.abspath("harness/notes/ingest")
_H9 = os.path.abspath("harness/notes/h9")
for _p in (_HERE, _H9):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import helpdoc  # noqa: E402

from _i0_reader import (BUILD, open_archive, page_names, parse_page,  # noqa: E402
                        read_page)


def main() -> dict:
    z = open_archive()
    corpus = helpdoc.HelpCorpus()
    out = {"schema": "i0-xvalidate/v1", "build": BUILD,
           "producer": "harness/notes/ingest/_i0_xvalidate.py",
           "instrument_a": "harness/notes/ingest/_i0_reader.py",
           "instrument_b": "harness/notes/h9/helpdoc.py", "contexts": {}}

    for ctx in ("cop", "cop2", "lop"):        # helpdoc's own CONTEXTS
        agree = same = 0
        diffs = []
        deltas = []
        for n in page_names(z, ctx):
            stem = n.split("/", 1)[1][:-4]
            key = f"nodes/{ctx}/{stem}"
            if key not in corpus.pages:
                continue
            raw = read_page(z, n)
            if not helpdoc.is_node_page(key, raw):
                continue
            mine = parse_page(n, helpdoc.resolve_includes(
                raw, corpus, f"nodes/{ctx}", self_key=key))
            theirs = helpdoc.parse_page(key, corpus)
            a, b = len(mine.params), len(theirs["parameters"])
            agree += 1
            deltas.append(a - b)
            if a == b:
                same += 1
            else:
                diffs.append({"page": n, "i0": a, "h9": b, "delta": a - b})
        diffs.sort(key=lambda d: -abs(d["delta"]))
        out["contexts"][ctx] = {
            "pages_compared": agree,
            "exact_agreement": same,
            "exact_agreement_pct": round(100.0 * same / agree, 1) if agree else None,
            "median_delta": statistics.median(deltas) if deltas else None,
            "mean_abs_delta": round(sum(abs(d) for d in deltas) / len(deltas), 2) if deltas else None,
            "largest_disagreements": diffs[:10],
        }

    p = os.path.join(_HERE, "_i0_xvalidate.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    print(f"{'ctx':6s} {'compared':>9s} {'exact':>7s} {'agree%':>8s} "
          f"{'med d':>6s} {'mean|d|':>8s}")
    for ctx, r in out["contexts"].items():
        print(f"{ctx:6s} {r['pages_compared']:9d} {r['exact_agreement']:7d} "
              f"{str(r['exact_agreement_pct']):>8s} {str(r['median_delta']):>6s} "
              f"{str(r['mean_abs_delta']):>8s}")
    print("\nlargest disagreements (i0 - h9):")
    for ctx, r in out["contexts"].items():
        for d in r["largest_disagreements"][:4]:
            print(f"   {d['page']:34s} i0={d['i0']:4d} h9={d['h9']:4d} delta={d['delta']:+d}")
    print(f"\nwrote {p}")
    return out


REPORT = main()
