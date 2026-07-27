"""H9 Work 2+3 -- harvest the shipped help into a structured grounding corpus,
and gate it on quality.

Writes harness/notes/h22_doc_grounding_corpus.json (the leg's oracle artifact)
and harness/notes/h9/quality.json (the producer detail behind every integer).

THE QUALITY FLOOR, and why this one
-----------------------------------
"Has a page" is not "is grounded". The corpus reports a four-rung ladder so the
gap is visible rather than averaged away:

  HAS_PAGE     a help page maps to this live type at all.
  HAS_SUMMARY  + the page carries an authored ``\"\"\"...\"\"\"`` intent line.
  FLOOR        + at least one parameter with a NON-EMPTY description.
  ACTIONABLE   + at least one parameter carrying an internal id (#id/#channels).

FLOOR is the headline, and it is the floor the brief proposes: a summary answers
"what is this node for" and a described parameter answers "how do I drive it".
Those are the two questions D2 grounding exists to answer; either alone leaves a
caller guessing.

ACTIONABLE is reported beside it because SYNAPSE's #1 defect class is phantom
API and parameter names. A parameter documented only as a UI label ("Read Pixels
outside Image") cannot ground an emission -- nothing in the page says the parm
is called ``readoutside``. A corpus that reported FLOOR alone would count that
page as grounding for a task it cannot serve. The two numbers are different
questions and are never summed.

Each rung is falsifiable: a page with a summary and zero parameters lands on
HAS_SUMMARY and is excluded from FLOOR. The distribution below shows the rungs
are actually discriminating rather than all-pass.

TIER: every entry is VERIFIED-DOC. Documentation can be stale, silent or
internally broken, and each of those three is recorded per entry rather than
only in the receipt:
  silent_deprecation      runtime says deprecated, the page never says so (R72)
  version_ambiguous       one page credited to several live versions of the type
  doc_includes_broken     the page references include anchors that do not ship
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpdoc  # noqa: E402
import coverage as cov  # noqa: E402

H9 = Path(__file__).resolve().parent
NOTES = H9.parent
CORPUS_OUT = NOTES / "h22_doc_grounding_corpus.json"
QUALITY_OUT = H9 / "quality.json"
COVERAGE_IN = H9 / "coverage.json"

RUNGS = ("HAS_PAGE", "HAS_SUMMARY", "FLOOR", "ACTIONABLE")


def rung_for(page: dict) -> tuple[str, list[str]]:
    """Highest rung this page reaches, and why it stopped there."""
    why: list[str] = []
    described = [p for p in page["parameters"] if p["description"].strip()]
    with_id = [p for p in described if p["ids"]]
    if not page.get("summary"):
        why.append("no authored summary")
    if not described:
        why.append("no parameter carries a description")
    if not with_id:
        why.append("no parameter carries an internal id (#id/#channels)")
    if page.get("summary") and described and with_id:
        return "ACTIONABLE", why
    if page.get("summary") and described:
        return "FLOOR", why
    if page.get("summary"):
        return "HAS_SUMMARY", why
    return "HAS_PAGE", why


def build() -> tuple[dict, dict]:
    corpus = helpdoc.HelpCorpus()
    covdata = json.loads(COVERAGE_IN.read_text(encoding="utf-8"))

    # Parse each distinct page once; many live types share a page.
    page_cache: dict[str, dict] = {}
    include_health: dict[str, dict] = {}

    def get_page(key: str) -> dict:
        if key not in page_cache:
            st: dict = {}
            page_cache[key] = helpdoc.parse_page(key, corpus, st)
            include_health[key] = {
                "seen": st.get("seen", 0),
                "resolved": st.get("resolved", 0),
                "unresolved_page": st.get("unresolved", 0),
                "unresolved_anchor": st.get("unresolved_anchor", 0),
                "unresolved_targets": sorted(st.get("unresolved_targets", set()))[:40],
            }
        return page_cache[key]

    # How many live types each page is credited to -> version ambiguity.
    page_users: dict[str, list[str]] = {}
    for ctx in ("lop", "cop", "cop2"):
        for row in covdata["contexts"][ctx]["rows"]:
            if row["help_key"]:
                page_users.setdefault(row["help_key"], []).append(
                    "%s:%s" % (ctx, row["type"]))

    entries: list[dict] = []
    quality = {
        "schema": "h9_quality/v1",
        "truth_tier": "VERIFIED-DOC",
        "producer": "harness/notes/h9/harvest.py",
        "floor_definition": {
            "headline_rung": "FLOOR",
            "rungs": {
                "HAS_PAGE": "a help page maps to the live type",
                "HAS_SUMMARY": "+ authored \"\"\"intent\"\"\" line",
                "FLOOR": "+ >=1 parameter with a non-empty description",
                "ACTIONABLE": "+ >=1 parameter with an internal id (#id/#channels)",
            },
            "why": "FLOOR answers the two D2 questions (what is it for / how do I "
                   "drive it). ACTIONABLE is reported separately because a UI label "
                   "without an internal parm name cannot ground an emission, which "
                   "is SYNAPSE's #1 defect class.",
        },
        "contexts": {},
    }

    for ctx in ("lop", "cop", "cop2"):
        cdata = covdata["contexts"][ctx]
        rung_counts: Counter = Counter()
        naive_floor = 0
        for row in cdata["rows"]:
            key = row["help_key"]
            if key is None:
                rung_counts["ABSENT"] += 1
                continue
            page = get_page(key)
            rung, why = rung_for(page)
            rung_counts[rung] += 1

            described = [p for p in page["parameters"] if p["description"].strip()]
            with_id = [p for p in described if p["ids"]]
            ih = include_health[key]
            shared = sorted(page_users.get(key, []))
            # A colon-namespaced id is a USD attribute name, not a parm name --
            # VERIFIED-RUNTIME on 22.0.368: lop/rendergeometrysettings documents
            # 84 ids, 82 of them colon-namespaced, against 16 live parms.
            all_ids = {i for p in page["parameters"] for i in p["ids"]}
            usd_shaped = {i for i in all_ids if ":" in i}

            # Counterfactual: what the floor would report if :include statements
            # were not resolved. Quantifies the cost of the naive parse.
            if page.get("summary") and page.get("_unresolved_described"):
                naive_floor += 1

            entries.append({
                "type": row["type"],
                "context": ctx,
                "truth_tier": "VERIFIED-DOC",
                "truth_tier_note": "Read from the shipped reference of build %s. "
                                   "Documentation, not observation: it may be stale, "
                                   "silent or internally broken. Never sum with "
                                   "probe-derived (VERIFIED-RUNTIME) grounding."
                                   % helpdoc.BUILD,
                "match": row["verdict"],
                "help_key": key,
                "source": page["source"],
                "title": page["title"],
                "summary": page["summary"],
                "overview": page["overview"],
                "since": page["since"],
                "runtime_label": row["label"],
                "parameters": [
                    {"label": p["label"], "id": p["id"], "ids": p["ids"],
                     "description": p["description"]}
                    for p in page["parameters"]
                ],
                "inputs": page["inputs"],
                "outputs": page["outputs"],
                "counts": {
                    "parameters": len(page["parameters"]),
                    "described": len(described),
                    "with_internal_id": len(with_id),
                    "inputs": len(page["inputs"]),
                    "outputs": len(page["outputs"]),
                    "ids_total": len(all_ids),
                    "ids_usd_attribute_shaped": len(usd_shaped),
                },
                "id_semantics": {
                    "usd_attribute_shaped_ids": sorted(usd_shaped)[:20],
                    "warning": (
                        "%d of %d documented ids are colon-namespaced and are USD "
                        "ATTRIBUTE names, not Houdini parameter names. Emitting them "
                        "as parm names produces phantoms."
                        % (len(usd_shaped), len(all_ids))) if usd_shaped else None,
                },
                "quality": {
                    "rung": rung,
                    "clears_floor": rung in ("FLOOR", "ACTIONABLE"),
                    "actionable": rung == "ACTIONABLE",
                    "shortfalls": why,
                },
                "caveats": {
                    "silent_deprecation": bool(
                        row["deprecated_runtime"]
                        and not page["mentions_deprecated_resolved"]),
                    "runtime_deprecated": bool(row["deprecated_runtime"]),
                    "doc_mentions_deprecated": bool(page["mentions_deprecated_resolved"]),
                    "doc_mentions_deprecated_before_includes": bool(
                        page["mentions_deprecated"]),
                    "version_ambiguous": len(shared) > 1,
                    "page_shared_with": shared if len(shared) > 1 else [],
                    "matched_by_base_name_only": row["verdict"] == "BASE",
                    "documented_in_other_context": row["verdict"] == "ELSEWHERE",
                    "doc_includes_broken": (ih["unresolved_page"]
                                            + ih["unresolved_anchor"]) > 0,
                    "broken_include_targets": ih["unresolved_targets"],
                },
            })

        total = cdata["live_types"]
        floor_n = rung_counts["FLOOR"] + rung_counts["ACTIONABLE"]
        quality["contexts"][ctx] = {
            "live_types": total,
            "has_page": total - rung_counts["ABSENT"],
            "rungs": {r: rung_counts[r] for r in RUNGS},
            "absent": rung_counts["ABSENT"],
            "clears_floor": floor_n,
            "actionable": rung_counts["ACTIONABLE"],
            "has_page_pct": round(100.0 * (total - rung_counts["ABSENT"]) / total, 1),
            "clears_floor_pct": round(100.0 * floor_n / total, 1),
            "actionable_pct": round(100.0 * rung_counts["ACTIONABLE"] / total, 1),
            "gap_haspage_minus_floor": (total - rung_counts["ABSENT"]) - floor_n,
        }

    # Corpus-wide doc-health rollup over the pages actually used.
    used = sorted({e["help_key"] for e in entries})
    ih_tot = Counter()
    broken_pages = []
    for k in used:
        ih = include_health[k]
        ih_tot["seen"] += ih["seen"]
        ih_tot["resolved"] += ih["resolved"]
        ih_tot["unresolved_page"] += ih["unresolved_page"]
        ih_tot["unresolved_anchor"] += ih["unresolved_anchor"]
        if ih["unresolved_page"] or ih["unresolved_anchor"]:
            broken_pages.append(k)
    quality["include_health"] = {
        "pages_used": len(used),
        "include_statements": ih_tot["seen"],
        "resolved": ih_tot["resolved"],
        "unresolved_page_missing": ih_tot["unresolved_page"],
        "unresolved_anchor_missing": ih_tot["unresolved_anchor"],
        "pages_with_a_broken_include": len(broken_pages),
        "note": "Unresolved targets are defects in the SHIPPED documentation, not "
                "parse failures: e.g. lop/karmarenderproperties references "
                "karmastandardrendervars#hitstack and that anchor appears nowhere "
                "in lop/karmastandardrendervars.txt.",
        "examples": broken_pages[:15],
    }

    hz = [e for e in entries if e["counts"]["ids_usd_attribute_shaped"]]
    quality["id_semantics"] = {
        "entries_with_usd_attribute_shaped_ids": len(hz),
        "ids_total": sum(e["counts"]["ids_total"] for e in entries),
        "ids_usd_attribute_shaped": sum(
            e["counts"]["ids_usd_attribute_shaped"] for e in entries),
        "by_context": {
            ctx: sum(1 for e in hz if e["context"] == ctx)
            for ctx in ("lop", "cop", "cop2")},
        "worst": sorted(
            ({"type": e["type"], "context": e["context"],
              "usd_shaped": e["counts"]["ids_usd_attribute_shaped"],
              "ids_total": e["counts"]["ids_total"]} for e in hz),
            key=lambda x: -x["usd_shaped"])[:12],
        "note": "See corpus id_semantics_hazard. Colon-namespaced ids are USD "
                "attribute names; they are not parm names and must not be emitted "
                "as such.",
    }

    silent = [e for e in entries if e["caveats"]["silent_deprecation"]]
    quality["silent_deprecation"] = {
        "count": len(silent),
        "types": [e["type"] for e in silent][:60],
        "note": "R72 class: the runtime flags the type deprecated and the page -- "
                "after include resolution -- never says so. Doc-derived grounding "
                "inherits this silence.",
    }
    vamb = [e for e in entries if e["caveats"]["version_ambiguous"]]
    quality["version_ambiguous"] = {
        "count": len(vamb),
        "note": "One page credited to several live types (e.g. nodes/lop/domelight "
                "serves domelight, domelight::2.0 and domelight::3.0). Those types "
                "inherit documentation that may describe a different version.",
        "examples": sorted({tuple(e["caveats"]["page_shared_with"]) for e in vamb},
                           key=len, reverse=True)[:8],
    }

    corpus_doc = {
        "schema": "doc_grounding_corpus/v1",
        "truth_tier": "VERIFIED-DOC",
        "build": helpdoc.BUILD,
        "producer": "harness/notes/h9/harvest.py (parser: harness/notes/h9/helpdoc.py)",
        "source_archive": str(helpdoc.NODES_ZIP),
        "leg": "H9",
        "wiring_status": "NOT WIRED. This corpus is measured, not connected. It is "
                         "not referenced by the emission path or the RAG corpus. U.6 "
                         "found 15 phantom createNode sites already living in the RAG "
                         "corpus outside the emission gate; adding doc-derived entries "
                         "to that surface without a gate would repeat that at scale.",
        "tier_rule": "VERIFIED-DOC is a distinct tier from VERIFIED-RUNTIME. "
                     "Documentation supplies D2 (semantic) only. It cannot supply D3 "
                     "(behavioural). A doc-derived grounding figure must be reported "
                     "separately from a probe-derived one; summing them produces a "
                     "number that looks like coverage and is partly hearsay.",
        "denominator_note": "cop and cop2 are DIFFERENT live categories (384 and 169 "
                            "types). SYNAPSE's COP grounding figure uses the cop "
                            "category. Do not add cop2 into it.",
        "id_semantics_hazard": {
            "severity": "blocking for any emission use",
            "claim": "A documented #id: is NOT reliably a Houdini parameter name.",
            "tier": "VERIFIED-RUNTIME (22.0.368), producer "
                    "harness/notes/h9/diagnose_mismatch.py",
            "evidence": [
                "lop/rendergeometrysettings documents 84 ids, 82 of them "
                "colon-namespaced (karma:object:*); the live type has 16 parms.",
                "lop/rendersettings documents 199 ids, 177 absent from the live "
                "type, 175 of those colon-namespaced; the live type has 48 parms.",
                "lop/light::2.0 documents color/colorTemperature/exposure/angle; "
                "the live type carries 62 punycode parms such as "
                "xn__inputscolorTemperature_control_xpb. The doc names the USD "
                "attribute, Houdini encodes it into the parm name.",
            ],
            "consequence": "Feeding these ids to an emitter as parm names produces "
                           "exactly SYNAPSE's #1 defect class (phantom names). This "
                           "is the concrete reason the corpus ships unwired: the "
                           "gate a future wiring decision needs is an id->parm "
                           "resolution step, not a coverage number.",
            "per_entry_field": "counts.ids_usd_attribute_shaped and id_semantics",
        },
        "counts": {
            "entries": len(entries),
            "by_context": dict(Counter(e["context"] for e in entries)),
            "distinct_pages": len(used),
        },
        "entries": entries,
    }
    return corpus_doc, quality


if __name__ == "__main__":
    corpus_doc, quality = build()
    CORPUS_OUT.write_text(json.dumps(corpus_doc, indent=1), encoding="utf-8")
    QUALITY_OUT.write_text(json.dumps(quality, indent=1), encoding="utf-8")

    print("QUALITY LADDER -- 'has a page' vs 'is grounding'")
    for ctx, q in quality["contexts"].items():
        print("  %-5s live=%3d  has_page=%3d (%.1f%%)  FLOOR=%3d (%.1f%%)  "
              "ACTIONABLE=%3d (%.1f%%)  gap(page-floor)=%d"
              % (ctx, q["live_types"], q["has_page"], q["has_page_pct"],
                 q["clears_floor"], q["clears_floor_pct"],
                 q["actionable"], q["actionable_pct"],
                 q["gap_haspage_minus_floor"]))
        print("        rungs:", q["rungs"], " absent:", q["absent"])
    ih = quality["include_health"]
    print("\nDOC HEALTH: %d include statements over %d pages -- %d resolved, "
          "%d target a missing page, %d target a missing anchor (%d pages affected)"
          % (ih["include_statements"], ih["pages_used"], ih["resolved"],
             ih["unresolved_page_missing"], ih["unresolved_anchor_missing"],
             ih["pages_with_a_broken_include"]))
    print("SILENT DEPRECATION (R72 class): %d entries" % quality["silent_deprecation"]["count"])
    print("  ", quality["silent_deprecation"]["types"][:12])
    print("VERSION-AMBIGUOUS entries: %d" % quality["version_ambiguous"]["count"])
    print("\nwrote %s (%.1f MB)" % (CORPUS_OUT, CORPUS_OUT.stat().st_size / 1e6))
    print("wrote", QUALITY_OUT)
