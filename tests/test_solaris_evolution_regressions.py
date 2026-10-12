"""Seven Solaris regressions using synthetic HOM doubles, never native USD.

The validator, planner and build handler remain intact. Only the host boundary,
main-thread dispatch, update-mode context and free-area query are substituted.
Undo below models one independent group; it does not qualify native recovery.
"""
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest

from synapse.core.errors import SynapseUserError
from synapse.server import handlers_solaris_graph as graph
from synapse.server import main_thread, update_mode
from synapse.server.solaris_graph_plan import observed_inputs, resolve_plan


class _Type:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name

    def category(self):
        return SimpleNamespace(name=lambda: "Lop")

    def maxNumInputs(self):
        return 8 if self._name == "merge" else 1

    def maxNumOutputs(self):
        return 2 if self._name == "test_source" else 1

    def hasUnorderedInputs(self):
        return False


class _Node:
    def __init__(self, scene, name, type_name="null"):
        self.scene, self._name, self.type_name = scene, name, type_name
        self.links, self.values = {}, {"gain": 0}
        self.pos, self.comment, self.flags, self.display = (9, 9), "", {}, False

    def name(self):
        return self._name

    def path(self):
        return self.scene.path() + "/" + self._name

    def parent(self):
        return self.scene

    def type(self):
        return self.scene.types[self.type_name]

    def inputConnections(self):
        if self.scene.unreadable == self.path():
            raise RuntimeError("synthetic final socket observation unavailable")
        return tuple(SimpleNamespace(
            inputIndex=lambda index=index: index,
            inputNode=lambda source=source: source,
            outputIndex=lambda output=output: output,
            subnetIndirectInput=lambda: None,
        ) for index, (source, output) in sorted(self.links.items()))

    def setInput(self, index, source, output=0):
        self.scene.writes.append(("wire", self.path(), index, source.path(), output))
        self.links[index] = (source, output)

    def parm(self, name):
        if name not in self.values:
            return None

        def set_value(value):
            self.scene.writes.append(("parm", self.path(), name, value))
            self.values[name] = value

        return SimpleNamespace(eval=lambda: self.values[name], set=set_value)

    def parmTuple(self, name):
        return None

    def position(self):
        return self.pos

    def setPosition(self, value):
        self.scene.writes.append(("position", self.path()))
        self.pos = tuple(value)
        self.scene.callback("layout")

    def setComment(self, value):
        self.scene.writes.append(("comment", self.path()))
        self.comment = value

    def setGenericFlag(self, flag, value):
        self.scene.writes.append(("flag", self.path()))
        self.flags[flag] = value

    def isDisplayFlagSet(self):
        return self.display

    def setDisplayFlag(self, value):
        self.scene.writes.append(("display", self.path()))
        for node in self.scene.children():
            node.display = bool(value and node is self)
        self.scene.callback("display")

    def cook(self, force=False):
        self.scene.callback("cook")

    def errors(self):
        return ()

    def warnings(self):
        return ()


