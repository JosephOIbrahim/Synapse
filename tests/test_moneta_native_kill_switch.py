"""NATIVE-KILL-SWITCH: ``MONETA_NATIVE=0`` keeps ``moneta_native`` out of the process.

Moneta imports its Rust extension, ``moneta_native``, eagerly when the
``moneta`` package loads, and reads ``MONETA_NATIVE`` only later, when objects
are constructed. ``MONETA_NATIVE=0`` (Moneta's "use the pure-Python oracle"
switch) therefore chose the oracle with the DLL already loaded into Houdini.
``moneta_runtime._try_import`` now honours the switch before its first
``from moneta import``.

Nothing real is imported here: not the moneta package, not the native module.
Each test writes a fake ``moneta_native.py`` into tmp_path whose body leaves a
marker file when it executes (executing it is the stand-in for the DLL
loading), and a fake ``moneta.py`` that imports ``moneta_native`` at module
load the way the live checkout does. The module under test is this checkout's
``python/synapse/memory/moneta_runtime.py``, executed as a private copy so its
module-level ``_try_import()`` runs exactly as it does at SYNAPSE startup
without touching the shared ``synapse.memory.moneta_runtime`` that other tests
hold, and with ``moneta`` either blocked or resolved to the fake.
"""

import importlib
import importlib.util
import sys
import types
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_RUNTIME_PY = _ROOT / "python" / "synapse" / "memory" / "moneta_runtime.py"

_ABSENT = object()
_GUARDED = ("moneta", "moneta_native")

_FAKE_NATIVE = '''\
"""Stand-in for the Rust extension. This body running = the DLL loading."""
import pathlib

IS_FAKE = True
pathlib.Path(__file__).with_name("moneta_native.loaded").write_text(
    "loaded", encoding="utf-8")
'''

_FAKE_MONETA = '''\
"""Stand-in for moneta: binds the native module at import, as the live checkout does."""
try:
    import moneta_native as _native
except ImportError:
    _native = None

NATIVE_SEEN = _native is not None


class MonetaConfig:
    pass


class Moneta:
    pass
'''


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Fakes first on sys.path, both module names evicted, env cleared.

    ``sys.modules`` is snapshotted and restored by hand rather than through
    ``monkeypatch.delitem``: that records nothing for a key that was absent,
    so the guard's ``None`` entry, or a fake, would outlive the test and break
    every later ``import moneta`` in the run.
    """
    (tmp_path / "moneta_native.py").write_text(_FAKE_NATIVE, encoding="utf-8")
    (tmp_path / "moneta.py").write_text(_FAKE_MONETA, encoding="utf-8")
    saved = {name: sys.modules.get(name, _ABSENT) for name in _GUARDED}
    for name in _GUARDED:
        sys.modules.pop(name, None)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delenv("MONETA_NATIVE", raising=False)
    monkeypatch.delenv("MONETA_SRC", raising=False)
    try:
        yield tmp_path
    finally:
        for name, module in saved.items():
            if module is _ABSENT:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def _load_runtime(*, block_moneta):
    """Execute this checkout's moneta_runtime.py as a private module.

    With *block_moneta* the module-level ``from moneta import`` fails at once
    and no package is imported; otherwise it resolves to the fake in tmp_path.
    The ``sandbox`` fixture restores ``sys.modules['moneta']`` either way.
    """
    if block_moneta:
        sys.modules["moneta"] = None
    spec = importlib.util.spec_from_file_location(
        "_moneta_runtime_native_kill_switch_under_test", _RUNTIME_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _kill_switch(rt):
    """Call the guard. A tree that predates it has no such name; a no-op stands
    in so the test fails on the behaviour (the native module still loads),
    which is the defect, rather than on a missing attribute."""
    return getattr(rt, "_apply_native_kill_switch", lambda: None)()


def _state(rt):
    return getattr(rt, "_NATIVE_KILL_SWITCH", "<no _NATIVE_KILL_SWITCH on this tree>")


def test_module_under_test_is_the_one_synapse_imports():
    """Law 1: the private copy is the file ``synapse.memory.moneta_runtime``
    resolves to in this run, not the editable install's checkout."""
    spec = importlib.util.find_spec("synapse.memory.moneta_runtime")
    assert spec is not None and spec.origin, "synapse.memory.moneta_runtime not found"
    print(f"synapse.memory.moneta_runtime -> {spec.origin}")
    assert Path(spec.origin).resolve() == _RUNTIME_PY.resolve(), (
        f"this run imports moneta_runtime from {spec.origin}, but the tests "
        f"below exercise {_RUNTIME_PY}")


