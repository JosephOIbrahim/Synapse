"""Phase 0c / S3: blast-radius inference must follow WIRES, not just param refs.

_infer_stage_touch traced only node.dependents() (parameter/expression refs). A
wired SOP chain feeding a SOP-Import LOP -- box ->(wire)-> blast ->(soppath ref)->
sopimport -- is missed when you mutate `box`, because box.dependents() is empty
(blast is wired) so the trace stops before reaching the LOP.

LIVE V1 (H21.0.631 hython, .scout/s3_sopimport_recon2.py): dependents-only from box
returns None (MISS); outputs()+dependents() returns /stage/sopimport1 (CATCH). This
test pins the fix in stock CI with a fake graph of that exact shape.
"""
import shared.bridge as b
from shared.bridge import Operation
from shared.types import AgentID


class _Node:
    def __init__(self, path, deps=(), outs=()):
        self._path, self._deps, self._outs = path, deps, outs

    def path(self):
        return self._path

    def dependents(self):
        return list(self._deps)

    def outputs(self):
        return list(self._outs)


class _Lop(_Node):
    """Stands in for an hou.LopNode instance."""


class _FakeHou:
    LopNode = _Lop

    def __init__(self, node):
        self._node = node

    def node(self, path):
        return self._node


def test_infer_stage_touch_follows_wired_sop_chain(monkeypatch):
    sopimport = _Lop("/stage/sopimport1")
    blast = _Node("/obj/s3geo/blast", deps=(sopimport,), outs=())   # blast.dependents -> sopimport (param ref)
    box = _Node("/obj/s3geo/box", deps=(), outs=(blast,))           # box.outputs -> blast (wire); no dependents

    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(b, "hou", _FakeHou(box))

    bridge = b.LosslessExecutionBridge()
    op = Operation(
        agent_id=AgentID.HANDS,
        operation_type="create_node",
        summary="s3",
        fn=lambda: None,
        kwargs={"node_path": "/obj/s3geo/box"},
    )
    assert bridge._infer_stage_touch(op) is True
    assert op.touches_stage is True
    assert op.stage_path == "/stage/sopimport1"
