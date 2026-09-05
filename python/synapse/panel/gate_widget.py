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
from synapse.panel.designsystem import components as c
from synapse.panel.designsystem import fontload, qss

logger = logging.getLogger(__name__)

# bc-wave BC-6a (REVIEW.md F4): the level is never a hue. A consent card is a
# DsCard in the panel's own vocabulary - the level is a `tag`, the decision is
# a `tag`, the verbs are DsVerb type; the only warm note is HOT_SOFT through
# status=BLOCKED (CRITICAL's tag, REJECT, a rejected / unrecorded decision)
# and the only accent is APPROVE - the artist's next action.

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


def _verb(text, on_click, tone=None, scale=t.FONT_SCALE_DEFAULT):
    """The panel's type-set verb idiom (synapse_panel._verb) for the card:
    QPushButton#DsVerb, LABEL tracked mono, flat; ``tone`` in {None, 'hot',
    'accent'} selects the semantic colour via the canonical DsVerb rule."""
    btn = QtWidgets.QPushButton(text)
    btn.setObjectName("DsVerb")
    btn.setFont(fontload.tracked_font("LABEL", t.SIZE_SMALL, scale=scale, mono=True))
    btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
    btn.setFlat(True)
    if tone:
        btn.setProperty("tone", tone)
    btn.clicked.connect(on_click)
    return btn


def _tag(text, blocked=False):
    """A rhythm `tag` badge (mono, upper, +0.06em through rhythm.apply;
    RADIUS_ROUND, TEXT_SECONDARY); ``blocked`` paints it HOT_SOFT - the one
    warm note the card may carry."""
    badge = c.Badge(text)
    badge.setProperty("rhythm_role", "tag")
    badge.setFont(fontload.apply_family(badge.font(), mono=True))
    if blocked:
        badge.setProperty("status", "BLOCKED")
    return badge


def _band(name, parent):
    """One of the three DsCard bands (#DsCard > #DsCardHeader / Body /
    Footer - qss.py dresses them); its interior is a `stack` row."""
    band = QtWidgets.QWidget(parent)
    band.setObjectName(name)
    band.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
    band.setProperty("rhythm_role", "stack")
    return band


