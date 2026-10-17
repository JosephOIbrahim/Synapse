"""A real-Merge-shaped double for the Solaris graph planner and validator.

Before this file, every planner double answered ``hasUnorderedInputs()`` with
False (tests/test_solaris_evolution_regressions.py:35,
tests/test_solaris_insert_splice.py:52), and the evolution "merge" took 8
ordered inputs (:30). So the planner's unordered-gap refusal
(``_check_unordered_gaps``, "cannot contain gaps") and its bundled-catalog
lookup (``_ordered_inputs_catalog``) had never run under test.

Vendor docs cited below: the local SideFX docs crawl at
``D:\\Houdini_AI_Reference\\upstream_sidefx\\snapshot-2026-10-04\\docs``. It is a
nightly 22.0.4xx crawl, not a 22.0.400 build artifact
(``D:\\Houdini_AI_Reference\\LIBRARY_README.md:18``).

* ``nodes/lop/merge.md`` (sha256 e7c203a2821b4eff...)
  - :7  Merge takes multiple inputs and merges them into one layer stack.
  - :9  input order matters: layers in earlier inputs are weaker.
* ``hom/hou/Node.md`` (sha256 7c432eb9764e91d4...)
  - :518-531 ``setInput(input_index, ...)`` wires one input connector.
  - :541-554 ``setNextInput`` connects to the first unconnected input.
  - :556-558 ``insertInput`` SHIFTS every later input up by one.
  - :560-562 ``numOrderedInputs``: the dedicated inputs that come before the
    unordered ones, "where gaps are not permitted between the inputs".
* ``hom/hou/NodeType.md`` (sha256 3cd8e76190c18deb...)
  - :94-96   ``maxNumInputs`` returns 9999 when a type "can accept an unlimited
    number of inputs (e.g. the merge SOP)".
  - :112-114 ``hasUnorderedInputs`` is True for the merge SOP, which
    "cannot have any gaps in its inputs".

What the ``Lop/merge`` double stands on, half by half:

* ``hasUnorderedInputs() -> True`` is the DOCUMENTED merge-SOP analogue
  (NodeType.md:112-114). It is not a measured 22.0.400 fact for ``Lop/merge``:
  the bundled catalog carries no such field, and the takeover report
  (TAKEOVER_REPORT.frozen-5457ac84.md:478, local evidence outside this repo)
  lists that probe as still open.
* ``maxNumInputs() -> 9999`` and ``numOrderedInputs() -> 0`` match the bundled
  catalog row ``"Lop/merge"`` in
  ``python/synapse/cognitive/tools/data/connectivity_22.json``
  (houdini_version "22.0.400": max_inputs 9999, num_ordered_inputs 0), the row
  the planner itself reads for a node that does not exist yet.

SYNAPSE semantics these cases pin (the planner is not changed):

* A wire with no ``input`` into an ``existing`` node is an append.
  ``resolve_plan`` gives it the lowest live input that is neither occupied nor
  reserved by an explicit wire, like ``setNextInput`` (Node.md:541-554).
* Into a NEW node, a missing ``input`` means input 0.
* ``insert: true`` REPLACES one occupied input
  (tests/test_solaris_insert_splice.py). HOM's ``insertInput`` shifts instead
  (Node.md:556-558): the same word for different operations. Not exercised here.

The validator fix (B-SOLARIS): ``validate_graph``'s gap warning read a missing
``input`` as 0 everywhere. Two appends into an existing merge therefore warned
"input gap: indices [0, 0]", while the same request's preview planned them
onto inputs 0 and 1. The v5.97.2 release recorded that warning on the 22.0.400
seat (harness/notes/release-v5.97.2/production_validation/production.json:124).
The pure validator cannot see live inputs. So it now leaves those appends out
of its check. For unordered inputs the planner's live check is the authority.

Scope: these cases run on stock CPython with synthetic doubles; none of them
ran inside Houdini. The highest state they earn is experimental.
"""
from copy import deepcopy

