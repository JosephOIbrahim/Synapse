"""MONETA-NATIVE: Doctor names the Rust module this process loaded, and checks its hash.

Live-seat fact (2026-11-09): ``MONETA_NATIVE=1``, and Houdini had loaded
``.../versions/5.99.0-.../dependencies/moneta-native/moneta_native/moneta_native.pyd``
(sha256 ``76789dd4...``, the pinned build). ``synapse_doctor`` printed nothing
about native at all: no module, no file, no hash, no counters.

The ``moneta_native`` check reports ``MONETA_NATIVE``, whether the module is
loaded and from which file, that file's sha256 against the reviewed pin in
``native_artifact.json``, and Moneta's native counters and fallbacks when
Moneta exposes them. ``ok`` is reachable only through a hash comparison that
matched. A hash outside the pin set fails. ``MONETA_NATIVE`` on with Moneta on
its Python oracle fails. Native off by choice, or not loaded yet, is
``skipped`` and the result says which. With no readable pin the verdict is
``unknown``, never ``ok``.

No real native module is loaded by these tests. The module is a
``types.ModuleType`` planted in ``sys.modules`` whose extension file is junk
bytes in ``tmp_path``. An import probe records any attempt to import
``moneta_native`` (there must be none: a status read that imported the wheel
would itself be the load it reports). ``moneta._native`` and the process
memory store are isolated per test, so nothing an earlier test constructed
can decide a verdict here.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.machinery
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

from synapse.server import doctor

_REPO = Path(__file__).resolve().parents[1]
_REPO_POLICY = _REPO / "installer" / "native_artifact.json"
_NAME = "moneta_native"
_MEMBER = "moneta_native/moneta_native.pyd"
# The platform's own extension suffix, so the planted file is recognised as a
# compiled module on every CI runner (.pyd on Windows, .so elsewhere).
_EXT = importlib.machinery.EXTENSION_SUFFIXES[-1]


def _repo_pin() -> str:
    return json.loads(_REPO_POLICY.read_text(encoding="utf-8"))["manifest"]["pyd_sha256"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _ImportProbe:
    """A meta-path finder that would satisfy ``import moneta_native`` with a
    fake, and records every time the import system asks for it."""

    def __init__(self):
        self.attempts = []

    def find_spec(self, name, path=None, target=None):
        if name != _NAME and not name.startswith(_NAME + "."):
            return None
        self.attempts.append(name)
        return importlib.util.spec_from_loader(name, self)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__version__ = "0.0.0+probe"


@pytest.fixture
def probe(monkeypatch):
    finder = _ImportProbe()
    monkeypatch.setattr(sys, "meta_path", [finder, *sys.meta_path])
    yield finder
    for name in (_NAME, _NAME + "." + _NAME):
        if getattr(sys.modules.get(name), "__loader__", None) is finder:
            del sys.modules[name]


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    """No native module, loader state or live store leaks in from elsewhere."""
    monkeypatch.delenv("MONETA_NATIVE", raising=False)
    monkeypatch.delenv("SYNAPSE_MEMORY_BACKEND", raising=False)
    for name in (_NAME, _NAME + "." + _NAME, "moneta._native"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    store_mod = importlib.import_module("synapse.memory.store")
    monkeypatch.setattr(store_mod, "_global_synapse", None)
    yield
    # run_doctor's memory checks publish a real jsonl store; close it here so
    # its handle does not outlive the test (monkeypatch then restores the
    # prior value). A fake planted by a test is left for monkeypatch alone.
    if isinstance(store_mod._global_synapse, store_mod.SynapseMemory):
        store_mod.reset_synapse_memory()


def _plant_native(monkeypatch, root: Path, payload: bytes, *, version="0.1.0",
                  with_extension=True):
    """Plant a maturin-layout ``moneta_native`` package in ``sys.modules``.

    The package's ``__file__`` is its ``__init__.py``; the compiled extension
    is the ``moneta_native.moneta_native`` submodule, exactly as the shipped
    wheel imports. Returns ``(extension_path, sha256)``.
    """
    pkg_dir = root / "site" / _NAME
    pkg_dir.mkdir(parents=True)
    init = pkg_dir / "__init__.py"
    init.write_text("from .moneta_native import *\n", encoding="utf-8")
    ext = pkg_dir / (_NAME + _EXT)
    ext.write_bytes(payload)
    pkg = types.ModuleType(_NAME)
    pkg.__file__ = str(init)
    pkg.__path__ = [str(pkg_dir)]
    pkg.__version__ = version
    monkeypatch.setitem(sys.modules, _NAME, pkg)
    if with_extension:
        sub = types.ModuleType(_NAME + "." + _NAME)
        sub.__file__ = str(ext)
        pkg.moneta_native = sub
        monkeypatch.setitem(sys.modules, _NAME + "." + _NAME, sub)
    return ext, hashlib.sha256(payload).hexdigest()


def _policy(pyd_sha256, external=(), *, schema="synapse-native-policy-1",
            member_sha256=None):
    member = pyd_sha256 if member_sha256 is None else member_sha256
    return {
        "schema": schema,
        "execution_required": True,
        "external_artifacts": [{"files": {_MEMBER: h}} for h in external],
        "manifest": {"pyd_sha256": pyd_sha256, "files": {_MEMBER: member}},
    }


def _dev_tree(root: Path, policy=None) -> str:
    """A checkout: ``<repo>/python/synapse/__init__.py`` + ``installer/``."""
    repo = root / "repo"
    pkg = repo / "python" / "synapse"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    if policy is not None:
        (repo / "installer").mkdir()
        (repo / "installer" / "native_artifact.json").write_text(
            json.dumps(policy), encoding="utf-8")
    return str(pkg / "__init__.py")


def _installed_tree(root: Path, policy=None) -> str:
    """An installed seat: ``<app>/versions/<id>/python/synapse/__init__.py``
    beside ``<app>/maintenance/synapse_setup/native_artifact.json``."""
    app = root / "app"
    pkg = app / "versions" / "5.99.0-0123456789abcdef" / "python" / "synapse"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    if policy is not None:
        setup = app / "maintenance" / "synapse_setup"
        setup.mkdir(parents=True)
        (setup / "native_artifact.json").write_text(json.dumps(policy), encoding="utf-8")
    return str(pkg / "__init__.py")


def _no_sockets(monkeypatch):
    """run_doctor's coexistence check TCP-probes localhost ports. Not here."""
    monkeypatch.setattr(doctor, "_check_mcp_coexistence", lambda base: {
        "name": "mcp_coexistence", "status": "skipped",
        "detail": "stubbed by test_doctor_moneta_native (no socket probes)"})


