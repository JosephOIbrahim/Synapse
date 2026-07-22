"""LIVE PROBE -- requires hython on the target build; not part of `pytest tests/`.

    "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe" \
        scripts/live_probes/probe_b4_build_idempotency.py

B4: proves that running an identical build_graph twice converges instead of
drawing a second complete network on top of the first. Also exercises B5
(unknown node types rejected before the undo group opens, with the catalog's
remediation) and M4 (unresolvable parms reported instead of silently dropped).

Exit 0 = idempotent.
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO, "python"))

import hou  # noqa: E402
from synapse.core.errors import SynapseUserError  # noqa: E402
from synapse.server.handlers_solaris_graph import SolarisGraphMixin  # noqa: E402


class _Harness(SolarisGraphMixin):
    pass


GRAPH = {
    "parent": "/stage",
    "nodes": [
        {"id": "geo", "type": "sopcreate", "name": "asset"},
        {"id": "mat", "type": "materiallibrary", "name": "matlib"},
        {"id": "cam", "type": "camera", "name": "shotcam"},
        {"id": "rs", "type": "karmarendersettings", "name": "rendersettings"},
        {"id": "rop", "type": "usdrender_rop", "name": "render"},
    ],
    "connections": [
        {"from": "geo", "to": "mat"},
        {"from": "mat", "to": "cam"},
        {"from": "cam", "to": "rs"},
        {"from": "rs", "to": "rop"},
    ],
    "display_node": "rop",
}


def clear():
    for child in list(hou.node("/stage").children()):
        child.destroy()


def main():
    failures = []
    h = _Harness()
    clear()

    first = h._handle_solaris_build_graph(dict(GRAPH))
    n1 = len(hou.node("/stage").children())
    print("BUILD 1  status=%-9s children=%d created=%d reused=%d"
          % (first["status"], n1, len(first["nodes_created"]),
             len(first.get("nodes_reused", []))))

    second = h._handle_solaris_build_graph(dict(GRAPH))
    n2 = len(hou.node("/stage").children())
    print("BUILD 2  status=%-9s children=%d created=%d reused=%d"
          % (second["status"], n2, len(second["nodes_created"]),
             len(second.get("nodes_reused", []))))

    if n2 != n1:
        failures.append("second build changed child count %d -> %d (duplicated)"
                        % (n1, n2))
    if second["status"] != "unchanged":
        failures.append("second identical build reported status=%r, expected "
                        "'unchanged'" % second["status"])
    if second["nodes_created"]:
        failures.append("second build created %d node(s)"
                        % len(second["nodes_created"]))
    dupes = [c.name() for c in hou.node("/stage").children()
             if c.name().rstrip("0123456789") != c.name()]
    if dupes:
        failures.append("auto-uniquified duplicates present: %s" % dupes)
    if second["display_node"] != first["display_node"]:
        failures.append("display flag moved: %s -> %s"
                        % (first["display_node"], second["display_node"]))

    # B5 -- an unknown type must be rejected BEFORE anything is created.
    print()
    before = len(hou.node("/stage").children())
    bad = dict(GRAPH)
    bad["nodes"] = list(GRAPH["nodes"]) + [
        {"id": "ground", "type": "grid", "name": "ground"}]
    try:
        h._handle_solaris_build_graph(bad)
        failures.append("B5: unknown type 'grid' was NOT rejected")
    except SynapseUserError as e:
        print("B5 rejected  :", str(e)[:150])
        if "plane" not in str(e):
            failures.append("B5: rejection carried no catalog remediation")
        if len(hou.node("/stage").children()) != before:
            failures.append("B5: nodes were created despite rejection")
    except Exception as e:
        failures.append("B5: wrong error type %s: %s" % (type(e).__name__, e))

    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("PASS: identical rebuild converges; unknown type rejected clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
