"""B-PROVENANCE (FM7 + FM12): ``moneta_provenance()`` names the native module.

The failure this pins (R3 audit; FM7 binary identity, FM12 native state
invisible to telemetry): ``moneta_provenance()`` is what the ledger reads on
every deposit and what ``store.py`` logs when the Moneta backend falls back to
jsonl, and it carried no native field. Once a ``moneta_native`` wheel is on a
Houdini-visible path, Moneta switches its Rust scan and decay kernels on by
default, and nothing in the provenance said whether the extension was loaded,
blocked (``MONETA_NATIVE=0``) or absent, or which file it came from.

``moneta_provenance()["native"]`` is the module half of
``synapse.memory.native_status.native_status()``: ``state`` (``not_loaded`` /
``blocked`` / ``loaded``), ``file``, ``version``, ``size``, ``mtime`` and
``env_MONETA_NATIVE``, plus the helper's ``error``. It hashes nothing, imports
nothing, never raises, and leaves every key the payload already had as it was.

Nothing real is loaded. ``sys.modules`` entries are saved and restored by hand,
not with ``monkeypatch.delitem``: that records nothing for a key that was
absent, so an entry planted or imported during a test would outlive it.
``_ImportProbe`` goes first on ``sys.meta_path`` and refuses ``import
moneta_native`` with ImportError after recording the request. The real wheel
is installed in site-packages on the dev seat, so without the probe an
accidental import would load it; with it, the import fails and is counted.

Pure Python: no hou, no store, no disk beyond tmp_path.
"""
from __future__ import annotations

import builtins
import contextlib
import hashlib
import importlib
import io
import os
import sys
import types
from pathlib import Path

import pytest

from synapse.memory import moneta_runtime as mr
from synapse.memory import native_status as native_status_module

_ROOT = Path(__file__).resolve().parents[1]
_NAME = "moneta_native"
_HELPER = "synapse.memory.native_status"
_ABSENT = object()

#: Every key moneta_provenance() returned before the native block: the seed at
#: the top of the function. The block goes beside them; none of them changes.
EXISTING_KEYS = (
    "available", "version", "file", "import_error",
    "moneta_src", "root", "revision", "revision_ref", "revision_source",
    "revision_repo", "revision_resolved_at", "revision_scope",
    "schema_registered", "schema_registered_reason",
    "schema_in_use", "schema_in_use_reason", "usd_root_inspected",
)

#: The native block: the module half of native_status() and its error. The
#: handle half (handle_via, vector_backend, native_decay) needs a live store,
#: which provenance does not have; synapse_memory_status reports it.
NATIVE_KEYS = ("state", "file", "version", "size", "mtime",
               "env_MONETA_NATIVE", "error")

#: (state, MONETA_NATIVE). None leaves the variable unset.
CASES = (
    ("not_loaded", None),
    ("blocked", "0"),    # what NATIVE-KILL-SWITCH leaves in sys.modules
    ("loaded", None),    # Moneta's default once the module imports
    ("loaded", "0"),     # the switch came after the load: still loaded
)
CASE_IDS = ("not-loaded", "blocked-by-the-switch", "loaded",
            "loaded-before-the-switch")

_FAKE_VERSION = "9.9.9"
_FAKE_SIZE = 4096


@contextlib.contextmanager
def _saved_modules(*names):
    """Restore these ``sys.modules`` entries exactly as found, absent included."""
    saved = {name: sys.modules.get(name, _ABSENT) for name in names}
    try:
        yield
    finally:
        for name, module in saved.items():
            if module is _ABSENT:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


class _ImportProbe:
    """First on ``sys.meta_path``: records a request for moneta_native and
    refuses it, so the real wheel cannot load even if the code asks."""

    def __init__(self):
        self.attempts = []

    def find_spec(self, name, path=None, target=None):
        if name != _NAME and not name.startswith(_NAME + "."):
            return None
        self.attempts.append(name)
        raise ImportError("%s was requested during a provenance read" % name)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """moneta_native and moneta saved and restored by hand, the probe first on
    sys.meta_path, the variables the payload reads cleared, fresh caches.

    ``moneta`` is a fake whose ``__file__`` names a package in tmp_path, a
    directory with no git repository, so the moneta half of the payload is the
    same on every box and no real Moneta is imported."""
    probe = _ImportProbe()
    package = tmp_path / "Moneta" / "src" / "moneta"
    package.mkdir(parents=True)
    moneta_file = package / "__init__.py"
    moneta_file.write_text("# fake moneta\n", encoding="utf-8")
    fake_moneta = types.ModuleType("moneta")
    fake_moneta.__file__ = str(moneta_file)

    with _saved_modules(_NAME, "moneta"):
        sys.modules.pop(_NAME, None)
        sys.modules["moneta"] = fake_moneta
        monkeypatch.setattr(sys, "meta_path", [probe, *sys.meta_path])
        for name in ("MONETA_NATIVE", "SYNAPSE_MONETA_USD_ROOT"):
            monkeypatch.delenv(name, raising=False)
        mr.reset_revision_cache()
        try:
            yield types.SimpleNamespace(probe=probe, tmp=tmp_path,
                                        moneta_file=str(moneta_file))
        finally:
            mr.reset_revision_cache()


