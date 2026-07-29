"""V1 / PROBE A — MUTATION TEST. Law 1: a check that has never been shown to
fail is a decoration.

Two mutations, each in its own process so the real ``hou`` is never evicted and
re-executed (the SWIG half-build trap, RES-F1 / R51).

  M1  no hou at all              -> every control UNVERIFIABLE, controls_ok False
  M2  a fake hou that resolves
      EVERY attribute            -> negative controls resolve, negative_ok False

If either mutation still reports controls_ok True, probe_a_surfaces.py is a
decoration and none of its verdicts may be cited.

Run:  hython3.13.exe probe_a_mutation.py <probe_path> <out.json>
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import os

PROBE = sys.argv[1]
OUT = sys.argv[2]
HYTHON = sys.executable

M2_PREAMBLE = r'''
import sys, types, runpy

class _YesToEverything(types.ModuleType):
    """Resolves any attribute, at any depth. The shape of a broken resolver."""
    def __getattr__(self, name):
        child = _YesToEverything("hou." + name)
        setattr(self, name, child)
        return child

sys.modules["hou"] = _YesToEverything("hou")
sys.argv = ["probe", sys.argv[1]]
runpy.run_path(sys.argv0_probe, run_name="__main__")
'''


def run(argv, label):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=600)
        return {"label": label, "returncode": p.returncode,
                "stdout": p.stdout[-2000:], "stderr": p.stderr[-2000:]}
    except Exception as exc:
        return {"label": label, "returncode": None, "error": repr(exc)}


tmp = tempfile.mkdtemp(prefix="v1_mut_")
results = {"probe_under_test": PROBE, "mutations": []}

# ---------------------------------------------------------------- M1: no hou
m1_out = os.path.join(tmp, "m1.json")
# A python that certainly has no hou: the same interpreter, but with hou
# pre-blocked in sys.modules (None makes `import hou` raise ImportError without
# ever executing hou.py -- the safe form, per RES-F1).
m1_driver = os.path.join(tmp, "m1_driver.py")
with open(m1_driver, "w", encoding="utf-8") as fh:
    fh.write(
        "import sys, runpy\n"
        "sys.modules['hou'] = None\n"
        f"sys.argv = ['probe', {m1_out!r}]\n"
        f"runpy.run_path({PROBE!r}, run_name='__main__')\n"
    )
m1 = run([HYTHON, m1_driver], "M1 no-hou")
if os.path.exists(m1_out):
    with open(m1_out, encoding="utf-8") as fh:
        d = json.load(fh)
    m1["controls_ok"] = d["controls"]["controls_ok"]
    m1["positive_ok"] = d["controls"]["positive_ok"]
    m1["hou_imported"] = d["hou_imported"]
    m1["artifact"] = m1_out
m1["expected"] = "controls_ok False (positive controls cannot resolve)"
m1["passed"] = m1.get("controls_ok") is False
results["mutations"].append(m1)

# ------------------------------------------------- M2: a hou that says yes to all
m2_out = os.path.join(tmp, "m2.json")
m2_driver = os.path.join(tmp, "m2_driver.py")
with open(m2_driver, "w", encoding="utf-8") as fh:
    fh.write(
        "import sys, types, runpy\n"
        "class Yes(types.ModuleType):\n"
        "    # Resolves ANY attribute at ANY depth, and is callable, so it models a\n"
        "    # resolver that answers yes to everything rather than one that merely\n"
        "    # crashes. A probe must catch this, not die on it.\n"
        "    def __getattr__(self, name):\n"
        "        c = Yes('hou.' + name)\n"
        "        setattr(self, name, c)\n"
        "        return c\n"
        "    def __call__(self, *a, **k):\n"
        "        return Yes('hou.call')\n"
        "sys.modules['hou'] = Yes('hou')\n"
        f"sys.argv = ['probe', {m2_out!r}]\n"
        f"runpy.run_path({PROBE!r}, run_name='__main__')\n"
    )
m2 = run([HYTHON, m2_driver], "M2 resolver-says-yes")
if os.path.exists(m2_out):
    with open(m2_out, encoding="utf-8") as fh:
        d = json.load(fh)
    m2["controls_ok"] = d["controls"]["controls_ok"]
    m2["negative_ok"] = d["controls"]["negative_ok"]
    m2["artifact"] = m2_out
m2["expected"] = "negative_ok False (a resolver that answers yes to everything must be caught)"
m2["passed"] = m2.get("negative_ok") is False
results["mutations"].append(m2)

results["verdict"] = (
    "PROBE CAN FAIL IN BOTH DIRECTIONS"
    if all(m.get("passed") for m in results["mutations"])
    else "MUTATION TEST FAILED -- probe_a_surfaces.py verdicts are NOT citable"
)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(results, fh, indent=1)

for m in results["mutations"]:
    print(f"{m['label']}: passed={m.get('passed')} controls_ok={m.get('controls_ok')} "
          f"negative_ok={m.get('negative_ok')} rc={m.get('returncode')}")
print(results["verdict"])
sys.exit(0 if all(m.get("passed") for m in results["mutations"]) else 1)