def _run_doctor_native(tmp_path, monkeypatch):
    _no_sockets(monkeypatch)
    monkeypatch.chdir(tmp_path)
    report = doctor.run_doctor({}, home=tmp_path)
    assert sum(report["summary"].values()) == len(report["checks"])
    by_name = {c["name"]: c for c in report["checks"]}
    assert "moneta_native" in by_name, (
        "Doctor printed nothing about moneta_native (the live-seat finding): "
        f"checks were {sorted(by_name)}")
    return by_name["moneta_native"]


def _fake_loader(monkeypatch, *, state="loaded", reason=None, path=None,
                 sha256=None, counters=None):
    """A stand-in for Moneta 1.3.0's ``moneta._native``: the two read-only
    accessors the check may call. ``wheel_info``/``select`` raise, because
    calling them would run Moneta's import probe."""
    loader = types.ModuleType("moneta._native")

    def current_wheel():
        return types.SimpleNamespace(state=state, reason=reason, version="0.1.0",
                                     api=None, path=path, sha256=sha256,
                                     record_match=None)

    def counters_fn():
        return json.loads(json.dumps(counters or {
            "scan": {"native_calls": 0, "fallbacks": {}},
            "decay": {"native_calls": 0, "fallbacks": {}}}))

    def forbidden(*_a, **_k):
        raise AssertionError("the doctor called a moneta._native function that probes")

    loader.current_wheel = current_wheel
    loader.counters = counters_fn
    loader.wheel_info = loader.native_available = loader.select = forbidden
    monkeypatch.setitem(sys.modules, "moneta._native", loader)
    return loader


# ---------------------------------------------------------------------------
# RED: the check is wired, reports path + hash, and fails off the pin
# ---------------------------------------------------------------------------