def _enter(state, env, sandbox, monkeypatch):
    """Put moneta_native in *state* and MONETA_NATIVE at *env*. Returns what
    ``sys.modules`` now holds for it (``_ABSENT`` when there is no entry)."""
    monkeypatch.delenv("MONETA_NATIVE", raising=False)
    if env is not None:
        monkeypatch.setenv("MONETA_NATIVE", env)
    if state == "not_loaded":
        sys.modules.pop(_NAME, None)
        return _ABSENT
    if state == "blocked":
        sys.modules[_NAME] = None
        return None
    binary = sandbox.tmp / "moneta_native.cp313-win_amd64.pyd"
    binary.write_bytes(b"\x00" * _FAKE_SIZE)
    fake = types.ModuleType(_NAME)
    fake.__file__ = str(binary)
    fake.__version__ = _FAKE_VERSION
    sys.modules[_NAME] = fake
    return fake


def _native(prov):
    assert "native" in prov, (
        "moneta_provenance() has no 'native' block: nothing in the provenance "
        "says whether moneta_native is loaded, blocked or absent, or which "
        "file it is (FM7 + FM12)")
    native = prov["native"]
    assert isinstance(native, dict), "the native block is %r" % (native,)
    return native


def _existing(prov):
    return {key: prov.get(key, "<missing>") for key in EXISTING_KEYS}


def _norm(path):
    return os.path.normcase(os.path.abspath(os.fsdecode(path)))


# ---------------------------------------------------------------------------
# The block
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("available", [True, False],
                         ids=["moneta-available", "moneta-unavailable"])
@pytest.mark.parametrize("state, env", CASES, ids=CASE_IDS)
def test_the_native_block_reports_the_module_state(
        sandbox, monkeypatch, state, env, available):
    """All three states, on both arms of the early return. Like conditions 3
    and 4, the native state does not depend on the package importing."""
    monkeypatch.setattr(mr, "_MONETA_AVAILABLE", available)
    entry = _enter(state, env, sandbox, monkeypatch)
    before = set(sys.modules)

    prov = mr.moneta_provenance()

    native = _native(prov)
    assert sorted(native) == sorted(NATIVE_KEYS)
    assert native["state"] == state
    assert native["env_MONETA_NATIVE"] == env
    assert native["error"] is None
    if state == "loaded":
        stat = os.stat(entry.__file__)
        assert native["file"] == entry.__file__
        assert native["version"] == _FAKE_VERSION
        assert native["size"] == _FAKE_SIZE == stat.st_size
        assert native["mtime"] == stat.st_mtime
    else:
        assert native["file"] is None and native["version"] is None
        assert native["size"] is None and native["mtime"] is None
    # Read, never triggered: no import request, the entry untouched, and no
    # moneta module new to the process.
    assert sandbox.probe.attempts == [], (
        "moneta_provenance() asked the import system for %s: a provenance read "
        "must never import the wheel it reports on" % sandbox.probe.attempts)
    assert sys.modules.get(_NAME, _ABSENT) is entry
    assert not {name for name in set(sys.modules) - before
                if name.split(".")[0] in ("moneta", _NAME)}


def test_the_native_block_is_read_when_the_schema_probes_are_skipped(
        sandbox, monkeypatch):
    """probe_schema=False is scoped to conditions 3 and 4. The native block is
    one sys.modules lookup and at most one os.stat, so it is always read."""
    monkeypatch.setattr(mr, "_MONETA_AVAILABLE", True)
    fake = _enter("loaded", None, sandbox, monkeypatch)

    prov = mr.moneta_provenance(probe_schema=False)

    native = _native(prov)
    assert native["state"] == "loaded"
    assert native["file"] == fake.__file__
    assert native["error"] is None
    assert prov["schema_registered_reason"] == mr.NOT_PROBED_REASON
    assert prov["schema_in_use_reason"] == mr.NOT_PROBED_REASON


# ---------------------------------------------------------------------------
# The payload around it
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("available", [True, False],
                         ids=["moneta-available", "moneta-unavailable"])
def test_the_existing_keys_are_unchanged(sandbox, monkeypatch, available):
    """The block is added beside the existing keys. None is dropped, renamed or
    changed by the native state: a payload that folded the native reading into
    the top level would report the native module's file and version as
    Moneta's, in every ledger record and in store.py's fallback log line."""
    monkeypatch.setattr(mr, "_MONETA_AVAILABLE", available)
    mr.moneta_provenance()  # warm the caches: the revision resolves once per root
    expected = set(EXISTING_KEYS) | {"native"}
    seen = {}
    for (state, env), case in zip(CASES, CASE_IDS):
        _enter(state, env, sandbox, monkeypatch)
        prov = mr.moneta_provenance()
        got = set(prov)
        assert got == expected, (
            "%s: moneta_provenance() keys missing %s, unexpected %s"
            % (case, sorted(expected - got), sorted(got - expected)))
        seen[case] = _existing(prov)

    reference = seen[CASE_IDS[0]]
    for case, values in seen.items():
        changed = sorted(key for key in EXISTING_KEYS
                         if values[key] != reference[key])
        assert not changed, "%s changed existing keys %s" % (case, changed)
    if available:
        assert reference["file"] == sandbox.moneta_file