import pytest

from synapse.core.errors import SynapseUserError
from synapse.server import handlers_solaris_graph as graph
from synapse.server import main_thread
from synapse.server.solaris_graph_plan import _ordered_inputs_catalog, resolve_plan

CATALOG_BUILD = "22.0.400"   # connectivity_22.json "houdini_version"
OTHER_BUILD = "22.0.429"     # the docs crawl's local target build, not in the catalog


class _Category:
    def name(self):
        return "Lop"


class _Type:
    """A single-input LOP type (null-like), ordered inputs."""

    def __init__(self, name, outputs=1):
        self._name, self._outputs = name, outputs

    def name(self):
        return self._name

    def category(self):
        return _Category()

    def __eq__(self, other):   # hou.NodeType compares by type, not by wrapper
        return isinstance(other, _Type) and other._name == self._name

    def __hash__(self):
        return hash(self._name)

    def maxNumInputs(self):
        return 1

    def maxNumOutputs(self):
        return self._outputs

    def hasUnorderedInputs(self):
        return False


class _MergeType(_Type):
    """``Lop/merge`` as the documented merge-SOP analogue (NodeType.md:112-114).

    Unordered inputs are the documented analogue, not a measured 22.0.400 fact.
    9999 inputs is NodeType.md:96 and the catalog row's max_inputs.
    """

    def __init__(self):
        super().__init__("merge")

    def maxNumInputs(self):
        return 9999

    def hasUnorderedInputs(self):
        return True


_TYPES = {"merge": _MergeType, "null": lambda: _Type("null"),
          "subnet": lambda: _Type("subnet", outputs=2)}


class _Conn:
    def __init__(self, index, source, output):
        self._index, self._source, self._output = index, source, output

    def inputNode(self):
        return self._source

    def subnetIndirectInput(self):
        return None

    def inputIndex(self):
        return self._index

    def outputIndex(self):
        return self._output


class _Node:
    """A live node. It has no setInput: any wiring attempt would raise."""

    def __init__(self, net, name, node_type):
        self._net, self._name, self._type = net, name, node_type
        self.inputs = {}          # input index -> (live source node, its output index)
        self.ordered_reads = 0

    def name(self):
        return self._name

    def path(self):
        return self._net.path() + "/" + self._name

    def parent(self):
        return self._net

    def type(self):
        return self._type

    def inputConnections(self):
        return tuple(_Conn(index, source, output)
                     for index, (source, output) in sorted(self.inputs.items()))

    def numOrderedInputs(self):
        # Node.md:560-562; 0 for Lop/merge (catalog num_ordered_inputs).
        self.ordered_reads += 1
        return 0

    def isDisplayFlagSet(self):
        return False


class _Net:
    """``/stage`` with live children."""

    def __init__(self):
        self._kids = {}

    def path(self):
        return "/stage"

    def node(self, name):
        return self._kids.get(name)

    def children(self):
        return tuple(self._kids.values())

    def childTypeCategory(self):
        return _Category()

    def add(self, name, type_name):
        node = _Node(self, name, _TYPES[type_name]())
        self._kids[name] = node
        return node

    def merge_holding(self, count):
        """A live merge whose inputs 0..count-1 are wired (Houdini compacts them)."""
        merge = self.add("merge1", "merge")
        for index in range(count):
            merge.inputs[index] = (self.add("live%d" % index, "null"), 0)
        return merge


class _Host:
    """The slice of ``hou`` the planner and the dry-run handler touch."""

    def __init__(self, net, version=CATALOG_BUILD):
        self._net, self._version = net, version
        self.version_reads = 0

    def applicationVersionString(self):
        self.version_reads += 1
        return self._version

    def preferredNodeType(self, name, parent):
        return _TYPES[name.split("/")[-1]]()

    def nodeType(self, category, name):
        return _TYPES[name]() if name in _TYPES else None

    def node(self, path):
        if path == self._net.path():
            return self._net
        prefix = self._net.path() + "/"
        return self._net.node(path[len(prefix):]) if path.startswith(prefix) else None