def test_doctor_reports_native_path_and_hash_and_fails_off_the_repo_pin(
        tmp_path, monkeypatch, probe):
    """The live-seat gap, through ``run_doctor`` and the REAL reviewed pin.

    A planted module whose extension holds junk bytes must be reported by
    file and sha256, compared with ``installer/native_artifact.json``'s pin
    (resolved from the running package, not mocked), and FAIL. Fails on the
    unmodified tree because run_doctor has no ``moneta_native`` check."""
    ext, sha = _plant_native(monkeypatch, tmp_path, b"junk: not the pinned build")

    check = _run_doctor_native(tmp_path, monkeypatch)

    assert check["status"] == "fail", check
    res = check["result"]
    assert res["verdict"] == "hash_mismatch"
    assert res["module_state"] == "loaded"
    assert res["file"] == str(ext)
    assert res["sha256"] == sha
    assert res["pinned_sha256"] == _repo_pin()
    assert Path(res["pin_source"]).resolve() == _REPO_POLICY.resolve()
    assert res["pin_match"] is None
    assert str(ext) in check["detail"] and sha in check["detail"]
    assert probe.attempts == [], (
        "the doctor asked the import system for %s: a status read must never "
        "import the native module it reports on" % probe.attempts)


def test_doctor_reports_native_ok_only_when_the_loaded_hash_is_pinned(
        tmp_path, monkeypatch, probe):
    """The one ``ok`` path, through ``run_doctor`` and the real resolver: the
    running package sits in a checkout whose ``installer/native_artifact.json``
    pins exactly the loaded extension's sha256. Fails on the unmodified tree
    because run_doctor has no ``moneta_native`` check."""
    ext, sha = _plant_native(monkeypatch, tmp_path, b"the pinned build, in this test")
    package_file = _dev_tree(tmp_path, _policy(sha))
    import synapse
    monkeypatch.setattr(synapse, "__file__", package_file)

    check = _run_doctor_native(tmp_path, monkeypatch)

    assert check["status"] == "ok", check
    res = check["result"]
    assert res["verdict"] == "ok"
    assert res["file"] == str(ext) and res["sha256"] == sha
    assert res["pinned_sha256"] == sha and res["pin_match"] == "bundled_pin"
    assert Path(res["pin_source"]).resolve() == (
        tmp_path / "repo" / "installer" / "native_artifact.json").resolve()
    assert probe.attempts == []


# ---------------------------------------------------------------------------
# Where the pin comes from: the reviewed policy, in both layouts
# ---------------------------------------------------------------------------

def test_the_repo_policy_is_the_pin_the_doctor_reads_in_a_checkout():
    """The real checkout resolves to the real policy, and that policy pins the
    build the live seat loaded (76789dd4...)."""
    import synapse
    pin = doctor._resolve_native_pin(synapse.__file__)
    assert Path(pin["source"]).resolve() == _REPO_POLICY.resolve()
    assert pin["pinned_sha256"] == _repo_pin()
    assert pin["pinned_sha256"].startswith("76789dd4")
    assert pin["error"] is None


def test_an_installed_seat_reads_the_maintenance_copy_of_the_policy(
        tmp_path, monkeypatch):
    ext, sha = _plant_native(monkeypatch, tmp_path, b"installed seat build")
    package_file = _installed_tree(tmp_path, _policy(sha))

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "ok", check
    assert Path(check["result"]["pin_source"]).resolve() == (
        tmp_path / "app" / "maintenance" / "synapse_setup"
        / "native_artifact.json").resolve()


@pytest.mark.parametrize("layout", [_dev_tree, _installed_tree])
def test_no_pin_source_is_unknown_never_ok(tmp_path, monkeypatch, layout):
    ext, sha = _plant_native(monkeypatch, tmp_path, b"loaded, nothing to compare with")
    package_file = layout(tmp_path, policy=None)

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "skipped", check
    res = check["result"]
    assert res["verdict"] == "unknown"
    assert res["sha256"] == sha and res["file"] == str(ext)
    assert res["pin_source"] is None and res["pinned_sha256"] is None
    assert res["pin_sources_tried"], "the paths that were tried must be named"
    assert "UNKNOWN" in check["detail"]


def test_a_package_outside_the_repo_layout_is_unknown(tmp_path, monkeypatch):
    _plant_native(monkeypatch, tmp_path, b"site-packages install")
    loose = tmp_path / "site-packages" / "synapse"
    loose.mkdir(parents=True)
    (loose / "__init__.py").write_text("", encoding="utf-8")

    check = doctor._check_moneta_native(package_file=str(loose / "__init__.py"))

    assert check["status"] == "skipped"
    assert check["result"]["verdict"] == "unknown"
    assert check["result"]["pin_sources_tried"] == []


