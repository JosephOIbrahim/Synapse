"""D4 (2026-10-18): the sleep pass is refused unless the process opts in.

``synapse_sleep_pass`` permanently prunes unprotected memories. The APPROVE
class it carries on the bridge cannot block anything: the process bridge is
built auto-approve with its gate nulled (CLAUDE.md 1.2.1), and the panel
worker's fail-closed DENY covers the panel alone. So the handler is the choke
point. It runs only when the PROCESS ENVIRONMENT has SYNAPSE_ALLOW_SLEEP_PASS
set to exactly "1", and nothing in a request payload can opt in.

When it does run, the pass is called directly. It never enters
``bridge.execute()``, so there is no undo group and no ``performUndo`` that
could pop the artist's last edit (FM11). A pass that raises is answered
``ran=False`` with no retry and no fallback prune. A PyO3 panic is answered
the same way. Interpreter control flow propagates untouched. A pass that ran
leaves one observe-only IntegrityBlock in the process trail.

Hermetic: a fake store, a fake trail, and a bare MemoryHandlerMixin host. No
Moneta, no Houdini, no SynapseHandler, and no handle(), so no audit-log write.
"""

import asyncio
import logging
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))
sys.path.insert(0, str(_ROOT))

import shared.bridge as bridge_mod  # noqa: E402
from synapse.memory.native_panic import is_native_panic  # noqa: E402
from synapse.server import integrity_envelope  # noqa: E402
from synapse.server.handlers_memory import MemoryHandlerMixin  # noqa: E402

#: The opt-in is a contract with operators, so the tests spell it out instead
#: of importing a constant that could drift along with the code under test.
OPT_IN = "SYNAPSE_ALLOW_SLEEP_PASS"
HANDLER_LOGGER = "synapse.server.handlers_memory"

#: Shaped like the class PyO3 creates inside the extension: named
#: PanicException, module pyo3_runtime, derived from BaseException.
_PanicException = type("PanicException", (BaseException,), {"__module__": "pyo3_runtime"})


class _FakeStore:
    """Moneta-shaped enough for the handler: count() and run_sleep_pass()."""

    def __init__(self, raises=None, n=3, prune=1):
        self.calls = 0
        self._raises = raises
        self._n = n
        self._prune = prune

    def count(self):
        return self._n

    def run_sleep_pass(self):
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        self._n -= self._prune
        return SimpleNamespace(
            pruned=self._prune,
            pruned_ids=["m%d" % i for i in range(self._prune)],
            staged=0,
        )


class _Host(MemoryHandlerMixin):
    """The real _handle_sleep_pass on a host whose bridge holds one store."""

    def __init__(self, store):
        self._store = store

    def _get_bridge(self):
        return SimpleNamespace(_synapse=SimpleNamespace(store=self._store))


class _Trail:
    def __init__(self):
        self.blocks = []

    def record_external_block(self, block):
        self.blocks.append(block)


@pytest.fixture(autouse=True)
def _no_opt_in(monkeypatch):
    """Every test starts from the default: this process has not opted in."""
    monkeypatch.delenv(OPT_IN, raising=False)


@pytest.fixture(autouse=True)
def trail(monkeypatch):
    """Capture recorded blocks instead of touching the process-wide bridge."""
    t = _Trail()
    monkeypatch.setattr(integrity_envelope, "get_process_bridge", lambda: t)
    return t


@pytest.fixture
def records():
    """Every record the handler module logs. Attached to its own logger so a
    non-propagating parent cannot hide the line from the test."""
    log = logging.getLogger(HANDLER_LOGGER)
    seen = []

    class _Collect(logging.Handler):
        def emit(self, record):
            seen.append(record)

    handler = _Collect(level=logging.DEBUG)
    old_level = log.level
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
    try:
        yield seen
    finally:
        log.removeHandler(handler)
        log.setLevel(old_level)


# --- the opt-in --------------------------------------------------------------

def test_default_refuses_and_never_prunes(trail, records):
    store = _FakeStore()
    out = _Host(store)._handle_sleep_pass({})
    assert out["ran"] is False
    assert out["refused"] is True
    assert OPT_IN + "=1" in out["reason"]
    assert store.calls == 0, "the prune ran although the process never opted in"
    assert trail.blocks == []
    logged = [r for r in records if r.levelno >= logging.INFO]
    assert len(logged) == 1, [r.getMessage() for r in logged]
    assert logged[0].levelno == logging.INFO
    assert OPT_IN in logged[0].getMessage()


def test_exactly_one_runs_the_pass(monkeypatch):
    monkeypatch.setenv(OPT_IN, "1")
    store = _FakeStore(n=3, prune=1)
    out = _Host(store)._handle_sleep_pass({})
    assert out == {
        "ran": True, "pruned": 1, "pruned_ids": ["m0"], "staged": 0,
        "before": 3, "after": 2,
    }
    assert store.calls == 1


@pytest.mark.parametrize("value", ["true", "True", "0", "", " 1", "1 ", "yes", "on", "01"])
def test_anything_but_exactly_one_refuses(monkeypatch, value):
    monkeypatch.setenv(OPT_IN, value)
    store = _FakeStore()
    out = _Host(store)._handle_sleep_pass({})
    assert out["ran"] is False and out["refused"] is True
    assert store.calls == 0, "%r opted the process in; only exactly '1' may" % value


@pytest.mark.parametrize("payload", [
    {OPT_IN: "1"},
    {"allow": True, "force": True, "approved": True, "consent": True, "opt_in": True},
    {"env": {OPT_IN: "1"}},
])
def test_payload_cannot_opt_in(payload):
    store = _FakeStore()
    out = _Host(store)._handle_sleep_pass(payload)
    assert out["ran"] is False and out["refused"] is True
    assert store.calls == 0, "a request payload opted itself in"


