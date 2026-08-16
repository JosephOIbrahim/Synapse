"""W5-PANEL item 3 — the Token tab per-task token spend, from a real usage source.

Three layers, most of them pure:

  1. usage_sink (PURE, always runs): per-task accumulation + the R162 honesty
     rules — a field the API never reported stays None (UNKNOWN, never zero), a
     bool is never a token count, a real measured 0 is kept, begin_task resets.
  2. worker wiring (Qt-gated): the real ClaudeWorker conversation loop folds each
     stream() call's provider.last_usage into the sink across the whole tool loop.
  3. FaceToken mapping (Qt-gated): refresh_from_probe reads the sink and lands
     cache_read -> CACHE prefix, cache_creation -> CACHE last-turn, model -> ENGINE,
     with UNKNOWN everywhere the usage is absent (no task, or a non-Anthropic engine).

The Qt layers run under hython (real PySide6 + hou); they skip in stock-Python CI.
The honesty rules that make the counter trustworthy are all in layer 1 and run
everywhere.
"""
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

from synapse.panel.usage_sink import UsageSink, USAGE_SINK


# ----------------------------------------------------------------------
# Layer 1 — the sink (pure, always runs)
# ----------------------------------------------------------------------

def _full(**over):
    u = {"input_tokens": 100, "output_tokens": 20,
         "cache_read_input_tokens": 30, "cache_creation_input_tokens": 5}
    u.update(over)
    return u


def test_fresh_sink_snapshots_none():
    s = UsageSink()
    assert s.snapshot() is None


def test_begun_but_unfed_reports_model_and_all_unknown():
    s = UsageSink()
    s.begin_task("claude-x")
    snap = s.snapshot()
    assert snap is not None
    assert snap["model"] == "claude-x"
    assert snap["runs"] == 0
    # nothing measured yet -> every spend field UNKNOWN (None), never 0
    for k in ("input_tokens", "output_tokens", "cache_read", "cache_creation"):
        assert snap[k] is None, k


def test_single_call_lands_real_fields():
    s = UsageSink()
    s.begin_task("claude-x")
    s.add(_full())
    snap = s.snapshot()
    assert snap["runs"] == 1
    assert snap["input_tokens"] == 100
    assert snap["output_tokens"] == 20
    assert snap["cache_read"] == 30
    assert snap["cache_creation"] == 5


def test_per_task_accumulates_across_calls():
    # The unit is a TASK: last_usage resets each stream(), so per-task spend is
    # the SUM across the tool loop.
    s = UsageSink()
    s.begin_task("claude-x")
    s.add(_full(input_tokens=100, output_tokens=20,
                cache_read_input_tokens=30, cache_creation_input_tokens=5))
    s.add(_full(input_tokens=80, output_tokens=40,
                cache_read_input_tokens=7, cache_creation_input_tokens=0))
    snap = s.snapshot()
    assert snap["runs"] == 2
    assert snap["input_tokens"] == 180
    assert snap["output_tokens"] == 60
    assert snap["cache_read"] == 37
    assert snap["cache_creation"] == 5      # 5 + 0


def test_none_usage_counts_the_run_but_invents_nothing():
    # A non-Anthropic provider (or an aborted stream) reports no usage: the run is
    # counted, but no field is fabricated -> stays UNKNOWN, not a fake zero.
    s = UsageSink()
    s.begin_task("gemini-x")
    s.add(None)
    s.add(None)
    snap = s.snapshot()
    assert snap["model"] == "gemini-x"
    assert snap["runs"] == 2
    for k in ("input_tokens", "output_tokens", "cache_read", "cache_creation"):
        assert snap[k] is None, k


def test_bool_is_never_a_token_count():
    # bool is an int subclass; it must never be mistaken for a count (matches the
    # provider _merge_usage guard).
    s = UsageSink()
    s.begin_task("claude-x")
    s.add({"input_tokens": True, "output_tokens": False,
           "cache_read_input_tokens": 12})
    snap = s.snapshot()
    assert snap["input_tokens"] is None
    assert snap["output_tokens"] is None
    assert snap["cache_read"] == 12         # the only genuine int folded


def test_a_real_measured_zero_is_kept_not_hidden():
    # A zero the API actually REPORTED is a real claim (a cache miss), distinct
    # from "never measured". It is kept as 0; only never-measured is None.
    s = UsageSink()
    s.begin_task("claude-x")
    s.add({"cache_read_input_tokens": 0})
    snap = s.snapshot()
    assert snap["cache_read"] == 0
    assert snap["cache_creation"] is None   # this one truly was never measured


def test_begin_task_resets_previous_totals():
    s = UsageSink()
    s.begin_task("claude-x")
    s.add(_full())
    s.begin_task("claude-y")                # new task, new receipt
    snap = s.snapshot()
    assert snap["model"] == "claude-y"
    assert snap["runs"] == 0
    for k in ("input_tokens", "output_tokens", "cache_read", "cache_creation"):
        assert snap[k] is None, k


