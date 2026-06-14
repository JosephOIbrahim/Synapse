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
from synapse.panel.designsystem import fontload

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


def _verb(text, on_click, tone=None):
    """Type-set action — mono, no pill chrome (matches Direct's act bar). Styled
    by the canonical QPushButton#DsVerb QSS rule; ``tone`` selects the color."""
    btn = QtWidgets.QPushButton(text)
    btn.setObjectName("DsVerb")
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFlat(True)
    if tone:
        btn.setProperty("tone", tone)
    btn.clicked.connect(on_click)
    return btn


class RenderHero(QtWidgets.QWidget):
    """The render, made the hero — the one chromatic event on the surface.

    Shows the actual frame (a QPixmap) when a real on-disk frame is in hand; with
    no frame it paints nothing and the parent hides it in favour of the compact
    render-view locator (the render is Houdini's job)."""

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
        return pix is not None

    def set_meta(self, text):
        self._meta = text or ""
        self.update()

    def paintEvent(self, _event):
        # Real-frame-only: with no on-disk frame, paint nothing (the parent hides
        # this widget and shows the locator). No decorative placeholder.
        if self._pix is None:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = QtCore.QRectF(self.rect())
        scaled = self._pix.scaled(
            self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = (scaled.width() - self.width()) / 2.0
        y = (scaled.height() - self.height()) / 2.0
        p.drawPixmap(QtCore.QPointF(-x, -y), scaled)
        self._paint_vignette(p, r)
        if self._meta:
            self._paint_meta(p, r)
        p.end()

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
    open_render_requested = Signal()

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
        self._verdict.setStyleSheet("color:%s;" % t.TEXT_BRIGHT)
        self._verdict.setFont(fontload.tracked_font("DISPLAY", 15))  # tight display
        col.addWidget(self._verdict)

        # — no-frame locator — when no real frame is on disk, the render stays
        # Houdini's job: show the frame/AOV/path meta + a verb that surfaces the
        # existing render view (display-only, never spawns a pane). Hidden when a
        # real thumbnail is in hand (set_render drives the swap). —
        self._locator = QtWidgets.QWidget()
        self._locator.setObjectName("DsSection")
        self._locator.setAttribute(Qt.WA_StyledBackground, True)
        loc = QtWidgets.QHBoxLayout(self._locator)
        loc.setContentsMargins(0, 0, 0, 0)
        loc.setSpacing(t.SPACE_SM)
        self._locator_meta = c.label("", role="code")
        self._locator_meta.setWordWrap(True)
        self._locator_meta.setStyleSheet("color:%s; font-size:10px;" % t.TEXT_TERTIARY)
        loc.addWidget(self._locator_meta, 1)
        loc.addWidget(_verb("⤢ open in render view",
                            lambda _=False: self.open_render_requested.emit()))
        self._locator.setVisible(False)
        col.addWidget(self._locator)

        # — SIGNED authorship line — DISPLAY ONLY. It reports who produced the
        # result (the panel's model); it NEVER authors USD / customData. —
        self._signed = c.label("", role="code")
        self._signed.setStyleSheet(
            "color:%s; font-size:10px; letter-spacing:1px;" % t.TEXT_TERTIARY)
        self._signed.setVisible(False)
        col.addWidget(self._signed)

        # — credit headline (the DECISION leads; provenance folds into detail) —
        self._credit_box = QtWidgets.QVBoxLayout()
        self._credit_box.setSpacing(1)
        col.addLayout(self._credit_box)

        # — quality flags / status dots (preflight + BL-007 / BL-008) —
        self._flags_box = QtWidgets.QVBoxLayout()
        self._flags_box.setSpacing(1)
        col.addLayout(self._flags_box)

        # — expandable detail: VIA provenance + touched paths, collapsed by
        # default (simplified synthesis keeps the headline taut) —
        self._detail_btn = _verb("▸ detail", lambda _=False: self._toggle_detail())
        col.addWidget(self._detail_btn, 0, Qt.AlignLeft)
        self._detail = QtWidgets.QWidget()
        self._detail.setObjectName("DsSection")
        self._detail.setAttribute(Qt.WA_StyledBackground, True)
        dcol = QtWidgets.QVBoxLayout(self._detail)
        dcol.setContentsMargins(0, 0, 0, 0)
        dcol.setSpacing(1)
        self._via_box = QtWidgets.QVBoxLayout()
        self._via_box.setSpacing(1)
        dcol.addLayout(self._via_box)
        self._paths = c.label("", role="code")
        self._paths.setWordWrap(True)
        self._paths.setStyleSheet("color:%s; font-size:10px;" % t.TEXT_TERTIARY)
        dcol.addWidget(self._paths)
        self._detail.setVisible(False)
        self._detail_expanded = False
        col.addWidget(self._detail)

        # — consent gate (graduated GATE_LEVELS, embedded here) —
        if GateWidget is not None:
            self.gate = GateWidget(parent=self)
            col.addWidget(self.gate)
        else:
            self.gate = None

        # — the close: accept / revert / commit —
        acts = QtWidgets.QHBoxLayout()
        acts.setSpacing(t.SPACE_MD)
        acts.addWidget(_verb("ACCEPT", lambda _=False: self.accepted.emit(), tone="ok"))
        acts.addWidget(_verb("↶ REVERT", lambda _=False: self.reverted.emit()))
        acts.addStretch(1)
        acts.addWidget(_verb("COMMIT TO /STAGE", lambda _=False: self.committed.emit(),
                             tone="hot"))
        col.addLayout(acts)
        col.addStretch(1)

        self._verdict.setText("Standing by for the next result.")
        # rest state has no real frame → hide the hero, show the compact locator
        self._hero.setVisible(False)
        self._locator.setVisible(True)

    # -- setters ---------------------------------------------------------
    def set_render(self, path=None, meta=None):
        has_frame = self._hero.set_image(path)
        if meta is not None:
            self._hero.set_meta(meta)
            self._locator_meta.setText(meta)
        # real frame → thumbnail visible, locator hidden; no frame → hero hidden,
        # the locator surfaces the render-view verb + meta (no 168px of décor).
        self._hero.setVisible(has_frame)
        self._locator.setVisible(not has_frame)

    def set_verdict(self, text):
        self._verdict.setText(text or "")

    def set_signed(self, author):
        """The SIGNED authorship line — DISPLAY ONLY. Reports who produced the
        result (the panel's model). It NEVER authors USD / customData."""
        if author:
            self._signed.setText("SIGNED  %s" % author)
            self._signed.setVisible(True)
        else:
            self._signed.setText("")
            self._signed.setVisible(False)

    def _credit_row(self, label, value, note):
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
        return row

    def set_credit(self, items):
        """items: list of (label, value, note). DECISION leads the headline;
        VIA / ROUTED / other provenance fold into the expandable detail
        (the simplified synthesis keeps the headline taut)."""
        self._clear(self._credit_box)
        self._clear(self._via_box)
        for label, value, note in items or []:
            box = self._credit_box if str(label).upper() == "DECISION" else self._via_box
            box.addWidget(self._credit_row(label, value, note))

    def _toggle_detail(self):
        self._detail_expanded = not self._detail_expanded
        self._detail.setVisible(self._detail_expanded)
        self._detail_btn.setText("▾ detail" if self._detail_expanded else "▸ detail")

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
                    render=None, meta=None, signed=None):
        """Populate the whole surface for a landed result (one call)."""
        if render is not None or meta is not None:
            self.set_render(render, meta)
        if verdict is not None:
            self.set_verdict(verdict)
        if signed is not None:
            self.set_signed(signed)
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
