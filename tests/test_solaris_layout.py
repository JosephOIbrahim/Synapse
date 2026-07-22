"""Solaris DAG layout math (Phase 3). Pure Python -- no Houdini.

Pins the three artist-visible layout fixes against the old center-every-layer
placement, all exercised through the pure ``_compute_dag_positions``:

  * M8 -- nodes feeding a merge are ordered by their input index, so wires do
    not cross.
  * M9 -- a node sits at the barycenter of its parents, not on a fixed center.
  * M7 -- a build into a populated stage starts below existing content instead
    of on top of it (``_free_origin``, tested with a fake parent).

The old code centered every layer on start_x and iterated ``sorted_ids`` order,
so both the crossing and the barycenter tests below would have failed on it.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.server.handler_helpers import (  # noqa: E402
    _compute_dag_positions, _free_origin, HORIZONTAL_SPACING, VERTICAL_SPACING,
)


def _x(pos, nid):
    return pos[nid][0]


def _y(pos, nid):
    return pos[nid][1]


class TestInputIndexOrdering:
    """M8: fan-in nodes lay out left-to-right in wire order."""

    def test_merge_inputs_ordered_by_index_not_id(self):
        # Listed g0,g1,g2 but they feed merge inputs 2,0,1 -- x order must follow
        # the INPUT index (0,1,2), i.e. g1, g2, g0, not the id order.
        conns = [
            {"from": "g0", "to": "m", "input": 2},
            {"from": "g1", "to": "m", "input": 0},
            {"from": "g2", "to": "m", "input": 1},
        ]
        pos = _compute_dag_positions(["g0", "g1", "g2", "m"], conns)
        left_to_right = sorted(("g0", "g1", "g2"), key=lambda n: _x(pos, n))
        assert left_to_right == ["g1", "g2", "g0"]

    def test_merge_lands_at_parent_barycenter(self):
        conns = [
            {"from": "g0", "to": "m", "input": 0},
            {"from": "g1", "to": "m", "input": 1},
        ]
        pos = _compute_dag_positions(["g0", "g1", "m"], conns)
        bary = (_x(pos, "g0") + _x(pos, "g1")) / 2.0
        assert abs(_x(pos, "m") - bary) < 1e-6


class TestBarycenterAndSeparation:
    """M9 + spacing."""

    def test_child_follows_single_parent_x(self):
        # A one-in/one-out chain hanging off one branch of a merge: the child
        # must track its parent's x, not snap back to center 0.
        conns = [
            {"from": "a", "to": "m", "input": 0},
            {"from": "b", "to": "m", "input": 1},
            {"from": "m", "to": "tail", "input": 0},
        ]
        pos = _compute_dag_positions(["a", "b", "m", "tail"], conns)
        assert abs(_x(pos, "tail") - _x(pos, "m")) < 1e-6

    def test_same_layer_nodes_respect_min_separation(self):
        conns = [
            {"from": "g0", "to": "m", "input": 0},
            {"from": "g1", "to": "m", "input": 1},
            {"from": "g2", "to": "m", "input": 2},
        ]
        pos = _compute_dag_positions(["g0", "g1", "g2", "m"], conns)
        xs = sorted(_x(pos, n) for n in ("g0", "g1", "g2"))
        gaps = [b - a for a, b in zip(xs, xs[1:])]
        assert all(g >= HORIZONTAL_SPACING - 1e-6 for g in gaps), gaps

    def test_layers_descend_by_v_spacing(self):
        conns = [{"from": "a", "to": "b", "input": 0},
                 {"from": "b", "to": "c", "input": 0}]
        pos = _compute_dag_positions(["a", "b", "c"], conns)
        assert _y(pos, "a") == 0.0
        assert abs(_y(pos, "b") - (-VERTICAL_SPACING)) < 1e-6
        assert abs(_y(pos, "c") - (-2 * VERTICAL_SPACING)) < 1e-6

    def test_empty_is_empty(self):
        assert _compute_dag_positions([], []) == {}


class _FakeChild:
    def __init__(self, path, x, y):
        self._path = path
        self._pos = (x, y)

    def path(self):
        return self._path

    def position(self):
        return self._pos


class _FakeParent:
    def __init__(self, children):
        self._children = children

    def children(self):
        return self._children


class TestFreeOrigin:
    """M7: a build into a populated stage starts clear of existing content."""

    def test_empty_stage_uses_zero(self):
        assert _free_origin(_FakeParent([]), set()) == (0.0, 0.0)

    def test_origin_drops_below_existing_content(self):
        existing = [_FakeChild("/stage/a", 0.0, 0.0),
                    _FakeChild("/stage/b", 2.0, -3.0)]
        ox, oy = _free_origin(_FakeParent(existing), set())
        assert oy < -3.0, "new origin must sit below the lowest existing node"
        assert ox == 1.0, "origin x should be the existing content's center"

    def test_new_nodes_do_not_move_the_origin(self):
        # A node that IS part of this build must not count as pre-existing.
        kids = [_FakeChild("/stage/new1", 0.0, -50.0)]
        ox, oy = _free_origin(_FakeParent(kids), {"/stage/new1"})
        assert (ox, oy) == (0.0, 0.0)
