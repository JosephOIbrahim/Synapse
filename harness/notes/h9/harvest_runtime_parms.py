"""H9 producer 1 of 4 -- runtime parameter harvest, instantiation-free.

Emits harness/notes/h9/runtime_parms_22.0.368.json

WHY THIS EXISTS
    The LOP catalogue (h22_lop_catalog_live_22.0.368.json) carries no `parms` key.
    The COP catalogue does. Work item 4 of the H9 brief compares DOCUMENTED parameter
    names against the LIVE node's actual parms, so the LOP half has no ground truth in
    the tree and must be probed.

    The whole population is harvested, not just the 20 sampled types, so the quality
    floor can be scored against reality for every type and the 20-node cross-check is
    a sample of a measured population rather than the only measurement taken.

THE MULTIPARM BLIND SPOT -- read this before trusting any agreement figure
    `parmTemplateGroup().entriesWithoutFolders()` -- the call the committed COP
    catalogue uses -- returns the multiparm block's COUNT parm but NOT its children.
    On lop/attribwrangle the children `bindattrib#`, `bindattribtype#`, `bindparm#`
    are live, documented, and invisible to that call.

    Scoring documentation against that set alone manufactures three false
    "documented but not on the node" disagreements on one node. So this harvest walks
    the template tree recursively and records BOTH views:

      parms                    every leaf, recursive, multiparm children included
      parms_entries_no_folders exactly what entriesWithoutFolders() returns

    The second exists so the check below can fail. It is compared against the
    committed COP catalogue; if the two ever disagree, either the catalogue is stale
    or this harvest drifted, and the run stops.

    Note what that control does and does not prove: it proves METHOD EQUIVALENCE with
    the committed artifact, not method CORRECTNESS. Both share the multiparm blind
    spot. `parms` is the corrected view and has no committed counterpart to check
    against.

METHOD
    hou.nodeTypeCategories()['Lop'|'Cop'|'Cop2'] -> nodeTypes() -> parmTemplateGroup()
    No node is instantiated.

FAILURE CONDITIONS (Law 1 -- state them before writing the check)
    1. hou unimportable, or build != 22.0.368            -> SystemExit
    2. live type count != the committed catalogue's      -> SystemExit
    3. entriesWithoutFolders view != committed COP parms -> recorded as a
       control_failure in the artifact AND non-zero exit
    Condition 3 is true today only if something drifted; that is the point.

RUN
    "<HFS>/bin/hython3.13.exe" harness/notes/h9/harvest_runtime_parms.py
"""
import json
import os
import sys

import hou

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "runtime_parms_22.0.368.json")
COP_CATALOG = os.path.join(HERE, "..", "h22_cop_catalog_live_22.0.368.json")
LOP_CATALOG = os.path.join(HERE, "..", "h22_lop_catalog_live_22.0.368.json")

EXPECTED = {"Lop": 218, "Cop": 384, "Cop2": 169}


def harvest(cat_name):
    cats = hou.nodeTypeCategories()
    if cat_name not in cats:
        raise SystemExit("FAIL: node type category %r absent on this build" % cat_name)
    out, errors = {}, []
    for type_name, nt in cats[cat_name].nodeTypes().items():
        try:
            ptg = nt.parmTemplateGroup()
            leaves, multiparm, folder_labels, folder_names = [], [], [], []
            label_map = {}

            def walk(entries, in_multi=False):
                for e in entries:
                    if isinstance(e, hou.FolderParmTemplate):
                        folder_labels.append(e.label())
                        folder_names.append(e.name())
                        is_multi = in_multi or (
                            e.folderType() == hou.folderType.MultiparmBlock
                        )
                        walk(e.parmTemplates(), is_multi)
                    else:
                        leaves.append(e.name())
                        label_map.setdefault(e.label(), []).append(e.name())
                        if in_multi:
                            multiparm.append(e.name())

            walk(ptg.entries())
            # A MultiparmBlock folder IS itself a parameter -- it holds the instance
            # count, and `bindings` on lop/attribwrangle is exactly that. The recursive
            # walk classifies it as a folder and would drop it, so `parms` is taken as a
            # strict SUPERSET of both views. Neither view alone is complete: the walk
            # adds the children, entriesWithoutFolders adds the count parms.
            flat = set(p.name() for p in ptg.entriesWithoutFolders())
            for lbl_owner in ptg.entriesWithoutFolders():
                label_map.setdefault(lbl_owner.label(), []).append(lbl_owner.name())
            rec = {
                "parms": sorted(set(leaves) | flat),
                "parms_entries_no_folders": sorted(
                    set(p.name() for p in ptg.entriesWithoutFolders())
                ),
                "multiparm_children": sorted(set(multiparm)),
                "folder_labels": sorted(set(folder_labels)),
                "folder_names": sorted(set(folder_names)),
                "label_to_parms": {k: sorted(set(v)) for k, v in sorted(label_map.items())},
            }
        except Exception as exc:  # noqa: BLE001 - recorded, never swallowed (Law 3)
            errors.append({"type": type_name, "error": "%s: %s" % (type(exc).__name__, exc)})
            continue
        try:
            rec["deprecated"] = bool(nt.deprecated())
        except Exception:
            rec["deprecated"] = None
        try:
            rec["label"] = nt.description()
        except Exception:
            rec["label"] = None
        out[type_name] = rec
    return out, errors


