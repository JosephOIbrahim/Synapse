"""I1 — the PROBE axis. Runs under hython on live Houdini 22.0.368.

This producer is SEPARATE from `i1b_extract.py` on purpose. Documentation
grounding and probe grounding are different tiers and are never summed into one
number: the docs say what a node is FOR, only the runtime says what it DOES.
Keeping them in two artifacts written by two producers makes that structural
rather than a promise in prose.

Four things are measured here, each with its own failure condition:

  1. CATALOGUE TOTALS      hou.nodeTypeCategories()[c].nodeTypes()
                           the denominators the brief reports against. Probed,
                           never inherited.

  2. TYPE RESOLUTION       does each help page's candidate type spelling exist
                           in the live catalogue? A page that resolves to no
                           live type documents nothing this build can create.

  3. LABEL AGREEMENT       I0-R2's precision pass. For every documented
                           parameter, does its normalised LABEL match a live
                           parameter label? Recorded PER ENTRY, so precision
                           becomes a per-entry fact instead of a corpus-wide
                           unknown — and the corpus re-audits itself on the
                           next build. Templates, not instances: labels live on
                           the tuple, and 693 instantiations is a risk this
                           measurement does not need.

  4. DEPRECATION           nodeType().deprecationInfo(). The runtime side of
                           the union. R72: doc and runtime disagree, and the
                           dangerous direction is runtime-flagged/doc-silent.

  5. THE 20-NODE CROSS-CHECK  the brief's oracle, and the only part that
                           INSTANTIATES: documented parameter names vs the real
                           node.parms() / node.parmTuples() of a created node.
                           Agreement count reported.

Producer: this file -> harness/notes/ingest/_i1b_runtime.json
"""

from __future__ import annotations

import json
import re
import sys
import traceback
from pathlib import Path

import hou

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

BUILD = "22.0.368"
CATEGORY = {"cop": "Cop", "lop": "Lop", "cop2": "Cop2"}
_WS = re.compile(r"\s+")


def norm_label(s: str) -> str:
    """Must stay byte-identical in behaviour to _i1_reader.norm_label.
    Duplicated rather than imported because this file runs under hython and
    must not drag the archive reader (and its zip handles) into the host."""
    return _WS.sub(" ", (s or "").replace("’", "'").strip()).casefold()


# The 20 for the instantiated cross-check. Chosen to span the measured hazards
# rather than to flatter the result: pages with parameters at column 0 and at
# indent 8, a CRLF page, a BOM page, an #id-keyed page and a #channels-keyed
# one, a page whose parameters exist ONLY after include resolution, the
# pathological USD-attribute-id page, both runtime-deprecated Karma LOPs, and
# six of the newly-named Copernicus nodes.
CROSSCHECK = [
    ("cop", "chromakey"), ("cop", "camerablend"), ("cop", "grunge_rust"),
    ("cop", "cellularnoise3d"), ("cop", "adjacency_distort"), ("cop", "xform"),
    ("cop", "blur"), ("cop", "remap"),
    ("lop", "distantlight"), ("lop", "rendersettings"), ("lop", "karma"),
    ("lop", "karmarenderproperties"), ("lop", "sublayer"), ("lop", "reference"),
    ("lop", "componentoutput"),
    ("cop2", "blur"), ("cop2", "emboss"), ("cop2", "levels"),
    ("cop2", "light"), ("cop2", "sharpen"),
]


def catalogue() -> dict:
    cats = hou.nodeTypeCategories()
    out = {}
    for ctx, cat in CATEGORY.items():
        types = cats[cat].nodeTypes()
        out[ctx] = {
            "category": cat,
            "total": len(types),
            "names": sorted(types.keys()),
        }
    return out


def template_labels(ntype) -> tuple[set, set, int]:
    """(normalised labels, internal names, count) from the parm template group."""
    labels, names, n = set(), set(), 0
    try:
        grp = ntype.parmTemplateGroup()
    except Exception:
        return labels, names, 0

    def walk(templates):
        nonlocal n
        for t in templates:
            try:
                lab = t.label()
                if lab:
                    labels.add(norm_label(lab))
                names.add(t.name())
                n += 1
            except Exception:
                pass
            try:
                if isinstance(t, hou.FolderParmTemplate):
                    walk(t.parmTemplates())
            except Exception:
                pass

    walk(grp.parmTemplates())
    return labels, names, n


def resolve_type(cands: list, live: dict):
    for c in cands:
        if c in live:
            return c
    return None


