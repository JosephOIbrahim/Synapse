"""I1 -- build the grounding corpus.

    python harness/notes/ingest/i1_build.py

Joins two artifacts that are deliberately produced separately:

    VERIFIED-DOC       harness/notes/ingest/i1_extract.py  (the shipped archive)
    VERIFIED-RUNTIME   harness/notes/ingest/_i1_runtime.json (hython, live build)

and records WHICH SIDE said what, per entry. They are never summed into a single
grounding number: documentation says what a node is FOR, only a probe says what
it DOES, and an assistant that averages the two into one confident voice is less
useful than one that knows which of its own knowledge is current.

THREE THINGS THIS COSTS COVERAGE TO GET RIGHT
---------------------------------------------
1. **Provenance per ENTRY.** Every record carries its tier, its build, and the
   path inside the archive it came from. Never per corpus.
2. **A stub is not knowledge.** An entry clearing the floor is INGESTED. One
   that does not is recorded in ``known_thin`` with the reason it is thin, and
   COUNTED -- not padded with a title and an empty parameter list so the totals
   look better.
3. **Deprecation travels with the entry**, as a two-source union with the source
   recorded per side (R72). ``karmarenderproperties`` carries 56,325 characters
   of documentation that never mentions it is deprecated while the runtime flags
   it; a corpus without that axis teaches decaying nodes as current.

NOT WIRED. Nothing here imports ``synapse.*``, writes to ``rag/``, or touches
the emission path. U.6 found 15 phantom ``createNode`` sites already living in
the RAG corpus outside the emission gate, re-teaching phantoms through
``knowledge_lookup``. Adding thousands of doc-derived entries to that surface
without a gate is that mistake at scale. Wiring is a separate decision with its
own oracle.

PRODUCER: this file -> harness/notes/ingest/h22_node_corpus.json
                    -> harness/notes/ingest/_i1_counts.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import i1_extract as X  # noqa: E402

HERE = Path(__file__).resolve().parent
RUNTIME = HERE / "_i1_runtime.json"

# Output names are overridable so this producer can be re-run without clobbering
# a contested path. Added after a SECOND agent was found writing this same
# directory concurrently (Constitution Article V: every parallel agent gets its
# own worktree) -- regenerating deterministic output must never be the thing
# that destroys someone else's in-flight work.
_TAG = os.environ.get("I1_OUT_TAG", "")
CORPUS_OUT = HERE / ("h22_node_corpus%s.json" % _TAG)
COUNTS_OUT = HERE / ("_i1_counts%s.json" % _TAG)

# context -> live node type category
CATEGORY = {"cop": "Cop", "cop2": "Cop2", "lop": "Lop"}

# The order the brief sets: the 161 measured frontier gap first, then the rest of
# cop/, then lop/. cop2/ is last and is here because the leg must report against
# all three live catalogue totals -- and because 138 of the 144 doc-says /
# runtime-does-not deprecations live in it.
CONTEXT_ORDER = ("cop", "lop", "cop2")


def resolve_live_type(candidates: list, live_types: dict,
                      declared_version: str | None) -> tuple:
    """(matched type, how it matched, other live types the candidates hit).

    Candidates are TRIED, never assumed. The help system mangles ``::`` to
    ``--`` and ``::<version>`` to ``-<version>`` in filenames, and pages
    disagree about whether ``#internal:`` carries the version.

    **A DECLARED ``#version:`` WINS OVER THE FILENAME.** Measured on this
    build: 10 ``lop/`` pages match TWO live types, and taking the first
    candidate binds them to the OLDER one. ``lop/distantlight.txt`` declares
    ``#version: 2.0``; the live build registers both ``distantlight`` and
    ``distantlight::2.0``; filename-first hands 87 documented parameters to the
    legacy type and reports the CURRENT type -- the one an artist gets when they
    create the node -- as undocumented. Same for ``light`` (93 parameters),
    ``sceneimport`` (94), ``domelight`` (73). The page states which version it
    documents; believing it is not a heuristic.
    """
    present = [c for c in candidates if c in live_types]
    if declared_version:
        suffix = "::%s" % declared_version.strip()
        for c in present:
            if c.endswith(suffix):
                return c, "declared-version", [x for x in present if x != c]
    if present:
        return present[0], "candidate", present[1:]
    # Version-stripped fallback: a page may document a type that ships
    # unversioned on this build.
    for c in candidates:
        base = c.split("::")[0]
        if base in live_types:
            return base, "version-stripped", []
    return None, None, []


def join_param(param, live: dict) -> dict:
    """The precision pass I0-R2 asks for, as a PER-ENTRY fact.

    I0 measured that the two available parsers fail in opposite directions on
    ``lop/`` -- one at ~18x the recall and lower precision, the other precise and
    under-extracting a 402-parameter node down to 12 -- and that neither carries
    a precision pass. Recording, per parameter, whether its label resolves
    against the live build converts precision from an unknown into a fact, and
    makes the corpus self-auditing on the next build.

    Label first (it is the key: present on 100% of records, resolving 88.7-89.1%).
    ``#id`` is tried against TUPLE names before component names -- I0 measured
    that ordering as worth 2-8 points for free. Both are recorded as EVIDENCE;
    neither is the key.
    """
    out = {"live_label_match": False, "live_id_match": None, "live_channels_match": False}
    if not live:
        return out
    if param.label_norm and param.label_norm in live["tuple_labels_norm"]:
        out["live_label_match"] = True
        out["live_matched_name"] = live["label_to_name"].get(param.label_norm)
    for pid in param.ids:
        if pid in live["tuple_names"]:
            out["live_id_match"] = "tuple"
            break
        if pid in live["parm_names"]:
            out["live_id_match"] = "parm"
            break
    for ch in param.channels:
        if ch in live["parm_names"] or ch in live["tuple_names"]:
            out["live_channels_match"] = True
            break
    return out


def build_entry(help_key: str, page, corpus, live_types: dict, ctx: str,
                boms: set, is_161: bool) -> dict:
    raw = corpus.pages[help_key]
    dep_doc = X.doc_deprecation(raw, page.directives, page.raw_includes,
                                page.colon_directives)
    cands = X.type_candidates(help_key, page.directives)
    live_name, how, also = resolve_live_type(cands, live_types,
                                             page.directives.get("version"))
    live = live_types.get(live_name) if live_name else None

    params = []
    for pm in page.params:
        rec = pm.to_dict()
        rec.update(join_param(pm, live))
        params.append(rec)

    rt = live or {}
    dep_rt = {
        "deprecated": bool(rt.get("deprecated")),
        "reason": rt.get("deprecation_reason"),
        "version": rt.get("deprecation_version"),
        "tier": "VERIFIED-RUNTIME" if live else "UNVERIFIED",
        "build": X.BUILD,
        "applicable": bool(live),
    }
    direction = None
    if dep_doc["deprecated"] and not dep_rt["deprecated"]:
        direction = "doc-says-runtime-does-not"
    elif dep_rt["deprecated"] and not dep_doc["deprecated"]:
        direction = "runtime-says-doc-does-not"

    r = X.rung(page)
    described = sum(1 for p in page.params if p.description)
    internal = sum(1 for p in page.params if p.internal_names)
    matched = sum(1 for p in params if p["live_label_match"])

    return {
        # ---- provenance, per ENTRY, never per corpus (R119) ----------------
        "tier": "VERIFIED-DOC",
        "build": X.BUILD,
        "source": page.source,                 # e.g. nodes.zip!cop/chromakey.txt
        "help_key": help_key,
        # ---- identity ------------------------------------------------------
        "context": ctx,
        "stem": page.stem,
        "type_candidates": cands,
        "live_type": live_name,
        "live_type_match": how,
        "live_type_matched": live_name is not None,
        # Other live types this page's candidate set also hits -- recorded as
        # evidence, never counted as grounded. A predecessor version that ships
        # with no page of its own is a real gap and is reported as one.
        "live_type_also_matched": also,
        "runtime_label": rt.get("label"),
        # The live parameter count is what turns "thin" from a verdict into a
        # diagnosis: a node with ZERO live parameters cannot clear a floor that
        # requires a described parameter, however well documented it is.
        "live_parm_tuples": len(rt["tuple_names"]) if live else None,
        "new_in_22": is_161,
        # ---- knowledge -----------------------------------------------------
        "title": page.title,
        "summary": page.summary,
        "overview": page.overview,
        "since": page.directives.get("since"),
        "headings": page.headings,
        "related": page.related,
        "parameters": params,
        # ---- the floor -----------------------------------------------------
        "rung": r,
        "clears_floor": X.clears_floor(r),
        "known_thin": not X.clears_floor(r),
        "floor_facts": {
            "has_summary": bool(page.summary),
            "parameters": len(page.params),
            "with_description": described,
            "with_internal_name": internal,
        },
        # ---- deprecation, two sources, never merged (R72) -------------------
        "deprecation": {
            "doc": dep_doc,
            "runtime": dep_rt,
            "union": bool(dep_doc["deprecated"] or dep_rt["deprecated"]),
            "disagree": direction is not None,
            "direction": direction,
        },
        # ---- how the read went ---------------------------------------------
        "extraction": {
            "eol": page.eol,
            "bom": help_key in boms,
            "header_order": page.header_order,
            "includes": page.include_stats,
            "live_label_matched": matched,
            "live_label_match_rate": round(matched / len(params), 4) if params else None,
        },
    }


def thin_record(entry: dict) -> dict:
    """A thin page is RECORDED and COUNTED -- never padded to look complete.

    And it is CLASSIFIED, because the floor alone mislabels a whole class of
    page. Measured on this build: 11 of the 13 ``cop/`` pages that miss the
    floor document node types with ZERO live parameters. Their documentation is
    not thin -- it is complete for what the node is, and no floor requiring a
    described parameter can ever be cleared by a parameterless node. Reporting
    those in the same integer as ``lop/usdrender_rop`` -- which has 166 live
    parameter tuples and no summary -- would be the flattering number's mirror
    image: an unflattering one that is equally wrong.

    The classification is reported BESIDE the floor verdict, never merged into
    it. The floor stays exactly as I0 defined it so the two legs compare.
    """
    ff = entry["floor_facts"]
    if not ff["has_summary"] and ff["with_description"] == 0:
        why = "no summary and no described parameter"
    elif not ff["has_summary"]:
        why = "no authored summary (%d described parameters)" % ff["with_description"]
    else:
        why = "summary only -- 0 of %d parameters carry a description" % ff["parameters"]

    live_n = entry["live_parm_tuples"]
    if live_n is None:
        klass = "no-live-type"
        probe = "the page does not resolve to a live type on this build; a runtime " \
                "probe is what would settle whether the type exists under another name"
    elif live_n == 0:
        klass = "parameterless-node"
        probe = "PROBED: the live type carries 0 parameter tuples. The page is not a " \
                "stub -- there is nothing further to document. No probe outstanding."
    else:
        klass = "doc-gap"
        probe = "the live type carries %d parameter tuples that this page does not " \
                "ground; a runtime probe is the only source for them" % live_n
    return {
        "help_key": entry["help_key"],
        "context": entry["context"],
        "stem": entry["stem"],
        "source": entry["source"],
        "tier": "VERIFIED-DOC",
        "build": entry["build"],
        "rung": entry["rung"],
        "why_thin": why,
        "thin_class": klass,
        "live_parm_tuples": live_n,
        "probe_status": probe,
        "needs_runtime_probe": klass == "doc-gap",
        "floor_facts": ff,
        "live_type": entry["live_type"],
        "new_in_22": entry["new_in_22"],
    }


def main() -> int:
    if not RUNTIME.exists():
        print("REFUSING: %s absent. Run i1_runtime.py under hython first --\n"
              "  the corpus is not built without the live half." % RUNTIME)
        return 2
    runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
    if runtime["build"] != X.BUILD:
        print("REFUSING: runtime artifact is build %s, archive is %s"
              % (runtime["build"], X.BUILD))
        return 2

    # Pre-normalise the live label index once per type.
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

    corpus = X.load_corpus()
    boms = X.bom_keys()
    the161 = X.the_161()
    key161 = ["nodes/cop/%s" % n for n in the161]

    entries: list = []
    thin: list = []
    counts: dict = {}
    seen: set = set()

    for ctx in CONTEXT_ORDER:
        cat = CATEGORY[ctx]
        live_types = live_index[cat]
        exists = X.all_pages(corpus, ctx)
        nodes = X.node_pages(corpus, ctx)
        # The 161 first, then the rest of the context in sorted order.
        order = [k for k in key161 if k in nodes] if ctx == "cop" else []
        order += [k for k in nodes if k not in order]

        c = {"exists": len(exists), "node_pages": len(nodes), "clears_floor": 0,
             "ingested": 0, "known_thin": 0, "live_type_matched": 0,
             "doc_deprecated": 0, "runtime_deprecated": 0, "deprecation_union": 0,
             "disagree_doc_only": 0, "disagree_runtime_only": 0,
             "parameters": 0, "parameters_live_label_matched": 0,
             "catalogue_total": runtime["categories"][cat]["count"]}

        for k in order:
            if k in seen:
                continue
            seen.add(k)
            page = X.parse_page(k, corpus)
            e = build_entry(k, page, corpus, live_types, ctx, boms, k in key161)
            if e["live_type_matched"]:
                c["live_type_matched"] += 1
            d = e["deprecation"]
            c["doc_deprecated"] += int(d["doc"]["deprecated"])
            c["runtime_deprecated"] += int(d["runtime"]["deprecated"])
            c["deprecation_union"] += int(d["union"])
            if d["direction"] == "doc-says-runtime-does-not":
                c["disagree_doc_only"] += 1
            elif d["direction"] == "runtime-says-doc-does-not":
                c["disagree_runtime_only"] += 1
            if e["clears_floor"]:
                c["clears_floor"] += 1
                c["ingested"] += 1
                c["parameters"] += len(e["parameters"])
                c["parameters_live_label_matched"] += e["extraction"]["live_label_matched"]
                entries.append(e)
            else:
                c["known_thin"] += 1
                thin.append(thin_record(e))
        counts[ctx] = c

    # ---- coverage against the LIVE CATALOGUE, not against the page count ----
    #
    # "358 of 371 pages clear the floor" is a statement about the archive.
    # "358 of 384 live Copernicus types are grounded" is the statement about
    # SYNAPSE, and it is the one the leg exists to make. They differ, because a
    # live type can have no page at all -- and a page-based denominator hides
    # exactly those.
    catalogue: dict = {}
    for ctx in CONTEXT_ORDER:
        cat = CATEGORY[ctx]
        live_all = set(runtime["categories"][cat]["types"])
        ingested_types = {e["live_type"] for e in entries
                          if e["context"] == ctx and e["live_type"]}
        thin_types = {t["live_type"] for t in thin
                      if t["context"] == ctx and t["live_type"]} - ingested_types
        no_page = sorted(live_all - ingested_types - thin_types)
        dep_live = {t for t, r in runtime["categories"][cat]["types"].items()
                    if r["deprecated"]}
        catalogue[ctx] = {
            "category": cat,
            "catalogue_total": len(live_all),
            "types_grounded_to_floor": len(ingested_types),
            "types_grounded_pct": round(100.0 * len(ingested_types) / len(live_all), 1),
            "types_known_thin": len(thin_types),
            "types_with_no_page_at_all": len(no_page),
            "types_with_no_page_named": no_page[:40],
            "types_with_no_page_truncated": max(0, len(no_page) - 40),
            "runtime_deprecated_types": len(dep_live),
            "runtime_deprecated_with_no_page": sorted(dep_live & set(no_page)),
        }

    # ---- the 161, measured at the floor rather than at the page -------------
    by_key = {e["help_key"]: e for e in entries}
    thin_keys = {t["help_key"]: t for t in thin}
    ing161 = [k for k in key161 if k in by_key]
    thin161 = [k for k in key161 if k in thin_keys]
    absent161 = [k for k in key161 if k not in by_key and k not in thin_keys]
    the_161_block = {
        "named_in_shipped_whats_new": len(the161),
        "source": "news.zip!22/copernicus.txt (SHIPPED, version-pinned by "
                  "construction -- not the browsing help cache)",
        "have_a_page": len(the161) - len(absent161),
        "ingested": len(ing161),
        "known_thin": len(thin161),
        "no_page_at_all": len(absent161),
        "known_thin_named": [
            {"stem": k.rsplit("/", 1)[-1],
             "live_type": thin_keys[k]["live_type"],
             "thin_class": thin_keys[k]["thin_class"],
             "live_parm_tuples": thin_keys[k]["live_parm_tuples"],
             "needs_runtime_probe": thin_keys[k]["needs_runtime_probe"],
             "probe_status": thin_keys[k]["probe_status"]} for k in thin161],
        "still_need_a_runtime_probe": sum(
            1 for k in thin161 if thin_keys[k]["needs_runtime_probe"]),
        "no_page_named": [k.rsplit("/", 1)[-1] for k in absent161],
        "ingested_live_type_matched": sum(1 for k in ing161 if by_key[k]["live_type_matched"]),
    }

    out = {
        "schema": "h22_node_corpus/v1",
        "leg": "I1 (harness/SYNAPSE_INGEST.md)",
        "build": X.BUILD,
        "producer": "harness/notes/ingest/i1_build.py "
                    "(extractor: i1_extract.py, calibration: i1_calibrate.py, "
                    "runtime: i1_runtime.py under hython)",
        "source_archive": str(X.HELP_DIR),
        "gated_on": "I0 -- the join key is its finding, not this leg's assumption. "
                    "LABEL is the key (I0-F3, measured against the live runtime four "
                    "ways); #id and #channels are recorded as EVIDENCE and are never "
                    "the key.",
        "truth_tier": "VERIFIED-DOC per entry, at this build. Every record carries "
                      "its own tier, build and archive path.",
        "tier_rule": "VERIFIED-DOC and VERIFIED-RUNTIME are DIFFERENT tiers and are "
                     "never summed into one grounding number. Documentation supplies "
                     "what a node is FOR; only a probe supplies what it DOES. The "
                     "runtime fields in each entry are labelled VERIFIED-RUNTIME and "
                     "are reported beside the doc fields, never merged into them.",
        "wiring_status": "NOT WIRED. Nothing here is referenced by the RAG corpus or "
                         "the emission path, and no product file was touched. U.6 "
                         "found 15 phantom createNode sites already living in the RAG "
                         "corpus outside the emission gate; adding thousands of "
                         "doc-derived entries to that surface without a gate is that "
                         "mistake at scale. Wiring is a separate decision with its "
                         "own oracle.",
        "floor": "I0-FLOOR, taken verbatim so the two legs' numbers are comparable: "
                 "the page carries a \"\"\"summary\"\"\" AND >= 1 documented parameter "
                 "with a non-empty description. Rungs are cumulative: "
                 "EXISTS < SUMMARY < FLOOR < ACTIONABLE.",
        "stub_rule": "An entry clearing the floor is INGESTED. One that does not is "
                     "recorded in known_thin with the reason, and counted -- not "
                     "padded to look complete.",
        "counts": counts,
        "catalogue_coverage": catalogue,
        "denominator_rule": "clears-floor is reported against BOTH denominators and "
                            "they are labelled: counts.* is per help PAGE (the "
                            "archive's view), catalogue_coverage.* is per LIVE TYPE "
                            "(SYNAPSE's view). Only the second one can see a type "
                            "that ships with no documentation at all.",
        "the_161": the_161_block,
        "totals": {
            "ingested": len(entries),
            "known_thin": len(thin),
            "parameters": sum(len(e["parameters"]) for e in entries),
            "parameters_live_label_matched": sum(
                e["extraction"]["live_label_matched"] for e in entries),
        },
        "entries": entries,
        "known_thin": thin,
    }
    CORPUS_OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")

    thin_by_class: dict = {}
    for t in thin:
        thin_by_class.setdefault(t["context"], {}).setdefault(t["thin_class"], 0)
        thin_by_class[t["context"]][t["thin_class"]] += 1
    out["known_thin_by_class"] = thin_by_class
    out["known_thin_rule"] = (
        "thin_class is reported BESIDE the floor verdict and never merged into "
        "it. parameterless-node = the live type carries 0 parameter tuples, so "
        "no floor requiring a described parameter can ever be cleared and the "
        "documentation is complete for what the node is. doc-gap = the live type "
        "carries parameters this page does not ground -- the real gap.")

    slim = {k: v for k, v in out.items() if k not in ("entries", "known_thin")}
    slim["known_thin_index"] = [
        {"help_key": t["help_key"], "rung": t["rung"], "why_thin": t["why_thin"],
         "thin_class": t["thin_class"], "live_parm_tuples": t["live_parm_tuples"],
         "needs_runtime_probe": t["needs_runtime_probe"]} for t in thin]
    COUNTS_OUT.write_text(json.dumps(slim, indent=1), encoding="utf-8")

    print("wrote %s (%.1f MB)" % (CORPUS_OUT, CORPUS_OUT.stat().st_size / 1e6))
    print()
    print("PER PAGE (the archive's view)")
    print("ctx    exists  nodepg  clears  thin   ingested")
    for ctx in CONTEXT_ORDER:
        c = counts[ctx]
        print("%-6s %6d  %6d  %6d  %4d   %6d"
              % (ctx, c["exists"], c["node_pages"], c["clears_floor"],
                 c["known_thin"], c["ingested"]))
    print()
    print("PER LIVE TYPE (SYNAPSE's view -- the number the leg is for)")
    print("ctx    catalogue  grounded   pct   thin  no-page")
    for ctx in CONTEXT_ORDER:
        v = catalogue[ctx]
        print("%-6s %9d  %8d  %4.1f%%  %5d  %7d"
              % (ctx, v["catalogue_total"], v["types_grounded_to_floor"],
                 v["types_grounded_pct"], v["types_known_thin"],
                 v["types_with_no_page_at_all"]))
    print()
    print("the 161: ingested %d | known-thin %d (of which %d still need a probe) | no page %d"
          % (the_161_block["ingested"], the_161_block["known_thin"],
             the_161_block["still_need_a_runtime_probe"],
             the_161_block["no_page_at_all"]))
    print("known-thin by class: %s" % json.dumps(thin_by_class))
    print("parameters %d, live-label-matched %d (%.1f%%)"
          % (out["totals"]["parameters"], out["totals"]["parameters_live_label_matched"],
             100.0 * out["totals"]["parameters_live_label_matched"]
             / max(1, out["totals"]["parameters"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