def test_an_unimportable_bridge_is_not_a_way_past_the_gate(monkeypatch):
    """Before D4, ``except ImportError`` ran the prune with no gate at all."""
    monkeypatch.setitem(sys.modules, "shared.bridge", None)
    store = _FakeStore()
    out = _Host(store)._handle_sleep_pass({})
    assert out["refused"] is True
    assert store.calls == 0


# --- no fallback, no retry ---------------------------------------------------

def test_a_failed_pass_is_answered_once(monkeypatch, trail):
    monkeypatch.setenv(OPT_IN, "1")
    store = _FakeStore(raises=RuntimeError("moneta exploded"))
    out = _Host(store)._handle_sleep_pass({})
    assert out["ran"] is False
    assert "moneta exploded" in out["error"]
    assert store.calls == 1, "the pass was retried"
    assert trail.blocks == [], "only a pass that ran is recorded"


def test_a_bridge_failure_never_reruns_the_prune(monkeypatch):
    """Before D4, when ``bridge.execute()`` raised, ``except Exception`` ran
    ``_do_prune()`` again with no gate: a SECOND destructive pass whenever the
    bridge failed after the first had already run. The pass no longer enters
    ``bridge.execute()`` at all, so a broken bridge cannot cause a prune."""
    monkeypatch.setenv(OPT_IN, "1")
    entered = []

    def _execute_then_fail(self, operation):
        entered.append(operation.operation_type)
        operation.fn()
        raise RuntimeError("bridge failed after the operation ran")

    monkeypatch.setattr(bridge_mod.LosslessExecutionBridge, "execute", _execute_then_fail)
    store = _FakeStore()
    out = _Host(store)._handle_sleep_pass({})
    assert store.calls == 1, "the destructive prune ran %d times" % store.calls
    assert entered == [], "the pass went through bridge.execute()"
    assert out["ran"] is True


def test_a_native_panic_returns_ran_false(monkeypatch, trail, records):
    assert is_native_panic(_PanicException("x")), "control: the shape must read as a PyO3 panic"
    monkeypatch.setenv(OPT_IN, "1")
    store = _FakeStore(raises=_PanicException("rust panicked: index out of bounds"))
    out = _Host(store)._handle_sleep_pass({})
    assert out["ran"] is False
    assert "PanicException" in out["error"]
    assert store.calls == 1, "the pass was retried after a panic"
    assert trail.blocks == []
    assert any(r.levelno >= logging.ERROR for r in records), "the panic was not logged"


@pytest.mark.parametrize("exc", [
    KeyboardInterrupt(), SystemExit(3), GeneratorExit(), asyncio.CancelledError(),
], ids=lambda e: type(e).__name__)
def test_control_flow_propagates_untouched(monkeypatch, trail, exc):
    monkeypatch.setenv(OPT_IN, "1")
    store = _FakeStore(raises=exc)
    with pytest.raises(type(exc)) as caught:
        _Host(store)._handle_sleep_pass({})
    assert caught.value is exc
    assert store.calls == 1
    assert trail.blocks == []


# --- the observe-only block --------------------------------------------------

def test_a_pass_that_ran_leaves_one_honest_observe_only_block(monkeypatch, trail):
    monkeypatch.setenv(OPT_IN, "1")
    out = _Host(_FakeStore())._handle_sleep_pass({})
    assert out["ran"] is True
    assert len(trail.blocks) == 1
    block = trail.blocks[0]
    assert block.operation_type == "sleep_pass"
    assert block.agent_id == "CONDUCTOR"
    assert block.execution_path == "live"
    # Never claimed: no gate ran, nothing was undo-wrapped, no composition check.
    assert block.consent_verified is False and block.consent_applicable is False
    assert block.undo_group_active is False and block.undo_applicable is False
    assert block.composition_valid is False and block.composition_applicable is False
    # Measured: pytest runs this test on the main thread.
    assert block.main_thread_executed is True
    # The pass touches no scene, so no scene hash is taken.
    assert block.scene_hash_before == "" and block.scene_hash_after == ""
    assert block.delta_hash == "scene_free"
    assert block.fidelity == 1.0


def test_an_off_main_pass_reports_ran_and_its_real_thread(monkeypatch, trail):
    """FM11: through ``bridge.execute()`` an off-main pass scored fidelity 0,
    so the handler answered ran=False although the prune had happened. Called
    directly, the caller gets the audit, and the block records the thread the
    pass really ran on instead of asserting the main thread."""
    monkeypatch.setenv(OPT_IN, "1")
    store = _FakeStore()
    box = {}

    def _run():
        box["out"] = _Host(store)._handle_sleep_pass({})

    worker = threading.Thread(target=_run)
    worker.start()
    worker.join(10)
    assert box["out"]["ran"] is True
    assert store.calls == 1
    assert len(trail.blocks) == 1
    assert trail.blocks[0].main_thread_executed is False


def test_a_failed_block_record_still_returns_the_pass_result(monkeypatch, records):
    monkeypatch.setenv(OPT_IN, "1")

    def _broken():
        raise RuntimeError("trail unavailable")

    monkeypatch.setattr(integrity_envelope, "get_process_bridge", _broken)
    store = _FakeStore()
    out = _Host(store)._handle_sleep_pass({})
    assert out["ran"] is True and store.calls == 1
    assert any(
        r.levelno >= logging.WARNING and "integrity block" in r.getMessage()
        for r in records
    ), "a lost integrity block must be logged"
