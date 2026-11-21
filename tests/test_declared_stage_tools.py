"""R-025: stage-keyed Solaris tools declare their stage to the bridge.

``synapse_solaris_shotsetup_karma_xpu`` and ``synapse_matlib_bind`` build
into a LOP stage named by ``payload["stage"]`` (default ``/stage``). That key
is not one of the four R7 blast-radius keys (node/parent/path/source), so the
Operation used to reach the bridge with ``touches_stage=False``: blast-radius
inference had no anchor, composition validation never ran, and the R1 scene
hash measured ``/obj`` instead of the stage.

The adapter now carries the handler's own declaration onto the Operation.
These tests pin the declaration and execute both tools through
``execute_through_bridge`` — the dispatcher the in-Houdini /mcp endpoint and
the panel worker both call — against a fake ``hou``. The fake hou is the
established idiom of tests/test_composition_validation.py and
tests/test_blast_radius.py: the code path is the production one, only the
Houdini runtime is simulated. The live check on a real 22.0.400 session
remains outstanding (Receipt: LIVE).
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("shared.bridge")

import shared.bridge as bridge_module  # noqa: E402
from shared.bridge import LosslessExecutionBridge  # noqa: E402
from synapse.core.protocol import SynapseCommand, SynapseResponse  # noqa: E402
from synapse.panel import bridge_adapter  # noqa: E402


# ---------------------------------------------------------------------------
# Fake hou: one stage node at /stage; a build mutates stage content, adds a
# child node and records an undo-stack entry. Anything else is "not found".
# ---------------------------------------------------------------------------


class _FakeStage:
    """Minimal composed stage: empty traversal, Flatten reflects content."""

    def __init__(self):
        self.content = ["/World"]

    def Traverse(self):
        return []

    def TraverseAll(self):
        return ()

    def Flatten(self):
        content = "|".join(self.content)
        return SimpleNamespace(ExportToString=lambda: content)


class _FakeChild:
    def __init__(self, session_id):
        self._session_id = session_id

    def sessionId(self):
        return self._session_id

    def cookCount(self):
        return 1


class _FakeStageNode:
    def __init__(self):
        self.stage_obj = _FakeStage()
        self.children_list = []

    def path(self):
        return "/stage"

    def children(self):
        return list(self.children_list)

    def cookCount(self):
        return len(self.children_list)

    def geometry(self):
        return None

    def stage(self):
        return self.stage_obj


class _FakeUndos:
    """hou.undos fake: the label stack grows when a scene write is recorded."""

    def __init__(self):
        self.labels = ["artist previous edit"]

    def areEnabled(self):
        return True

    def undoLabels(self):
        return tuple(self.labels)

    def group(self, label):
        class _Ctx:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Ctx()


def _fake_hou(node, undos):
    return SimpleNamespace(
        undos=undos,
        node=lambda path: node if path == "/stage" else None,
    )


class _BuildHandler:
    """Stands in for SynapseHandler.handle: 'builds' by mutating the stage."""

    def __init__(self, node, undos):
        self._node = node
        self._undos = undos
        self.calls = 0

    def handle(self, command):
        self.calls += 1
        self._node.stage_obj.content.append("/World/shot_setup")
        self._node.children_list.append(_FakeChild("sid-shot"))
        self._undos.labels.append("SYNAPSE: build")
        return SynapseResponse(id=command.id, success=True,
                               data={"status": "created"})


class _RecordingBridge:
    """Captures the Operations the adapter hands to the bridge."""

    def __init__(self):
        self.ops = []

    def execute(self, op):
        self.ops.append(op)
        return SimpleNamespace(success=True, result=SimpleNamespace(data={}),
                               integrity=None, error=None)


class _RecordingRealBridge(LosslessExecutionBridge):
    """The real bridge, with the panel's non-blocking consent posture, that
    also keeps every Operation it ran (the predicate reads stage_path)."""

    def __init__(self):
        super().__init__(consent_callback=lambda op: True)
        self._gate = None  # never the blocking HumanGate poll
        self.ops = []

    def execute(self, op):
        self.ops.append(op)
        return super().execute(op)


def _command(payload):
    return SynapseCommand(type="solaris_compose", id="r025", payload=payload)


# ---------------------------------------------------------------------------
# The Operation carries the declared stage
# ---------------------------------------------------------------------------


class TestOperationCarriesDeclaredStage:

    def test_shotsetup_defaults_to_stage(self, monkeypatch):
        recorder = _RecordingBridge()
        monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: recorder)

        bridge_adapter.execute_through_bridge(
            "synapse_solaris_shotsetup_karma_xpu", object(),
            _command({"shot": "r025"}),
        )

        assert len(recorder.ops) == 1
        op = recorder.ops[0]
        assert op.touches_stage is True
        assert op.stage_path == "/stage"

    def test_matlib_bind_defaults_to_stage(self, monkeypatch):
        recorder = _RecordingBridge()
        monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: recorder)

        bridge_adapter.execute_through_bridge(
            "synapse_matlib_bind", object(),
            _command({"material": "/materials/red", "targets": "//Mesh",
                      "input_node": "/stage/dept_stack"}),
        )

        assert len(recorder.ops) == 1
        op = recorder.ops[0]
        assert op.touches_stage is True
        assert op.stage_path == "/stage"

    def test_payload_stage_path_wins(self, monkeypatch):
        recorder = _RecordingBridge()
        monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: recorder)

        bridge_adapter.execute_through_bridge(
            "synapse_matlib_bind", object(),
            _command({"material": "/materials/red", "targets": "//Mesh",
                      "stage": "/stage/lookdev"}),
        )

        assert recorder.ops[0].stage_path == "/stage/lookdev"

    def test_non_stage_tool_is_not_declared(self, monkeypatch):
        recorder = _RecordingBridge()
        monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: recorder)

        bridge_adapter.execute_through_bridge(
            "houdini_set_parm", object(),
            _command({"node": "/obj/geo1", "parm": "tx", "value": 1.0}),
        )

        op = recorder.ops[0]
        assert op.touches_stage is False
        assert op.stage_path is None


# ---------------------------------------------------------------------------
# Through the bridge: composition anchor fires, stage hash sees the build
# ---------------------------------------------------------------------------


class TestStageBuildAnchors:

    def _run(self, monkeypatch, tool_name, payload):
        node, undos = _FakeStageNode(), _FakeUndos()
        monkeypatch.setattr(bridge_module, "_HOU_AVAILABLE", True)
        monkeypatch.setattr(bridge_module, "hou", _fake_hou(node, undos))

        bridge = _RecordingRealBridge()
        monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: bridge)

        handler = _BuildHandler(node, undos)
        response = bridge_adapter.execute_through_bridge(
            tool_name, handler, _command(payload))
        return bridge, handler, response

    def test_shotsetup_anchors_composition_and_stage_hash(self, monkeypatch):
        bridge, handler, response = self._run(
            monkeypatch, "synapse_solaris_shotsetup_karma_xpu",
            {"shot": "r025"},
        )

        assert handler.calls == 1
        op = bridge.ops[0]
        assert op.stage_path == "/stage"
        assert op.touches_stage is True

        integrity = response.data["_integrity"]
        assert integrity["composition_applicable"] is True
        assert integrity["composition"] is True
        assert integrity["delta_hash"] != "no_change"
        assert integrity["scene_hash_before"] != integrity["scene_hash_after"]
        # The composed stage (not /obj) backed the hash.
        assert integrity["stage_hash_mode"] in ("full", "structural")

    def test_matlib_bind_anchors_composition_and_stage_hash(self, monkeypatch):
        bridge, handler, response = self._run(
            monkeypatch, "synapse_matlib_bind",
            {"material": "/materials/red", "targets": "//Mesh"},
        )

        assert handler.calls == 1
        op = bridge.ops[0]
        assert op.stage_path == "/stage"
        assert op.touches_stage is True

        integrity = response.data["_integrity"]
        assert integrity["composition_applicable"] is True
        assert integrity["composition"] is True
        assert integrity["delta_hash"] != "no_change"
        assert integrity["stage_hash_mode"] in ("full", "structural")
