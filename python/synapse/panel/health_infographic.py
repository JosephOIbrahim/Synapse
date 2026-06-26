"""HealthInfographic — the observability surface, drawn as infographics.

Area 4 / RSI Line O. Renders the recursive-observability telemetry
(CLAUDE.md §16) as painted charts rather than text — a bridge success gauge,
a per-agent bar chart, and a recommendation-activity sparkline, plus a chronic
/ anchor-violation banner. Reads the dict from
``agent_health.poll_agent_health()``; touches no ``hou`` API and degrades to a
single "awaiting telemetry" line when no bridge is running.

This is the GRAPHICAL surface that sits alongside the existing text/gate
representation — bars and gauges, information represented graphically.
"""

try:
    from PySide6 import QtWidgets, QtGui, QtCore
    from PySide6.QtCore import Qt
except ImportError:  # pragma: no cover - Houdini ships PySide6
    from PySide2 import QtWidgets, QtGui, QtCore
    from PySide2.QtCore import Qt

from synapse.panel.designsystem import tokens as t

_ROSTER = ["SUBSTRATE", "BRAINSTEM", "OBSERVER", "HANDS", "CONDUCTOR", "INTEGRATOR"]
_SHORT = {"SUBSTRATE": "SUB", "BRAINSTEM": "BRN", "OBSERVER": "OBS",
          "HANDS": "HND", "CONDUCTOR": "CND", "INTEGRATOR": "INT"}


def _short(key) -> str:
    k = str(key).upper()
    for name in _ROSTER:
        if name in k:
            return _SHORT[name]
    return (k.split(".")[-1][:3] or "?")


def _roster_rank(key) -> int:
    k = str(key).upper()
    for i, name in enumerate(_ROSTER):
        if name in k:
            return i
    return len(_ROSTER)


def _rate_color(r: float) -> str:
    if r >= 0.95:
        return t.GROW
    if r >= 0.85:
        return t.WARN
    return t.ERROR


