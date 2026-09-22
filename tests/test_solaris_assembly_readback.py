"""Assembly receipts must describe observed wires, including the source port."""
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from synapse.core.errors import SynapseUserError
from synapse.server import handlers_solaris_assemble as assembly
from synapse.server import main_thread


class Node:
    def __init__(self, name, parent=None):
        self._name, self._parent = name, parent
        self.links = {}
        self.siblings = []
        self.writes = []
        self.corrupt = None
        if parent is not None:
            parent.siblings.append(self)

    def path(self):
        return (self._parent.path() + "/" if self._parent else "/") + self._name

    def name(self):
        return self._name

    def parent(self):
        return self._parent

    def children(self):
        return tuple(self.siblings)

    def type(self):
        return SimpleNamespace(name=lambda: "null", maxNumOutputs=lambda: 2,
                               maxNumInputs=lambda: 1)

    def inputs(self):
        return tuple(self.links[i][0] if i in self.links else None
                     for i in range(max(self.links, default=-1) + 1))

    def outputs(self):
        return tuple(n for n in self._parent.children()
                     if any(source is self for source, _ in n.links.values()))

    def inputConnections(self):
        return tuple(SimpleNamespace(inputIndex=lambda i=i: i,
                                     inputNode=lambda source=source: source,
                                     outputIndex=lambda output=output: output,
                                     subnetIndirectInput=lambda: None)
                     for i, (source, output) in self.links.items())

    def setInput(self, index, source, output=0):
        self.writes.append((index, source, output))
        if self.corrupt == "ignored":
            return
        if self.corrupt == "wrong_output":
            output = 1
        elif self.corrupt == "wrong_source":
            source = self
        elif self.corrupt == "unresolved":
            source = None
        self.links[index] = (source, output)

    def position(self):
        return (0, 0)


@pytest.fixture
def scene(monkeypatch):
    stage = Node("stage")
    a, b = Node("a", stage), Node("b", stage)
    nodes = {n.path(): n for n in (stage, a, b)}
    undos = []
    monkeypatch.setattr(assembly, "HOU_AVAILABLE", True)
    monkeypatch.setattr(assembly, "hou", SimpleNamespace(
        node=nodes.get,
        undos=SimpleNamespace(group=lambda name: nullcontext(),
                              areEnabled=lambda: False, undoLabels=lambda: (),
                              performUndo=lambda: undos.append(True))), raising=False)
    monkeypatch.setattr(main_thread, "run_on_main", lambda fn, **kwargs: fn())
    monkeypatch.setattr(assembly, "_free_origin", lambda *a: (0, 0))
    monkeypatch.setattr(assembly, "_layout_vertical_chain", lambda *a, **k: None)
    payload = {"parent": "/stage", "mode": "nodes", "sort": False,
               "nodes": ["/stage/a", "/stage/b"]}
    run = lambda **changes: assembly.SolarisAssembleMixin()._handle_solaris_assemble_chain(
        {**payload, **changes})
    return a, b, run, undos


@pytest.mark.parametrize("failure", ["ignored", "wrong_output", "wrong_source", "unresolved"])
def test_unobserved_connection_is_never_reported_as_wired(scene, failure):
    _a, b, run, undos = scene
    b.corrupt = failure
    with pytest.raises(SynapseUserError, match="[Ii]nput|[Cc]onnection"):
        run()
    assert undos == []  # Headless/disabled undo must not consume unrelated history.


def test_success_receipt_matches_source_and_output_then_repeat_is_quiet(scene):
    a, b, run, _ = scene
    result = run()
    wire, = result["wired"]
    actual, = b.inputConnections()
    assert wire["from"] == actual.inputNode().path() == a.path()
    assert wire["input"] == actual.inputIndex()
    assert wire["output"] == actual.outputIndex() == 0
    assert result["verification"]["connections"] == "verified"
    assert run()["wired"] == []
    assert len(b.writes) == 1


def test_preview_does_not_read_a_write_or_claim_verification(scene):
    _a, b, run, _ = scene
    b.corrupt = "ignored"
    result = run(dry_run=True)
    assert result["wired"][0]["output"] == 0
    assert result["verification"]["connections"] == "planned"
    assert b.links == {} and b.writes == []


def test_existing_nonzero_output_remains_untouched(scene):
    a, b, run, _ = scene
    b.links[0] = (a, 1)
    assert run()["wired"] == []
    assert b.links[0] == (a, 1)
    assert b.writes == []


def test_later_layout_callback_cannot_stale_a_verified_receipt(scene, monkeypatch):
    a, b, run, _ = scene
    monkeypatch.setattr(assembly, "_layout_vertical_chain",
                        lambda *args, **kwargs: b.links.update({0: (a, 1)}))
    with pytest.raises(SynapseUserError, match="[Cc]onnection"):
        run()
