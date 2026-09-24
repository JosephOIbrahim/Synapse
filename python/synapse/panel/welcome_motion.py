"""Bounded motion for the fitted welcome overlay; never changes chat layout."""

try:
    from PySide6 import QtCore, QtWidgets
except ImportError:  # pragma: no cover - Qt5 host fallback
    from PySide2 import QtCore, QtWidgets

from synapse.panel.designsystem import tokens as t


class WelcomeMotion(QtCore.QObject):
    """One entrance and one dismissal per empty conversation.

    The widget's fitted rectangle is the resting position. Only a vertical
    offset and opacity change, so refitting a dock never restarts the clock.
    Hidden/undersized docks settle active motion and retain its outcome.
    """

    def __init__(self, widget, parent=None):
        super().__init__(parent)
        self._widget = widget
        self._target = QtCore.QRect()
        self._distance = 0
        self._available = False
        self._phase = "pending"
        self._offset = 0.0
        self._opacity = 1.0
        self._effect = QtWidgets.QGraphicsOpacityEffect(widget)
        self._effect.setOpacity(1.0)
        self._effect.setEnabled(False)
        widget.setGraphicsEffect(self._effect)
        self._animation = QtCore.QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.valueChanged.connect(self._frame)
        self._animation.finished.connect(self._finish)

    def show_at(self, rect, distance, ready=True):
        """Refit without replaying; wait for the first visible, usable dock."""
        self._available = rect is not None and ready
        if rect is not None:
            self._target = QtCore.QRect(rect)
        self._distance = distance
        if not self._available:
            self.suspend()
            return
        if self._phase == "pending":
            self._start("entering", -distance, 0.0, 0.0, 1.0,
                        t.DUR_SLOW, QtCore.QEasingCurve.OutCubic)
        elif t.reduced_motion() and self._phase in ("entering", "exiting"):
            self._finish()
        else:
            self._paint_frame()

    def dismiss(self):
        """Yield to intentional interaction, including during the entrance."""
        if self._phase in ("exiting", "dismissed"):
            return
        if self._phase == "pending" or not self._available:
            self.cancel()
            return
        self._start("exiting", self._offset, -self._distance,
                    self._opacity, 0.0, t.DUR_BASE, QtCore.QEasingCurve.InCubic)

    def reset(self):
        """Rearm only when a new empty conversation begins."""
        self.cancel()
        self._phase = "pending"

    def cancel(self):
        """Remove immediately when real content arrives or the owner shuts down."""
        self._animation.stop()
        self._phase = "dismissed"
        self._effect.setEnabled(False)
        self._widget.hide()

    def suspend(self):
        """Stop hidden motion without replaying it when the dock returns."""
        self._available = False
        self._finish()
        self._widget.hide()

    def _start(self, phase, offset_from, offset_to, opacity_from, opacity_to,
               duration, easing):
        self._animation.stop()
        self._phase = phase
        self._offset_from, self._offset_to = offset_from, offset_to
        self._opacity_from, self._opacity_to = opacity_from, opacity_to
        self._offset, self._opacity = offset_from, opacity_from
        if t.reduced_motion():
            self._finish()
            return
        self._effect.setEnabled(True)
        self._animation.setDuration(duration)
        self._animation.setEasingCurve(easing)
        self._paint_frame()
        self._animation.start()

    def _frame(self, value):
        # The preference may change during an animation. There is no polling
        # timer once the bounded animation has finished.
        if t.reduced_motion():
            self._finish()
            return
        self._offset = self._offset_from + (self._offset_to - self._offset_from) * value
        self._opacity = self._opacity_from + (self._opacity_to - self._opacity_from) * value
        self._paint_frame()

    def _finish(self):
        self._animation.stop()
        if self._phase == "entering":
            self._phase = "shown"
            self._offset, self._opacity = 0.0, 1.0
        elif self._phase == "exiting":
            self._phase = "dismissed"
        self._effect.setEnabled(False)
        self._paint_frame()

    def _paint_frame(self):
        self._widget.setVisible(self._available and self._phase not in ("pending", "dismissed"))
        if not self._available or self._phase in ("pending", "dismissed"):
            return
        self._widget.setGeometry(self._target.translated(0, round(self._offset)))
        self._effect.setOpacity(self._opacity)