@pytest.mark.parametrize("policy, why", [
    (_policy("a" * 64, schema="something-else"), "schema"),
    (_policy("a" * 64, member_sha256="b" * 64), "disagree"),
    (_policy("not-a-sha"), "pyd_sha256"),
])
def test_an_unusable_policy_is_unknown_never_ok(tmp_path, monkeypatch, policy, why):
    _plant_native(monkeypatch, tmp_path, b"whatever")
    package_file = _dev_tree(tmp_path, policy)

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "skipped", check
    assert check["result"]["verdict"] == "unknown"
    assert why in check["result"]["pin_error"]


def test_an_unparsable_policy_is_unknown(tmp_path, monkeypatch):
    _plant_native(monkeypatch, tmp_path, b"whatever")
    package_file = _dev_tree(tmp_path, _policy("a" * 64))
    (tmp_path / "repo" / "installer" / "native_artifact.json").write_text(
        "{not json", encoding="utf-8")

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "skipped"
    assert check["result"]["verdict"] == "unknown"
    assert "unreadable" in check["result"]["pin_error"]


def test_an_approved_external_artifact_is_ok_and_named(tmp_path, monkeypatch):
    """The installer accepts the policy's external_artifacts rows for an
    existing wheel (native_policy._external); the dev interpreter's wheel is
    one of them. Ok, but the detail says it is not the bundled pin."""
    ext, sha = _plant_native(monkeypatch, tmp_path, b"an approved external build")
    package_file = _dev_tree(tmp_path, _policy("c" * 64, external=[sha]))

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "ok", check
    assert check["result"]["pin_match"] == "approved_external_artifact"
    assert check["result"]["pinned_sha256"] == "c" * 64
    assert "approved external" in check["detail"]


def test_the_repo_policy_approves_the_two_reviewed_builds_only():
    import synapse
    pin = doctor._resolve_native_pin(synapse.__file__)
    policy = json.loads(_REPO_POLICY.read_text(encoding="utf-8"))
    expected = {policy["manifest"]["pyd_sha256"]} | {
        row["files"][_MEMBER] for row in policy["external_artifacts"]}
    assert set(pin["approved"]) == expected


# ---------------------------------------------------------------------------
# Which file is hashed
# ---------------------------------------------------------------------------

def test_the_package_init_is_never_hashed_as_the_extension(tmp_path, monkeypatch):
    """A loaded package with no compiled submodule: the ``__init__.py`` is not
    the pyd, so nothing is hashed and nothing can be ok."""
    _plant_native(monkeypatch, tmp_path, b"never read", with_extension=False)
    init = tmp_path / "site" / _NAME / "__init__.py"
    package_file = _dev_tree(tmp_path, _policy(
        hashlib.sha256(init.read_bytes()).hexdigest()))

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "skipped", check
    assert check["result"]["verdict"] == "unknown"
    assert check["result"]["sha256"] is None
    assert check["result"]["package_file"] == str(init)


def test_a_moneta_load_time_hash_that_disagrees_with_the_disk_fails(
        tmp_path, monkeypatch):
    ext, sha = _plant_native(monkeypatch, tmp_path, b"what is on disk now")
    package_file = _dev_tree(tmp_path, _policy(sha))
    _fake_loader(monkeypatch, path=str(ext), sha256="d" * 64)

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "fail", check
    assert check["result"]["verdict"] == "hash_mismatch"
    assert check["result"]["moneta_probe"]["sha256"] == "d" * 64


# ---------------------------------------------------------------------------
# MONETA_NATIVE: off by choice, not loaded yet, fell back to Python
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["0", "false", "OFF", " no "])
def test_off_by_choice_and_blocked_is_skipped_and_says_so(monkeypatch, value):
    monkeypatch.setenv("MONETA_NATIVE", value)
    monkeypatch.setitem(sys.modules, _NAME, None)

    check = doctor._check_moneta_native()

    assert check["status"] == "skipped", check
    res = check["result"]
    assert res["verdict"] == "off_by_choice"
    assert res["env_class"] == "off" and res["env_MONETA_NATIVE"] == value
    assert res["module_state"] == "blocked"
    assert "off by choice" in check["detail"]


