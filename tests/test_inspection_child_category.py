"""Read-only category facts; no Houdini, model or scene mutation."""
from types import SimpleNamespace
import pytest
from synapse.server import introspection, selection_snapshot

class Node:
    def __init__(self, own="Object", child="Sop"):
        self.own, self.child = own, child
    def path(self): return "/obj/artist_container"
    def name(self): return "artist_container"
    def sessionId(self): return 7
    def parent(self): return None
    def type(self):
        return SimpleNamespace(name=lambda: "geo", category=lambda: SimpleNamespace(name=lambda: self.own))
    def childTypeCategory(self):
        if isinstance(self.child, Exception): raise self.child
        return None if self.child is None else SimpleNamespace(name=lambda: self.child)
    def __getattr__(self, name):
        if name in {"createNode", "cook", "geometry", "stage", "parms", "setInput"}:
            raise AssertionError("inspection must not call " + name)
        raise AttributeError(name)

@pytest.mark.parametrize("surface", ["basic", "selection"])
@pytest.mark.parametrize("own,child", [("Object", "Sop"), ("Object", "Lop"), ("Sop", "Vop"), ("Lop", "Lop")])
def test_distinct_own_and_creatable_child_category(surface, own, child):
    node = Node(own, child)
    row = (introspection._node_basic(node) if surface == "basic" else
           selection_snapshot._Scan(10, 10, {}).metadata(node))
    assert {k: row[k] for k in ("path", "name", "type", "category")} == {
        "path": node.path(), "name": node.name(), "type": "geo", "category": own}
    assert row["child_category"] == {"status": "available", "name": child, "reason": None}

@pytest.mark.parametrize("surface", ["basic", "selection"])
@pytest.mark.parametrize("child,status,reason", [
    (None, "none", "Node reports no child type category."),
    (RuntimeError("private details"), "unavailable", "Could not read child type category."),
    ("", "unavailable", "Could not read child type category."),
    ("  ", "unavailable", "Could not read child type category."),
    (123, "unavailable", "Could not read child type category."),
])
def test_absence_is_not_inferred_from_own_category(surface, child, status, reason):
    node = Node("Object", child)
    row = (introspection._node_basic(node) if surface == "basic" else
           selection_snapshot._Scan(10, 10, {}).metadata(node))
    assert row["category"] == "Object"
    assert row["child_category"] == {"status": status, "name": None, "reason": reason}

@pytest.mark.parametrize("surface", ["basic", "selection"])
def test_missing_api_is_unavailable(surface):
    node = Node()
    node.childTypeCategory = None
    row = (introspection._node_basic(node) if surface == "basic" else
           selection_snapshot._Scan(10, 10, {}).metadata(node))
    assert row["child_category"]["status"] == "unavailable"
    assert row["child_category"]["name"] is None

@pytest.mark.parametrize("category", [object(), SimpleNamespace(name=lambda: (_ for _ in ()).throw(RuntimeError("secret")))])
def test_missing_or_throwing_category_name(category):
    node = Node()
    node.childTypeCategory = lambda: category
    assert selection_snapshot.child_category_fact(node) == {
        "status": "unavailable", "name": None, "reason": "Could not read child type category."}


@pytest.mark.parametrize("surface", ["basic", "selection"])
@pytest.mark.parametrize("initial", ["raise", "bad_name", "invalid", "none"])
def test_read_recovers_without_rewriting_an_earlier_view(surface, initial):
    """The eight preserved pure transitions now import this candidate normally."""
    import copy

    node = Node()
    state, reads = [initial], [0]

    def category():
        reads[0] += 1
        if state[0] == "raise":
            raise RuntimeError("private primary error")
        if state[0] == "none":
            return None
        if state[0] == "bad_name":
            return SimpleNamespace(name=lambda: (_ for _ in ()).throw(RuntimeError("private name error")))
        return SimpleNamespace(name=lambda: False if state[0] == "invalid" else state[0])

    node.childTypeCategory = category

    def observe():
        return (introspection._node_basic(node) if surface == "basic" else
                selection_snapshot._Scan(10, 10, {}).metadata(node))

    before = observe()
    frozen = copy.deepcopy(before)
    assert before["child_category"]["status"] == ("none" if initial == "none" else "unavailable")
    assert "private" not in str(before)
    state[0] = "Sop"
    after = observe()
    assert after["child_category"] == {"status": "available", "name": "Sop", "reason": None}
    assert before == frozen
    assert {key: after[key] for key in ("path", "name", "type", "category")} == {
        key: before[key] for key in ("path", "name", "type", "category")}
    assert reads == [2]
    assert before["child_category"] is not after["child_category"]


def _consumer_snapshot():
    """Reuse the existing wire fixture from this checkout, never an older tree."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().with_name("test_selection_wire_preview.py")
    spec = importlib.util.spec_from_file_location("child_category_wire_fixture", path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    return fixture.snapshot.__wrapped__()


@pytest.mark.parametrize("fact", [
    {"status": "available", "name": "Sop", "reason": None},
    {"status": "none", "name": None, "reason": "Node reports no child type category."},
    {"status": "unavailable", "name": None, "reason": "Could not read child type category."},
])
def test_existing_pin_and_wire_consumers_preserve_their_contract(fact):
    import copy
    from synapse.panel.selection_inspection import inspection_request
    from synapse.panel.wire_preview import build_insertion_preview

    original = _consumer_snapshot()
    enriched = copy.deepcopy(original)
    for row in enriched["nodes"]:
        row["child_category"] = copy.deepcopy(fact)
    before = copy.deepcopy(enriched)
    assert inspection_request(enriched) == inspection_request(original)
    edge = original["wires"]["internal"][0]
    assert build_insertion_preview(enriched, edge, "/stage/middle") == build_insertion_preview(original, edge, "/stage/middle")
    assert enriched == before


def test_child_category_does_not_override_a_consumers_own_category_check():
    from synapse.panel.wire_preview import build_insertion_preview

    value = _consumer_snapshot()
    value["nodes"][2]["category"] = "Object"
    value["nodes"][2]["child_category"] = {"status": "available", "name": "Lop", "reason": None}
    with pytest.raises(ValueError):
        build_insertion_preview(value, value["wires"]["internal"][0], "/stage/middle")
