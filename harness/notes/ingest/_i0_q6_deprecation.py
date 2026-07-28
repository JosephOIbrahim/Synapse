"""I0 / Q6 — the deprecation axis: how far do the doc and the runtime disagree?

R72/R86/R87: deprecation is the UNION of runtime `deprecationInfo()` and authored
help, and the two DISAGREE. This measures the disagreement in BOTH directions
over every node-typed page in six contexts that resolves to a live type.

Doc-side signal is TIERED on purpose, because H7-F12 caught the trap: lop/
reference.txt says "($IIDX is deprecated)" — prose about an EXPRESSION VARIABLE,
not about the node. Counting that as a node deprecation flags a node SYNAPSE
emits 78 times.

  STRONG  '#status: deprecated'                       (page-level directive)
          ':include /composite/_old_cops_deprecated:' (the H7-F4 banner)
          ':warning:Deprecated'                       (warning block)
  WEAK    the word 'deprecat'/'obsolete' anywhere in the prose

Only STRONG is treated as "the page states a deprecation". WEAK is reported
beside it, never merged into it.

Run: hython harness/notes/ingest/_i0_q6_deprecation.py
"""

from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_H9 = os.path.join(os.path.dirname(HERE), "h9")
for _p in (HERE, _H9):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hou  # noqa: E402

import helpdoc  # noqa: E402

from _i0_reader import (BUILD, open_archive, page_names, parse_page,  # noqa: E402
                        read_page)

CONTEXTS = ["cop", "lop", "sop", "out", "top", "cop2"]
CATEGORY = {"cop": "Cop", "cop2": "Cop2", "lop": "Lop",
            "sop": "Sop", "out": "Driver", "top": "Top"}

RE_STATUS_DEPR = re.compile(r"^#status:\s*deprecated\s*$", re.M | re.I)
RE_BANNER = re.compile(r"^\s*:include\s+/composite/_old_cops_deprecated:\s*$", re.M)
RE_WARN_DEPR = re.compile(r"^\s*:warning:\s*Deprecated", re.M | re.I)
RE_WEAK = re.compile(r"deprecat|obsolete", re.I)


def doc_signal(raw: str) -> dict:
    strong = []
    if RE_STATUS_DEPR.search(raw):
        strong.append("status_header")
    if RE_BANNER.search(raw):
        strong.append("include_banner")
    if RE_WARN_DEPR.search(raw):
        strong.append("warning_block")
    return {"strong": strong, "weak": bool(RE_WEAK.search(raw))}


def stem_to_typenames(stem: str) -> list:
    out = [stem]
    if "--" in stem:
        out.append(stem.replace("--", "::"))
    base, sep, tail = stem.rpartition("-")
    if sep and tail and tail[0].isdigit():
        out.append(f"{base}::{tail}")
        if "--" in base:
            out.append(f"{base.replace('--', '::')}::{tail}")
    return list(dict.fromkeys(out))


def runtime_depr(ctx: str, stem: str):
    """(found_in_runtime, is_deprecated, info). No instantiation needed —
    nodeType() + deprecationInfo() is enough and avoids licence surprises."""
    cat = hou.nodeTypeCategories().get(CATEGORY.get(ctx, ""))
    if cat is None:
        return False, None, None
    for cand in stem_to_typenames(stem):
        nt = hou.nodeType(cat, cand)
        if nt is not None:
            try:
                info = nt.deprecationInfo() or {}
            except Exception:
                info = {}
            return True, bool(info), {k: str(v) for k, v in info.items()}
    return False, None, None


