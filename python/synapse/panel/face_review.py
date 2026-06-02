"""FaceReview — the Review face: *the payoff* (Pentagram pass, Mile 5).

When the work lands, this is the surface that has to be trustworthy enough to
walk away from. It makes the **render the hero** (the only chromatic event),
states a taut benefit **verdict**, credits the **authorship/provenance** like a
named partner (apex_trace / routing_log), surfaces **quality flags** — including
the BL-007 (silent no-output) and BL-008 (silent material-binding loss)
detections — embeds the graduated **GateWidget** for consent, and offers
**accept / revert / commit** as the close.

Panel-layer only: ``Commit to /stage`` *raises a gate*, it never writes the USD
substrate itself. Every dependency is optional so the face always instantiates.
"""

import os

try:
    from PySide6 import QtWidgets, QtGui, QtCore
    from PySide6.QtCore import Qt, Signal
except ImportError:  # pragma: no cover - Houdini ships PySide6
    from PySide2 import QtWidgets, QtGui, QtCore
    from PySide2.QtCore import Qt, Signal

from synapse.panel.designsystem import tokens as t
from synapse.panel.designsystem import components as c

try:
    from synapse.panel.gate_widget import GateWidget
except Exception:  # pragma: no cover
    GateWidget = None
try:
    from synapse.panel.routing_log import get_routing_log
except Exception:  # pragma: no cover
    get_routing_log = None
try:
    from synapse.panel.render_preflight import run_preflight
except Exception:  # pragma: no cover
    run_preflight = None

# render-hero placeholder palette — the abstract "work" when no real frame is
# in hand yet. Cool dark ground + the brand's two accents. Mile-7-tunable.
_HERO_BG0, _HERO_BG1, _HERO_BG2 = "#2D3742", "#1A1F26", "#101317"

# quality-flag status → dot color
_FLAG_COLOR = {
    "ok": t.GROW, "pass": t.GROW,
    "warn": t.WARN,
    "fail": t.ERROR, "no": t.ERROR,
}


def bl007_flag(output_path):
    """BL-007 (silent no-output): a render is only real if a file landed at the
    configured path with size > 0. Pure os check — no hou, so it is testable
    standalone and honest about the husk-no-op-on-Indie failure mode."""
    try:
        if output_path and os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
            return ("ok", "output written")
    except Exception:
        pass
    return ("fail", "EXR not written — BL-007")


def detect_render_flags(render_node="", output_path=""):
    """Best-effort live quality flags for the Review face. Combines the render
    preflight report with the BL-007 output-on-disk check. Returns a list of
    (status, text). Degrades to a single BL-007 row outside Houdini."""
    flags = []
    if run_preflight is not None:
        try:
            report = run_preflight(render_node)
            flags.append(("ok" if report.ready else "fail",
                          "render ready" if report.ready else "render not ready"))
            for chk in report.checks:
                if chk.status in ("fail", "warn"):
                    text = chk.message
                    # surface BL-008 framing on the material-binding check
                    if chk.name == "materials":
                        text += " — BL-008"
                    flags.append((chk.status, text))
        except Exception:
            pass
    flags.append(bl007_flag(output_path))
    return flags


def _verb(text, on_click, color=None):
    """Type-set action — mono, letter-spaced, no pill chrome (matches Direct's
    act bar). Inline-styled so it doesn't depend on the Mile-7 QSS pass."""
    btn = QtWidgets.QPushButton(text)
    btn.setObjectName("DsVerb")
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFlat(True)
    rest = color or t.TEXT_SECONDARY
    btn.setStyleSheet(
        "QPushButton#DsVerb{background:transparent; border:none; padding:2px 0;"
        " color:%s; font-family:%s; font-size:11px; letter-spacing:1.4px;}"
        "QPushButton#DsVerb:hover{color:%s;}"
        % (rest, t.FONT_MONO, t.TEXT_ACCENT)
    )
    btn.clicked.connect(on_click)
    return btn


