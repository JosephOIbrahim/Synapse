"""Does the C1-F3 segfault still happen? The decisive test.

C1-F3: houdini_network_explain SEGFAULTS hython 22.0.368 (rc=139) on
karma_user_guide.hip - reproducibly on both runs - dying inside
_get_non_default_params while evaluating matspecpath1 / bindname1 parms on
Solaris material-assignment LOPs.

A try/except cannot catch a segfault. The fix avoids the evaluation: string
parms now read rawValue() instead of eval().

This script exercises the SHIPPED function on the SAME scene. If it exits 0 and
prints a summary, the crash is gone. If the process dies, the exit code says so
and no output appears - which is itself the answer.
"""
import sys, time

SCENE = (r"C:\Program Files\Side Effects Software\Houdini 22.0.368"
         r"\houdini\help\files\karma_user_guide\karma_user_guide.hip")

import hou

print("loading:", SCENE.rsplit("\\", 1)[-1], flush=True)
t0 = time.time()
hou.hipFile.load(SCENE, suppress_save_prompt=True, ignore_load_warnings=True)
print("loaded in %.1fs" % (time.time() - t0), flush=True)

stage = hou.node("/stage")
kids = stage.children() if stage else ()
print("/stage children:", len(kids), flush=True)

# The exact function that died. Drive it over the material-assignment LOPs that
# C1 named, then over everything, and report rather than assume.
from synapse.server.handlers_node import _get_non_default_params

targets = [n for n in kids if "assign" in n.type().name().lower()
           or "material" in n.type().name().lower()]
print("material-ish LOPs:", len(targets), flush=True)

done = 0
for n in targets:
    p, e = _get_non_default_params(n, include_expressions=True)
    done += 1
print("SURVIVED the named crash set: %d nodes" % done, flush=True)

t1 = time.time()
total = 0
for n in kids:
    p, e = _get_non_default_params(n, include_expressions=False)
    total += len(p)
print("SURVIVED all /stage children: %d nodes, %d non-default parms, %.1fs"
      % (len(kids), total, time.time() - t1), flush=True)

print("RESULT: no segfault.", flush=True)