def crosscheck(doc_by_key: dict) -> dict:
    """INSTANTIATE 20 nodes and compare documented parameter names against the
    real node.parms() / node.parmTuples(). This is the brief's oracle."""
    rows = []
    roots = {}
    try:
        roots["cop"] = hou.node("/obj").createNode("copnet", "i1_cop")
    except Exception:
        roots["cop"] = None
    try:
        roots["lop"] = hou.node("/stage")
    except Exception:
        roots["lop"] = None
    try:
        img = hou.node("/img") or hou.root().createNode("img", "i1_img")
        roots["cop2"] = img.createNode("img", "i1_comp")
    except Exception:
        roots["cop2"] = None

    for ctx, stem in CROSSCHECK:
        key = "%s/%s.txt" % (ctx, stem)
        doc = doc_by_key.get(key)
        row = {"context": ctx, "stem": stem, "source": key}
        if doc is None:
            row["status"] = "no-doc-entry"
            rows.append(row)
            continue
        parent = roots.get(ctx)
        if parent is None:
            row["status"] = "no-parent-network"
            rows.append(row)
            continue
        node = None
        for cand in doc["type_candidates"]:
            try:
                node = parent.createNode(cand)
                row["created_as"] = cand
                break
            except Exception:
                continue
        if node is None:
            row["status"] = "could-not-create"
            rows.append(row)
            continue
        try:
            live_parm_names = {p.name() for p in node.parms()}
            live_tuple_names = {p.name() for p in node.parmTuples()}
            live_labels = {norm_label(p.parmTemplate().label()) for p in node.parmTuples()}
            live_labels |= {norm_label(p.description()) for p in node.parms()}

            doc_params = doc["parameters"]
            doc_internal = [n for p in doc_params for n in p["internal_names"]]
            doc_labels = [p["label_norm"] for p in doc_params]

            name_hits = [n for n in doc_internal
                         if n in live_parm_names or n in live_tuple_names]
            label_hits = [l for l in doc_labels if l in live_labels]

            row.update({
                "status": "ok",
                "live_parms": len(live_parm_names),
                "live_parm_tuples": len(live_tuple_names),
                "documented_params": len(doc_params),
                "documented_internal_names": len(doc_internal),
                "internal_name_agreement": len(name_hits),
                "internal_name_agreement_pct": round(
                    100.0 * len(name_hits) / max(len(doc_internal), 1), 1),
                "label_agreement": len(label_hits),
                "label_agreement_pct": round(
                    100.0 * len(label_hits) / max(len(doc_labels), 1), 1),
                "documented_but_absent_names": sorted(
                    set(doc_internal) - live_parm_names - live_tuple_names)[:12],
            })
        except Exception as e:
            row["status"] = "probe-error: %s" % e
        finally:
            try:
                node.destroy()
            except Exception:
                pass
        rows.append(row)
    return {"nodes": rows}


def main() -> int:
    doc = json.loads((HERE / "_i1b_doc.json").read_text(encoding="utf-8"))
    cat = catalogue()

    per_entry = {}
    for e in doc["entries"]:
        ctx = e["context"]
        live = hou.nodeTypeCategories()[CATEGORY[ctx]].nodeTypes()
        tname = resolve_type(e["type_candidates"], live)
        rec = {
            "tier": "VERIFIED-RUNTIME",
            "build": BUILD,
            "producer": "harness/notes/ingest/i1b_runtime.py",
            "live_type": tname,
            "live_type_exists": tname is not None,
        }
        if tname is not None:
            nt = live[tname]
            labels, names, ntmpl = template_labels(nt)
            doc_labels = [p["label_norm"] for p in e["parameters"]]
            doc_names = [n for p in e["parameters"] for n in p["internal_names"]]
            lab_hits = [l for l in doc_labels if l in labels]
            nam_hits = [n for n in doc_names if n in names]
            try:
                dep = nt.deprecationInfo() or {}
            except Exception:
                dep = {}
            rec.update({
                "live_parm_templates": ntmpl,
                "documented_params": len(doc_labels),
                "label_resolved": len(lab_hits),
                "label_resolved_pct": round(
                    100.0 * len(lab_hits) / max(len(doc_labels), 1), 1),
                "internal_name_resolved": len(nam_hits),
                "documented_internal_names": len(doc_names),
                "deprecation_runtime": {
                    "is_deprecated": bool(dep),
                    "reason": str(dep.get("reason", "")) if dep else "",
                    "new_type": str(dep.get("new_type", "")) if dep else "",
                    "version": str(dep.get("version", "")) if dep else "",
                },
                # per-parameter, so the corpus is self-auditing next build
                "per_parameter_label_resolved": [
                    p["label_norm"] in labels for p in e["parameters"]],
            })
        per_entry[e["source"]] = rec

    doc_by_key = {e["source"]: e for e in doc["entries"]}
    cc = crosscheck(doc_by_key)

    out = {
        "producer": "harness/notes/ingest/i1b_runtime.py",
        "build": hou.applicationVersionString(),
        "tier": "VERIFIED-RUNTIME",
        "tier_note": "Probe grounding. NEVER summed with the VERIFIED-DOC axis "
                     "into a single coverage number.",
        "catalogue_totals": {k: v["total"] for k, v in cat.items()},
        "catalogue_names": {k: v["names"] for k, v in cat.items()},
        "per_entry": per_entry,
        "crosscheck_20": cc,
    }
    (HERE / "_i1b_runtime.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    print("RUNTIME PASS  build=%s" % out["build"])
    for k, v in out["catalogue_totals"].items():
        print("  catalogue %-5s %d" % (k, v))
    ok = [r for r in cc["nodes"] if r.get("status") == "ok"]
    print("  crosscheck nodes ok: %d / %d" % (len(ok), len(cc["nodes"])))
    for r in cc["nodes"]:
        if r.get("status") == "ok":
            print("    %-5s %-24s live_parms=%-4d doc=%-4d names=%-4d(%.0f%%) labels=%d(%.0f%%)"
                  % (r["context"], r["stem"], r["live_parms"], r["documented_params"],
                     r["internal_name_agreement"], r["internal_name_agreement_pct"],
                     r["label_agreement"], r["label_agreement_pct"]))
        else:
            print("    %-5s %-24s %s" % (r["context"], r["stem"], r.get("status")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
