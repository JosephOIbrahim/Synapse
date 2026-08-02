"""The write-plane field on ``get_health`` — the monitoring blind spot.

Background: on 2026-08-02 ``memory_write`` failed with ``PermissionError
WinError 5`` while ``get_health`` answered ``healthy: true``. These tests pin
the fix (``synapse/server/write_plane.py``) and, just as importantly, pin the
EXISTING health contract so the improvement cannot silently break a consumer.

The classification tests inject the refusal (``wp._probe_open`` raising
``PermissionError``) rather than building an ACL-denied directory: what is
under test is how SYNAPSE *classifies* a refusal. The ``ok`` path is real I/O
against a real ``tmp_path``. The REAL ACL-denied case is additionally pinned
on Windows with a wall-clock bound (test_probe_bounded_on_real_acl_denied_dir)
because the first version of this module hung ~43 hours on exactly that case
while these mock-seam tests stayed green — a mock seam can never see the
primitive's own pathology, so the primitive is pinned separately
(test_probe_never_uses_mkstemp).
"""

from __future__ import annotations

import os
import tempfile

import pytest

import synapse.server.write_plane as wp
from synapse.server.handlers import (
    HOU_AVAILABLE,
    PROTOCOL_VERSION,
    SynapseHandler,
    _READ_ONLY_COMMANDS,
)


@pytest.fixture
def targets(tmp_path, monkeypatch):
    """Point both write targets at real, writable tmp dirs."""
    mem = tmp_path / "scene" / ".synapse"
    mem.mkdir(parents=True)
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(wp, "resolve_memory_target_dir", lambda: mem)
    monkeypatch.setenv("SYNAPSE_REPORTS_DIR", str(reports))
    monkeypatch.setattr(wp, "_backend_fallback", lambda: None)
    return mem, reports


# ---------------------------------------------------------------------------
# ok
# ---------------------------------------------------------------------------

def test_ok_when_every_target_is_writable(targets):
    mem, reports = targets
    state = wp.write_plane_state()
    assert state["status"] == "ok"
    assert state["reason"] is None
    assert state["backend_fallback"] is None
    assert state["targets"]["memory"]["writable"] is True
    assert state["targets"]["reports"]["writable"] is True
    assert state["targets"]["memory"]["path"] == str(mem)
    assert state["targets"]["reports"]["path"] == str(reports)


def test_probe_leaves_no_artifact_behind(targets):
    """The probe writes, but nothing durable survives it."""
    mem, reports = targets
    before = {p: sorted(os.listdir(p)) for p in (mem, reports)}
    wp.write_plane_state()
    for p in (mem, reports):
        assert sorted(os.listdir(p)) == before[p]


def test_probe_targets_the_dir_that_would_be_created(tmp_path, monkeypatch):
    """A store dir that does not exist yet is probed at its nearest existing
    ancestor — that is where ``mkdir(parents=True)`` has to succeed."""
    scene = tmp_path / "scene"
    scene.mkdir()
    not_yet = scene / ".synapse"
    monkeypatch.setattr(wp, "resolve_memory_target_dir", lambda: not_yet)
    monkeypatch.setenv("SYNAPSE_REPORTS_DIR", str(scene))
    monkeypatch.setattr(wp, "_backend_fallback", lambda: None)

    state = wp.write_plane_state()
    assert state["status"] == "ok"
    assert state["targets"]["memory"]["path"] == str(not_yet)
    assert state["targets"]["memory"]["probed"] == str(scene)


# ---------------------------------------------------------------------------
# degraded
# ---------------------------------------------------------------------------

def test_degraded_when_a_target_is_unwritable(targets, monkeypatch):
    """The WinError 5 shape: the OS refuses the create.

    Injection seam is ``wp._probe_open`` — the single non-retrying create —
    NOT ``tempfile.mkstemp``. mkstemp is banned from the probe path (its retry
    loop spins ~43h on a real ACL-denied dir; see the module docstring and
    test_probe_never_uses_mkstemp below).
    """
    mem, _reports = targets
    real_open = wp._probe_open

    def denied(tmp_path):
        if os.path.dirname(tmp_path) == str(mem):
            raise PermissionError(13, "Access is denied")
        return real_open(tmp_path)

    monkeypatch.setattr(wp, "_probe_open", denied)

    state = wp.write_plane_state()
    assert state["status"] == "degraded"
    assert state["targets"]["memory"]["writable"] is False
    assert state["targets"]["reports"]["writable"] is True
    assert "memory dir not writable" in state["reason"]
    assert str(mem) in state["reason"]
    assert "Access is denied" in state["reason"]


