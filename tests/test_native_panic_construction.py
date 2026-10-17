"""PANIC-FENCE-CONSTRUCTION: a Rust panic while building the Moneta store
falls back to jsonl and is recorded, instead of escaping.

PyO3 turns a Rust panic into ``pyo3_runtime.PanicException``, which derives
from ``BaseException``. During store construction it passed the
``except Exception`` fallback arms in ``SynapseMemory._make_store`` (and the
retry arm inside ``MonetaBackedStore.from_storage_dir``), so no jsonl store was
served, ``backend_fallback()`` stayed None, ``_global_synapse`` was never
published, and every later ``get_synapse_memory()`` built the store again and
panicked again.

Hermetic. The real ``moneta`` and ``moneta_native`` cannot be imported by any
test here. ``synapse.memory.moneta_runtime`` imports moneta at module scope, so
it is never imported either: a stand-in module takes its place. The native
constructor is a fake that raises a ``PanicException`` shaped like PyO3's (a
``BaseException`` subclass whose ``__module__`` is ``pyo3_runtime``). Every
path a store touches is under ``tmp_path``.

Bite. Against the unguarded ``store.py`` the panic cases fail with the
``PanicException`` escaping ``_make_store`` and ``get_synapse_memory()``. The
interpreter-control cases pass on both sides, because those must still
propagate.
"""

import asyncio
import logging
import sys
import types

import pytest

import synapse.memory as memory_pkg
from synapse.memory import moneta_store
from synapse.memory import store as store_mod
from synapse.memory.store import MemoryStore, SynapseMemory


class PanicException(BaseException):
    """Stand-in for PyO3's ``pyo3_runtime.PanicException``."""

    __module__ = "pyo3_runtime"


#: Named like PyO3's panic but defined by some other module: not ours to serve.
ForeignPanicException = type(
    "PanicException", (BaseException,), {"__module__": "not_pyo3_runtime"})


def _rust_panic():
    return PanicException("rust panicked")


# ---------------------------------------------------------------------------
# the seat
# ---------------------------------------------------------------------------

@pytest.fixture
def seat(monkeypatch, tmp_path):
    """A seat that selects Moneta, with no real Moneta anywhere near it."""
    # An import of the real package now raises ImportError instead of loading.
    monkeypatch.setitem(sys.modules, "moneta", None)
    monkeypatch.setitem(sys.modules, "moneta_native", None)

    runtime = types.ModuleType("synapse.memory.moneta_runtime")
    runtime.moneta_available = lambda: True
    runtime.import_error = lambda: None
    runtime.moneta_provenance = lambda *a, **k: {"file": "<stand-in moneta>"}
    # _make_store does `from . import moneta_runtime`, which reads the package
    # attribute before sys.modules. Both have to hold the stand-in.
    monkeypatch.setitem(sys.modules, "synapse.memory.moneta_runtime", runtime)
    monkeypatch.setattr(memory_pkg, "moneta_runtime", runtime, raising=False)

    for name, leaf in (("HOUDINI_TEMP_DIR", "houdini_temp"), ("HOME", "home"),
                       ("USERPROFILE", "home"), ("SYNAPSE_LOG_DIR", "logs")):
        target = tmp_path / leaf
        target.mkdir(exist_ok=True)
        monkeypatch.setenv(name, str(target))

    # conftest's fake hou is not a host; never route through main-thread hops.
    monkeypatch.setattr(store_mod, "HOU_AVAILABLE", False)
    monkeypatch.setattr(store_mod, "_BACKEND_FALLBACK", None)
    monkeypatch.setattr(store_mod, "_global_synapse", None)

    calls = []

    def constructor_raises(make_exc):
        def from_storage_dir(storage_dir, *_a, **_k):
            calls.append(storage_dir)
            raise make_exc()

        monkeypatch.setattr(moneta_store.MonetaBackedStore, "from_storage_dir",
                            staticmethod(from_storage_dir))

    return types.SimpleNamespace(calls=calls,
                                 constructor_raises=constructor_raises)


