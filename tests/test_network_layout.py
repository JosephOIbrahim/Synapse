"""Existing-network organization, without permitting arbitrary code or rebuilds."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT))

from synapse.server.network_layout import plan_layout, validate_request


def descriptors():
    return [
        {"path": "/stage/sphere", "type": "sopimport", "description": "SOP Import"},
        {"path": "/stage/coral", "type": "materiallibrary", "description": "Material Library"},
        {"path": "/stage/light", "type": "light::2.0", "description": "Light"},
        {"path": "/stage/OUTPUT", "type": "null", "description": "Null"},
    ]


def connections():
    paths = [n["path"] for n in descriptors()]
    return [{"from": a, "to": b, "input": 0} for a, b in zip(paths, paths[1:])]


def request(**kwargs):
    return validate_request({"parent": "/stage", "nodes": [n["path"] for n in descriptors()], **kwargs})


def test_orientation_repositions_the_same_observed_chain():
    vertical = plan_layout(request(), descriptors(), connections())
    horizontal = plan_layout(request(orientation="horizontal"), descriptors(), connections())
    paths = [n["path"] for n in descriptors()]
    assert set(vertical["positions"]) == set(horizontal["positions"]) == set(paths)
    assert len({vertical["positions"][p][0] for p in paths}) == 1
    assert all(vertical["positions"][a][1] > vertical["positions"][b][1] for a, b in zip(paths, paths[1:]))
    assert len({horizontal["positions"][p][1] for p in paths}) == 1
    assert all(horizontal["positions"][a][0] < horizontal["positions"][b][0] for a, b in zip(paths, paths[1:]))


def test_focus_has_readable_sections_labels_and_more_space():
    plain = plan_layout(request(), descriptors(), connections())
    focused = plan_layout(request(style="focus"), descriptors(), connections())
    assert {s["label"] for s in focused["sections"]} == {
        "Geometry", "Materials", "Camera and lighting", "Shared assembly and output"}
    assert focused["labels"]["/stage/coral"] == "Material Library"
    assert focused["positions"]["/stage/OUTPUT"][1] < plain["positions"]["/stage/OUTPUT"][1]
    assert all(max(s["color"]) - min(s["color"]) < 0.2 for s in focused["sections"])


def test_assets_use_declared_membership_and_expose_shared_nodes():
    plan = plan_layout(request(style="assets", groups=[
        {"label": "Hero sphere", "nodes": ["/stage/sphere", "/stage/coral"]}
    ], labels={"/stage/coral": "Warm coral surface"}), descriptors(), connections())
    assert [s["label"] for s in plan["sections"]] == ["Hero sphere", "Shared assembly and output"]
    assert plan["sections"][0]["nodes"] == ["/stage/sphere", "/stage/coral"]
    assert plan["sections"][1]["nodes"] == ["/stage/light", "/stage/OUTPUT"]
    assert plan["labels"]["/stage/coral"] == "Warm coral surface"


@pytest.mark.parametrize("invalid", [
    {"style": "assets"},
    {"nodes": ["/stage/sphere", "/obj/elsewhere"]},
    {"nodes": ["/stage/sphere", "/stage/sphere"]},
    {"orientation": "diagonal"},
    {"spacing": float("nan")},
    {"spacing": 0.1},
    {"style": "focus", "groups": [{"label": "A", "nodes": ["/stage/not_selected"]}]},
    {"style": "focus", "groups": [{"label": "A", "nodes": ["/stage/sphere"]},
                                      {"label": "B", "nodes": ["/stage/sphere"]}]},
    {"labels": {"/stage/not_selected": "No"}},
    {"labels": {"/stage/sphere": "\x00hidden"}},
    {"replace_boxes": ["../unrelated"]},
    {"dry_run": "false"},
    {"code": "arbitrary code is outside this tool"},
])
def test_invalid_request_fails_before_native_changes(invalid):
    with pytest.raises(ValueError):
        request(**invalid)


def test_cycle_fails_before_positions_are_applied():
    edges = connections() + [{"from": "/stage/OUTPUT", "to": "/stage/sphere", "input": 0}]
    with pytest.raises(ValueError, match="cycle"):
        plan_layout(request(), descriptors(), edges)


def test_registration_uses_normal_mutation_policy_and_preserves_python_gate(monkeypatch):
    from synapse.mcp._tool_registry import TOOL_DEFS
    from synapse.panel.worker_policy import is_tool_allowed_for_worker
    from synapse.panel.bridge_adapter import _TOOL_TO_OPERATION
    from synapse.server.rbac import check_permission, Role
    from synapse.server.handlers import SynapseHandler
    entry = next(e for e in TOOL_DEFS if e[0] == "houdini_layout_network")
    assert entry[1] == "layout_network"
    assert entry[5] is False
    assert _TOOL_TO_OPERATION[entry[0]] == "set_parameter"
    assert SynapseHandler()._registry.has("layout_network")
    monkeypatch.delenv("SYNAPSE_WORKER_TOOL_PROFILE", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKER_TOOL_MODE", "standard")
    assert is_tool_allowed_for_worker(entry[0])[0]
    assert not is_tool_allowed_for_worker("houdini_execute_python")[0]
    monkeypatch.setenv("SYNAPSE_WORKER_TOOL_MODE", "strict")
    assert not is_tool_allowed_for_worker(entry[0])[0]
    assert check_permission(Role.ARTIST, "layout_network")
    assert not check_permission(Role.VIEWER, "layout_network")


def test_bridge_keeps_concise_action_label_and_target_for_integrity(monkeypatch):
    from types import SimpleNamespace
    from synapse.core.protocol import SynapseCommand, SynapseResponse
    from synapse.panel import bridge_adapter
    operations = []
    command = SynapseCommand(type="layout_network", id="layout-test", payload=request(style="assets", groups=[
        {"label": "Hero", "nodes": ["/stage/sphere"]}]))
    response = SynapseResponse(id=command.id, success=True, data={"status": "updated"})
    class Bridge:
        def execute(self, operation):
            operations.append(operation)
            return SimpleNamespace(success=True, result=operation.fn(), integrity=None)
    monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: Bridge())
    handler = SimpleNamespace(handle=lambda received: response if received is command else None)
    assert bridge_adapter.execute_through_bridge("houdini_layout_network", handler, command) is response
    assert len(operations) == 1
    assert operations[0].summary == "Organize network by asset"
    assert operations[0].operation_type == "set_parameter"
    assert operations[0].kwargs["node_path"] == "/stage"


def test_labels_preserve_artist_text_on_repeated_changes():
    from synapse.server.handlers_network_layout import _with_label
    original = "Artist note: copper is approved."
    focused, first = _with_label(original, None, "Material Library")
    asset, second = _with_label(focused, first, "Copper surface")
    assert asset == original + "\n\nSYNAPSE · Copper surface"
    repeated, _ = _with_label(asset, second, "Copper surface")
    assert repeated == asset
    edited = asset + "\nArtist added this later."
    updated, _ = _with_label(edited, second, "Metallic surface")
    assert updated.startswith(edited)


def test_float_color_storage_does_not_create_a_repeated_mutation():
    from synapse.server.handlers_network_layout import _same_color
    assert _same_color((0.3199999928, 0.3799999952, 0.4300000071), (0.32, 0.38, 0.43))
    assert not _same_color((0.32, 0.38, 0.50), (0.32, 0.38, 0.43))
