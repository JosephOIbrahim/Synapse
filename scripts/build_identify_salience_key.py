"""BP11-SALIENCE T2: MEASURE the salience answer key (hython, Houdini 22.0.400).

The salience question is graded against a *measured* key, not a vote
(IDENTIFY_BLUEPRINT sec. 5). For each changed-parameter case this script:

  1. builds a fresh node of the case's type,
  2. sets the one parameter to a non-default value and cooks -> hash_changed,
  3. reverts *that one parameter* to its default and cooks -> hash_default,
  4. records ``matters = hash_changed != hash_default``.

The output hash is exactly the blueprint's:
  * SOP: point count, primitive count, bounding box, and a hash of the P
    attribute (the produced geometry).
  * LOP: the flattened layer export of the node's composed stage (what the
    node writes to USD).

Only hex hashes, booleans and strings enter the file, so a re-run on the same
build is byte-identical (no raw float formatting). A parameter that is missing on
this build, cannot be set, or does not actually leave its default is SKIPPED and
listed under ``skipped`` with a reason -- never guessed into a case.

Run (records its own producer command in the file):
    "C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe" \
        scripts/build_identify_salience_key.py

Exit 0 only when the file holds >= 40 cases across >= 10 node types; a shortfall
prints a FINDING and exits non-zero.
"""
import array
import hashlib
import json
import os
import sys
import traceback
from pathlib import Path

import hou

PRODUCER = "hython scripts/build_identify_salience_key.py"
OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "identify_salience_key_v1.json"
MIN_CASES = 40
MIN_TYPES = 10

# Curated candidate cases: (context, node_type, feeder, [(parm, non_default_value), ...]).
# ``feeder`` is a generator wired into input 0 (modifier SOPs/LOPs will not cook
# standalone), or None for a generator. Over-provisioned so build drift (a
# renamed/absent parm, a modifier that will not cook) still clears the floor; the
# producer MEASURES matters and skips any parm it cannot genuinely change.
CANDIDATES = [
    # --- SOP generators (no input) ---
    ("Sop", "grid", None, [("rows", 30), ("cols", 30), ("sizex", 2.5), ("sizey", 2.5)]),
    ("Sop", "box", None, [("sizex", 2.0), ("sizey", 2.0), ("tx", 1.0), ("dodivs", 1)]),
    ("Sop", "sphere", None, [("scale", 2.0), ("rows", 30), ("cols", 30), ("freq", 4)]),
    ("Sop", "tube", None, [("rad1", 0.7), ("rad2", 0.3), ("height", 2.0), ("cols", 24)]),
    ("Sop", "circle", None, [("radx", 1.5), ("rady", 0.8), ("divs", 24)]),
    ("Sop", "line", None, [("points", 10), ("dist", 2.0)]),
    ("Sop", "torus", None, [("rows", 24), ("cols", 24), ("radx", 1.5), ("rady", 0.4)]),
    # --- SOP modifiers (fed a generator) ---
    ("Sop", "mountain", "grid", [("height", 2.0), ("elementsize", 0.5)]),
    ("Sop", "scatter", "grid", [("npts", 500), ("seed", 3.0)]),
    ("Sop", "xform", "grid", [("tx", 1.0), ("scale", 2.0)]),
    ("Sop", "polyextrude", "box", [("dist", 0.5)]),
    ("Sop", "subdivide", "box", [("iterations", 2)]),
    ("Sop", "polybevel", "box", [("offset", 0.2)]),
    ("Sop", "color", "grid", [("colorr", 0.9), ("colorg", 0.2)]),
    ("Sop", "attribcreate", "grid", [("name1", "salience_probe")]),
    ("Sop", "normal", "grid", [("type", 1)]),
    ("Sop", "facet", "grid", [("prenml", 1), ("postnml", 1)]),
    # --- LOP generators (no input) ---
    ("Lop", "sphere", None, [("primpath", "/salience_ball"), ("radius", 2.0)]),
    ("Lop", "cube", None, [("primpath", "/salience_box")]),
    ("Lop", "light", None, [("primpath", "/salience_light")]),
    # --- LOP modifiers (fed a generator) ---
    ("Lop", "xform", "sphere", [("tx", 2.0), ("ty", 1.0)]),
    ("Lop", "duplicate", "sphere", [("ncy", 3)]),
]


def _sop_hash(node):
    geo = node.geometry()
    if geo is None:
        raise RuntimeError("no geometry")
    head = "pts:%s|prims:%s|bounds:%s" % (
        geo.intrinsicValue("pointcount"),
        geo.intrinsicValue("primitivecount"),
        geo.boundingBox(),
    )
    p = geo.pointFloatAttribValues("P") if geo.findPointAttrib("P") else ()
    body = array.array("f", p).tobytes()
    return hashlib.sha256(head.encode("utf-8") + body).hexdigest()


