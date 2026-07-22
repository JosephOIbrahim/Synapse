"""LIVE PROBE -- the whole loop composed on one realistic artist request.

    "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe" \
        scripts/live_probes/probe_loop_composed.py

A branching lookdev shot exercises every fix at once. Asserts they COMPOSE:
  B9  -- emits karmarendersettings, never the deprecated karmarenderproperties
  B5  -- a bad type in a second call is rejected before anything is created
  B1  -- ground plane + shadow catcher land UPSTREAM of usdrender_rop
  Phase3 -- merge inputs are ordered, no wire crossings
  M10 -- section boxes APPEAR on this normal branching shot (NOT falsely
         suppressed by the monotonicity gate — the key seam worry)
  B4  -- a rebuild converges (no duplicate nodes, no stacked boxes)

Exit 0 = the loop is closed.
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


SHOT = {
    "parent": "/stage",
    "nodes": [
        {"id": "hero", "type": "sopcreate", "name": "hero"},
        {"id": "env", "type": "sopcreate", "name": "env"},
        {"id": "ground", "type": "plane", "name": "ground"},
        {"id": "shadow", "type": "shadowcatcher", "name": "shadowcatcher"},
        {"id": "merge", "type": "merge", "name": "assembly"},
        {"id": "mat", "type": "materiallibrary", "name": "matlib"},
        {"id": "assign", "type": "assignmaterial", "name": "assign"},
        {"id": "cam", "type": "camera", "name": "shotcam"},
        {"id": "key", "type": "distantlight", "name": "key"},
        {"id": "fill", "type": "distantlight", "name": "fill"},
        {"id": "dome", "type": "domelight", "name": "env_dome"},
        {"id": "rs", "type": "karmarendersettings", "name": "rendersettings"},
        {"id": "rop", "type": "usdrender_rop", "name": "render"},
        {"id": "out", "type": "null", "name": "OUTPUT"},
    ],
    "connections": [
        {"from": "hero", "to": "merge", "input": 0},
        {"from": "env", "to": "merge", "input": 1},
        {"from": "ground", "to": "merge", "input": 2},
        {"from": "shadow", "to": "merge", "input": 3},
        {"from": "merge", "to": "mat", "input": 0},
        {"from": "mat", "to": "assign", "input": 0},
        {"from": "assign", "to": "cam", "input": 0},
        {"from": "cam", "to": "key", "input": 0},
        {"from": "key", "to": "fill", "input": 0},
        {"from": "fill", "to": "dome", "input": 0},
        {"from": "dome", "to": "rs", "input": 0},
        {"from": "rs", "to": "out", "input": 0},
        {"from": "rs", "to": "rop", "input": 0},
    ],
    "display_node": "out",
}


def y_of(name):
    return hou.node("/stage/%s" % name).position()[1]


def main():
    stage = hou.node("/stage")
    for c in list(stage.children()):
        c.destroy()
    for b in list(stage.networkBoxes()):
        b.destroy()

    h = _Harness()
    r = h._handle_solaris_build_graph(dict(SHOT))
    f = []

    # B9: no deprecated type on the built stage.
    types = {c.type().name().split("::")[0] for c in stage.children()}
    if "karmarenderproperties" in types:
        f.append("B9: deprecated karmarenderproperties on the stage")
    if "karmarendersettings" not in types:
        f.append("B9: karmarendersettings not created")

    # B1: ground + shadowcatcher upstream of the ROP (higher Y = upstream).
    rop_y = y_of("render")
    for g in ("ground", "shadowcatcher"):
        if y_of(g) <= rop_y:
            f.append("B1: %s at y=%.2f not upstream of ROP y=%.2f"
                     % (g, y_of(g), rop_y))

    # Phase3: merge inputs 0..3 laid left-to-right (no crossing).
    xs = [hou.node("/stage/%s" % n).position()[0] for n in ("hero", "env", "ground", "shadowcatcher")]
    if xs != sorted(xs):
        f.append("Phase3: merge inputs not L->R in wire order: %s" % xs)

    # M10 (the seam): boxes MUST appear on this normal branching shot.
    boxes = {b.name() for b in stage.networkBoxes()}
    print("sections:", r.get("sections"))
    print("boxes:", sorted(boxes))
    if not r.get("sections"):
        f.append("M10 SEAM: boxes FALSELY SUPPRESSED on a normal branching "
                 "shot (monotonicity gate too strict)")
    else:
        for want in ("synapse_sec_scene", "synapse_sec_lighting", "synapse_sec_render"):
            if want not in boxes:
                f.append("M10: missing %s" % want)

    # B4: rebuild converges.
    n1 = len(stage.children()); nb1 = len(stage.networkBoxes())
    r2 = h._handle_solaris_build_graph(dict(SHOT))
    n2 = len(stage.children()); nb2 = len(stage.networkBoxes())
    print("rebuild: children %d->%d  boxes %d->%d  status=%s"
          % (n1, n2, nb1, nb2, r2.get("status")))
    if n2 != n1:
        f.append("B4: rebuild changed child count %d->%d" % (n1, n2))
    if nb2 != nb1:
        f.append("B4xM10: rebuild stacked boxes %d->%d" % (nb1, nb2))

    # B5: a bad type in a fresh build is rejected before creation.
    for c in list(stage.children()):
        c.destroy()
    for b in list(stage.networkBoxes()):
        b.destroy()
    bad = {"parent": "/stage",
           "nodes": [{"id": "g", "type": "grid", "name": "g"},
                     {"id": "o", "type": "null", "name": "O"}],
           "connections": [{"from": "g", "to": "o", "input": 0}],
           "display_node": "o"}
    try:
        h._handle_solaris_build_graph(bad)
        f.append("B5: bad type 'grid' not rejected")
    except SynapseUserError as e:
        if "plane" not in str(e):
            f.append("B5: rejection missing remediation")
        if stage.children():
            f.append("B5: nodes created despite rejection")

    print()
    if f:
        for x in f:
            print("FAIL:", x)
        return 1
    print("PASS: B9 + B1 + Phase3 + M10(boxes appear) + B4 + B5 all compose "
          "on one realistic lookdev shot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