def control_against_committed(payload):
    """Condition 3. Returns a list of failures; empty list is the healthy state."""
    failures = []
    with open(COP_CATALOG, encoding="utf-8") as fh:
        cop = json.load(fh)
    pairs = (("copNodeTypeCategory", "Cop"), ("cop2NodeTypeCategory", "Cop2"))
    for cat_key, mine in pairs:
        committed = cop["categories"][cat_key]["types"]
        got = payload["categories"][mine]["types"]
        for tname, rec in committed.items():
            a = set(rec.get("parms", []))
            b = set(got.get(tname, {}).get("parms_entries_no_folders", []))
            if a != b:
                failures.append(
                    {
                        "type": "%s/%s" % (mine, tname),
                        "in_catalogue_not_probe": sorted(a - b)[:8],
                        "in_probe_not_catalogue": sorted(b - a)[:8],
                    }
                )
    with open(LOP_CATALOG, encoding="utf-8") as fh:
        lop = json.load(fh)
    missing = set(lop["types"]) ^ set(payload["categories"]["Lop"]["types"])
    if missing:
        failures.append({"type": "Lop", "type_name_set_symmetric_difference": sorted(missing)[:20]})
    return failures


def main():
    build = hou.applicationVersionString()
    if build != "22.0.368":
        raise SystemExit("FAIL: build is %s, catalogues assert 22.0.368" % build)

    payload = {
        "schema": "runtime_parms/v1",
        "build": build,
        "python": sys.version.split()[0],
        "producer": "harness/notes/h9/harvest_runtime_parms.py",
        "method": "nodeType.parmTemplateGroup(), recursive walk -- no node instantiated",
        "tier": "VERIFIED-RUNTIME",
        "categories": {},
        "probe_errors": [],
    }

    for cat in ("Lop", "Cop", "Cop2"):
        types, errors = harvest(cat)
        if len(types) + len(errors) != EXPECTED[cat]:
            raise SystemExit(
                "FAIL: %s live count %d (+%d errored) != catalogue assertion %d"
                % (cat, len(types), len(errors), EXPECTED[cat])
            )
        payload["categories"][cat] = {"count": len(types), "types": types}
        payload["probe_errors"].extend(errors)

    failures = control_against_committed(payload)
    payload["control_vs_committed_catalogues"] = {
        "what_it_proves": "method equivalence with the committed artifacts, NOT correctness -- "
        "both sides share the multiparm blind spot",
        "failures": failures,
        "result": "PASS" if not failures else "FAIL",
    }

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True)
    print("WROTE", OUT)
    for cat in ("Lop", "Cop", "Cop2"):
        c = payload["categories"][cat]
        n = sum(len(v["parms"]) for v in c["types"].values())
        m = sum(len(v["multiparm_children"]) for v in c["types"].values())
        print("  %-5s %3d types, %6d parms (%d of them multiparm children)" % (cat, c["count"], n, m))
    print("  probe_errors:", len(payload["probe_errors"]))
    print("  control vs committed catalogues:", payload["control_vs_committed_catalogues"]["result"])
    if failures:
        print("  FAILURES:", json.dumps(failures[:3], indent=1))
        sys.exit(2)


main()
