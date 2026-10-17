"""NATIVE-STATUS: ``synapse_memory_status`` says which Moneta native path runs.

The failure this pins (R3 audit): memory_status, get_health, doctor and
moneta_provenance carried no native, backend or demotion field. When a
``moneta_native`` wheel lands on a Houdini-visible path, Moneta switches its
Rust scan and decay kernels on by default (``vector_index._resolve_backend``
and ``ECS.__init__`` both pick native when the module imports), and nothing
said so.

``native_status()`` reads only what is already in the process: the
``sys.modules`` entry, ``MONETA_NATIVE``, one ``os.stat`` of the loaded file,
and plain attributes of a Moneta handle. It must never import anything: a
status read that imported the wheel would itself be the activation it exists
to report.

No real native module is used. ``_ImportProbe`` answers any attempt to import
``moneta_native`` with a fake and records it, so an accidental import is caught
whether or not the real wheel is installed. On the dev seat it is installed
(site-packages); on a box without it, a failed import leaves nothing in
``sys.modules``, so a ``sys.modules`` check alone would pass there and prove
nothing.

Pure Python: no hou, no store, no disk beyond tmp_path.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types
from unittest.mock import MagicMock

import pytest

from synapse.memory.native_status import native_status
from synapse.server.handlers_memory import MemoryHandlerMixin

_NAME = "moneta_native"


class PanicException(BaseException):
    """Stands in for ``pyo3_runtime.PanicException``.

    PyO3 raises it when Rust code panics. It derives from BaseException, so a
    guard written as ``except Exception`` lets it straight through.
    """


class _ImportProbe:
    """A meta-path finder that would satisfy ``import moneta_native`` with a
    fake module, and records every time the import system asks for it."""

    def __init__(self):
        self.attempts = []

    def find_spec(self, name, path=None, target=None):
        if name != _NAME and not name.startswith(_NAME + "."):
            return None
        self.attempts.append(name)
        return importlib.util.spec_from_loader(name, self)

    def create_module(self, spec):
        return None  # the default module object

    def exec_module(self, module):
        module.__version__ = "0.0.0+probe"


@pytest.fixture
def probe(monkeypatch):
    finder = _ImportProbe()
    monkeypatch.setattr(sys, "meta_path", [finder, *sys.meta_path])
    yield finder
    # If the probe served its fake, do not let it outlive this test.
    if getattr(sys.modules.get(_NAME), "__loader__", None) is finder:
        del sys.modules[_NAME]


@pytest.fixture(autouse=True)
def _no_native_env(monkeypatch):
    monkeypatch.delenv("MONETA_NATIVE", raising=False)


def _moneta_handle(backend="native", decay=True):
    """The two attributes Moneta exposes: Moneta.vector_index.backend
    (vector_index.py) and Moneta.ecs.native_decay (ecs.py)."""
    return types.SimpleNamespace(
        vector_index=types.SimpleNamespace(backend=backend),
        ecs=types.SimpleNamespace(native_decay=decay),
    )


# ---------------------------------------------------------------------------
# The module reading
# ---------------------------------------------------------------------------

def test_an_absent_module_reads_not_loaded_and_the_read_imports_nothing(
        monkeypatch, probe):
    monkeypatch.delitem(sys.modules, _NAME, raising=False)
    before = set(sys.modules)

    reading = native_status()

    assert probe.attempts == [], (
        "native_status() asked the import system for %s: a status read must "
        "never import the wheel it reports on" % probe.attempts)
    assert _NAME not in sys.modules, "native_status() imported moneta_native"
    assert not {m for m in set(sys.modules) - before
                if m.split(".")[0] in ("moneta", _NAME)}
    assert reading["state"] == "not_loaded"
    assert reading["file"] is None and reading["version"] is None
    assert reading["size"] is None and reading["mtime"] is None
    assert reading["error"] is None


def test_a_none_entry_reads_blocked_and_stays_blocked(monkeypatch, probe):
    monkeypatch.setitem(sys.modules, _NAME, None)

    reading = native_status()

    assert reading["state"] == "blocked"
    assert sys.modules[_NAME] is None
    assert probe.attempts == []
    assert reading["file"] is None and reading["size"] is None
    assert reading["error"] is None


def test_a_loaded_module_reports_its_file_version_size_and_mtime(
        monkeypatch, tmp_path):
    binary = tmp_path / "moneta_native.cp313-win_amd64.pyd"
    binary.write_bytes(b"\x00" * 4096)
    fake = types.ModuleType(_NAME)
    fake.__file__ = str(binary)
    fake.__version__ = "9.9.9"
    monkeypatch.setitem(sys.modules, _NAME, fake)
    monkeypatch.setenv("MONETA_NATIVE", "0")

    reading = native_status()

    stat = os.stat(binary)
    assert reading["state"] == "loaded"
    assert reading["file"] == str(binary)
    assert reading["version"] == "9.9.9"
    assert reading["size"] == 4096 == stat.st_size
    assert reading["mtime"] == stat.st_mtime
    assert reading["env_MONETA_NATIVE"] == "0"
    assert reading["error"] is None


def test_module_attributes_are_read_without_running_module_code(monkeypatch):
    """A module-level ``__getattr__`` (PEP 562) can run anything, imports
    included. The reading uses the module's namespace dict, so it never runs."""
    calls = []

    def __getattr__(name):
        calls.append(name)
        raise AttributeError(name)

    fake = types.ModuleType(_NAME)
    fake.__getattr__ = __getattr__
    monkeypatch.setitem(sys.modules, _NAME, fake)

    reading = native_status()

    assert calls == []
    assert reading["state"] == "loaded"
    assert reading["file"] is None and reading["version"] is None
    assert reading["error"] is None


