"""R.2 — the panel no longer OWNS the freeze beat.

The v9 panel used to run a 1s QTimer parented to the widget that beat the
process-wide freeze chain. Closing the panel killed that timer (and the
runtime's only heartbeat); the old closeEvent then shut the whole chain down —
trading the R310a zombie for zero freeze protection after close (g5 lifecycle
fail, 2026-08-16).

R.2 moves the beat to a process-lifetime owner (server/runtime_beat.py). These
pins verify the panel SOURCE reflects the new contract: it no longer constructs
the widget-parented timer (machine-gate leg 1), it asks the owner to start the
beat, and closeEvent performs a DELIBERATE detach instead of a chain shutdown.
Source pins (no QApplication needed) — the house pattern for GUI-lifecycle code
whose Qt tests skip on stock CPython.

SELF-SUFFICIENT (Q1/D1): supplies its own Qt stub inside a scoped, self-
restoring window (``tests/qt_stub_window``) that plants nothing when real
PySide6 is present, so it collects on both interpreters, alone.
"""

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qt_stub_window import qt_stub_window  # noqa: E402

with qt_stub_window():
    from synapse.panel.synapse_panel import SynapsePanel  # noqa: E402


def _panel_src():
    return inspect.getsource(SynapsePanel)


def test_panel_does_not_construct_a_widget_parented_beat_timer():
    # Machine-gate leg 1 (harness/verify/checks.py::check_runtime_owns_heartbeat):
    # this exact literal must be gone, and no _freeze_timer may remain.
    src = _panel_src()
    assert "self._freeze_timer = QTimer(self)" not in src
    assert "_freeze_timer" not in src
    assert "_beat_freeze_chain" not in src


def test_panel_starts_the_process_lifetime_beat_owner():
    # Construction hands the beat to the process-lifetime owner.
    assert "ensure_beat_started" in _panel_src()


def test_closeEvent_deliberately_detaches_and_never_shuts_the_chain_down():
    src = _panel_src()
    start = src.find("def closeEvent")
    assert start != -1, "synapse_panel.closeEvent no longer exists"
    import re
    m = re.search(r"\n    def \w+", src[start + 10:])
    body = src[start:start + 10 + (m.start() if m else len(src))]
    assert "detach_panel" in body, (
        "closeEvent must perform the deliberate beat-source detach "
        "(runtime_beat.detach_panel)")
    assert "shutdown_freeze_chain" not in body, (
        "closeEvent must NOT shut the process-wide chain down — R.2 keeps the "
        "process-lifetime beat alive so the chain is never left unbeaten")