class _ProposalCard(c.Card):
    """One gate proposal, in the panel's own vocabulary (bc-wave BC-6a).

    A DsCard (no tone - the level is never a border hue) whose three bands
    touch (`band`, 0/0 through the applier):

      header  level `tag` + operation (mono DATA, TEXT_PRIMARY) + agent (mono,
              TEXT_TERTIARY); CRITICAL's tag is the one BLOCKED (HOT_SOFT)
      body    the description in sans body text; CRITICAL adds the line
              'Arbitrary code execution' in body text - no hue, no pulse
      footer  countdown (mono DATA, TEXT_SECONDARY; timed levels only) left,
              verbs right - REJECT tone=hot and APPROVE tone=accent for
              APPROVE / CRITICAL (APPROVE is the one accented thing on the
              card); REVIEW gets '<- REVERT' with no tone: REVIEW 'continues
              unless rejected' (CLAUDE.md 1.2, shared/bridge.py), so the
              reject after the fact IS a revert - the verb emits
              reject_clicked (the ledger) AND revert_requested (the undo the
              panel routes to _on_revert).

    A decision reads as a `tag` in the footer's left slot - APPROVED
    (neutral) or REJECTED (BLOCKED) - with the verbs hidden and the card
    disabled; a decision that never reached the gate reads NOT RECORDED
    (BLOCKED) with the card still live (RULING 18). Uses QWidget parents (not
    QFrame) so Houdini's global QFrame styles cannot intercept clicks.
    """

    approve_clicked = Signal(str)   # proposal_id
    reject_clicked = Signal(str)    # proposal_id
    revert_requested = Signal(str)  # proposal_id (REVIEW's verb)

    def __init__(self, proposal_data, parent=None):
        super().__init__(parent=parent)
        self.setProperty("rhythm_role", "band")
        self._proposal_id = proposal_data.get("proposal_id", "")
        self._level = proposal_data.get("level", "review")
        self._timeout = _LEVEL_TIMEOUTS.get(self._level, 0)
        self._created_at = proposal_data.get("created_at", "")
        self._operation = proposal_data.get("operation", "unknown")
        self._reject_btn = None
        self._approve_btn = None
        self._revert_btn = None
        self._decision = None

        bands = QtWidgets.QVBoxLayout(self)

        # -- header: [level tag][operation .................][agent] --------
        header = _band("DsCardHeader", self)
        hrow = QtWidgets.QHBoxLayout(header)
        self._badge = _tag(self._level.upper(), blocked=(self._level == "critical"))
        hrow.addWidget(self._badge)
        self._op_label = c.label(self._operation, role="body")
        self._op_label.setFont(fontload.tracked_font("DATA", t.SIZE_SMALL, mono=True))
        hrow.addWidget(self._op_label, 1)
        self._agent_label = None
        agent_id = proposal_data.get("agent_id", "")
        if agent_id:
            self._agent_label = c.label(agent_id, role="caption")
            self._agent_label.setFont(fontload.tracked_font("DATA", t.SIZE_SMALL, mono=True))
            hrow.addWidget(self._agent_label)
        bands.addWidget(header)

        # -- body: the description (sans body); CRITICAL says so in words ---
        body = _band("DsCardBody", self)
        brow = QtWidgets.QVBoxLayout(body)
        desc = proposal_data.get("description", "")
        self._desc_label = c.label(desc, role="body")
        self._desc_label.setWordWrap(True)
        brow.addWidget(self._desc_label)
        self._critical_label = None
        if self._level == "critical":
            self._critical_label = c.label("Arbitrary code execution", role="body")
            self._critical_label.setWordWrap(True)
            brow.addWidget(self._critical_label)
        if not desc and self._critical_label is None:
            body.hide()
        bands.addWidget(body)

        # -- footer: [countdown | decision tag] ........ [verbs] ------------
        footer = _band("DsCardFooter", self)
        frow = QtWidgets.QHBoxLayout(footer)
        self._countdown_label = c.label("", role="label")
        self._countdown_label.setFont(fontload.tracked_font("DATA", t.SIZE_SMALL, mono=True))
        frow.addWidget(self._countdown_label)
        self._decision_tag = _tag("")
        self._decision_tag.hide()
        frow.addWidget(self._decision_tag)
        frow.addStretch(1)
        if self._level == "review":
            self._revert_btn = _verb("\u2190 REVERT", self._on_revert_clicked)
            frow.addWidget(self._revert_btn)
        elif self._level in ("approve", "critical"):
            # Store as instance vars to prevent GC before layout takes ownership
            self._reject_btn = _verb("REJECT", partial(self._emit_reject, self._proposal_id),
                                     tone="hot")
            frow.addWidget(self._reject_btn)
            self._approve_btn = _verb("APPROVE", self._on_approve_clicked, tone="accent")
            frow.addWidget(self._approve_btn)
        bands.addWidget(footer)

        if self._timeout > 0 and self._level in ("approve", "critical"):
            self._remaining = self._timeout
            self._countdown_timer = QTimer(self)
            self._countdown_timer.timeout.connect(self._tick_countdown)
            self._countdown_timer.setInterval(1000)
            self._countdown_timer.start()
            self._update_countdown_text()
        else:
            self._countdown_label.hide()

    # -- verbs ---------------------------------------------------------------
    def _verbs(self):
        return [b for b in (self._reject_btn, self._approve_btn, self._revert_btn)
                if b is not None]

    def _emit_reject(self, proposal_id, checked=False):
        """Slot for reject button. Accepts checked arg from clicked(bool)."""
        self.reject_clicked.emit(proposal_id)

    def _on_revert_clicked(self, checked=False):
        """REVIEW's verb: the rejection goes to the ledger, the undo goes to
        the panel (revert_requested -> _on_revert)."""
        self.reject_clicked.emit(self._proposal_id)
        self.revert_requested.emit(self._proposal_id)

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

    # -- countdown -----------------------------------------------------------
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

    def _stop_timers(self):
        timer = getattr(self, "_countdown_timer", None)
        if timer is not None:
            timer.stop()

    def _show_decision_tag(self, text, blocked):
        self._countdown_label.hide()
        self._decision_tag.setText(text)
        self._decision_tag.setProperty("status", "BLOCKED" if blocked else "")
        self._decision_tag.show()
        c.repolish(self._decision_tag)

    # -- outcomes ------------------------------------------------------------
    def mark_gate_unreachable(self):
        """The decision did NOT reach the gate. Say so, and stay undecided.

        RULING 18. The card must not dim, must not read APPROVED or REJECTED,
        and must not look settled - because nothing was settled. The proposal
        is still live and still needs a decision that lands: the verbs stay,
        the card stays enabled, the footer says NOT RECORDED.
        """
        self._stop_timers()
        self._show_decision_tag("NOT RECORDED", blocked=True)

    def mark_decided(self, decision):
        """The decision landed: the verbs go, the footer's left slot becomes
        the decision tag - APPROVED (neutral) or REJECTED (BLOCKED) - and the
        card disables. A tag, never a hue (F4); the chat message is the
        GateWidget's."""
        self._stop_timers()
        self._decision = decision
        is_approved = decision == "approved"
        for verb in self._verbs():
            verb.setVisible(False)
        self._show_decision_tag("APPROVED" if is_approved else "REJECTED",
                                blocked=not is_approved)
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
    # bc-wave BC-6a: REVIEW's '<- REVERT' asks the panel for the undo.
    revert_requested = Signal(str)  # proposal_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._cards = {}  # proposal_id -> _ProposalCard
        self._card_host = None          # a QLayout the panel lends (BC-6b), else own
        self._card_host_changed = None  # callback after a card lands / decides

        self._build_ui()
        self._register_gate_callbacks()
        self._proposal_received.connect(self._add_proposal_card)
        self._decision_made.connect(self._on_remote_decision)

    def _build_ui(self):
        """Build the collapsible container with proposals list + integrity row."""
        layout = QtWidgets.QVBoxLayout(self)
        self.setProperty("rhythm_role", "stack")

        # -- Chevron toggle header --
        self._header = QtWidgets.QPushButton(self)
        self._header.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        # Landing r3 repair (F-C1): the mono family rides the QFont (the QSS
        # family declarations were purged); header, fidelity, counts and
        # violations are the ids master rendered in Space Mono.
        self._header.setFont(fontload.apply_family(self._header.font(), mono=True))
        qss.sweep_a_style(self._header, "gate_header")
        self._update_header_text()
        self._header.clicked.connect(self._toggle)
        layout.addWidget(self._header)

        # -- Collapsible body --
        self._body = QtWidgets.QWidget(self)
        self._body.setVisible(False)
        qss.sweep_a_style(self._body, "gate_body")
        body_layout = QtWidgets.QVBoxLayout(self._body)
        self._body.setProperty("rhythm_role", "stack")


        # Proposals container (direct layout — no QScrollArea, which eats
        # mouse events on Windows 11 / PySide6 and blocks button clicks)
        self._proposals_container = QtWidgets.QWidget(self._body)
        self._proposals_container.setMaximumHeight(200)
        self._proposals_layout = QtWidgets.QVBoxLayout(self._proposals_container)
        self._proposals_container.setProperty("rhythm_role", "card")

        self._proposals_layout.addStretch()

        body_layout.addWidget(self._proposals_container)

        # -- Integrity status row --
        self._integrity_row = QtWidgets.QWidget(self._body)
        qss.sweep_a_style(self._integrity_row, "gate_integrity")
        integrity_layout = QtWidgets.QHBoxLayout(self._integrity_row)
        self._integrity_row.setProperty("rhythm_role", "stack")


        # Neither the dot's color nor the label's text is named here. Both come
        # from _render_fidelity below, seeded with None \u2014 so the row is born
        # UNKNOWN and cannot be constructed into a state it never observed.
        self._fidelity_dot = QtWidgets.QLabel("\u25CF")
        integrity_layout.addWidget(self._fidelity_dot)

        self._fidelity_label = QtWidgets.QLabel()
        self._fidelity_label.setFont(fontload.apply_family(self._fidelity_label.font(), mono=True))
        qss.sweep_a_style(self._fidelity_label, "gate_fidelity_label")
        integrity_layout.addWidget(self._fidelity_label)

        # Honest resting state: unmeasured until an observation arrives.
        self._render_fidelity(None)

        sep1 = QtWidgets.QLabel("|")
        qss.sweep_a_style(sep1, "gate_separator")
        integrity_layout.addWidget(sep1)

        self._ops_label = QtWidgets.QLabel("0 ops")
        self._ops_label.setFont(fontload.apply_family(self._ops_label.font(), mono=True))
        qss.sweep_a_style(self._ops_label, "gate_counts")
        integrity_layout.addWidget(self._ops_label)

        sep2 = QtWidgets.QLabel("|")
        qss.sweep_a_style(sep2, "gate_separator")
        integrity_layout.addWidget(sep2)

        self._violations_label = QtWidgets.QLabel("0 violations")
        self._violations_label.setFont(
            fontload.apply_family(self._violations_label.font(), mono=True))
        qss.sweep_a_style(self._violations_label, "gate_violations", t.SLATE)
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

    def set_card_host(self, layout, on_change=None):
        """Lend the cards a home (bc-wave BC-6a/6b): new proposal cards insert
        into ``layout`` (the panel's CHAT consent slot) instead of this
        widget's own fold; ``on_change`` is called after a card lands or
        decides so the host can re-sync its visibility. ``None`` restores
        the default (this widget's container)."""
        self._card_host = layout
        self._card_host_changed = on_change

    def _notify_host(self):
        # getattr: the consent-honesty tests drive the handlers on a bare
        # GateWidget.__new__ that carries only what they touch.
        cb = getattr(self, "_card_host_changed", None)
        if callable(cb):
            try:
                cb()
            except Exception:
                logger.debug("consent host callback failed", exc_info=True)

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

        host = getattr(self, "_card_host", None)
        card = _ProposalCard(data, parent=None if host is not None else self._proposals_container)
        card.approve_clicked.connect(self._on_approve)
        card.reject_clicked.connect(self._on_reject)
        card.revert_requested.connect(self.revert_requested)

        if host is not None:
            host.addWidget(card)             # the panel's consent slot (BC-6b)
        else:
            # Insert before the stretch
            count = self._proposals_layout.count()
            self._proposals_layout.insertWidget(max(0, count - 1), card)
        self._cards[proposal_id] = card
        qss.sweep_a_refresh_rhythm(card)

        # Auto-expand when a proposal arrives in the fold
        if host is None and not self._expanded:
            self._toggle()

        self._update_header_text()
        self._notify_host()

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
        self._notify_host()

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
        self._notify_host()

    @Slot(str, str)
    def _on_remote_decision(self, proposal_id, decision):
        """Handle decision made elsewhere (e.g. another UI or auto-system)."""
        card = self._cards.get(proposal_id)
        if card:
            card.mark_decided(decision)
        self._update_header_text()
        self._notify_host()

    def _render_fidelity(self, fidelity):
        """Paint the dot + label from an observed fidelity, or ``None``.

        The single write point for this row. It names no color token itself —
        the verdict is delegated to ``_fidelity_color`` so green cannot be
        reached without passing that guard, the same containment
        ``IntegrityReadout.set_integrity`` uses.
        """
        qss.sweep_a_style(self._fidelity_dot, "gate_fidelity_dot", _fidelity_color(fidelity))
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
        qss.sweep_a_style(self._violations_label, "gate_violations", v_color)
        self._violations_label.setText("{n} violations".format(n=violations))

    def handle_ws_proposal(self, data):
        """Handle a gate_proposal message from the WebSocket bridge."""
        self._add_proposal_card(data)

    def handle_ws_report(self, data):
        """Handle a session_report message from the WebSocket bridge."""
        self.update_integrity(data)
