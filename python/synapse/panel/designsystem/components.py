"""Tokenized component library — consumed everywhere.

A small set of styled QWidget subclasses (Button, Pill, Card, Badge, StatusDot,
ProgressBar + label/divider factories) that set objectName + dynamic properties
and let the single generated QSS (qss.stylesheet) style them. Replaces the
per-file inline styling + hardcoded hex the audit found. PySide6 primary,
PySide2 fallback. Avoids QFrame for cards (Houdini global styles eat clicks on
QFrame) — uses QWidget + WA_StyledBackground.
"""

try:
    from PySide6 import QtWidgets, QtGui, QtCore
    from PySide6.QtCore import Qt
except ImportError:  # pragma: no cover - Houdini ships PySide6
    from PySide2 import QtWidgets, QtGui, QtCore
    from PySide2.QtCore import Qt

from . import tokens as t
from . import fontload

__all__ = [
    "Button", "Pill", "Card", "Badge", "StatusDot", "MarkDot", "ProgressBar",
    "label", "divider", "apply_font_role", "repolish",
]


def repolish(w):
    """Re-apply QSS after a dynamic property change (variant/tone/kind)."""
    st = w.style()
    st.unpolish(w)
    st.polish(w)
    w.update()


def apply_font_role(w, role="body", scale=1.0):
    """Apply family/size/weight/tracking from a TYPE_ROLE. v9 ratified call:
    the family is the bundled pair (Space Grotesk sans / Space Mono for the
    mono-stack roles), applied via QFont with fontload's graceful native
    fallback when the bundle didn't register (build_mismatch)."""
    fam, size, weight, tracking = t.TYPE_ROLES.get(role, t.TYPE_ROLES["body"])
    f = QtGui.QFont(w.font())  # inherit host attrs (hinting, style strategy)
    fontload.apply_family(f, mono=(fam == t.FONT_MONO_CSS))
    f.setPixelSize(t.scaled(size, scale))
    f.setBold(weight >= 600)
    if tracking:
        try:
            f.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, tracking)
        except Exception:
            pass
    w.setFont(f)
    return w


class Button(QtWidgets.QPushButton):
    """Variant button: primary | secondary | ghost | danger."""

    def __init__(self, text="", variant="primary", parent=None):
        super().__init__(text, parent)
        self.setObjectName("DsButton")
        self.setProperty("variant", variant)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_variant(self, variant):
        self.setProperty("variant", variant)
        repolish(self)