@pytest.mark.parametrize("failure, raised", [
    ("helper-raises", "RuntimeError"),
    ("helper-unimportable", "ModuleNotFoundError"),
], ids=["helper-raises", "helper-unimportable"])
def test_a_failed_helper_keeps_every_existing_key(
        sandbox, monkeypatch, failure, raised):
    """_make_store calls moneta_provenance() inside its own except handler, so
    the payload must never raise. If the helper raises, or cannot even be
    imported, the existing keys come back as they would have, and the native
    block is still there, empty, with the reason in ``error``."""
    monkeypatch.setattr(mr, "_MONETA_AVAILABLE", True)
    _enter("loaded", None, sandbox, monkeypatch)
    healthy = mr.moneta_provenance()

    with _saved_modules(_HELPER):
        if failure == "helper-raises":
            def broken(*_args, **_kwargs):
                raise RuntimeError("native_status is on fire")
            monkeypatch.setattr(native_status_module, "native_status", broken)
        else:
            sys.modules[_HELPER] = None
        try:
            prov = mr.moneta_provenance()
        except Exception as exc:  # noqa: BLE001
            pytest.fail("moneta_provenance() raised when the native helper "
                        "failed: %r" % (exc,))

    assert _existing(prov) == {key: healthy[key] for key in EXISTING_KEYS}
    native = _native(prov)
    assert sorted(native) == sorted(NATIVE_KEYS)
    assert all(native[key] is None for key in NATIVE_KEYS if key != "error"), (
        "a failed reading must not leave a state or a file standing: %r"
        % (native,))
    assert raised in (native["error"] or ""), native["error"]


# ---------------------------------------------------------------------------
# No hashing, no import
# ---------------------------------------------------------------------------

def test_the_native_file_is_stat_ed_and_never_read(sandbox, monkeypatch):
    """No hashing. Size and mtime come from one os.stat; nothing opens the
    file, so nothing can hash it. Every opener is recorded for that one path:
    builtins.open, io.open (pathlib's way in) and os.open."""
    monkeypatch.setattr(mr, "_MONETA_AVAILABLE", True)
    fake = _enter("loaded", None, sandbox, monkeypatch)
    target = _norm(fake.__file__)
    opened = []

    def recording(label, real):
        def opener(file, *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)) and _norm(file) == target:
                opened.append(label)
            return real(file, *args, **kwargs)
        return opener

    with pytest.MonkeyPatch.context() as mp:
        for owner, name in ((builtins, "open"), (io, "open"), (os, "open")):
            mp.setattr(owner, name,
                       recording("%s.%s" % (owner.__name__, name),
                                 getattr(owner, name)))
        prov = mr.moneta_provenance()
        during_provenance = list(opened)
        # Control: the recorder sees a read of that file by each route, so
        # the empty list above is not an artefact of the patch.
        hashlib.sha256(Path(fake.__file__).read_bytes()).hexdigest()
        with open(fake.__file__, "rb"):
            pass
        os.close(os.open(fake.__file__, os.O_RDONLY))
        control = list(opened[len(during_provenance):])

    native = _native(prov)
    assert native["size"] == _FAKE_SIZE
    assert during_provenance == [], (
        "moneta_provenance() opened the native file (%s): the native block "
        "reads size and mtime from os.stat and never hashes" % during_provenance)
    assert sorted(set(control)) == ["builtins.open", "io.open", "os.open"], (
        "the recorder missed a route (%s): the pin above proves nothing" % control)


def test_the_probe_refuses_and_records_an_import(sandbox):
    """Control for every ``probe.attempts == []`` above: with no entry in
    sys.modules, an import of moneta_native reaches the probe, is recorded,
    fails, and leaves nothing behind."""
    with pytest.raises(ImportError):
        importlib.import_module(_NAME)
    assert sandbox.probe.attempts == [_NAME]
    assert _NAME not in sys.modules


def test_the_modules_under_test_are_this_checkouts():
    """Law 1: the moneta_runtime and native_status these tests exercise are the
    files in this checkout, not the editable install's."""
    python_dir = (_ROOT / "python").resolve()
    for module in (mr, native_status_module):
        path = Path(module.__file__).resolve()
        print("BINDING %s -> %s" % (module.__name__, path))
        assert python_dir in path.parents, (
            "%s resolved to %s, outside %s" % (module.__name__, path, python_dir))