def test_degraded_when_backend_silently_fell_back(targets, monkeypatch):
    """PR #60's ``backend_fallback()`` is wired in, not re-detected: a process
    serving jsonl while moneta was selected is NOT an ok write plane."""
    fallback = {
        "requested": "moneta",
        "served": "jsonl",
        "storage_dir": "C:/nope",
        "reason": "Moneta not importable: ModuleNotFoundError: moneta",
        "at": "2026-08-02 12:00:00",
    }
    monkeypatch.setattr(wp, "_backend_fallback", lambda: fallback)

    state = wp.write_plane_state()
    assert state["status"] == "degraded"
    assert state["backend_fallback"] == fallback
    assert "moneta" in state["reason"]
    assert "fell back" in state["reason"]
    # ...even though both directories accepted a write.
    assert state["targets"]["memory"]["writable"] is True
    assert state["targets"]["reports"]["writable"] is True


def test_degraded_outranks_unknown(targets, monkeypatch):
    """A demonstrated break is never downgraded to 'could not tell'."""
    mem, _reports = targets

    def half_broken(path):
        if str(path) == str(mem):
            return False, str(path), "PermissionError: Access is denied"
        return None, None, "no existing ancestor directory to probe"

    monkeypatch.setattr(wp, "probe_dir_writable", half_broken)
    assert wp.write_plane_state()["status"] == "degraded"


# ---------------------------------------------------------------------------
# unknown — a legitimate answer, and never 'ok'
# ---------------------------------------------------------------------------

def test_unknown_when_the_check_raises(targets, monkeypatch):
    def boom(path):
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(wp, "probe_dir_writable", boom)

    state = wp.write_plane_state()
    assert state["status"] == "unknown"
    assert "probe exploded" in state["reason"]


def test_unknown_when_the_target_cannot_be_resolved(targets, monkeypatch):
    def boom():
        raise RuntimeError("no scene, no store")

    monkeypatch.setattr(wp, "resolve_memory_target_dir", boom)

    state = wp.write_plane_state()
    assert state["status"] == "unknown"
    assert "no scene, no store" in state["reason"]


def test_unknown_when_nothing_in_the_path_exists(targets, monkeypatch):
    monkeypatch.setattr(wp, "_nearest_existing_dir", lambda p: None)

    state = wp.write_plane_state()
    assert state["status"] == "unknown"
    assert "no existing ancestor" in state["reason"]
    assert state["targets"]["memory"]["writable"] is None


def test_unreadable_fallback_state_is_unknown_not_ok(targets, monkeypatch):
    def boom():
        raise RuntimeError("store module import failed")

    monkeypatch.setattr(wp, "_backend_fallback", boom)

    state = wp.write_plane_state()
    assert state["status"] == "unknown"
    assert "unreadable" in state["reason"]


def test_write_plane_state_never_raises(monkeypatch):
    """Health is called constantly; it must not become a failure source."""
    monkeypatch.setattr(wp, "resolve_reports_base_dir", lambda: (_ for _ in ()).throw(OSError("x")))
    monkeypatch.setattr(wp, "_backend_fallback", lambda: None)
    assert wp.write_plane_state()["status"] == "unknown"


# ---------------------------------------------------------------------------
# The bounded ancestor walk
# ---------------------------------------------------------------------------

def test_ancestor_walk_is_bounded(tmp_path):
    deep = tmp_path
    for i in range(wp._MAX_ANCESTOR_WALK + 5):
        deep = deep / f"d{i}"
    # Nothing below tmp_path exists and the walk gives up before reaching it.
    assert wp._nearest_existing_dir(deep) is None


def test_ancestor_walk_finds_an_existing_dir(tmp_path):
    assert wp._nearest_existing_dir(tmp_path / "a" / "b") == tmp_path


# ---------------------------------------------------------------------------
# The EXISTING health contract — additive only
# ---------------------------------------------------------------------------

def test_health_keys_are_additive(targets):
    """Pins the pre-existing contract. ``write_plane`` is the ONLY new key and
    the three original keys keep their original meanings — breaking a consumer
    to improve a signal is a net loss."""
    data = SynapseHandler()._handle_get_health({})
    assert set(data) == {
        "healthy",
        "houdini_available",
        "protocol_version",
        "write_plane",
    }
    assert data["healthy"] is True
    assert data["houdini_available"] is HOU_AVAILABLE
    assert data["protocol_version"] == PROTOCOL_VERSION


def test_healthy_stays_true_when_the_write_plane_is_degraded(targets, monkeypatch):
    """``healthy`` is a liveness answer and is NOT repurposed. The degradation
    is reported in its own field — consumers opt in."""
    monkeypatch.setattr(
        wp, "_backend_fallback",
        lambda: {"requested": "moneta", "reason": "not importable"},
    )
    data = SynapseHandler()._handle_get_health({})
    assert data["healthy"] is True
    assert data["write_plane"]["status"] == "degraded"


