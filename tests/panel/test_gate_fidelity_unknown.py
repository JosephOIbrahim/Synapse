"""FID — the gate widget's integrity row must never claim a fidelity it has
not observed.

The defect these pin: ``gate_widget.py`` CONSTRUCTED its integrity row reading
a literal ``"Fidelity 1.0"`` against a green dot, before a single operation had
run, and its update path formatted ``report.get("session_fidelity", 1.0)``
unconditionally — so a report carrying no fidelity at all still painted a green
perfect score. Same claim-without-observation class as a hardcoded
``success=True``. The house rule it broke is stated in ``panel/face_token.py``:
*"Unobtainable renders as UNKNOWN, never zero and never an estimate."*

WHAT MAKES EACH OF THESE ABLE TO FAIL (Constitution Law 1 — state the condition
under which the check fails, or you have written a decoration):

  · (a) fails if the constructed row reads anything other than UNKNOWN — the
        pre-fix code read "Fidelity 1.0" and failed this assertion.
  · (b) fails if the UNKNOWN guard swallowed the working path and a genuinely
        observed value stopped rendering as a number.
  · (c) fails if a missing ``session_fidelity`` produces a formatted number
        again (a restored ``.get`` default), or raises.
  · (d) fails if the bridge's rest-state 1.0 at zero operations is rendered as
        a measurement.

All four were run against the pre-fix source and the three that pin the defect
(a, c, d) FAILED there; (b) passed before and after, which is the point — it is
the regression guard on the path that already worked.

RUNTIME ENVIRONMENT — read before trusting a green: these construct real
``QWidget``s, and ``gate_widget.py`` hard-imports PySide at module top. Under
the stock dev interpreter (3.14, no PySide) this module SKIPS, and a skip exits
0, which a harness reads as passing. Run under hython for a real signal:

    QT_QPA_PLATFORM=offscreen hython3.13 -m pytest tests/panel/test_gate_fidelity_unknown.py

The Qt-free half of this contract — the one that executes on EVERY interpreter —
is ``tests/test_gate_fidelity_honesty_sourcepin.py``.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtWidgets  # noqa: F401
    _HAVE_QT = True
except ImportError:
    try:
        from PySide2 import QtWidgets  # noqa: F401
        _HAVE_QT = True
    except ImportError:
        _HAVE_QT = False

# Real Qt only — reject leaked PySide stubs (see tests/test_panel_faces.py).
# A MagicMock QApplication would let these "pass" without building a widget,
# which is the Law-1 failure mode wearing a green coat.
if _HAVE_QT:
    try:
        _qapp = getattr(QtWidgets, "QApplication", None)
        if not (isinstance(_qapp, type) and "PySide" in getattr(_qapp, "__module__", "")):
            _HAVE_QT = False
    except Exception:
        _HAVE_QT = False

import pytest

if not _HAVE_QT:
    pytestmark = pytest.mark.skip(reason="PySide unavailable — run via hython")


_APP = None


def _make_widget():
    """A real, fully constructed GateWidget — no stubs on the row under test."""
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from synapse.panel.gate_widget import GateWidget
    return GateWidget()


def _dot_color(widget):
    """The colour the fidelity dot is actually painted, from its stylesheet."""
    return widget._fidelity_dot.styleSheet()


# ── (a) constructed, never updated ───────────────────────────────

def test_constructed_widget_reads_unknown_before_any_update():
    """id-a — a widget that has observed nothing says so.

    FAILS IF: the row is born with a number. The pre-fix constructor wrote the
    literal "Fidelity 1.0" here against a t.GROW dot.
    """
    from synapse.panel.designsystem import tokens as t

    w = _make_widget()

    assert w._fidelity_label.text() == "Fidelity UNKNOWN", (
        "a constructed row must read UNKNOWN — nothing has been measured yet"
    )
    assert t.SLATE in _dot_color(w), "unmeasured dot must be the neutral token"
    assert t.GROW not in _dot_color(w), (
        "unmeasured dot is GREEN — a fabricated perfect score"
    )
    assert t.ERROR not in _dot_color(w), (
        "unmeasured dot is RED — UNKNOWN is neutral, not a failure claim"
    )


# ── (b) a real observation ───────────────────────────────────────

@pytest.mark.parametrize("fidelity,ops,expected_text,expected_token", [
    (1.0, 5, "Fidelity 1.0", "GROW"),    # genuine all-clear
    (0.8, 3, "Fidelity 0.8", "WARN"),    # degraded
    (0.2, 3, "Fidelity 0.2", "ERROR"),   # broken
])
def test_observed_value_renders_numeric(fidelity, ops, expected_text, expected_token):
    """id-b — an observed value still renders as the number it is.

    The regression guard on the working path: the UNKNOWN state must not have
    been bought by breaking the measured one. Thresholds are unchanged from the
    original row.

    FAILS IF: the guard swallows real observations, or a threshold moved.
    """
    from synapse.panel.designsystem import tokens as t

    w = _make_widget()
    w.update_integrity({
        "session_fidelity": fidelity,
        "operations_total": ops,
        "anchor_violations": 0 if fidelity >= 1.0 else 1,
    })

    assert w._fidelity_label.text() == expected_text
    assert getattr(t, expected_token) in _dot_color(w)


# ── (c) the key is absent ────────────────────────────────────────

def test_missing_session_fidelity_renders_unknown_not_a_default():
    """id-c — an absent measurement is UNKNOWN, never a default.

    FAILS IF: a ``.get(..., 1.0)`` default is restored anywhere on the way in,
    or the missing key raises. The rest of the row must keep working, which is
    what the ops assertion proves — this is a fidelity guard, not a bail-out.
    """
    from synapse.panel.designsystem import tokens as t

    w = _make_widget()
    w.update_integrity({"operations_total": 3, "anchor_violations": 0})

    assert w._fidelity_label.text() == "Fidelity UNKNOWN", (
        "absent session_fidelity produced a number — a default was invented"
    )
    assert t.SLATE in _dot_color(w)
    assert t.GROW not in _dot_color(w)
    # ...and the row did not simply give up:
    assert w._ops_label.text() == "3 ops"
    assert w._violations_label.text() == "0 violations"


def test_unusable_fidelity_value_renders_unknown_without_crashing():
    """id-c, the wire-shaped half. The report arrives as remote JSON, so a
    non-numeric value is reachable. It is not an observation and must not be
    formatted — nor may it raise inside a Qt slot.

    FAILS IF: a string/None/bool is coerced into a number or propagates a
    TypeError out of ``update_integrity``.
    """
    from synapse.panel.designsystem import tokens as t

    for junk in ("1.0", None, True, [], {}):
        w = _make_widget()
        w.update_integrity({
            "session_fidelity": junk,
            "operations_total": 2,
            "anchor_violations": 0,
        })
        assert w._fidelity_label.text() == "Fidelity UNKNOWN", (
            "unusable value %r rendered as a measurement" % (junk,)
        )
        assert t.SLATE in _dot_color(w)


# ── (d) the live path: the bridge's rest state ───────────────────

def test_zero_operations_is_unknown_not_the_bridges_resting_one():
    """id-d — the case the feeder trace actually turns on.

    ``shared/bridge.py``'s ``session_fidelity`` property returns a clean 1.0
    when ``operations_total == 0``, and ``session_report()`` always includes the
    key. So on the live WebSocket path the fabricated perfect score arrives from
    UPSTREAM — removing this widget's ``.get`` default alone would have changed
    nothing visible. Zero operations means nothing was measured.

    This is the already-ratified ``has_data`` doctrine
    (``session_integrity.summary`` / ``integrity_readout._fidelity_color``)
    applied to this row, not new policy.

    FAILS IF: a zero-op report paints a green "Fidelity 1.0".
    """
    from synapse.panel.designsystem import tokens as t

    w = _make_widget()
    w.update_integrity({
        "operations_total": 0,
        "operations_verified": 0,
        "anchor_violations": 0,
        "session_fidelity": 1.0,      # the bridge's rest state, not a measurement
    })

    assert w._fidelity_label.text() == "Fidelity UNKNOWN", (
        "zero operations rendered as a verified 1.0 — the bridge's rest state "
        "presented as a measurement"
    )
    assert t.GROW not in _dot_color(w)
    assert t.SLATE in _dot_color(w)


def test_a_measured_session_still_reaches_green():
    """The negative control for (d): prove the zero-ops guard is not simply
    suppressing green everywhere. With operations present and fidelity full,
    green MUST be reachable — otherwise the guard is a decoration that always
    says UNKNOWN and the row has stopped carrying information.
    """
    from synapse.panel.designsystem import tokens as t

    w = _make_widget()
    w.update_integrity({
        "operations_total": 4,
        "operations_verified": 4,
        "anchor_violations": 0,
        "session_fidelity": 1.0,
    })

    assert w._fidelity_label.text() == "Fidelity 1.0"
    assert t.GROW in _dot_color(w), (
        "a genuinely verified session cannot reach green — the guard over-fires"
    )