class Pill(QtWidgets.QPushButton):
    """Small context-action pill (mono, rounded)."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("DsPill")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class Card(QtWidgets.QWidget):
    """Surface container. tone: None | warn | approve | critical (border hue)."""

    def __init__(self, tone=None, parent=None):
        super().__init__(parent)
        self.setObjectName("DsCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        if tone:
            self.setProperty("tone", tone)

    def set_tone(self, tone):
        self.setProperty("tone", tone or "")
        repolish(self)


class Badge(QtWidgets.QLabel):
    """Tiny status chip. kind: None | grow | warn | error | signal."""

    def __init__(self, text="", kind=None, parent=None):
        super().__init__(text, parent)
        self.setObjectName("DsBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if kind:
            self.setProperty("kind", kind)

    def set_kind(self, kind):
        self.setProperty("kind", kind or "")
        repolish(self)


class StatusDot(QtWidgets.QWidget):
    """A small ring in the status-grammar color (one status vocabulary).

    Monolinear: stroked at ``tokens.STROKE_PX``, no fill, no second tone. The
    default diameter 8 is the 24px icon grid / 3, so it sits on the same rhythm
    as every other drawn glyph.
    """

    def __init__(self, status="idle", diameter=t.ICON_GRID // 3, parent=None):
        super().__init__(parent)
        self._d = diameter
        self._color = t.STATUS.get(status, t.STATUS["idle"])[0]
        self.setFixedSize(diameter + 2, diameter + 2)

    def set_status(self, status):
        self._color = t.STATUS.get(status, t.STATUS["idle"])[0]
        self.update()

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(QtGui.QColor(self._color))
        pen.setWidthF(t.STROKE_PX)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        inset = t.STROKE_PX / 2.0
        p.drawEllipse(QtCore.QRectF(1 + inset, 1 + inset,
                                    self._d - t.STROKE_PX, self._d - t.STROKE_PX))
        p.end()


class MarkDot(QtWidgets.QWidget):
    """The SYNAPSE mark IS the status light.

    A ring at rest, a sweeping half-disc while working, a full disc when done —
    always in the one warm note (WARM). Identity and live state collapse into a
    single element, and because it never borrows Houdini's own orange, SYNAPSE
    keeps a distinct presence in the host. (Pentagram pass.)
    """

    _RESTING = {"idle", "ready", "connected", "disconnected", "warning", "error", ""}

    def __init__(self, state="idle", diameter=16, parent=None):
        super().__init__(parent)
        self._d = diameter
        self._state = state or "idle"
        self._angle = 0
        self._spin = QtCore.QTimer(self)
        self._spin.setInterval(33)  # ~30 fps; only runs while working
        self._spin.timeout.connect(self._tick)
        self.setFixedSize(diameter + 4, diameter + 4)
        self._sync_timer()

    def set_state(self, state):
        state = state or "idle"
        if state == self._state:
            return
        self._state = state
        self._sync_timer()
        self.update()

    def _sync_timer(self):
        # Reduced-motion: a working mark stays a static disc (no sweep).
        if self._state == "working" and not t.reduced_motion():
            if not self._spin.isActive():
                self._spin.start()
        elif self._spin.isActive():
            self._spin.stop()

    def _tick(self):
        self._angle = (self._angle + 6) % 360
        self.update()

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        col = QtGui.QColor(t.WARM)
        m = 2
        # Monolinear: ONE weight, ONE line, no fills and no dual-tone. State is
        # carried by how much of the circle is drawn -- an open ring at rest, a
        # sweeping half-arc while working, a closed ring when done -- never by a
        # second tone or a heavier stroke. Diameter 16 = the 24px grid x 2/3.
        pen = QtGui.QPen(col)
        pen.setWidthF(t.STROKE_PX)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        inset = m + t.STROKE_PX / 2.0
        rect = QtCore.QRectF(inset, inset,
                             self._d - t.STROKE_PX, self._d - t.STROKE_PX)
        if self._state == "working":
            p.drawArc(rect, int(self._angle * 16), 180 * 16)   # sweeping half-arc
        elif self._state == "done":
            p.drawEllipse(rect)                                # closed ring
            # ...plus a check, drawn with the SAME pen: the completed sweep.
            cx, cy, rr = rect.center().x(), rect.center().y(), rect.width() / 2.0
            path = QtGui.QPainterPath()
            path.moveTo(cx - rr * 0.42, cy + rr * 0.02)
            path.lineTo(cx - rr * 0.10, cy + rr * 0.36)
            path.lineTo(cx + rr * 0.46, cy - rr * 0.34)
            p.drawPath(path)
        else:
            # at rest: an OPEN ring -- one gap, same line, nothing started yet.
            p.drawArc(rect, 60 * 16, 300 * 16)
        p.end()


class ProgressBar(QtWidgets.QProgressBar):
    """Thin accent progress bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsProgress")
        self.setTextVisible(False)


_LABEL_COLOR_ROLES = {"title", "body", "caption", "label", "accent"}


def label(text="", role="body", scale=1.0, parent=None):
    """Role-based label: font from TYPE_ROLES, color from the QSS [role] rule."""
    lbl = QtWidgets.QLabel(text, parent)
    lbl.setProperty("role", role if role in _LABEL_COLOR_ROLES else "body")
    apply_font_role(lbl, role if role in t.TYPE_ROLES else "body", scale)
    return lbl


def divider(parent=None):
    """A 1px hairline in the border color."""
    line = QtWidgets.QWidget(parent)
    line.setObjectName("DsDivider")
    line.setFixedHeight(1)
    line.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    line.setStyleSheet(f"background:{t.BORDER};")  # token, not a raw literal
    return line
