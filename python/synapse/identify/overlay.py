"""Identify bubbles drawn over the network editor: the paint layer.

Houdini draws its whole main window in one native OpenGL surface
(``RE_WindowDrawable``, probed live on 22.0.400), so a plain child widget would
sit underneath it. The overlay is therefore its own window: frameless,
see-through and click-through, owned by the Houdini window that holds the
network editor. It stays above that window, moves with it and minimizes with
it, and it covers only the editor's drawing area, below the editor's toolbar.

Nothing here writes to the scene: no comments, no flags, no undo entries.
While bubbles are shown a timer follows pan, zoom, pane moves and network
changes, and it stops when they are cleared. Colours, fonts, spacing and radii
come from the panel design system and are scaled by the host font, the same way
the panel scales itself.

Main thread only. ``hou`` and Qt are import-guarded, so the module imports on
system Python; ``read_state``, ``chip_text``, ``rows`` and the controller are
tested there with fakes.
"""
from __future__ import annotations

import logging

from synapse.panel.designsystem import tokens as _t

from . import layout as _layout
from .bubble import CAP

_log = logging.getLogger(__name__)

try:  # pragma: no cover - live Houdini only
    import hou
except ImportError:  # pragma: no cover
    hou = None

try:  # pragma: no cover - Houdini ships PySide6
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover
    try:
        from PySide2 import QtCore, QtGui, QtWidgets
    except ImportError:
        QtCore = QtGui = QtWidgets = None


#: Timer period while bubbles are shown. 30 Hz follows a pan smoothly; a tick
#: that finds nothing moved does not repaint.
TICK_MS = 33

#: Bubble anatomy in unscaled pixels, from the Identify Bubbles canvas
#: (option 1). Colours, fonts, padding and radii are design-system tokens.
BUBBLE_W = 300
MIN_W = 200                # narrowest a bubble gets when its node has little room
TAG_PX = 11                # Space Mono tags and paths
MARK_PX = 10               # the SYNAPSE ring's box
MARK_STROKE = 1.8
DOT_SMALL_R = 2.0          # tail dots: 4 px and 7 px across
DOT_LARGE_R = 3.5
DOT_GAP = 5
CHIP_PAD_V = 6
LEADER_ALPHA = 140         # a displaced bubble's leader line: quiet, but visible

#: Nodes drawn shorter than this share of a text line get a marker instead of
#: a bubble: at that zoom a bubble no longer reads as belonging to its node.
MARKER_BELOW = 0.5

#: Node name labels run about 0.07 to 0.11 network units per character on
#: 22.0.400 (probed with ``networkItemsInBox``). 0.1 keeps the tail just clear
#: of the name without measuring every label on every tick.
NAME_UNITS_PER_CHAR = 0.1

CHIP_LABEL = "Identify"
NOT_IN_LIBRARY = "Not in the local SideFX library."
NO_EDITOR = "Identify needs a network editor to draw on."

_OVERLAY = None            # the live overlay window, or None
_OVERLAY_CLASS = None      # built on first use, when Qt is present


# ---------------------------------------------------------------------------
# Pure pieces (no Qt): what is written, and where the nodes are
# ---------------------------------------------------------------------------

def chip_text(shown: int, total: int, zoomed_out: bool = False, cleaned: int = 0) -> str:
    """The chip's text after the ``Identify`` label."""
    parts = [f"{shown} of {total} nodes"]
    if zoomed_out:
        parts.append("zoom in to read")
    if cleaned:
        parts.append(f"{cleaned} old note{'' if cleaned == 1 else 's'} removed")
    return " · ".join(parts)


def rows(model: dict) -> list:
    """The rows under a bubble's header, top to bottom.

    Each row is ``("text", text, font, ink)`` or ``("writes", path, more)``.
    A node with no library row says so in a quiet ink instead of guessing.
    """
    out: list = []
    summary = model.get("summary")
    if summary:
        out.append(("text", summary, "body", "body"))
    else:
        out.append(("text", NOT_IN_LIBRARY, "body", "quiet"))
    writes = model.get("writes")
    if writes:
        out.append(("writes", str(writes.get("path") or ""), int(writes.get("more") or 0)))
    changes = model.get("changes")
    if changes:
        out.append(("text", changes, "body", "detail"))
    state = model.get("state")
    if state:
        if state.startswith("error:"):
            ink = "error"
        elif state.startswith("warning:"):
            ink = "warning"
        else:
            ink = "quiet"
        out.append(("text", state, "body", ink))
    return out


