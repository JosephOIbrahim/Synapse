"""F4 - a REVIEW consent card is the way back, and it must not lie to buy it.

THE DIAGNOSIS (Pass 2's, and it stands).  A REVIEW card is not a decision point.
``shared/bridge.py:_check_consent_gate`` returns ``proposal.decision != REJECTED``
for REVIEW at propose time, with no wait, so consent is granted before the
artist sees anything and the mutation goes ahead.  The card's lone verb,
``<- REVERT``, is the artist's labelled route back to that mutation.

THE TWO DEFECTS THIS FILE PINS.

1.  The verb filed a decision that never happened.  ``_on_revert_clicked``
    emitted ``reject_clicked`` first, which reached
    ``GateWidget._on_reject`` -> ``HumanGate.decide(pid, REJECTED)`` ->
    ``mark_decided('rejected')``.  Nothing was blocked - the bridge had already
    returned True - so REJECTED was false in the gate ledger, false in the
    footer tag, and false in the chat line ``[x] REJECTED: <op> (REVIEW)``.

2.  The verb destroyed itself on the one path where it was still needed.  That
    same ``reject_clicked`` tore the card down synchronously, and only THEN did
    ``revert_requested`` reach ``synapse_panel._on_revert``, which refuses while
    the worker is streaming with "Still working - Stop the current turn before
    reverting."  A REVIEW card is raised by a tool call inside a streaming turn,
    so the refusal is the ordinary case: the artist was told to come back to a
    control that had just been removed.

THE SHAPE.  Not permanence.  ``houdini_undo`` is ``hou.undos.performUndo()``
(``server/handlers.py``) - one global step, no target - so the verb cannot be
scoped, and an unscoped verb must not be permanent.  So the card settles on a
request that actually went out (reading UNDO SENT, which is what happened), and
survives a refusal, which is what the artist needs.

Stated exactly, because an earlier draft of this docstring overclaimed it as
"momentary" and "not unbounded": nothing here bounds a refused card's lifetime.
``_cards`` is only ever appended to, ``_sync_consent_slot`` only HIDES disabled
cards, and REVIEW carries no auto-decide timer - that wiring is gated to
approve/critical at ``gate_widget.py:269``.  A refused card returns to the same
undecided-and-live state an unclicked card is already in, and nothing evicts it.
That is master's pre-existing state reached by a second door.  It is strictly
better than a card made permanent on EVERY path, which is what this replaces -
but it is not a bound, and must not be described as one.

BAND: HEADLESS-PROVEN.  Every test here runs the SHIPPED method bodies, pulled
out of the source by ``ast`` and driven against stand-ins - the same technique
``tests/test_first_session_panel.py`` uses for the panel.  Nothing imports
PySide, so nothing here can skip on the dev interpreter, and a green line means
the code ran.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

_ROOT = Path(__file__).parents[2] / "python/synapse/panel"


def _methods(filename, classname, *names):
    """Exec the named methods of ``classname`` straight out of the source file.

    No import of the module, so ``gate_widget``'s top-level ``from PySide6
    import ...`` never runs.  The bodies below touch only ``self``, so a
    SimpleNamespace is a sufficient receiver.
    """
    source = _ROOT / filename
    tree = ast.parse(source.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == classname)
    out = {}
    namespace = {"logger": Mock()}
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            node.decorator_list = []
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"),
                 namespace)
            out[node.name] = namespace[node.name]
    missing = set(names) - set(out)
    assert not missing, "%s.%s does not define %s" % (filename, classname, sorted(missing))
    return out


def _panel_methods(*names):
    return _methods("synapse_panel.py", "SynapsePanel", *names)


class _Recorder:
    """A stand-in Signal that remembers what was emitted, in order."""

    def __init__(self, log, label):
        self._log = log
        self._label = label

    def emit(self, *args):
        self._log.append((self._label,) + args)


def _fake_card(level="review", pid="p1", operation="delete_node"):
    """A card stand-in carrying only what the extracted bodies touch."""
    verb = SimpleNamespace(visible=True)
    verb.setVisible = lambda v, _b=verb: setattr(_b, "visible", v)
    card = SimpleNamespace(
        _proposal_id=pid, _level=level, _operation=operation, _decision=None,
        _revert_btn=verb, _enabled=True, tag=None, tag_blocked=None,
        timers_stopped=False, emitted=[],
    )
    card.reject_clicked = _Recorder(card.emitted, "reject_clicked")
    card.revert_requested = _Recorder(card.emitted, "revert_requested")
    card._verbs = lambda: [verb]
    card._stop_timers = lambda: setattr(card, "timers_stopped", True)
    card._show_decision_tag = lambda text, blocked: (
        setattr(card, "tag", text), setattr(card, "tag_blocked", blocked))
    card.setEnabled = lambda v: setattr(card, "_enabled", v)
    return card


# ── Defect 1: the verb files no decision that did not happen ──────────────

def test_revert_verb_files_no_gate_decision():
    """REVIEW consent was granted by the bridge before this card was drawn, so
    the verb has no decision to report.  It must ask for the undo and nothing
    else - no ``reject_clicked``, which is what reached
    ``HumanGate.decide(pid, REJECTED)`` and painted REJECTED on an operation
    that was never blocked."""
    clicked = _methods("gate_widget.py", "_ProposalCard", "_on_revert_clicked")
    card = _fake_card(pid="p7")

    clicked["_on_revert_clicked"](card)

    assert card.emitted == [("revert_requested", "p7")], card.emitted
    assert not any(e[0] == "reject_clicked" for e in card.emitted), (
        "the verb still files REJECTED against a proposal the bridge let through")


def test_the_card_carries_its_proposal_id_to_the_panel():
    """The answer has to come back to THIS card, so the id has to leave it."""
    clicked = _methods("gate_widget.py", "_ProposalCard", "_on_revert_clicked")
    card = _fake_card(pid="proposal-42")

    clicked["_on_revert_clicked"](card)

    assert card.emitted[0][1] == "proposal-42"


# ── Defect 2: a refused revert does not take the way back with it ─────────

def _gate(cards):
    g = SimpleNamespace(_cards=cards, header_updates=0, host_notified=0)
    g._update_header_text = lambda: setattr(g, "header_updates", g.header_updates + 1)
    g._notify_host = lambda: setattr(g, "host_notified", g.host_notified + 1)
    return g


def test_refused_revert_leaves_the_card_live_and_records_nothing():
    """The refusal is the ORDINARY case - a REVIEW card is raised by a tool call
    inside a streaming turn, and ``_on_revert`` refuses while the worker runs.
    On that path nothing happened, so the card must say nothing and stay
    clickable."""
    note = _methods("gate_widget.py", "GateWidget", "note_revert_outcome")
    card = _fake_card()
    g = _gate({"p1": card})

    note["note_revert_outcome"](g, "p1", False)

    assert card.tag is None, "the card reported an outcome that did not happen"
    assert card._enabled is True, "the refused path disabled the way back"
    assert card._revert_btn.visible is True, "the refused path hid the way back"
    assert card._decision is None


def test_sent_revert_settles_the_card_reading_what_happened():
    """The request went out.  That - not APPROVED, not REJECTED - is what the
    card reports, and it settles like any other resolved card so
    ``_sync_consent_slot`` retires it on the existing rule."""
    methods = _methods("gate_widget.py", "GateWidget", "note_revert_outcome")
    sent = _methods("gate_widget.py", "_ProposalCard", "mark_revert_sent")
    card = _fake_card()
    card.mark_revert_sent = lambda: sent["mark_revert_sent"](card)
    g = _gate({"p1": card})

    methods["note_revert_outcome"](g, "p1", True)

    assert card.tag == "UNDO SENT"
    assert card.tag_blocked is False, "a request in flight is not a block"
    assert card._enabled is False
    assert card._revert_btn.visible is False
    assert card.timers_stopped is True


def test_the_outcome_never_reads_rejected():
    """B7's pin.  Whatever the card ends up saying about its own revert, it is
    not a claim that the operation was blocked."""
    sent = _methods("gate_widget.py", "_ProposalCard", "mark_revert_sent")
    card = _fake_card()

    sent["mark_revert_sent"](card)

    assert card.tag != "REJECTED"
    assert card.tag_blocked is False


def test_an_unknown_proposal_id_settles_nothing():
    """An answer for a card that is gone must not settle a different one."""
    note = _methods("gate_widget.py", "GateWidget", "note_revert_outcome")
    card = _fake_card()
    g = _gate({"p1": card})

    note["note_revert_outcome"](g, "does-not-exist", True)

    assert card.tag is None
    assert card._enabled is True


# ── The panel half: the request reports whether it went out ──────────────

def _panel(running):
    return SimpleNamespace(
        _worker=SimpleNamespace(isRunning=lambda: running),
        _chat=Mock(), _set_face=Mock(), _send=Mock(return_value=True),
    )


def test_refused_revert_returns_false():
    """``_on_revert`` refuses while the worker streams.  Its caller has to be
    able to tell - a card that settles on a refused request is the lie this
    whole fix is about."""
    revert = _panel_methods("_on_revert")["_on_revert"]
    panel = _panel(running=True)

    assert revert(panel) is False
    panel._send.assert_not_called()
    panel._chat.append_system_message.assert_called_once_with(
        "Still working - Stop the current turn before reverting.")


def test_accepted_revert_returns_true_and_a_declined_send_returns_false():
    revert = _panel_methods("_on_revert")["_on_revert"]

    panel = _panel(running=False)
    assert revert(panel) is True
    panel._set_face.assert_called_once_with("direct")

    declined = _panel(running=False)
    declined._send.return_value = False
    assert revert(declined) is False
    declined._set_face.assert_not_called()


def test_the_request_names_the_operation_the_card_names():
    """B6's pin, narrowed to what is true.  ``houdini_undo`` is
    ``hou.undos.performUndo()`` - one global step, no target - so this does NOT
    scope the undo.  It puts the card's own operation name into the request, so
    the request names the same change the card header does instead of asking
    for 'the last change' and nothing else."""
    revert = _panel_methods("_on_revert")["_on_revert"]
    panel = _panel(running=False)

    assert revert(panel, "delete_node") is True

    prompt = panel._send.call_args[0][0]
    assert "houdini_undo" in prompt
    assert "delete_node" in prompt, prompt

    plain = _panel(running=False)
    revert(plain)
    assert "delete_node" not in plain._send.call_args[0][0]


# ── The whole chain, on the path that actually happens ───────────────────

def test_clicking_revert_mid_turn_leaves_the_control_the_artist_was_sent_back_to():
    """End to end, on the ordinary path: the card is raised by a tool call in a
    streaming turn, the artist clicks REVERT, the panel refuses.  Nothing is
    filed, and the control they were just told to use is still there."""
    clicked = _methods("gate_widget.py", "_ProposalCard", "_on_revert_clicked")
    note = _methods("gate_widget.py", "GateWidget", "note_revert_outcome")
    relay = _panel_methods("_on_gate_revert")["_on_gate_revert"]
    revert = _panel_methods("_on_revert")["_on_revert"]

    card = _fake_card(pid="p1", operation="delete_node")
    gate = _gate({"p1": card})
    gate.note_revert_outcome = lambda pid, ok: note["note_revert_outcome"](gate, pid, ok)

    panel = _panel(running=True)
    panel._gate = gate
    panel._on_revert = lambda operation="": revert(panel, operation)

    # The card's verb fires; the relay is what the panel wires it to.
    clicked["_on_revert_clicked"](card)
    assert card.emitted == [("revert_requested", "p1")]
    assert relay(panel, card.emitted[0][1]) is False

    panel._chat.append_system_message.assert_called_once_with(
        "Still working - Stop the current turn before reverting.")
    assert card.tag is None, "a refused revert reported an outcome"
    assert card._enabled is True, "the artist was sent back to a control that was gone"
    assert card._revert_btn.visible is True


def test_the_same_chain_after_the_turn_stops_settles_the_card_once():
    """And the other half: with the turn stopped the request goes out, the card
    settles reading what happened, and the operation name rides along."""
    note = _methods("gate_widget.py", "GateWidget", "note_revert_outcome")
    sent = _methods("gate_widget.py", "_ProposalCard", "mark_revert_sent")
    relay = _panel_methods("_on_gate_revert")["_on_gate_revert"]
    revert = _panel_methods("_on_revert")["_on_revert"]

    card = _fake_card(pid="p1", operation="delete_node")
    card.mark_revert_sent = lambda: sent["mark_revert_sent"](card)
    gate = _gate({"p1": card})
    gate.note_revert_outcome = lambda pid, ok: note["note_revert_outcome"](gate, pid, ok)

    panel = _panel(running=False)
    panel._gate = gate
    panel._on_revert = lambda operation="": revert(panel, operation)

    assert relay(panel, "p1") is True
    assert "delete_node" in panel._send.call_args[0][0]
    assert card.tag == "UNDO SENT"
    assert card._enabled is False
