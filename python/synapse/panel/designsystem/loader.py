"""BouncingToy — SYNAPSE's "thinking" loader.

A squash-and-stretch bouncing rubber toy (the classic Houdini test-geometry
animation archetype), painted in the SYNAPSE accent with a contact shadow.
Replaces the old typing indicator that re-inserted "SYNAPSE is thinking…" every
tick and accumulated dozens of copies in the chat.
"""

import math

try:
    from PySide6 import QtWidgets, QtGui, QtCore
    from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property, QRectF
except ImportError:  # pragma: no cover - Houdini ships PySide6
    from PySide2 import QtWidgets, QtGui, QtCore
    from PySide2.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property, QRectF

from . import tokens as t


class BouncingToy(QtWidgets.QWidget):
    """A looping squash-and-stretch bounce. start()/stop() control the anim."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self.setFixedSize(56, 38)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._anim = QPropertyAnimation(self, b"phase", self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(680)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.Linear)  # the parabola does the bounce

    def start(self):
        if t.reduced_motion():   # honor reduced-motion — no bounce loop
            return
        if self._anim.state() != QPropertyAnimation.Running:
            self._anim.start()

    def stop(self):
        self._anim.stop()

    def _get_phase(self):
        return self._phase

    def _set_phase(self, value):
        self._phase = value
        self.update()

    phase = Property(float, _get_phase, _set_phase)

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx = w / 2.0
        r = 8.0
        top_y = r + 2
        ground_y = h - r - 4

        ph = self._phase
        # up: 0 at the loop ends (ground contact), 1 at mid (apex) — so the ball
        # is fast near the ground and "hangs" at the top, the natural bounce feel.
        up = 4.0 * ph * (1.0 - ph)
        contact = 1.0 - up                       # 1 on the ground, 0 at apex
        cy = ground_y - (ground_y - top_y) * up

        squash = 0.38 * contact                  # round at apex, squashed on impact
        rx = r * (1.0 + squash)
        ry = r * (1.0 - squash)

        # contact shadow — wider + darker the closer to the ground
        p.setPen(Qt.NoPen)
        sh_w = rx * (0.7 + 0.9 * contact)
        p.setBrush(QtGui.QColor(0, 0, 0, int(70 * (0.35 + 0.65 * contact))))
        p.drawEllipse(QtCore.QRectF(cx - sh_w, ground_y + ry - 2, sh_w * 2, 4.5))

        # the toy — warm coral (Cohere's human accent), not the cool link-blue
        p.setBrush(QtGui.QColor(t.WARM))
        p.drawEllipse(QtCore.QRectF(cx - rx, cy - ry, rx * 2, ry * 2))
        # soft highlight
        p.setBrush(QtGui.QColor(255, 255, 255, 70))
        p.drawEllipse(QtCore.QRectF(cx - rx * 0.35, cy - ry * 0.55, rx * 0.5, ry * 0.4))
        p.end()
