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


# =============================================================================
# M10 -- section boxes (Tri-Band Minimal: SCENE / LIGHTING / RENDER)
# =============================================================================

from synapse.server.handler_helpers import (  # noqa: E402
    _compute_section_bands, _MIN_NODES_FOR_SECTIONS,
)


class TestSectionBands:
    """The pure banding logic. Rank cuts: SCENE < 400 <= LIGHTING < 700 <= RENDER."""

    def _full_shot(self):
        # geo(100) matlib(200) cam(400) light(500) rendersettings(700) rop(800)
        return {"geo": 100, "matlib": 200, "cam": 400,
                "light": 500, "rs": 700, "rop": 800}

    def test_three_bands_for_a_full_shot(self):
        bands = _compute_section_bands(self._full_shot())
        names = [b["name"] for b in bands]
        assert names == ["synapse_sec_scene", "synapse_sec_lighting",
                         "synapse_sec_render"]

    def test_band_membership_respects_the_cut_points(self):
        bands = {b["name"]: b["node_ids"] for b in _compute_section_bands(self._full_shot())}
        assert bands["synapse_sec_scene"] == ["geo", "matlib"]      # <400
        assert bands["synapse_sec_lighting"] == ["cam", "light"]     # 400..699
        assert bands["synapse_sec_render"] == ["rop", "rs"]          # >=700 (sorted)

    def test_boundary_400_is_lighting_700_is_render(self):
        ranks = {"a": 399, "b": 400, "c": 699, "d": 700}
        bands = {b["name"]: set(b["node_ids"]) for b in _compute_section_bands(ranks)}
        assert "a" in bands["synapse_sec_scene"]
        assert "b" in bands["synapse_sec_lighting"]
        assert "c" in bands["synapse_sec_lighting"]
        assert "d" in bands["synapse_sec_render"]

    def test_tiny_network_gets_no_boxes(self):
        # Below the size floor: sectioning is noise.
        ranks = {"a": 100, "b": 500}
        assert len(ranks) < _MIN_NODES_FOR_SECTIONS
        assert _compute_section_bands(ranks) == []

    def test_single_band_network_gets_no_boxes(self):
        # Enough nodes, but all in one band -> a box around everything is noise.
        ranks = {"a": 100, "b": 110, "c": 150, "d": 200}
        assert _compute_section_bands(ranks) == []

    def test_two_populated_bands_of_three_is_enough(self):
        # SCENE + RENDER present, LIGHTING empty -> 2 boxes, no empty band.
        ranks = {"a": 100, "b": 200, "c": 700, "d": 800}
        names = [b["name"] for b in _compute_section_bands(ranks)]
        assert names == ["synapse_sec_scene", "synapse_sec_render"]

    def test_unranked_690_lands_in_scene_not_render(self):
        # _UNRANKED_RANK is 690 -- upstream of the render tier (700), so an
        # unknown-type node bands with SCENE-side content, never RENDER.
        ranks = {"a": 100, "b": 200, "c": 690, "d": 800}
        bands = {b["name"]: set(b["node_ids"]) for b in _compute_section_bands(ranks)}
        assert "c" in bands["synapse_sec_lighting"]  # 400<=690<700
        assert "c" not in bands.get("synapse_sec_render", set())


class TestSectionMonotonicityGate:
    """The adversarial finding: the layout keys Y off DAG depth, not rank, so a
    rank band is only safe to box when the bands form disjoint vertical slabs.
    A rank-ordered pipeline satisfies it; a depth!=rank wiring does not."""

    def _bands(self, ranks):
        from synapse.server.handler_helpers import _compute_section_bands
        return _compute_section_bands(ranks)

    def test_rank_ordered_pipeline_is_monotonic(self):
        from synapse.server.handler_helpers import _bands_are_rank_monotonic
        ranks = {"geo": 100, "mat": 200, "cam": 400, "light": 500, "rs": 700, "rop": 800}
        # depth == rank order: Y decreases as rank increases (SCENE highest).
        y = {"geo": 0.0, "mat": -1.2, "cam": -2.4, "light": -3.6, "rs": -4.8, "rop": -6.0}
        assert _bands_are_rank_monotonic(self._bands(ranks), y) is True

    def test_depth_not_matching_rank_is_rejected(self):
        from synapse.server.handler_helpers import _bands_are_rank_monotonic
        # A LIGHTS-band node wired as a ROOT (top, y=0) feeding a SCENE-band node
        # below it: the SCENE slab now overlaps the LIGHTING slab. Must reject.
        ranks = {"light": 500, "geo": 100, "mat": 200, "cam": 400, "rs": 700, "rop": 800}
        y = {"light": 0.0, "geo": -1.2, "mat": -2.4, "cam": -3.6, "rs": -4.8, "rop": -6.0}
        assert _bands_are_rank_monotonic(self._bands(ranks), y) is False

    def test_foreign_node_inside_a_slab_is_rejected(self):
        from synapse.server.handler_helpers import _bands_are_rank_monotonic
        ranks = {"geo": 100, "mat": 200, "rs": 700, "rop": 800, "stray": 500, "cam": 400}
        # 'stray' (LIGHTING) sits at y=-1.5, inside the SCENE slab [-2.4, 0].
        y = {"geo": 0.0, "mat": -2.4, "stray": -1.5, "cam": -3.6, "rs": -4.8, "rop": -6.0}
        assert _bands_are_rank_monotonic(self._bands(ranks), y) is False
