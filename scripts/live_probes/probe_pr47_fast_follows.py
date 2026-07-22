"""LIVE PROBE -- requires hython on the target build; not part of `pytest tests/`.

    "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe" \
        scripts/live_probes/probe_pr47_fast_follows.py

Drives the REAL build_graph handler to prove the three PR-#47 code fast-follows
compose end to end:

  item 2 -- extend an existing network: reference a live merge (existing:true),
            append a new asset to its NEXT FREE input; first inputs untouched;
            the existing node is not moved/stamped/re-parmed; result reports it.
  item 1 -- per-network box identity: two differently-named networks in one
            /stage each keep their own three section boxes (6 total).
  item 4 -- status: a full-reuse rebuild that CHANGES a parm reports 'updated';
            an identical rebuild reports 'unchanged'.

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


def clear():
    stage = hou.node("/stage")
    for c in list(stage.children()):
        c.destroy()
    for b in list(stage.networkBoxes()):
        b.destroy()


def main():
    h = _Harness()
    stage = hou.node("/stage")
    f = []

    # ---- item 2: extend an ARTIST'S existing merge -------------------------
    # Build the base network by hand (no SYNAPSE stamp) -- this is the real
    # extend scenario: adding to a network the artist already built.
    clear()
    a0 = stage.createNode("sopcreate", "asset_a")
    b0 = stage.createNode("sopcreate", "asset_b")
    merge = stage.createNode("merge", "MERGE")
    merge.setInput(0, a0)
    merge.setInput(1, b0)
    before = [i.name() for i in merge.inputs()]

    # Now extend: a new asset appended to the EXISTING merge.
    res = h._handle_solaris_build_graph({
        "parent": "/stage",
        "nodes": [
            {"id": "c", "type": "sopcreate", "name": "asset_c"},
            {"id": "m", "existing": True, "name": "MERGE"}],
        "connections": [{"from": "c", "to": "m"}],   # no explicit index -> append
        "display_node": "c"})
    after = [i.name() for i in merge.inputs()]
    print("merge inputs: before=%s  after=%s" % (before, after))
    print("existing_nodes reported:", res.get("existing_nodes"))
    if after != ["asset_a", "asset_b", "asset_c"]:
        f.append("item2: append wrong -> %s" % after)
    if before != after[:2]:
        f.append("item2: existing inputs were disturbed")
    if not any(e["path"] == "/stage/MERGE" for e in res.get("existing_nodes", [])):
        f.append("item2: existing merge not reported in existing_nodes")
    if "SYNAPSE" in (merge.comment() or ""):
        f.append("item2: existing merge was provenance-stamped (should not be)")

    # SEAM (found by the loop-close fleet): the CORE build->look->rebuild loop.
    # Re-running the identical extend must be a no-op, not an unbounded re-append.
    extend_payload = {
        "parent": "/stage",
        "nodes": [
            {"id": "c", "type": "sopcreate", "name": "asset_c"},
            {"id": "m", "existing": True, "name": "MERGE"}],
        "connections": [{"from": "c", "to": "m"}],
        "display_node": "c"}
    r2 = h._handle_solaris_build_graph(dict(extend_payload))
    r3 = h._handle_solaris_build_graph(dict(extend_payload))
    idem = [i.name() for i in merge.inputs()]
    print("after 2 more identical extends:", idem, "| statuses:",
          res.get("status"), r2.get("status"), r3.get("status"))
    if idem != ["asset_a", "asset_b", "asset_c"]:
        f.append("item2 SEAM: re-extend duplicated the wire -> %s "
                 "(non-idempotent)" % idem)
    if r3.get("status") != "unchanged":
        f.append("item2 SEAM: no-op re-extend reported status=%r (should be "
                 "'unchanged')" % r3.get("status"))

    # ---- item 1: two networks keep their own boxes -------------------------
    clear()
    full = lambda tag: {  # noqa: E731
        "parent": "/stage",
        "nodes": [
            {"id": "g", "type": "sopcreate", "name": "g_" + tag},
            {"id": "mt", "type": "materiallibrary", "name": "m_" + tag},
            {"id": "cm", "type": "camera", "name": "c_" + tag},
            {"id": "lt", "type": "distantlight", "name": "l_" + tag},
            {"id": "rs", "type": "karmarendersettings", "name": "rs_" + tag},
            {"id": "o", "type": "null", "name": "OUT_" + tag}],
        "connections": [{"from": "g", "to": "mt", "input": 0},
                        {"from": "mt", "to": "cm", "input": 0},
                        {"from": "cm", "to": "lt", "input": 0},
                        {"from": "lt", "to": "rs", "input": 0},
                        {"from": "rs", "to": "o", "input": 0}],
        "display_node": "o"}
    h._handle_solaris_build_graph(full("A"))
    h._handle_solaris_build_graph(full("B"))
    boxes = sorted(b.name() for b in stage.networkBoxes())
    print("two-network boxes:", boxes)
    if len(boxes) != 6:
        f.append("item1: expected 6 section boxes (3 per network), got %d" % len(boxes))
    if not (any("OUT_A" in b for b in boxes) and any("OUT_B" in b for b in boxes)):
        f.append("item1: a network's boxes were swept by the other")

    # ---- item 4: status='updated' after a parm change ----------------------
    clear()
    shot = {
        "parent": "/stage",
        "nodes": [
            {"id": "l", "type": "distantlight", "name": "key",
             "parms": {"xn__inputsintensity_i0a": 1.0}},
            {"id": "o", "type": "null", "name": "OUT"}],
        "connections": [{"from": "l", "to": "o", "input": 0}],
        "display_node": "o"}
    h._handle_solaris_build_graph(dict(shot))
    same = h._handle_solaris_build_graph(dict(shot))
    changed = dict(shot)
    changed["nodes"] = [dict(shot["nodes"][0],
                             parms={"xn__inputsintensity_i0a": 3.0}),
                        shot["nodes"][1]]
    upd = h._handle_solaris_build_graph(changed)
    print("status: identical-rebuild=%s  parm-changed-rebuild=%s"
          % (same.get("status"), upd.get("status")))
    if same.get("status") != "unchanged":
        f.append("item4: identical rebuild should be 'unchanged', got %r"
                 % same.get("status"))
    if upd.get("status") != "updated":
        f.append("item4: parm-changed rebuild should be 'updated', got %r"
                 % upd.get("status"))

    clear()
    print()
    if f:
        for x in f:
            print("FAIL:", x)
        return 1
    print("PASS: item2 extend-existing + item1 per-network boxes + item4 "
          "status='updated' all hold end to end")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