def _editor_errors() -> tuple:
    """What a pane tab raises once it is gone, plus Qt's deleted-object error."""
    errors = [RuntimeError]
    for name in ("ObjectWasDeleted", "OperationFailed", "NotAvailable"):
        err = getattr(hou, name, None)
        if isinstance(err, type) and issubclass(err, BaseException):
            errors.append(err)
    return tuple(errors)


def read_state(editor, order):
    """Where the editor's drawing area is and where each identified node sits.

    Returns None while the editor's tab is hidden or has no area. Otherwise it
    returns ``(area, anchors, alive)``. *area* is the drawing area in global Qt
    coordinates ``(x, y, w, h)``: the pane minus the toolbar above it. *anchors*
    holds the identified nodes in the editor's current network, in window
    pixels. *alive* counts identified nodes that still exist in any network.
    """
    if not editor.isCurrentTab():
        return None
    geo = editor.qtScreenGeometry()
    size = editor.screenBounds().size()
    view_w, view_h = float(size[0]), float(size[1])
    if view_w <= 0 or view_h <= 0 or geo.width() <= 0 or geo.height() <= 0:
        return None
    k = geo.width() / view_w              # editor pixels -> Qt pixels (1.0 at DPR 1)
    area_h = int(round(view_h * k))
    area = (geo.x(), geo.y() + geo.height() - area_h, geo.width(), area_h)
    here = editor.pwd().sessionId()
    unit = editor.lengthToScreen(1.0) * k
    anchors = []
    alive = 0
    for key in order:
        node = hou.nodeBySessionId(key)
        if node is None:
            continue
        alive += 1
        parent = node.parent()
        if parent is None or parent.sessionId() != here:
            continue
        pos, box = node.position(), node.size()
        point = editor.posToScreen(hou.Vector2(pos[0] + box[0], pos[1] + box[1] * 0.5))
        x, y = _layout.window_point(point[0] * k, point[1] * k, area_h)
        anchors.append(_layout.Anchor(
            key, round(x, 1), round(y, 1), round(box[1] * unit, 1),
            round(NAME_UNITS_PER_CHAR * len(node.name()) * unit, 1),
            round(box[0] * unit, 1)))
    return area, tuple(anchors), alive


# ---------------------------------------------------------------------------
# Qt pieces: style, measuring, painting
# ---------------------------------------------------------------------------

def host_scale() -> float:
    """Houdini's UI scale as the panel reads it: host font pixels / SIZE_BODY."""
    app = QtWidgets.QApplication.instance() if QtWidgets is not None else None
    if app is None:
        return 1.0
    px = QtGui.QFontInfo(app.font()).pixelSize()
    return px / float(_t.SIZE_BODY) if px and px > 0 else 1.0


def _flags(*members) -> int:
    value = 0
    for member in members:
        value |= int(getattr(member, "value", member))
    return value


def _with_alpha(color, alpha):
    color.setAlpha(int(alpha))
    return color


def _font(family, fallbacks, px, bold=False):
    font = QtGui.QFont(family)
    font.setFamilies([family, *fallbacks])
    font.setPixelSize(max(1, int(round(px))))
    if bold:
        font.setWeight(QtGui.QFont.Weight.DemiBold)
    return font