def test_off_by_choice_with_the_module_already_loaded_is_skipped_not_ok(
        tmp_path, monkeypatch):
    """SYNAPSE's kill switch arms only on exactly "0"; "false" is OFF to
    Moneta 1.3.0, yet the module can still be loaded. Skipped, and the detail
    says the module is in the process anyway."""
    monkeypatch.setenv("MONETA_NATIVE", "false")
    ext, sha = _plant_native(monkeypatch, tmp_path, b"loaded but unused")
    package_file = _dev_tree(tmp_path, _policy(sha))

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "skipped", check
    assert check["result"]["verdict"] == "off_by_choice"
    assert check["result"]["sha256"] == sha
    assert "loaded" in check["detail"]


def test_zero_with_the_module_already_loaded_names_the_kill_switch(
        tmp_path, monkeypatch):
    """Exactly "0" arms SYNAPSE's kill switch, which cannot unload a module
    that loaded before it ran (moneta_runtime: "already_loaded")."""
    monkeypatch.setenv("MONETA_NATIVE", "0")
    ext, sha = _plant_native(monkeypatch, tmp_path, b"loaded before the switch")
    package_file = _dev_tree(tmp_path, _policy(sha))

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "skipped", check
    assert check["result"]["verdict"] == "off_by_choice"
    assert "already loaded" in check["detail"]


def test_an_unreadable_module_state_is_unknown(monkeypatch):
    native_status_mod = importlib.import_module("synapse.memory.native_status")
    monkeypatch.setenv("MONETA_NATIVE", "1")
    monkeypatch.setattr(native_status_mod, "native_status", lambda handle=None: {
        "state": None, "file": None, "version": None, "error": "RuntimeError('boom')",
        "handle_via": None, "vector_backend": None, "native_decay": None})

    check = doctor._check_moneta_native()

    assert check["status"] == "skipped", check
    assert check["result"]["verdict"] == "unknown"
    assert "boom" in check["detail"]


def test_off_by_choice_does_not_excuse_an_unpinned_binary(tmp_path, monkeypatch):
    monkeypatch.setenv("MONETA_NATIVE", "0")
    _plant_native(monkeypatch, tmp_path, b"unpinned, loaded before the switch ran")
    package_file = _dev_tree(tmp_path, _policy("e" * 64))

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "fail", check
    assert check["result"]["verdict"] == "hash_mismatch"


@pytest.mark.parametrize("value", [None, "1", "auto", "require", "maybe"])
def test_on_but_not_loaded_yet_is_skipped_and_says_so(monkeypatch, value):
    if value is not None:
        monkeypatch.setenv("MONETA_NATIVE", value)

    check = doctor._check_moneta_native()

    assert check["status"] == "skipped", check
    res = check["result"]
    assert res["verdict"] == "not_loaded_yet"
    assert res["module_state"] == "not_loaded"
    assert res["sha256"] is None
    assert "not loaded yet" in check["detail"]
    if value == "maybe":
        assert res["env_class"] == "unknown"


@pytest.mark.parametrize("state", ["absent", "broken", "incompatible"])
def test_on_and_moneta_probed_a_missing_wheel_is_a_python_fallback(
        monkeypatch, state):
    monkeypatch.setenv("MONETA_NATIVE", "1")
    _fake_loader(monkeypatch, state=state, reason="ModuleNotFoundError: no wheel")

    check = doctor._check_moneta_native()

    assert check["status"] == "fail", check
    assert check["result"]["verdict"] == "python_fallback"
    assert state in check["detail"]


def test_on_but_blocked_is_a_python_fallback(monkeypatch):
    monkeypatch.setenv("MONETA_NATIVE", "1")
    monkeypatch.setitem(sys.modules, _NAME, None)

    check = doctor._check_moneta_native()

    assert check["status"] == "fail", check
    assert check["result"]["verdict"] == "python_fallback"
    assert "blocked" in check["detail"]


def test_counters_and_per_query_oracle_answers_are_reported_not_failed(
        tmp_path, monkeypatch):
    """Moneta's own rule: a scan's per-query oracle answer (non-finite query,
    cosine overflow) is permitted even under require. Reported, not failed."""
    monkeypatch.setenv("MONETA_NATIVE", "1")
    ext, sha = _plant_native(monkeypatch, tmp_path, b"pinned and busy")
    package_file = _dev_tree(tmp_path, _policy(sha))
    counters = {"scan": {"native_calls": 12, "fallbacks": {"cosine_overflow": 2}},
                "decay": {"native_calls": 5, "fallbacks": {}}}
    _fake_loader(monkeypatch, path=str(ext), sha256=sha, counters=counters)

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "ok", check
    assert check["result"]["counters"] == counters
    assert check["result"]["moneta_probe"]["state"] == "loaded"
    assert "cosine_overflow" in check["detail"]


