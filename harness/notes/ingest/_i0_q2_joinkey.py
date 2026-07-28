"""I0 / Q2 — WHICH FIELD JOINS a documented parameter to a live one?

Runs under hython on the live 22.0.368 build. Answers, per candidate key, the
match rate against the running runtime — not against an assumption, and not by
inheriting H9's verdict.

Six candidate keys, because the runtime exposes parameters at TWO levels and the
documentation is not consistent about which one it names:

  K1  #id            -> node.parms()          component level  (tx, ty, tz)
  K2  #id            -> node.parmTuples()     tuple level      (t)
  K3  #id, component suffix stripped -> node.parms()
  K4  label          -> parm labels
  K5  label          -> parmTuple labels
  K6  #channels (leading '/' stripped) -> node.parms()

R60: the probe carries its own controls. A POSITIVE control asserts a
hand-verified match; a NEGATIVE control asserts that a fabricated id does NOT
match. Without the negative, a matcher that returns True for everything scores
100% and means nothing.

Run:
  hython harness/notes/ingest/_i0_q2_joinkey.py
Emits:
  harness/notes/ingest/_i0_q2_joinkey.json
"""

from __future__ import annotations

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import hou  # noqa: E402

from _i0_reader import (BUILD, open_archive, page_names, parse_page,  # noqa: E402
                        read_page)

SEED = 20260727            # deterministic: a re-run on this build is identical
POP_SAMPLE_PER_CTX = 25    # population sweep, on top of the hand-picked 15

# The 15 the brief asks for. Chosen to include every hard case found in Q1 —
# not a convenience sample. Each entry: (context, page stem, why it is here).
HAND_PICKED = [
    ("cop",  "chromakey",          "every param carries #id; CRLF page"),
    ("cop",  "adjacency_distort",  "#contentfrom params with no inline prose"),
    ("cop",  "grunge_rust",        "one of the 161 new Copernicus nodes"),
    ("cop",  "cellularnoise3d",    "one of the 161 new Copernicus nodes"),
    ("cop",  "chromaticaberration", "new-surface COP"),
    ("cop2", "blur",               "ZERO #id; the :include deprecation banner"),
    ("cop2", "edgeblur",           "#channels instead of #id"),
    ("cop2", "emboss",             "H9: 15/15 ids recovered by suffix-stripping"),
    ("lop",  "karma",              "R72/H7-F2 doc-silent deprecation, 123 emissions"),
    ("lop",  "rendersettings",     "H9: 199 documented ids vs 48 live parms"),
    ("lop",  "distantlight",       "H9: 62 punycode parms on the live type"),
    ("sop",  "xform",              "tuple-vs-component split; the :vimeo: id trap"),
    ("sop",  "scatter",            "high-parameter-count SOP"),
    ("out",  "geometry",           "ROP context, sparse ids"),
    ("top",  "ropfetch",           "@top_attributes, not @parameters"),
]

CATEGORY = {
    "cop": "Cop", "cop2": "Cop2", "lop": "Lop", "sop": "Sop",
    "out": "Driver", "top": "Top", "dop": "Dop", "chop": "Chop",   # measured: "Top", not "TOP"
    "obj": "Object", "vop": "Vop",
}


# ---------------------------------------------------------------- name mapping
def stem_to_typenames(stem: str) -> list:
    """Help filenames encode namespace/version. Measured conventions:
         'ns--name'   -> 'ns::name'
         'name-2.0'   -> 'name::2.0'
    Returns candidates most-specific first; CALIBRATED below against the live
    catalogue rather than trusted."""
    out = [stem]
    if "--" in stem:
        out.append(stem.replace("--", "::"))
    base, sep, tail = stem.rpartition("-")
    if sep and tail and tail[0].isdigit():
        out.append(f"{base}::{tail}")
        if "--" in base:
            out.append(f"{base.replace('--', '::')}::{tail}")
    return list(dict.fromkeys(out))


_PARENTS: dict = {}


def parent_for(ctx: str):
    """A container in which a node of this context can be instantiated."""
    if ctx in _PARENTS:
        return _PARENTS[ctx]
    obj = hou.node("/obj")
    if ctx == "sop":
        p = obj.createNode("geo", "i0_geo")
    elif ctx == "cop":
        p = obj.createNode("copnet", "i0_copnet")
    elif ctx == "cop2":
        p = hou.node("/img").createNode("img", "i0_img")
    elif ctx == "lop":
        p = hou.node("/stage")
    elif ctx == "out":
        p = hou.node("/out")
    elif ctx == "top":
        p = obj.createNode("topnet", "i0_topnet")
    elif ctx == "dop":
        p = obj.createNode("dopnet", "i0_dopnet")
    else:
        p = None
    _PARENTS[ctx] = p
    return p