class _Style:
    """Fonts, inks and sizes for one host scale, all from the design system."""

    def __init__(self, scale: float):
        Qt = QtCore.Qt
        self.scale = s = max(float(scale), 0.5)
        self.width = BUBBLE_W * s
        self.pad_v = _t.SPACE_SM * s
        self.pad_h = _t.SPACE_12 * s
        self.row_gap = _t.SPACE_XS * s
        self.inline_gap = _t.SPACE_SM * s
        self.radius = _t.RADIUS_MD * s
        self.tail_radius = _t.RADIUS_SM * s
        self.hairline = float(max(1, round(s)))
        self.mark = MARK_PX * s
        self.mark_stroke = MARK_STROKE * s
        self.chip_margin = _t.SPACE_12 * s
        self.chip_pad_v = CHIP_PAD_V * s
        self.chip_pad_h = _t.SPACE_12 * s
        self.min_w = MIN_W * s
        self.fonts = {
            "title": _font(_t.FONT_SANS, _t.FONT_SANS_FALLBACKS, _t.SIZE_BODY * s, bold=True),
            "body": _font(_t.FONT_SANS, _t.FONT_SANS_FALLBACKS, _t.SIZE_BODY * s),
            "mono": _font(_t.FONT_MONO, _t.FONT_MONO_FALLBACKS, TAG_PX * s),
        }
        self.fm = {key: QtGui.QFontMetricsF(font) for key, font in self.fonts.items()}
        self.inks = {
            "surface": QtGui.QColor(_t.CARBON),
            "hairline": QtGui.QColor(_t.BORDER_STRONG),
            "title": QtGui.QColor(_t.TEXT_BRIGHT),
            "body": QtGui.QColor(_t.BONE),
            "detail": QtGui.QColor(_t.TEXT_SECONDARY),
            "quiet": QtGui.QColor(_t.TEXT_TERTIARY),
            "path": QtGui.QColor(_t.SIGNAL),
            "mark": QtGui.QColor(_t.WARM),
            "error": QtGui.QColor(_t.ERROR),
            "warning": QtGui.QColor(_t.WARN),
            "leader": _with_alpha(QtGui.QColor(_t.TEXT_TERTIARY), LEADER_ALPHA),
        }
        self.wrap = _flags(Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignTop,
                           Qt.TextFlag.TextWordWrap)
        self.left_mid = _flags(Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignVCenter)
        self.right_mid = _flags(Qt.AlignmentFlag.AlignRight, Qt.AlignmentFlag.AlignVCenter)

    def header_h(self) -> float:
        return max(self.mark, self.fm["title"].height(), self.fm["mono"].height())

    def text_w(self, width) -> float:
        return max(1.0, width - 2 * self.pad_h)

    def row_h(self, row, text_w) -> float:
        if row[0] == "writes":
            return max(self.fm["body"].height(), self.fm["mono"].height())
        _kind, text, font, _ink = row
        box = QtCore.QRectF(0.0, 0.0, text_w, 1.0e6)
        return self.fm[font].boundingRect(box, self.wrap, text).height()


def bubble_height(style, model, width) -> float:
    """Height of one bubble drawn *width* pixels wide; its text wraps to fit."""
    text_w = style.text_w(width)
    height = style.pad_v * 2 + style.header_h()
    for row in rows(model):
        height += style.row_gap + style.row_h(row, text_w)
    return height


def _chip_size(style, text) -> tuple:
    fm_t, fm_b = style.fm["title"], style.fm["body"]
    height = max(fm_t.height(), fm_b.height(), style.mark) + 2 * style.chip_pad_v
    width = (2 * style.chip_pad_h + style.mark + style.inline_gap
             + fm_t.horizontalAdvance(CHIP_LABEL) + style.inline_gap
             + fm_b.horizontalAdvance(text))
    return (width, height)


def _layout_metrics(style, chip_h) -> _layout.Metrics:
    s = style.scale
    return _layout.Metrics(
        name_gap=_t.SPACE_12 * s, dot_small=DOT_SMALL_R * s, dot_large=DOT_LARGE_R * s,
        dot_gap=DOT_GAP * s, bubble_gap=_t.SPACE_12 * s, stack_gap=_t.SPACE_SM * s,
        top_reserved=style.chip_margin + chip_h + _t.SPACE_SM * s,
        marker_below=MARKER_BELOW * style.fm["body"].height(), marker=style.mark,
        margin=style.chip_margin, bubble_w=style.width, min_w=style.min_w)


