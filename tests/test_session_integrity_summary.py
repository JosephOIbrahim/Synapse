"""Qt-free tests for ``SessionIntegrityTracker.summary()`` (panel Mile 4).

``summary()`` is the honesty-critical aggregation feeding the panel's fidelity
readout. Its load-bearing field is ``has_data``: ``session_fidelity`` returns a
clean 1.0 when nothing has run, so a widget reading only ``fidelity`` would
paint a green 100% before a single operation. ``has_data`` (``total > 0``) is
what tells the widget to render "no operations yet" instead. These tests pin
the contract under stock CPython — no Qt, no ``hou``.
"""

import os
import sys

# Editable install resolves `synapse` -> python/synapse under stock CPython (CI).
# hython launches with CWD=repo root, where a sibling `synapse/` NAMESPACE dir
# shadows python/synapse; pytest's rootdir-prepend + conftest can cache that
# namespace before this module imports. Put python/ first, then evict a stale
# namespace `synapse` (no __file__) so the real package wins — same purge idiom
# the .pypanel loader uses on panel reopen. No-op under stock CPython.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PY = os.path.join(_ROOT, "python")
if _PY not in sys.path:
    sys.path.insert(0, _PY)
_cached = sys.modules.get("synapse")
if _cached is not None and getattr(_cached, "__file__", None) is None:
    for _m in [k for k in list(sys.modules)
               if k == "synapse" or k.startswith("synapse.")]:
        del sys.modules[_m]

from synapse.panel.session_integrity import SessionIntegrityTracker


def _block(fidelity=1.0):
    return {"operation": "create_node", "fidelity": fidelity}


def test_summary_no_data_is_not_a_pass():
    """total == 0 → has_data False, verified 0, fidelity 1.0 (clean but NOT a
    claim of success — has_data is the guard the widget reads)."""
    s = SessionIntegrityTracker().summary()
    assert s["total"] == 0
    assert s["verified"] == 0
    assert s["violations"] == 0
    assert s["has_data"] is False
    assert s["should_warn"] is False
    # fidelity reads a clean 1.0 at total==0 — exactly why has_data must exist
    assert s["fidelity"] == 1.0


def test_summary_all_clear():
    """Two clean ops → has_data True, verified == total, full fidelity, no
    warning. This is the ONLY state that may render green."""
    tr = SessionIntegrityTracker()
    tr.record(_block(1.0))
    tr.record(_block(1.0))
    s = tr.summary()
    assert s["total"] == 2
    assert s["verified"] == 2
    assert s["violations"] == 0
    assert s["fidelity"] == 1.0
    assert s["has_data"] is True
    assert s["should_warn"] is False


def test_summary_single_violation():
    """One sub-1.0 block → violations 1, fidelity < 1.0, has_data True, but
    should_warn still False (under the 3-violation threshold)."""
    tr = SessionIntegrityTracker()
    tr.record(_block(1.0))
    tr.record(_block(0.5))
    s = tr.summary()
    assert s["total"] == 2
    assert s["violations"] == 1
    assert s["verified"] == 1
    assert s["fidelity"] < 1.0
    assert s["has_data"] is True
    assert s["should_warn"] is False


def test_summary_three_violations_should_warn():
    """3 violations → should_warn True (the red/NO_SOFT escalation threshold)."""
    tr = SessionIntegrityTracker()
    for _ in range(3):
        tr.record(_block(0.0))
    s = tr.summary()
    assert s["total"] == 3
    assert s["violations"] == 3
    assert s["verified"] == 0
    assert s["has_data"] is True
    assert s["should_warn"] is True
    assert s["fidelity"] < 1.0
