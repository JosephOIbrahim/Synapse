"""FRZ — pins for the result-path main-thread instrument.

Constitution Law 1: every check must be able to fail, and the failing condition is
stated per test. The negative controls are not decoration — a slow-detector with no
fast-path control passes vacuously, which is exactly the defect this repo has paid
for four times (AGENT_CONSTITUTION.md Article III, Law 1).

These are pure-Python: the module under test is zero-Qt and zero-``hou`` by
construction, and that property is itself pinned below.
"""

import os
import sys
import threading

import pytest

from synapse.panel import result_telemetry as rt


@pytest.fixture(autouse=True)
def _clean():
    rt.reset_result_render_stats()
    yield
    rt.reset_result_render_stats()


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

def test_main_thread_sample_is_recorded():
    """FAILS IF: a main-thread phase does not land in the main counters."""
    rt.record_result_phase("append", 12.5, payload_chars=100, doc_chars=2000,
                           on_main=True)
    slot = rt.result_render_stats()["append"]
    assert slot["count"] == 1
    assert slot["sum_ms"] == pytest.approx(12.5)
    assert slot["max_ms"] == pytest.approx(12.5)
    assert slot["max_payload_chars"] == 100
    assert slot["max_doc_chars"] == 2000


def test_offmain_sample_never_pollutes_main_counters():
    """FAILS IF: an off-main sample is folded into main-thread hold time.

    This is the exact corruption that invalidated the 2026-07-31 tool-attribution
    numbers — off-main wall-time recorded as main-thread time sends the next
    investigator at the wrong mechanism.
    """
    rt.record_result_phase("stream", 900.0, on_main=False)
    slot = rt.result_render_stats()["stream"]
    assert slot["count"] == 0
    assert slot["sum_ms"] == 0.0
    assert slot["max_ms"] == 0.0
    assert slot["slow_count"] == 0
    assert slot["offmain_count"] == 1
    assert slot["offmain_max_ms"] == pytest.approx(900.0)


def test_thread_identity_is_measured_not_assumed():
    """FAILS IF: on_main defaults to True instead of being measured.

    A worker thread recording without an explicit flag must be attributed
    off-main. Passing a proxy flag is banned by convention; the default path
    must therefore do a real identity check.
    """
    done = threading.Event()

    def _worker():
        rt.record_result_phase("finalize", 50.0)  # no on_main= → must measure
        done.set()

    t = threading.Thread(target=_worker)
    t.start()
    assert done.wait(5.0)
    t.join(5.0)

    slot = rt.result_render_stats()["finalize"]
    assert slot["count"] == 0, "worker-thread sample was attributed to MAIN"
    assert slot["offmain_count"] == 1


def test_unknown_phase_is_dropped_not_invented():
    """FAILS IF: a typo'd phase silently creates a new series."""
    rt.record_result_phase("not_a_phase", 999.0, on_main=True)
    stats = rt.result_render_stats()
    assert "not_a_phase" not in stats
    assert set(stats) == set(rt.PHASES)


# ---------------------------------------------------------------------------
# The slow threshold — with its negative control
# ---------------------------------------------------------------------------

def test_slow_phase_is_counted_slow():
    """FAILS IF: a phase over PANEL_RESULT_SLOW_MS is not flagged."""
    rt.record_result_phase("append", rt.PANEL_RESULT_SLOW_MS + 1.0, on_main=True)
    assert rt.result_render_stats()["append"]["slow_count"] == 1


def test_fast_phase_is_not_counted_slow_NEGATIVE_CONTROL():
    """FAILS IF: slow_count increments for a fast phase.

    Without this control the test above passes even if slow_count were
    incremented unconditionally — i.e. the check could not fail.
    """
    rt.record_result_phase("append", rt.PANEL_RESULT_SLOW_MS - 1.0, on_main=True)
    slot = rt.result_render_stats()["append"]
    assert slot["count"] == 1, "the fast sample must still be recorded"
    assert slot["slow_count"] == 0