def test_get_health_is_still_classified_read_only(targets):
    """The probe writes, but leaves no durable artifact — see the read-only
    tension documented in ``write_plane``'s module docstring. If this ever has
    to change, reclassify the command; do not weaken the probe."""
    assert "get_health" in _READ_ONLY_COMMANDS


# ---------------------------------------------------------------------------
# Drift guard: health must probe the dir reports actually land in
# ---------------------------------------------------------------------------

def test_write_report_and_health_share_one_reports_resolver(tmp_path, monkeypatch):
    """A second copy of the base-dir logic is how health starts reporting on a
    directory nothing writes to. One resolver, pinned by behaviour."""
    chosen = tmp_path / "elsewhere"
    chosen.mkdir()
    monkeypatch.setattr(wp, "resolve_reports_base_dir", lambda: str(chosen))
    monkeypatch.setattr(wp, "resolve_memory_target_dir", lambda: chosen)
    monkeypatch.setattr(wp, "_backend_fallback", lambda: None)

    handler = SynapseHandler()
    result = handler._handle_write_report(
        {"relative_path": "probe/report.md", "content": "hello"}
    )
    written = os.path.abspath(result["path"])
    assert written.startswith(os.path.abspath(str(chosen)))

    state = wp.write_plane_state()
    assert state["targets"]["reports"]["path"] == str(chosen)


def test_reports_resolver_honours_the_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_REPORTS_DIR", str(tmp_path))
    assert wp.resolve_reports_base_dir() == str(tmp_path)


def test_reports_resolver_defaults_to_repo_docs(monkeypatch):
    monkeypatch.delenv("SYNAPSE_REPORTS_DIR", raising=False)
    resolved = wp.resolve_reports_base_dir()
    assert os.path.basename(resolved) == "docs"
    assert os.path.isdir(resolved)


# ---------------------------------------------------------------------------
# The doctor refactor this lane leaned on must not have changed behaviour
# ---------------------------------------------------------------------------

def test_store_dir_resolution_is_unchanged_by_the_split(tmp_path, monkeypatch):
    """``doctor._resolve_store_dir`` still returns an existing store dir, and
    still returns None when there is none — the split only exposed the base."""
    from synapse.server import doctor

    scene = tmp_path / "scene"
    scene.mkdir()
    monkeypatch.setattr(doctor, "_resolve_store_base_dir", lambda: scene)
    assert doctor._resolve_store_dir() is None

    (scene / ".synapse").mkdir()
    assert doctor._resolve_store_dir() == scene / ".synapse"


def test_memory_target_falls_back_to_the_dir_that_would_be_created(tmp_path, monkeypatch):
    from synapse.server import doctor

    scene = tmp_path / "scene"
    scene.mkdir()
    monkeypatch.setattr(doctor, "_resolve_store_base_dir", lambda: scene)
    assert wp.resolve_memory_target_dir() == scene / ".synapse"

    (scene / ".synapse").mkdir()
    assert wp.resolve_memory_target_dir() == scene / ".synapse"


# ---------------------------------------------------------------------------
# G1b crucible pins — the primitive itself, not just the classification
# ---------------------------------------------------------------------------

def test_probe_never_uses_mkstemp(tmp_path, monkeypatch):
    """mkstemp is BANNED from the probe path.

    Its retry loop trusts os.access(W_OK) — which lies on Windows ACL-denied
    dirs — and retries PermissionError up to TMP_MAX (2**31-1) times: the
    crucible measured ~43 hours of spin on the health call, on the transport
    event loop, pre-RBAC. This pin makes reintroducing it a test failure, not
    a studio incident.
    """
    def _banned(*_a, **_k):  # pragma: no cover - the whole point is no call
        raise AssertionError(
            "tempfile.mkstemp reached the probe path - banned, see docstring")

    monkeypatch.setattr(tempfile, "mkstemp", _banned)
    writable, probed, detail = wp.probe_dir_writable(tmp_path)
    assert writable is True and probed == str(tmp_path) and detail is None
    assert not list(tmp_path.glob(f"{wp._PROBE_PREFIX}*")), "probe file leaked"


