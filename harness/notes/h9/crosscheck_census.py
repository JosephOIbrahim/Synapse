"""H9 producer 6 -- doc-vs-runtime agreement as a CENSUS, not a sample.

Emits harness/notes/h9/crosscheck_census.json

WHY THIS REPLACES THE HEADLINE (audit findings H9-CC-1, CC-2, CC-3)
    The brief asked for 10 LOP and 10 COP at random. That sample was drawn, and it was
    a bad estimator of the thing it was being read as:

        Cop   seed 9 scored 48/48 = 100.0%.  Over 500 seeds NO seed scored higher.
                                             Population: 95.1%.
        Lop   seed 9 scored 174/184 = 94.6%. ~85th percentile of 500 draws; across 41
                                             consecutive seeds the figure ranges
                                             56.2% to 96.1%. Population: 81.7%.

    A 20-node draw was never necessary. Every ingredient was already on disk: the
    corpus holds the documented ids for all 691 paged types, and the two runtime
    artifacts hold the template and instantiated parameters for all 771 live types. So
    the population can simply be COUNTED, and a count has no sampling error to defend.

    The sample is retained below as an illustration, reported as one draw with its seed
    sensitivity beside it -- never as a bare percentage.

WHAT AGREEMENT MEANS HERE
    Over DOCUMENTED PARAMETER IDS ONLY. A documented id agrees when a parameter of that
    name exists on the live node in EITHER ground truth (template or instantiated) or as
    a multiparm token. It says nothing about parameters the reference never mentions;
    that is the undocumented column, and it is much larger.

TIER
    VERIFIED-DERIVED, from two VERIFIED-RUNTIME inputs (runtime_parms + instantiated_parms,
    both probed on 22.0.368 this session). No new probe; nothing inferred.

FAILURE CONDITION (Law 1)
    Fails a documented id absent from both ground truths. It reports non-zero
    disagreements on this build, which is the evidence it can fail. If the census and
    the corpus's own per-entry disagreement lists ever diverge, the run raises --
    they are computed from the same rule and must agree.

RUN
    python harness/notes/h9/crosscheck_census.py
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "..", "h22_doc_grounding_corpus.json")
RUNTIME = os.path.join(HERE, "runtime_parms_22.0.368.json")
INSTANTIATED = os.path.join(HERE, "instantiated_parms_22.0.368.json")
OUT = os.path.join(HERE, "crosscheck_census.json")

SEED = 9
N_SAMPLE = 10


def id_exists(pid, template, instantiated):
    return pid in template or pid in instantiated or (pid + "#") in template


def score(entry, template, instantiated):
    documented = sorted({i for p in entry["parameters"] for i in p["documented_ids"]})
    agree = [p for p in documented if id_exists(p, template, instantiated)]
    disagree = [p for p in documented if not id_exists(p, template, instantiated)]
    documented_live = {n for p in entry["parameters"] for n in p["resolved_runtime_parms"]}
    return {
        "type_name": entry["type_name"],
        "ids": len(documented),
        "agree": len(agree),
        "disagree": disagree,
        "live_parms": len(template),
        "undocumented": len(template - documented_live),
    }


def main():
    with open(CORPUS, encoding="utf-8") as fh:
        corpus = json.load(fh)
    with open(RUNTIME, encoding="utf-8") as fh:
        rt = json.load(fh)
    with open(INSTANTIATED, encoding="utf-8") as fh:
        inst = json.load(fh)

    out = {
        "schema": "h9_crosscheck_census/v1",
        "producer": "harness/notes/h9/crosscheck_census.py",
        "build": rt["build"],
        "tier": "VERIFIED-DERIVED",
        "tier_basis": [
            "harness/notes/h9/runtime_parms_22.0.368.json (VERIFIED-RUNTIME)",
            "harness/notes/h9/instantiated_parms_22.0.368.json (VERIFIED-RUNTIME)",
        ],
        "agreement_is_over": "documented parameter ids only -- NOT over the parameters "
        "the reference never mentions",
        "census": {},
        "the_sample_the_brief_asked_for": {},
    }

    rows_by_cat, consistency = {}, []
    for cat in ("Lop", "Cop", "Cop2"):
        entries = [e for e in corpus["entries"] if e["category"] == cat and e["has_page"]]
        rows = []
        for e in entries:
            template = set(rt["categories"][cat]["types"].get(e["type_name"], {}).get("parms", []))
            i_rec = inst["categories"][cat]["types"].get(e["type_name"], {})
            instantiated = set(i_rec.get("parms", [])) | set(i_rec.get("parm_tuples", []))
            row = score(e, template, instantiated)
            rows.append(row)
            # the corpus computes the same set independently; they must agree
            if sorted(row["disagree"]) != sorted(
                e["runtime_disagreement"]["documented_parms_absent_from_node"]
            ):
                consistency.append(e["type_name"])
        rows_by_cat[cat] = rows

        ids = sum(r["ids"] for r in rows)
        agree = sum(r["agree"] for r in rows)
        informative = [r for r in rows if r["ids"] > 0]
        out["census"][cat] = {
            "types_with_a_page": len(rows),
            "types_with_at_least_one_documented_id": len(informative),
            "documented_ids_checked": ids,
            "agree": agree,
            "disagree": ids - agree,
            "agreement_pct": round(100.0 * agree / ids, 1) if ids else None,
            "types_with_zero_disagreements": sum(1 for r in informative if not r["disagree"]),
            "types_with_at_least_one_disagreement": sum(1 for r in informative if r["disagree"]),
            "live_parms_total": sum(r["live_parms"] for r in rows),
            "live_parms_undocumented": sum(r["undocumented"] for r in rows),
            "worst_offenders": sorted(
                ({"type": r["type_name"], "disagree": r["disagree"][:8], "n": len(r["disagree"])}
                 for r in rows if r["disagree"]),
                key=lambda d: -d["n"],
            )[:12],
        }

    if consistency:
        raise SystemExit(
            "FAIL: census and corpus disagree on %d types, e.g. %s"
            % (len(consistency), consistency[:5])
        )

    # ---- the 10+10 sample, kept as an illustration with its own sensitivity
    for cat, n in (("Lop", N_SAMPLE), ("Cop", N_SAMPLE), ("Cop2", 5)):
        rows = rows_by_cat[cat]
        pool = sorted(rows, key=lambda r: r["type_name"])
        rng = random.Random(SEED)
        picked = rng.sample(pool, min(n, len(pool)))
        ids = sum(r["ids"] for r in picked)
        agree = sum(r["agree"] for r in picked)

        spread = []
        for s in range(200):
            r2 = random.Random(s).sample(pool, min(n, len(pool)))
            i2 = sum(r["ids"] for r in r2)
            a2 = sum(r["agree"] for r in r2)
            if i2:
                spread.append(100.0 * a2 / i2)
        spread.sort()
        out["the_sample_the_brief_asked_for"][cat] = {
            "nodes": len(picked),
            "seed": SEED,
            "documented_ids_checked": ids,
            "agreement_pct_this_draw": round(100.0 * agree / ids, 1) if ids else None,
            "informative_nodes": sum(1 for r in picked if r["ids"] > 0),
            "vacuous_nodes": sum(1 for r in picked if r["ids"] == 0),
            "population_agreement_pct": out["census"][cat]["agreement_pct"],
            "seed_sensitivity_200_draws": {
                "min": round(spread[0], 1) if spread else None,
                "p05": round(spread[len(spread) // 20], 1) if spread else None,
                "median": round(spread[len(spread) // 2], 1) if spread else None,
                "max": round(spread[-1], 1) if spread else None,
                "draws_that_were_vacuous": (min(n, len(pool)) and 200 - len(spread)),
            },
            "how_to_read_it": "one draw. The population figure beside it is the number "
            "to quote; this row exists because the brief asked for a 10-node sample and "
            "because its spread is itself the evidence that a sample was the wrong "
            "instrument here.",
        }

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("WROTE", OUT)
    for cat in ("Lop", "Cop", "Cop2"):
        c = out["census"][cat]
        s = out["the_sample_the_brief_asked_for"][cat]
        print(
            "  %-5s CENSUS %5d ids, %5d agree = %5s%%  | undocumented live parms %5d"
            % (cat, c["documented_ids_checked"], c["agree"], c["agreement_pct"],
               c["live_parms_undocumented"])
        )
        print(
            "        sample(seed %d) %s%% over %d ids | 200-seed spread %s..%s"
            % (SEED, s["agreement_pct_this_draw"], s["documented_ids_checked"],
               s["seed_sensitivity_200_draws"]["min"], s["seed_sensitivity_200_draws"]["max"])
        )


main()
