"""Where Identify bubbles sit on the network editor: pure geometry.

No ``hou`` and no Qt. The overlay reads numbers off the editor and measures
each bubble's text, then asks this module where everything goes. Keeping the
placement rules pure is what lets them be tested on system Python.

Coordinates are window pixels: the origin is the top left of the editor's
drawing area and y grows downward. The editor reports positions with y growing
upward from its bottom edge; :func:`window_point` converts between the two.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True)
class Metrics:
    """Spacing in window pixels, already scaled for the host UI."""
    name_gap: float      # space after the node's name label, before the tail
    dot_small: float     # radius of the tail dot nearest the node
    dot_large: float     # radius of the tail dot nearest the bubble
    dot_gap: float       # space between the two tail dots
    bubble_gap: float    # space between the large dot and the bubble
    stack_gap: float     # vertical space between stacked bubbles
    top_reserved: float  # height kept clear at the top for the chip
    marker_below: float  # node heights under this draw markers, not bubbles
    marker: float        # size of a marker's ring box
    margin: float        # inset from the drawing area's left and right edges
    bubble_w: float      # a bubble's preferred width
    min_w: float         # the narrowest a bubble gets before it may overlap


@dataclass(frozen=True)
class Anchor:
    """One identified node as the editor shows it right now."""
    key: object          # the node's sessionId
    x: float             # right edge of the node shape
    y: float             # vertical centre of the node shape
    node_h: float        # node shape height on screen
    name_w: float        # the name label's width on screen (estimated)
    node_w: float = 0.0  # node shape width on screen


@dataclass(frozen=True)
class Placed:
    """Where one bubble (or, zoomed out, one marker) is drawn."""
    key: object
    x: float
    y: float
    w: float
    h: float
    dots: tuple          # ((cx, cy, r), (cx, cy, r)): small dot, then large
    marker: bool
    side: str = "right"  # which side of its node the bubble sits on


def window_point(editor_x: float, editor_y: float, view_h: float) -> tuple:
    """Editor pixels (y up from the bottom edge) to window pixels (y down)."""
    return float(editor_x), float(view_h) - float(editor_y)


def zoomed_out(anchors, m: Metrics) -> bool:
    """True when nodes are drawn too small for a bubble to read as theirs."""
    heights = [a.node_h for a in anchors]
    return bool(heights) and median(heights) < m.marker_below


def _overlaps(x: float, y: float, w: float, h: float, other: Placed, gap: float) -> bool:
    return (x < other.x + other.w + gap and other.x < x + w + gap
            and y < other.y + other.h + gap and other.y < y + h + gap)


def _tail(m: Metrics) -> float:
    """Length of the gap a bubble keeps from its node: gaps plus both dots."""
    return m.name_gap + 2 * m.dot_small + m.dot_gap + 2 * m.dot_large + m.bubble_gap


def _settle(x: float, top: float, w: float, h: float, placed, gap: float) -> float:
    """Move *top* down past every placed bubble this one would overlap."""
    moved = True
    while moved:
        moved = False
        for other in placed:
            if _overlaps(x, top, w, h, other, gap):
                top = other.y + other.h + gap
                moved = True
    return top


def _candidate(a: Anchor, side: str, measure, view_w: float, m: Metrics, placed):
    """(fits, drift, Placed) for *a*'s bubble on *side*, or None if unmeasurable.

    *fits* says the side has at least ``min_w`` of room; *drift* is how far
    stacking had to push the bubble down from where it is centred on its node.
    """
    tail = _tail(m)
    if side == "right":
        start = a.x + a.name_w + tail
        room = view_w - m.margin - start
    else:
        end = a.x - a.node_w - tail
        room = end - m.margin
    w = min(m.bubble_w, max(m.min_w, room))
    h = measure(a.key, w)
    if h is None:
        return None
    if side == "right":
        x = max(m.margin, min(start, view_w - m.margin - w))
        small_cx = a.x + a.name_w + m.name_gap + m.dot_small
        large_cx = small_cx + m.dot_small + m.dot_gap + m.dot_large
    else:
        x = max(m.margin, end - w)
        small_cx = a.x - a.node_w - m.name_gap - m.dot_small
        large_cx = small_cx - m.dot_small - m.dot_gap - m.dot_large
    wanted = max(a.y - h / 2.0, m.top_reserved)
    top = _settle(x, wanted, w, h, placed, m.stack_gap)
    dots = ((small_cx, a.y, m.dot_small), (large_cx, a.y, m.dot_large))
    return (room >= m.min_w, top - wanted, room, Placed(a.key, x, top, w, h, dots, False, side))


def place(anchors, measure, view_w: float, view_h: float, m: Metrics) -> list:
    """Place one bubble per visible anchor.

    *measure* is ``measure(key, width) -> height`` for a bubble drawn at that
    width, or None for a key it does not know. A node is visible when its
    anchor lies inside the drawing area.

    A bubble sits beside its node, after two tail dots: on the right, past the
    name label, or on the left. It narrows to the room that side has, down to
    ``min_w``. Bubbles are placed from the top of the view down; one that would
    overlap a bubble already placed moves down below it, so no two bubbles
    ever cover each other. Of the sides with at least ``min_w`` of room, a
    bubble takes the one where it drifts least from its node, preferring the
    right on a tie, so a crowded column of nodes alternates sides instead of
    pushing every bubble away. When neither side has ``min_w``, it takes the
    roomier side at ``min_w`` and stays inside the view, where it may cover
    the node. When the network is zoomed out so far that nodes are shorter
    than ``marker_below``, only a marker is drawn beside each node.
    """
    visible = [a for a in anchors if 0.0 <= a.x <= view_w and 0.0 <= a.y <= view_h]
    if not visible:
        return []
    if zoomed_out(visible, m):
        box = m.marker
        return [Placed(a.key, a.x + m.dot_gap, a.y - box / 2.0, box, box, (), True)
                for a in visible if measure(a.key, m.bubble_w) is not None]
    placed: list = []
    for a in sorted(visible, key=lambda item: (item.y, item.x)):
        options = [c for c in (_candidate(a, "right", measure, view_w, m, placed),
                               _candidate(a, "left", measure, view_w, m, placed))
                   if c is not None]
        if not options:
            continue
        fitting = [c for c in options if c[0]]
        if fitting:
            best = min(fitting, key=lambda c: c[1])      # stable: right wins ties
        else:
            best = max(options, key=lambda c: c[2])      # the roomier side
        placed.append(best[3])
    return placed


def leader(p: Placed, radius: float):
    """The line from a displaced bubble's tail to its edge, or None.

    A bubble centred on its node needs no line: the tail dots already point at
    it. One that stacking pushed away from its node gets a line from the large
    dot to the nearest point on its side edge, so it still reads as that
    node's bubble.
    """
    if p.marker or not p.dots:
        return None
    (_sx, node_y, _sr), (lx, ly, lr) = p.dots
    if p.y <= node_y <= p.y + p.h:
        return None
    edge_x = p.x if p.side == "right" else p.x + p.w
    start_x = lx + lr if p.side == "right" else lx - lr
    edge_y = min(max(ly, p.y + radius), p.y + p.h - radius)
    return ((start_x, ly), (edge_x, edge_y))