def test_clear_returns_to_none():
    s = UsageSink()
    s.begin_task("claude-x")
    s.add(_full())
    s.clear()
    assert s.snapshot() is None


def test_add_before_begin_is_defensive_not_lossy():
    # A call before begin_task opens implicitly rather than dropping the receipt.
    s = UsageSink()
    s.add(_full(input_tokens=42))
    snap = s.snapshot()
    assert snap is not None
    assert snap["input_tokens"] == 42


# ----------------------------------------------------------------------
# Qt-gated layers — worker wiring + FaceToken mapping (run under hython)
# ----------------------------------------------------------------------

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("hou", types.ModuleType("hou"))

try:
    from PySide6 import QtWidgets  # noqa: F401
    _HAVE_QT = True
except ImportError:
    try:
        from PySide2 import QtWidgets  # noqa: F401
        _HAVE_QT = True
    except ImportError:
        _HAVE_QT = False

if _HAVE_QT:
    try:
        _qapp = getattr(QtWidgets, "QApplication", None)
        if not (isinstance(_qapp, type) and "PySide" in getattr(_qapp, "__module__", "")):
            _HAVE_QT = False
    except Exception:
        _HAVE_QT = False

_qt = pytest.mark.skipif(not _HAVE_QT, reason="PySide unavailable — run via hython")

_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


class _FakeProvider:
    """Two stream() calls in one task, each publishing real usage — the multi-call
    accumulation the worker must fold. First returns tool_use with NO tool blocks
    (loops without any tool dispatch), second ends the turn."""
    model_identity = "claude-fake-2call"

    def __init__(self):
        self.last_usage = None
        self._n = 0

    def resolve_key(self):
        return "key"

    def key_error_message(self):
        return "no key"

    def stream(self, **_kw):
        self._n += 1
        if self._n == 1:
            self.last_usage = {"input_tokens": 100, "output_tokens": 20,
                               "cache_read_input_tokens": 5,
                               "cache_creation_input_tokens": 2}
            return ("tool_use", [])         # no tool_use blocks -> loops, no dispatch
        self.last_usage = {"input_tokens": 80, "output_tokens": 40,
                           "cache_read_input_tokens": 7,
                           "cache_creation_input_tokens": 0}
        return ("end_turn", [])


@_qt
def test_worker_loop_folds_per_task_spend_into_the_sink():
    _app()
    from synapse.panel.claude_worker import ClaudeWorker
    USAGE_SINK.clear()
    worker = ClaudeWorker([{"role": "user", "content": "hi"}],
                          tools=[], provider=_FakeProvider())
    worker._conversation_loop("key")
    snap = USAGE_SINK.snapshot()
    assert snap is not None
    assert snap["model"] == "claude-fake-2call"     # the SELECTED model
    assert snap["runs"] == 2
    assert snap["input_tokens"] == 180              # summed across the tool loop
    assert snap["output_tokens"] == 60
    assert snap["cache_read"] == 12
    assert snap["cache_creation"] == 2
    USAGE_SINK.clear()


@_qt
def test_face_token_shows_real_cache_and_selected_model():
    _app()
    from synapse.panel.face_token import FaceToken, UNKNOWN
    USAGE_SINK.clear()
    USAGE_SINK.begin_task("claude-face-model")
    USAGE_SINK.add({"cache_read_input_tokens": 123,
                    "cache_creation_input_tokens": 45,
                    "input_tokens": 1, "output_tokens": 2})
    face = FaceToken()
    face.refresh_from_probe()
    assert face._rows["prefix"].text() == "123"         # real cache_read receipt
    assert face._rows["last turn"].text() == "45"       # real cache_creation receipt
    assert face._rows["model"].text() == "claude-face-model"
    USAGE_SINK.clear()


@_qt
def test_face_token_unknown_when_no_task_ran():
    _app()
    from synapse.panel.face_token import FaceToken, UNKNOWN
    USAGE_SINK.clear()                                   # no task at all
    face = FaceToken()
    face.refresh_from_probe()
    assert face._rows["prefix"].text() == UNKNOWN
    assert face._rows["last turn"].text() == UNKNOWN


@_qt
def test_face_token_unknown_spend_for_non_anthropic_engine():
    _app()
    from synapse.panel.face_token import FaceToken, UNKNOWN
    USAGE_SINK.clear()
    USAGE_SINK.begin_task("gemini-2.5")                  # engine that reports no usage
    USAGE_SINK.add(None)
    face = FaceToken()
    face.refresh_from_probe()
    # spend is unmeasurable -> UNKNOWN, never a fake zero; the selected model still shows
    assert face._rows["prefix"].text() == UNKNOWN
    assert face._rows["last turn"].text() == UNKNOWN
    assert face._rows["model"].text() == "gemini-2.5"
    USAGE_SINK.clear()