@pytest.mark.parametrize("counters, needle", [
    ({"scan": {"native_calls": 3, "fallbacks": {}},
      "decay": {"native_calls": 1, "fallbacks": {"error:PanicException": 1}}},
     "decay"),
    ({"scan": {"native_calls": 3, "fallbacks": {"demoted:query_nonfinite": 1}},
      "decay": {"native_calls": 1, "fallbacks": {}}},
     "demoted"),
])
def test_decay_fallbacks_and_demotions_are_a_python_fallback(
        tmp_path, monkeypatch, counters, needle):
    monkeypatch.setenv("MONETA_NATIVE", "1")
    ext, sha = _plant_native(monkeypatch, tmp_path, b"pinned, but fell back")
    package_file = _dev_tree(tmp_path, _policy(sha))
    _fake_loader(monkeypatch, path=str(ext), sha256=sha, counters=counters)

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "fail", check
    assert check["result"]["verdict"] == "python_fallback"
    assert needle in check["detail"]


def _live_store(monkeypatch, handle):
    store_mod = importlib.import_module("synapse.memory.store")
    store = types.SimpleNamespace(_handle=handle)
    monkeypatch.setattr(store_mod, "_global_synapse", types.SimpleNamespace(store=store))


def test_a_live_store_on_the_python_scan_is_a_python_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("MONETA_NATIVE", "1")
    ext, sha = _plant_native(monkeypatch, tmp_path, b"pinned, store on python")
    package_file = _dev_tree(tmp_path, _policy(sha))
    _live_store(monkeypatch, types.SimpleNamespace(
        vector_index=types.SimpleNamespace(backend="python"),
        ecs=types.SimpleNamespace(native_decay=True)))

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "fail", check
    assert check["result"]["verdict"] == "python_fallback"
    assert check["result"]["live_store"]["vector_backend"] == "python"


def test_a_demoted_seam_on_a_live_handle_is_a_python_fallback(tmp_path, monkeypatch):
    """Moneta 1.3.0 exposes ``handle.native_status`` (scan/decay seams)."""
    monkeypatch.setenv("MONETA_NATIVE", "1")
    ext, sha = _plant_native(monkeypatch, tmp_path, b"pinned, seam demoted")
    package_file = _dev_tree(tmp_path, _policy(sha))

    def seam(name, active, demoted, fallbacks):
        return types.SimpleNamespace(seam=name, requested="auto", active=active,
                                     reason=None if active == "native" else "demoted:x",
                                     demoted=demoted, native_calls=4,
                                     fallbacks=fallbacks, all_native=False)

    handle = types.SimpleNamespace(
        vector_index=types.SimpleNamespace(backend="native"),
        ecs=types.SimpleNamespace(native_decay=True),
        native_status=types.SimpleNamespace(
            scan=seam("scan", "native", False, {}),
            decay=seam("decay", "python", True, {"error:ValueError": 1})))
    _live_store(monkeypatch, handle)

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "fail", check
    assert check["result"]["verdict"] == "python_fallback"
    assert check["result"]["live_store"]["seams"]["decay"]["demoted"] is True


def test_a_live_store_on_native_seams_stays_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("MONETA_NATIVE", "1")
    ext, sha = _plant_native(monkeypatch, tmp_path, b"pinned and native")
    package_file = _dev_tree(tmp_path, _policy(sha))
    _live_store(monkeypatch, types.SimpleNamespace(
        vector_index=types.SimpleNamespace(backend="native"),
        ecs=types.SimpleNamespace(native_decay=True)))

    check = doctor._check_moneta_native(package_file=package_file)

    assert check["status"] == "ok", check
    assert check["result"]["live_store"]["vector_backend"] == "native"


def test_the_check_never_raises_and_always_has_a_detail(monkeypatch):
    """A broken reading degrades to skipped with a reason; run_doctor's
    summary only knows ok / fail / skipped."""
    def boom(*_a, **_k):
        raise RuntimeError("reader exploded")
    monkeypatch.setattr(doctor, "_resolve_native_pin", boom)

    check = doctor._check_moneta_native()

    assert check["status"] == "skipped"
    assert "reader exploded" in check["detail"]
