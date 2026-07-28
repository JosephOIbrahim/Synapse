"""I0 / Q4 — the quality floor: how many pages CLEAR it vs merely EXIST?

THE FLOOR, and why this one
---------------------------
  I0-FLOOR = the page carries a \"\"\"summary\"\"\"
             AND >= 1 documented parameter with a non-empty description

Justification: those are the two questions an assistant must answer before it
can say anything useful about a node — *what is this for* (summary) and *how do
I drive it* (a described parameter). Either alone is not knowledge: a summary
with no parameters cannot ground an action, and parameters with no summary
cannot be retrieved by intent. It is also H9's FLOOR rung verbatim, so the two
legs' numbers are comparable rather than merely similar.

Reported alongside, never merged into it:
  EXISTS      a page maps to the context
  SUMMARY     + an authored summary line
  FLOOR       + >=1 described parameter          <- the headline
  ACTIONABLE  + >=1 parameter with an internal name (#id or #channels)
ACTIONABLE is separate because a UI label with no internal name cannot ground an
emission, which is SYNAPSE's #1 defect class.

MEASURED TWICE, and the gap is the finding
------------------------------------------
RAW      = the page as it ships
RESOLVED = with :include/:includeprop/:import expanded (H9's resolver)
lop/distantlight documents 0 parameters raw and 87 resolved — its whole
@parameters section is 14 :include lines. An extractor that does not resolve
includes reports a fully-documented node as ungrounded.

Run: python -c "exec(open('harness/notes/ingest/_i0_q4_floor.py',encoding='utf-8').read())"
"""

from __future__ import annotations

import json
import os
import re
import sys
import time

_HERE = os.path.abspath("harness/notes/ingest")
_H9 = os.path.abspath("harness/notes/h9")
for _p in (_HERE, _H9):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import helpdoc  # noqa: E402  (H9's committed corpus loader + include resolver)

from _i0_reader import (BUILD, open_archive, page_names, parse_page,  # noqa: E402
                        read_page)

CONTEXTS = ["cop", "lop", "sop", "out", "top", "cop2"]
UNRESOLVED = re.compile(r"UNRESOLVED-(?:INCLUDE|ANCHOR)|CYCLIC-INCLUDE")


def rung(p) -> str:
    described = [i for i in p.params if i.desc_lines > 0]
    internal = [i for i in p.params if i.ident or i.channels]
    if not p.summary and not p.params:
        return "EXISTS"
    if not p.summary:
        return "EXISTS"          # no summary => cannot clear the floor
    if not described:
        return "SUMMARY"
    if not internal:
        return "FLOOR"
    return "ACTIONABLE"


ORDER = ["EXISTS", "SUMMARY", "FLOOR", "ACTIONABLE"]


def clears(r: str) -> bool:
    return ORDER.index(r) >= ORDER.index("FLOOR")


