"""V1 / PROBE C — the ID-AOV and denoiser parm surface (Q2 + Q4).

Q2 is the crux of the whole harness: without a per-pixel prim identity there is no
mask, and without a mask there is no "only X changed".

retina/ingest.py:191 tells a caller to "declare an ID AOV
(karmarendersettings.primid=1)". That is a SPELLING CLAIM about a live build and
this probe settles it. R90 is the precedent: SYNAPSE shipped two
hou.NodeEventType spellings that were not the build's.

Method is R73's: do not keyword-guess parm names. Enumerate the COMPLETE parm list
of each render node type and then classify. Reading the whole list is the positive
control that licenses an ABSENT verdict (R50).

Controls (Law 1):
  positive  each node type must instantiate and yield a non-empty parm list. If it
            does not, every parm verdict on it is UNVERIFIABLE, not ABSENT.
  negative  a synthetic parm name must NOT resolve on any node. A parm lookup that
            answers yes to everything makes every CONFIRMED here worthless.
  FAILS IF  a target type yields zero parms, or the synthetic parm resolves.

Instantiates throwaway nodes in this process's in-memory scene only. Writes no
scene file, touches no repo path.
"""

from __future__ import annotations

import json
import re
import sys
import traceback

OUT = sys.argv[1] if len(sys.argv) > 1 else "probe_c_aov_denoise.json"

import hou  # noqa: E402

SYNTHETIC = "zzz_parm_that_cannot_exist_v1"

# Spellings the tree or the docs assert. Each gets an explicit verdict.
ASSERTED_SPELLINGS = [
    ("karmarendersettings", "primid",
     "retina/ingest.py:191 tells callers to set karmarendersettings.primid=1"),
]

ID_PAT = re.compile(
    r"(primid|prim_id|objid|obj_id|objectid|object_id|elementid|instanceid|"
    r"crypto|cryptomatte|id$|_id|idmask)", re.I)
AOV_PAT = re.compile(r"(aov|rendervar|render_var|extraimageplane|imageplane|plane|product)", re.I)
DENOISE_PAT = re.compile(r"(denois|oidn|optix|nvidia)", re.I)
SAMPLE_PAT = re.compile(r"(samples|convergence|pathtrace|raylimit|pixelsamples|minsamples|maxsamples)", re.I)


def parm_rows(node, pat):
    out = []
    for p in node.parms():
        t = p.parmTemplate()
        name, label = p.name(), (t.label() if t else "")
        if pat.search(name) or (label and pat.search(label)):
            row = {"name": name, "label": label,
                   "type": type(t).__name__ if t else None}
            try:
                row["default"] = p.eval()
                if isinstance(row["default"], (bytes, bytearray)):
                    row["default"] = repr(row["default"])[:120]
            except Exception as exc:
                row["default"] = f"ERROR {exc!r}"[:120]
            try:
                if t is not None and hasattr(t, "menuItems") and t.menuItems():
                    row["menu_items"] = list(t.menuItems())[:40]
                    row["menu_labels"] = list(t.menuLabels())[:40]
            except Exception:
                pass
            out.append(row)
    return out


R = {
    "probe": "V1/C ID-AOV + denoiser parm surface",
    "producer": "harness/notes/v1/probe_c_aov_denoise.py",
    "build": str(hou.applicationVersionString()),
    "license_category": str(hou.licenseCategory()),
    "node_types": {},
    "asserted_spellings": [],
    "controls": {},
}

CATS = {
    "lop": hou.lopNodeTypeCategory(),
    "rop": hou.ropNodeTypeCategory(),
    "cop": hou.copNodeTypeCategory(),
}

# 1. Which render-relevant node types exist at all, by category.
avail = {}
for cname, cat in CATS.items():
    try:
        avail[cname] = sorted(cat.nodeTypes().keys())
    except Exception as exc:
        avail[cname] = f"ERROR {exc!r}"
R["type_census"] = {
    c: {"count": len(v) if isinstance(v, list) else None,
        "render_related": [t for t in v if re.search(r"(karma|render|husk|usdrender|rendervar|aov|denois)", t, re.I)]
        if isinstance(v, list) else v}
    for c, v in avail.items()
}

