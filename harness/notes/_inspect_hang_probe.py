"""Is node.errors()/warnings() the thing that makes inspect_scene never return?

S1-F2, VERIFIED-RUNTIME: synapse_inspect_scene ran the full 1800s MCP idle
timeout on a 9-node EMPTY scene at max_depth=1, twice, while synapse_ping
answered instantly in the same session. Concurrency refuted.

S1 carried the mechanism as a candidate and did not test it:
    _node_issues calls node.errors() (introspection.py:184), which forces cooks.

This times each stage separately so the answer is a measurement, not a guess.
"""
import time, sys
import hou

SCENE = (r"C:\Program Files\Side Effects Software\Houdini 22.0.368"
         r"\houdini\help\files\karma_user_guide\karma_user_guide.hip")

def timed(label, fn, *a):
    t = time.time()
    try:
        r = fn(*a)
        dt = time.time() - t
        n = len(r) if hasattr(r, "__len__") else "-"
        print("  %-34s %7.2fs   -> %s" % (label, dt, n), flush=True)
        return dt
    except Exception as e:
        print("  %-34s RAISED %s: %s" % (label, type(e).__name__, str(e)[:60]), flush=True)
        return -1

print("=== EMPTY SCENE ===", flush=True)
stage = hou.node("/stage")
kids = list(stage.children()) if stage else []
print("  /stage children:", len(kids), flush=True)

from synapse.server.introspection import _node_basic, _node_issues, _modified_parms

for n in kids[:3]:
    print("  node:", n.name(), n.type().name(), flush=True)
    timed("    warnings()", lambda x=n: list(x.warnings()))
    timed("    errors()", lambda x=n: list(x.errors()))
    timed("    _node_issues()", lambda x=n: _node_issues(x))

print(flush=True)
print("=== LOADING karma_user_guide.hip ===", flush=True)
t = time.time()
hou.hipFile.load(SCENE, suppress_save_prompt=True, ignore_load_warnings=True)
print("  loaded in %.1fs" % (time.time() - t), flush=True)

stage = hou.node("/stage")
kids = list(stage.children())
print("  /stage children:", len(kids), flush=True)

worst = (0, None)
total = 0.0
for n in kids[:12]:
    t = time.time()
    try:
        _node_issues(n)
    except Exception:
        pass
    dt = time.time() - t
    total += dt
    if dt > worst[0]:
        worst = (dt, n.name())
    if dt > 1.0:
        print("  SLOW  %-40s %6.2fs" % (n.name()[:40], dt), flush=True)

print("  12 nodes, _node_issues total: %.2fs   worst: %.2fs on %s"
      % (total, worst[0], worst[1]), flush=True)
print("RESULT: measured, not inferred.", flush=True)
