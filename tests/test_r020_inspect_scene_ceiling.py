"""R-020 (OBSERVER-4) — inspect_scene has a hard node ceiling and stamps its
truncation instead of presenting a capped tree as the whole scene.

Predicate: ``inspect_scene(root='/', max_depth=100)`` above the ceiling returns
``truncated: true`` with the ceiling and omitted count, and returned node
records never exceed it.

The counting half matters as much as the cap: a degraded read is still useful,
so ``overview.node_count``/``contexts`` continue to count past the ceiling
(integers only, no records). A capped read that silently reported the capped
count as the scene total would be the exact failure this node exists to stop.

Pure Python — no hou, no hython, no network.
"""
from __future__ import annotations

from types import SimpleNamespace

from synapse.server import introspection


# ---------------------------------------------------------------------------
# Fakes — duck-typed nodes; every member inspect_scene touches is explicit so
# an unfinished read cannot silently pick up a MagicMock truthy.
# ---------------------------------------------------------------------------

class _Category:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _NodeType:
    def __init__(self, name, category):
        self._name = name
        self._category = category

    def name(self):
        return self._name

    def category(self):
        return _Category(self._category)


class _FakeNode:
    """A hou.Node stand-in: path, name, type, children, warnings/errors."""

    def __init__(self, path, category="Sop", node_type="null",
                 children=(), warnings=(), errors=()):
        self._path = path
        self._category = category
        self._node_type = node_type
        self._children = list(children)
        self._warnings = list(warnings)
        self._errors = list(errors)

    def path(self):
        return self._path

    def name(self):
        return self._path.rsplit("/", 1)[-1]

    def type(self):
        return _NodeType(self._node_type, self._category)

    def children(self):
        return tuple(self._children)

    def warnings(self):
        return list(self._warnings)

    def errors(self):
        return list(self._errors)

    def stickyNotes(self):
        return ()


def _flat_leaf_children(count, parent="/obj"):
    return [_FakeNode("%s/node%04d" % (parent, i)) for i in range(count)]


def _records(tree):
    """Every dict returned in the tree, wrappers and leaves alike."""
    out = []
    for entry in tree:
        out.append(entry)
        out.extend(_records(entry.get("children", [])))
    return out


def _install_root(monkeypatch, root):
    monkeypatch.setattr(
        introspection, "hou", SimpleNamespace(node=lambda _path: root))


# ---------------------------------------------------------------------------
# The predicate, called exactly as written
# ---------------------------------------------------------------------------

def test_default_ceiling_stamps_truncation(monkeypatch):
    """inspect_scene(root='/', max_depth=100) above the ceiling is truncated,
    names the ceiling and the omitted count, and returns no more records than
    the ceiling."""
    over = 25
    root = _FakeNode(
        "/", category="Manager",
        children=_flat_leaf_children(introspection.SCENE_NODE_CAP + over))
    _install_root(monkeypatch, root)

    result = introspection.inspect_scene(root="/", max_depth=100)

    assert result["truncated"] is True
    assert result["complete"] is False
    assert result["node_ceiling"] == introspection.SCENE_NODE_CAP
    # 1 root + SCENE_NODE_CAP + 25 children observed; the records stop at the
    # ceiling, so the omission is the rest — a measured count, not a guess.
    assert result["overview"]["node_count"] == introspection.SCENE_NODE_CAP + 1 + over
    assert result["omitted_count"] == result["overview"]["node_count"] - introspection.SCENE_NODE_CAP
    assert result["record_count"] <= result["node_ceiling"]
    assert len(_records(result["network_tree"])) <= result["node_ceiling"]
    assert len(_records(result["network_tree"])) == result["record_count"]


def test_returned_records_never_exceed_explicit_ceiling(monkeypatch):
    """An explicit max_nodes is the ceiling: exactly that many records at most,
    every omitted node still counted into the overview."""
    total_children = 100
    root = _FakeNode("/obj", category="Manager",
                     children=_flat_leaf_children(total_children))
    _install_root(monkeypatch, root)

    result = introspection.inspect_scene(root="/obj", max_depth=3, max_nodes=25)

    assert result["node_ceiling"] == 25
    records = _records(result["network_tree"])
    assert len(records) == 25
    assert len(records) <= result["node_ceiling"]
    assert result["truncated"] is True
    assert result["truncated_reason"] == "node_ceiling"
    # Counting continued past the cap: 1 root + 100 children.
    assert result["overview"]["node_count"] == total_children + 1
    assert sum(result["overview"]["contexts"].values()) == result["overview"]["node_count"]
    assert result["omitted_count"] == total_children + 1 - 25


def test_token_budget_can_bind_before_the_node_ceiling(monkeypatch):
    """A token budget too small for even the root returns no records, says
    which budget bound, and still reports the full node census."""
    root = _FakeNode("/obj", category="Manager",
                     children=_flat_leaf_children(10))
    _install_root(monkeypatch, root)

    result = introspection.inspect_scene(
        root="/obj", max_depth=3, token_budget=1)

    assert result["network_tree"] == []
    assert result["truncated"] is True
    assert result["truncated_reason"] == "token_budget"
    assert result["record_count"] == 0
    assert result["overview"]["node_count"] == 11
    assert result["omitted_count"] == 11
    assert result["token_budget"] == 1


def test_under_the_ceiling_is_complete(monkeypatch):
    """A small scene is untouched: no truncation stamp, nothing omitted."""
    root = _FakeNode("/obj", category="Manager",
                     children=_flat_leaf_children(3))
    _install_root(monkeypatch, root)

    result = introspection.inspect_scene(root="/obj", max_depth=3)

    assert result["truncated"] is False
    assert result["truncated_reason"] is None
    assert result["complete"] is True
    assert result["omitted_count"] == 0
    assert result["record_count"] == 4
    assert len(_records(result["network_tree"])) == 4


def test_context_filter_wrappers_count_against_the_ceiling(monkeypatch):
    """Filter wrappers are returned records too; the ceiling still holds."""
    root = _FakeNode("/", category="Manager",
                     children=[
                         _FakeNode("/%s/sop%02d" % (cat, i), category=cat)
                         for cat in ("Sop", "Lop") for i in range(10)
                     ])
    _install_root(monkeypatch, root)

    result = introspection.inspect_scene(
        root="/", max_depth=3, context_filter="Sop", max_nodes=5)

    records = _records(result["network_tree"])
    assert len(records) <= 5
    assert result["node_ceiling"] == 5
    assert result["truncated"] is True
    # Only Sop nodes count toward the census; Lop nodes are filtered out.
    assert result["overview"]["node_count"] == 10
    assert result["overview"]["contexts"] == {"Sop": 10}


def test_visit_cap_reports_incomplete_counts(monkeypatch):
    """If the count-only walk itself hits its bound, the result says the
    counts are partial rather than presenting them as the scene total."""
    monkeypatch.setattr(introspection, "SCENE_VISIT_CAP", 10)
    root = _FakeNode("/obj", category="Manager",
                     children=_flat_leaf_children(50))
    _install_root(monkeypatch, root)

    result = introspection.inspect_scene(root="/obj", max_depth=3)

    assert result["overview"]["counts_complete"] is False
    assert result["complete"] is False
    assert result["overview"]["node_count"] < 51