def live_parms(ctx: str, stem: str):
    """Instantiate and read the live parameter surface. Returns None if the type
    does not exist on this build (an absent type is data, not an error)."""
    parent = parent_for(ctx)
    if parent is None:
        return None
    cat = hou.nodeTypeCategories().get(CATEGORY.get(ctx, ""))
    if cat is None:
        return None
    nt = None
    used = None
    for cand in stem_to_typenames(stem):
        nt = hou.nodeType(cat, cand)
        if nt is not None:
            used = cand
            break
    if nt is None:
        return None
    try:
        n = parent.createNode(nt.name())
    except Exception:
        return None
    try:
        parms = {p.name() for p in n.parms()}
        parm_labels = {p.parmTemplate().label() for p in n.parms()}
        tuples = {p.name() for p in n.parmTuples()}
        tuple_labels = {p.parmTemplate().label() for p in n.parmTuples()}
        depr = nt.deprecationInfo() or {}
        depr = {k: str(v) for k, v in depr.items()}
    finally:
        try:
            n.destroy()
        except Exception:
            pass
    return {
        "type_name": used, "resolved": nt.name(),
        "parms": parms, "parm_labels": parm_labels,
        "tuples": tuples, "tuple_labels": tuple_labels,
        "deprecation": depr,
    }


# ---------------------------------------------------------------- key matchers
_COMPONENT_SUFFIXES = ("x", "y", "z", "w", "r", "g", "b", "a",
                       "1", "2", "3", "4", "u", "v")


def strip_component(name: str) -> str:
    if len(name) > 1 and name[-1] in _COMPONENT_SUFFIXES:
        return name[:-1]
    return name


def norm_label(s: str) -> str:
    return " ".join(s.replace("’", "'").split()).strip().lower()


def score(doc_params, live) -> dict:
    """Per-candidate-key hit counts over one node's documented parameters."""
    res = {k: 0 for k in ("K1_id_vs_parms", "K2_id_vs_tuples",
                          "K3_idstrip_vs_parms", "K4_label_vs_parmlabels",
                          "K5_label_vs_tuplelabels", "K6_channels_vs_parms")}
    denom = {k: 0 for k in res}
    plabels = {norm_label(x) for x in live["parm_labels"]}
    tlabels = {norm_label(x) for x in live["tuple_labels"]}
    for it in doc_params:
        if it.ident:
            denom["K1_id_vs_parms"] += 1
            denom["K2_id_vs_tuples"] += 1
            denom["K3_idstrip_vs_parms"] += 1
            if it.ident in live["parms"]:
                res["K1_id_vs_parms"] += 1
            if it.ident in live["tuples"]:
                res["K2_id_vs_tuples"] += 1
            if strip_component(it.ident) in live["parms"] or it.ident in live["parms"]:
                res["K3_idstrip_vs_parms"] += 1
        if it.label:
            denom["K4_label_vs_parmlabels"] += 1
            denom["K5_label_vs_tuplelabels"] += 1
            nl = norm_label(it.label)
            if nl in plabels:
                res["K4_label_vs_parmlabels"] += 1
            if nl in tlabels:
                res["K5_label_vs_tuplelabels"] += 1
        if it.channels:
            for ch in it.channels.split():
                denom["K6_channels_vs_parms"] += 1
                if ch.lstrip("/") in live["parms"]:
                    res["K6_channels_vs_parms"] += 1
    return {"hits": res, "denom": denom}


# ---------------------------------------------------------------- controls
def run_controls(z) -> list:
    out = []

    def ck(name, got, want, note=""):
        out.append({"control": name, "got": got, "want": want,
                    "pass": got == want, "note": note})

    # name-mapping calibration against the LIVE catalogue
    ck("C1 stem_map plain", stem_to_typenames("xform"), ["xform"])
    ck("C1 stem_map versioned", stem_to_typenames("bakegeometrytextures-2.0"),
       ["bakegeometrytextures-2.0", "bakegeometrytextures::2.0"])
    ck("C1 stem_map namespaced", stem_to_typenames("rig--CurveIK"),
       ["rig--CurveIK", "rig::CurveIK"])

    # POSITIVE: a hand-verified join that MUST hold
    lv = live_parms("sop", "xform")
    ck("C2 xform instantiates", lv is not None, True)
    if lv:
        ck("C2 'tx' is a live PARM", "tx" in lv["parms"], True)
        ck("C2 't' is NOT a live parm", "t" in lv["parms"], False,
           "the documented '#id: t' names the TUPLE, not the parm")
        ck("C2 't' IS a live parmTuple", "t" in lv["tuples"], True)
        ck("C2 'Translate' is a live tuple label",
           "translate" in {norm_label(x) for x in lv["tuple_labels"]}, True)

    # NEGATIVE: a fabricated id must not match anything. Without this, a
    # permissive matcher scores 100% and the whole Q2 table is meaningless.
    if lv:
        fake = "zzz_i0_not_a_real_parm"
        ck("C3 fabricated id does NOT match parms", fake in lv["parms"], False)
        ck("C3 fabricated id does NOT match tuples", fake in lv["tuples"], False)
        ck("C3 fabricated label does NOT match",
           norm_label("Zzz I0 Not A Real Label") in
           {norm_label(x) for x in lv["parm_labels"]}, False)

    # K3's stripper must be ALIVE. Its zero lift over K1 is only a finding if the
    # function can in fact fire; a dead branch would score zero identically.
    ck("C6 strip_component fires", strip_component("diffr"), "diff")
    ck("C6 strip_component leaves non-suffixed alone", strip_component("signature"), "signature")

    # NEGATIVE: an absent node type returns None rather than a silent empty match
    ck("C4 absent type -> None", live_parms("sop", "i0_definitely_absent_type"), None)

    # POSITIVE: the reader still reproduces its hand-read control inside hython
    p = parse_page("cop/chromakey.txt", read_page(z, "cop/chromakey.txt"))
    ck("C5 reader intact under hython", len(p.params), 15)
    return out


