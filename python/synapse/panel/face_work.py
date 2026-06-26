"""FaceWork — the Work face: *the walk-away glance* (Pentagram pass, Mile 4).

When the agent is working, this is the surface the artist leaves up and walks
away from. It promotes the live signals that say "it's running, and it's fine":

  · a thinking pulse + the current tool status   (is it moving?)
  · a **cook preview** — a bucket grid           (how far along?)
  · a plan-with-progress, fed by the live tool    (what's it doing, in order?)
    stream and the MOE routing_log
  · the HealthInfographic                          (is it healthy?)

Composed from the proven runtime — it embeds the existing ``HealthInfographic``
and reuses ``routing_log`` rather than reinventing them. Every dependency is
optional so the face always instantiates (graceful degradation is a contract).
"""

try:
    from PySide6 import QtWidgets, QtGui, QtCore
    from PySide6.QtCore import Qt, QTimer
except ImportError:  # pragma: no cover - Houdini ships PySide6
    from PySide2 import QtWidgets, QtGui, QtCore
    from PySide2.QtCore import Qt, QTimer

from synapse.panel.designsystem import tokens as t
from synapse.panel.designsystem import components as c

try:
    from synapse.panel.designsystem.loader import BouncingToy
except Exception:  # pragma: no cover
    BouncingToy = None
try:
    from synapse.panel.health_infographic import HealthInfographic
except Exception:  # pragma: no cover
    HealthInfographic = None
try:
    from synapse.panel.routing_log import get_routing_log
except Exception:  # pragma: no cover
    get_routing_log = None

# tool phase → (glyph, color-token) for the plan-with-progress rows
_PHASE = {
    "running": ("→", t.SIGNAL),
    "done":    ("✓", t.GROW),
    "ok":      ("✓", t.GROW),
    "error":   ("✗", t.ERROR),
    "failed":  ("✗", t.ERROR),
}


class BucketGrid(QtWidgets.QWidget):
    """The cook preview — an N×M grid of buckets that fill as work lands.

    Two modes: *determinate* (``set_progress(done, total)`` maps real cook /
    render progress onto the grid) and an *indeterminate pulse* (a scanline
    sweep) for when the agent is busy but no counted progress is wired yet —
    it reads alive without fabricating a number.
    """

    def __init__(self, cols=8, rows=5, parent=None):
        super().__init__(parent)
        self.setObjectName("DsSection")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._cols, self._rows = cols, rows
        self._n = cols * rows
        self._done = 0
        self._live = set()
        self._determinate = False
        self._head = 0
        self._timer = QTimer(self)
        self._timer.setInterval(110)
        self._timer.timeout.connect(self._tick)
        self.setMinimumHeight(150)

    def sizeHint(self):
        return QtCore.QSize(300, 170)

    # -- state -----------------------------------------------------------
    def set_progress(self, done, total, live=None):
        """Map real cook progress (done/total) onto the grid cells."""
        self._determinate = True
        self.stop_pulse()
        frac = (done / float(total)) if total else 0.0
        self._done = max(0, min(self._n, int(round(frac * self._n))))
        if live:
            self._live = {self._done} if self._done < self._n else set()
        else:
            self._live = set()
        self.update()

    def start_pulse(self):
        """Indeterminate 'busy' sweep (no counted progress available). Honors
        reduced-motion: shows a static grid instead of the scanline sweep."""
        self._determinate = False
        if t.reduced_motion():
            self.update()
            return
        if not self._timer.isActive():
            self._timer.start()

    def stop_pulse(self):
        if self._timer.isActive():
            self._timer.stop()
        self.update()

    def reset(self):
        self._done = 0
        self._live = set()
        self._head = 0
        self._determinate = False
        self.update()

    def _tick(self):
        self._head = (self._head + 1) % self._n
        self.update()

    # -- paint -----------------------------------------------------------
    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor(t.VOID))   # opaque dark ground
        gap = 1.0
        w = (self.width() - (self._cols + 1) * gap) / float(self._cols)
        h = (self.height() - (self._rows + 1) * gap) / float(self._rows)
        pending = QtGui.QColor(t.GROUND)
        done = QtGui.QColor(t.SIGNAL); done.setAlpha(70)
        live = QtGui.QColor(t.GROW); live.setAlpha(175)
        trail = 6
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(self._n):
            r, col = divmod(i, self._cols)
            x = gap + col * (w + gap)
            y = gap + r * (h + gap)
            color = pending
            if self._determinate:
                if i in self._live:
                    color = live
                elif i < self._done:
                    color = done
            else:
                dist = (self._head - i) % self._n
                if i == self._head:
                    color = live
                elif dist < trail:
                    color = done
            p.setBrush(color)
            p.drawRect(QtCore.QRectF(x, y, w, h))
        p.end()


