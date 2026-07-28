"""I1 — join the doc axis and the probe axis into the deliverable corpus, and
cross-validate against the SECOND extractor that ran in this worktree.

Two things happen here and they are kept apart:

  MERGE   `_i1b_doc.json` (VERIFIED-DOC) + `_i1b_runtime.json` (VERIFIED-RUNTIME)
          -> `h22_node_corpus.json`. Every field keeps the tier of the producer
          that measured it. The deprecation UNION is computed here because it
          is the one fact that genuinely needs both sides — and it records
          WHICH side fired, because 'doc says / runtime does not' and 'runtime
          says / doc does not' mean different things to an artist and merging
          them into one boolean destroys exactly the information they need.

  CROSS-VALIDATE  a second I1 extractor (`i1_*.py`) ran in this worktree
          concurrently and left `h22_node_corpus.json` + `_i1_counts.json`.
          That is an Article V violation and is escalated in the receipt — but
          the artifact itself is a genuine SECOND INSTRUMENT, and I0 §7 is the
          precedent: two independent parsers disagreeing is information, and
          averaging it away destroys that information. Where they agree, the
          number is strong. Where they disagree, the disagreement is reported
          and adjudicated against the live runtime, never split the difference.

Producer: this file -> harness/notes/ingest/h22_node_corpus.json
                       harness/notes/ingest/_i1b_counts.json
                       harness/notes/ingest/_i1b_crossvalidate.json
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORACLE = HERE / "h22_node_corpus.json"
PRESERVED = HERE / "_i1a_h22_node_corpus.json"


def deprecation_union(doc: dict, rt: dict) -> dict:
    d = bool(doc.get("is_deprecated_doc"))
    r = bool(rt.get("deprecation_runtime", {}).get("is_deprecated"))
    if d and r:
        agreement = "both"
    elif d:
        agreement = "doc_only"          # vendor announced removal; build still ships it
    elif r:
        agreement = "runtime_only"      # THE DANGEROUS CELL — every human-facing
                                        # surface reads clean while the runtime flags it
    else:
        agreement = "neither"
    return {
        "is_deprecated": d or r,
        "agreement": agreement,
        "sources": [s for s, on in (("doc", d), ("runtime", r)) if on],
        "doc_signals": doc.get("strong", []),
        "runtime_reason": rt.get("deprecation_runtime", {}).get("reason", ""),
        "runtime_new_type": rt.get("deprecation_runtime", {}).get("new_type", ""),
        "doc_weak_mention_only": bool(doc.get("weak_mention")) and not d,
        "tier": "VERIFIED-DOC + VERIFIED-RUNTIME (union, sides recorded "
                "separately — never collapsed to one boolean)",
    }


def main() -> int:
    doc = json.loads((HERE / "_i1b_doc.json").read_text(encoding="utf-8"))
    rt = json.loads((HERE / "_i1b_runtime.json").read_text(encoding="utf-8"))
    the161 = json.loads((HERE / "_i1b_the161.json").read_text(encoding="utf-8"))
    cal = json.loads((HERE / "_i1b_calibration.json").read_text(encoding="utf-8"))
    per = rt["per_entry"]

    entries = []
    for e in doc["entries"]:
        r = per.get(e["source"], {})
        ent = dict(e)
        ent["runtime"] = {k: v for k, v in r.items()
                          if k not in ("per_parameter_label_resolved",
                                       "deprecation_runtime")}
        flags = r.get("per_parameter_label_resolved") or []
        for i, p in enumerate(ent["parameters"]):
            p["live_label_resolved"] = flags[i] if i < len(flags) else None
            p["live_label_resolved_tier"] = "VERIFIED-RUNTIME"
        ent["deprecation"] = deprecation_union(e["deprecation_doc"], r)
        entries.append(ent)

    # ---------------- counts, per context, against the LIVE catalogue --------
    counts = {}
    for ctx in ("cop", "lop", "cop2"):
        es = [e for e in entries if e["context"] == ctx]
        clears = [e for e in es if e["floor"]["clears"]]
        thin = [e for e in es if not e["floor"]["clears"]]
        matched = [e for e in es if e["runtime"].get("live_type_exists")]
        dp = sum(len(e["parameters"]) for e in es)
        dpr = sum(e["runtime"].get("label_resolved", 0) for e in es)
        counts[ctx] = {
            "catalogue_total_live": rt["catalogue_totals"][ctx],
            "exists": len(es),
            "clears_floor": len(clears),
            "ingested": len(es),
            "known_thin": len(thin),
            "exists_minus_clears": len(es) - len(clears),
            "clears_vs_catalogue_pct": round(
                100.0 * len(clears) / rt["catalogue_totals"][ctx], 1),
            "live_type_resolved": len(matched),
            "rescued_by_include_resolution": len(
                [e for e in es if e["floor"]["rescued_by_include_resolution"]]),
            "rungs": {k: len([e for e in es if e["floor"]["rung"] == k])
                      for k in ("EXISTS", "SUMMARY", "FLOOR", "ACTIONABLE")},
            "parameters_documented": dp,
            "parameters_label_resolved_live": dpr,
            "parameters_label_resolved_pct": round(100.0 * dpr / max(dp, 1), 1),
            "deprecation": {
                a: len([e for e in es if e["deprecation"]["agreement"] == a])
                for a in ("both", "doc_only", "runtime_only", "neither")},
        }

    named = set(the161["named"])
    ne = [e for e in entries if e["stem"] in named and e["context"] == "cop"]
    named_block = {
        "named_shipped_total": the161["named_total_shipped"],
        "governing_number_161_reproduced": the161["governing_number_reproduced"],
        "entries_built": len(ne),
        "have_a_page": len(ne),
        "ingested": len(ne),
        "clears_floor": len([e for e in ne if e["floor"]["clears"]]),
        "known_thin_need_a_runtime_probe": len(
            [e for e in ne if not e["floor"]["clears"]]),
        "known_thin_named": sorted(
            e["stem"] for e in ne if not e["floor"]["clears"]),
        "live_type_resolved": len(
            [e for e in ne if e["runtime"].get("live_type_exists")]),
        "invisible_to_the_governing_number": the161["shipped_only"],
        "named_in_new_sections": the161["named_in_new_sections"],
        "named_only_in_improvements": the161["named_improvements_only"],
    }

    # ---------------- cross-validation against the second extractor ----------
    # The other agent's FINAL build is `h22_node_corpus.i1-orchestrator.json`.
    # `_i1a_h22_node_corpus.json` is the copy this leg preserved off the oracle
    # path, and its own remediation ticket records that copy as its
    # SECOND-TO-LAST build. Cross-validating against the superseded one would
    # compare against work its author had already replaced, so the final build
    # is preferred and the fallback is kept only for the case where it is absent.
    FINAL_OTHER = HERE / "h22_node_corpus.i1-orchestrator.json"
    xval = {"available": False}
    if FINAL_OTHER.exists() or PRESERVED.exists() or ORACLE.exists():
        src = (FINAL_OTHER if FINAL_OTHER.exists()
               else PRESERVED if PRESERVED.exists() else ORACLE)
        try:
            other = json.loads(src.read_text(encoding="utf-8"))
            oentries = other.get("entries") or other.get("corpus") or []
            okey = {}
            for o in oentries:
                k = o.get("help_key") or o.get("source") or ""
                k = k.replace("nodes/", "")
                if k and not k.endswith(".txt"):
                    k += ".txt"
                okey[k] = o
            agree = disagree = only_mine = 0
            rows = []
            for e in entries:
                o = okey.get(e["source"])
                if o is None:
                    only_mine += 1
                    continue
                mine_c = e["floor"]["clears"]
                oc = o.get("clears_floor")
                if oc is None:
                    oc = (o.get("floor") or {}).get("clears")
                if oc is None:
                    oc = o.get("rung") in ("FLOOR", "ACTIONABLE")
                if bool(mine_c) == bool(oc):
                    agree += 1
                else:
                    disagree += 1
                    rows.append({
                        "source": e["source"], "mine_clears": mine_c,
                        "other_clears": bool(oc), "mine_rung": e["floor"]["rung"],
                        "other_rung": o.get("rung"),
                        "mine_params": len(e["parameters"]),
                        "live_label_resolved": e["runtime"].get("label_resolved"),
                    })
            xval = {
                "available": True,
                "other_corpus_file": src.name,
                "other_producer": other.get("producer", "unknown"),
                "other_entries": len(oentries),
                "mine_entries": len(entries),
                "compared": agree + disagree,
                "agree_on_floor": agree,
                "disagree_on_floor": disagree,
                "agreement_pct": round(100.0 * agree / max(agree + disagree, 1), 2),
                "in_mine_only": only_mine,
                "disagreements": rows[:40],
                "note": "Two independent extractors. Disagreements are reported "
                        "and adjudicated against the live runtime, never averaged.",
            }
        except Exception as ex:
            xval = {"available": False, "error": str(ex)}

    corpus = {
        "schema": "h22_node_corpus/v1",
        "leg": "I1",
        "harness": "INGEST-01",
        "build": "22.0.368",
        "generated_by": [
            "harness/notes/ingest/i1b_reader.py     (parser + include resolver)",
            "harness/notes/ingest/i1b_calibrate.py  (R60 gate, %d/%d controls)"
            % (cal["passed"], cal["total"]),
            "harness/notes/ingest/i1b_the161.py     (the named Copernicus set)",
            "harness/notes/ingest/i1b_extract.py    (VERIFIED-DOC axis)",
            "harness/notes/ingest/i1b_runtime.py   (VERIFIED-RUNTIME axis, hython)",
            "harness/notes/ingest/i1b_merge.py     (this file)",
        ],
        "tier_rule":
            "Provenance is per ENTRY and per FIELD, never per corpus. Doc fields "
            "are VERIFIED-DOC at 22.0.368; runtime fields are VERIFIED-RUNTIME. "
            "The two are NEVER summed into one grounding number — documentation "
            "supplies what a node is FOR, only a probe supplies what it DOES.",
        "floor_rule":
            "I0-FLOOR, adopted verbatim: a page clears the floor when it carries "
            'a """summary""" AND >= 1 documented parameter with a non-empty '
            "description. A stub is recorded known_thin and COUNTED, never "
            "padded to look complete and never dropped.",
        "join_key":
            "LABEL, normalised (collapse whitespace, casefold, U+2019 -> '). "
            "#id and #channels are recorded as EVIDENCE and are never the key "
            "(R97). Re-confirmed on this build: lop/rendersettings resolves 12% "
            "of its documented ids and 92% of its labels.",
        "wiring_status":
            "NOT WIRED. Nothing here is referenced by rag/, by the emission "
            "path, or by any product file. U.6 found 15 phantom createNode "
            "sites already living in the RAG corpus outside the emission gate; "
            "adding thousands of doc-derived entries to that surface without a "
            "gate is that mistake at scale. Wiring is a separate decision with "
            "its own oracle.",
        "calibration": {"controls": cal["total"], "passed": cal["passed"],
                        "by_class": cal["by_class"],
                        "reader_sha256": cal["reader_sha256"]},
        "catalogue_totals_live": rt["catalogue_totals"],
        "counts": counts,
        "named_copernicus": named_block,
        "crosscheck_20": rt["crosscheck_20"],
        "cross_validation": xval,
        "entries": entries,
    }

    if ORACLE.exists() and not PRESERVED.exists():
        shutil.copy2(ORACLE, PRESERVED)          # preserve, never destroy (Law 4)
    ORACLE.write_text(json.dumps(corpus, indent=1), encoding="utf-8")
    (HERE / "_i1b_counts.json").write_text(json.dumps(
        {k: corpus[k] for k in ("build", "catalogue_totals_live", "counts",
                                "named_copernicus", "calibration",
                                "cross_validation")}, indent=1), encoding="utf-8")
    (HERE / "_i1b_crossvalidate.json").write_text(
        json.dumps(xval, indent=1), encoding="utf-8")

    print("CORPUS  %d entries -> h22_node_corpus.json" % len(entries))
    print("  %-5s %-9s %-7s %-7s %-6s %-6s %s"
          % ("ctx", "catalogue", "exists", "clears", "thin", "live", "label%"))
    for ctx, c in counts.items():
        print("  %-5s %-9d %-7d %-7d %-6d %-6d %.1f%%"
              % (ctx, c["catalogue_total_live"], c["exists"], c["clears_floor"],
                 c["known_thin"], c["live_type_resolved"],
                 c["parameters_label_resolved_pct"]))
    n = named_block
    print("  named Copernicus: shipped=%d governing=%d ingested=%d clears=%d thin=%d"
          % (n["named_shipped_total"], n["governing_number_161_reproduced"],
             n["ingested"], n["clears_floor"], n["known_thin_need_a_runtime_probe"]))
    print("  thin named: %s" % ", ".join(n["known_thin_named"]))
    if xval.get("available"):
        print("  cross-validate vs 2nd extractor: %d compared, agree %d (%.2f%%), "
              "disagree %d" % (xval["compared"], xval["agree_on_floor"],
                               xval["agreement_pct"], xval["disagree_on_floor"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
