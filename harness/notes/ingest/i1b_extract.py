"""I1 — build the doc-derived grounding corpus for cop/, lop/ and cop2/.

Pure Python. No `hou`, no licence, no network. Reproducible on any machine with
Houdini 22.0.368 installed, which is the point: the corpus is DOCUMENTATION
grounding and must not silently depend on a running host.

Every record in the output is tiered **VERIFIED-DOC at 22.0.368** and carries
its source path inside nodes.zip. That tier is a per-ENTRY fact, never a
per-corpus one, and it is never summed with probe-derived grounding into a
single number — docs supply what a node is FOR, only a probe supplies what it
DOES. The probe axis is a SEPARATE artifact (`_i1b_runtime.json`) written by a
SEPARATE producer, and the two are joined by `_i1_merge.py` with each field
keeping its own tier. The separation is structural, not a reporting convention.

A stub is not knowledge. An entry that clears I0-FLOOR is ingested with
`known_thin: false`. One that does not is ingested with `known_thin: true`,
its rung, and the reason it fell short — recorded and COUNTED, never padded to
look complete and never dropped to flatter the coverage number.

Order of work, per the brief: the named Copernicus set first, then the rest of
cop/, then lop/, then cop2/. Recorded per entry as `ingest_order`.

REFUSES TO RUN unless `_i1_calibration.json` reports every control passing at
this reader's current source hash (R60).

Producer: this file -> harness/notes/ingest/_i1b_doc.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import i1b_reader as R  # noqa: E402

ORDER = ("cop", "lop", "cop2")


def require_calibration() -> dict:
    """R60. A reader trusted on 5,032 pages nobody read, without controls, is
    the failure this leg exists to prevent. This check FAILS if the calibration
    is missing, red, or was produced against different reader source."""
    path = HERE / "_i1b_calibration.json"
    if not path.exists():
        raise SystemExit("REFUSING: no _i1_calibration.json — run _i1_calibrate.py")
    cal = json.loads(path.read_text(encoding="utf-8"))
    if not cal.get("all_pass"):
        raise SystemExit("REFUSING: calibration is RED (%d failed)" % cal.get("failed"))
    live = hashlib.sha256((HERE / "i1b_reader.py").read_bytes()).hexdigest()
    if cal.get("reader_sha256") != live:
        raise SystemExit(
            "REFUSING: calibration was produced against a DIFFERENT reader\n"
            "  calibrated: %s\n  live      : %s\n"
            "  re-run _i1_calibrate.py" % (cal.get("reader_sha256"), live))
    return cal


def floor_reason(page: R.Page) -> str:
    if not page.summary:
        return 'no """summary""" on the page'
    if not page.described_params:
        return "no documented parameter carries a description"
    if not page.actionable_params:
        return "described parameters, but none carries an internal name (#id/#channels)"
    return ""


def build_entry(a: R.Archive, name: str, ctx: str, order: int,
                named_set: set[str]) -> dict:
    raw = a.raw(name)
    res, stats = a.resolved(name)
    raw_text, _ = a.raw_text(name)
    targets = a.include_targets_recursive(name)
    dep = R.doc_deprecation(raw, raw_text, targets)

    params = []
    for it in res.params:
        params.append({
            "label": it.label,
            "label_norm": R.norm_label(it.label),
            "id": it.ident,
            "channels": it.channels,
            "internal_names": it.internal_names,
            "type": it.ptype,
            "contentfrom": it.contentfrom,
            "heading": it.heading,
            "described": it.described,
            "description": it.desc,
        })

    rung = res.rung()
    clears = res.clears_floor
    return {
        # ---- provenance, per ENTRY -----------------------------------------
        "tier": "VERIFIED-DOC",
        "build": R.BUILD,
        "source": name,                       # path INSIDE nodes.zip
        "source_archive": "nodes.zip",
        "producer": "harness/notes/ingest/i1b_extract.py",
        "context": ctx,
        "category": R.CATEGORY[ctx],
        "stem": raw.stem,
        "type_candidates": a.type_candidates(raw),
        "ingest_order": order,
        "in_named_copernicus_set": raw.stem in named_set,

        # ---- content --------------------------------------------------------
        "title": raw.title,
        "summary": raw.summary,
        "parameters": params,

        # ---- the floor verdict ----------------------------------------------
        "floor": {
            "definition": 'summary AND >=1 documented parameter with a '
                          'non-empty description  (I0-FLOOR, adopted verbatim)',
            "rung": rung,
            "clears": clears,
            "known_thin": not clears,
            "reason": floor_reason(res),
            "rung_raw": raw.rung(),
            "clears_raw": raw.clears_floor,
            "rescued_by_include_resolution": clears and not raw.clears_floor,
        },

        # ---- counts ---------------------------------------------------------
        "counts": {
            "params_raw": len(raw.params),
            "params_resolved": len(res.params),
            "described_resolved": len(res.described_params),
            "actionable_resolved": len(res.actionable_params),
            "with_id": len([p for p in res.params if p.ident]),
            "with_channels": len([p for p in res.params if p.channels]),
            "with_contentfrom": len([p for p in res.params if p.contentfrom]),
        },

        # ---- transclusion ----------------------------------------------------
        "includes": {
            "statements_on_page": len(raw.includes),
            "verbs": sorted({v for _, _, _, v in raw.includes}),
            "seen": stats.get("seen", 0),
            "resolved": stats.get("resolved", 0),
            "unresolved_page": stats.get("unresolved", 0),
            "unresolved_anchor": stats.get("unresolved_anchor", 0),
            "unresolved_targets": sorted(stats.get("unresolved_targets", set())),
        },

        # ---- deprecation: the DOC side only. The runtime side and the union
        #      are added by _i1_merge.py from a probe, each keeping its tier.
        "deprecation_doc": dep,

        # ---- shape facts worth keeping (they are why the reader is shaped
        #      the way it is, and they let a future leg re-audit without
        #      re-parsing) ---------------------------------------------------
        "shape": {
            "eol": raw.eol,
            "had_bom": raw.had_bom,
            "header_order": raw.header_order,
        },
    }


def main() -> int:
    cal = require_calibration()
    a = R.Archive()

    named = set(json.loads(
        (HERE / "_i1b_the161.json").read_text(encoding="utf-8"))["named"])

    entries: list[dict] = []
    per_ctx: dict = {}
    order = 0

    for ctx in ORDER:
        pages = a.page_names(ctx)
        node_pages = [n for n in pages if a.is_node_page(n)]
        # The brief's order: the named Copernicus set FIRST, then the rest.
        if ctx == "cop":
            node_pages.sort(key=lambda n: (n[4:-4] not in named, n))
        for n in node_pages:
            order += 1
            entries.append(build_entry(a, n, ctx, order, named))
        clears = [e for e in entries if e["context"] == ctx and e["floor"]["clears"]]
        thin = [e for e in entries if e["context"] == ctx and not e["floor"]["clears"]]
        per_ctx[ctx] = {
            "category": R.CATEGORY[ctx],
            "pages_in_archive": len(pages),
            "node_pages_exists": len(node_pages),
            "clears_floor": len(clears),
            "known_thin": len(thin),
            "ingested": len(node_pages),
            "exists_minus_clears": len(node_pages) - len(clears),
            "rescued_by_include_resolution": len(
                [e for e in entries if e["context"] == ctx
                 and e["floor"]["rescued_by_include_resolution"]]),
            "rungs": {
                r: len([e for e in entries if e["context"] == ctx
                        and e["floor"]["rung"] == r])
                for r in ("EXISTS", "SUMMARY", "FLOOR", "ACTIONABLE")
            },
            "doc_deprecated_strong": len(
                [e for e in entries if e["context"] == ctx
                 and e["deprecation_doc"]["is_deprecated_doc"]]),
            "weak_mention_only": len(
                [e for e in entries if e["context"] == ctx
                 and e["deprecation_doc"]["weak_mention"]
                 and not e["deprecation_doc"]["is_deprecated_doc"]]),
        }
        print("  %-5s exists=%-5d clears=%-5d thin=%-4d rescued=%-3d dep_doc=%d"
              % (ctx, per_ctx[ctx]["node_pages_exists"], per_ctx[ctx]["clears_floor"],
                 per_ctx[ctx]["known_thin"],
                 per_ctx[ctx]["rescued_by_include_resolution"],
                 per_ctx[ctx]["doc_deprecated_strong"]))

    named_entries = [e for e in entries if e["in_named_copernicus_set"]]
    out = {
        "producer": "harness/notes/ingest/i1b_extract.py",
        "build": R.BUILD,
        "tier": "VERIFIED-DOC",
        "tier_note": "Documentation grounding ONLY. Never summed with "
                     "probe-derived grounding — see _i1b_runtime.json for the "
                     "probe axis, which is a separate artifact by design.",
        "floor": 'summary AND >=1 documented parameter with a non-empty '
                 'description (I0-FLOOR, adopted verbatim so the two legs are '
                 'comparable rather than merely similar)',
        "calibration": {
            "controls": cal["total"], "passed": cal["passed"],
            "reader_sha256": cal["reader_sha256"],
        },
        "per_context": per_ctx,
        "named_copernicus": {
            "named_total": len(named),
            "entries_built": len(named_entries),
            "clears_floor": len([e for e in named_entries if e["floor"]["clears"]]),
            "known_thin": len([e for e in named_entries if not e["floor"]["clears"]]),
            "known_thin_named": sorted(
                e["stem"] for e in named_entries if not e["floor"]["clears"]),
        },
        "entries": entries,
    }
    (HERE / "_i1b_doc.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("doc corpus: %d entries -> _i1_doc.json" % len(entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
