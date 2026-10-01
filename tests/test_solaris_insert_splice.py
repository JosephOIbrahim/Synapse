"""Insert-between for the Oct 7 demo (DIAG C1-C5).

C1 resolve_plan honors an opt-in ``insert: true`` splice: a wire may replace an
   occupied input only when the displaced node is in the graph AND feeds the
   new source through the planned wires (re-route, never cut).
C5 the panel worker says something when the token cap ends a turn silently.

The planner fakes below are plain classes exposing only the methods
resolve_plan / observed_inputs / _reject_live_cycles call on real hou objects.
"""
import os
import sys
from unittest.mock import MagicMock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from synapse.core.errors import SynapseUserError  # noqa: E402
from synapse.server.solaris_graph_plan import resolve_plan  # noqa: E402
from synapse.server.handlers_solaris_graph import validate_graph, topo_sort  # noqa: E402


class _Category:
    def name(self):
        return "Lop"


class _Type:
    def __init__(self, name, inputs=1):
        self._name, self._inputs = name, inputs

    def name(self):
        return self._name

    def __eq__(self, other):   # hou.NodeType compares by identity of the type
        return isinstance(other, _Type) and other._name == self._name

    def __hash__(self):
        return hash(self._name)

    def maxNumInputs(self):
        return self._inputs

    def maxNumOutputs(self):
        return 1

    def hasUnorderedInputs(self):
        return False

    def category(self):
        return _Category()


class _Conn:
    def __init__(self, index, source):
        self._index, self._source = index, source

    def inputNode(self):
        return self._source

    def subnetIndirectInput(self):
        return None

    def inputIndex(self):
        return self._index

    def outputIndex(self):
        return 0


class _LiveNode:
    def __init__(self, parent, name, type_name, inputs=()):
        self._parent, self._name, self._type = parent, name, _Type(type_name)
        self._inputs = list(inputs)

    def path(self):
        return "/stage/" + self._name

    def parent(self):
        return self._parent

    def type(self):
        return self._type

    def inputConnections(self):
        return [_Conn(i, src) for i, src in enumerate(self._inputs) if src is not None]


class _Parent:
    def __init__(self):
        self.children = {}

    def path(self):
        return "/stage"

    def node(self, name):
        return self.children.get(name)

    def childTypeCategory(self):
        return _Category()


class _Hou:
    def __init__(self, parent):
        self._parent = parent

    def preferredNodeType(self, name, parent):
        return _Type(name.split("/")[-1])

    def node(self, path):
        return self._parent.children.get(path.rsplit("/", 1)[-1])


def _demo():
    """ground -> look_fade_10 -> demo_dome (dome has ONE input, occupied)."""
    parent = _Parent()
    ground = _LiveNode(parent, "ground", "sopimport")
    look = _LiveNode(parent, "look_fade_10", "edit", [ground])
    dome = _LiveNode(parent, "demo_dome", "domelight::3.0", [look])
    for n in (ground, look, dome):
        parent.children[n._name] = n
    return parent


def _plan(parent, nodes, connections):
    valid, errors, _ = validate_graph(nodes, connections)
    assert valid, errors
    node_map = {n["id"]: n for n in nodes}
    order = topo_sort(set(node_map), connections)
    return resolve_plan(parent, node_map, order, connections, _Hou(parent),
                        lambda p, spec: p.node(spec["name"]))


_NODES = [
    {"id": "look", "existing": True, "name": "look_fade_10"},
    {"id": "key", "type": "distantlight", "name": "dusk_key"},
    {"id": "rim", "type": "distantlight", "name": "dusk_rim"},
    {"id": "dome", "existing": True, "name": "demo_dome"},
]


def _links(insert=True):
    last = {"from": "rim", "to": "dome", "input": 0}
    if insert is not None:
        last["insert"] = insert
    return [{"from": "look", "to": "key"}, {"from": "key", "to": "rim"}, last]


class TestSplice:
    def test_insert_between_existing_nodes_is_planned(self):
        plan = _plan(_demo(), _NODES, _links())
        wire = [c for c in plan["connections"] if c["to"] == "/stage/demo_dome"]
        assert wire == [{"from_id": "rim", "to_id": "dome", "from": "/stage/dusk_rim",
                         "to": "/stage/demo_dome", "input": 0, "output": 0, "changed": True,
                         "displaced": "/stage/look_fade_10"}]
        assert all(c["displaced"] is None for c in plan["connections"] if c["to"] != "/stage/demo_dome")

    def test_without_insert_the_occupied_input_is_still_refused(self):
        with pytest.raises(SynapseUserError, match="already connected"):
            _plan(_demo(), _NODES, _links(insert=None))

    def test_insert_false_is_refused_like_no_flag(self):
        with pytest.raises(SynapseUserError, match="already connected"):
            _plan(_demo(), _NODES, _links(insert=False))

    def test_displaced_node_outside_the_graph_is_never_cut(self):
        nodes = [{"id": "ground", "existing": True, "name": "ground"}] + _NODES[1:]
        links = [{"from": "ground", "to": "key"}, {"from": "key", "to": "rim"},
                 {"from": "rim", "to": "dome", "input": 0, "insert": True}]
        with pytest.raises(SynapseUserError, match="already connected"):
            _plan(_demo(), nodes, links)

    def test_displaced_node_in_graph_but_not_upstream_is_a_cut(self):
        nodes = [{"id": "ground", "existing": True, "name": "ground"}] + _NODES
        links = [{"from": "ground", "to": "key"}, {"from": "key", "to": "rim"},
                 {"from": "rim", "to": "dome", "input": 0, "insert": True}]
        with pytest.raises(SynapseUserError, match="would cut /stage/look_fade_10"):
            _plan(_demo(), nodes, links)

    def test_rerun_after_splice_is_a_noop(self):
        parent = _demo()
        rim = _LiveNode(parent, "dusk_rim", "distantlight")
        parent.children["dusk_rim"] = rim
        parent.children["demo_dome"]._inputs = [rim]
        key = _LiveNode(parent, "dusk_key", "distantlight", [parent.children["look_fade_10"]])
        parent.children["dusk_key"] = key
        rim._inputs = [key]
        plan = _plan(parent, _NODES, _links())
        assert not any(c["changed"] for c in plan["connections"])

    def test_validate_rejects_non_boolean_insert(self):
        links = _links()
        links[-1]["insert"] = "yes"
        valid, errors, _ = validate_graph(_NODES, links)
        assert not valid and any("insert must be a boolean" in e for e in errors)