def main() -> dict:
    t0 = time.time()
    z = open_archive()
    corpus = helpdoc.HelpCorpus()

    # ------------------------------------------------------------- controls
    controls = []

    def ck(name, got, want, note=""):
        controls.append({"control": name, "got": got, "want": want,
                         "pass": got == want, "note": note})

    d_raw = parse_page("lop/distantlight.txt", read_page(z, "lop/distantlight.txt"))
    d_res = parse_page("lop/distantlight.txt", helpdoc.resolve_includes(
        read_page(z, "lop/distantlight.txt"), corpus, "nodes/lop",
        self_key="nodes/lop/distantlight"))
    ck("C1 distantlight raw params", len(d_raw.params), 0,
       "its entire @parameters section is :include lines")
    ck("C1 distantlight resolved params", len(d_res.params), 87)
    # Hand-value corrected after the first run: distantlight DOES carry a summary,
    # so its raw rung is SUMMARY (summary present, zero DESCRIBED parameters).
    # The claim under test is unchanged and still holds — resolution moves the
    # page ACROSS the floor, which is what makes the floor resolution-dependent.
    ck("C1 resolution CHANGES the rung", (rung(d_raw), rung(d_res)),
       ("SUMMARY", "ACTIONABLE"), "the floor answer depends on resolution")
    ck("C1 raw is BELOW the floor, resolved is ABOVE",
       (clears(rung(d_raw)), clears(rung(d_res))), (False, True))

    c_raw = parse_page("cop/chromakey.txt", read_page(z, "cop/chromakey.txt"))
    c_res = parse_page("cop/chromakey.txt", helpdoc.resolve_includes(
        read_page(z, "cop/chromakey.txt"), corpus, "nodes/cop",
        self_key="nodes/cop/chromakey"))
    ck("C2 include-free page is UNCHANGED by resolution",
       (len(c_raw.params), len(c_res.params)), (15, 15),
       "resolution must not corrupt pages it does not apply to")

    # NEGATIVE: an unresolvable target must be MARKED, never silently dropped —
    # a dropped include is an undercount that looks like a clean parse.
    fake = "@parameters\n\n:include /nodes/cop/i0_no_such_page#nope:\n"
    ck("C3 bogus include is marked, not dropped",
       bool(UNRESOLVED.search(helpdoc.resolve_includes(
           fake, corpus, "nodes/cop", self_key="nodes/cop/i0_fake"))), True)

    # NEGATIVE: the floor must be able to FAIL. out/karma has no @parameters.
    k = parse_page("out/karma.txt", read_page(z, "out/karma.txt"))
    ck("C4 floor CAN fail", clears(rung(k)), False,
       "out/karma has a summary and zero parameters")

    # ------------------------------------------------------------- the sweep
    report_ctx: dict = {}
    per_page: dict = {}
    for ctx in CONTEXTS:
        names = page_names(z, ctx)
        rows = []
        for n in names:
            stem = n.split("/", 1)[1][:-4]
            raw = read_page(z, n)
            praw = parse_page(n, raw)
            stats: dict = {}
            try:
                res = helpdoc.resolve_includes(raw, corpus, f"nodes/{ctx}",
                                               stats=stats,
                                               self_key=f"nodes/{ctx}/{stem}")
            except Exception:
                res = raw
            pres = parse_page(n, res)
            rows.append({
                "page": n, "stem": stem,
                "rung_raw": rung(praw), "rung_resolved": rung(pres),
                "params_raw": len(praw.params), "params_resolved": len(pres.params),
                "includes": len(praw.includes),
                "unresolved": stats.get("unresolved_anchor", 0)
                              + stats.get("unresolved_include", 0),
                "is_node_page": praw.directives.get("type") == "node",
            })
        per_page[ctx] = rows
        n_all = len(rows)
        nodes = [r for r in rows if r["is_node_page"]]

        def tally(key):
            return {g: sum(1 for r in rows if r[key] == g) for g in ORDER}

        report_ctx[ctx] = {
            "pages_exist": n_all,
            "pages_typed_node": len(nodes),
            "raw": {
                "rungs": tally("rung_raw"),
                "clears_floor": sum(1 for r in rows if clears(r["rung_raw"])),
            },
            "resolved": {
                "rungs": tally("rung_resolved"),
                "clears_floor": sum(1 for r in rows if clears(r["rung_resolved"])),
            },
            "pages_rescued_by_resolution": sum(
                1 for r in rows if not clears(r["rung_raw"]) and clears(r["rung_resolved"])),
            "pages_with_unresolved_target": sum(1 for r in rows if r["unresolved"]),
        }

    # ------------------------------------- the 161, at the floor rather than the page
    the161 = json.load(open(os.path.join(_HERE, "_i0_q3_the161.json"), encoding="utf-8"))
    assert the161["new_cop_nodes_named"] == 161, the161["new_cop_nodes_named"]
    shipped161 = [r for r in per_page["cop"]
                  if r["stem"] in set(_shipped_names())]
    c161 = {
        "named": len(_shipped_names()),
        "have_a_page": len(shipped161),
        "clear_floor_raw": sum(1 for r in shipped161 if clears(r["rung_raw"])),
        "clear_floor_resolved": sum(1 for r in shipped161 if clears(r["rung_resolved"])),
        "actionable_resolved": sum(1 for r in shipped161
                                   if r["rung_resolved"] == "ACTIONABLE"),
        "below_floor_named": sorted(r["stem"] for r in shipped161
                                    if not clears(r["rung_resolved"])),
    }

    report = {
        "schema": "i0-q4/v1",
        "build": BUILD,
        "truth_tier": "VERIFIED-STATIC",
        "producer": "harness/notes/ingest/_i0_q4_floor.py",
        "resolver": "harness/notes/h9/helpdoc.py (HelpCorpus + resolve_includes)",
        "floor_definition": {
            "I0-FLOOR": 'summary AND >=1 parameter with a non-empty description',
            "rungs": ORDER,
            "note": "ACTIONABLE additionally requires an internal name (#id or #channels)",
        },
        "controls": controls,
        "controls_passed": sum(1 for c in controls if c["pass"]),
        "controls_total": len(controls),
        "contexts": report_ctx,
        "the_161_new_copernicus_nodes": c161,
        "elapsed_s": round(time.time() - t0, 1),
    }
    out = os.path.join(_HERE, "_i0_q4_floor.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    with open(os.path.join(_HERE, "_i0_q4_per_page.json"), "w", encoding="utf-8") as fh:
        json.dump(per_page, fh, indent=2)

    # ------------------------------------------------------------- printout
    print(f"controls: {report['controls_passed']}/{report['controls_total']}")
    for c in controls:
        if not c["pass"]:
            print(f"   FAIL {c['control']}: {c['got']!r} != {c['want']!r}")
    print(f"\n{'ctx':6s} {'EXISTS':>7s} {'clears RAW':>11s} {'clears RESOLVED':>16s} "
          f"{'rescued':>8s} {'unres':>6s}")
    print("-" * 62)
    for ctx in CONTEXTS:
        r = report_ctx[ctx]
        pct = 100.0 * r["resolved"]["clears_floor"] / r["pages_exist"]
        print(f"{ctx:6s} {r['pages_exist']:7d} "
              f"{r['raw']['clears_floor']:11d} {r['resolved']['clears_floor']:16d} "
              f"{r['pages_rescued_by_resolution']:8d} {r['pages_with_unresolved_target']:6d}"
              f"  node-typed={r['pages_typed_node']:5d}  clears={pct:5.1f}%")
    print("\nrung breakdown (RESOLVED):")
    for ctx in CONTEXTS:
        print(f"  {ctx:6s} {report_ctx[ctx]['resolved']['rungs']}")
    print(f"\nthe 161 new Copernicus nodes: {json.dumps(c161, indent=2)}")
    print(f"\nelapsed {report['elapsed_s']}s -> {out}")
    return report


def _shipped_names():
    import zipfile
    from _i0_reader import NEWS_ZIP
    t = zipfile.ZipFile(NEWS_ZIP).read("22/copernicus.txt").decode("utf-8-sig")
    return sorted(set(re.findall(r"Node:/cop/([a-z0-9_]+)", t)))


REPORT = main()
