"""W.3-H22-setdressing live pin: paintinstances + copytopoints create AND cook.

Runs ONLY under real Houdini (hython on H22.0.368+). Under the stock suite the
conftest canonical fake ``hou`` is resident, so every test here skips — the
stock-python side of this cycle (emitted TYPE NAMES) is pinned by
tests/test_setdressing_recipe.py and tests/test_solaris_graph.py.

Ground truth being pinned (N-5, docs/reviews/h22-now-probes-2026-07-16.md, all
re-observed by the W.3 pre-test hython probe on 22.0.368, 2026-07-16):

  * ``Lop/layout``    -> ``Lop/paintinstances`` (whats-new 22/solaris.txt L137);
    sole dropped parm: ``method``. Cooks clean with no inputs.
  * ``Lop/instancer`` -> ``Lop/copytopoints``   (L143); dropped parms:
    ``allowmissingprototypes`` + ``protooptionsgroup`` (successor:
    ``handlemissingprototypes``, default 'error'; the H21 ``soppath`` point
    source became ``pointsoppath``). Needs points + a prototype to cook: the
    minimal verified config is transformsourcemode='extsop' + pointsoppath ->
    a 1-point SOP + input 1 = a `primitive` LOP.
  * ``hou.nodeType(lop, 'layout'/'instancer')`` -> None — only the shipped
    opalias rescues createNode(). SYNAPSE emits canonical spellings only
    (W.3 ruling: never lean on the alias table).

Run:  hython -m pytest tests/test_h22_setdressing_live.py -v
"""

from __future__ import annotations

import pytest

import hou

# Real-hou gate: the canonical fake carries __synapse_canonical__ and does not
# define lopNodeTypeCategory; real hou has both properties inverted.
_LIVE = (
    not getattr(hou, "__synapse_canonical__", False)
    and hasattr(hou, "lopNodeTypeCategory")
)

pytestmark = pytest.mark.skipif(
    not _LIVE, reason="requires real Houdini (hython) — H22 live create+cook pin"
)


def _destroy(*nodes) -> None:
    for node in nodes:
        try:
            if node is not None:
                node.destroy()
        except Exception:  # noqa: BLE001 — teardown best-effort
            pass


def test_paintinstances_creates_canonical_and_cooks():
    stage = hou.node("/stage")
    node = stage.createNode("paintinstances", "w3live_paint")
    try:
        assert node.type().name() == "paintinstances"
        # Dropped in the H22 rename (41/42 parms survive) — a setParm('method')
        # anywhere in an emit path would silently miss; pin its absence.
        assert node.parm("method") is None
        node.cook(force=True)
        assert not node.errors(), f"paintinstances cook errors: {node.errors()}"
    finally:
        _destroy(node)


def test_copytopoints_canonical_type_and_dropped_parms():
    stage = hou.node("/stage")
    node = stage.createNode("copytopoints", "w3live_copy_parms")
    try:
        assert node.type().name() == "copytopoints"
        # Dropped in the H22 rename (39/41 parms survive):
        assert node.parm("allowmissingprototypes") is None
        assert node.parm("protooptionsgroup") is None
        # Successor surface present (probe-verified 22.0.368):
        assert node.parm("handlemissingprototypes") is not None
        assert node.parm("pointsoppath") is not None
    finally:
        _destroy(node)


def test_copytopoints_cooks_with_points_and_prototype():
    stage = hou.node("/stage")
    geo = hou.node("/obj").createNode("geo", "w3live_points")
    proto = node = None
    try:
        add = geo.createNode("add", "w3live_pt")
        add.parm("points").set(1)
        add.parm("usept0").set(1)
        add.setDisplayFlag(True)
        add.setRenderFlag(True)

        proto = stage.createNode("primitive", "w3live_proto")
        node = stage.createNode("copytopoints", "w3live_copy")
        node.setInput(1, proto)
        node.parm("transformsourcemode").set("extsop")
        node.parm("pointsoppath").set(add.path())

        node.cook(force=True)
        assert not node.errors(), f"copytopoints cook errors: {node.errors()}"

        out_stage = node.stage()
        assert out_stage is not None
        paths = [p.GetPath().pathString for p in out_stage.Traverse()]
        # The node authors its PointInstancer prim + a Prototypes scope.
        assert any("/Prototypes" in p for p in paths), (
            f"no Prototypes scope on the cooked stage: {paths}"
        )
    finally:
        _destroy(node, proto, geo)


def test_legacy_spellings_absent_from_type_lookup():
    lop = hou.lopNodeTypeCategory()
    # Removed names: alias-only (creation-time); type lookup is honest.
    assert hou.nodeType(lop, "layout") is None
    assert hou.nodeType(lop, "instancer") is None
    # Canonical names resolve.
    assert hou.nodeType(lop, "paintinstances") is not None
    assert hou.nodeType(lop, "copytopoints") is not None
    # The NEW H22 node is distinct from both renames (SOL-03 correction).
    assert hou.nodeType(lop, "pointinstancer") is not None
