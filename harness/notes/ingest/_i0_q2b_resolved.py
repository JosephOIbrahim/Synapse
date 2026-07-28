"""I0 / Q2b — the join key measured on RESOLVED pages, not just raw ones.

_i0_q2_joinkey.py measures the raw page as it ships. That under-samples exactly
the pages where the join is hardest: lop/distantlight documents 0 parameters raw
and 87 resolved, and lop is the context where #id does worst (10 of 106 on
rendersettings). Leaving that inferred would be a Law 2 gap in the leg's own
headline answer, so it is measured.

Same six candidate keys, same seed, same controls — the ONLY change is that
:include/:includeprop/:import are expanded first.

Run: hython harness/notes/ingest/_i0_q2b_resolved.py
"""

from __future__ import annotations

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_H9 = os.path.join(os.path.dirname(HERE), "h9")
for _p in (HERE, _H9):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hou  # noqa: E402

import helpdoc  # noqa: E402

from _i0_q2_joinkey import (HAND_PICKED, POP_SAMPLE_PER_CTX, SEED,  # noqa: E402
                            live_parms, norm_label, score)
from _i0_reader import (BUILD, open_archive, page_names, parse_page,  # noqa: E402
                        read_page)


def main() -> int:
    z = open_archive()
    corpus = helpdoc.HelpCorpus()

    controls = []

    def ck(name, got, want, note=""):
        controls.append({"control": name, "got": got, "want": want,
                         "pass": got == want, "note": note})

    # the resolution step must actually fire, and must not corrupt include-free pages
    d = parse_page("lop/distantlight.txt", helpdoc.resolve_includes(
        read_page(z, "lop/distantlight.txt"), corpus, "nodes/lop",
        self_key="nodes/lop/distantlight"))
    ck("C1 resolution fires (distantlight)", len(d.params), 87)
    c = parse_page("cop/chromakey.txt", helpdoc.resolve_includes(
        read_page(z, "cop/chromakey.txt"), corpus, "nodes/cop",
        self_key="nodes/cop/chromakey"))
    ck("C2 include-free page unchanged", len(c.params), 15)
    lv = live_parms("sop", "xform")
    ck("C3 runtime reachable", lv is not None, True)
    ck("C4 fabricated id does not match",
       "zzz_i0_not_real" in (lv["parms"] if lv else set()), False)

    rng = random.Random(SEED)
    picked = [(a, b) for a, b, _ in HAND_PICKED]
    sweep = []
    for ctx in ("cop", "cop2", "lop", "sop", "out", "top"):
        stems = [n.split("/", 1)[1][:-4] for n in page_names(z, ctx)]
        stems = [s for s in stems if not s.startswith("_") and s != "index"]
        rng.shuffle(stems)
        sweep += [(ctx, s) for s in stems[:POP_SAMPLE_PER_CTX]]

    results = {"hand_picked": [], "population_sweep": []}
    agg: dict = {}

    def run(pairs, bucket):
        for ctx, stem in pairs:
            name = f"{ctx}/{stem}.txt"
            try:
                raw = read_page(z, name)
            except KeyError:
                continue
            try:
                res = helpdoc.resolve_includes(raw, corpus, f"nodes/{ctx}",
                                               self_key=f"nodes/{ctx}/{stem}")
            except Exception:
                res = raw
            page = parse_page(name, res)
            lv = live_parms(ctx, stem)
            if lv is None:
                results[bucket].append({"node": f"{ctx}/{stem}", "status": "NOT_IN_RUNTIME"})
                continue
            sc = score(page.params, lv)
            results[bucket].append({
                "node": f"{ctx}/{stem}", "status": "OK",
                "documented_params_resolved": len(page.params),
                "live_parms": len(lv["parms"]),
                "hits": sc["hits"], "denom": sc["denom"],
            })
            a = agg.setdefault(bucket, {"hits": {}, "denom": {}, "all": 0})
            for k in sc["hits"]:
                a["hits"][k] = a["hits"].get(k, 0) + sc["hits"][k]
                a["denom"][k] = a["denom"].get(k, 0) + sc["denom"][k]
            a["all"] += len(page.params)

    run(picked, "hand_picked")
    run(sweep, "population_sweep")

    rates = {}
    for bucket, a in agg.items():
        rates[bucket] = {
            "documented_parameter_records": a["all"],
            "keys": {k: {"matched": a["hits"][k], "field_present_on": a["denom"][k],
                         "pct_of_present": round(100.0 * a["hits"][k] / a["denom"][k], 1)
                         if a["denom"][k] else None,
                         "pct_of_ALL_records": round(100.0 * a["hits"][k] / a["all"], 1)
                         if a["all"] else None}
                     for k in sorted(a["hits"])},
        }

    report = {"schema": "i0-q2b/v1", "build": BUILD,
              "runtime": hou.applicationVersionString(),
              "truth_tier": "VERIFIED-RUNTIME",
              "producer": "harness/notes/ingest/_i0_q2b_resolved.py",
              "difference_from_q2": "includes resolved before parsing",
              "seed": SEED, "controls": controls,
              "controls_passed": sum(1 for c in controls if c["pass"]),
              "controls_total": len(controls),
              "match_rates": rates, "per_node": results}
    out = os.path.join(HERE, "_i0_q2b_resolved.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"controls: {report['controls_passed']}/{report['controls_total']}")
    for c in controls:
        if not c["pass"]:
            print(f"   FAIL {c['control']}: {c['got']!r} != {c['want']!r}")
    for bucket in ("hand_picked", "population_sweep"):
        r = rates.get(bucket)
        if not r:
            continue
        print(f"\n=== {bucket} (INCLUDES RESOLVED) — "
              f"{r['documented_parameter_records']} documented parameter records ===")
        print(f"{'key':28s} {'present on':>11s} {'matched':>8s} {'of present':>11s} {'of ALL':>8s}")
        for k, v in r["keys"].items():
            print(f"{k:28s} {v['field_present_on']:11d} {v['matched']:8d} "
                  f"{str(v['pct_of_present'])+'%':>11s} {str(v['pct_of_ALL_records'])+'%':>8s}")
    print(f"\nwrote {out}")
    return 0


main()
