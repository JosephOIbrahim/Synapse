"""A preview preserves ports and refuses unsupported observations; it never edits."""
import copy

import pytest

from synapse.panel.wire_preview import build_insertion_preview, format_insertion_preview


def edge(source, output, target, input_):
    return {"source": source, "source_output": output, "target": target, "target_input": input_}


@pytest.fixture
def snapshot():
    paths = ["/stage/source", "/stage/target", "/stage/middle"]
    return {"schema": "synapse-selection-v1", "truncated": False, "warnings": [],
            "complete": True, "can_pin": True,
            "topology_hash": "a" * 64, "scene": {"session_token": "session", "hip_path": "untitled.hip"},
            "identities": [{"path": path, "session_id": i + 1} for i, path in enumerate(paths)],
            "nodes": [{"path": path, "session_id": i + 1, "parent": "/stage", "category": "Lop",
                       "input_capacity": 4, "output_capacity": 3} for i, path in enumerate(paths)],
            "wires": {"internal": [edge(paths[0], 2, paths[1], 3)], "entering": [], "leaving": []}}


def preview(snapshot, **kwargs):
    return build_insertion_preview(snapshot, snapshot["wires"]["internal"][0], "/stage/middle", **kwargs)


def test_preserves_both_original_ports_and_explicit_intermediate_ports(snapshot):
    before = copy.deepcopy(snapshot)
    result = preview(snapshot, input_index=1, output_index=2)
    assert result["before"] == edge("/stage/source", 2, "/stage/target", 3)
    assert result["after"] == [edge("/stage/source", 2, "/stage/middle", 1),
                               edge("/stage/middle", 2, "/stage/target", 3)]
    assert result["can_apply"] is False and result["status"] == "proposal"
    assert result["preconditions"]["expected_topology_hash"] == "a" * 64
    assert result["preconditions"]["expected_scene"] == snapshot["scene"]
    assert result["preconditions"]["expected_identities"] == snapshot["identities"]
    assert snapshot == before
    result["preconditions"]["expected_scene"]["session_token"] = "changed"
    assert snapshot["scene"]["session_token"] == "session"
    text = format_insertion_preview(result)
    assert "/stage/source [out 2]" in text and "/stage/target [in 3]" in text
    assert "No connections have been changed" in text
    assert "outside" in text and "semantics" in text


def test_occupied_input_from_outside_selection_is_not_overwritten(snapshot):
    snapshot["wires"]["entering"] = [edge("/stage/external", 0, "/stage/middle", 1)]
    with pytest.raises(ValueError, match="occupied"):
        preview(snapshot, input_index=1)


def test_cycle_in_observed_graph_is_rejected(snapshot):
    snapshot["wires"]["internal"].append(edge("/stage/target", 0, "/stage/middle", 1))
    with pytest.raises(ValueError, match="cycle"):
        preview(snapshot)


@pytest.mark.parametrize("field,value", [("input_capacity", None), ("input_capacity", 0),
                                        ("output_capacity", None), ("output_capacity", 0)])
def test_unknown_or_impossible_middle_ports_refuse(snapshot, field, value):
    snapshot["nodes"][2][field] = value
    with pytest.raises(ValueError, match="port"):
        preview(snapshot)


@pytest.mark.parametrize("value", [-1, True, 4, "1"])
def test_invalid_input_port_refuses(snapshot, value):
    with pytest.raises(ValueError, match="port"):
        preview(snapshot, input_index=value)


@pytest.mark.parametrize("change,reason", [
    (lambda s: s.update(truncated=True), "complete"),
    (lambda s: s.update(complete=False), "complete"),
    (lambda s: s.update(can_pin=False), "complete"),
    (lambda s: s["warnings"].append("Unobserved edge"), "complete"),
    (lambda s: s["nodes"][2].update(parent="/obj"), "network"),
    (lambda s: s["nodes"][2].update(category="Sop"), "context"),
    (lambda s: s["nodes"].pop(), "Select"),
    (lambda s: s.update(topology_hash=""), "snapshot"),
    (lambda s: s.update(topology_hash="not-a-hash"), "snapshot"),
    (lambda s: s.update(topology_hash={"mutable": []}), "snapshot"),
    (lambda s: s["scene"].update(hip_path=""), "snapshot"),
    (lambda s: s["scene"].update(hip_path=None), "snapshot"),
    (lambda s: s["scene"].update(session_token={"mutable": []}), "snapshot"),
    (lambda s: s["identities"].pop(), "identity"),
])
def test_unsupported_snapshot_fails_with_actionable_reason(snapshot, change, reason):
    change(snapshot)
    with pytest.raises(ValueError, match=reason):
        preview(snapshot)


def test_indirect_wire_and_missing_wire_are_not_treated_as_direct(snapshot):
    wire = snapshot["wires"]["internal"][0]
    wire["source_item"] = "/stage/dot1"
    with pytest.raises(ValueError, match="direct"):
        preview(snapshot)
    with pytest.raises(ValueError, match="observed"):
        build_insertion_preview(snapshot, edge("/stage/source", 0, "/stage/target", 0), "/stage/middle")


def test_cannot_insert_endpoint_into_itself(snapshot):
    with pytest.raises(ValueError, match="different"):
        build_insertion_preview(snapshot, snapshot["wires"]["internal"][0], "/stage/source")
