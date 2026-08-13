"""W1-MTFIX — pins for the in-lane main-thread-stall changes.

Constitution Law 1: every check must be able to fail, and the failing condition is
stated per test. Negative controls are paired with positive ones — an UNKNOWN
detector with no known control passes vacuously, the defect this repo has paid for
repeatedly.

Scope note. This leg's larger targets landed as spawn proposals, not code:
  * doctor-off-main was REVERTED after adversarial review found a transitive crash
    path (store._resolve_project_path calls hou.* off-main, unmarshalled) — see the
    receipt's findings/spawn. So there is nothing here to pin for it.
  * append/finalize off-main formatting needs the blocked synapse_panel.py worker.

What DID land, and is pinned here:
  D. result-path / doctor-hold timing reports UNKNOWN off-GUI, never a 0.0-as-pass
     (the acceptance's headless contract).
  E. the chat document exposes the O(document) bound lever (set_max_result_blocks).

Section D is pure Python (no Qt, no hou) and runs everywhere. Section E needs real
PySide and skips cleanly on stock-Python CI, exactly like the sibling panel tests.
"""

import os
import sys
import types

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ===========================================================================
# D. Headless timing reports UNKNOWN, never a 0.0-as-pass
# ===========================================================================

from synapse.panel import result_telemetry as rt  # noqa: E402


def test_gui_timing_is_evidence_none_without_hou(monkeypatch):
    """FAILS IF: the gate claims GUI evidence with no hou present.

    No hou at all → None (GUI timing is not even defined). hou is forced absent so
    a leaked stub cannot flip the verdict.
    """
    monkeypatch.setitem(sys.modules, "hou", None)
    assert rt.gui_timing_is_evidence() is None


def test_gui_metric_verdict_headless_is_unknown_not_zero(monkeypatch):
    """FAILS IF: a headless reading is reported as its raw number.

    THE bug class this leg guards: a headless 0.0 read as 'fast/fixed'. Off-GUI the
    verdict is the string UNKNOWN whatever the number, so nobody claims an
    improvement from a session that could not measure one.
    """
    monkeypatch.setitem(sys.modules, "hou", None)
    assert rt.gui_metric_verdict(0.0) == "UNKNOWN"
    assert rt.gui_metric_verdict(648.0) == "UNKNOWN"


def test_gui_metric_verdict_gui_returns_value_NEGATIVE_CONTROL(monkeypatch):
    """FAILS IF: a GUI session's real value is masked as UNKNOWN.

    Pairs with the headless test: in a GUI session the number IS evidence and must
    pass through — including a genuine 0.0 (a phase that really ran fast).
    """
    monkeypatch.setattr(rt, "gui_timing_is_evidence", lambda: True)
    assert rt.gui_metric_verdict(0.0) == 0.0
    assert rt.gui_metric_verdict(648.0) == 648.0


def test_result_evidence_verdict_headless_marks_gui_phases_unknown(monkeypatch):
    """FAILS IF: append/finalize report a number off-GUI, or lose their count."""
    monkeypatch.setitem(sys.modules, "hou", None)
    stats = {p: dict(rt._blank()) for p in rt.PHASES}
    stats["append"]["max_ms"] = 648.0
    stats["append"]["count"] = 3
    stats["finalize"]["max_ms"] = 780.0
    verdict = rt.result_evidence_verdict(stats)
    assert verdict["append"]["max_ms"] == "UNKNOWN"
    assert verdict["append"]["gui_evidence"] is False
    assert verdict["append"]["count"] == 3          # context passes through
    assert verdict["finalize"]["max_ms"] == "UNKNOWN"


def test_result_evidence_verdict_gui_returns_real_values(monkeypatch):
    """FAILS IF: a GUI session's append/finalize numbers are hidden."""
    monkeypatch.setattr(rt, "gui_timing_is_evidence", lambda: True)
    stats = {p: dict(rt._blank()) for p in rt.PHASES}
    stats["append"]["max_ms"] = 42.0
    stats["finalize"]["max_ms"] = 90.0
    verdict = rt.result_evidence_verdict(stats)
    assert verdict["append"]["max_ms"] == 42.0
    assert verdict["append"]["gui_evidence"] is True
    assert verdict["finalize"]["max_ms"] == 90.0


def test_result_telemetry_import_pulls_no_hou():
    """FAILS IF: the new GUI gate broke the zero-hou-at-import property.

    Load-bearing: the headless server imports these accessors. The gate's hou
    import must be lazy, inside the function — importing the module must pull no
    hou. Runs in a clean subprocess so the check is about THIS module, not the
    suite's import history.
    """
    import subprocess
    import textwrap
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    probe = textwrap.dedent(
        """
        import sys
        import synapse.panel.result_telemetry as rt
        assert rt.GUI_REQUIRED_PHASES, 'module did not initialise'
        print('HOU=' + ('yes' if 'hou' in sys.modules else 'no'))
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=str(repo),
        env={**os.environ, "PYTHONPATH": str(repo / "python")},
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, "probe failed:\n%s\n%s" % (proc.stdout, proc.stderr)
    assert "HOU=no" in proc.stdout, \
        "result_telemetry pulled hou at import:\n%s" % proc.stdout


# ===========================================================================
# E. chat_display exposes the O(document) bound lever
# ===========================================================================
#
# Real PySide only — a MagicMock Qt stub would let these pass without a real
# QTextDocument. Skips on stock-Python CI, runs under hython, exactly like the
# sibling panel tests.

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("hou", types.ModuleType("hou"))  # chat_display need not use it

try:
    from PySide6 import QtWidgets as _QtWidgets
    _HAVE_QT = True
except ImportError:  # pragma: no cover
    try:
        from PySide2 import QtWidgets as _QtWidgets
        _HAVE_QT = True
    except ImportError:
        _HAVE_QT = False

if _HAVE_QT:
    try:
        _qapp_type = getattr(_QtWidgets, "QApplication", None)
        if not (isinstance(_qapp_type, type)
                and "PySide" in getattr(_qapp_type, "__module__", "")):
            _HAVE_QT = False
    except Exception:  # pragma: no cover
        _HAVE_QT = False

_needs_qt = pytest.mark.skipif(not _HAVE_QT, reason="PySide unavailable — run via hython")

_APP = None


def _chat():
    global _APP
    if _APP is None:
        _APP = _QtWidgets.QApplication.instance() or _QtWidgets.QApplication([])
    from synapse.panel.chat_display import ChatDisplay
    return ChatDisplay()


@_needs_qt
def test_max_result_blocks_default_is_unlimited():
    """FAILS IF: construction silently caps the document.

    Default must be unlimited (0) — trimming is a content decision this leg does
    not make, so a fresh ChatDisplay must retain everything (no result-content
    regression). Verified against a live QTextBrowser: bare default is 0.
    """
    cd = _chat()
    assert cd.document().maximumBlockCount() == 0


@_needs_qt
def test_set_max_result_blocks_bounds_and_restores():
    """FAILS IF: the O(document) lever does not set / clear the Qt bound.

    setMaximumBlockCount(5) → maximumBlockCount() == 5 was confirmed on the live
    H22.0.400 PySide6 before wiring; non-positive restores unlimited (0).
    """
    cd = _chat()
    cd.set_max_result_blocks(5)
    assert cd.document().maximumBlockCount() == 5
    cd.set_max_result_blocks(0)          # restore unlimited
    assert cd.document().maximumBlockCount() == 0
    cd.set_max_result_blocks(-1)         # non-positive → unlimited too
    assert cd.document().maximumBlockCount() == 0
