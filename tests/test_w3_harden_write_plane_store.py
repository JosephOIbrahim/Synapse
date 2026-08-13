"""W3-HARDEN target 3 — write_plane reflects STORE health, not just the bridge.

Spec: ``docs/SYNAPSE-memory-engineering-spec.md`` §8 Phase 6 — *"Telemetry:
doctor reports ``write_plane`` for the STORE, not just the bridge."* Acceptance:
*"doctor's memory section reads all-ok AND write-plane is independently
verified."*

Crucible seam (W3-HARDEN mission ``crucible_criteria``): *"a degraded store with
a healthy bridge must show degraded — crucible attacks this seam directly."*

These tests inject a LIVE store object (via ``store._global_synapse``) and prove
the ``write_plane`` verdict is derived from that object's real state — surviving
a ``backend_fallback()`` flag that is None (``_make_store`` resets it on every
construction, so a real fallback can be blanked; the serving CLASS cannot be).
The directory probes are pointed at writable temp dirs and the fallback flag is
forced None, so ONLY the store-object signal can move the verdict.
"""

from __future__ import annotations

import types

import pytest

import synapse.server.write_plane as wp
from synapse.memory import store as store_mod
from synapse.memory.store import MemoryStore
from synapse.server.handlers import SynapseHandler


@pytest.fixture
def writable_dirs(tmp_path, monkeypatch):
    """Both write TARGETS are healthy; only the store object can degrade."""
    mem = tmp_path / "scene" / ".synapse"
    mem.mkdir(parents=True)
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(wp, "resolve_memory_target_dir", lambda: mem)
    monkeypatch.setenv("SYNAPSE_REPORTS_DIR", str(reports))
    monkeypatch.setattr(wp, "_backend_fallback", lambda: None)
    return mem, reports


def _inject_live_store(monkeypatch, backend):
    """Make ``_live_store()`` see *backend* as the process's serving store."""
    monkeypatch.setattr(store_mod, "_global_synapse",
                        types.SimpleNamespace(store=backend), raising=False)


# ---------------------------------------------------------------------------
# no live store -> evaluated=False, verdict unchanged (ok stays ok)
# ---------------------------------------------------------------------------

def test_no_live_store_contributes_nothing(writable_dirs, monkeypatch):
    monkeypatch.setattr(store_mod, "_global_synapse", None, raising=False)
    state = wp.write_plane_state()
    assert state["status"] == "ok"
    assert state["store"]["evaluated"] is False
    assert "no memory store" in state["store"]["reason"]


# ---------------------------------------------------------------------------
# THE crucible seam: a jsonl store serving while moneta was selected, with the
# fallback flag None (missed) and both dirs writable -> DEGRADED anyway.
# ---------------------------------------------------------------------------

