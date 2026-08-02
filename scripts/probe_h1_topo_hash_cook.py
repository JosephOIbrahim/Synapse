"""H1 probe (R302 rank 7) — does the R1 topo-hash's per-node read COOK?

QUESTION (harness/latency/REGISTRY.json H1, C4 caveat): the live-envelope
scene hash reads node.cookCount() + geometry intrinsics per mutating op
(shared/bridge.py:_compute_scene_hash_impl, the ``cook:``/``pts:``/``bounds:``
components). On a DIRTY node — the state the live path's scene_hash_after
capture always finds — is that read (a) a pure read, (b) a FORCED COOK the
hash itself pays for (removable work), or (c) a re-timing of a cook that
would have happened anyway? Headless there is no viewport to cook the node,
so a forced cook here is work the hash ADDS on the live path.

METHOD. Build a 1M-point grid, cook it, dirty it with a parm change, then
time each component of the bridge's read separately and watch cookCount
BEFORE/AFTER each step:

  step 1  cookCount() read on the dirty node      -> does IT cook?
  step 2  node.geometry() handle acquisition      -> does IT cook?
  step 3  intrinsicValue('pointcount'+'bounds')   -> does IT cook?
  step 4  repeat step 2+3 on the now-clean node   -> the cached-read floor

RUN (hython, any H22 build — record the build with the numbers):
  & "C:/Program Files/Side Effects Software/Houdini 22.0.397/bin/hython.exe" \
      scripts/probe_h1_topo_hash_cook.py

Zero SYNAPSE imports — this isolates the vendor behavior the bridge sits on.
"""
import time

import hou

geo = hou.node("/obj").createNode("geo", "h1_probe")
g = geo.createNode("grid")
g.parm("rows").set(1000)
g.parm("cols").set(1000)
g.cook(force=True)
g.parm("rows").set(1001)  # dirty it — the post-mutation state the hash reads

print("build:", hou.applicationVersionString())

cc0 = g.cookCount()
t0 = time.perf_counter()
cc1 = g.cookCount()
t1 = time.perf_counter()
print(f"step1 cookCount read on DIRTY node: {(t1-t0)*1000:.3f} ms | "
      f"cookCount {cc0} -> {g.cookCount()} (cooked: {g.cookCount() != cc0})")

t2 = time.perf_counter()
geo_h = g.geometry()
t3 = time.perf_counter()
cc2 = g.cookCount()
print(f"step2 geometry() on DIRTY node:     {(t3-t2)*1000:.3f} ms | "
      f"cookCount {cc1} -> {cc2} (cooked: {cc2 != cc1})")

t4 = time.perf_counter()
pts = geo_h.intrinsicValue("pointcount")
bounds = geo_h.intrinsicValue("bounds")
t5 = time.perf_counter()
cc3 = g.cookCount()
print(f"step3 intrinsics on that handle:    {(t5-t4)*1000:.3f} ms | "
      f"cookCount {cc2} -> {cc3} (cooked: {cc3 != cc2}) | pts={pts}")

t6 = time.perf_counter()
geo_h2 = g.geometry()
pts2 = geo_h2.intrinsicValue("pointcount")
b2 = geo_h2.intrinsicValue("bounds")
t7 = time.perf_counter()
cc4 = g.cookCount()
print(f"step4 repeat read on CLEAN node:    {(t7-t6)*1000:.3f} ms | "
      f"cookCount {cc3} -> {cc4} (cooked: {cc4 != cc3})")
