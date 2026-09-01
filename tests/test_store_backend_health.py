"""BP2-STORE T2/T3 -- honest memory-backend health (``store.backend_health``).

M-5 rule: ``SYNAPSE_MEMORY_BACKEND=moneta`` served by a jsonl fallback must be
reported UNAVAILABLE/BLOCKED, never a healthy jsonl masquerading as Moneta. The
accessor carries the five W1 operator-acceptance fields (requested backend,
active backend, embedder id, embedding dim, row count) and speaks the ratified
``loop/ports.py`` status vocabulary.

Ungated on purpose: the fallback path FORCES Moneta absent (monkeypatch), so
these run with or without the moneta package installed -- skip would be a false
green (constitution: skip != pass). Only the one moneta-serves assertion is
gated on the live backend.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.loop import ports  # noqa: E402
from synapse.memory import moneta_runtime as _mr  # noqa: E402
from synapse.memory import store as store_mod  # noqa: E402
from synapse.memory.models import Memory, MemoryType  # noqa: E402
from synapse.memory.store import MemoryStore, SynapseMemory  # noqa: E402

FIVE_FIELDS = {
    "requested_backend", "active_backend", "embedder_id", "embedding_dim", "row_count",
}


def _moneta_unavailable_store(tmp_path, monkeypatch):
    """A SynapseMemory that requested moneta but got the jsonl fallback."""
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    monkeypatch.setattr(_mr, "moneta_available", lambda: False)
    return SynapseMemory(project_path=str(tmp_path / "proj"))


def _close(sm):
    if hasattr(sm.store, "close"):
        sm.store.close()


# --------------------------------------------------------------------------- #
# M-5: moneta requested + un-importable -> reported honestly, never SUCCESS
# --------------------------------------------------------------------------- #

def test_backend_health_reports_unavailable_when_moneta_unimportable(tmp_path, monkeypatch):
    sm = _moneta_unavailable_store(tmp_path, monkeypatch)
    try:
        assert isinstance(sm.store, MemoryStore)  # jsonl is what actually serves
        h = store_mod.backend_health(sm.store)
        assert h["requested_backend"] == "moneta"
        assert h["active_backend"] == "jsonl"
        assert h["status"] == "UNAVAILABLE"
        assert h["status"] != "SUCCESS"            # the anti-masquerade core
        assert h["reason"]                         # names the requested-vs-served gap
        assert isinstance(h["row_count"], int)     # the fallback store is still enumerable
    finally:
        _close(sm)


def test_backend_health_carries_all_five_operator_fields(tmp_path, monkeypatch):
    sm = _moneta_unavailable_store(tmp_path, monkeypatch)
    try:
        h = store_mod.backend_health(sm.store)
        assert FIVE_FIELDS <= set(h)
        # jsonl fallback has no embedder -> honest Nones, not fabricated values
        assert h["embedder_id"] is None
        assert h["embedding_dim"] is None
    finally:
        _close(sm)


def test_backend_health_status_in_ratified_vocabulary(tmp_path, monkeypatch):
    # The accessor's declared vocabulary IS the ratified ports.STATUS (no drift).
    assert store_mod._BACKEND_STATUS == ports.STATUS
    sm = _moneta_unavailable_store(tmp_path, monkeypatch)
    try:
        assert store_mod.backend_health(sm.store)["status"] in ports.STATUS
    finally:
        _close(sm)


def test_health_row_does_not_masquerade_jsonl_as_moneta(tmp_path, monkeypatch):
    # The server health row (write_plane.store_health) reads the SAME live store
    # via store._global_synapse. Prove it reports the requested-vs-served gap --
    # i.e. it never presents a healthy jsonl as Moneta.
    sm = _moneta_unavailable_store(tmp_path, monkeypatch)
    monkeypatch.setattr(store_mod, "_global_synapse", sm)
    try:
        from synapse.server import write_plane
        info = write_plane.store_health()
        assert info["requested_backend"] == "moneta"
        assert info["serving_jsonl"] is True
        assert info["status"] == "degraded"        # not "ok" -- honest degradation
    finally:
        _close(sm)


# --------------------------------------------------------------------------- #
# SUCCESS paths + observer law
# --------------------------------------------------------------------------- #

def test_backend_health_success_when_jsonl_requested_and_served(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "jsonl")
    sm = SynapseMemory(project_path=str(tmp_path / "proj"))
    try:
        h = store_mod.backend_health(sm.store)
        assert h["requested_backend"] == "jsonl"
        assert h["active_backend"] == "jsonl"
        assert h["status"] == "SUCCESS"
        assert h["reason"] is None
    finally:
        _close(sm)


@pytest.mark.skipif(
    not _mr.moneta_available(),
    reason=f"Moneta not importable (set $MONETA_SRC). Last error: {_mr.import_error()}",
)
def test_backend_health_success_when_moneta_serves(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    sm = SynapseMemory(project_path=str(tmp_path / "proj"))
    try:
        h = store_mod.backend_health(sm.store)
        assert h["requested_backend"] == "moneta"
        assert h["active_backend"] == "moneta"
        assert h["status"] == "SUCCESS"
        assert h["embedder_id"]                                   # real embedder id
        assert isinstance(h["embedding_dim"], int) and h["embedding_dim"] > 0
    finally:
        _close(sm)


def test_backend_health_returns_none_and_constructs_nothing(monkeypatch):
    # Observer law: no global store -> None, and the call constructs nothing.
    monkeypatch.setattr(store_mod, "_global_synapse", None)
    assert store_mod.backend_health() is None
    assert store_mod._global_synapse is None


# --------------------------------------------------------------------------- #
# T1 companion: JSONL dedup on identical content+type+created_at (overwrite
# intended). Ungated -- pure jsonl, needs no moneta.
# --------------------------------------------------------------------------- #

def test_identical_content_type_created_at_dedups_in_jsonl(tmp_path):
    j = MemoryStore(tmp_path / ".synapse")
    ts = "2026-01-01T00:00:00Z"
    a = Memory(content="dup", memory_type=MemoryType.NOTE, created_at=ts)
    b = Memory(content="dup", memory_type=MemoryType.NOTE, created_at=ts)
    assert a.id == b.id                            # same fields -> same id (precondition)
    j.add(a)
    j.add(b)
    assert j.count() == 1                           # dict overwrite -- dedup is intended