# ---------------------------------------------------------------------------
# the panic is served: jsonl, recorded, loud
# ---------------------------------------------------------------------------

def test_panic_building_the_moneta_store_serves_jsonl_and_is_recorded(
        seat, monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    seat.constructor_raises(_rust_panic)
    storage = tmp_path / "proj" / ".synapse"

    with caplog.at_level(logging.ERROR, logger="synapse.memory"):
        store = SynapseMemory._make_store(None, storage)

    # The same jsonl store the Exception path serves.
    assert type(store) is MemoryStore
    assert seat.calls == [storage]

    fb = store_mod.backend_fallback()
    assert fb is not None, "the panic fell back without being recorded"
    assert fb["requested"] == "moneta"
    assert fb["served"] == "jsonl"
    assert fb["storage_dir"] == str(storage)
    assert "native panic" in fb["reason"]
    assert "PanicException: rust panicked" in fb["reason"]

    # Loud, like the installed-but-broken arm: ERROR, consequence, address.
    loud = [r.getMessage() for r in caplog.records
            if r.levelno >= logging.ERROR and "FELL BACK" in r.getMessage()]
    assert loud, [r.getMessage() for r in caplog.records]
    assert str(storage) in loud[0]

    # Installed but faulted reads BLOCKED, as an init failure does -- not
    # UNAVAILABLE, which means "not installed".
    health = store_mod.backend_health(store)
    assert health["status"] == "BLOCKED", health
    assert "native panic" in health["reason"]


def test_panic_building_the_shadow_store_serves_jsonl_and_is_recorded(
        seat, monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "shadow")
    seat.constructor_raises(_rust_panic)
    storage = tmp_path / "proj" / ".synapse"

    with caplog.at_level(logging.WARNING, logger="synapse.memory"):
        store = SynapseMemory._make_store(None, storage)

    assert type(store) is MemoryStore  # jsonl, not a ShadowMemoryStore
    assert seat.calls == [storage]
    fb = store_mod.backend_fallback()
    assert fb is not None, "the panic fell back without being recorded"
    assert fb["requested"] == "shadow"
    assert fb["served"] == "jsonl"
    assert "native panic" in fb["reason"]
    assert "PanicException: rust panicked" in fb["reason"]
    said = [r.getMessage() for r in caplog.records
            if r.levelno >= logging.WARNING and "fell back to jsonl" in r.getMessage()]
    assert said, [r.getMessage() for r in caplog.records]


def test_get_synapse_memory_publishes_once_instead_of_repanicking(
        seat, monkeypatch, tmp_path):
    """The public entry. Unguarded, the panic escaped construction, the global
    was never assigned, and the next call built the store and panicked again."""
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    seat.constructor_raises(_rust_panic)
    project = tmp_path / "project"
    real_init = SynapseMemory.__init__

    def pinned(self, project_path=None):
        real_init(self, project_path=str(project))

    monkeypatch.setattr(SynapseMemory, "__init__", pinned)

    first = store_mod.get_synapse_memory()
    second = store_mod.get_synapse_memory()

    assert first is second
    assert first is store_mod._global_synapse
    assert type(first.store) is MemoryStore
    assert len(seat.calls) == 1, (
        f"the store was built {len(seat.calls)} times; a published fallback "
        "is built once")
    assert "native panic" in store_mod.backend_fallback()["reason"]


# ---------------------------------------------------------------------------
# controls: the existing path is unchanged, and nothing else is caught
# ---------------------------------------------------------------------------

def test_an_ordinary_exception_still_takes_the_existing_path(
        seat, monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    seat.constructor_raises(lambda: RuntimeError("adapter drift"))

    with caplog.at_level(logging.ERROR, logger="synapse.memory"):
        store = SynapseMemory._make_store(None, tmp_path / "proj" / ".synapse")

    assert type(store) is MemoryStore
    assert store_mod.backend_fallback()["reason"] == (
        "init failed: RuntimeError: adapter drift")
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "is installed but failed to initialize" in said
    # The existing arm's provenance came from the stand-in, never real moneta.
    assert "<stand-in moneta>" in said
    assert "native panic" not in said.lower()


_MUST_PROPAGATE = [
    pytest.param(KeyboardInterrupt, id="KeyboardInterrupt"),
    pytest.param(SystemExit, id="SystemExit"),
    pytest.param(GeneratorExit, id="GeneratorExit"),
    pytest.param(asyncio.CancelledError, id="CancelledError"),
    pytest.param(ForeignPanicException, id="PanicException-from-another-module"),
]


@pytest.mark.parametrize("backend", ["moneta", "shadow"])
@pytest.mark.parametrize("exc_type", _MUST_PROPAGATE)
def test_other_base_exceptions_from_the_same_constructor_still_propagate(
        seat, monkeypatch, tmp_path, backend, exc_type):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", backend)
    seat.constructor_raises(exc_type)

    with pytest.raises(exc_type):
        SynapseMemory._make_store(None, tmp_path / "proj" / ".synapse")

    assert seat.calls, "the constructor was never reached"
    assert store_mod.backend_fallback() is None


# ---------------------------------------------------------------------------
# is_native_panic
# ---------------------------------------------------------------------------

def test_is_native_panic_matches_pyo3_panics():
    from synapse.memory.native_panic import is_native_panic

    class SubclassedPanic(PanicException):
        pass

    no_module = type("PanicException", (BaseException,), {"__module__": None})

    assert is_native_panic(_rust_panic()) is True
    assert is_native_panic(SubclassedPanic("x")) is True  # matched through the MRO
    assert is_native_panic(no_module("x")) is True  # a missing module is accepted


@pytest.mark.parametrize("exc", [
    pytest.param(KeyboardInterrupt(), id="KeyboardInterrupt"),
    pytest.param(SystemExit(0), id="SystemExit"),
    pytest.param(GeneratorExit(), id="GeneratorExit"),
    pytest.param(asyncio.CancelledError(), id="CancelledError"),
    pytest.param(ValueError("x"), id="ValueError"),
    pytest.param(RuntimeError("x"), id="RuntimeError"),
    pytest.param(BaseException("x"), id="BaseException"),
    pytest.param(ForeignPanicException("x"), id="PanicException-from-another-module"),
    pytest.param(type("PanicException", (Exception,),
                      {"__module__": "pyo3_runtime"})("x"),
                 id="PanicException-deriving-from-Exception"),
])
def test_is_native_panic_rejects_everything_else(exc):
    from synapse.memory.native_panic import is_native_panic

    assert is_native_panic(exc) is False


@pytest.mark.parametrize("control", [
    KeyboardInterrupt, SystemExit, GeneratorExit, asyncio.CancelledError])
def test_is_native_panic_never_matches_control_flow_named_panicexception(control):
    """A control-flow exception does not become servable by being renamed."""
    from synapse.memory.native_panic import is_native_panic

    disguised = type("PanicException", (control,), {"__module__": "pyo3_runtime"})
    assert is_native_panic(disguised()) is False


@pytest.mark.parametrize("obj", [None, "PanicException", 42, PanicException],
                         ids=["None", "str", "int", "the-class-not-an-instance"])
def test_is_native_panic_rejects_non_instances(obj):
    from synapse.memory.native_panic import is_native_panic

    assert is_native_panic(obj) is False


def test_is_native_panic_never_raises():
    """It runs inside except arms: a class that cannot even be named is not a
    panic, and the check must not raise in its place."""
    from synapse.memory.native_panic import is_native_panic

    class _Unnameable(type):
        def __getattribute__(cls, name):
            if name in ("__name__", "__module__"):
                raise RuntimeError("this class refuses to be named")
            return super().__getattribute__(name)

    class Unnameable(BaseException, metaclass=_Unnameable):
        pass

    assert is_native_panic(Unnameable()) is False