@pytest.fixture(autouse=True)
def _cold_catalog_cache():
    """``_ordered_inputs_catalog`` is lru_cached per build string: start each case cold."""
    _ordered_inputs_catalog.cache_clear()
    yield
    _ordered_inputs_catalog.cache_clear()


_EXISTING_MERGE = {"id": "m", "existing": True, "name": "merge1"}
_NEW_MERGE = {"id": "m", "type": "merge"}
_SOURCES = [{"id": "key", "type": "null"}, {"id": "rim", "type": "null"}]
_TWO_APPENDS = [{"from": "key", "to": "m"}, {"from": "rim", "to": "m"}]
_APPEND_BESIDE_SLOT_2 = [{"from": "key", "to": "m", "input": 2}, {"from": "rim", "to": "m"}]


def _gap_warnings(warnings):
    return [warning for warning in warnings if "input gap" in warning]


def _plan(net, host, nodes, wires):
    valid, errors, _warnings = graph.validate_graph(nodes, wires)
    assert valid, errors
    node_map = {node["id"]: node for node in nodes}
    return resolve_plan(net, node_map, graph.topo_sort(set(node_map), wires), wires,
                        host, graph._resolve_existing_node)


def _merge_inputs(plan):
    return {link["from_id"]: link["input"] for link in plan["connections"] if link["to_id"] == "m"}


# ── The spurious warning (fails on the base: the warning is present) ────────


def test_two_appends_into_an_existing_merge_raise_no_gap_warning():
    """The contract case: two wires with no ``input`` into an existing merge.

    resolve_plan appends them to the merge's next free inputs (setNextInput
    semantics, Node.md:541-554), so they cannot open a gap. The base validator
    read both as input 0 and warned "input gap: indices [0, 0]".
    """
    nodes, wires = _SOURCES + [_EXISTING_MERGE], deepcopy(_TWO_APPENDS)
    valid, errors, warnings = graph.validate_graph(nodes, wires)
    assert valid and errors == []
    assert _gap_warnings(warnings) == []


def test_append_beside_an_explicit_slot_raises_no_gap_warning():
    """An append next to an explicit ``input: 2`` on an existing merge.

    Where the append lands depends on the live inputs, which the pure validator
    cannot see. The base read it as input 0 and warned "indices [0, 2]".
    """
    nodes, wires = _SOURCES + [_EXISTING_MERGE], deepcopy(_APPEND_BESIDE_SLOT_2)
    valid, errors, warnings = graph.validate_graph(nodes, wires)
    assert valid and errors == []
    assert _gap_warnings(warnings) == []


def test_v5972_production_merge_wires_raise_no_gap_warning():
    """The merge wires of the v5.97.2 production probe, run on the 22.0.400 seat
    (harness/notes/release-v5.97.2/production_validation/production_probe.py:296-297,
    in the request at :289; build per runtime-pins.json:2). Its recorded preview
    planned merge inputs 1 and 0 yet warned "indices [0, 0]" (production.json:124),
    and the applied merge held inputs 0 and 1 (production_probe.py:331).

    The explicit wire re-states the live input 0 (unchanged), so the append
    takes input 1. Only the validator's warning was wrong.
    """
    net = _Net()
    source, merge = net.add("source", "subnet"), net.add("merge", "merge")
    merge.inputs[0] = (source, 1)
    nodes = [{"id": "source", "existing": True, "name": "source"},
             {"id": "merge", "existing": True, "name": "merge"}]
    wires = [{"from": "source", "to": "merge", "output": 1},
             {"from": "source", "to": "merge", "input": 0, "output": 1}]
    valid, errors, warnings = graph.validate_graph(nodes, deepcopy(wires))
    assert valid and errors == []
    assert _gap_warnings(warnings) == []
    plan = _plan(net, _Host(net), nodes, wires)
    assert sorted((link["input"], link["output"], link["changed"])
                  for link in plan["connections"]) == [(0, 1, False), (1, 1, True)]
    assert merge.inputs == {0: (source, 1)}


