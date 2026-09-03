"""BP4-CRUX / SPATIAL T-E -- acceptance row 3 with the crux own stages.

Runs the three tools, with NO change to the package, on three stages the builder
test does not use as its D3.4 evidence:
  S1  a LOP `sphere` stage           -- native UsdGeomSphere, no Mesh anywhere
  S2  a sopimport of box+grid SOPs   -- real Mesh geometry, a floor and a box
  S3  fixtures/solaris.basic.json    -- the same stage the D3.4 test builds
Records the status and payload of each of the nine calls.
"""
import json, os, sys, time

SCR = os.environ["CRUX_SCR"]
sys.path.insert(0, SCR + "/python")
sys.path.insert(1, SCR)

import hou
from pxr import Usd, UsdGeom

import synapse.spatial as SP
from synapse.spatial import (synapse_spatial_describe, synapse_spatial_classify,
                             synapse_spatial_frustum)

assert SP.__file__.replace("\\", "/").lower().startswith(SCR.lower()), SP.__file__
OUT = {"binding": SP.__file__, "stages": {}}


def run_three(stage, label, eye=(0.0, 1.0, -5.0)):
    res = {}
    for name, fn in (("describe", lambda: synapse_spatial_describe(stage)),
                     ("classify", lambda: synapse_spatial_classify(stage)),
                     ("frustum", lambda: synapse_spatial_frustum(stage, eye=eye))):
        t0 = time.perf_counter()
        try:
            r = fn()
            err = None
        except Exception as exc:            # a raise is the failure mode we hunt
            r, err = None, "%s: %s" % (type(exc).__name__, exc)
        wall = time.perf_counter() - t0
        res[name] = {"status": (r or {}).get("status"), "wall_seconds": wall,
                     "raised": err, "payload": r}
    OUT["stages"][label] = res
    print("==== %s ====" % label)
    for k, v in res.items():
        print(" ", k, "->", v["status"], "raised=%s" % v["raised"],
              "%.4fs" % v["wall_seconds"])
    return res


# ---- S1: a LOP sphere stage (no Mesh prim at all) ---------------------------
stage_ctx = hou.node("/stage")
sph = stage_ctx.createNode("sphere", "crux_s1_sphere")
sph.cook(force=True)
s1 = sph.stage()
OUT["stages_meta"] = {"S1_prims": [(p.GetPath().pathString, p.GetTypeName())
                                   for p in s1.Traverse()]}
run_three(s1, "S1_lop_sphere", eye=(0.0, 0.0, -10.0))

# ---- S2: sopimport of a box + a grid (real Mesh, floor + walls) -------------
geo = hou.node("/obj").createNode("geo", "crux_s2")
box = geo.createNode("box", "b")
box.parm("scale").set(2.0)
grid = geo.createNode("grid", "g")
for pn, pv in (("sizex", 10.0), ("sizey", 10.0), ("rows", 4), ("cols", 4)):
    p = grid.parm(pn)
    if p is not None:
        p.set(pv)
mrg = geo.createNode("merge", "m")
mrg.setInput(0, box)
mrg.setInput(1, grid)
mrg.cook(force=True)
si = stage_ctx.createNode("sopimport", "crux_s2_import")
si.parm("soppath").set(mrg.path())
si.parm("primpath").set("/crux_box_grid")
si.cook(force=True)
s2 = si.stage()
OUT["stages_meta"]["S2_prims"] = [(p.GetPath().pathString, p.GetTypeName())
                                  for p in s2.Traverse()]
run_three(s2, "S2_sopimport_box_grid", eye=(0.0, 1.0, -12.0))

# ---- S3: fixtures/solaris.basic.json, built the way the D3.4 test does ------
fx = os.path.join(SCR, "fixtures", "solaris.basic.json")
if os.path.exists(fx):
    spec = json.loads(open(fx, encoding="utf-8").read())
    made = {}
    for nd in spec["nodes"]:
        n = stage_ctx.createNode(nd["type"], "crux_" + nd["name"])
        for pn, pv in (nd.get("parms") or {}).items():
            p = n.parm(pn)
            if p is not None:
                p.set(pv)
        made[nd["name"]] = n
    for dst, idx, src in spec.get("wires", []):
        if dst in made and src in made:
            made[dst].setInput(idx, made[src])
    disp = made[spec["display"]]
    disp.cook(force=True)
    s3 = disp.stage()
    OUT["stages_meta"]["S3_prims"] = [(p.GetPath().pathString, p.GetTypeName())
                                      for p in s3.Traverse()]
    OUT["stages_meta"]["S3_spec_nodes"] = [nd["type"] for nd in spec["nodes"]]
    run_three(s3, "S3_solaris_basic")
else:
    OUT["stages"]["S3_solaris_basic"] = {"error": "fixture missing: " + fx}

# ---- did any tool write anything? confirm read-only on a live stage ---------
# snapshot prim paths before/after each stage was queried is implicit above;
# here we re-traverse S2 and compare against the pre-query snapshot.
after = [(p.GetPath().pathString, p.GetTypeName()) for p in s2.Traverse()]
OUT["readonly_check_S2"] = {
    "prims_before_query": OUT["stages_meta"]["S2_prims"],
    "prims_after_query": after,
    "unchanged": after == OUT["stages_meta"]["S2_prims"],
}
print("READONLY S2 unchanged:", OUT["readonly_check_S2"]["unchanged"])

with open(os.environ["CRUX_OUT2"], "w", encoding="utf-8") as fh:
    json.dump(OUT, fh, indent=2, default=str)
print("WROTE", os.environ["CRUX_OUT2"])
