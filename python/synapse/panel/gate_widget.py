"""Gate proposals + integrity status widget for the Synapse chat panel.

Displays pending gate proposals as color-coded cards with approve/reject
buttons, and shows a single-row integrity status bar with fidelity indicator.

Thread safety: HumanGate callbacks arrive from the bridge thread. We relay
them to the Qt main thread via a Signal before touching any widgets.
"""

import time
import logging
from functools import partial

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Signal, Slot, QTimer
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import Signal, Slot, QTimer

from synapse.panel.designsystem import tokens as t
from synapse.panel.styles import (
    get_gate_widget_stylesheet,
    get_gate_card_stylesheet,
    get_gate_badge_stylesheet,
    get_gate_approve_btn_stylesheet,
    get_gate_reject_btn_stylesheet,
    get_integrity_bar_stylesheet,
)

logger = logging.getLogger(__name__)

# Gate level -> color mapping
_LEVEL_COLORS = {
    "inform": t.SIGNAL,     # blue accent
    "review": t.WARN,       # amber
    "approve": t.FIRE,      # orange
    "critical": t.ERROR,    # red
}

# Gate level -> timeout seconds
_LEVEL_TIMEOUTS = {
    "inform": 0,
    "review": 0,
    "approve": 120,
    "critical": 300,
}


# ── Fidelity honesty ─────────────────────────────────────────────
# UNMEASURED IS NOT 1.0.
#
# This row was CONSTRUCTED reading "Fidelity 1.0" against a green dot, before
# a single operation had been observed — a fabricated perfect score, the same
# claim-without-observation class as a hardcoded success=True. And the update
# path defaulted the missing key to 1.0 on the way in, so an integrity report
# that carried no fidelity at all still painted a green pass.
#
# The house rule it broke is stated in panel/face_token.py: "Unobtainable
# renders as UNKNOWN, never zero and never an estimate." A zero is a claim —
# and so is a one, in the more dangerous direction, because a fabricated 1.0
# is indistinguishable from a session that genuinely verified clean. CLAUDE.md
# §1.3's guarantee is "fidelity = 1.0 or stop"; a widget that invents the 1.0
# disarms the only instrument that would have said stop.
#
# The verdict lives in these pure helpers rather than inline, for the same
# reason integrity_readout.py factors out `_fidelity_color`: the honesty
# invariant then sits in ONE place a Qt-free source-pin can prove, instead of
# being re-decided at each call site.
FIDELITY_UNKNOWN = "UNKNOWN"


def _observed_fidelity(report):
    """The fidelity this report ACTUALLY carries, or ``None`` for unmeasured.

    No default. ``None`` is returned — never a number — when:

      · the report is not a dict (nothing to read),
      · ``session_fidelity`` is absent (nobody measured it),
      · the value is not a real number (an unusable value is not an
        observation, and formatting it would either crash or invent one),
      · ``operations_total`` is present and zero.

    That last clause is the one that matters most, and it is not this widget
    inventing policy — it is the already-ratified `has_data` doctrine from
    ``session_integrity.summary`` / ``integrity_readout._fidelity_color``
    applied here. ``shared/bridge.py``'s ``session_fidelity`` property returns
    a clean 1.0 when ``operations_total == 0``, so the key is ALWAYS present
    and ALWAYS 1.0 at rest. Removing this widget's ``.get`` default alone would
    therefore have changed nothing on the live WebSocket path: the fabricated
    perfect score would simply have arrived from upstream instead of being
    minted here. A number that is the producer's rest state rather than a
    measurement is exactly what UNKNOWN is for.

    Absent ``operations_total`` is NOT treated as zero — that would be the same
    invention wearing the opposite coat. We suppress only what we can
    positively disqualify.
    """
    if not isinstance(report, dict):
        return None
    if "session_fidelity" not in report:
        return None
    value = report["session_fidelity"]
    # bool is an int subclass; True would otherwise format as "Fidelity 1.0".
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    total = report.get("operations_total")
    if (isinstance(total, (int, float)) and not isinstance(total, bool)
            and total <= 0):
        return None
    return float(value)