class _Scene:
    """A tiny synthetic network with explicitly modeled mutation and undo."""
    def __init__(self):
        self.types = {name: _Type(name) for name in ("null", "merge", "test_source")}
        self.nodes, self.writes = {}, []
        self.undo_enabled, self.undo_calls, self.groups = True, 0, 0
        self.history = [("Unrelated artist edit", None)]
        self.fault, self.fault_observed, self.unreadable = None, None, None
        self.add("unrelated").comment = "artist comment"

    def path(self):
        return "/stage/evolution_test"

    def childTypeCategory(self):
        return SimpleNamespace(name=lambda: "Lop")

    def children(self):
        return tuple(self.nodes.values())

    def node(self, name):
        return self.nodes.get(name)

    def lookup(self, path):
        if path == self.path():
            return self
        return next((node for node in self.children() if node.path() == path), None)

    def add(self, name, type_name="null"):
        node = _Node(self, name, type_name)
        self.nodes[name] = node
        return node

    def createNode(self, type_name, name):
        assert name not in self.nodes, "synthetic host must not auto-rename collisions"
        self.writes.append(("create", name))
        return self.add(name, type_name)

    def snapshot(self):
        return {name: (node.type_name,
                       {i: (source.name(), output) for i, (source, output) in node.links.items()},
                       deepcopy(node.values), node.pos, node.comment,
                       deepcopy(node.flags), node.display)
                for name, node in self.nodes.items()}

    def restore(self, snapshot):
        self.nodes = {name: _Node(self, name, row[0]) for name, row in snapshot.items()}
        for name, row in snapshot.items():
            node = self.nodes[name]
            node.links = {i: (self.nodes[source], output) for i, (source, output) in row[1].items()}
            node.values, node.pos, node.comment, node.flags, node.display = deepcopy(row[2:])
        self.unreadable = None

    @contextmanager
    def group(self, label):
        self.groups += 1
        before = self.snapshot()
        try:
            yield
        finally:
            if self.undo_enabled and self.snapshot() != before:
                self.history.append((label, before))

    def undo(self):
        assert len(self.history) > 1, "must never consume unrelated artist history"
        self.undo_calls += 1
        self.restore(self.history.pop()[1])

    def callback(self, phase):
        if not self.fault or self.fault_observed or self.fault[0] != phase:
            return
        source, target = self.node("source"), self.node("sink")
        if source is None or target is None or target.links.get(0) != (source, 1):
            return
        # Corrupt only AFTER an exact requested socket has actually landed.
        self.fault_observed = (phase, source.path(), target.path(), 0, 1)
        kind = self.fault[1]
        if kind == "wrong_output":
            target.links[0] = (source, 0)
        elif kind == "wrong_source":
            target.links[0] = (self.node("unrelated"), 0)
        elif kind == "disconnected":
            del target.links[0]
        elif kind == "unreadable":
            self.unreadable = target.path()
        else:
            raise AssertionError("unknown synthetic fault")

    def run(self, payload):
        return graph.SolarisGraphMixin()._handle_solaris_build_graph(
            {"parent": self.path(), "frame": False, "sections": False, **payload})

    def plan(self, nodes, connections):
        valid, errors, _ = graph.validate_graph(nodes, connections)
        assert valid, errors
        node_map = {node["id"]: node for node in nodes}
        return resolve_plan(self, node_map, graph.topo_sort(set(node_map), connections),
                            connections, graph.hou, graph._resolve_existing_node)


@pytest.fixture
def scene(monkeypatch):
    scene = _Scene()
    host = SimpleNamespace(
        node=scene.lookup, LopNode=_Node,
        nodeType=lambda category, name: scene.types.get(name),
        preferredNodeType=lambda name, parent: scene.types.get(name.split("/")[-1]),
        Vector2=lambda *xy: tuple(xy), nodeFlag=SimpleNamespace(DisplayComment="comment"),
        undos=SimpleNamespace(group=scene.group, areEnabled=lambda: scene.undo_enabled,
                              undoLabels=lambda: tuple(label for label, _ in scene.history),
                              performUndo=scene.undo),
    )

    @contextmanager
    def sandwich(**kwargs):
        yield SimpleNamespace(note_estimate=lambda count: None)

    # Do not replace sys.modules['hou'] or change the shared conftest fake.
    monkeypatch.setattr(graph, "hou", host, raising=False)
    monkeypatch.setattr(graph, "HOU_AVAILABLE", True)
    monkeypatch.setattr(main_thread, "run_on_main", lambda fn, **kwargs: fn())
    monkeypatch.setattr(update_mode, "cook_sandwich", sandwich)
    monkeypatch.setattr(graph, "_free_origin", lambda *args: (0, 0))
    return scene


def _request():
    return {"nodes": [{"id": "source", "type": "test_source"},
                      {"id": "sink", "type": "null", "parms": {"gain": 2.5}}],
            "connections": [{"from": "source", "to": "sink", "input": 0, "output": 1}],
            "display_node": "sink"}


@pytest.mark.parametrize("prior_output,output", [(1, 0), (1, 1), (0, 0)])
def test_insert_preserves_displaced_output_socket_before_mutation(scene, prior_output, output):
    source, target = scene.add("source", "test_source"), scene.add("target")
    target.links[0] = (source, prior_output)
    nodes = [{"id": "a", "existing": True, "name": "source"},
             {"id": "b", "existing": True, "name": "target"},
             {"id": "inserted", "type": "null"}]
    wires = [{"from": "a", "to": "inserted", "output": output},
             {"from": "inserted", "to": "b", "input": 0, "insert": True}]
    before, request_before = scene.snapshot(), deepcopy((nodes, wires))
    if output != prior_output:
        with pytest.raises(SynapseUserError, match="cut.*output 1"):
            scene.plan(nodes, wires)
    else:
        plan = scene.plan(nodes, wires)
        inserted = next(link for link in plan["connections"] if link["to_id"] == "b")
        assert inserted["displaced"] == source.path()
        assert inserted["input"] == 0
    assert scene.snapshot() == before
    assert scene.writes == [] and scene.groups == 0
    assert (nodes, wires) == request_before