# ---------------------------------------------------------------- main
def main() -> int:
    z = open_archive()
    controls = run_controls(z)

    # ---- build the node list: 15 hand-picked + a seeded population sweep
    rng = random.Random(SEED)
    picked = [(c, s) for c, s, _ in HAND_PICKED]
    sweep = []
    for ctx in ("cop", "cop2", "lop", "sop", "out", "top"):
        stems = [n.split("/", 1)[1][:-4] for n in page_names(z, ctx)]
        stems = [s for s in stems if not s.startswith("_") and s != "index"]
        rng.shuffle(stems)
        sweep += [(ctx, s) for s in stems[:POP_SAMPLE_PER_CTX]]

    results = {"hand_picked": [], "population_sweep": []}
    agg = {}

    def run_set(pairs, bucket):
        for ctx, stem in pairs:
            name = f"{ctx}/{stem}.txt"
            try:
                page = parse_page(name, read_page(z, name))
            except KeyError:
                results[bucket].append({"node": f"{ctx}/{stem}",
                                        "status": "NO_PAGE"})
                continue
            lv = live_parms(ctx, stem)
            if lv is None:
                results[bucket].append({"node": f"{ctx}/{stem}",
                                        "status": "NOT_IN_RUNTIME",
                                        "documented_params": len(page.params)})
                continue
            sc = score(page.params, lv)
            row = {
                "node": f"{ctx}/{stem}",
                "status": "OK",
                "live_type": lv["resolved"],
                "documented_params": len(page.params),
                "documented_with_id": len(page.params_with_id),
                "documented_with_channels": sum(1 for i in page.params if i.channels),
                "live_parms": len(lv["parms"]),
                "live_tuples": len(lv["tuples"]),
                "runtime_deprecated": bool(lv["deprecation"]),
                "hits": sc["hits"], "denom": sc["denom"],
            }
            results[bucket].append(row)
            a = agg.setdefault(bucket, {"hits": {}, "denom": {}})
            for k in sc["hits"]:
                a["hits"][k] = a["hits"].get(k, 0) + sc["hits"][k]
                a["denom"][k] = a["denom"].get(k, 0) + sc["denom"][k]

    run_set(picked, "hand_picked")
    run_set(sweep, "population_sweep")

    rates = {}
    for bucket, a in agg.items():
        rates[bucket] = {
            k: {"matched": a["hits"][k], "of": a["denom"][k],
                "pct": round(100.0 * a["hits"][k] / a["denom"][k], 1) if a["denom"][k] else None}
            for k in sorted(a["hits"])
        }

    report = {
        "schema": "i0-q2/v1",
        "build": BUILD,
        "runtime": hou.applicationVersionString(),
        "truth_tier": "VERIFIED-RUNTIME",
        "seed": SEED,
        "producer": "harness/notes/ingest/_i0_q2_joinkey.py",
        "reader": "harness/notes/ingest/_i0_reader.py (calibrated 57/57)",
        "controls": controls,
        "controls_passed": sum(1 for c in controls if c["pass"]),
        "controls_total": len(controls),
        "match_rates": rates,
        "per_node": results,
    }
    out = os.path.join(HERE, "_i0_q2_joinkey.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"runtime {hou.applicationVersionString()}  seed {SEED}")
    print(f"controls: {report['controls_passed']}/{report['controls_total']}")
    for c in controls:
        if not c["pass"]:
            print(f"   FAIL {c['control']}: got {c['got']!r} want {c['want']!r}")
    for bucket in ("hand_picked", "population_sweep"):
        n_ok = sum(1 for r in results[bucket] if r.get("status") == "OK")
        print(f"\n=== {bucket}  ({n_ok} nodes joined to the live runtime) ===")
        print(f"{'candidate key':28s} {'matched':>9s} {'of':>7s} {'rate':>7s}")
        for k, v in rates.get(bucket, {}).items():
            print(f"{k:28s} {v['matched']:9d} {v['of']:7d} "
                  f"{(str(v['pct'])+'%') if v['pct'] is not None else '   n/a':>7s}")
    print(f"\nwrote {out}")
    return 0


main()