# ---------------------------------------------------------------------------
# The handle reading
# ---------------------------------------------------------------------------

class _RaisingHandle:
    """Every attribute it does not have raises ``exc`` instead of AttributeError."""

    def __init__(self, exc):
        self._exc = exc

    def __getattr__(self, name):
        raise self._exc


@pytest.mark.parametrize("exc", [
    RuntimeError("store swapped mid-read"),
    PanicException("rust panicked"),
], ids=["exception", "panic"])
def test_a_handle_that_raises_is_reported_not_raised(monkeypatch, exc):
    monkeypatch.delitem(sys.modules, _NAME, raising=False)

    reading = native_status(_RaisingHandle(exc))

    assert reading["error"] == repr(exc)
    # What was read before the failure is kept.
    assert reading["state"] == "not_loaded"
    assert reading["vector_backend"] is None and reading["native_decay"] is None


def test_keyboard_interrupt_is_not_swallowed():
    with pytest.raises(KeyboardInterrupt):
        native_status(_RaisingHandle(KeyboardInterrupt()))


@pytest.mark.parametrize("wrap, via", [
    (lambda h: h, "handle"),
    (lambda h: types.SimpleNamespace(_handle=h), "_handle"),
    (lambda h: types.SimpleNamespace(
        primary=types.SimpleNamespace(_handle=h)), "primary._handle"),
    (lambda h: types.SimpleNamespace(
        primary=types.SimpleNamespace(), shadow=types.SimpleNamespace(_handle=h)),
     "shadow._handle"),
], ids=["moneta-handle", "MonetaBackedStore", "WriteThroughStore", "ShadowMemoryStore"])
def test_the_handle_is_found_on_every_store_shape(wrap, via):
    reading = native_status(wrap(_moneta_handle(backend="python", decay=False)))

    assert reading["handle_via"] == via
    assert reading["vector_backend"] == "python"
    assert reading["native_decay"] is False
    assert reading["error"] is None


@pytest.mark.parametrize("store, via", [
    (types.SimpleNamespace(count=lambda: 0), None),
    (types.SimpleNamespace(_handle=types.SimpleNamespace(
        vector_index=types.SimpleNamespace(), ecs=types.SimpleNamespace())),
     "_handle"),
    (types.SimpleNamespace(_handle=types.SimpleNamespace(
        vector_index=types.SimpleNamespace(backend=MagicMock()),
        ecs=types.SimpleNamespace(native_decay="yes"))),
     "_handle"),
], ids=["jsonl-store-has-no-handle", "moneta-before-the-native-seam",
        "values-of-the-wrong-type"])
def test_what_is_not_there_reads_null(store, via):
    reading = native_status(store)

    assert reading["handle_via"] == via
    assert reading["vector_backend"] is None
    assert reading["native_decay"] is None
    assert reading["error"] is None


# ---------------------------------------------------------------------------
# Wired into _handle_memory_status
# ---------------------------------------------------------------------------

class _Handler(MemoryHandlerMixin):
    """Just enough host for _handle_memory_status: no hou, no main-thread hop."""

    def __init__(self, bridge):
        self._bridge_obj = bridge

    @staticmethod
    def _scene_paths():
        return {"hip_path": "scene.hip", "hip_dir": "scene",
                "job_path": "job", "job_root": "job"}

    def _memory_on_main(self, callback):
        return callback(self._bridge_obj)


class _UnreachableHandler(_Handler):
    def _memory_on_main(self, callback):
        raise TimeoutError("main thread busy")


@pytest.fixture
def scene_status(monkeypatch):
    """Keep the markdown half off disk: the real resolvers probe writability
    and can fall back to the shared unsaved-scene folder."""
    from synapse.memory import scene_memory

    monkeypatch.setattr(scene_memory, "get_memory_status", lambda scene_dir, project_dir: {
        "project": {"evolution": "none"},
        "scene": {"evolution": "none"},
        "agent": {"status": "idle"},
    })


def _bridge_with(store):
    return types.SimpleNamespace(_synapse=types.SimpleNamespace(store=store))


def test_memory_status_reports_the_native_path_of_the_live_store(
        monkeypatch, scene_status):
    fake = types.ModuleType(_NAME)
    fake.__version__ = "0.1.0"
    monkeypatch.setitem(sys.modules, _NAME, fake)
    store = types.SimpleNamespace(count=lambda: 3, _handle=_moneta_handle())

    status = _Handler(_bridge_with(store))._handle_memory_status({})

    native = status["native"]
    assert native["state"] == "loaded" and native["version"] == "0.1.0"
    assert native["handle_via"] == "_handle"
    assert native["vector_backend"] == "native"
    assert native["native_decay"] is True
    assert native["error"] is None
    # The existing keys are unchanged.
    assert status["entries_total"] == 3
    assert {"project", "scene", "agent", "health"} <= set(status)
    assert status["health"]["status"] == "unknown"


@pytest.mark.parametrize("handler", [
    _UnreachableHandler(None),
    _Handler(types.SimpleNamespace(_synapse=None)),
], ids=["store-unreachable", "no-store-loaded"])
def test_memory_status_keeps_the_native_key_when_no_store_is_read(
        monkeypatch, scene_status, handler):
    monkeypatch.setitem(sys.modules, _NAME, None)

    status = handler._handle_memory_status({})

    native = status["native"]
    assert native["state"] == "blocked"
    assert native["handle_via"] is None and native["vector_backend"] is None
    assert status["health"]["status"] == "unknown"