@pytest.mark.parametrize("implicit_first", [True, False])
def test_existing_merge_implicit_wire_respects_reserved_explicit_slot(scene, implicit_first):
    source, target = scene.add("source", "test_source"), scene.add("target", "merge")
    target.links[0] = (source, 1)
    nodes = [{"id": "a", "existing": True, "name": "source"},
             {"id": "b", "existing": True, "name": "target"},
             {"id": "inserted", "type": "null"}]
    implicit = {"from": "a", "to": "b", "output": 1}
    explicit = {"from": "inserted", "to": "b", "input": 0, "insert": True}
    wires = [{"from": "a", "to": "inserted", "output": 1}]
    wires.extend([implicit, explicit] if implicit_first else [explicit, implicit])
    before, request_before = scene.snapshot(), deepcopy((nodes, wires))
    plan = scene.plan(nodes, wires)
    actual = {(link["from_id"], link["to_id"], link["input"], link["output"])
              for link in plan["connections"]}
    assert actual == {("a", "inserted", 0, 1), ("inserted", "b", 0, 0), ("a", "b", 1, 1)}
    assert scene.snapshot() == before
    assert scene.writes == [] and scene.groups == 0
    assert (nodes, wires) == request_before


@pytest.mark.parametrize("display", [[], {}, False, 0])
@pytest.mark.parametrize("empty", [True, False])
def test_display_selector_rejects_non_strings_even_on_empty_graphs(scene, display, empty):
    nodes = [] if empty else [{"id": "source", "type": "null"}]
    before = deepcopy((nodes, display))
    valid, errors, warnings = graph.validate_graph(nodes, [], display)
    assert valid is False
    assert any("display_node" in error for error in errors)
    assert isinstance(warnings, list)
    scene_before = scene.snapshot()
    with pytest.raises(SynapseUserError, match="display_node"):
        scene.run({"nodes": nodes, "connections": [], "display_node": display})
    assert scene.snapshot() == scene_before
    assert scene.writes == [] and scene.groups == 0
    assert (nodes, display) == before


@pytest.mark.parametrize("display,valid", [(None, True), ("source", True), ("missing", False)])
def test_display_selector_keeps_valid_and_unknown_string_behavior(display, valid):
    result, errors, _ = graph.validate_graph([{"id": "source", "type": "null"}], [], display)
    assert result is valid
    assert bool(errors) is (not valid)


@pytest.mark.parametrize("indices,warns", [([4, 5], False), ([0, 2], True), ([0, 0], True)])
def test_input_gap_warning_preserves_contiguity_and_duplicate_behavior(indices, warns):
    wires = [{"from": str(i), "to": "merge", "input": index} for i, index in enumerate(indices)]
    assert bool(graph._check_merge_input_gaps(wires)) is warns


def test_sparse_gap_diagnostic_is_bounded_but_does_not_admit_nonexistent_port(scene):
    # The former list(range(...)) overflows before allocation at this span.
    huge = 2 ** 100
    nodes = [{"id": "a", "type": "null"}, {"id": "b", "type": "null"},
             {"id": "merge", "type": "merge"}]
    wires = [{"from": "a", "to": "merge", "input": 0},
             {"from": "b", "to": "merge", "input": huge}]
    before = deepcopy((nodes, wires))
    valid, errors, warnings = graph.validate_graph(nodes, wires)
    assert valid and errors == []
    assert len(warnings) == 1 and str(huge) in warnings[0]
    assert len(warnings[0].encode("utf-8")) < 512
    with pytest.raises(SynapseUserError, match="input|[Pp]ort"):
        scene.plan(nodes, wires)
    assert scene.writes == [] and scene.groups == 0
    assert (nodes, wires) == before