class FaceWork(QtWidgets.QWidget):
    """The Work face content surface. The panel delegates its working-state
    signals here (``set_thinking`` / ``set_tool_status`` / ``set_health``)."""

    _MAX_STEPS = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsSection")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._steps = []   # ordered [name, phase] — the live plan-with-progress

        col = QtWidgets.QVBoxLayout(self)
        col.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)
        col.setSpacing(t.SPACE_SM)

        # — activity + current tool status —
        head = QtWidgets.QHBoxLayout()
        head.setSpacing(t.SPACE_SM)
        self._toy = BouncingToy() if BouncingToy is not None else None
        if self._toy is not None:
            head.addWidget(self._toy)
        self._status = c.label("Standing by", role="caption")
        self._status.setStyleSheet("color:%s;" % t.TEXT_SECONDARY)
        head.addWidget(self._status)
        head.addStretch(1)
        col.addLayout(head)

        # — the cook preview (the focus of the glance) —
        self._cook = BucketGrid()
        col.addWidget(self._cook)
        self._cook_lbl = c.label("waiting for work", role="caption")
        self._cook_lbl.setStyleSheet("color:%s;" % t.TEXT_TERTIARY)
        col.addWidget(self._cook_lbl)

        # — plan-with-progress (driven by the live tool stream + routing_log) —
        self._plan_title = c.label("PLAN", role="label")
        self._plan_title.setStyleSheet(
            "color:%s; letter-spacing:1.5px;" % t.TEXT_TERTIARY)
        col.addWidget(self._plan_title)
        self._plan_box = QtWidgets.QVBoxLayout()
        self._plan_box.setSpacing(2)
        col.addLayout(self._plan_box)
        self._render_plan()

        # — observability (the existing infographic, embedded here) —
        if HealthInfographic is not None:
            self._health = HealthInfographic(parent=self)
            col.addWidget(self._health)
        else:
            self._health = None
        col.addStretch(1)

    # -- panel-facing API ------------------------------------------------
    def set_thinking(self, on):
        """Working ↔ at rest. Couples the toy + the cook's indeterminate pulse."""
        if self._toy is not None:
            self._toy.start() if on else self._toy.stop()
        if on:
            self._cook.start_pulse()
        else:
            self._cook.stop_pulse()
            self._status.setText("Standing by")

    def set_tool_status(self, name, phase, detail=None):
        """A live tool event → update the status line + the plan-with-progress."""
        self._status.setText("%s  %s" % (name, phase))
        # update-or-append this tool as a plan step
        for step in self._steps:
            if step[0] == name:
                step[1] = phase
                break
        else:
            self._steps.append([name, phase])
            if len(self._steps) > self._MAX_STEPS:
                self._steps.pop(0)
        self._render_plan()

    def set_cook(self, done, total, live=True, label=None):
        """Wire real cook / render progress onto the bucket grid."""
        self._cook.set_progress(done, total, live=live)
        self._cook_lbl.setText(
            label or ("cooking %d / %d" % (done, total)))

    def set_health(self, data):
        if self._health is not None:
            self._health.set_data(data)

    def reset(self):
        self._steps = []
        self._cook.reset()
        self._cook_lbl.setText("waiting for work")
        self._render_plan()

    # -- plan rendering --------------------------------------------------
    def _routing_summary(self):
        """Best-effort: the last routed agent pair from the MOE routing_log."""
        if get_routing_log is None:
            return ""
        try:
            decisions = get_routing_log().to_dict().get("decisions", [])
        except Exception:
            return ""
        if not decisions:
            return ""
        last = decisions[-1]
        adv = last.get("advisory", "none")
        pair = last.get("primary", "?")
        if adv and adv != "none":
            pair += " + " + adv
        return pair

    def _clear_plan(self):
        while self._plan_box.count():
            item = self._plan_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _render_plan(self):
        self._clear_plan()
        routed = self._routing_summary()
        if routed:
            self._plan_title.setText("PLAN · routed %s" % routed)
        else:
            self._plan_title.setText("PLAN")
        if not self._steps:
            row = c.label("no steps yet", role="caption")
            row.setStyleSheet("color:%s;" % t.TEXT_TERTIARY)
            self._plan_box.addWidget(row)
            return
        for name, phase in self._steps:
            glyph, color = _PHASE.get(phase, ("·", t.TEXT_SECONDARY))
            row = c.label("%s  %s" % (glyph, name), role="caption")
            row.setStyleSheet("color:%s;" % color)
            self._plan_box.addWidget(row)
