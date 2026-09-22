"""Selection observations and pin preconditions; no Houdini or model requests."""
import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from synapse.server import introspection


class Item:
    def __init__(self, path, sid=1):
        self._path, self._sid = path, sid
    def path(self):
        return self._path
    def name(self):
        return self._path.rsplit("/", 1)[-1]
    def sessionId(self):
        return self._sid


class Node(Item):
    def __init__(self, path, sid=1):
        super().__init__(path, sid)
        self.ins, self.outs = [], []
        self.reads = 0
    def type(self):
        return SimpleNamespace(name=lambda: "subnet", category=lambda: SimpleNamespace(name=lambda: "Lop")),
    def inputConnections(self):
        self.reads += 1
        return tuple(self.ins)
    def outputConnections(self):
        return tuple(self.outs)
    def inputs(self):
        if not self.ins:
            return ()
        out = [None] * (1 + max(c.inputIndex() for c in self.ins))
        for c in self.ins:
            out[c.inputIndex()] = c.inputNode()
        return tuple(out)
    def inputNames(self):
        return ("first", "second", "third", "fourth")
    def outputNames(self):
        return ("result", "alternate", "third", "fourth")
    def parms(self):
        raise AssertionError("Topology scan evaluated parameters")
    def geometry(self):
        raise AssertionError("Topology scan requested geometry")
    def stage(self):
        raise AssertionError("Topology scan requested a stage")
    def cook(self):
        raise AssertionError("Topology scan cooked")


def node(path, sid=1):
    value = Node(path, sid)
    value.type = lambda: SimpleNamespace(
        name=lambda: "subnet", category=lambda: SimpleNamespace(name=lambda: "Lop"),
        minNumInputs=lambda: 0, maxNumInputs=lambda: 4, maxNumOutputs=lambda: 4)
    return value


class Wire:
    def __init__(self, source, target, output=0, input=0, item=None, indirect=None):
        self.source, self.target, self.output, self.input = source, target, output, input
        self.item, self.indirect = item, indirect
    def inputNode(self):
        return self.source
    def outputNode(self):
        return self.target
    def inputItem(self):
        return self.item or self.indirect or self.source
    def outputItem(self):
        return self.target
    def subnetIndirectInput(self):
        return self.indirect
    def inputIndex(self):
        return self.input
    def outputIndex(self):
        return self.output
    def inputItemOutputIndex(self):
        return 0 if self.item else self.output


def wire(source, target, output=0, input=0, **kwargs):
    conn = Wire(source, target, output, input, **kwargs)
    target.ins.append(conn)
    if source is not None:
        source.outs.append(conn)
    return conn


@pytest.fixture
def host(monkeypatch):
    values = {name: node("/stage/" + name, i + 10) for i, name in enumerate(("up", "a", "b", "down"))}
    wire(values["up"], values["a"], output=2)
    wire(values["a"], values["b"], output=3, input=1)
    wire(values["b"], values["down"], output=1, input=2)
    native = SimpleNamespace(selectedNodes=Mock(return_value=(values["a"], values["b"])),
                             node=lambda path: next((n for n in values.values() if n.path() == path), None),
                             hipFile=SimpleNamespace(path=lambda: "/project/a.hip"),
                             applicationVersionString=lambda: "22.0.400")
    monkeypatch.setattr(introspection, "hou", native)
    return native, values


def pinned(report):
    return {"node_paths": [row["path"] for row in report["identities"]],
            "expected_identities": report["identities"], "expected_scene": report["scene"]}


def test_default_is_topology_only_and_exact(host):
    result = introspection.inspect_selection()
    assert result["schema"] == "synapse-selection-v1"
    assert result["complete"] and result["can_pin"]
    assert result["selected_count"] == result["observed_count"] == 2
    assert result["omitted_count"] == 0 and not result["truncated"]
    for category, expected in (("entering", ("up", 2, "a", 0)),
                               ("internal", ("a", 3, "b", 1)),
                               ("leaving", ("b", 1, "down", 2))):
        edge = result["wires"][category][0]
        assert (edge["source"].split("/")[-1], edge["source_output"],
                edge["target"].split("/")[-1], edge["target_input"]) == expected
    assert ["a", "b", 1] in result["topology"]
    assert result["nodes"][1]["connections"]["inputs"][0]["output_index"] == 3
    assert result["limits"]["max_nodes"] == 200


def test_explicit_detail_opt_ins(host, monkeypatch):
    parms = Mock(return_value={"scale": 2})
    geometry = Mock(return_value={"points": 8})
    monkeypatch.setattr(introspection, "_modified_parms", parms)
    monkeypatch.setattr(introspection, "_geometry_summary", geometry)
    result = introspection.inspect_selection(include_parameters=True, include_geometry=True)
    assert parms.call_count == geometry.call_count == 2
    assert result["nodes"][0]["modified_parms"] == {"scale": 2}
    assert result["nodes"][0]["geometry"] == {"points": 8}


