"""Positive control for the local H22 help cache as a documentation oracle.

Test it against two answers already established by live probe:
  1. hou.RopNode has NO cancel/abort/interrupt/stop  (H3a-F1, R58)
  2. hou.TopNode.dirtyAllTasks IS deprecated          (H5-F3, inspect.signature)

If the cache reproduces both, it is usable as the documented-status axis that
H5 could not reach - the pinned /docs/houdini22.0/ tree is ROBOTS_DISALLOWED and
the unpinned tree serves 21.0. This cache ships with the 22.0.368 install, so it
is version-pinned by construction.

If it fails either, it is not an oracle and must not be treated as one.
"""
import json, os, re

CACHE = r"C:\Users\User\OneDrive\Documents\houdini22.0\config\Help\cache"
HOM = os.path.join(CACHE, "hom", "hou")


def load(name):
    p = os.path.join(HOM, name + ".json")
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8", errors="replace"))


def flatten(o, out):
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, dict):
        for v in o.values():
            flatten(v, out)
    elif isinstance(o, list):
        for v in o:
            flatten(v, out)
    return out


print("=" * 66)
print("CONTROL 1  hou.RopNode - expect NO cancel verb")
print("=" * 66)
d = load("RopNode")
if d is None:
    print("  RopNode.json ABSENT - cache does not cover it")
else:
    text = " ".join(flatten(d, []))
    print("  size:", len(text), "chars")
    methods = sorted(set(re.findall(r"\b([a-z][A-Za-z0-9]{3,})\s*\(", text)))
    print("  method-shaped tokens:", len(methods))
    hits = [m for m in methods if re.search(r"cancel|abort|interrupt|stop|kill|terminate", m, re.I)]
    print("  CANCEL-LIKE:", hits if hits else "NONE  <- matches live probe")
    print("  has render():", "render(" in text)

print()
print("=" * 66)
print("CONTROL 2  hou.TopNode.dirtyAllTasks - expect DEPRECATED")
print("=" * 66)
d = load("TopNode")
if d is None:
    print("  TopNode.json ABSENT")
else:
    text = " ".join(flatten(d, []))
    print("  size:", len(text), "chars")
    i = text.lower().find("dirtyalltasks")
    if i < 0:
        print("  dirtyAllTasks NOT MENTIONED  <- cache disagrees with runtime")
    else:
        window = text[max(0, i - 120):i + 320]
        print("  found at char", i)
        dep = "deprecat" in window.lower()
        print("  DEPRECATION NOTED NEARBY:", dep, "<- matches runtime" if dep else "<- MISS")
        print("  ...", " ".join(window.split())[:280])

print()
print("=" * 66)
print("COVERAGE")
print("=" * 66)
files = [f for f in os.listdir(HOM) if f.endswith(".json")]
print("  hom/hou symbol files:", len(files))
dep_files = 0
for f in files:
    try:
        t = open(os.path.join(HOM, f), encoding="utf-8", errors="replace").read()
        if "deprecat" in t.lower():
            dep_files += 1
    except Exception:
        pass
print("  mentioning deprecation:", dep_files)
