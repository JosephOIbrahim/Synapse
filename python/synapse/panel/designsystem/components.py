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
# Module level, NOT inside apply_stylesheet. A lazy import there ran while the
# panel's ws_bridge off-main thread held the import lock and the seat suite died
# with a Windows access violation in importlib._bootstrap.acquire (2026-09-21).
# qss imports only tokens, so there is no cycle to avoid here.
from . import qss

__all__ = [
    "Button", "Pill", "Card", "Badge", "StatusDot", "MarkDot", "ProgressBar",
    "ModelMenu", "ConversationInvitation", "EdgeRow", "ComposerHints", "label", "divider", "apply_font_role", "repolish",
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
    # D4 (READABILITY.md 2026-09-15): this used to be `setBold(weight >= 600)`
    # and nothing else, so a role asking for 500 was silently drawn at 400 --
    # `label` (sans 12/500) threw away a face the variable Space Grotesk really
    # ships. Measured at pixelSize 24: sans 400 ink 184395, sans 500 ink 230308
    # (+24.9%). fontload.tracked_font has carried this exact ladder since v9;
    # this path just never grew it. Same ladder, one owner.
    if weight >= 600:
        f.setBold(True)
    elif weight == 500:
        try:
            f.setWeight(QtGui.QFont.Weight.Medium)   # Qt6
        except Exception:
            try:
                f.setWeight(QtGui.QFont.Medium)      # Qt5 / PySide2
            except Exception:
                pass
    else:
        f.setBold(False)
    if tracking:
        try:
            f.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, tracking)
        except Exception:
            pass
    # PNL-L4 (ruling R3-B): a role in tokens.ROLE_CAPS is quiet by CASE, not by
    # size. Set on the QFont rather than by rewriting the string so the widget's
    # text() still returns what the caller passed — every test and tooltip that
    # reads it back keeps working, and nothing double-uppercases.
    if role in getattr(t, "ROLE_CAPS", ()):
        try:
            f.setCapitalization(QtGui.QFont.Capitalization.AllUppercase)  # Qt6
        except Exception:
            try:
                f.setCapitalization(QtGui.QFont.AllUppercase)             # Qt5
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


class ModelMenu(QtWidgets.QMenu):
    """Native model selection with readable rows and bounded popup geometry.

    The scoped stylesheet enables Qt's own scrolling, preserving keyboard and
    checked-action behavior even for a long local-model list. Full labels stay
    in tooltips when a model name is wider than the screen.
    """

    def __init__(self, parent=None, *, title="", scale=t.FONT_SCALE_DEFAULT):
        super().__init__(title, parent)
        self.setObjectName("DsModelMenu")
        self.setAccessibleName(title or "Choose generation model")
        self.setToolTipsVisible(True)
        self._chrome_scale = scale
        # QMenu caches SH_Menu_Scrollable during construction, before its
        # object name exists. Apply at this popup boundary so Qt receives a
        # StyleChange and creates its scroller; inherited paint alone does
        # not initialize scrolling (Qt 6.8 QMenu::changeEvent).
        apply_stylesheet(self, scale)
        apply_font_role(self, "body", scale)
        repolish(self)  # discard the inherited selector cache from QMenu.__init__
        QtWidgets.QApplication.sendEvent(self, QtCore.QEvent(QtCore.QEvent.Type.StyleChange))
        self.aboutToShow.connect(self._fit_to_screen)

    def _fit_to_screen(self):
        screen = self.screen()
        if screen is None:
            return
        available = screen.availableGeometry()
        limit = max(t.SPACE_48, available.width() - 2 * t.SPACE_SM)
        self.setMaximumWidth(limit)
        self.setMaximumHeight(max(t.SPACE_48, available.height() - 2 * t.SPACE_SM))
        # Leave space for native checkmarks, submenu arrows and both insets.
        text_width = max(t.SPACE_48, limit - t.scaled(t.SPACE_48 * 2, self._chrome_scale))
        fm = self.fontMetrics()
        for action in self.actions():
            if action.isSeparator():
                continue
            full = action.property("model_full_label") or action.text()
            action.setProperty("model_full_label", full)
            action.setToolTip(full)
            action.setText(fm.elidedText(full, Qt.TextElideMode.ElideMiddle, text_width))