def _fidelity_color(fidelity):
    """Verdict → dot color. ``None`` (unmeasured) is SLATE — neutral, never
    the green success token and never the red error one.

    Green is reachable ONLY from an observed value at full fidelity. The
    thresholds below the guard are unchanged from the original row; the guard
    is the whole fix.
    """
    if fidelity is None:
        return t.SLATE
    if fidelity >= 1.0:
        return t.GROW
    if fidelity >= 0.5:
        return t.WARN
    return t.ERROR


def _fidelity_text(fidelity):
    """The row's one label. Unmeasured says so in words rather than borrowing
    a number — a formatted float here is a claim that something was observed.
    """
    if fidelity is None:
        return "Fidelity {u}".format(u=FIDELITY_UNKNOWN)
    return "Fidelity {f:.1f}".format(f=fidelity)


class _ProposalCard(QtWidgets.QWidget):
    """Single gate proposal card with level badge and action buttons.

    Uses QWidget (not QFrame) to avoid Houdini's global QFrame styles
    that can intercept mouse events and block button clicks in PySide6.
    """

    approve_clicked = Signal(str)  # proposal_id
    reject_clicked = Signal(str)   # proposal_id

    def __init__(self, proposal_data, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        self._proposal_id = proposal_data.get("proposal_id", "")
        self._level = proposal_data.get("level", "review")
        self._timeout = _LEVEL_TIMEOUTS.get(self._level, 0)
        self._created_at = proposal_data.get("created_at", "")
        self._operation = proposal_data.get("operation", "unknown")
        self._pulse_on = False
        self._reject_btn = None
        self._approve_btn = None

        level_color = _LEVEL_COLORS.get(self._level, t.SIGNAL)
        # Use object-name-qualified selector to prevent cascade to children
        self.setObjectName("gateCard")
        self._apply_card_style(level_color)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Top row: badge + operation name + agent
        top_row = QtWidgets.QHBoxLayout()
        top_row.setSpacing(8)

        badge = QtWidgets.QLabel(self._level.upper())
        badge.setStyleSheet(get_gate_badge_stylesheet(level_color))
        top_row.addWidget(badge)

        op_label = QtWidgets.QLabel(proposal_data.get("operation", "unknown"))
        op_label.setStyleSheet(
            "color: {fg}; font-family: '{mono}', 'Consolas', monospace; "
            "font-size: {sz}px; font-weight: 700; border: none;".format(
                fg=t.BONE, mono=t.FONT_MONO, sz=t.SIZE_LABEL,
            )
        )
        top_row.addWidget(op_label, stretch=1)

        agent_id = proposal_data.get("agent_id", "")
        if agent_id:
            agent_label = QtWidgets.QLabel(agent_id)
            agent_label.setStyleSheet(
                "color: {fg}; font-size: {sz}px; border: none;".format(
                    fg=t.SLATE, sz=t.SIZE_LABEL,
                )
            )
            top_row.addWidget(agent_label)

        layout.addLayout(top_row)

        # Description
        desc = proposal_data.get("description", "")
        if desc:
            desc_label = QtWidgets.QLabel(desc)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet(
                "color: {fg}; font-size: {sz}px; border: none;".format(
                    fg=t.SILVER, sz=t.SIZE_LABEL,
                )
            )
            layout.addWidget(desc_label)

        # CRITICAL header
        if self._level == "critical":
            crit_label = QtWidgets.QLabel("CRITICAL -- Arbitrary code execution")
            crit_label.setStyleSheet(
                "color: {c}; font-size: {sz}px; font-weight: 700; "
                "border: none;".format(c=t.ERROR, sz=t.SIZE_LABEL)
            )
            layout.addWidget(crit_label)

        # Action buttons for APPROVE / CRITICAL
        if self._level in ("approve", "critical"):
            btn_row = QtWidgets.QHBoxLayout()
            btn_row.setSpacing(8)

            # Countdown label
            self._countdown_label = QtWidgets.QLabel("")
            self._countdown_label.setStyleSheet(
                "color: {fg}; font-size: {sz}px; "
                "font-family: '{mono}', 'Consolas', monospace; "
                "border: none;".format(
                    fg=t.SLATE, sz=t.SIZE_LABEL, mono=t.FONT_MONO,
                )
            )
            btn_row.addWidget(self._countdown_label)

            btn_row.addStretch()

            # Store as instance vars to prevent GC before layout takes ownership
            self._reject_btn = QtWidgets.QPushButton("Reject")
            self._reject_btn.setStyleSheet(get_gate_reject_btn_stylesheet())
            self._reject_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            self._reject_btn.clicked.connect(
                partial(self._emit_reject, self._proposal_id)
            )
            btn_row.addWidget(self._reject_btn)

            self._approve_btn = QtWidgets.QPushButton("Approve")
            self._approve_btn.setStyleSheet(get_gate_approve_btn_stylesheet())
            self._approve_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            self._approve_btn.clicked.connect(self._on_approve_clicked)
            btn_row.addWidget(self._approve_btn)

            layout.addLayout(btn_row)

            # Start countdown timer
            if self._timeout > 0:
                self._remaining = self._timeout
                self._countdown_timer = QTimer(self)
                self._countdown_timer.timeout.connect(self._tick_countdown)
                self._countdown_timer.setInterval(1000)
                self._countdown_timer.start()
                self._update_countdown_text()

        # Pulse timer for CRITICAL cards
        if self._level == "critical":
            self._pulse_timer = QTimer(self)
            self._pulse_timer.timeout.connect(self._toggle_pulse)
            self._pulse_timer.setInterval(800)
            self._pulse_timer.start()

    def _apply_card_style(self, level_color):
        """Apply card stylesheet. Uses property-only (no type selector) to
        avoid cascading to child widgets like QPushButtons."""
        from synapse.panel.designsystem import tokens as t
        self.setStyleSheet(
            "background: {bg}; border: none; border-left: 3px solid {lc}; "
            "border-radius: 4px; margin: 2px 0;".format(
                bg=t.SURFACE, lc=level_color,
            )
        )

    def _emit_reject(self, proposal_id, checked=False):
        """Slot for reject button. Accepts checked arg from clicked(bool)."""
        self.reject_clicked.emit(proposal_id)

    def _on_approve_clicked(self, checked=False):
        """Handle approve click. CRITICAL requires confirmation."""
        if self._level == "critical":
            reply = QtWidgets.QMessageBox.warning(
                self,
                "Confirm CRITICAL Approval",
                "This approves arbitrary code execution.\n\nAre you sure?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
        self.approve_clicked.emit(self._proposal_id)

    def _tick_countdown(self):
        """Decrement countdown each second."""
        self._remaining -= 1
        self._update_countdown_text()
        if self._remaining <= 0:
            self._countdown_timer.stop()
            # Auto-reject on timeout (safe default)
            self.reject_clicked.emit(self._proposal_id)

    def _update_countdown_text(self):
        """Update the countdown display."""
        mins = self._remaining // 60
        secs = self._remaining % 60
        self._countdown_label.setText("{m}:{s:02d}".format(m=mins, s=secs))

    def _toggle_pulse(self):
        """Toggle CRITICAL card border for pulsing effect."""
        self._pulse_on = not self._pulse_on
        color = t.ERROR if self._pulse_on else t.GRAPHITE
        self._apply_card_style(color)

    def mark_gate_unreachable(self):
        """The decision did NOT reach the gate. Say so, and stay undecided.

        RULING 18. The card must not dim, must not read APPROVED or REJECTED, and must not
        look settled — because nothing was settled. The proposal is still live and still
        needs a decision that lands.
        """
        if hasattr(self, "_countdown_timer"):
            self._countdown_timer.stop()
        if hasattr(self, "_pulse_timer"):
            self._pulse_timer.stop()

        self.setStyleSheet(
            "background: {bg}30; border: none; border-left: 4px solid {c}; "
            "border-radius: 4px; margin: 2px 0;".format(bg=t.WARN, c=t.WARN)
        )
        if hasattr(self, "_countdown_label"):
            self._countdown_label.setText("NOT RECORDED - GATE UNREACHABLE")
            self._countdown_label.setStyleSheet(
                "color: {c}; font-weight: bold;".format(c=t.WARN)
            )

    def mark_decided(self, decision):
        """Visually mark the card as decided with triple feedback:
        1. Green/red flash on the card background
        2. Status text replacing countdown
        3. Card dims after flash (chat message handled by GateWidget)
        """
        # Stop timers
        if hasattr(self, "_countdown_timer"):
            self._countdown_timer.stop()
        if hasattr(self, "_pulse_timer"):
            self._pulse_timer.stop()

        is_approved = decision == "approved"
        color = t.GROW if is_approved else t.ERROR
        label = "APPROVED" if is_approved else "REJECTED"

        # 1. Flash: bright background pulse
        flash_bg = "{c}30".format(c=color)
        self.setStyleSheet(
            "background: {fb}; border: none; border-left: 4px solid {c}; "
            "border-radius: 4px; margin: 2px 0;".format(fb=flash_bg, c=color)
        )

        # 2. Status text replacing countdown
        if hasattr(self, "_countdown_label"):
            self._countdown_label.setText(label)
            self._countdown_label.setStyleSheet(
                "color: {c}; font-size: {sz}px; font-weight: 700; "
                "font-family: '{mono}', 'Consolas', monospace; "
                "border: none;".format(
                    c=color, sz=t.SIZE_LABEL, mono=t.FONT_MONO,
                )
            )

        # Hide buttons
        if self._approve_btn:
            self._approve_btn.setVisible(False)
        if self._reject_btn:
            self._reject_btn.setVisible(False)

        # 3. Dim after 600ms flash
        self._decision = decision
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._end_flash)
        self._flash_timer.start(600)

    def _end_flash(self):
        """Dim the card after the flash."""
        color = t.GROW if self._decision == "approved" else t.ERROR
        self._apply_card_style(color)
        self.setEnabled(False)


class GateWidget(QtWidgets.QWidget):
    """Collapsible gate proposals + integrity display widget.

    Inserted between quick actions and input area in the chat panel.
    Receives proposals from HumanGate callbacks (thread-safe via Signal)
    and displays an integrity status bar that polls the bridge.
    """

    # Thread-safe relays: gate callbacks -> Qt main thread
    _proposal_received = Signal(object)
    _decision_made = Signal(str, str)  # proposal_id, decision

    # Public signal for chat panel to show decision messages
    decision_announced = Signal(str, str, str)  # operation, decision, level

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._cards = {}  # proposal_id -> _ProposalCard

        self._build_ui()
        self._register_gate_callbacks()
        self._proposal_received.connect(self._add_proposal_card)
        self._decision_made.connect(self._on_remote_decision)

    def _build_ui(self):
        """Build the collapsible container with proposals list + integrity row."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # -- Chevron toggle header --
        self._header = QtWidgets.QPushButton(self)
        self._header.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self._header.setStyleSheet(
            "QPushButton {{ background: transparent; color: {fg}; "
            "border: none; text-align: left; padding: 4px 8px; "
            "font-family: '{mono}', 'Consolas', monospace; "
            "font-size: {sz}px; }}"
            "QPushButton:hover {{ color: {accent}; }}".format(
                fg=t.SLATE, mono=t.FONT_MONO, sz=t.SIZE_LABEL,
                accent=t.SIGNAL,
            )
        )
        self._update_header_text()
        self._header.clicked.connect(self._toggle)
        layout.addWidget(self._header)

        # -- Collapsible body --
        self._body = QtWidgets.QWidget(self)
        self._body.setVisible(False)
        self._body.setStyleSheet(get_gate_widget_stylesheet())
        body_layout = QtWidgets.QVBoxLayout(self._body)
        body_layout.setContentsMargins(8, 4, 8, 4)
        body_layout.setSpacing(4)

        # Proposals container (direct layout — no QScrollArea, which eats
        # mouse events on Windows 11 / PySide6 and blocks button clicks)
        self._proposals_container = QtWidgets.QWidget(self._body)
        self._proposals_container.setMaximumHeight(200)
        self._proposals_layout = QtWidgets.QVBoxLayout(self._proposals_container)
        self._proposals_layout.setContentsMargins(0, 0, 0, 0)
        self._proposals_layout.setSpacing(4)
        self._proposals_layout.addStretch()

        body_layout.addWidget(self._proposals_container)

        # -- Integrity status row --
        self._integrity_row = QtWidgets.QWidget(self._body)
        self._integrity_row.setStyleSheet(get_integrity_bar_stylesheet())
        integrity_layout = QtWidgets.QHBoxLayout(self._integrity_row)
        integrity_layout.setContentsMargins(8, 4, 8, 4)
        integrity_layout.setSpacing(8)

        # Neither the dot's color nor the label's text is named here. Both come
        # from _render_fidelity below, seeded with None \u2014 so the row is born
        # UNKNOWN and cannot be constructed into a state it never observed.
        self._fidelity_dot = QtWidgets.QLabel("\u25CF")
        integrity_layout.addWidget(self._fidelity_dot)

        self._fidelity_label = QtWidgets.QLabel()
        self._fidelity_label.setStyleSheet(
            "color: {fg}; font-family: '{mono}', 'Consolas', monospace; "
            "font-size: {sz}px; border: none;".format(
                fg=t.SILVER, mono=t.FONT_MONO, sz=t.SIZE_LABEL,
            )
        )
        integrity_layout.addWidget(self._fidelity_label)

        # Honest resting state: unmeasured until an observation arrives.
        self._render_fidelity(None)

        sep1 = QtWidgets.QLabel("|")
        sep1.setStyleSheet(
            "color: {c}; border: none;".format(c=t.GRAPHITE)
        )
        integrity_layout.addWidget(sep1)

        self._ops_label = QtWidgets.QLabel("0 ops")
        self._ops_label.setStyleSheet(
            "color: {fg}; font-family: '{mono}', 'Consolas', monospace; "
            "font-size: {sz}px; border: none;".format(
                fg=t.SLATE, mono=t.FONT_MONO, sz=t.SIZE_LABEL,
            )
        )
        integrity_layout.addWidget(self._ops_label)

        sep2 = QtWidgets.QLabel("|")
        sep2.setStyleSheet(
            "color: {c}; border: none;".format(c=t.GRAPHITE)
        )
        integrity_layout.addWidget(sep2)

        self._violations_label = QtWidgets.QLabel("0 violations")
        self._violations_label.setStyleSheet(
            "color: {fg}; font-family: '{mono}', 'Consolas', monospace; "
            "font-size: {sz}px; border: none;".format(
                fg=t.SLATE, mono=t.FONT_MONO, sz=t.SIZE_LABEL,
            )
        )
        integrity_layout.addWidget(self._violations_label)

        integrity_layout.addStretch()

        body_layout.addWidget(self._integrity_row)

        layout.addWidget(self._body)

    def _update_header_text(self):
        """Update the chevron header with pending count."""
        pending = sum(
            1 for c in self._cards.values() if c.isEnabled()
        )
        chevron = "\u25BC" if self._expanded else "\u25B6"
        if pending > 0:
            self._header.setText(
                "{chev}  Gates ({n} pending)".format(chev=chevron, n=pending)
            )
        else:
            self._header.setText("{chev}  Gates".format(chev=chevron))

    def _toggle(self):
        """Expand or collapse the body."""
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._update_header_text()

    def _register_gate_callbacks(self):
        """Register with HumanGate to receive proposal notifications."""
        try:
            from synapse.core.gates import HumanGate
            gate = HumanGate.get_instance()
            gate.on_proposal(self._on_gate_proposal)
            gate.on_decision(self._on_gate_decision)
        except Exception:
            logger.debug("HumanGate not available -- gate widget passive mode")

    def _on_gate_proposal(self, proposal):
        """Gate callback (may be called from bridge thread). Relay via signal."""
        # Convert to dict for thread-safe signal transport
        data = proposal.to_dict() if hasattr(proposal, "to_dict") else proposal
        self._proposal_received.emit(data)

    def _on_gate_decision(self, proposal, decision):
        """Gate callback for decisions. Relay via signal."""
        pid = proposal.proposal_id if hasattr(proposal, "proposal_id") else str(proposal)
        dec = decision.value if hasattr(decision, "value") else str(decision)
        self._decision_made.emit(pid, dec)

    @Slot(object)
    def _add_proposal_card(self, proposal_data):
        """Add a proposal card to the widget (Qt main thread)."""
        if isinstance(proposal_data, dict):
            data = proposal_data
        else:
            data = proposal_data.to_dict() if hasattr(proposal_data, "to_dict") else {}

        proposal_id = data.get("proposal_id", "")
        level = data.get("level", "inform")

        # Skip INFORM by default (too noisy)
        if level == "inform":
            return

        # Don't duplicate
        if proposal_id in self._cards:
            return

        card = _ProposalCard(data, parent=self._proposals_container)
        card.approve_clicked.connect(self._on_approve)
        card.reject_clicked.connect(self._on_reject)

        # Insert before the stretch
        count = self._proposals_layout.count()
        self._proposals_layout.insertWidget(max(0, count - 1), card)
        self._cards[proposal_id] = card

        # Auto-expand when a proposal arrives
        if not self._expanded:
            self._toggle()

        self._update_header_text()

    def _on_approve(self, proposal_id):
        """Handle approve button click.

        RULING 18 / Constitution Law 3: the UI announces what HAPPENED, never what was
        attempted. If ``gate.decide`` raises, the decision did not land — the card is NOT
        marked decided and ``decision_announced`` is NOT emitted. A consent gate that
        reports success on a swallowed exception is worse than no gate, because the artist
        stops watching.
        """
        try:
            from synapse.core.gates import HumanGate, GateDecision
            gate = HumanGate.get_instance()
            gate.decide(proposal_id, GateDecision.APPROVED, "panel_artist")
        except Exception as exc:
            logger.error("Failed to approve proposal %s: %s", proposal_id, exc)
            card = self._cards.get(proposal_id)
            if card:
                card.mark_gate_unreachable()
            self._update_header_text()
            return

        card = self._cards.get(proposal_id)
        if card:
            card.mark_decided("approved")
            op = card._proposal_id
            # Emit for chat panel to post a visible message
            self.decision_announced.emit(
                getattr(card, '_operation', op), "approved", card._level
            )
        self._update_header_text()

    def _on_reject(self, proposal_id):
        """Handle reject button click (or timeout auto-reject).

        RULING 18: same contract as ``_on_approve``, and the stakes are higher — a reject
        that never reached the gate has NOT blocked anything. Do not report it as though
        it had.
        """
        try:
            from synapse.core.gates import HumanGate, GateDecision
            gate = HumanGate.get_instance()
            gate.decide(proposal_id, GateDecision.REJECTED, "panel_artist")
        except Exception as exc:
            logger.error("Failed to reject proposal %s: %s", proposal_id, exc)
            card = self._cards.get(proposal_id)
            if card:
                card.mark_gate_unreachable()
            self._update_header_text()
            return

        card = self._cards.get(proposal_id)
        if card:
            card.mark_decided("rejected")
            op = card._proposal_id
            self.decision_announced.emit(
                getattr(card, '_operation', op), "rejected", card._level
            )
        self._update_header_text()

    @Slot(str, str)
    def _on_remote_decision(self, proposal_id, decision):
        """Handle decision made elsewhere (e.g. another UI or auto-system)."""
        card = self._cards.get(proposal_id)
        if card:
            card.mark_decided(decision)
        self._update_header_text()

    def _render_fidelity(self, fidelity):
        """Paint the dot + label from an observed fidelity, or ``None``.

        The single write point for this row. It names no color token itself —
        the verdict is delegated to ``_fidelity_color`` so green cannot be
        reached without passing that guard, the same containment
        ``IntegrityReadout.set_integrity`` uses.
        """
        self._fidelity_dot.setStyleSheet(
            "color: {c}; font-size: 14px; border: none;".format(
                c=_fidelity_color(fidelity)
            )
        )
        self._fidelity_label.setText(_fidelity_text(fidelity))

    def update_integrity(self, report):
        """Update the integrity status row from a session report dict.

        Expected keys: session_fidelity, operations_total, anchor_violations

        Fidelity is read through ``_observed_fidelity``, which has NO default:
        a report that does not carry a usable measurement leaves the row
        reading UNKNOWN rather than borrowing a number. A falsy report is not
        an observation either, so it is ignored outright — the row keeps the
        last state it can actually account for, which at rest is UNKNOWN.
        """
        if not report:
            return

        fidelity = _observed_fidelity(report)
        ops = report.get("operations_total", 0)
        violations = report.get("anchor_violations", 0)

        self._render_fidelity(fidelity)
        self._ops_label.setText("{n} ops".format(n=ops))

        v_color = t.ERROR if violations > 0 else t.SLATE
        self._violations_label.setStyleSheet(
            "color: {fg}; font-family: '{mono}', 'Consolas', monospace; "
            "font-size: {sz}px; border: none;".format(
                fg=v_color, mono=t.FONT_MONO, sz=t.SIZE_LABEL,
            )
        )
        self._violations_label.setText("{n} violations".format(n=violations))

    def handle_ws_proposal(self, data):
        """Handle a gate_proposal message from the WebSocket bridge."""
        self._add_proposal_card(data)

    def handle_ws_report(self, data):
        """Handle a session_report message from the WebSocket bridge."""
        self.update_integrity(data)