def test_selection_cap_is_explicit_and_cannot_pin_partial(host):
    native, _ = host
    native.selectedNodes.return_value = tuple(node("/stage/n" + str(i), i + 100) for i in range(51))
    result = introspection.inspect_selection(max_nodes=50)
    assert (result["selected_count"], result["observed_count"], result["omitted_count"]) == (51, 50, 1)
    assert result["truncated"] and not result["complete"] and not result["can_pin"]


def test_pin_is_independent_of_subsequent_live_selection(host):
    native, values = host
    first = introspection.inspect_selection()
    native.selectedNodes.return_value = (values["down"],)
    native.selectedNodes.reset_mock()
    second = introspection.inspect_selection(**pinned(first), expected_topology_hash=first["topology_hash"])
    native.selectedNodes.assert_not_called()
    assert second["identities"] == first["identities"]
    assert second["topology_hash"] == first["topology_hash"]


@pytest.mark.parametrize("change", ["replace", "delete", "rename", "scene", "session"])
def test_pin_rejects_stale_identity_or_scene(host, change):
    native, values = host
    payload = pinned(introspection.inspect_selection())
    if change == "replace":
        values["a"] = node("/stage/a", 999)
    elif change == "delete":
        values.pop("a")
    elif change == "rename":
        values["a"]._path = "/stage/new_name"
    elif change == "scene":
        native.hipFile.path = lambda: "/project/b.hip"
    else:
        payload["expected_scene"]["session_token"] = "old-process"
    with pytest.raises(ValueError, match="SELECTION_STALE"):
        introspection.inspect_selection(**payload)


def test_topology_precondition_rejects_changed_source_output(host):
    _, values = host
    first = introspection.inspect_selection()
    values["b"].ins[0].output = 2
    with pytest.raises(ValueError, match="SELECTION_STALE"):
        introspection.inspect_selection(**pinned(first), expected_topology_hash=first["topology_hash"])
    current = introspection.inspect_selection(**pinned(first))
    assert current["topology_hash"] != first["topology_hash"]


@pytest.mark.parametrize("surface", ["capacity", "names", "data_types"])
def test_topology_precondition_includes_observed_port_contract(host, surface):
    _, values = host
    first = introspection.inspect_selection()
    target = values["a"]
    if surface == "capacity":
        old = target.type()
        old.maxNumInputs = lambda: 8
        target.type = lambda: old
    elif surface == "names":
        target.inputNames = lambda: ("different",)
    else:
        target.inputDataTypes = lambda: ("float",)
    with pytest.raises(ValueError, match="SELECTION_STALE"):
        introspection.inspect_selection(**pinned(first), expected_topology_hash=first["topology_hash"])


def test_empty_selection_is_not_whole_scene(host):
    host[0].selectedNodes.return_value = ()
    result = introspection.inspect_selection()
    assert result["count"] == result["selected_count"] == 0
    assert result["nodes"] == [] and not result["can_pin"]
    assert result["wires"] == {"internal": [], "entering": [], "leaving": []}


@pytest.mark.parametrize("payload", [
    {"depth": True}, {"depth": -1}, {"max_nodes": 501}, {"max_edges": 5001},
    {"node_paths": ["../stage/a"]}, {"node_paths": ["/stage/a", "/stage/a"]},
    {"expected_identities": [{"path": "/stage/a", "session_id": 11}]},
    {"node_paths": ["/stage/a"], "expected_identities": []},
    {"include_geometry": "false"}, {"expected_topology_hash": "not-a-hash"},
])
def test_invalid_requests_refuse(host, payload):
    with pytest.raises(ValueError, match="SELECTION_INVALID"):
        introspection.inspect_selection(**payload)


def test_shared_upstream_traversal_deduplicates_and_is_bounded(host):
    native, values = host
    left, right = node("/stage/left", 90), node("/stage/right", 91)
    wire(values["up"], left)
    wire(values["up"], right)
    wire(left, values["a"], input=1)
    wire(right, values["b"], input=2)
    result = introspection.inspect_selection(depth=5, max_nodes=4)
    traversal = result["traversal"]
    paths = [row["path"] for row in traversal["nodes"]]
    assert len(paths) == len(set(paths))
    assert result["observed_count"] + traversal["observed_count"] <= 4
    assert traversal["truncated"]
    assert traversal["omitted_count"] is None
    assert traversal["known_omitted_count"] >= 1


def test_edge_limit_never_claims_complete(host):
    result = introspection.inspect_selection(max_edges=1)
    assert sum(len(rows) for rows in result["wires"].values()) <= 1
    assert result["truncated"] and not result["complete"] and not result["can_pin"]


