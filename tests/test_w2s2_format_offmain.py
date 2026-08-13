"""W2-S2 (F4) — format_synapse_message off the Qt main thread.

The F4 design (W1-MTFIX spawn S2): decide grouping on main (cheap), run the pure
formatter (``format_synapse_message`` — zero Qt, zero hou) on a WORKER thread, hand a
prerendered HTML STRING back to main, insert there. Only ``insertHtml`` (and grouping)
stay on the Qt thread. Ordering is preserved across a burst of results.

Constitution Law 1: every check can fail, and the failing condition is stated per
test. Positive checks are paired with negative controls — an off-main assertion that
never had a way to observe "ran on main" passes vacuously.

Two tiers, exactly like the sibling W1-MTFIX tests:

  * Section A — PURE. The async_format pipeline + the formatter boundary. Zero Qt,
    zero hou; runs everywhere (stock-Python CI included). This tier carries the
    LOAD-BEARING off-main + ordering + byte-equal proofs, because the ChatDisplay
    integration below skips without PySide.
  * Section B — INTEGRATION. Drives the real ChatDisplay under offscreen PySide;
    proves the widget formats off-main, inserts on-main, keeps order, and does NOT
    change the trimming default. Skips on stock Python, runs under hython — exactly
    like the sibling panel tests.
"""

import os
import sys
import threading
import time
import types

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ===========================================================================
# Section A — PURE: async_format pipeline + formatter boundary (no Qt, no hou)
# ===========================================================================

from synapse.panel.async_format import OrderedAsyncFormatter, FormatJob  # noqa: E402
from synapse.panel import message_formatter as mf  # noqa: E402


def _mk(idx, html="<x>", delay=0.0, record=None, boom=False):
    """A FormatJob whose render records the thread it ran on (record list) and,
    optionally, sleeps `delay` s or raises."""
    def render():
        if delay:
            time.sleep(delay)
        if record is not None:
            record.append((idx, threading.get_ident()))
        if boom:
            raise RuntimeError("render boom %d" % idx)
        return "%s-%d" % (html, idx)
    return FormatJob(render=render, meta=idx)


def test_render_runs_off_the_submitting_thread():
    """FAILS IF: the formatter runs render() on the caller's thread.

    Acceptance #1, pure evidence: format executes on a WORKER thread. The negative
    control is the recorded thread ident — without it the assertion could not tell a
    main-thread run from an off-main one.
    """
    main_ident = threading.get_ident()
    assert main_ident == threading.main_thread().ident  # test runs on main
    rec = []
    f = OrderedAsyncFormatter()
    try:
        f.submit(_mk(0, record=rec))
        assert f.wait_idle(5.0), "job never rendered"
        jobs = f.drain()
    finally:
        f.stop()
    assert len(rec) == 1
    ran_idx, ran_ident = rec[0]
    assert ran_ident != main_ident, "render ran on the submitting (main) thread"
    assert ran_ident != threading.main_thread().ident
    assert jobs[0].thread_ident == ran_ident  # job records where it ran


def test_burst_ordering_is_submit_order_not_completion_order():
    """FAILS IF: a burst of completions surfaces out of submit order.

    Acceptance #4 + crucible #3: a REAL burst — five queued jobs whose render delays
    DECREASE (job 0 slowest, job 4 fastest). A completion-order pipeline (a thread
    pool) would surface 4,3,2,1,0; the single-consumer FIFO must surface 0..4. Both
    the drained order and the apply (insert) order are checked.
    """
    apply_order = []
    f = OrderedAsyncFormatter()
    try:
        for i in range(5):
            job = _mk(i, delay=0.04 * (5 - i))
            job.apply = lambda j: apply_order.append(j.meta)
            f.submit(job)
        assert f.wait_idle(10.0), "burst never drained"
        jobs = f.drain()
    finally:
        f.stop()
    assert [j.meta for j in jobs] == [0, 1, 2, 3, 4], "drain order not submit order"
    assert apply_order == [0, 1, 2, 3, 4], "insert (apply) order not submit order"