def _bubble_path(x, y, w, h, r, rt, side="right"):
    """A rounded rectangle whose bottom corner nearest the node is tighter."""
    bl, br = (rt, r) if side == "right" else (r, rt)
    path = QtGui.QPainterPath()
    path.moveTo(x + r, y)
    path.lineTo(x + w - r, y)
    path.arcTo(x + w - 2 * r, y, 2 * r, 2 * r, 90, -90)
    path.lineTo(x + w, y + h - br)
    path.arcTo(x + w - 2 * br, y + h - 2 * br, 2 * br, 2 * br, 0, -90)
    path.lineTo(x + bl, y + h)
    path.arcTo(x, y + h - 2 * bl, 2 * bl, 2 * bl, 270, -90)
    path.lineTo(x, y + r)
    path.arcTo(x, y, 2 * r, 2 * r, 180, -90)
    path.closeSubpath()
    return path


def _pen(color, width):
    pen = QtGui.QPen(color)
    pen.setWidthF(float(width))
    return pen


def _paint_mark(painter, style, cx, cy):
    painter.setPen(_pen(style.inks["mark"], style.mark_stroke))
    painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
    radius = style.mark * 0.35
    painter.drawEllipse(QtCore.QPointF(cx, cy), radius, radius)


def _paint_writes(painter, style, left, top, height, row, text_w):
    Qt = QtCore.Qt
    _kind, path, more = row
    fm_body, fm_mono = style.fm["body"], style.fm["mono"]
    label = "writes"
    painter.setFont(style.fonts["body"])
    painter.setPen(style.inks["quiet"])
    label_w = fm_body.horizontalAdvance(label)
    painter.drawText(QtCore.QRectF(left, top, label_w + 1, height), style.left_mid, label)
    x = left + label_w + style.inline_gap * 0.75
    suffix = f" (+{more})" if more else ""
    suffix_w = fm_body.horizontalAdvance(suffix) if suffix else 0.0
    room = max(0.0, left + text_w - x - suffix_w)
    shown = fm_mono.elidedText(path, Qt.TextElideMode.ElideMiddle, room)
    path_w = fm_mono.horizontalAdvance(shown)
    painter.setFont(style.fonts["mono"])
    painter.setPen(style.inks["path"])
    painter.drawText(QtCore.QRectF(x, top, path_w + 1, height), style.left_mid, shown)
    if suffix:
        painter.setFont(style.fonts["body"])
        painter.setPen(style.inks["quiet"])
        painter.drawText(QtCore.QRectF(x + path_w, top, suffix_w + 1, height),
                         style.left_mid, suffix)


def _paint_leader(painter, style, placed):
    line = _layout.leader(placed, style.radius)
    if line is not None:
        painter.setPen(_pen(style.inks["leader"], style.hairline))
        painter.drawLine(QtCore.QPointF(*line[0]), QtCore.QPointF(*line[1]))


def _paint_bubble(painter, style, placed, model):
    Qt = QtCore.Qt
    x, y, w, h = placed.x, placed.y, placed.w, placed.h
    painter.setPen(_pen(style.inks["hairline"], style.hairline))
    painter.setBrush(style.inks["surface"])
    for cx, cy, radius in placed.dots:
        painter.drawEllipse(QtCore.QPointF(cx, cy), radius, radius)
    painter.drawPath(_bubble_path(x, y, w, h, style.radius, style.tail_radius, placed.side))

    top = y + style.pad_v
    head_h = style.header_h()
    left = x + style.pad_h
    _paint_mark(painter, style, left + style.mark / 2.0, top + head_h / 2.0)
    tag = model.get("tag") or ""
    tag_w = style.fm["mono"].horizontalAdvance(tag) if tag else 0.0
    title_x = left + style.mark + style.inline_gap
    title_w = max(0.0, x + w - style.pad_h - title_x - (tag_w + style.inline_gap if tag else 0.0))
    title = style.fm["title"].elidedText(model.get("title") or "", Qt.TextElideMode.ElideRight, title_w)
    painter.setFont(style.fonts["title"])
    painter.setPen(style.inks["title"])
    painter.drawText(QtCore.QRectF(title_x, top, title_w, head_h), style.left_mid, title)
    if tag:
        painter.setFont(style.fonts["mono"])
        painter.setPen(style.inks["quiet"])
        painter.drawText(QtCore.QRectF(x + w - style.pad_h - tag_w, top, tag_w + 1, head_h),
                         style.right_mid, tag)

    text_w = style.text_w(w)
    cursor = top + head_h
    for row in rows(model):
        cursor += style.row_gap
        row_h = style.row_h(row, text_w)
        if row[0] == "writes":
            _paint_writes(painter, style, left, cursor, row_h, row, text_w)
        else:
            _kind, text, font, ink = row
            painter.setFont(style.fonts[font])
            painter.setPen(style.inks[ink])
            painter.drawText(QtCore.QRectF(left, cursor, text_w, row_h), style.wrap, text)
        cursor += row_h


