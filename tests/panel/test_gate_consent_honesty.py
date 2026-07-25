"""RULING 18 - a consent gate that reports success on a swallowed exception.

Regression pins for the defect L3 found: `_on_approve` / `_on_reject` caught every
exception from `gate.decide()`, logged it, and then marked the card decided and emitted
`decision_announced` REGARDLESS. The artist saw APPROVED, the chat announced APPROVED,
and the gate recorded nothing.

The reject path is the dangerous one: a reject that never reached the gate has not
blocked anything.

These tests import the module and drive the handlers with a stubbed HumanGate. They do
not construct Qt widgets, so they run on any interpreter.
"""
import sys
import types
import pytest

# Constitution Law 1: a skip is honest, a pass is a lie.
# PySide is absent from the dev interpreter (3.14) and present under hython3.13.
# These tests therefore SKIP on the dev box and EXECUTE on the shipping one.
pytest.importorskip(
    "synapse.panel.gate_widget",
    reason="panel/gate_widget needs PySide6/PySide2 - present under hython, absent on the dev interpreter",
)


def _install_failing_gate(monkeypatch):
    """Make synapse.core.gates.HumanGate.get_instance().decide() raise."""
    mod = types.ModuleType("synapse.core.gates")

    class GateDecision:
        APPROVED = "APPROVED"
        REJECTED = "REJECTED"

    class HumanGate:
        @staticmethod
        def get_instance():
            class _G:
                def decide(self, *a, **k):
                    raise RuntimeError("gate unreachable")
            return _G()

    mod.GateDecision = GateDecision
    mod.HumanGate = HumanGate
    monkeypatch.setitem(sys.modules, "synapse.core.gates", mod)


class _FakeCard:
    """Minimal stand-in - records which visual contract was invoked."""

    def __init__(self):
        self._proposal_id = "p1"
        self._operation = "delete_node"
        self._level = "APPROVE"
        self.decided_as = None
        self.gate_unreachable = False

    def mark_decided(self, decision):
        self.decided_as = decision

    def mark_gate_unreachable(self):
        self.gate_unreachable = True


class _Recorder:
    def __init__(self):
        self.emitted = []

    def emit(self, *args):
        self.emitted.append(args)


def _make_widget(card):
    """Build a bare object carrying only what the handlers touch."""
    from synapse.panel import gate_widget

    w = object.__new__(gate_widget.GateWidget)
    w._cards = {"p1": card}
    w.decision_announced = _Recorder()
    w._update_header_text = lambda: None
    return w


def test_approve_does_not_announce_when_gate_raises(monkeypatch):
    _install_failing_gate(monkeypatch)
    card = _FakeCard()
    w = _make_widget(card)

    w._on_approve("p1")

    assert card.decided_as is None, "card must not read APPROVED - the gate never recorded it"
    assert w.decision_announced.emitted == [], "must not announce a decision that did not land"
    assert card.gate_unreachable is True, "artist must be told the decision was not recorded"


def test_reject_does_not_announce_when_gate_raises(monkeypatch):
    """The high-stakes half: an unlanded reject has blocked nothing."""
    _install_failing_gate(monkeypatch)
    card = _FakeCard()
    w = _make_widget(card)

    w._on_reject("p1")

    assert card.decided_as is None, "card must not read REJECTED - nothing was blocked"
    assert w.decision_announced.emitted == [], "must not announce a reject that did not land"
    assert card.gate_unreachable is True


def test_approve_announces_normally_when_gate_succeeds(monkeypatch):
    """The fix must not break the working path."""
    mod = types.ModuleType("synapse.core.gates")

    class GateDecision:
        APPROVED = "APPROVED"
        REJECTED = "REJECTED"

    recorded = []

    class HumanGate:
        @staticmethod
        def get_instance():
            class _G:
                def decide(self, pid, decision, who):
                    recorded.append((pid, decision, who))
            return _G()

    mod.GateDecision = GateDecision
    mod.HumanGate = HumanGate
    monkeypatch.setitem(sys.modules, "synapse.core.gates", mod)

    card = _FakeCard()
    w = _make_widget(card)

    w._on_approve("p1")

    assert recorded == [("p1", "APPROVED", "panel_artist")]
    assert card.decided_as == "approved"
    assert card.gate_unreachable is False
    assert len(w.decision_announced.emitted) == 1
