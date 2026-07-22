"""LIVE PROBE -- requires hython on the target build; not part of `pytest tests/`.

    "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe" \
        scripts/live_probes/probe_m10_section_boxes.py

M10 section boxes on real Houdini nodes:
  * a full shot gets three bands (SCENE / LIGHTING / RENDER) with correct
    membership, colored and labelled;
  * a REBUILD is idempotent -- the box count does not grow (find-first, not the
    auto-suffixing blind create).

Exit 0 = both hold.
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO, "python"))

import hou  # noqa: E402
from synapse.server.handlers_solaris_graph import SolarisGraphMixin  # noqa: E402


class _Harness(SolarisGraphMixin):
    pass


SHOT = {
    "parent": "/stage",
    "nodes": [
        {"id": "geo", "type": "sopcreate", "name": "asset"},
        {"id": "mat", "type": "materiallibrary", "name": "matlib"},
        {"id": "cam", "type": "camera", "name": "shotcam"},
        {"id": "key", "type": "distantlight", "name": "key"},
        {"id": "dome", "type": "domelight", "name": "env"},
        {"id": "rs", "type": "karmarendersettings", "name": "rendersettings"},
        {"id": "rop", "type": "usdrender_rop", "name": "render"},
        {"id": "out", "type": "null", "name": "OUTPUT"},
    ],
    "connections": [
        {"from": "geo", "to": "mat", "input": 0},
        {"from": "mat", "to": "cam", "input": 0},
        {"from": "cam", "to": "key", "input": 0},
        {"from": "key", "to": "dome", "input": 0},
        {"from": "dome", "to": "rs", "input": 0},
        {"from": "rs", "to": "out", "input": 0},
        {"from": "rs", "to": "rop", "input": 0},
    ],
    "display_node": "out",
}

# Section boxes are namespaced by the display node's name (per-network identity,
# M10 fast-follow). The SHOT's display_node "out" is the null named OUTPUT.
_EXPECT = {
    "synapse_sec_OUTPUT_scene": {"asset", "matlib"},
    "synapse_sec_OUTPUT_lighting": {"shotcam", "key", "env"},
    "synapse_sec_OUTPUT_render": {"rendersettings", "render", "OUTPUT"},
}


def main():
    stage = hou.node("/stage")
    for c in list(stage.children()):
        c.destroy()

    h = _Harness()
    result = h._handle_solaris_build_graph(dict(SHOT))
    failures = []

    boxes = {b.name(): {n.name() for n in b.nodes()} for b in stage.networkBoxes()}
    print("build 1 sections:", result.get("sections"))
    print("boxes:", {k: sorted(v) for k, v in boxes.items()})

    for name, expect in _EXPECT.items():
        if name not in boxes:
            failures.append("missing band %s" % name)
        elif boxes[name] != expect:
            failures.append("%s membership %s != %s"
                            % (name, sorted(boxes[name]), sorted(expect)))
    for name in boxes:
        b = stage.findNetworkBox(name)
        if not b.comment():
            failures.append("%s has no label" % name)

    # Idempotency: a rebuild must not stack a second set of boxes.
    n_before = len(stage.networkBoxes())
    h._handle_solaris_build_graph(dict(SHOT))
    n_after = len(stage.networkBoxes())
    print("boxes before rebuild=%d  after=%d" % (n_before, n_after))
    if n_after != n_before:
        failures.append("rebuild stacked boxes: %d -> %d" % (n_before, n_after))
    suffixed = [b.name() for b in stage.networkBoxes()
                if b.name().rstrip("0123456789") != b.name()]
    if suffixed:
        failures.append("auto-suffixed duplicate boxes present: %s" % suffixed)

    # Monotonicity gate (adversarial finding): a network whose DAG depth does
    # NOT follow rank order must get NO boxes rather than overlapping ones.
    for c in list(stage.children()):
        c.destroy()
    non_monotonic = {
        "parent": "/stage",
        "nodes": [
            {"id": "light", "type": "distantlight", "name": "rootlight"},
            {"id": "geo", "type": "sopcreate", "name": "geo"},
            {"id": "mat", "type": "materiallibrary", "name": "matlib"},
            {"id": "rs", "type": "karmarendersettings", "name": "rs"},
            {"id": "out", "type": "null", "name": "OUTPUT"},
        ],
        # light (rank 500) is the ROOT feeding geo (rank 100): depth != rank.
        "connections": [
            {"from": "light", "to": "geo", "input": 0},
            {"from": "geo", "to": "mat", "input": 0},
            {"from": "mat", "to": "rs", "input": 0},
            {"from": "rs", "to": "out", "input": 0},
        ],
        "display_node": "out",
    }
    res2 = h._handle_solaris_build_graph(non_monotonic)
    n_boxes = len(stage.networkBoxes())
    print("non-monotonic build: sections=%s  boxes drawn=%d"
          % (res2.get("sections"), n_boxes))
    if n_boxes != 0:
        failures.append("gate FAILED: %d boxes drawn on a non-rank-monotonic "
                        "layout (should be 0)" % n_boxes)

    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        return 1
    print("PASS: 3 correct bands + idempotent rebuild + gate suppresses "
          "boxes on a depth!=rank layout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