@pytest.mark.parametrize("dry_run", [None, 0, "", [], {}, "false"])
def test_malformed_preview_control_rejects_before_any_host_mutation(scene, dry_run):
    payload = {**_request(), "dry_run": dry_run}
    before, request_before = scene.snapshot(), deepcopy(payload)
    with pytest.raises(SynapseUserError, match="dry_run.*boolean"):
        scene.run(payload)
    assert scene.snapshot() == before
    assert scene.writes == [] and scene.groups == 0 and scene.undo_calls == 0
    assert payload == request_before


@pytest.mark.parametrize("parms", [None, [], "", 0])
def test_managed_parameter_map_rejects_before_mutation_or_undo(scene, parms):
    payload = _request()
    payload["nodes"][1]["parms"] = parms
    before, request_before = scene.snapshot(), deepcopy(payload)
    with pytest.raises(SynapseUserError, match="parms.*object"):
        scene.run(payload)
    assert scene.snapshot() == before
    assert scene.writes == [] and scene.groups == 0 and scene.undo_calls == 0
    assert payload == request_before


def test_existing_parameter_metadata_is_ignored_and_managed_dictionary_applies(scene):
    artist = scene.add("artist", "test_source")
    artist.values["gain"], artist.comment = 7, "keep artist metadata"
    payload = {"nodes": [{"id": "source", "existing": True, "name": "artist", "parms": []},
                         {"id": "sink", "type": "null", "parms": {"gain": 2.5}}],
               "connections": [{"from": "source", "to": "sink", "output": 1}],
               "display_node": "sink"}
    artist_before, request_before = scene.snapshot()["artist"], deepcopy(payload)
    result = scene.run(payload)
    assert result["verification"]["parameters"] == "applied"
    assert scene.node("sink").values["gain"] == 2.5
    assert scene.snapshot()["artist"] == artist_before
    assert not any(write[0] == "parm" and write[1] == artist.path() for write in scene.writes)
    assert payload == request_before


def test_preview_then_apply_then_repeat_receipts_match_observed_sockets(scene):
    payload = _request()
    before, request_before = scene.snapshot(), deepcopy(payload)
    preview = scene.run({**payload, "dry_run": True})
    assert preview["status"] == "preview" and preview["dry_run"] is True
    assert preview["planned_connections"] == preview["connections_made"]
    assert "verification" not in preview
    assert scene.snapshot() == before and scene.writes == [] and scene.groups == 0
    result = scene.run({**payload, "dry_run": False})
    expected = [{"from": scene.node("source").path(), "to": scene.node("sink").path(),
                 "input": 0, "output": 1}]
    assert result["connections_made"] == expected
    assert observed_inputs(scene.node("sink")) == {0: (expected[0]["from"], 1)}
    assert result["verification"]["connections"] == "verified"
    applied, wires = scene.snapshot(), [w for w in scene.writes if w[0] == "wire"]
    repeated = scene.run(payload)
    assert repeated["status"] == "unchanged"
    assert repeated["connections_made"] == expected
    assert scene.snapshot() == applied
    assert [w for w in scene.writes if w[0] == "wire"] == wires
    assert scene.snapshot()["unrelated"] == before["unrelated"]
    assert payload == request_before


@pytest.mark.parametrize("phase,kind,undo_enabled", [
    ("layout", "wrong_output", True),
    ("display", "disconnected", True),
    ("cook", "wrong_source", True),
    ("cook", "unreadable", True),
    ("layout", "wrong_output", False),
])
def test_later_callback_cannot_leave_a_stale_verified_wire_receipt(scene, phase, kind, undo_enabled):
    scene.fault, scene.undo_enabled = (phase, kind), undo_enabled
    payload = _request()
    before, history_before, request_before = scene.snapshot(), list(scene.history), deepcopy(payload)
    with pytest.raises(SynapseUserError, match="[Ff]inal connection"):
        scene.run(payload)
    assert scene.fault_observed == (phase, scene.path() + "/source", scene.path() + "/sink", 0, 1)
    assert scene.undo_calls == int(undo_enabled)
    assert scene.history == history_before
    if undo_enabled:
        assert scene.snapshot() == before  # Modeled recovery, not native undo proof.
    else:
        assert scene.snapshot() != before  # No rollback is invented with undo disabled.
    assert scene.snapshot()["unrelated"] == before["unrelated"]
    assert payload == request_before
