"""D.1 (Mile 1) — cook-API confirmation probe. hython-only, ZERO synapse imports.

Spec: harness/notes/spec-D-diagnostic-truth.md §1. Every hou.* symbol on the D track's
critical path is UNVERIFIED until dir()-confirmed against the live build — dir() membership
is the hard gate (the same demotion that drove scout's false-phantom rate 0.667 -> 0).
Absent symbols auto-quarantine: the catalog probe (§2) and the D.5 handler may only use
`confirmed`. The deposit is check_cook_api_confirmed's OWN authority — it is NEVER spliced
into h21_symbol_table.json (that table's blake2b + dir()-membership invariant are untouchable).

Artifact contract (must match check_cook_api_confirmed byte-for-byte):
  {schema: "cook_api/v1", houdini_version, confirmed: [...], absent: [...], blake2b}
  blake2b = hashlib.blake2b(json.dumps({"confirmed":..., "absent":...}, sort_keys=True,
            ensure_ascii=False).encode("utf-8"), digest_size=16).hexdigest()

Write-iff-complete via .tmp + os.replace; rc 0 iff the artifact was written. Re-run per
build (H22: deposits verified_cook_api_22.x.y.json next to the 21 file — zero check edits).
"""
import hashlib
import json
import os
import sys

import hou  # hython interpreter — the live build IS the authority

# The spec §1 candidate set ("candidate MEANS candidate — the probe decides, not the spec"),
# plus removeEventCallback: registering a callback (D.5) without a confirmed deregistration
# path would leak into the artist's session — same critical path as addEventCallback.
#
# FIRST-RUN FINDING (2026-07-07, 21.0.671): the spec's spellings are H18-era PHANTOMS. The
# cook surface lives on hou.OpNode (the H19.5 Node split), and the event enum is lowercase
# hou.nodeEventType — hou.NodeEventType does not exist. Both spellings are probed: the live
# ones confirm; the spec's originals stay in `absent` — which IS their value, as the
# quarantine list that catches anyone emitting hou.Node.cookCount / hou.NodeEventType.*.
CANDIDATES = [
    # spec-spelled (H18-era — expected absent on 21.x, kept as quarantine authority)
    "hou.Node.cookCount",
    "hou.Node.needsToCook",
    "hou.Node.isTimeDependent",
    "hou.Node.cook",
    "hou.Node.infoTree",
    "hou.Node.addEventCallback",
    "hou.Node.removeEventCallback",
    "hou.NodeEventType.ParmTupleChanged",
    "hou.NodeEventType.InputRewired",
    # live-spelled (the H19.5+ class split: OpNode carries the cook surface)
    "hou.OpNode.cookCount",
    "hou.OpNode.needsToCook",
    "hou.OpNode.isTimeDependent",
    "hou.OpNode.cook",
    "hou.OpNode.infoTree",
    "hou.OpNode.addEventCallback",
    "hou.OpNode.removeEventCallback",
    "hou.nodeEventType.ParmTupleChanged",
    "hou.nodeEventType.InputRewired",
    # spelling-stable across the split
    "hou.expressionGlobals",
    "hou.Parm.expressionLanguage",
    "hou.Parm.evalAsString",
]


def _exists(dotted):
    """dir()-membership for a dotted hou symbol — resolve the parent by attribute walk,
    then require the leaf in dir(parent). Never getattr the leaf (properties could execute)."""
    parts = dotted.split(".")
    assert parts[0] == "hou"
    obj = hou
    for part in parts[1:-1]:
        if part not in dir(obj):
            return False
        obj = getattr(obj, part)
    return parts[-1] in dir(obj)


def main():
    out = None
    args = sys.argv[1:]
    if "--out" in args:
        out = args[args.index("--out") + 1]
    build = hou.applicationVersionString()
    if out is None:
        out = os.path.join("harness", "notes", f"verified_cook_api_{build}.json")

    confirmed, absent = [], []
    for sym in CANDIDATES:
        try:
            (confirmed if _exists(sym) else absent).append(sym)
        except Exception as e:  # a symbol whose PARENT walk explodes is not confirmed
            print(f"probe-gap {sym}: {type(e).__name__}: {e}")
            absent.append(sym)
    confirmed.sort()
    absent.sort()

    doc = {
        "schema": "cook_api/v1",
        "houdini_version": build,
        "confirmed": confirmed,
        "absent": absent,
        "blake2b": hashlib.blake2b(
            json.dumps({"confirmed": confirmed, "absent": absent},
                       sort_keys=True, ensure_ascii=False).encode("utf-8"),
            digest_size=16).hexdigest(),
    }
    tmp = out + ".tmp"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, out)
    print(f"COOK_API_PROBE ok build={build} confirmed={len(confirmed)} absent={len(absent)} -> {out}")
    for s in absent:
        print(f"  QUARANTINED (absent as spelled): {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