class HealthInfographic(QtWidgets.QWidget):
    """Compact painted observability chart. Feed it with set_data(health)."""

    # geometry (px)
    _PAD = t.SPACE_MD
    _ROW_H = 16
    _GAUGE_H = 18
    _HEAD_H = 16
    _SPARK_H = 24
    _BANNER_H = 18
    _GAP = t.SPACE_SM

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsSection")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._data = None
        self.setMinimumHeight(28)
        self._recompute_height()

    # ---------------------------------------------------------------- data
    def set_data(self, health):
        self._data = health if (health and health.get("available")) else None
        self._recompute_height()
        self.update()

    def _agents_sorted(self):
        per = (self._data or {}).get("per_agent", {})
        return sorted(per.items(), key=lambda kv: (_roster_rank(kv[0]), str(kv[0])))

    def _recompute_height(self):
        if not self._data:
            self.setFixedHeight(28)
            return
        h = self._PAD + self._HEAD_H + self._GAP + self._GAUGE_H + self._GAP
        h += max(1, len(self._agents_sorted())) * self._ROW_H
        recent = (self._data.get("history") or {}).get("recent_counts") or []
        if recent:
            h += self._GAP + self._SPARK_H
        if self._has_banner():
            h += self._GAP + self._BANNER_H
        h += self._PAD
        self.setFixedHeight(int(h))

    def _has_banner(self) -> bool:
        if not self._data:
            return False
        viol = self._data.get("bridge_stats", {}).get("anchor_violations", 0)
        meta = self._data.get("meta_recommendations") or []
        return bool(viol) or bool(meta)

    # ---------------------------------------------------------------- paint
    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.fillRect(self.rect(), QtGui.QColor(t.PANEL))   # opaque — no ghosting

        x0 = self._PAD
        x1 = self.width() - self._PAD
        if not self._data:
            self._text(p, x0, 0, self.width() - 2 * self._PAD, self.height(),
                       "Awaiting telemetry…", t.TEXT_TERTIARY, 11,
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            p.end()
            return

        stats = self._data.get("bridge_stats", {})
        total = stats.get("operations_total", 0)
        rate = stats.get("success_rate", 0.0)
        y = self._PAD

        # ── header: label + ops/rate summary ──────────────────────
        self._text(p, x0, y, x1 - x0, self._HEAD_H, "OBSERVABILITY",
                   t.TEXT_TERTIARY, 11, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, spacing=1.5)
        self._text(p, x0, y, x1 - x0, self._HEAD_H,
                   "%d ops · %.0f%%" % (total, rate * 100),
                   t.TEXT_SECONDARY, 11, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        y += self._HEAD_H + self._GAP

        # ── bridge success gauge (the hero metric) ────────────────
        self._gauge(p, x0, y, x1 - x0, rate)
        y += self._GAUGE_H + self._GAP

        # ── per-agent bar chart ───────────────────────────────────
        agents = self._agents_sorted()
        if not agents:
            self._text(p, x0, y, x1 - x0, self._ROW_H, "no agent activity yet",
                       t.TEXT_TERTIARY, 10, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            y += self._ROW_H
        else:
            for key, d in agents:
                self._agent_bar(p, x0, y, x1 - x0, _short(key),
                                d.get("rate", 0.0), d.get("total", 0))
                y += self._ROW_H

        # ── recommendation-activity sparkline ─────────────────────
        recent = (self._data.get("history") or {}).get("recent_counts") or []
        if recent:
            y += self._GAP
            self._sparkline(p, x0, y, x1 - x0, recent)
            y += self._SPARK_H

        # ── banner: anchor violations (red) or chronic (amber) ────
        if self._has_banner():
            y += self._GAP
            self._banner(p, x0, y, x1 - x0)
        p.end()

    # ---------------------------------------------------------------- pieces
    def _gauge(self, p, x, y, w, rate):
        track_h = 8
        ty = y + (self._GAUGE_H - track_h) / 2.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(t.SURFACE))
        p.drawRoundedRect(QtCore.QRectF(x, ty, w, track_h), 4, 4)
        fill_w = max(2.0, w * max(0.0, min(1.0, rate)))
        p.setBrush(QtGui.QColor(_rate_color(rate)))
        p.drawRoundedRect(QtCore.QRectF(x, ty, fill_w, track_h), 4, 4)
        # threshold ticks at 85% / 95% — the health boundaries the advisor uses
        p.setPen(QtGui.QPen(QtGui.QColor(t.BORDER_STRONG), 1))
        for thr in (0.85, 0.95):
            tx = x + w * thr
            p.drawLine(QtCore.QPointF(tx, ty - 1), QtCore.QPointF(tx, ty + track_h + 1))

    def _agent_bar(self, p, x, y, w, label, rate, count):
        lab_w, val_w = 34, 42
        bar_x = x + lab_w
        bar_w = w - lab_w - val_w
        track_h = 7
        by = y + (self._ROW_H - track_h) / 2.0
        self._text(p, x, y, lab_w, self._ROW_H, label, t.TEXT_SECONDARY, 10,
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, mono=True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(t.SURFACE))
        p.drawRoundedRect(QtCore.QRectF(bar_x, by, bar_w, track_h), 3, 3)
        fill_w = max(2.0, bar_w * max(0.0, min(1.0, rate)))
        p.setBrush(QtGui.QColor(_rate_color(rate)))
        p.drawRoundedRect(QtCore.QRectF(bar_x, by, fill_w, track_h), 3, 3)
        self._text(p, x + w - val_w, y, val_w, self._ROW_H,
                   "%.0f%% (%d)" % (rate * 100, count), t.TEXT_TERTIARY, 10,
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, mono=True)

    def _sparkline(self, p, x, y, w, values):
        self._text(p, x, y, w, 10, "RECOMMENDATION ACTIVITY", t.TEXT_TERTIARY, 9,
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, spacing=1.2)
        gy = y + 11
        gh = self._SPARK_H - 11
        n = len(values)
        if n == 0:
            return
        peak = max(values) or 1
        slot = w / float(n)
        bw = max(2.0, slot * 0.6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(t.SIGNAL))
        for i, v in enumerate(values):
            bh = max(2.0, gh * (v / float(peak)))
            bx = x + i * slot + (slot - bw) / 2.0
            p.drawRoundedRect(QtCore.QRectF(bx, gy + gh - bh, bw, bh), 1.5, 1.5)

    def _banner(self, p, x, y, w):
        viol = self._data.get("bridge_stats", {}).get("anchor_violations", 0)
        meta = self._data.get("meta_recommendations") or []
        if viol:
            col, msg = t.ERROR, "⚠  %d anchor violation%s — pipeline integrity" % (
                viol, "" if viol == 1 else "s")
        else:
            tgt = getattr(meta[0], "target", "")
            col, msg = t.WARN, "⟳  %d chronic: %s" % (len(meta), tgt)
        rgb = t._hex_to_rgb_int(col)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(rgb[0], rgb[1], rgb[2], 36))
        p.drawRoundedRect(QtCore.QRectF(x, y, w, self._BANNER_H), 4, 4)
        self._text(p, x + t.SPACE_SM, y, w - 2 * t.SPACE_SM, self._BANNER_H,
                   msg, col, 10, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    # ---------------------------------------------------------------- text
    def _text(self, p, x, y, w, h, s, color, px, align, mono=False, spacing=0.0):
        f = QtGui.QFont()
        f.setPixelSize(px)
        if mono:
            f.setStyleHint(QtGui.QFont.Monospace)
            f.setFamily("monospace")
        if spacing:
            f.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, spacing)
        p.setFont(f)
        p.setPen(QtGui.QColor(color))
        p.drawText(QtCore.QRectF(x, y, w, h), int(align), s)