def test_worker_survives_a_render_exception_and_keeps_ordering():
    """FAILS IF: a formatter exception kills the worker or drops a later job.

    Negative control for robustness: job 1 raises. It must land with error set and
    html=="" (never None crossing to insertHtml), and jobs 0 and 2 must still render
    and stay in order — the worker thread does not die on a bad render.
    """
    f = OrderedAsyncFormatter()
    try:
        f.submit(_mk(0))
        f.submit(_mk(1, boom=True))
        f.submit(_mk(2))
        assert f.wait_idle(5.0)
        jobs = f.drain()
    finally:
        f.stop()
    assert [j.meta for j in jobs] == [0, 1, 2]
    assert jobs[1].error is not None and isinstance(jobs[1].error, RuntimeError)
    assert jobs[1].html == "", "a failed render must yield '' not None"
    assert jobs[0].html and jobs[2].html, "sibling jobs lost after an exception"


def test_wait_idle_and_pending_accounting():
    """FAILS IF: pending/idle accounting is wrong (would make the flush unreliable).

    Control for _flush_pending_formats: a fresh formatter is idle with 0 pending;
    after a slow submit it reports pending>0 and is not-idle; after wait_idle it is
    idle again with 0 pending.
    """
    f = OrderedAsyncFormatter()
    try:
        assert f.pending() == 0
        assert f.wait_idle(0.1) is True  # already idle
        f.submit(_mk(0, delay=0.2))
        assert f.pending() == 1
        assert f.wait_idle(5.0) is True
        assert f.pending() == 0
        f.drain()
    finally:
        f.stop()


# -- byte-equal (acceptance #3) ---------------------------------------------

# Fixtures exercise every formatter branch: plain str, dict+status, a node-path
# chip, inline+block code, list items, and the signed authorship note — each at
# grouped True and False.
_FIXTURES = [
    "just a plain sentence",
    {"message": "operation complete", "status": "success"},
    "created the light at /stage/lights and bound it",
    "run `hou.node` then:\n```vex\nfloat x = 1.0;\n```",
    "steps:\n- first\n- second\n- third",
    {"result": "see /obj/geo1 and /out/mantra1", "status": "warning"},
]


def _direct(fixture, grouped, signed):
    return mf.format_synapse_message(
        fixture, grouped=grouped, timestamp="1:23 PM",
        font_scale=1.0, signed=signed)


def test_pipeline_output_is_byte_equal_to_direct_format():
    """FAILS IF: routing the format through the async pipeline changes ONE byte.

    Acceptance #3: for every fixture, at grouped True/False and signed/None, the HTML
    the pipeline produces must be byte-identical to calling format_synapse_message
    directly — including grouped results. The pipeline is plumbing; it must not touch
    the bytes.
    """
    f = OrderedAsyncFormatter()
    try:
        for fixture in _FIXTURES:
            for grouped in (False, True):
                for signed in (None, "GLM 5.2"):
                    baseline = _direct(fixture, grouped, signed)
                    job = FormatJob(render=(lambda fx=fixture, g=grouped, s=signed:
                                            _direct(fx, g, s)))
                    f.submit(job)
                    assert f.wait_idle(5.0)
                    got = f.drain()[0]
                    assert got.error is None
                    assert got.html == baseline, (
                        "pipeline altered bytes for fixture=%r grouped=%s signed=%r"
                        % (fixture, grouped, signed))
    finally:
        f.stop()


def test_grouped_and_ungrouped_differ_NEGATIVE_CONTROL():
    """FAILS IF: grouped is ignored (then the byte-equal test above is vacuous).

    Guards the fixtures: a grouped message must differ from an ungrouped one (the
    ungrouped one carries the SYNAPSE speaker label the grouped one drops), so the
    byte-equal test is comparing a real, content-bearing surface.
    """
    ungrouped = _direct("hello world", grouped=False, signed=None)
    grouped = _direct("hello world", grouped=True, signed=None)
    assert ungrouped != grouped
    assert "SYNAPSE" in ungrouped and "SYNAPSE" not in grouped