def test_preview_payload_carries_no_spurious_gap_warning(monkeypatch):
    """The artist-visible symptom: a dry run planned inputs 0 and 1 and warned [0, 0]."""
    net = _Net()
    net.merge_holding(0)
    monkeypatch.setattr(graph, "hou", _Host(net), raising=False)
    monkeypatch.setattr(graph, "HOU_AVAILABLE", True)
    monkeypatch.setattr(main_thread, "run_on_main", lambda fn, **kwargs: fn())
    result = graph.SolarisGraphMixin()._handle_solaris_build_graph({
        "parent": "/stage", "dry_run": True, "frame": False, "sections": False,
        "nodes": _SOURCES + [_EXISTING_MERGE], "connections": deepcopy(_TWO_APPENDS)})
    assert result["status"] == "preview"
    planned = {(link["from"], link["input"]) for link in result["planned_connections"]
               if link["to"] == "/stage/merge1"}
    assert planned == {("/stage/key", 0), ("/stage/rim", 1)}
    assert _gap_warnings(result["warnings"]) == []
    assert net.node("merge1").inputs == {}


# ── Planner pins: appends land on the next free inputs (semantics unchanged) ──


@pytest.mark.parametrize("live,expected", [(0, {"key": 0, "rim": 1}), (2, {"key": 2, "rim": 3})])
def test_planner_appends_onto_the_next_free_merge_inputs(live, expected):
    """Appends fill the live merge's next free inputs, so no gap and no refusal."""
    net = _Net()
    merge = net.merge_holding(live)
    host, before = _Host(net), dict(merge.inputs)
    plan = _plan(net, host, _SOURCES + [_EXISTING_MERGE], deepcopy(_TWO_APPENDS))
    assert _merge_inputs(plan) == expected
    assert merge.inputs == before
    assert host.version_reads == 0   # contiguous: the gap boundary was never needed


@pytest.mark.parametrize("live", [0, 1])
def test_append_beside_an_explicit_slot_is_planned_or_refused_against_the_live_merge(live):
    """The planner, not the validator, decides this case from the live inputs.

    With input 0 live, the append takes input 1: inputs 0-2, accepted. On an
    empty merge it takes input 0 and leaves input 1 empty, so the planner
    refuses with nothing changed (Node.md:560-562: no gaps on unordered inputs).
    """
    net = _Net()
    merge = net.merge_holding(live)
    host, before = _Host(net), dict(merge.inputs)
    nodes, wires = _SOURCES + [_EXISTING_MERGE], deepcopy(_APPEND_BESIDE_SLOT_2)
    if live:
        assert _merge_inputs(_plan(net, host, nodes, wires)) == {"key": 2, "rim": 1}
    else:
        with pytest.raises(SynapseUserError, match="Unordered inputs on m cannot contain gaps"):
            _plan(net, host, nodes, wires)
        assert merge.ordered_reads == 1
    assert merge.inputs == before


# ── The unordered-gap refusal, live and new ─────────────────────────────────