def test_indirect_and_dot_items_are_preserved(host):
    native, values = host
    indirect = Item("/stage/sub/input0", 601)
    dot = Item("/stage/dot1", 602)
    values["a"].ins.clear()
    wire(None, values["a"], indirect=indirect)
    values["b"].ins[0].item = dot
    result = introspection.inspect_selection()
    edge = result["wires"]["entering"][0]
    assert edge["source"] == indirect.path()
    assert edge["source_kind"] == "subnet_input"
    internal = result["wires"]["internal"][0]
    assert internal["source"] == "/stage/a"
    assert internal["source_item"] == dot.path()
    assert internal["source_item_output"] == 0


def test_unreadable_connection_is_unknown_not_empty(host):
    _, values = host
    values["a"].inputConnections = Mock(side_effect=RuntimeError("unreadable"))
    result = introspection.inspect_selection()
    assert not result["complete"] and not result["can_pin"]
    assert result["warnings"]
    assert result["omitted_edge_count"] is None


def test_session_token_survives_module_reload(host):
    first = introspection.inspect_selection()
    from synapse.server import selection_snapshot
    importlib.reload(selection_snapshot)
    second = introspection.inspect_selection()
    assert first["scene"]["session_token"] == second["scene"]["session_token"]


def test_ports_unknown_are_not_zero(host):
    _, values = host
    values["a"].type = lambda: SimpleNamespace(name=lambda: "unknown",
                                               category=lambda: SimpleNamespace(name=lambda: "Lop"))
    result = introspection.inspect_selection()
    assert result["nodes"][0]["ports"]["max_inputs"] is None


def test_explicit_empty_paths_never_fall_back_to_live_selection(host):
    result = introspection.inspect_selection(node_paths=[])
    host[0].selectedNodes.assert_not_called()
    assert result["selection_source"] == "pinned" and result["selected_count"] == 0


def test_intermediate_dot_identity_is_preserved_and_hashed(host):
    native, values = host
    a, b = values["a"], values["b"]
    dot1, dot2 = Item("/stage/dot1", 800), Item("/stage/dot2", 801)
    first = Wire(a, None)
    first.outputItem = lambda: dot1
    middle = Wire(a, None, item=dot1)
    middle.outputItem = lambda: dot2
    last = Wire(a, b, input=1, item=dot2)
    dot1.outputConnections = lambda: (middle,)
    dot2.outputConnections = lambda: (last,)
    a.outs = [first]
    b.ins = [last]
    result = introspection.inspect_selection()
    assert result["complete"]
    assert len(result["wires"]["internal"]) == 1
    assert any(edge["target_item"] == "/stage/dot1" for edge in result["item_wires"])
    dot1._sid = 999
    with pytest.raises(ValueError, match="SELECTION_STALE"):
        introspection.inspect_selection(**pinned(result), expected_topology_hash=result["topology_hash"])


def test_disagreeing_connection_observations_cannot_pin(host):
    _, values = host
    values["a"].outs = [Wire(values["a"], values["b"], output=1, input=1)]
    result = introspection.inspect_selection()
    assert not result["complete"] and not result["can_pin"]


def test_equal_hom_item_wrappers_do_not_change_topology_hash(host):
    _, values = host
    values["b"].ins[0].output = 0
    first = introspection.inspect_selection()
    # HOM may return a new Python wrapper for the same native item. Python
    # object identity is not the network item identity used by the contract.
    values["b"].ins[0].item = Item(values["a"].path(), values["a"].sessionId())
    second = introspection.inspect_selection(**pinned(first), expected_topology_hash=first["topology_hash"])
    assert second["topology_hash"] == first["topology_hash"]


def test_pin_rechecks_identity_after_explicit_details(host, monkeypatch):
    _, values = host
    first = introspection.inspect_selection()
    def detail(n):
        values["a"]._sid = 991
        return {}
    monkeypatch.setattr(introspection, "_modified_parms", detail)
    with pytest.raises(ValueError, match="SELECTION_STALE"):
        introspection.inspect_selection(**pinned(first), include_parameters=True)


def test_handler_keeps_main_thread_dispatch_and_forwards_fields(monkeypatch):
    from synapse.server import handlers, main_thread
    capture = {}
    monkeypatch.setattr(handlers, "HOU_AVAILABLE", True)
    def run(fn, **kwargs):
        capture["dispatch"] = kwargs
        return fn()
    monkeypatch.setattr(main_thread, "run_on_main", run)
    monkeypatch.setattr(introspection, "inspect_selection", lambda **kwargs: capture.setdefault("payload", kwargs))
    obj = handlers.SynapseHandler.__new__(handlers.SynapseHandler)
    obj._handle_inspect_selection({"node_paths": ["/stage/a"], "max_nodes": 50})
    assert capture["dispatch"]["label"] == "handlers:_handle_inspect_selection"
    assert capture["payload"]["node_paths"] == ["/stage/a"]
    assert capture["payload"]["include_geometry"] is False
    assert capture["payload"]["depth"] == 0