def _paint_chip(painter, style, text):
    width, height = _chip_size(style, text)
    x = y = style.chip_margin
    painter.setPen(_pen(style.inks["hairline"], style.hairline))
    painter.setBrush(style.inks["surface"])
    painter.drawRoundedRect(QtCore.QRectF(x, y, width, height), style.radius, style.radius)
    cx = x + style.chip_pad_h
    _paint_mark(painter, style, cx + style.mark / 2.0, y + height / 2.0)
    tx = cx + style.mark + style.inline_gap
    label_w = style.fm["title"].horizontalAdvance(CHIP_LABEL)
    painter.setFont(style.fonts["title"])
    painter.setPen(style.inks["title"])
    painter.drawText(QtCore.QRectF(tx, y, label_w + 1, height), style.left_mid, CHIP_LABEL)
    text_w = style.fm["body"].horizontalAdvance(text)
    painter.setFont(style.fonts["body"])
    painter.setPen(style.inks["body"])
    painter.drawText(QtCore.QRectF(tx + label_w + style.inline_gap, y, text_w + 1, height),
                     style.left_mid, text)


def _build_overlay_class():
    Qt = QtCore.Qt

    class IdentifyOverlay(QtWidgets.QWidget):
        """A click-through window over one network editor's drawing area."""

        def __init__(self, editor):
            flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                     | Qt.WindowType.WindowTransparentForInput
                     | Qt.WindowType.WindowDoesNotAcceptFocus
                     | Qt.WindowType.NoDropShadowWindowHint)
            super().__init__(editor.qtParentWindow(), flags)
            self.setObjectName("SynapseIdentifyOverlay")
            for attr in (Qt.WidgetAttribute.WA_TranslucentBackground,
                         Qt.WidgetAttribute.WA_ShowWithoutActivating,
                         Qt.WidgetAttribute.WA_TransparentForMouseEvents):
                self.setAttribute(attr, True)
            self.editor = editor
            self.style_ = _Style(host_scale())
            self.metrics_ = None
            self.order = []
            self.models = {}
            self.heights = {}
            self.total = 0
            self.cleaned = 0
            self.placed = []
            self.zoomed = False
            self.signature = None
            self.timer = QtCore.QTimer(self)
            self.timer.setInterval(TICK_MS)
            self.timer.timeout.connect(self.tick)

        def set_entries(self, entries, total, cleaned):
            self.order = [key for key, _model in entries]
            self.models = dict(entries)
            self.heights = {}
            self.total, self.cleaned = total, cleaned
            chip = chip_text(len(self.order), total, False, cleaned)
            self.metrics_ = _layout_metrics(self.style_, _chip_size(self.style_, chip)[1])
            self.signature = None

        def tick(self):
            try:
                state = read_state(self.editor, self.order)
            except _editor_errors() as exc:
                _log.debug("Identify overlay: the network editor went away (%s)", exc)
                clear()
                return
            if state is None:
                self.signature = None
                self.hide()
                return
            area, anchors, alive = state
            if alive == 0:
                clear()
                return
            signature = (area, anchors)
            if signature == self.signature and self.isVisible():
                return
            self.signature = signature
            x, y, w, h = area
            self.setGeometry(x, y, w, h)
            self.zoomed = _layout.zoomed_out(anchors, self.metrics_)
            self.placed = _layout.place(anchors, self.measure, w, h, self.metrics_)
            if not self.isVisible():
                self.show()
            self.update()

        def measure(self, key, width):
            """Bubble height at *width*, cached; None for a node it does not show."""
            model = self.models.get(key)
            if model is None:
                return None
            slot = (key, int(round(width)))
            if slot not in self.heights:
                self.heights[slot] = bubble_height(self.style_, model, width)
            return self.heights[slot]

        def paintEvent(self, _event):
            painter = QtGui.QPainter(self)
            try:
                painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
                _paint_chip(painter, self.style_,
                            chip_text(len(self.order), self.total, self.zoomed, self.cleaned))
                # Leaders first, so every bubble covers any line that crosses it.
                for placed in self.placed:
                    _paint_leader(painter, self.style_, placed)
                for placed in self.placed:
                    model = self.models.get(placed.key)
                    if model is None:
                        continue
                    if placed.marker:
                        _paint_mark(painter, self.style_, placed.x + placed.w / 2.0,
                                    placed.y + placed.h / 2.0)
                    else:
                        _paint_bubble(painter, self.style_, placed, model)
            finally:
                painter.end()

    return IdentifyOverlay