class RenderHero(QtWidgets.QWidget):
    """The render, made the hero — the one chromatic event on the surface.

    Shows the actual frame (a QPixmap) if a path is given; otherwise paints the
    abstract gradient + shards placeholder from the v3 comp so the surface still
    reads 'a result landed here'."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsSection")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._pix = None
        self._meta = ""
        self.setMinimumHeight(168)

    def sizeHint(self):
        return QtCore.QSize(340, 191)   # 16:9

    def heightForWidth(self, w):
        return int(w * 9 / 16)

    def set_image(self, path):
        pix = None
        try:
            if path and os.path.isfile(path):
                pix = QtGui.QPixmap(path)
                if pix.isNull():
                    pix = None
        except Exception:
            pix = None
        self._pix = pix
        self.update()

    def set_meta(self, text):
        self._meta = text or ""
        self.update()

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = QtCore.QRectF(self.rect())
        if self._pix is not None:
            scaled = self._pix.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (scaled.width() - self.width()) / 2.0
            y = (scaled.height() - self.height()) / 2.0
            p.drawPixmap(QtCore.QPointF(-x, -y), scaled)
        else:
            self._paint_placeholder(p, r)
        self._paint_vignette(p, r)
        if self._meta:
            self._paint_meta(p, r)
        p.end()

    def _paint_placeholder(self, p, r):
        bg = QtGui.QRadialGradient(r.width() * 0.32, r.height() * 0.22,
                                   max(r.width(), r.height()) * 1.1)
        bg.setColorAt(0.0, QtGui.QColor(_HERO_BG0))
        bg.setColorAt(0.55, QtGui.QColor(_HERO_BG1))
        bg.setColorAt(1.0, QtGui.QColor(_HERO_BG2))
        p.fillRect(r, QtGui.QBrush(bg))
        # three angled shards, lit by the brand's two accents
        self._shard(p, r, 0.24, 0.14, 0.34, 0.74, t.SIGNAL, t.WARM, 0.42)
        self._shard(p, r, 0.48, 0.30, 0.30, 0.60, t.WARM, t.SIGNAL, 0.30)
        self._shard(p, r, 0.14, 0.42, 0.22, 0.46, t.SIGNAL, t.SIGNAL, 0.24)

    def _shard(self, p, r, fx, fy, fw, fh, c0, c1, a):
        x, y = r.width() * fx, r.height() * fy
        w, h = r.width() * fw, r.height() * fh
        path = QtGui.QPainterPath()
        path.moveTo(x + w * 0.38, y)
        path.lineTo(x + w, y + h * 0.24)
        path.lineTo(x + w * 0.72, y + h)
        path.lineTo(x, y + h * 0.70)
        path.closeSubpath()
        grad = QtGui.QLinearGradient(x, y, x + w, y + h)
        col0 = QtGui.QColor(c0); col0.setAlphaF(a)
        col1 = QtGui.QColor(c1); col1.setAlphaF(a * 0.35)
        grad.setColorAt(0.0, col0)
        grad.setColorAt(1.0, col1)
        p.setPen(Qt.NoPen)
        p.setBrush(QtGui.QBrush(grad))
        p.drawPath(path)

    def _paint_vignette(self, p, r):
        vig = QtGui.QRadialGradient(r.center(), max(r.width(), r.height()) * 0.62)
        vig.setColorAt(0.55, QtGui.QColor(0, 0, 0, 0))
        vig.setColorAt(1.0, QtGui.QColor(0, 0, 0, 115))
        p.fillRect(r, QtGui.QBrush(vig))

    def _paint_meta(self, p, r):
        f = QtGui.QFont()
        f.setPixelSize(10)
        f.setFamily("monospace")
        p.setFont(f)
        p.setPen(QtGui.QColor("#97A3AD"))
        p.drawText(QtCore.QRectF(r.left() + 10, r.bottom() - 20, r.width() - 20, 16),
                   int(Qt.AlignLeft | Qt.AlignVCenter), self._meta)


class FaceReview(QtWidgets.QWidget):
    """The Review face content surface. The panel switches here on 'done' and
    feeds it via ``show_result`` / the individual setters."""

    accepted = Signal()
    reverted = Signal()
    committed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsSection")
        self.setAttribute(Qt.WA_StyledBackground, True)

        col = QtWidgets.QVBoxLayout(self)
        col.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_MD)
        col.setSpacing(t.SPACE_SM)

        # — the render, the hero —
        self._hero = RenderHero()
        col.addWidget(self._hero)

        # — taut benefit verdict —
        self._verdict = c.label("", role="title")
        self._verdict.setWordWrap(True)
        self._verdict.setStyleSheet("color:%s; font-size:15px;" % t.TEXT_BRIGHT)
        col.addWidget(self._verdict)

        # — credit / provenance (named authorship) —
        self._credit_box = QtWidgets.QVBoxLayout()
        self._credit_box.setSpacing(1)
        col.addLayout(self._credit_box)

        # — quality flags (preflight + BL-007 / BL-008) —
        self._flags_box = QtWidgets.QVBoxLayout()
        self._flags_box.setSpacing(1)
        col.addLayout(self._flags_box)

        # — touched paths —
        self._paths = c.label("", role="code")
        self._paths.setWordWrap(True)
        self._paths.setStyleSheet("color:%s; font-size:10px;" % t.TEXT_TERTIARY)
        self._paths.setVisible(False)
        col.addWidget(self._paths)

        # — consent gate (graduated GATE_LEVELS, embedded here) —
        if GateWidget is not None:
            self.gate = GateWidget(parent=self)
            col.addWidget(self.gate)
        else:
            self.gate = None

        # — the close: accept / revert / commit —
        acts = QtWidgets.QHBoxLayout()
        acts.setSpacing(t.SPACE_MD)
        acts.addWidget(_verb("ACCEPT", lambda _=False: self.accepted.emit(), color=t.GROW))
        acts.addWidget(_verb("↶ REVERT", lambda _=False: self.reverted.emit()))
        acts.addStretch(1)
        acts.addWidget(_verb("COMMIT TO /STAGE", lambda _=False: self.committed.emit(),
                             color=t.WARM))
        col.addLayout(acts)
        col.addStretch(1)

        self._verdict.setText("Standing by for the next result.")

    # -- setters ---------------------------------------------------------
    def set_render(self, path=None, meta=None):
        self._hero.set_image(path)
        if meta is not None:
            self._hero.set_meta(meta)

    def set_verdict(self, text):
        self._verdict.setText(text or "")

    def set_credit(self, items):
        """items: list of (label, value, note)."""
        self._clear(self._credit_box)
        for label, value, note in items or []:
            row = QtWidgets.QLabel()
            row.setTextFormat(Qt.RichText)
            row.setWordWrap(True)
            row.setText(
                '<span style="color:%s; font-family:%s; letter-spacing:1px;">%s </span>'
                '<span style="color:%s;">%s</span>'
                '<span style="color:%s;">%s</span>' % (
                    t.TEXT_TERTIARY, t.FONT_MONO, label,
                    t.SIGNAL, value,
                    t.TEXT_SECONDARY, ("  — " + note) if note else "",
                )
            )
            self._credit_box.addWidget(row)

    def set_flags(self, flags):
        """flags: list of (status, text). status in ok/pass/warn/fail/no."""
        self._clear(self._flags_box)
        for status, text in flags or []:
            color = _FLAG_COLOR.get(status, t.TEXT_SECONDARY)
            row = QtWidgets.QLabel()
            row.setTextFormat(Qt.RichText)
            row.setWordWrap(True)
            row.setText(
                '<span style="color:%s;">&#9679;</span> '
                '<span style="color:%s;">%s</span>' % (color, t.TEXT_PRIMARY, text)
            )
            self._flags_box.addWidget(row)

    def set_paths(self, paths):
        if paths:
            self._paths.setText("\n".join("~ %s" % p for p in paths))
            self._paths.setVisible(True)
        else:
            self._paths.setVisible(False)

    def show_result(self, verdict=None, credit=None, flags=None, paths=None,
                    render=None, meta=None):
        """Populate the whole surface for a landed result (one call)."""
        if render is not None or meta is not None:
            self.set_render(render, meta)
        if verdict is not None:
            self.set_verdict(verdict)
        if credit is not None:
            self.set_credit(credit)
        if flags is not None:
            self.set_flags(flags)
        if paths is not None:
            self.set_paths(paths)

    def refresh_provenance(self):
        """Best-effort credit row from the MOE routing_log (named authorship)."""
        if get_routing_log is None:
            return
        try:
            decisions = get_routing_log().to_dict().get("decisions", [])
        except Exception:
            return
        if not decisions:
            return
        last = decisions[-1]
        pair = last.get("primary", "?")
        adv = last.get("advisory", "none")
        if adv and adv != "none":
            pair += " + " + adv
        self.set_credit([("ROUTED", pair, last.get("method", ""))])

    # -- helpers ---------------------------------------------------------
    def _clear(self, box):
        while box.count():
            item = box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