def test_max_carries_the_sizes_of_the_worst_sample():
    """FAILS IF: payload/doc size at max is not the size of the SLOWEST sample.

    A duration without the payload that produced it is a number; with it, it is a
    scaling law. Pinning that the pairing tracks max_ms (not last-write) is what
    makes the sample readable.
    """
    rt.record_result_phase("append", 10.0, payload_chars=5, doc_chars=7, on_main=True)
    rt.record_result_phase("append", 90.0, payload_chars=500, doc_chars=700, on_main=True)
    rt.record_result_phase("append", 20.0, payload_chars=9, doc_chars=11, on_main=True)
    slot = rt.result_render_stats()["append"]
    assert slot["max_ms"] == pytest.approx(90.0)
    assert slot["payload_chars_at_max_ms"] == 500
    assert slot["doc_chars_at_max_ms"] == 700


# ---------------------------------------------------------------------------
# timed_phase — the context manager must not change behaviour
# ---------------------------------------------------------------------------

def test_timed_phase_records_and_returns_handle():
    """FAILS IF: the context manager does not record on exit."""
    with rt.timed_phase("review") as h:
        h.set_sizes(payload_chars=42)
    slot = rt.result_render_stats()["review"]
    assert slot["count"] == 1
    assert slot["max_payload_chars"] == 42


def test_timed_phase_records_then_reraises():
    """FAILS IF: the instrument swallows an exception (a behaviour change) OR
    fails to record a phase that raised.

    A phase that blew up still occupied the main thread for however long it ran.
    Both halves matter: suppressing would alter control flow, and not recording
    would hide real hold time.
    """
    with pytest.raises(ValueError, match="boom"):
        with rt.timed_phase("finalize"):
            raise ValueError("boom")
    assert rt.result_render_stats()["finalize"]["count"] == 1


def test_stats_snapshot_is_a_copy():
    """FAILS IF: a caller can mutate live counters through the snapshot."""
    rt.record_result_phase("send", 5.0, on_main=True)
    snap = rt.result_render_stats()
    snap["send"]["count"] = 9999
    assert rt.result_render_stats()["send"]["count"] == 1


def test_telemetry_never_raises_on_bad_input():
    """FAILS IF: a telemetry path propagates an exception to its caller."""
    rt.record_result_phase("send", "not-a-number", on_main=True)  # must not raise
    rt.record_result_phase(None, 5.0, on_main=True)               # must not raise


# ---------------------------------------------------------------------------
# Structural properties the wiring depends on
# ---------------------------------------------------------------------------