def test_jsonl_serving_while_moneta_requested_is_degraded(
        writable_dirs, tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    jsonl = MemoryStore(tmp_path / "jsonl_store", background_load=False)
    _inject_live_store(monkeypatch, jsonl)

    state = wp.write_plane_state()
    assert state["status"] == "degraded", state
    assert state["store"]["evaluated"] is True
    assert state["store"]["serving_jsonl"] is True
    assert "not the one serving" in state["reason"]
    # ...even though the fallback flag was clean and both dirs accepted a write.
    assert state["backend_fallback"] is None
    assert state["targets"]["memory"]["writable"] is True
    assert state["targets"]["reports"]["writable"] is True


def test_store_count_raising_is_degraded(writable_dirs, monkeypatch):
    class Unenumerable:
        def count(self):
            raise RuntimeError("index corrupt")

    _inject_live_store(monkeypatch, Unenumerable())
    state = wp.write_plane_state()
    assert state["status"] == "degraded"
    assert state["store"]["count"] is None
    assert "cannot be enumerated" in state["reason"]


def test_moneta_store_without_engine_handle_is_degraded(writable_dirs, monkeypatch):
    # Latent-safety guard (adversarial P3-b): a Moneta-classed store whose
    # _handle is None can neither persist nor read — degraded, not silently ok.
    class MonetaBackedStore:  # noqa: N801 — name is the signal under test
        _handle = None

        def count(self):
            return 0

    _inject_live_store(monkeypatch, MonetaBackedStore())
    state = wp.write_plane_state()
    assert state["status"] == "degraded"
    assert state["store"]["durable"] is False
    assert "no engine handle" in state["reason"]


def test_moneta_store_without_durability_is_degraded(writable_dirs, monkeypatch):
    # A stand-in whose class name is the Moneta adapter's and whose handle has
    # no durability layer — RAM-only deposits, a real write-plane degradation.
    class MonetaBackedStore:  # noqa: N801 — name is the signal under test
        def __init__(self):
            self._handle = types.SimpleNamespace(durability=None)

        def count(self):
            return 5

    _inject_live_store(monkeypatch, MonetaBackedStore())
    state = wp.write_plane_state()
    assert state["status"] == "degraded"
    assert state["store"]["durable"] is False
    assert "RAM-only" in state["reason"]


# ---------------------------------------------------------------------------
# a genuinely healthy store keeps the verdict ok AND surfaces store evidence
# (so 'ok' is demonstrably store-derived, not merely dir-derived)
# ---------------------------------------------------------------------------

def test_healthy_jsonl_store_stays_ok_with_store_evidence(
        writable_dirs, tmp_path, monkeypatch):
    monkeypatch.delenv("SYNAPSE_MEMORY_BACKEND", raising=False)  # default jsonl
    jsonl = MemoryStore(tmp_path / "ok_store", background_load=False)
    _inject_live_store(monkeypatch, jsonl)

    state = wp.write_plane_state()
    assert state["status"] == "ok"
    assert state["store"]["evaluated"] is True
    assert state["store"]["status"] == "ok"
    assert state["store"]["serving_class"] == "MemoryStore"
    assert state["store"]["count"] == 0


# ---------------------------------------------------------------------------
# healthy BRIDGE liveness stays true while the STORE reads degraded
# (the exact 'green light over a broken product' this field exists to kill)
# ---------------------------------------------------------------------------

def test_healthy_bridge_stays_true_when_store_is_degraded(
        writable_dirs, tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    jsonl = MemoryStore(tmp_path / "jsonl_store", background_load=False)
    _inject_live_store(monkeypatch, jsonl)

    data = SynapseHandler()._handle_get_health({})
    assert data["healthy"] is True  # liveness is NOT repurposed
    assert data["write_plane"]["status"] == "degraded"
    assert data["write_plane"]["store"]["evaluated"] is True


# ---------------------------------------------------------------------------
# the DOCTOR (not only health) reports write_plane for the store
# ---------------------------------------------------------------------------

def test_doctor_check_reports_store_degraded(writable_dirs, tmp_path, monkeypatch):
    from synapse.server import doctor

    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    jsonl = MemoryStore(tmp_path / "jsonl_store", background_load=False)
    _inject_live_store(monkeypatch, jsonl)

    check = doctor._check_write_plane_store()
    assert check["name"] == "write_plane_store"
    assert check["status"] == "fail"  # degraded -> fail
    assert "write_plane=degraded" in check["detail"]
    assert check["result"]["write_plane"]["store"]["evaluated"] is True


def test_doctor_check_is_wired_into_run_doctor():
    """The check must actually be in the doctor's check list (target-3 literal:
    'doctor reports write_plane for the store')."""
    import inspect

    from synapse.server import doctor

    src = inspect.getsource(doctor.run_doctor)
    assert "_check_write_plane_store()" in src


def test_doctor_check_unknown_maps_to_skipped_never_ok(writable_dirs, monkeypatch):
    """House rule: a could-not-tell is 'skipped', never a false ok."""
    from synapse.server import doctor

    monkeypatch.setattr(doctor, "write_plane_state",
                        lambda: {"status": "unknown", "reason": "busy main",
                                 "store": {"evaluated": False}},
                        raising=False)
    # patch the imported symbol at call site: _check imports write_plane_state
    # from .write_plane, so patch there.
    import synapse.server.write_plane as _wp
    monkeypatch.setattr(_wp, "write_plane_state",
                        lambda: {"status": "unknown", "reason": "busy main",
                                 "store": {"evaluated": False}})
    check = doctor._check_write_plane_store()
    assert check["status"] == "skipped"