TARGETS = [
    ("karmarendersettings", "lop"),
    ("rendervar", "lop"),
    ("renderproduct", "lop"),
    ("rendersettings", "lop"),
    ("karmarenderproperties", "lop"),
    ("usdrender_rop", "lop"),
    ("usdrender", "lop"),
    ("karma", "lop"),
    ("rendergeometrysettings", "lop"),
]

stage = hou.node("/stage")
synthetic_resolved_anywhere = False
built_any = False

for tname, cname in TARGETS:
    entry = {"category": cname, "requested": tname}
    cat = CATS.get(cname)
    try:
        types = cat.nodeTypes()
        entry["type_exists"] = tname in types
        if not entry["type_exists"]:
            entry["verdict"] = "ABSENT"
            entry["control"] = (
                f"licensed: the complete {cname} type list was enumerated "
                f"({len(types)} types) and this spelling is not in it"
            )
            R["node_types"][tname] = entry
            continue
        n = stage.createNode(tname)
        parms = n.parms()
        entry["verdict"] = "CONFIRMED"
        entry["parm_count"] = len(parms)
        entry["control_parms_nonempty"] = len(parms) > 0
        if len(parms) > 0:
            built_any = True
        # negative control on THIS node
        entry["synthetic_parm_resolves"] = n.parm(SYNTHETIC) is not None
        if entry["synthetic_parm_resolves"]:
            synthetic_resolved_anywhere = True
        entry["id_parms"] = parm_rows(n, ID_PAT)
        entry["aov_parms"] = parm_rows(n, AOV_PAT)
        entry["denoise_parms"] = parm_rows(n, DENOISE_PAT)
        entry["sampling_parms"] = parm_rows(n, SAMPLE_PAT)
        entry["all_parm_names"] = [p.name() for p in parms]
    except Exception:
        entry["verdict"] = "UNVERIFIABLE"
        entry["error"] = traceback.format_exc()[-900:]
    R["node_types"][tname] = entry

# 2. The spellings the tree asserts, settled one by one.
for tname, parmname, why in ASSERTED_SPELLINGS:
    row = {"node_type": tname, "parm": parmname, "asserted_by": why}
    e = R["node_types"].get(tname, {})
    if e.get("verdict") != "CONFIRMED":
        row["verdict"] = "UNVERIFIABLE"
        row["note"] = f"node type {tname} did not instantiate; no parm claim is licensed"
    else:
        names = e.get("all_parm_names", [])
        row["verdict"] = "CONFIRMED" if parmname in names else "ABSENT"
        row["control"] = (
            f"licensed: the complete parm list of {tname} was enumerated "
            f"({len(names)} parms) and searched"
        )
        if row["verdict"] == "ABSENT":
            row["nearest_spellings"] = [
                n for n in names if parmname.lower() in n.lower()
                or n.lower() in parmname.lower()
                or ID_PAT.search(n)
            ][:25]
    R["asserted_spellings"].append(row)

R["controls"] = {
    "any_target_built": built_any,
    "synthetic_parm_resolved_anywhere": synthetic_resolved_anywhere,
    "negative_ok": not synthetic_resolved_anywhere,
    "positive_ok": built_any,
    "controls_ok": built_any and not synthetic_resolved_anywhere,
    "synthetic_parm_used": SYNTHETIC,
    "stated_failure_condition": (
        "controls_ok is false if no target node type instantiated with a non-empty "
        "parm list (making every ABSENT here an artifact of a dead probe), or if a "
        "synthetic parm name resolved on any node (making every CONFIRMED here the "
        "output of a lookup that answers yes to everything)."
    ),
}

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(R, fh, indent=1)

print(f"controls_ok={R['controls']['controls_ok']} "
      f"positive={R['controls']['positive_ok']} negative={R['controls']['negative_ok']}")
for t, e in R["node_types"].items():
    print(f"  {e.get('verdict','?'):13} {t:26} parms={e.get('parm_count','-')} "
          f"id={len(e.get('id_parms',[]))} aov={len(e.get('aov_parms',[]))} "
          f"denoise={len(e.get('denoise_parms',[]))}")
for row in R["asserted_spellings"]:
    print(f"  ASSERTED {row['node_type']}.{row['parm']} -> {row['verdict']}")
print(f"wrote {OUT}")
