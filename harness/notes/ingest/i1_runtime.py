"""I1 -- the LIVE half. Runs under ``hython`` on Houdini 22.0.368.

    "$HFS/bin/hython" harness/notes/ingest/i1_runtime.py

Produces the runtime facts the corpus needs and the archive cannot supply:

  * the three live catalogues (Cop 384 / Cop2 169 / Lop 218) -- the DENOMINATOR
    every coverage number in this leg is reported against.
  * per type: display label, ``deprecationInfo()``, and the parameter surface
    at BOTH levels the runtime exposes -- tuple names/labels and expanded
    component names. I0-F3 measured that documentation is not consistent about
    which level it names, and that trying ``#id`` against parmTuples BEFORE
    parms is worth 2-8 points for free.
  * the per-entry precision pass I0-R2 asks for: without live labels there is no
    way to say whether an extracted parameter is real, and a corpus that cannot
    say that is asserting its own accuracy.

TRUTH TIER: **VERIFIED-RUNTIME** (22.0.368). Kept in a SEPARATE artifact from
the doc-derived corpus and joined at build time with the source recorded per
side. Docs say what a node is FOR; only this says what it DOES. The two are
never summed into one grounding number.

Determinism: no wall-clock stamp. A second run on the same build must be
byte-identical, matching the convention the committed LOP catalogue already set.

PRODUCER: this file -> harness/notes/ingest/_i1_runtime.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import hou

CATEGORIES = ("Cop", "Cop2", "Lop")

# Houdini's component-suffix convention. VERIFIED rather than assumed: the
# control at the bottom of this file expands sop/xform's templates and compares
# the result against a live ``node.parms()``. If the convention is wrong the
# control says so and the expansion is marked untrusted instead of quietly
# producing plausible names that join to nothing.
SUFFIXES = {
    "XYZW": ("x", "y", "z", "w"),
    "RGBA": ("r", "g", "b", "a"),
    "UVW": ("u", "v", "w"),
    "XYWH": ("x", "y", "w", "h"),
    "MinMax": ("min", "max"),
    "MaxMin": ("max", "min"),
    "StartEnd": ("start", "end"),
    "BeginEnd": ("begin", "end"),
}


def scheme_name(pt) -> str:
    try:
        return str(pt.namingScheme()).rsplit(".", 1)[-1]
    except Exception:
        return "Base1"


def component_names(pt) -> list:
    """The parm names one template produces, as ``node.parms()`` would name them."""
    name = pt.name()
    try:
        nc = pt.numComponents()
    except Exception:
        return [name]
    if not nc or nc <= 1:
        return [name]
    sch = scheme_name(pt)
    if sch in SUFFIXES:
        suf = SUFFIXES[sch]
        return [name + suf[i] for i in range(min(nc, len(suf)))]
    return ["%s%d" % (name, i + 1) for i in range(nc)]     # Base1


def walk(templates) -> list:
    """Flatten a parm template tree. Folders are containers, not parameters."""
    out = []
    for pt in templates:
        kids = None
        if isinstance(pt, (hou.FolderParmTemplate, hou.FolderSetParmTemplate)):
            try:
                kids = pt.parmTemplates()
            except Exception:
                kids = None
            if kids:
                out.extend(walk(kids))
            continue
        out.append(pt)
        if hasattr(pt, "parmTemplates"):
            try:
                kids = pt.parmTemplates()
            except Exception:
                kids = None
            if kids:
                out.extend(walk(kids))
    return out


def harvest_category(cat_name: str) -> dict:
    cats = hou.nodeTypeCategories()
    cat = cats[cat_name]
    types = {}
    errors = []
    for tname, nt in sorted(cat.nodeTypes().items()):
        rec = {
            "label": nt.description(),
            "is_manager": nt.isManager(),
            "is_generator": nt.isGenerator(),
        }
        try:
            dep = nt.deprecationInfo() or {}
        except Exception as exc:                                  # pragma: no cover
            dep = {}
            errors.append("%s deprecationInfo: %s" % (tname, exc))
        rec["deprecated"] = bool(dep)
        rec["deprecation_reason"] = dep.get("reason")
        rec["deprecation_version"] = dep.get("version")
        try:
            flat = walk(nt.parmTemplates())
        except Exception as exc:
            flat = []
            errors.append("%s parmTemplates: %s" % (tname, exc))
        tuple_names, tuple_labels, parm_names = [], [], []
        for pt in flat:
            tuple_names.append(pt.name())
            try:
                tuple_labels.append(pt.label())
            except Exception:
                tuple_labels.append("")
            parm_names.extend(component_names(pt))
        rec["tuple_names"] = tuple_names
        rec["tuple_labels"] = tuple_labels
        rec["parm_names"] = parm_names
        types[tname] = rec
    return {"category_name": cat_name, "count": len(types),
            "types": types, "probe_errors": errors}


# --------------------------------------------------------------- controls
def expansion_control() -> dict:
    """Prove the component-suffix expansion against a LIVE ``node.parms()``.

    Law 1: without this, ``parm_names`` is a convention I remembered, and every
    ``#id`` match measured against it would be measuring my memory. The control
    fails if the expansion invents a name the live node does not carry.
    """
    out = []
    parent = hou.node("/obj").createNode("geo", "i1_ctl_geo")
    stage = hou.node("/stage")
    copnet = hou.node("/obj").createNode("copnet", "i1_ctl_cop")
    targets = [
        ("Sop", "xform", parent),
        ("Sop", "sphere", parent),
        ("Lop", "distantlight::2.0", stage),
        ("Cop", "chromakey", copnet),
    ]
    cats = hou.nodeTypeCategories()
    for cat, tname, par in targets:
        rec = {"category": cat, "type": tname}
        try:
            nt = hou.nodeType(cats[cat], tname)
            expanded = []
            for pt in walk(nt.parmTemplates()):
                expanded.extend(component_names(pt))
            node = par.createNode(tname)
            live = [p.name() for p in node.parms()]
            live_tuples = [p.name() for p in node.parmTuples()]
            missing = sorted(set(live) - set(expanded))
            # A live node carries FOLDER parms (the tab switchers) as real
            # hou.Parm objects. They are runtime furniture, not documented
            # parameters, and the walk drops them on purpose. Classifying them
            # keeps "recall 0.75" from reading as a miss when it is a category
            # difference.
            folderish = []
            for nm in missing:
                p = node.parm(nm)
                try:
                    tpl = p.parmTemplate() if p else None
                    if isinstance(tpl, (hou.FolderParmTemplate, hou.FolderSetParmTemplate)):
                        folderish.append(nm)
                except Exception:
                    pass
            rec["expanded"] = len(expanded)
            rec["live_parms"] = len(live)
            rec["expanded_not_live"] = sorted(set(expanded) - set(live))[:12]
            rec["live_not_expanded"] = missing[:12]
            rec["live_not_expanded_total"] = len(missing)
            rec["live_not_expanded_that_are_folders"] = len(folderish)
            rec["invented_count"] = len(set(expanded) - set(live))
            rec["recall"] = round(len(set(expanded) & set(live)) / max(1, len(set(live))), 4)
            rec["tuple_names_match_live_tuples"] = len(
                set(pt.name() for pt in walk(nt.parmTemplates())) & set(live_tuples))
            rec["live_tuple_count"] = len(live_tuples)
            node.destroy()
            rec["ok"] = True
            rec["pass"] = rec["invented_count"] == 0
        except Exception as exc:
            rec["ok"] = False
            rec["pass"] = False
            rec["error"] = str(exc)
        out.append(rec)
    for n in (parent, copnet):
        try:
            n.destroy()
        except Exception:
            pass
    return {
        "asserts": "the component-suffix expansion reproduces live node.parms() names",
        "fails_if": "the expansion invents a parm name the live node does not carry, "
                    "in which case #id evidence measured against it is measuring a "
                    "convention rather than the runtime",
        "recall_note": "recall < 1.0 is EXPECTED and is not the failure condition. A "
                       "live node carries folder/tab-switcher parms and multiparm "
                       "instances that no documentation describes; the walk drops "
                       "folders deliberately. Only invented_count == 0 is asserted.",
        "pass": all(t.get("pass") for t in out),
        "targets": out,
    }


def deprecation_control() -> dict:
    """Prove ``deprecationInfo()`` can say BOTH things.

    Law 1: a detector that has only ever returned False on everything tested is
    not known to work. R72's canonical pair is used because it is the case this
    whole axis exists for.
    """
    cats = hou.nodeTypeCategories()
    pos = hou.nodeType(cats["Lop"], "karmarenderproperties")
    neg = hou.nodeType(cats["Cop"], "chromakey")
    return {
        "asserts": "deprecationInfo() returns a reason for a known-deprecated type "
                   "and empty for a known-current one",
        "fails_if": "the runtime deprecation axis is unfalsifiable -- it would report "
                    "the same verdict for every type",
        "positive": {"type": "Lop/karmarenderproperties",
                     "info": dict(pos.deprecationInfo() or {}) if pos else None},
        "negative": {"type": "Cop/chromakey",
                     "info": dict(neg.deprecationInfo() or {}) if neg else None},
        "pass": bool(pos and pos.deprecationInfo()) and not bool(neg and neg.deprecationInfo()),
    }


def main() -> int:
    build = hou.applicationVersionString()
    if build != "22.0.368":
        # Pinned, and loud. Every number in this leg moves with the build.
        print("REFUSING: expected 22.0.368, running %s" % build)
        return 2

    cats = {c: harvest_category(c) for c in CATEGORIES}
    controls = {
        "component_expansion": expansion_control(),
        "deprecation_detector": deprecation_control(),
    }

    out = {
        "schema": "i1_runtime/v1",
        "truth_tier": "VERIFIED-RUNTIME",
        "build": build,
        "producer": "harness/notes/ingest/i1_runtime.py (hython)",
        "determinism": "no wall-clock stamp; a second run on the same build is byte-identical",
        "tier_rule": "These are OBSERVED facts. They are kept in a separate artifact "
                     "from the VERIFIED-DOC corpus and joined with the source recorded "
                     "per side. A doc-derived grounding figure and a probe-derived one "
                     "are never summed.",
        "categories": cats,
        "controls": controls,
        "counts": {c: cats[c]["count"] for c in CATEGORIES},
    }
    dest = Path(__file__).resolve().parent / "_i1_runtime.json"
    dest.write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print("wrote %s" % dest)
    for c in CATEGORIES:
        print("  %-5s %4d types, %3d runtime-deprecated"
              % (c, cats[c]["count"],
                 sum(1 for t in cats[c]["types"].values() if t["deprecated"])))
    ec = controls["component_expansion"]
    for t in ec["targets"]:
        print("  expansion %-8s %-22s invented=%s recall=%s"
              % (t["category"], t["type"], t.get("invented_count"), t.get("recall")))
    print("  deprecation control pass=%s" % controls["deprecation_detector"]["pass"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
