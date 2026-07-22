"""LIVE PROBE -- requires hython on the target build; not part of `pytest tests/`.

    "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe" \
        scripts/live_probes/probe_phase3_layout.py

Phase 3 layout on real Houdini nodes:
  * M8 -- three assets feeding a merge lay out left-to-right in input order.
  * M9 -- the merge sits at the barycenter of its three parents.
  * M7 -- a SECOND build into the now-populated stage starts clear of the first
    instead of landing on top of it.

Exit 0 = all three hold.
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO, "python"))

import hou  # noqa: E402
from synapse.server.handlers_solaris_graph import SolarisGraphMixin  # noqa: E402


class _Harness(SolarisGraphMixin):
    pass


FAN_IN = {
    "parent": "/stage",
    "nodes": [
        {"id": "a0", "type": "sopcreate", "name": "asset_a"},
        {"id": "a1", "type": "sopcreate", "name": "asset_b"},
        {"id": "a2", "type": "sopcreate", "name": "asset_c"},
        {"id": "m", "type": "merge", "name": "assembly"},
        {"id": "out", "type": "null", "name": "OUTPUT"},
    ],
    "connections": [
        {"from": "a0", "to": "m", "input": 0},
        {"from": "a1", "to": "m", "input": 1},
        {"from": "a2", "to": "m", "input": 2},
        {"from": "m", "to": "out", "input": 0},
    ],
    "display_node": "out",
}


def _pos(name):
    n = hou.node("/stage/%s" % name)
    p = n.position()
    return p[0], p[1]


def main():
    stage = hou.node("/stage")
    for c in list(stage.children()):
        c.destroy()

    h = _Harness()
    h._handle_solaris_build_graph(dict(FAN_IN))
    failures = []

    xa = {n: _pos(n)[0] for n in ("asset_a", "asset_b", "asset_c")}
    order = sorted(xa, key=xa.get)
    print("merge inputs L->R:", order, {k: round(v, 3) for k, v in xa.items()})
    if order != ["asset_a", "asset_b", "asset_c"]:
        failures.append("M8: merge inputs not in wire order: %s" % order)

    mx = _pos("assembly")[0]
    bary = sum(xa.values()) / 3.0
    print("merge x=%.3f  parent barycenter=%.3f" % (mx, bary))
    if abs(mx - bary) > 1e-3:
        failures.append("M9: merge not at parent barycenter (%.3f vs %.3f)"
                        % (mx, bary))

    # M7: a second, unrelated build must not land on top of the first.
    lowest_before = min(_pos(c.name())[1] for c in stage.children())
    h._handle_solaris_build_graph({
        "parent": "/stage",
        "nodes": [{"id": "g", "type": "sopcreate", "name": "second_geo"},
                  {"id": "o2", "type": "null", "name": "OUTPUT2"}],
        "connections": [{"from": "g", "to": "o2", "input": 0}],
        "display_node": "o2",
    })
    new_top = max(_pos("second_geo")[1], _pos("OUTPUT2")[1])
    print("first build lowest y=%.3f  second build top y=%.3f" % (lowest_before, new_top))
    if new_top >= lowest_before:
        failures.append("M7: second build overlaps the first (top %.3f >= %.3f)"
                        % (new_top, lowest_before))

    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("PASS: input-order, barycenter, and non-overlapping second build all hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