class ConversationInvitation(QtWidgets.QWidget):
    """A quiet, left-aligned invitation, separate from conversation history."""

    def __init__(self, parent=None, scale=t.FONT_SCALE_DEFAULT):
        super().__init__(parent)
        self.setObjectName("DsConversationInvitation")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, t.SPACE_LG, 0, t.SPACE_MD)
        layout.setSpacing(t.SPACE_SM)
        self.title = label("What are we building?", role="title", scale=scale)
        self.body = label("Describe a network, inspect your scene, or work through a problem.",
                          role="body", scale=scale)
        for item in (self.title, self.body):
            item.setTextFormat(Qt.TextFormat.PlainText)
            item.setWordWrap(True)
            item.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            layout.addWidget(item)

    def set_scale(self, scale):
        apply_font_role(self.title, "title", scale)
        apply_font_role(self.body, "body", scale)

    def fit_content(self, width, height):
        """Reduce optional invitation copy before any text would be clipped."""
        layout = self.layout()
        self.title.setText("What are we building?")
        self.body.setVisible(True)
        layout.setContentsMargins(0, t.SPACE_LG, 0, t.SPACE_MD)
        layout.invalidate()
        needed = layout.totalHeightForWidth(width)
        if needed > height:
            self.body.hide()
            layout.setContentsMargins(0, t.SPACE_SM, 0, t.SPACE_SM)
            needed = self.title.heightForWidth(width) + 2 * t.SPACE_SM
        if needed > height:
            self.title.setText("Start here")
            needed = self.title.heightForWidth(width) + 2 * t.SPACE_SM
        # At extreme heights (for example a tall artist-owned composer plus
        # active Stop), keep the field/action visible and omit optional copy.
        self.setVisible(needed <= height)
        if needed <= height:
            self.setGeometry(0, 0, width, needed)
            layout.activate()


