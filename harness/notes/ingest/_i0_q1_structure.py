"""I0 / Q1 — is the page format consistent across contexts, and where would one
parser break?

The brief asks for >=20 samples per context. This measures the FULL POPULATION
of every context instead; a census beats a sample and costs the same here (5,033
pages, ~4s). Sample size is therefore stated as n = the whole context.

Producer for: the Q1 table in harness/notes/ingest/I0_SCOUT.md
Reader:       _i0_reader.py, calibrated 41/41 by _i0_calibrate.py
Run: python -c "exec(open('harness/notes/ingest/_i0_q1_structure.py',encoding='utf-8').read())"
"""

from __future__ import annotations

import collections
import json
import os
import sys

_HERE = os.path.abspath("harness/notes/ingest")
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from _i0_reader import (BUILD, NODES_ZIP, open_archive, page_names,  # noqa: E402
                        parse_page, read_page)

FOCUS = ["cop", "lop", "sop", "out", "top"]      # the five the brief names
ALSO = ["cop2", "vop", "dop", "apex", "chop", "obj", "shop"]


def main() -> dict:
    z = open_archive()
    pages = {}
    for n in page_names(z):
        pages[n] = parse_page(n, read_page(z, n))

    by_ctx: dict = collections.defaultdict(list)
    for n, p in pages.items():
        by_ctx[p.context].append(p)

    report: dict = {
        "schema": "i0-q1/v1",
        "build": BUILD,
        "archive": NODES_ZIP,
        "total_pages": len(pages),
        "contexts": {},
    }

    for ctx, ps in sorted(by_ctx.items()):
        n = len(ps)
        hdr = collections.Counter(p.header_order for p in ps)
        eol = collections.Counter(p.eol for p in ps)
        directives = collections.Counter()
        for p in ps:
            directives.update(p.directives.keys())
        atsec = collections.Counter()
        for p in ps:
            atsec.update(s[1] for s in p.at_sections)
        # heading marker shape
        # (recorded via the raw text so '~~~' vs '==' is distinguishable)
        # base indent of top-level params
        base_ind = collections.Counter()
        for p in ps:
            if p.params:
                base_ind[min(i.indent for i in p.params)] += 1
        n_with_params = sum(1 for p in ps if p.params)
        n_params = sum(len(p.params) for p in ps)
        n_ids = sum(len(p.params_with_id) for p in ps)
        n_inc = sum(len(p.includes) for p in ps)
        n_with_inc = sum(1 for p in ps if p.includes)
        report["contexts"][ctx] = {
            "n_pages": n,
            "header_order": dict(hdr),
            "line_endings": dict(eol),
            "pages_with_params": n_with_params,
            "params_total": n_params,
            "params_with_id": n_ids,
            "id_rate_pct": round(100.0 * n_ids / n_params, 1) if n_params else None,
            "param_base_indent": dict(sorted(base_ind.items())),
            "pages_with_include": n_with_inc,
            "includes_total": n_inc,
            "at_sections_top": dict(atsec.most_common(10)),
            "page_directives_top": dict(directives.most_common(12)),
        }

    # ---------------------------------------------------------- break points
    # Each entry: a concrete assumption a single parser might make, and the
    # measured number of pages on which that assumption is FALSE.
    breaks = []

    def add(assumption, pred, why):
        hits = [n for n, p in pages.items() if pred(p)]
        per = collections.Counter(h.split("/")[0] for h in hits)
        breaks.append({
            "assumption": assumption,
            "pages_violating": len(hits),
            "pct_of_archive": round(100.0 * len(hits) / len(pages), 1),
            "by_context": dict(per.most_common(8)),
            "example": sorted(hits)[:3],
            "consequence": why,
        })

    add("page begins with its # directives, then '= Title ='",
        lambda p: p.header_order == "title-first",
        "a header block read only from the file head returns no #context/#internal")
    add("lines are LF-terminated",
        lambda p: p.eol in ("CRLF", "MIXED"),
        "a '$'-anchored item regex matches nothing: page reads as 0 parameters, silently")
    add("parameters are labels at column 0 under @parameters",
        lambda p: bool(p.params) and min(i.indent for i in p.params) > 0,
        "every parameter on the page is missed")
    add("a documented node has an @parameters section",
        lambda p: "parameters" not in [s[1] for s in p.at_sections],
        "pages documenting via @top_attributes/@properties/prose read as ungrounded")
    add("the page carries a '= Title =' line",
        lambda p: p.title is None,
        "no display name for the entry")
    add("the page carries a '#internal:' directive naming the node type",
        lambda p: "internal" not in p.directives,
        "no key to join the entry to a live node type; filename is the only fallback")
    add("the page carries a '\"\"\"summary\"\"\"'",
        lambda p: not p.summary,
        "no one-line description; a quality floor requiring one rejects the page")
    add("parameter text is inline (no ':include' indirection)",
        lambda p: any(sec in ("parameters", "<preamble>") for _, _, sec, _ in p.includes),
        "parameters/prose pulled from another file are absent from the entry")
    add("'#id:' is present on documented parameters",
        lambda p: bool(p.params) and not p.params_with_id,
        "an id-keyed corpus carries nothing for this page")

    report["single_parser_break_points"] = sorted(
        breaks, key=lambda b: -b["pages_violating"])

    out = os.path.join(_HERE, "_i0_q1_structure.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    # ------------------------------------------------------------- printout
    print(f"nodes.zip {BUILD} — {len(pages)} pages, {len(by_ctx)} contexts\n")
    hdr = f"{'ctx':7s} {'n':>5s} {'hdr-order':>26s} {'eol':>16s} {'w/parm':>7s} {'parms':>6s} {'id%':>6s} {'indent':>12s} {'inc':>5s}"
    print(hdr)
    print("-" * len(hdr))
    for ctx in FOCUS + [c for c in ALSO if c in report["contexts"]]:
        r = report["contexts"].get(ctx)
        if not r:
            continue
        ho = ",".join(f"{k.split('-')[0]}:{v}" for k, v in sorted(r["header_order"].items()))
        eo = ",".join(f"{k}:{v}" for k, v in sorted(r["line_endings"].items()))
        ind = ",".join(f"{k}:{v}" for k, v in list(r["param_base_indent"].items())[:4])
        print(f"{ctx:7s} {r['n_pages']:5d} {ho:>26s} {eo:>16s} "
              f"{r['pages_with_params']:7d} {r['params_total']:6d} "
              f"{str(r['id_rate_pct']):>6s} {ind:>12s} {r['pages_with_include']:5d}")

    print("\n=== where a single parser breaks (whole archive, n=5033) ===")
    for b in report["single_parser_break_points"]:
        print(f"\n  {b['pages_violating']:4d} pages ({b['pct_of_archive']:4.1f}%)  "
              f"ASSUMES: {b['assumption']}")
        print(f"        by ctx: {b['by_context']}")
        print(f"        -> {b['consequence']}")
        print(f"        e.g.  {b['example']}")
    print(f"\nwrote {out}")
    return report


REPORT = main()