class TestRegistryAndPrompt:
    def test_connection_schema_documents_insert(self):
        reg = open(os.path.join(_ROOT, "python", "synapse", "mcp", "_tool_registry.py"),
                   encoding="utf-8").read()
        block = reg[reg.index('("synapse_solaris_build_graph"'):reg.index('("synapse_solaris_component_builder"')]
        assert '"insert": {"type": "boolean"' in block

    def test_prompt_teaches_one_call_insert_and_conditional_scout(self, monkeypatch):
        from synapse.panel import system_prompt
        g = system_prompt._SOLARIS_CONTEXT_GUIDANCE
        assert '"insert":true' in g
        assert "if **synapse_scout** is in" in g
        assert "rectlight, spherelight and" in g
        assert "If synapse_batch is in your tool list" in system_prompt._TOOL_GUIDANCE


# ── C5: a silent token-cap stop is surfaced ─────────────────────────────

from test_worker_tool_policy import claude_worker_module  # noqa: E402,F401


class _Provider:
    id = "fake"
    model_identity = "fake-model-1"

    def __init__(self, script):
        self._script = list(script)
        self.last_usage = None

    def resolve_key(self):
        return "key"

    def key_error_message(self):
        return "no key"

    def stream(self, **_kw):
        return self._script.pop(0)


def _worker(cw, provider):
    w = cw.ClaudeWorker([{"role": "user", "content": "hi"}], tools=[], provider=provider)
    for sig in ("tool_status", "activity_changed", "token_received", "stream_done", "stream_error"):
        setattr(w, sig, MagicMock())
    return w


@pytest.fixture
def ledger_path(tmp_path, monkeypatch):
    path = tmp_path / "usage" / "turns.jsonl"
    monkeypatch.setenv("SYNAPSE_USAGE_LEDGER", str(path))
    return path


def _last_row(path):
    import json
    return json.loads(path.read_text(encoding="utf-8").splitlines()[-1])


@pytest.mark.parametrize("stop", ["length", "max_tokens"])
def test_token_cap_with_nothing_shown_says_so(claude_worker_module, ledger_path, stop):
    cut = [{"type": "tool_use", "id": "t1", "name": "synapse_solaris_build_graph", "input": {}}]
    w = _worker(claude_worker_module, _Provider([(stop, cut)]))
    w._conversation_loop("key")
    said = " ".join(str(c.args[0]) for c in w.token_received.emit.call_args_list)
    assert "ran out of response budget" in said
    assert _last_row(ledger_path)["outcome"] == "truncated"


def test_token_cap_after_visible_text_stays_completed(claude_worker_module, ledger_path):
    w = _worker(claude_worker_module, _Provider([("length", [{"type": "text", "text": "Done."}])]))
    w._conversation_loop("key")
    assert not w.token_received.emit.called
    assert _last_row(ledger_path)["outcome"] == "completed"


def test_end_turn_is_unchanged(claude_worker_module, ledger_path):
    w = _worker(claude_worker_module, _Provider([("end_turn", [])]))
    w._conversation_loop("key")
    assert not w.token_received.emit.called
    assert _last_row(ledger_path)["outcome"] == "completed"


# ── Round 2 P1a: houdini_capture_viewport is not offered to a blind model ──

_ROSTER = [{"name": "houdini_capture_viewport", "input_schema": {}},
           {"name": "synapse_solaris_build_graph", "input_schema": {}}]


@pytest.mark.parametrize("model, kept", [
    ("deepseek-v4.1-flash:cloud", False),   # the 10/1 live take
    ("glm-5:cloud", False),
    ("claude-sonnet-5", True),
    ("qwen3-vl:8b", True),
])
def test_capture_tool_follows_vision_capability(claude_worker_module, model, kept):
    provider = _Provider([])
    provider.model_identity = model
    w = claude_worker_module.ClaudeWorker([{"role": "user", "content": "hi"}],
                                         tools=list(_ROSTER), provider=provider)
    names = [t["name"] for t in w._tools]
    assert ("houdini_capture_viewport" in names) is kept
    assert "synapse_solaris_build_graph" in names


def test_live_capability_check_wins_over_the_name(claude_worker_module):
    class _Facts:
        capabilities = {"vision"}

        def fresh(self):
            return True

    provider = _Provider([])
    provider.model_identity = "deepseek-v4.1-flash:cloud"
    provider._connection_facts = _Facts()
    w = claude_worker_module.ClaudeWorker([{"role": "user", "content": "hi"}],
                                         tools=list(_ROSTER), provider=provider)
    assert "houdini_capture_viewport" in [t["name"] for t in w._tools]
