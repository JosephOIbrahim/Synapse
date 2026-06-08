"""Tokenized motion helpers.

Qt QSS has no transition primitive, so all easing is QPropertyAnimation in
Python with durations/easings pulled from the token table — replacing the
scattered 200/500/600/800ms magic numbers the audit found.
"""

try:
    from PySide6 import QtWidgets
    from PySide6.QtCore import QPropertyAnimation, QEasingCurve
except ImportError:  # pragma: no cover - Houdini ships PySide6
    from PySide2 import QtWidgets
    from PySide2.QtCore import QPropertyAnimation, QEasingCurve

from . import tokens as t


def _ease():
    """Resolve the EASE token to a QEasingCurve, PySide2/6-safe."""
    try:
        return getattr(QEasingCurve.Type, t.EASE)   # PySide6
    except AttributeError:
        return getattr(QEasingCurve, t.EASE, QEasingCurve.OutCubic)  # PySide2


def fade_in(widget, duration=t.DUR_BASE):
    """Fade a widget from transparent to opaque. Returns the animation."""
    if t.reduced_motion():
        duration = 0   # honor reduced-motion — jump straight to opaque
    eff = QtWidgets.QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(eff)
    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(_ease())
    widget._ds_fade_anim = anim  # keep a ref so it isn't GC'd mid-flight
    anim.start()
    return anim


def fade_out(widget, duration=t.DUR_FAST, on_done=None):
    """Fade a widget to transparent; optionally call on_done() when finished."""
    if t.reduced_motion():
        duration = 0   # honor reduced-motion — jump straight to transparent
    eff = QtWidgets.QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(eff)
    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(_ease())
    if on_done is not None:
        anim.finished.connect(on_done)
    widget._ds_fade_anim = anim
    anim.start()
    return anim


def flash(widget, prop=b"maximumHeight", to=None, duration=t.DUR_SLOW):
    """Generic eased property tween (e.g. height for a drawer reveal)."""
    if t.reduced_motion():
        duration = 0   # honor reduced-motion — jump straight to the end value
    anim = QPropertyAnimation(widget, prop, widget)
    anim.setDuration(duration)
    anim.setEndValue(to)
    anim.setEasingCurve(_ease())
    widget._ds_flash_anim = anim
    anim.start()
    return anim
