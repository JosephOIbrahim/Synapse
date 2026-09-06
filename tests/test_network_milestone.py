"""Public-plan regressions for the second SYNAPSE UX milestone."""
import pytest

from synapse.server.handlers_solaris_graph import validate_graph
from synapse.server.solaris_graph_plan import observed_display


@pytest.mark.parametrize("port", [-1, 0.5, True, "1", None])
@pytest.mark.parametrize("field", ["input", "output"])
def test_invalid_connection_port_is_rejected(port, field):
    nodes = [{"id": "a", "type": "null"}, {"id": "b", "type": "null"}]
    valid, errors, _ = validate_graph(nodes, [{"from": "a", "to": "b", field: port}])
    assert not valid and errors


@pytest.mark.parametrize("extra", [{"input": 0}, {}])
def test_two_sources_cannot_claim_the_same_new_target_slot(extra):
    nodes = [{"id": n, "type": "null"} for n in ("a", "b", "m")]
    valid, errors, _ = validate_graph(nodes, [{"from": "a", "to": "m", "input": 0},
                                              {"from": "b", "to": "m", **extra}])
    assert not valid and any("input" in error.lower() for error in errors)


def test_existing_target_can_accept_multiple_implicit_appends():
    nodes = [{"id": "a", "type": "null"}, {"id": "b", "type": "null"},
             {"id": "m", "existing": True, "name": "artist_merge"}]
    assert validate_graph(nodes, [{"from": "a", "to": "m"}, {"from": "b", "to": "m"}])[0]


@pytest.mark.parametrize("nodes", [
    [{"id": "a"}], [{"type": "null"}], [{"id": "a", "type": 4}],
    [{"id": "a", "type": "null", "name": "same"}, {"id": "b", "type": "null", "name": "same"}],
])
def test_invalid_node_specs_return_a_clear_validation_error(nodes):
    valid, errors, _ = validate_graph(nodes, [])
    assert not valid and errors


def test_empty_nodes_cannot_claim_connections():
    assert not validate_graph([], [{"from": "missing", "to": "also_missing"}])[0]


def test_display_without_a_readable_accessor_is_unknown():
    from types import SimpleNamespace
    parent = SimpleNamespace(children=lambda: [SimpleNamespace()])
    assert observed_display(parent) == (None, False)


def test_empty_network_has_no_display_node():
    from types import SimpleNamespace
    assert observed_display(SimpleNamespace(children=lambda: [])) == (None, True)