class EdgeRow(QtWidgets.QWidget):
    """Two natural-size widgets at opposite edges, stacking under pressure."""

    def __init__(self, left, right, parent=None, scale=t.FONT_SCALE_DEFAULT):
        super().__init__(parent)
        self.setObjectName("DsEdgeRow")
        self._gap = t.scaled(t.SPACE_XS, scale)
        self.left, self.right = left, right
        for item in (left, right):
            item.setParent(self)
        policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                       QtWidgets.QSizePolicy.Fixed)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def _stacked(self, width):
        return self.left.sizeHint().width() + self.right.sizeHint().width() + self._gap > width

    def sizeHint(self):
        return QtCore.QSize(self.left.sizeHint().width() + self.right.sizeHint().width() + self._gap,
                            max(self.left.sizeHint().height(), self.right.sizeHint().height()))

    def minimumSizeHint(self):
        return QtCore.QSize(0, max(self.left.fontMetrics().height(), self.right.fontMetrics().height()))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        if self._stacked(width):
            return self._height(self.left, width) + self._gap + self._height(self.right, width)
        return self.sizeHint().height()

    @staticmethod
    def _height(widget, width):
        return max(widget.sizeHint().height(), widget.heightForWidth(width))

    def fit_width(self, width):
        """Reflow after a label update even when the row's size is unchanged."""
        self.setMinimumHeight(self.heightForWidth(width))
        self.updateGeometry()
        self._arrange(self.width())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange(self.width())

    def _arrange(self, width):
        if self._stacked(width):
            first = self._height(self.left, width)
            self.left.setGeometry(0, 0, width, first)
            right_width = min(width, self.right.sizeHint().width())
            self.right.setGeometry(width - right_width, first + self._gap,
                                   right_width, self._height(self.right, right_width))
        else:
            left, right = self.left.sizeHint(), self.right.sizeHint()
            height = max(left.height(), right.height())
            self.left.setGeometry(0, (height - left.height()) // 2, left.width(), left.height())
            self.right.setGeometry(width - right.width(), (height - right.height()) // 2,
                                   right.width(), right.height())


class ComposerHints(EdgeRow):
    """Two instructions anchored to the field edges, stacking when needed."""

    def __init__(self, parent=None, scale=t.FONT_SCALE_DEFAULT):
        left = label("Enter sends", role="body", scale=scale)
        right = label("Shift+Enter newline", role="body", scale=scale)
        for item, alignment in ((left, Qt.AlignmentFlag.AlignLeft),
                                (right, Qt.AlignmentFlag.AlignRight)):
            item.setObjectName("DsComposerHint")
            # Match the header status caption's tracking while keeping body type.
            font = item.font()
            font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, t.TYPE_ROLES["caption"][3])
            item.setFont(font)
            item.setTextFormat(Qt.TextFormat.PlainText)
            item.setWordWrap(True)
            item.setMargin(0)
            item.setAlignment(alignment | Qt.AlignmentFlag.AlignTop)
        super().__init__(left, right, parent, scale)
        self.setObjectName("DsComposerHints")


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
    """The SYNAPSE mark IS the status light — and, while working, the halt.

    Idle = an open outline. Working = the outline FILLING IN, one increment per
    completed step. Done = the outline closed, plus the check. Always in the one
    warm note (WARM), and because it never borrows Houdini's own orange, SYNAPSE
    keeps a distinct presence in the host. (Pentagram pass · P1.)

    Two independent channels, deliberately not mixed (Law 3 — a control reports
    what happened, never what was attempted):

      LENGTH  = accumulation. How much of the ring is drawn is a function of how
                many steps have actually completed. It is never advanced by a
                clock and it never reaches CLOSED while work is in flight, so a
                nearly-full ring cannot be misread as "nearly done".
      ROTATION = liveness. The arc turns so a stalled panel is distinguishable
                from a working one. Rotation moves the arc; it never lengthens
                it, so the animation cannot inflate the progress it draws.

    THE MARK AS THE HALT
    --------------------
    ``set_halt_handler`` binds the mark to the panel's EXISTING Stop. It is one
    control with two surfaces, never a second Stop with its own idea of what
    stopping means: the handler passed in is the same ``_on_stop`` the rail
    button fires. The affordance is STATE-GATED to ``working`` exactly as that
    button is — no pointing hand, no tooltip and no click when nothing is
    running, because a stop offered while the panel is idle is the same lie as
    a consent gate that does not gate (R18, R29).
    """

    # identity_ring keeps the Soft Editorial header's hollow circle in every
    # state. The existing default progress mark remains available to other faces.
    _RESTING = {"idle", "ready", "connected", "disconnected", "warning", "error", ""}

    # Ring geometry, in degrees. The working arc opens at MIN_SWEEP and grows
    # toward MAX_SWEEP; MAX stays short of 360 so "closed" belongs to `done`
    # alone and a long-running job can never paint itself finished.
    MIN_SWEEP = 90
    MAX_SWEEP = 300
    STEPS_TO_FULL = 8       # increments from MIN to MAX; further steps hold at MAX

    def __init__(self, state="idle", diameter=16, parent=None, *, identity_ring=False):
        super().__init__(parent)
        self._d = diameter
        self._identity_ring = identity_ring
        self._state = state or "idle"
        self._angle = 0
        self._steps = 0            # completed steps this cycle -> arc LENGTH
        self._halt = None          # bound Stop handler (the panel's own)
        self._halt_armed = True    # cleared on press, mirroring the Stop button
        self._spin = QtCore.QTimer(self)
        self._spin.setInterval(33)  # ~30 fps; only runs while working
        self._spin.timeout.connect(self._tick)
        self.setFixedSize(diameter + 4, diameter + 4)
        self._sync_timer()
        self._sync_halt_affordance()

    # -- state ------------------------------------------------------------
    def set_state(self, state):
        state = state or "idle"
        if state == self._state:
            return
        self._state = state
        self._sync_timer()
        self._sync_halt_affordance()
        self.update()

    def begin_cycle(self):
        """A new work cycle starts: the ring empties and the halt re-arms."""
        self._steps = 0
        self._halt_armed = True
        self._sync_halt_affordance()
        self.update()

    def advance(self):
        """One step actually completed — the ring grows by one increment.

        Called from the tool-status edge, so the length is a record of work
        that happened. Nothing else may call it, and nothing advances it on a
        timer.
        """
        self._steps += 1
        self.update()

    def progress(self):
        """0.0..1.0 — the drawn fraction between MIN_SWEEP and MAX_SWEEP."""
        if self.STEPS_TO_FULL <= 0:
            return 1.0
        return min(1.0, self._steps / float(self.STEPS_TO_FULL))

    # -- the halt affordance ----------------------------------------------
    def set_halt_handler(self, handler):
        """Bind the panel's EXISTING Stop to the mark. Not a second control."""
        self._halt = handler
        self._sync_halt_affordance()

    def halt_available(self):
        """True only when a press would really abort something right now."""
        return bool(self._halt is not None
                    and self._state == "working"
                    and self._halt_armed)

    def _sync_halt_affordance(self):
        """Cursor + tooltip appear only while the halt is genuinely live."""
        if self.halt_available():
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("Stop — abort the agent loop")
        else:
            self.unsetCursor()
            self.setToolTip("")

    def mousePressEvent(self, event):
        if not self.halt_available():
            return super().mousePressEvent(event)
        self._halt_armed = False      # the press registered — no confusing re-press
        self._sync_halt_affordance()
        self._halt()
        event.accept()

    # -- paint ------------------------------------------------------------
    def _sync_timer(self):
        # Reduced-motion: a working mark stays static (no rotation). Its LENGTH
        # still tracks completed steps, so the honest signal survives.
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
        col = QtGui.QColor(t.CHAT_ASSISTANT if self._identity_ring else t.WARM)
        m = 2
        # Monolinear: ONE weight, ONE line, no fills and no dual-tone. State is
        # carried by how much of the circle is drawn -- an open outline at rest,
        # an arc that FILLS IN as steps land, a closed ring when done -- never by
        # a second tone or a heavier stroke. Diameter 16 = the 24px grid x 2/3.
        pen = QtGui.QPen(col)
        stroke = self._d * 3.0 / 14.0 if self._identity_ring else t.STROKE_PX
        pen.setWidthF(stroke)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        inset = m + stroke / 2.0
        rect = QtCore.QRectF(inset, inset,
                             self._d - stroke, self._d - stroke)
        if self._identity_ring:
            # Keep the hole in every state; progress overlays the existing ring.
            p.setOpacity(0.4 if self._state == "working" else 1.0)
            p.drawEllipse(rect)
            p.setOpacity(1.0)
        if self._state == "working":
            # Length = accumulation, rotation = liveness. Qt angles are
            # 1/16 degree, 0 at 3 o'clock, positive counter-clockwise; the span
            # is negated so the ring fills CLOCKWISE from the rotating head.
            sweep = self.MIN_SWEEP + (self.MAX_SWEEP - self.MIN_SWEEP) * self.progress()
            start = (90 - self._angle) % 360
            p.drawArc(rect, int(start * 16), int(-sweep * 16))
        elif self._identity_ring:
            pass
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
            # at rest: an OPEN outline -- one gap, same line, nothing started.
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


