"""Scout the browsing cache for the axis hom.zip does NOT cover: NODE types.

I dismissed this cache after testing it against hou.RopNode and hou.TopNode -
both absent, 101 HOM symbols, conclusion "browsing cache, not an oracle". That
conclusion is correct FOR THE HOM AXIS and says nothing about node docs.

H5's census covers two different kinds of thing:
  - hou.* symbols          -> hom.zip is authoritative
  - node type literals     -> hom.zip has NOTHING on these

karmarenderproperties is a NODE TYPE. It is the headline DECAY_CLOCK symbol and
hom.zip cannot adjudicate it at all.

H5-F2 found node-type deprecation has TWO independent expressions that DISAGREE.
So the question here is not "is this an oracle" but "which expression is this,
and does it agree with the other one".
"""
import json, os, re

CACHE = r"C:\Users\User\OneDrive\Documents\houdini22.0\config\Help\cache"

def walk():
    for root, _, files in os.walk(CACHE):
        for f in files:
            if f.endswith(".json"):
                yield os.path.join(root, f)

files = list(walk())
print("cache files:", len(files))

# what areas are covered, by top-level dir
areas = {}
for p in files:
    rel = os.path.relpath(p, CACHE)
    top = rel.split(os.sep)[0]
    areas[top] = areas.get(top, 0) + 1
print("areas:", dict(sorted(areas.items(), key=lambda x: -x[1])[:12]))
print()

# THE decisive question: are LOP node docs in here, and is karmarenderproperties?
print("=" * 66)
print("NODE-TYPE COVERAGE  (the axis hom.zip cannot serve)")
print("=" * 66)
nodes = [p for p in files if os.sep + "nodes" + os.sep in p.lower()]
print("  files under a nodes/ path:", len(nodes))
lops = [p for p in nodes if os.sep + "lop" + os.sep in p.lower()]
print("  LOP node docs:", len(lops))
if lops:
    print("  sample:", [os.path.basename(p) for p in lops[:8]])

print()
for target in ("karmarenderproperties", "karma"):
    hit = [p for p in files if os.path.splitext(os.path.basename(p))[0].lower() == target]
    print(f"  '{target}' page present:", bool(hit), hit[0].replace(CACHE, "") if hit else "")

print()
print("=" * 66)
print("DEPRECATION SIGNAL IN NODE DOCS")
print("=" * 66)
dep_nodes = []
for p in nodes:
    try:
        t = open(p, encoding="utf-8", errors="replace").read()
        if "deprecat" in t.lower():
            dep_nodes.append(os.path.relpath(p, CACHE))
    except Exception:
        pass
print("  node docs mentioning deprecation:", len(dep_nodes))
for d in dep_nodes[:10]:
    print("   -", d)
