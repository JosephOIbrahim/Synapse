"""H9 producer 5 -- instantiated parameter names for every live type.

Emits harness/notes/h9/instantiated_parms_22.0.368.json

WHY THIS EXISTS (audit finding H9-CC-6)
    The template view and the instantiated view of a node's parameters are DIFFERENT
    SETS, and using only the template manufactures false "the documentation is wrong"
    findings:

      cop/bend documents '#id: bottomleftx, bottomlefty'. Those are real, live, and
      evaluable on an instantiated node. The parmTemplateGroup only carries the TUPLE
      name 'bottomleft', so a template-only check calls both documented ids phantom.

    Scoring documentation against the template alone inflated the leg's
    "385 documented ids are wrong" figure by roughly a third.

    The reverse asymmetry also holds, which is why BOTH views are kept: multiparm
    children exist in the template as 'bindattrib#' and do NOT exist on a freshly
    instantiated node, because no instances have been added yet. Neither view is
    complete; the union is the honest ground truth for "does this name exist".

METHOD
    One scratch network per category; create the node, read node.parms() and
    node.parmTuples(), destroy it. Every failure is recorded per type, never swallowed.

FAILURE CONDITION (Law 1)
    Exits non-zero if more than 5% of a category fails to instantiate -- that would
    mean the scratch network is wrong rather than the nodes being uncreatable, and the
    union would be silently missing a whole surface.

RUN
    "<HFS>/bin/hython3.13.exe" harness/notes/h9/harvest_instantiated_parms.py
"""
import json
import os
import sys

import hou

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "instantiated_parms_22.0.368.json")

HOLDERS = {"Lop": ("/stage", "lopnet"), "Cop": ("/img", "copnet"), "Cop2": ("/img", "img")}


def holder_for(category):
    root_path, kind = HOLDERS[category]
    root = hou.node(root_path)
    if root is None:
        raise SystemExit("FAIL: %s absent" % root_path)
    name = "h9_inst_%s" % category.lower()
    node = root.node(name)
    if node is None:
        node = root.createNode(kind, name)
    return node


def main():
    build = hou.applicationVersionString()
    if build != "22.0.368":
        raise SystemExit("FAIL: build is %s" % build)

    payload = {
        "schema": "instantiated_parms/v1",
        "build": build,
        "producer": "harness/notes/h9/harvest_instantiated_parms.py",
        "tier": "VERIFIED-RUNTIME",
        "method": "createNode in a scratch network, read node.parms() + node.parmTuples(), destroy",
        "why": "the template view and the instantiated view are different sets; see H9-CC-6",
        "categories": {},
    }

    cats = hou.nodeTypeCategories()
    for category in ("Lop", "Cop", "Cop2"):
        holder = holder_for(category)
        types, errors = {}, []
        names = sorted(cats[category].nodeTypes().keys())
        for tname in names:
            try:
                n = holder.createNode(tname)
            except Exception as exc:  # noqa: BLE001 -- recorded, never swallowed
                errors.append({"type": tname, "error": "%s: %s" % (type(exc).__name__, exc)})
                continue
            try:
                types[tname] = {
                    "parms": sorted({p.name() for p in n.parms()}),
                    "parm_tuples": sorted({t.name() for t in n.parmTuples()}),
                }
            except Exception as exc:  # noqa: BLE001
                errors.append({"type": tname, "error": "read: %s" % exc})
            finally:
                try:
                    n.destroy()
                except Exception:
                    pass
        fail_pct = 100.0 * len(errors) / max(1, len(names))
        payload["categories"][category] = {
            "count": len(types),
            "attempted": len(names),
            "failed": len(errors),
            "failed_pct": round(fail_pct, 1),
            "errors": errors,
            "types": types,
        }
        print("  %-5s %3d/%3d instantiated, %d failed (%.1f%%)"
              % (category, len(types), len(names), len(errors), fail_pct))
        if fail_pct > 5.0:
            print("  FAIL: %s exceeded the 5%% instantiation-failure ceiling" % category)

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True)
    print("WROTE", OUT)

    worst = max(c["failed_pct"] for c in payload["categories"].values())
    if worst > 5.0:
        sys.exit(2)


main()