def test_format_synapse_message_zero_qt_zero_hou_at_boundary():
    """FAILS IF: importing or CALLING format_synapse_message pulls hou or Qt.

    Acceptance #2 (guard test at the boundary). Runs in a clean subprocess so the
    verdict is about THIS function, not the suite's import history: it imports
    message_formatter, snapshots sys.modules, calls the function across the fixtures,
    and asserts NO hou / PySide / PyQt module was introduced by the import OR the
    call — the property that makes the formatter safe to run off the Qt thread.

    The teeth are the DELTA (modules introduced by the import/call), which is fully
    meaningful under stock Python where hou/Qt are absent — the normal dev/CI run.
    Under hython hou is pre-resident from interpreter startup (before this probe runs),
    so an absolute ``'hou' not in sys.modules`` check would false-fail there while
    proving nothing about the formatter; the delta stays correct in both.
    """
    import subprocess
    import textwrap
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    probe = textwrap.dedent(
        """
        import sys
        base = set(sys.modules)
        import synapse.panel.message_formatter as mf
        def bad(mods):
            return sorted(m for m in mods
                          if m == 'hou' or m.startswith('hou.')
                          or 'PySide' in m or 'PyQt' in m)
        imp = bad(set(sys.modules) - base)
        pre = set(sys.modules)
        for fx in ['x', {'message':'m','status':'success'}, 'see /obj/geo1',
                   '- a\\n- b', '```vex\\nfloat x=1;\\n```', {'result':'/stage/a'}]:
            for g in (False, True):
                mf.format_synapse_message(fx, grouped=g, timestamp='1:00 PM',
                                          font_scale=1.0, signed='GLM 5.2')
        call = bad(set(sys.modules) - pre)
        assert not imp, 'import pulled: %r' % imp
        assert not call, 'call pulled: %r' % call
        print('BOUNDARY_CLEAN')
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=str(repo),
        env={**os.environ, "PYTHONPATH": str(repo / "python")},
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, "probe failed:\n%s\n%s" % (proc.stdout, proc.stderr)
    assert "BOUNDARY_CLEAN" in proc.stdout, proc.stdout


# ===========================================================================
# Section B — INTEGRATION: the real ChatDisplay under offscreen PySide
# ===========================================================================
#
# Real PySide only — a MagicMock Qt stub would let these pass without a real
# QTextDocument / worker hand-off. Skips on stock-Python CI, runs under hython,
# exactly like the sibling panel tests (test_w1_mtfix.py Section E).

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


def _settle(cd, timeout=5.0):
    """Deterministically apply pending off-main formats on THIS (main) thread,
    without depending on a running Qt event loop: wait for the worker to finish
    rendering, then drain (which inserts on the calling thread). Mirrors what the
    queued _fmt_ready signal does in a live GUI session."""
    cd._fmt.wait_idle(timeout)
    cd._drain_fmt()


@_needs_qt
def test_chatdisplay_formats_off_main_and_inserts_on_main(monkeypatch):
    """FAILS IF: format_synapse_message runs on the Qt (main) thread for a panel
    result, or the prerendered HTML never reaches the document.

    Acceptance #1 at the integration seat. A spy wraps the formatter to record the
    thread it ran on; the append must run it OFF the main thread, and after settling
    the document must contain the reply text (proving the HTML crossed back and was
    inserted on main).
    """
    import synapse.panel.chat_display as cdmod
    main_ident = threading.get_ident()
    ran_on = {}
    real = cdmod.format_synapse_message

    def spy(*a, **k):
        ran_on["ident"] = threading.get_ident()
        return real(*a, **k)

    monkeypatch.setattr(cdmod, "format_synapse_message", spy)

    cd = _chat()
    cd.enable_off_main_format()          # the panel's F4 opt-in
    try:
        cd.append_synapse_message("off-main marker ZZZ")
        _settle(cd)
        assert "ident" in ran_on, "formatter never ran"
        assert ran_on["ident"] != main_ident, "formatter ran on the Qt main thread"
        assert "off-main marker ZZZ" in cd.toPlainText()
    finally:
        cd.shutdown()


@_needs_qt
def test_chatdisplay_burst_preserves_order():
    """FAILS IF: a rapid burst of appends lands out of order in the document.

    Acceptance #4 at the integration seat: five appends enqueued back-to-back must
    appear in submit order in the rendered document.
    """
    cd = _chat()
    cd.enable_off_main_format()          # the panel's F4 opt-in
    try:
        markers = ["AAA0", "BBB1", "CCC2", "DDD3", "EEE4"]
        for m in markers:
            cd.append_synapse_message(m)
        _settle(cd)
        text = cd.toPlainText()
        positions = [text.find(m) for m in markers]
        assert all(p >= 0 for p in positions), "a message went missing: %r" % positions
        assert positions == sorted(positions), "out of order: %r" % positions
    finally:
        cd.shutdown()


@_needs_qt
def test_chatdisplay_trimming_default_unchanged():
    """FAILS IF: this leg silently changes the trimming default.

    Crucible #2 / target #3: the whole-message trimming call (set_max_result_blocks)
    is Joe's UX decision, recorded as a finding — NOT enabled here. A fresh
    ChatDisplay must stay unlimited (maximumBlockCount == 0), and appending replies
    must not enable a cap.
    """
    cd = _chat()
    cd.enable_off_main_format()          # exercise the async path too
    try:
        assert cd.document().maximumBlockCount() == 0
        for i in range(3):
            cd.append_synapse_message("msg %d" % i)
        _settle(cd)
        assert cd.document().maximumBlockCount() == 0, "append changed the trim cap"
    finally:
        cd.shutdown()


@_needs_qt
def test_default_is_synchronous_no_settle_needed():
    """FAILS IF: the DEFAULT append_synapse_message stops inserting synchronously.

    The load-bearing floor guarantee: off-main is OFF by default, so a fresh
    ChatDisplay inserts the reply on the SAME call — no event loop, no settle. This is
    what keeps the existing panel tests (which read the document right after appending,
    including one in a peer-claimed file) green. If this fails, the default flipped and
    the synchronous contract broke.
    """
    cd = _chat()
    try:
        assert cd._async_format_enabled is False, "off-main must be OFF by default"
        cd.append_synapse_message("sync-by-default marker QQQ")
        # No settle, no event loop: the reply must already be in the document.
        assert "sync-by-default marker QQQ" in cd.toPlainText()
    finally:
        cd.shutdown()


@_needs_qt
def test_explicit_enable_then_disable_round_trips():
    """FAILS IF: the opt-in / opt-out toggle does not take effect.

    Negative control paired with the off-main test: enabling makes the insert deferred
    (empty until settled), disabling restores the synchronous insert. Proves the flag
    actually gates the two paths — the off-main assertion is not passing vacuously.
    """
    cd = _chat()
    try:
        cd.enable_off_main_format(True)
        cd.append_synapse_message("deferred marker DDD")
        # Deferred: not yet in the document (nothing settled it).
        assert "deferred marker DDD" not in cd.toPlainText()
        _settle(cd)
        assert "deferred marker DDD" in cd.toPlainText()
        cd.enable_off_main_format(False)
        cd.append_synapse_message("inline marker III")
        assert "inline marker III" in cd.toPlainText()  # synchronous again
    finally:
        cd.shutdown()


@_needs_qt
def test_user_message_flush_orders_before_pending_synapse():
    """FAILS IF: a user message can jump ahead of a still-formatting synapse reply.

    Cross-sender ordering: enqueue a synapse reply, then immediately append a user
    message. The flush at the top of append_user_message must land the synapse reply
    FIRST, so the document order is synapse-then-user (call order), never reversed.
    """
    cd = _chat()
    cd.enable_off_main_format()          # the panel's F4 opt-in
    try:
        cd.append_synapse_message("SYN_FIRST_marker")
        cd.append_user_message("USER_SECOND_marker")  # flushes pending synapse first
        text = cd.toPlainText()
        i_syn = text.find("SYN_FIRST_marker")
        i_usr = text.find("USER_SECOND_marker")
        assert i_syn >= 0 and i_usr >= 0
        assert i_syn < i_usr, "user message jumped ahead of the pending synapse reply"
    finally:
        cd.shutdown()