def _lop_hash(node):
    stage = node.stage()
    if stage is None:
        raise RuntimeError("no stage")
    usda = stage.Flatten().ExportToString()
    return hashlib.sha256(usda.encode("utf-8")).hexdigest()


def _make(ctx, type_name, feeder):
    """Return ``(to_destroy, node)``. A feeder generator is wired into input 0."""
    if ctx == "Sop":
        geo = hou.node("/obj").createNode("geo", "salkey_geo")
        node = geo.createNode(type_name)
        if feeder:
            node.setInput(0, geo.createNode(feeder))
        return [geo], node
    stage = hou.node("/stage")
    node = stage.createNode(type_name)
    to_destroy = [node]
    if feeder:
        gen = stage.createNode(feeder)
        node.setInput(0, gen)
        to_destroy.append(gen)
    return to_destroy, node


def _cook(node):
    node.cook(force=True)


def measure_case(ctx, type_name, feeder, parm_name, value):
    """Return a case dict or a (skip) dict. Fresh node; revert the one parm."""
    to_destroy = []
    node = None
    try:
        to_destroy, node = _make(ctx, type_name, feeder)
        parm = node.parm(parm_name)
        if parm is None:
            return {"skip": True, "reason": "no_parm"}
        if not parm.isAtDefault():
            return {"skip": True, "reason": "not_at_default_on_create"}
        template = parm.parmTemplate()
        # Template (parmTuple) order = the order compose.meaningful_params shows,
        # so the grader can reconstruct code-order top-2 with no live node.
        try:
            order = [t.name() for t in node.parmTuples()].index(parm.tuple().name())
        except Exception:
            order = -1
        parm.set(value)
        if parm.isAtDefault():
            return {"skip": True, "reason": "value_equals_default"}
        _cook(node)
        h_changed = _sop_hash(node) if ctx == "Sop" else _lop_hash(node)
        parm.revertToDefaults()
        _cook(node)
        h_default = _sop_hash(node) if ctx == "Sop" else _lop_hash(node)
        return {
            "context": ctx,
            "node_type": node.type().name(),
            "node_category": node.type().category().name(),
            "parm": parm_name,
            "parm_label": template.label(),
            "parm_type": template.type().name(),
            "parm_help": str(template.help() or ""),
            "template_order": order,
            "hash_changed": h_changed,
            "hash_default": h_default,
            "matters": h_changed != h_default,
        }
    except Exception as exc:  # noqa: BLE001 - a case that will not cook is skipped, never guessed
        return {"skip": True, "reason": "%s: %s" % (type(exc).__name__, str(exc)[:120])}
    finally:
        for victim in (to_destroy or ([node] if node is not None else [])):
            try:
                victim.destroy()
            except Exception:
                pass


def main():
    print("VERSION", hou.applicationVersionString())
    cases = []
    skipped = []
    seen_types = set()
    for ctx, type_name, feeder, parms in CANDIDATES:
        for parm_name, value in parms:
            res = measure_case(ctx, type_name, feeder, parm_name, value)
            if res.get("skip"):
                skipped.append({"context": ctx, "node_type": type_name,
                                "parm": parm_name, "reason": res["reason"]})
                print("SKIP", ctx, type_name, parm_name, "->", res["reason"])
                continue
            cases.append(res)
            seen_types.add((res["context"], res["node_type"]))
            print("CASE", res["context"], res["node_type"], res["parm"],
                  "matters=%s" % res["matters"])

    # Deterministic order independent of dict/set iteration.
    cases.sort(key=lambda c: (c["context"], c["node_type"], c["parm"]))
    n_true = sum(1 for c in cases if c["matters"])
    doc = {
        "schema": "identify_salience_key/v1",
        "producer": PRODUCER,
        "build": hou.applicationVersionString(),
        "hash_recipe": {
            "Sop": "sha256(pointcount|primcount|boundingBox + float32(P))",
            "Lop": "sha256(stage.Flatten().ExportToString())",
        },
        "summary": {
            "n_cases": len(cases),
            "n_node_types": len(seen_types),
            "n_matters_true": n_true,
            "n_matters_false": len(cases) - n_true,
        },
        "cases": cases,
        "skipped": sorted(skipped, key=lambda s: (s["context"], s["node_type"], s["parm"])),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Explicit LF so the on-disk file matches git's normalized blob on every
    # platform: a fresh checkout + hython re-run stays byte-identical (no CRLF trap).
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    print("WROTE", OUT, "cases=%d types=%d true=%d false=%d (producer: %s)" % (
        len(cases), len(seen_types), n_true, len(cases) - n_true, PRODUCER))

    if len(cases) < MIN_CASES or len(seen_types) < MIN_TYPES:
        print("FINDING: key below floor (need >= %d cases, >= %d types; got %d, %d)"
              % (MIN_CASES, MIN_TYPES, len(cases), len(seen_types)))
        return 1
    print("KEY_RESULT PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        print("KEY_RESULT ERROR")
        sys.exit(2)
