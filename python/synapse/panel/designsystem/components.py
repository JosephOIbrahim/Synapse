"""Tokenized component library — consumed everywhere.

A small set of styled QWidget subclasses (Button, Pill, Card, Badge, StatusDot,
ProgressBar + label/divider factories) that set objectName + dynamic properties
and let the single generated QSS (qss.stylesheet) style them. Replaces the
per-file inline styling + hardcoded hex the audit found. PySide6 primary,
PySide2 fallback. Avoids QFrame for cards (Houdini global styles eat clicks on
QFrame) — uses QWidget + WA_StyledBackground.
"""

try:
    from PySide6 import QtWidgets, QtGui
    from PySide6.QtCore import Qt
except ImportError:  # pragma: no cover - Houdini ships PySide6
    from PySide2 import QtWidgets, QtGui
    from PySide2.QtCore import Qt

from . import tokens as t

__all__ = [
    "Button", "Pill", "Card", "Badge", "StatusDot", "ProgressBar",
    "label", "divider", "apply_font_role", "repolish",
]


def repolish(w):
    """Re-apply QSS after a dynamic property change (variant/tone/kind)."""
    st = w.style()
    st.unpolish(w)
    st.polish(w)
    w.update()


def apply_font_role(w, role="body", scale=1.0):
    """Apply size/weight/tracking from a TYPE_ROLE while INHERITING Houdini's
    native app-level UI font — only the ``code`` role forces the mono family
    (paths / data). This is what makes the panel read as native, not web."""
    _fam, size, weight, tracking = t.TYPE_ROLES.get(role, t.TYPE_ROLES["body"])
    f = QtGui.QFont(w.font())  # start from the inherited native UI font
    if role == "code":
        f.setFamily(t.FONT_MONO)
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
        self.setCursor(Qt.PointingHandCursor)

    def set_variant(self, variant):
        self.setProperty("variant", variant)
        repolish(self)


class Pill(QtWidgets.QPushButton):
    """Small context-action pill (mono, rounded)."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("DsPill")
        self.setCursor(Qt.PointingHandCursor)


class Card(QtWidgets.QWidget):
    """Surface container. tone: None | warn | approve | critical (border hue)."""

    def __init__(self, tone=None, parent=None):
        super().__init__(parent)
        self.setObjectName("DsCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
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
        self.setAlignment(Qt.AlignCenter)
        if kind:
            self.setProperty("kind", kind)

    def set_kind(self, kind):
        self.setProperty("kind", kind or "")
        repolish(self)


class StatusDot(QtWidgets.QWidget):
    """A small filled dot in the status-grammar color (one status vocabulary)."""

    def __init__(self, status="idle", diameter=8, parent=None):
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
        p.setPen(Qt.NoPen)
        p.setBrush(QtGui.QColor(self._color))
        p.drawEllipse(1, 1, self._d, self._d)
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
    line.setAttribute(Qt.WA_StyledBackground, True)
    line.setStyleSheet(f"background:{t.BORDER};")  # token, not a raw literal
    return line