def test_module_imports_without_qt():
    """FAILS IF: importing the accessor pulls in Qt.

    Load-bearing: handlers.py and telemetry_dump.py import this from the SERVER
    side. ``tool_executor.panel_inline_stats`` degrades to None in a headless
    server precisely because its import pulls Qt; this instrument must not repeat
    that, or the freeze dump loses the Qt-side numbers exactly when a headless
    post-mortem needs them.

    Runs in a CLEAN SUBPROCESS on purpose. Asserting "no Qt in sys.modules" from
    inside the suite tests the whole session's import history, not this module —
    it passes in isolation and fails once any earlier test imports Qt, which is a
    check that fails for the wrong reason. The subprocess asserts the property
    that is actually claimed: importing THIS module, alone, pulls no Qt.
    """
    import subprocess
    import textwrap
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    probe = textwrap.dedent(
        """
        import sys
        import synapse.panel.result_telemetry as rt
        qt = sorted(m for m in sys.modules
                    if m.split('.')[0] in ('PySide2', 'PySide6', 'PyQt5', 'PyQt6'))
        assert rt.PHASES, 'module did not initialise'
        print('QT=' + ','.join(qt))
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=str(repo),
        env={**os.environ, "PYTHONPATH": str(repo / "python")},
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, "probe failed:\n%s\n%s" % (proc.stdout, proc.stderr)
    line = [l for l in proc.stdout.splitlines() if l.startswith("QT=")]
    assert line, "probe produced no verdict:\n%s\n%s" % (proc.stdout, proc.stderr)
    pulled = line[-1][3:].strip()
    assert not pulled, "result_telemetry pulled Qt into a clean interpreter: %s" % pulled


def test_phase_set_is_bounded():
    """FAILS IF: the phase set grows at runtime (an unbounded telemetry surface)."""
    before = set(rt.result_render_stats())
    for i in range(50):
        rt.record_result_phase("phase_%d" % i, 1.0, on_main=True)
    assert set(rt.result_render_stats()) == before


def test_reset_zeroes_every_phase():
    """FAILS IF: reset leaves residue in any phase."""
    for p in rt.PHASES:
        rt.record_result_phase(p, 10.0, payload_chars=3, doc_chars=4, on_main=True)
    rt.reset_result_render_stats()
    for p, slot in rt.result_render_stats().items():
        assert slot == rt._blank(), "phase %r not reset" % p


# ---------------------------------------------------------------------------
# Wiring — the instrument must be READABLE, or it is write-only decoration
# ---------------------------------------------------------------------------

def test_telemetry_dump_carries_the_freeze_attribution_sections():
    """FAILS IF: a freeze dump omits any of the three surfaces a post-mortem needs.

    main_thread_hold is the ONE instrument that can see a deferred-path hold;
    marshal_guard records whether the guard was armed; panel_result_render is the
    Qt half. All three were absent from collect_telemetry() before this leg.
    """
    from synapse.server.telemetry_dump import collect_telemetry
    out = collect_telemetry()
    for key in ("main_thread_hold", "marshal_guard", "panel_result_render"):
        assert key in out, "collect_telemetry() lost %r" % key
    assert isinstance(out["panel_result_render"], dict)
    assert set(out["panel_result_render"]) == set(rt.PHASES)


def test_prometheus_exports_result_phases_even_at_zero():
    """FAILS IF: the series vanishes when no sample has been taken.

    An absent series is indistinguishable from a dead recorder. This instrument
    exists to let a reader conclude "the result path was NOT where the time went",
    and that conclusion requires a visible zero.
    """
    from synapse.server.metrics import render_prometheus
    text = render_prometheus(panel_results=rt.result_render_stats())
    assert "synapse_panel_result_ms_count" in text
    for p in rt.PHASES:
        assert 'phase="%s"' % p in text
    assert 'synapse_panel_result_ms_count{phase="append"} 0' in text


def test_prometheus_reports_a_real_sample():
    """FAILS IF: a recorded sample does not reach the exposition text."""
    from synapse.server.metrics import render_prometheus
    rt.record_result_phase("append", 6000.0, payload_chars=10, doc_chars=123456,
                           on_main=True)
    text = render_prometheus(panel_results=rt.result_render_stats())
    assert 'synapse_panel_result_ms_count{phase="append"} 1' in text
    assert 'synapse_panel_result_slow_total{phase="append"} 1' in text
    assert 'synapse_panel_result_doc_chars_at_max{phase="append"} 123456' in text


def test_overbudget_phase_reaches_the_marshal_guard_ledger():
    """FAILS IF: a Qt-side hold past the inline budget does not land in the
    ledger a freeze post-mortem already reads.

    Reusing marshal_guard's sink rather than adding a parallel one is the whole
    point — a second ledger would split the evidence.
    """
    from synapse.server import marshal_guard as mg
    mg.reset_guard_state()
    before = mg.guard_stats()["inline_overruns"]
    over_ms = (mg.inline_budget_s() + 1.0) * 1000.0
    rt.record_result_phase("finalize", over_ms, payload_chars=1, doc_chars=2,
                           on_main=True)
    assert mg.guard_stats()["inline_overruns"] == before + 1
    wheres = [e.get("where") for e in mg.guard_events(20)]
    assert "panel.result_telemetry:finalize" in wheres


def test_underbudget_phase_does_not_reach_the_ledger_NEGATIVE_CONTROL():
    """FAILS IF: every slow phase escalates to the ledger.

    Without this the test above passes even if the sink were called
    unconditionally. Slow (>250ms, a hitch) and over-budget (>5s, the freeze) are
    two different questions and must stay distinguishable.
    """
    from synapse.server import marshal_guard as mg
    mg.reset_guard_state()
    before = mg.guard_stats()["inline_overruns"]
    rt.record_result_phase("finalize", rt.PANEL_RESULT_SLOW_MS + 1.0, on_main=True)
    assert rt.result_render_stats()["finalize"]["slow_count"] == 1
    assert mg.guard_stats()["inline_overruns"] == before
