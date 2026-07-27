"""V1 / Q1b — EXHAUSTIVE capture-verb sweep of the whole hou namespace.

Why this exists: R73. H3a verified the NARROW claim ("hou.RopNode has no cancel
method") and then wrote a BROAD one ("Houdini exposes no way to cancel a
render"). rkill had been there the whole time. The narrow probe was correct and
the sentence it licensed was not.

So before V1 says "there is no viewport-grab API", it walks every class in the
hou namespace and every member of every class, and greps the COMPLETE surface
for capture-adjacent tokens. A broad claim needs a broad control.

Run:  hython3.13.exe harness/notes/v1_capture_sweep.py
Emits: harness/notes/v1_q1_sweep.json
"""
from __future__ import annotations

import json
import os
import re
import sys

import hou

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "v1_q1_sweep.json")

# Tokens that would name a pixels-out-of-Houdini verb, if one existed.
TOKENS = [
    "flipbook", "screenshot", "snapshot", "grab", "capture",
    "saveimage", "savefile", "saveview", "writeimage", "toimage",
    "pixel", "buffer", "raster", "framebuffer",
    "render", "denois", "aov", "rendervar", "cryptomatte",
    "exr", "mplay", "imagefile", "canvas",
]
TOKEN_RE = re.compile("|".join(TOKENS), re.IGNORECASE)


def main() -> int:
    top = sorted(dir(hou))
    classes = {}
    module_level_hits = []

    for name in top:
        if name.startswith("__"):
            continue
        if TOKEN_RE.search(name):
            try:
                obj = getattr(hou, name)
                module_level_hits.append({"name": f"hou.{name}", "repr": repr(obj)[:120]})
            except Exception as exc:  # noqa: BLE001
                module_level_hits.append({"name": f"hou.{name}", "repr": f"<{exc}>"})

    # Walk every CLASS in hou and grep its complete member list.
    for name in top:
        if name.startswith("__"):
            continue
        try:
            obj = getattr(hou, name)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(obj, type):
            continue
        try:
            members = sorted(dir(obj))
        except Exception:  # noqa: BLE001
            continue
        hits = [m for m in members if not m.startswith("__") and TOKEN_RE.search(m)]
        if hits:
            classes[f"hou.{name}"] = {"member_count": len(members), "hits": hits}

    report = {
        "schema": "v1-q1-sweep/1",
        "build": hou.applicationVersionString(),
        "license": str(hou.licenseCategory()),
        "tokens": TOKENS,
        "hou_top_level_names": len(top),
        "hou_classes_walked": sum(
            1 for n in top
            if not n.startswith("__") and isinstance(getattr(hou, n, None), type)
        ),
        "module_level_hits": module_level_hits,
        "class_hits": classes,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"BUILD {report['build']}   top-level names={report['hou_top_level_names']}   "
          f"classes walked={report['hou_classes_walked']}")
    print("\n--- module-level hits ---")
    for h in module_level_hits:
        print(f"  {h['name']}")
    print("\n--- class member hits ---")
    for cls, e in sorted(classes.items()):
        print(f"  {cls} ({e['member_count']} members): {e['hits']}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
