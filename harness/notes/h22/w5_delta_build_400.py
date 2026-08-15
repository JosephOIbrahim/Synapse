"""W5-DELTA -- build the .400 I1 source archive for the shipped contexts (cop/lop/cop2).

Reproduces i1_build.main()'s entries loop VERBATIM (same dedup `seen`, same the-161
ordering, same clears_floor gate) but fed the 22.0.400 DOC archive (via i1_extract's
parameterized helpdoc surface, load_corpus(build='22.0.400')) and the fresh 22.0.400
runtime catalogue (_w5_runtime_400.json). i1_build.main() itself hard-pins .368 (zero-arg
load_corpus + runtime==X.BUILD refuse + writes into ingest/); it is NOT invoked. Only its
pure functions (build_entry / thin_record / resolve_live_type / join_param) are reused, so
no new extraction machinery is introduced -- the mission's "no new machinery" constraint.

Output: harness/notes/h22/h22_node_corpus_400.i1.json -- shaped like the committed
orchestrator archive rag_promote_h22 reads (top-level build + source_archive + entries[]),
so `rag_promote_h22.promote(src)` consumes it unchanged.

Pure DOC + reuse of a pre-harvested runtime json: needs NO live hou (runs under plain python).
"""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
INGEST = REPO / "harness" / "notes" / "ingest"
sys.path.insert(0, str(INGEST))

import i1_extract as X   # noqa: E402  (DOC extractor, build-parameterized)
import i1_build as B     # noqa: E402  (build_entry / thin_record / resolve_live_type / join_param)

TARGET_BUILD = "22.0.400"
RUNTIME_JSON = HERE / "_w5_runtime_400.json"
OUT = HERE / "h22_node_corpus_400.i1.json"


def live_index_from(runtime: dict) -> dict:
    """The per-type live index, pre-normalised exactly as i1_build.main builds it."""
    live_index: dict = {}
    for cat, blob in runtime["categories"].items():
        idx = {}
        for tname, rec in blob["types"].items():
            labels_norm = {}
            for nm, lb in zip(rec["tuple_names"], rec["tuple_labels"]):
                nl = X.norm_label(lb)
                if nl:
                    labels_norm.setdefault(nl, nm)
            idx[tname] = {
                "label": rec["label"],
                "deprecated": rec["deprecated"],
                "deprecation_reason": rec["deprecation_reason"],
                "deprecation_version": rec["deprecation_version"],
                "tuple_names": set(rec["tuple_names"]),
                "parm_names": set(rec["parm_names"]),
                "tuple_labels_norm": set(labels_norm),
                "label_to_name": labels_norm,
            }
        live_index[cat] = idx
    return live_index


def main() -> int:
    runtime = json.loads(RUNTIME_JSON.read_text(encoding="utf-8"))
    if runtime["build"] != TARGET_BUILD:
        print("REFUSING: runtime artifact build %r != target %r"
              % (runtime["build"], TARGET_BUILD))
        return 2

    corpus = X.load_corpus(build=TARGET_BUILD)          # .400 DOC via parameterized helpdoc
    if corpus.build != TARGET_BUILD:
        print("REFUSING: loaded corpus build %r != target %r" % (corpus.build, TARGET_BUILD))
        return 2

    live_index = live_index_from(runtime)
    boms = X.bom_keys(help_dir=corpus.help_dir)
    the161 = X.new_copernicus_nodes(help_dir=corpus.help_dir)
    key161 = ["nodes/cop/%s" % n for n in the161]

    entries: list = []
    thin: list = []
    counts: dict = {}
    seen: set = set()

    for ctx in B.CONTEXT_ORDER:                          # ("cop", "lop", "cop2")
        cat = B.CATEGORY[ctx]
        live_types = live_index[cat]
        exists = X.all_pages(corpus, ctx)
        nodes = X.node_pages(corpus, ctx)
        order = [k for k in key161 if k in nodes] if ctx == "cop" else []
        order += [k for k in nodes if k not in order]

        c = {"exists": len(exists), "node_pages": len(nodes),
             "clears_floor": 0, "ingested": 0, "known_thin": 0,
             "live_type_matched": 0, "catalogue_total": runtime["categories"][cat]["count"]}

        for k in order:
            if k in seen:
                continue
            seen.add(k)
            page = X.parse_page(k, corpus)
            e = B.build_entry(k, page, corpus, live_types, ctx, boms, k in key161)
            # build_entry stamps X.BUILD (.368 module pin) into cosmetic per-entry build
            # labels; promote drops them, but stamp the truth so the src archive is honest.
            e["build"] = TARGET_BUILD
            e["deprecation"]["doc"]["build"] = TARGET_BUILD
            e["deprecation"]["runtime"]["build"] = TARGET_BUILD
            if e["live_type_matched"]:
                c["live_type_matched"] += 1
            if e["clears_floor"]:
                c["clears_floor"] += 1
                c["ingested"] += 1
                entries.append(e)
            else:
                c["known_thin"] += 1
                thin.append(B.thin_record(e))
        counts[ctx] = c

    out = {
        "schema": "h22_node_corpus/v1",
        "leg": "W5-DELTA (ING-DELTA; reuses i1_extract + i1_build.build_entry at .400)",
        "build": TARGET_BUILD,
        "producer": "harness/notes/h22/w5_delta_build_400.py "
                    "(DOC: i1_extract.load_corpus(build=22.0.400); runtime: "
                    "harness/notes/h22/_w5_runtime_400.json harvested under hython 22.0.400)",
        "source_archive": str(corpus.help_dir),
        "runtime_archive": str(RUNTIME_JSON),
        "truth_tier": "VERIFIED-DOC per entry at 22.0.400; runtime membership/label from "
                      "VERIFIED-RUNTIME 22.0.400 (fresh harvest, reused i1_runtime.harvest_category).",
        "counts": counts,
        "totals": {"ingested": len(entries), "known_thin": len(thin)},
        "entries": entries,
        "known_thin": thin,
    }
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")

    print("wrote %s (%.1f MB)" % (OUT, OUT.stat().st_size / 1e6))
    print("ctx    exists nodepg clears  thin  ltype-matched  cat")
    for ctx in B.CONTEXT_ORDER:
        c = counts[ctx]
        print("%-6s %6d %6d %6d %5d %13d %6d"
              % (ctx, c["exists"], c["node_pages"], c["clears_floor"],
                 c["known_thin"], c["live_type_matched"], c["catalogue_total"]))
    print("TOTAL ingested=%d known_thin=%d" % (len(entries), len(thin)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