@pytest.mark.skipif(os.name != "nt", reason="icacls / Windows ACL semantics")
def test_probe_bounded_on_real_acl_denied_dir(tmp_path):
    """THE crucible reproduction: a genuinely ACL-write-denied directory.

    The old mkstemp probe never returned on this fixture (~43h projected).
    The contract now: returns within seconds, verdict False, and the detail
    carries the REAL refusal — not mkstemp's bogus name-collision message.
    """
    import getpass
    import subprocess
    import threading as _threading
    import time as _time

    denied = tmp_path / "denied"
    denied.mkdir()
    user = getpass.getuser()
    rc = subprocess.run(
        ["icacls", str(denied), "/deny", f"{user}:(WD,AD)"],
        capture_output=True, text=True).returncode
    if rc != 0:
        pytest.skip("icacls could not deny on this seat")
    try:
        result = {}

        def _run():
            result["r"] = wp.probe_dir_writable(denied)

        t = _threading.Thread(target=_run, daemon=True)
        start = _time.perf_counter()
        t.start()
        t.join(timeout=10.0)
        elapsed = _time.perf_counter() - start
        assert not t.is_alive(), (
            f"probe still running after {elapsed:.1f}s on an ACL-denied dir "
            f"- the 43-hour spin is back")
        writable, probed, detail = result["r"]
        assert writable is False
        assert probed == str(denied)
        assert "PermissionError" in detail or "Access is denied" in detail, (
            f"detail must carry the real refusal, got: {detail}")
        assert elapsed < 5.0, f"probe took {elapsed:.2f}s - bounded means fast"
    finally:
        subprocess.run(["icacls", str(denied), "/remove:d", user],
                       capture_output=True, text=True)


def test_memory_resolver_marshals_off_main_when_hou_is_live(monkeypatch, tmp_path):
    """Off the main thread with a live hou, resolution rides run_on_main.

    The lane's original commit claimed 'no hou call'; the crucible refuted it
    (hou.hipFile.path recorded on ws-handler-thread). The contract now: the
    hou-touching resolution is marshalled, same as every other hou-reading
    handler.
    """
    import sys
    import threading as _threading
    import types

    fake_hou = types.ModuleType("hou")
    monkeypatch.setitem(sys.modules, "hou", fake_hou)

    calls = {}

    def fake_run_on_main(fn, timeout=None, label=None, **_k):
        calls["used"] = True
        calls["timeout"] = timeout
        calls["thread"] = _threading.current_thread().name
        return tmp_path / ".synapse"

    # importlib.import_module, NOT 'from synapse.server import main_thread':
    # the from-import binds the PACKAGE ATTRIBUTE, while the code under
    # test's call-time relative import binds the SYS.MODULES entry. Some
    # test orderings leave those divergent, and a patch on the package
    # attribute then lands on an object production never reads (this test
    # failed exactly that way in the full suite, m-group ordering).
    import importlib
    mt = importlib.import_module("synapse.server.main_thread")
    monkeypatch.setattr(mt, "run_on_main", fake_run_on_main)

    result = {}

    def _off_main():
        result["path"] = wp.resolve_memory_target_dir()

    t = _threading.Thread(target=_off_main, name="fake-ws-handler", daemon=True)
    t.start()
    t.join(timeout=10.0)
    assert not t.is_alive()
    assert calls.get("used") is True, "off-main + live hou must marshal"
    assert calls["timeout"] == wp._RESOLVE_TIMEOUT_S, "marshal must be bounded"
    assert result["path"] == tmp_path / ".synapse"


def test_memory_resolver_direct_on_main_thread(monkeypatch, tmp_path):
    """On the main thread the resolver never marshals (marshal-deadlock class:
    a blocking marshal FROM main self-deadlocks on H22)."""
    import sys
    import types

    fake_hou = types.ModuleType("hou")
    monkeypatch.setitem(sys.modules, "hou", fake_hou)

    def _boom(*_a, **_k):  # pragma: no cover
        raise AssertionError("run_on_main called from the main thread")

    # importlib.import_module, NOT 'from synapse.server import main_thread':
    # the from-import binds the PACKAGE ATTRIBUTE, while the code under
    # test's call-time relative import binds the SYS.MODULES entry. Some
    # test orderings leave those divergent, and a patch on the package
    # attribute then lands on an object production never reads (this test
    # failed exactly that way in the full suite, m-group ordering).
    import importlib
    mt = importlib.import_module("synapse.server.main_thread")
    monkeypatch.setattr(mt, "run_on_main", _boom)
    monkeypatch.setattr(wp, "_resolve_via_doctor", lambda: tmp_path / ".synapse")

    assert wp.resolve_memory_target_dir() == tmp_path / ".synapse"


def test_resolver_failure_degrades_one_target_not_the_whole_verdict(
        targets, monkeypatch):
    """A busy-main marshal timeout on the memory resolver must not blank the
    reports verdict: one unresolvable target -> that target unclear, the rest
    still probed."""
    def _busy():
        raise RuntimeError("main thread busy (simulated marshal timeout)")

    monkeypatch.setattr(wp, "resolve_memory_target_dir", _busy)
    state = wp.write_plane_state()
    assert state["targets"]["memory"]["writable"] is None
    assert "unresolvable" in state["reason"]
    assert state["targets"]["reports"]["writable"] is True
    assert state["status"] == "unknown"