def main() -> int:
    z = open_archive()
    controls = []

    def ck(name, got, want, note=""):
        controls.append({"control": name, "got": got, "want": want,
                         "pass": got == want, "note": note})

    # ---- POSITIVE: the H7-F4 banner must fire on a cop2 page
    blur = read_page(z, "cop2/blur.txt")
    ck("C1 banner fires on cop2/blur", doc_signal(blur)["strong"], ["include_banner"])
    # ---- POSITIVE: R72/H7-F2 — lop/karma is runtime-deprecated and doc-SILENT
    found, dep, info = runtime_depr("lop", "karma")
    ck("C2 lop/karma in runtime", found, True)
    ck("C2 lop/karma runtime-deprecated", dep, True,
       "R72/H7-F2: the doc never says so")
    ck("C2 lop/karma doc STRONG-silent",
       doc_signal(read_page(z, "lop/karma.txt"))["strong"], [])
    # ---- NEGATIVE: a current node must read clean on BOTH axes
    ck("C3 cop/chromakey doc-clean",
       doc_signal(read_page(z, "cop/chromakey.txt"))["strong"], [])
    ck("C3 cop/chromakey runtime-clean", runtime_depr("cop", "chromakey")[1], False)
    # ---- NEGATIVE: the H7-F12 false-positive trap must NOT reach STRONG
    ref = read_page(z, "lop/reference.txt")
    ck("C4 lop/reference is WEAK-only, not STRONG",
       (doc_signal(ref)["strong"], doc_signal(ref)["weak"]), ([], True),
       "H7-F12: '($IIDX is deprecated)' is about a variable, not the node")
    # ---- the detectors must be ABLE to fire (Law 1)
    ck("C5 status_header detector fires",
       doc_signal("#status: deprecated\n")["strong"], ["status_header"])
    ck("C5 warning detector fires",
       doc_signal(":warning:Deprecated:\n")["strong"], ["warning_block"])
    ck("C5 clean text yields nothing",
       doc_signal("= A =\n\"\"\"fine.\"\"\"\n")["strong"], [])

    # ------------------------------------------------------------- the sweep
    cells = {"both": [], "doc_only": [], "runtime_only": [], "neither": 0}
    weak_only = []
    not_in_runtime = 0
    scanned = 0
    per_ctx: dict = {}

    for ctx in CONTEXTS:
        c = {"scanned": 0, "both": 0, "doc_only": 0, "runtime_only": 0,
             "neither": 0, "not_in_runtime": 0, "weak_only": 0}
        for n in page_names(z, ctx):
            stem = n.split("/", 1)[1][:-4]
            raw = read_page(z, n)
            p = parse_page(n, raw)
            if p.directives.get("type") != "node":
                continue
            found, dep, info = runtime_depr(ctx, stem)
            if not found:
                c["not_in_runtime"] += 1
                not_in_runtime += 1
                continue
            sig = doc_signal(raw)
            d = bool(sig["strong"])
            scanned += 1
            c["scanned"] += 1
            key = f"{ctx}/{stem}"
            if d and dep:
                cells["both"].append(key)
                c["both"] += 1
            elif d and not dep:
                cells["doc_only"].append({"node": key, "markers": sig["strong"]})
                c["doc_only"] += 1
            elif dep and not d:
                cells["runtime_only"].append({"node": key, "runtime": info,
                                              "doc_weak_mention": sig["weak"]})
                c["runtime_only"] += 1
            else:
                cells["neither"] += 1
                c["neither"] += 1
                if sig["weak"]:
                    weak_only.append(key)
                    c["weak_only"] += 1
        per_ctx[ctx] = c

    report = {
        "schema": "i0-q6/v1",
        "build": BUILD,
        "runtime": hou.applicationVersionString(),
        "truth_tier": "VERIFIED-RUNTIME (runtime axis) + VERIFIED-STATIC (doc axis)",
        "producer": "harness/notes/ingest/_i0_q6_deprecation.py",
        "doc_signal_definition": {
            "strong": ["#status: deprecated", ":include /composite/_old_cops_deprecated:",
                       ":warning:Deprecated"],
            "weak": "prose mention of deprecat|obsolete — reported, never counted as strong",
            "why_tiered": "H7-F12: lop/reference.txt's '($IIDX is deprecated)' is about an "
                          "expression variable; counting it flags a node SYNAPSE emits 78x",
        },
        "controls": controls,
        "controls_passed": sum(1 for c in controls if c["pass"]),
        "controls_total": len(controls),
        "nodes_scanned": scanned,
        "pages_typed_node_absent_from_runtime": not_in_runtime,
        "counts": {
            "both": len(cells["both"]),
            "doc_says_runtime_does_not": len(cells["doc_only"]),
            "runtime_says_doc_does_not": len(cells["runtime_only"]),
            "neither": cells["neither"],
            "union": len(cells["both"]) + len(cells["doc_only"]) + len(cells["runtime_only"]),
            "neither_but_weak_prose_mention": len(weak_only),
        },
        "per_context": per_ctx,
        "doc_says_runtime_does_not": cells["doc_only"],
        "runtime_says_doc_does_not": cells["runtime_only"],
        "both": cells["both"],
        "weak_only_examples": weak_only[:40],
    }
    out = os.path.join(HERE, "_i0_q6_deprecation.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"controls: {report['controls_passed']}/{report['controls_total']}")
    for c in controls:
        if not c["pass"]:
            print(f"   FAIL {c['control']}: {c['got']!r} != {c['want']!r}")
    print(f"\nnode-typed pages joined to the live runtime: {scanned}")
    print(f"node-typed pages with NO live type          : {not_in_runtime}")
    print(f"\n{'':22s} {'both':>6s} {'DOC-only':>9s} {'RUNTIME-only':>13s} {'neither':>8s}")
    for ctx in CONTEXTS:
        c = per_ctx[ctx]
        print(f"{ctx:22s} {c['both']:6d} {c['doc_only']:9d} "
              f"{c['runtime_only']:13d} {c['neither']:8d}")
    k = report["counts"]
    print(f"\nTOTAL  both={k['both']}  doc-says-runtime-does-not={k['doc_says_runtime_does_not']}"
          f"  runtime-says-doc-does-not={k['runtime_says_doc_does_not']}"
          f"  union={k['union']}")
    print(f"\nruntime-only (the DANGEROUS cell — docs read clean):")
    for r in cells["runtime_only"][:25]:
        print(f"   {r['node']:34s} weak_prose={r['doc_weak_mention']}")
    print(f"\nwrote {out}")
    return 0


main()