def _overlay_class():
    global _OVERLAY_CLASS
    if _OVERLAY_CLASS is None:
        _OVERLAY_CLASS = _build_overlay_class()
    return _OVERLAY_CLASS


def _load_fonts() -> None:
    from synapse.panel.designsystem import fontload
    fontload.load_application_fonts()


def _same_editor(a, b) -> bool:
    try:
        return a.name() == b.name()
    except _editor_errors():
        return False


# ---------------------------------------------------------------------------
# Controller: the panel's Identify worker calls these on the main thread
# ---------------------------------------------------------------------------

def is_active() -> bool:
    """True while bubbles are shown."""
    return _OVERLAY is not None


def is_showing(keys) -> bool:
    """True when the bubbles on screen are exactly these nodes."""
    return _OVERLAY is not None and frozenset(keys) == frozenset(_OVERLAY.order)


def show(entries, total=None, editor=None, cleaned=0) -> dict:
    """Draw a bubble for each ``(sessionId, model)`` entry over *editor*.

    Replaces whatever the overlay showed before. Draws at most :data:`CAP`
    bubbles; *total* is the full selection count for the chip. Without an
    editor (hython, no UI) nothing is drawn and the result says why.
    """
    global _OVERLAY
    entries = [(key, model) for key, model in entries][:CAP]
    total = len(entries) if total is None else int(total)
    if editor is None or hou is None or QtWidgets is None:
        return {"action": "show", "shown": 0, "total": total, "reason": NO_EDITOR}
    if _OVERLAY is not None and not _same_editor(_OVERLAY.editor, editor):
        clear()
    if _OVERLAY is None:
        _load_fonts()
        _OVERLAY = _overlay_class()(editor)
    _OVERLAY.set_entries(entries, total, cleaned)
    _OVERLAY.timer.start()
    _OVERLAY.tick()
    if _OVERLAY is None:  # the first tick found the editor or every node gone
        return {"action": "show", "shown": 0, "total": total, "reason": NO_EDITOR}
    return {"action": "show", "shown": len(entries), "total": total, "cleaned": cleaned}


def clear() -> dict:
    """Take every bubble away. Nothing in the scene changes."""
    global _OVERLAY
    overlay, _OVERLAY = _OVERLAY, None
    if overlay is None:
        return {"action": "clear", "removed": 0}
    removed = len(overlay.order)
    overlay.timer.stop()
    overlay.hide()
    overlay.deleteLater()
    return {"action": "clear", "removed": removed}


def toggle(entries, total=None, editor=None, cleanup=None) -> dict:
    """Clear when these exact nodes are already shown, otherwise show them.

    *cleanup* runs only on the show path, before drawing; the Identify worker
    passes the legacy comment cleanup, and its count appears in the chip.
    """
    entries = list(entries)
    if is_showing(key for key, _model in entries):
        return clear()
    cleaned = cleanup() if cleanup is not None else 0
    return show(entries, total=total, editor=editor, cleaned=cleaned)