@pytest.mark.parametrize("live,explicit,warned", [(0, [0, 2], [0, 2]), (2, [3], None)])
def test_explicit_gap_into_an_existing_merge_is_refused_by_the_live_boundary(live, explicit, warned):
    """Explicit indices that would leave a hole in a live merge are refused.

    The boundary comes from the live node's numOrderedInputs() (Node.md:560-562),
    never from the catalog. Explicit gaps still warn at request level, as before.
    """
    net = _Net()
    merge = net.merge_holding(live)
    sources = [{"id": "s%d" % index, "type": "null"} for index in range(len(explicit))]
    wires = [{"from": "s%d" % index, "to": "m", "input": slot} for index, slot in enumerate(explicit)]
    nodes, host, before = sources + [_EXISTING_MERGE], _Host(net), dict(merge.inputs)
    _valid, _errors, warnings = graph.validate_graph(nodes, wires)
    assert bool(_gap_warnings(warnings)) is (warned is not None)
    if warned is not None:
        assert "indices %s" % warned in _gap_warnings(warnings)[0]
    with pytest.raises(SynapseUserError, match="Unordered inputs on m cannot contain gaps"):
        _plan(net, host, nodes, wires)
    assert merge.ordered_reads == 1
    assert host.version_reads == 0 and _ordered_inputs_catalog.cache_info().misses == 0
    assert merge.inputs == before


def test_gap_on_a_new_merge_is_refused_from_the_bundled_catalog():
    """A merge that does not exist yet has no live node to ask, so the planner
    reads the bundled 22.0.400 catalog row (host build "22.0.400").

    A missing ``input`` into a NEW node is still input 0, so the validator
    still warns [0, 2]; the catalog boundary (0) then refuses the gap.
    """
    net = _Net()
    host = _Host(net, CATALOG_BUILD)
    nodes = _SOURCES + [_NEW_MERGE]
    wires = [{"from": "key", "to": "m"}, {"from": "rim", "to": "m", "input": 2}]
    _valid, _errors, warnings = graph.validate_graph(nodes, wires)
    assert len(_gap_warnings(warnings)) == 1 and "indices [0, 2]" in warnings[0]
    with pytest.raises(SynapseUserError, match="Unordered inputs on m cannot contain gaps"):
        _plan(net, host, nodes, wires)
    assert host.version_reads == 1
    info = _ordered_inputs_catalog.cache_info()
    assert (info.misses, info.currsize) == (1, 1)   # the planner read the catalog once
    row = _ordered_inputs_catalog(CATALOG_BUILD)["Lop/merge"]   # precondition, not vacuous
    assert (row["max_inputs"], row["num_ordered_inputs"]) == (9999, 0)
    assert net.children() == ()


def test_gap_on_a_new_merge_fails_closed_off_the_catalog_build():
    """On a build the catalog was not taken on, the boundary is unknown:
    the planner refuses rather than guess (negative control for the gate)."""
    net = _Net()
    host = _Host(net, OTHER_BUILD)
    nodes = _SOURCES + [_NEW_MERGE]
    wires = [{"from": "key", "to": "m", "input": 0}, {"from": "rim", "to": "m", "input": 2}]
    with pytest.raises(SynapseUserError, match="Cannot verify input gaps for m on this Houdini build"):
        _plan(net, host, nodes, wires)
    assert host.version_reads == 1
    assert _ordered_inputs_catalog.cache_info().misses == 1
    assert _ordered_inputs_catalog(OTHER_BUILD) == {}


def test_contiguous_inputs_on_a_new_merge_never_consult_the_catalog():
    net = _Net()
    host = _Host(net, CATALOG_BUILD)
    nodes = _SOURCES + [_NEW_MERGE]
    wires = [{"from": "key", "to": "m", "input": 0}, {"from": "rim", "to": "m", "input": 1}]
    assert _merge_inputs(_plan(net, host, nodes, wires)) == {"key": 0, "rim": 1}
    assert host.version_reads == 0 and _ordered_inputs_catalog.cache_info().misses == 0


def test_two_implicit_wires_into_a_new_merge_still_claim_input_0_twice():
    """Unchanged: into a NEW node a missing ``input`` is input 0, so two of them collide."""
    valid, errors, _warnings = graph.validate_graph(_SOURCES + [_NEW_MERGE], deepcopy(_TWO_APPENDS))
    assert valid is False
    assert "Multiple connections claim 'm' input 0" in errors