def apply_placeholder_palette(w, color=None):
    """Put QPalette::PlaceholderText under the design system.

    D3 (READABILITY.md 2026-09-15): nothing in ``designsystem/`` owned the input
    placeholder. Qt paints it from ``QPalette::PlaceholderText``, whose default
    is the text colour at 50% alpha -- composited over FIELD_INSET that landed
    on #727272, 3.43:1, under the AA floor, and unreachable from any token.
    Setting the role on a root propagates down the parent chain (dialogs
    included), so one call at the panel root covers every DsInput / DsField.

    Returns ``w`` so it chains; never raises -- a binding without the role (very
    old Qt) leaves Qt's default rather than taking the panel down.
    """
    try:
        role = QtGui.QPalette.ColorRole.PlaceholderText
    except AttributeError:          # pragma: no cover - Qt < 5.12
        try:
            role = QtGui.QPalette.PlaceholderText
        except AttributeError:
            return w
    try:
        pal = w.palette()
        pal.setColor(role, QtGui.QColor(color or t.TEXT_PLACEHOLDER))
        w.setPalette(pal)
    except Exception:               # pragma: no cover - defensive
        pass
    return w


def divider(parent=None):
    """A 1px hairline in the border color."""
    line = QtWidgets.QWidget(parent)
    line.setObjectName("DsDivider")
    line.setFixedHeight(1)
    line.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    line.setStyleSheet(f"background:{t.BORDER};")  # token, not a raw literal
    return line


def apply_stylesheet(widget, scale: float = t.FONT_SCALE_DEFAULT) -> None:
    """Put the generated sheet on a widget, from inside the design system.

    PNL-L5 (2026-09-21). tests/test_panel_rhythm_owner.py counts every raw
    setStyleSheet / setContentsMargins under python/synapse/panel as a RHYTHM
    OWNER, excludes designsystem/ because that is where ownership is meant to
    live, and caps the residual with a ratchet whose own policy reads "ceilings
    may only decrease". A probe that applied the sheet itself added an owner,
    and neither answer available to it was honest: tagging spends the residual,
    and raising the cap is the one move the policy forbids. Applying through the
    design system is the move the ratchet exists to encourage.

    It lives here rather than in qss.py because qss.py's generator is pinned
    byte-for-byte and its file must end on its own marker; components.py is
    already where the apply_* helpers live.
    """
    widget.setStyleSheet(qss.stylesheet(scale))