def test_native_0_blocks_the_native_import(sandbox, monkeypatch):
    """Case 1: MONETA_NATIVE=0 and nothing loaded yet -> the import is refused."""
    rt = _load_runtime(block_moneta=True)
    monkeypatch.setenv("MONETA_NATIVE", "0")
    _kill_switch(rt)
    with pytest.raises(ImportError):
        importlib.import_module("moneta_native")
    assert not (sandbox / "moneta_native.loaded").exists(), (
        "the stand-in native module executed although MONETA_NATIVE=0")
    assert sys.modules["moneta_native"] is None
    assert _state(rt) == "applied"
    # moneta_available() re-enters _try_import while moneta is unavailable,
    # so a second pass must find its own sentinel and still say "applied".
    _kill_switch(rt)
    assert _state(rt) == "applied"
    assert sys.modules["moneta_native"] is None


@pytest.mark.parametrize("value", [None, "1", ""], ids=["unset", "one", "empty"])
def test_switch_is_inert_unless_exactly_zero(sandbox, monkeypatch, value):
    """Case 2: MONETA_NATIVE unset (or any value but "0") -> nothing changes."""
    rt = _load_runtime(block_moneta=True)
    if value is not None:
        monkeypatch.setenv("MONETA_NATIVE", value)
    _kill_switch(rt)
    assert "moneta_native" not in sys.modules, "the guard wrote to sys.modules"
    native = importlib.import_module("moneta_native")
    # Positive control: the tmp_path stand-in imported, not site-packages'.
    assert getattr(native, "IS_FAKE", False) is True
    assert (sandbox / "moneta_native.loaded").exists()
    assert _state(rt) == "not_requested"


def test_already_loaded_native_module_is_left_alone(sandbox, monkeypatch):
    """Case 3: the module is already in sys.modules -> untouched, and said so."""
    rt = _load_runtime(block_moneta=True)
    resident = types.ModuleType("moneta_native")
    sys.modules["moneta_native"] = resident
    monkeypatch.setenv("MONETA_NATIVE", "0")
    _kill_switch(rt)
    assert sys.modules["moneta_native"] is resident, "a loaded DLL cannot be unloaded"
    assert importlib.import_module("moneta_native") is resident
    assert _state(rt) == "already_loaded"


def test_switch_lands_before_moneta_binds_its_native_module(sandbox, monkeypatch):
    """The call site: at module import (SYNAPSE startup), MONETA_NATIVE=0 must
    already be in force when ``from moneta import`` runs moneta's own
    ``import moneta_native``. Applying it after that import is too late."""
    monkeypatch.setenv("MONETA_NATIVE", "0")
    rt = _load_runtime(block_moneta=False)
    fake_moneta = sys.modules["moneta"]
    assert rt.moneta_available() is True
    assert rt.Moneta is fake_moneta.Moneta
    assert fake_moneta.NATIVE_SEEN is False, (
        "moneta bound moneta_native although MONETA_NATIVE=0 was set before import")
    assert not (sandbox / "moneta_native.loaded").exists()
    assert _state(rt) == "applied"


def test_fake_moneta_binds_native_when_not_requested(sandbox):
    """Control for the test above: without the switch the fake moneta really
    does load the native module, so its NATIVE_SEEN=False there is the guard's
    doing and not a fake that never reaches for it."""
    rt = _load_runtime(block_moneta=False)
    fake_moneta = sys.modules["moneta"]
    assert rt.moneta_available() is True
    assert fake_moneta.NATIVE_SEEN is True
    assert (sandbox / "moneta_native.loaded").exists()
    assert _state(rt) == "not_requested"
