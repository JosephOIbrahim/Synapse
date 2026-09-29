"""layout: where bubbles go on the network editor, as pure geometry."""
from __future__ import annotations

import itertools
import random

from synapse.identify import layout as L

M = L.Metrics(name_gap=12, dot_small=2, dot_large=3.5, dot_gap=5, bubble_gap=12,
              stack_gap=8, top_reserved=40, marker_below=8, marker=10,
              margin=12, bubble_w=300, min_w=200)
TAIL = 12 + 4 + 5 + 7 + 12   # name gap, small dot, dot gap, large dot, bubble gap


def _anchor(key, x, y, node_h=30, name_w=60, node_w=100):
    return L.Anchor(key, x, y, node_h, name_w, node_w)


def _fixed(height=60, known=None):
    """A measure that returns *height* at any width, for the known keys."""
    return lambda key, width: height if known is None or key in known else None


def test_window_point_flips_the_editor_y_axis():
    assert L.window_point(39, 1268, 1208) == (39.0, -60.0)
    assert L.window_point(10, 0, 500) == (10.0, 500.0)
    assert L.window_point(10, 500, 500) == (10.0, 0.0)


def test_bubble_starts_after_the_name_and_both_tail_dots():
    (p,) = L.place([_anchor("a", 100, 300)], _fixed(), 1200, 900, M)
    small, large = p.dots
    assert small == (100 + 60 + 12 + 2, 300, 2)
    assert large == (small[0] + 2 + 5 + 3.5, 300, 3.5)
    assert p.x == large[0] + 3.5 + 12 == 100 + 60 + TAIL
    assert (p.w, p.side, p.marker) == (300, "right", False)


def test_bubble_is_centred_on_its_node_when_nothing_is_in_the_way():
    (p,) = L.place([_anchor("a", 100, 300)], _fixed(), 1200, 900, M)
    assert p.y == 300 - 30


def test_bubble_never_rises_into_the_chip():
    (p,) = L.place([_anchor("a", 100, 20)], _fixed(), 1200, 900, M)
    assert p.y == M.top_reserved


def test_a_node_near_the_right_edge_gets_its_bubble_on_the_left():
    (p,) = L.place([_anchor("a", 1100, 300)], _fixed(), 1200, 900, M)
    assert p.side == "left" and p.w == 300
    node_left = 1100 - 100
    assert p.x + p.w == node_left - TAIL
    small, large = p.dots
    assert small[0] == node_left - 12 - 2 and large[0] < small[0]


def test_a_bubble_narrows_to_the_room_it_has():
    # right: 800 - 12 - (400 + 60 + TAIL) = 288; left: (400 - 100 - TAIL) - 12 = 248
    widths = []
    measure = lambda key, width: widths.append(width) or 60   # noqa: E731
    (p,) = L.place([_anchor("a", 400, 300)], measure, 800, 900, M)
    assert p.side == "right" and p.w == 800 - 12 - (400 + 60 + TAIL)
    assert widths == [p.w, (400 - 100 - TAIL) - 12]   # both sides were measured
    assert p.x + p.w == 800 - M.margin


def test_below_the_minimum_width_the_bubble_keeps_it_and_stays_in_view():
    (p,) = L.place([_anchor("a", 300, 300)], _fixed(), 500, 900, M)
    assert p.w == M.min_w
    assert M.margin <= p.x and p.x + p.w <= 500 - M.margin


def test_close_nodes_stack_without_overlapping():
    anchors = [_anchor("a", 100, 300), _anchor("b", 100, 320)]
    a, b = L.place(anchors, _fixed(), 1200, 900, M)
    assert b.y >= a.y + a.h + M.stack_gap


def test_no_two_bubbles_overlap_for_random_layouts():
    rng = random.Random(7)
    for _ in range(60):
        view_w = rng.choice([600, 900, 1250, 1800])
        anchors = [_anchor(i, rng.uniform(0, view_w), rng.uniform(0, 880),
                           name_w=rng.uniform(10, 120), node_w=rng.uniform(40, 140))
                   for i in range(25)]
        heights = {i: rng.uniform(40, 140) for i in range(25)}
        placed = L.place(anchors, lambda key, width: heights[key], view_w, 900, M)
        for p, q in itertools.combinations(placed, 2):
            assert not (p.x < q.x + q.w and q.x < p.x + p.w
                        and p.y < q.y + q.h and q.y < p.y + p.h), (p, q)
        for p in placed:
            assert M.margin <= p.x and p.x + p.w <= view_w - M.margin + 1e-9


def test_nodes_outside_the_view_or_unknown_to_the_measure_get_nothing():
    anchors = [_anchor("in", 100, 300), _anchor("left", -5, 300),
               _anchor("below", 100, 950), _anchor("unknown", 200, 400)]
    placed = L.place(anchors, _fixed(known={"in", "left", "below"}), 1200, 900, M)
    assert [p.key for p in placed] == ["in"]


def test_zoomed_out_draws_markers_beside_the_nodes_instead_of_bubbles():
    anchors = [_anchor("a", 100, 300, node_h=4), _anchor("b", 200, 310, node_h=4)]
    placed = L.place(anchors, _fixed(), 1200, 900, M)
    assert all(p.marker for p in placed)
    assert placed[0].x == 100 + M.dot_gap and placed[0].w == M.marker
    assert L.zoomed_out(anchors, M) is True


def test_zoom_decision_uses_the_median_node_height():
    anchors = [_anchor("a", 1, 1, node_h=4), _anchor("b", 1, 1, node_h=30),
               _anchor("c", 1, 1, node_h=30)]
    assert L.zoomed_out(anchors, M) is False
    assert L.zoomed_out([], M) is False


def test_a_crowded_column_alternates_sides_instead_of_drifting():
    anchors = [_anchor(k, 600, 200 + 30 * i) for i, k in enumerate("abcd")]
    placed = {p.key: p for p in L.place(anchors, _fixed(height=80), 1400, 900, M)}
    assert [placed[k].side for k in "abcd"] == ["right", "left", "right", "left"]
    assert placed["a"].y == 200 - 40 and placed["b"].y == 230 - 40


def test_with_one_side_blocked_a_crowded_column_stacks_and_draws_leaders():
    anchors = [_anchor(k, 100, 200 + 30 * i) for i, k in enumerate("abc")]
    placed = L.place(anchors, _fixed(height=80), 1200, 900, M)
    assert [p.side for p in placed] == ["right"] * 3
    assert L.leader(placed[0], 8) is None               # centred on its node
    line = L.leader(placed[2], 8)                       # pushed below its node
    (x1, y1), (x2, y2) = line
    assert x1 == placed[2].dots[1][0] + 3.5 and y1 == 260
    assert x2 == placed[2].x and y2 == placed[2].y + 8


def test_a_left_side_leader_ends_on_the_bubble_right_edge():
    p = L.Placed("k", 100, 400, 200, 60, ((330, 300, 2), (318, 300, 3.5)), False, "left")
    (x1, y1), (x2, y2) = L.leader(p, 8)
    assert (x1, y1) == (318 - 3.5, 300) and (x2, y2) == (300, 408)


def test_markers_have_no_leader():
    p = L.Placed("k", 100, 400, 10, 10, (), True)
    assert L.leader(p, 8) is None
