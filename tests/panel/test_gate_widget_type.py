"""GateWidget type travels by QFont, never by QSS (landing r3 repair, F-C1).

d26d2703 purged the SWEEP_A font-family declarations on the stated ground that
families travel by QFont via fontload / rhythm._apply_type. GateWidget is
shipped (synapse_panel.py builds it through FaceReview) and applied no family,
so every gate label and button fell to the app default (Houdini's UI font -
'Courier' offscreen) while master rendered them in Space Mono. Battleplan
section 4: mono = labels / tags / ids. This pins the composed panel's gate.

Skips cleanly without real PySide (stock-Python CI); runs for real under hython.
"""
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_hou = types.ModuleType("hou")
sys.modules.setdefault("hou", _hou)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtWidgets, QtGui
    _HAVE_QT = True
except ImportError:
    try:
        from PySide2 import QtWidgets, QtGui
        _HAVE_QT = True
    except ImportError:
        _HAVE_QT = False

# Real Qt only - a sibling test's PySide stub would otherwise flip _HAVE_QT.
if _HAVE_QT:
    try:
        _qapp = getattr(QtWidgets, "QApplication", None)
        if not (isinstance(_qapp, type) and "PySide" in getattr(_qapp, "__module__", "")):
            _HAVE_QT = False
    except Exception:
        _HAVE_QT = False

import pytest

if not _HAVE_QT:
    pytestmark = pytest.mark.skip(reason="PySide unavailable - run via hython")

_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def _family(widget):
    return QtGui.QFontInfo(widget.font()).family()


@pytest.fixture
def composed_gate():
    _app()
    from synapse.panel.designsystem import fontload
    from synapse.panel.synapse_panel import SynapsePanel
    fontload.load_application_fonts()
    panel = SynapsePanel()
    try:
        panel._recompose("expert")
        panel.resize(380, 760)
        panel.show()
        _app().processEvents()
        gate = panel._gate
        assert gate is not None and type(gate).__module__.endswith(".gate_widget")
        gate._add_proposal_card({"proposal_id": "p-type", "level": "approve",
                                 "operation": "delete_node", "agent_id": "HANDS",
                                 "description": "type probe", "created_at": ""})
        _app().processEvents()
        yield panel, gate, list(gate._cards.values())[0]
    finally:
        panel.close()


def _mono_and_default():
    from synapse.panel.designsystem import fontload
    mono = QtGui.QFontInfo(fontload.apply_family(QtGui.QFont(), mono=True)).family()
    default = QtGui.QFontInfo(_app().font()).family()
    # The pin is only evidence when the bundled mono differs from the app font.
    assert mono != default, (mono, default)
    return mono, default


def _card_elements(card):
    by_key = {}
    for w in card.findChildren(QtWidgets.QWidget):
        key = w.property("sweep_a_style")
        if key:
            by_key[key] = w
    return by_key


def test_gate_badge_in_the_composed_panel_is_the_bundled_mono(composed_gate):
    _, _, card = composed_gate
    mono, _ = _mono_and_default()
    badge = _card_elements(card)["gate_badge"]
    assert badge.text() == "APPROVE"
    assert _family(badge) == mono, _family(badge)


def test_every_master_mono_gate_element_is_still_mono(composed_gate):
    """The nine elements master rendered in Space Mono (CRUX round-3 probe):
    header, badge, operation, countdown, Reject, Approve, fidelity label,
    counts, violations. Agent / description / critical carried no family on
    master (host font) and are not pinned."""
    _, gate, card = composed_gate
    mono, _ = _mono_and_default()
    by_key = _card_elements(card)
    elements = {
        "gate_header": gate._header,
        "gate_fidelity_label": gate._fidelity_label,
        "gate_counts": gate._ops_label,
        "gate_violations": gate._violations_label,
        "gate_badge": by_key["gate_badge"],
        "gate_operation": by_key["gate_operation"],
        "gate_countdown": by_key["gate_countdown"],
        "gate_reject": by_key["gate_reject"],
        "gate_approve": by_key["gate_approve"],
    }
    wrong = {key: _family(w) for key, w in elements.items() if _family(w) != mono}
    assert not wrong, wrong


def test_gate_families_survive_a_state_transition(composed_gate):
    """sweep_a_style repolishes on every state change; the QFont family must
    survive the unpolish/polish cycle and the colour-selected rule swap."""
    _, gate, card = composed_gate
    mono, _ = _mono_and_default()
    gate._render_fidelity(0.5)
    _app().processEvents()
    assert _family(gate._violations_label) == mono
    assert _family(gate._fidelity_label) == mono
    by_key = _card_elements(card)
    assert _family(by_key["gate_countdown"]) == mono
