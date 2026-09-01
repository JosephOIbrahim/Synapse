"""BP2-HEALTHWIRE — the server operator health ROW carries the ratified backend
verdict + the two W1 operator fields it lacked (embedder id + embedding dim).

This leg is ADDITIVE over BP2-STORE's ``store.backend_health()`` (memory
territory, read-only here): ``write_plane.store_health()`` now merges
``embedder_id`` / ``embedding_dim`` and attaches the full ``backend_health()``
dict under ``info["backend_health"]`` — whose ``verdict`` (an alias of the
memory layer's ``status``, which is territory-frozen) speaks the ratified
``SUCCESS | UNAVAILABLE | BLOCKED`` vocabulary. The row's OWN
``ok/degraded/unknown`` word is unchanged, so its doctor / panel-strip /
``test_w3_harden_write_plane_store.py`` consumers do not break.

M-5 rule under test: ``SYNAPSE_MEMORY_BACKEND=moneta`` served by a jsonl
fallback is reported UNAVAILABLE in the ratified verdict and NEVER rendered as
ok — a healthy jsonl must not masquerade as Moneta.

Fixtures mirror ``tests/test_store_backend_health.py`` (the STORE leg): the
moneta-unavailable path FORCES Moneta absent (monkeypatch), so it runs with or
without the moneta package installed — skip would be a false green
(constitution: skip != pass). Only the one moneta-serves assertion is gated on
the live backend.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.loop import ports  # noqa: E402
from synapse.memory import moneta_runtime as _mr  # noqa: E402
from synapse.memory import store as store_mod  # noqa: E402
from synapse.memory.store import MemoryStore, SynapseMemory  # noqa: E402
from synapse.server import write_plane  # noqa: E402

FIVE_FIELDS = {
    "requested_backend", "active_backend", "embedder_id", "embedding_dim", "row_count",
}

# write_plane's OWN pre-ratified vocabulary — kept, not replaced by this leg.
WRITE_PLANE_WORDS = {"ok", "degraded", "unknown"}


def _close(sm):
    if hasattr(sm.store, "close"):
        sm.store.close()


def _moneta_unavailable_row(tmp_path, monkeypatch):
    """A live SynapseMemory that requested moneta but got the jsonl fallback,
    wired so ``write_plane.store_health()`` reads it as the process store."""
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    monkeypatch.setattr(_mr, "moneta_available", lambda: False)
    sm = SynapseMemory(project_path=str(tmp_path / "proj"))
    monkeypatch.setattr(store_mod, "_global_synapse", sm)
    return sm


def _jsonl_healthy_row(tmp_path, monkeypatch):
    """A live jsonl store, requested-and-served, wired as the process store."""
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "jsonl")
    sm = SynapseMemory(project_path=str(tmp_path / "proj"))
    monkeypatch.setattr(store_mod, "_global_synapse", sm)
    return sm


# --------------------------------------------------------------------------- #
# M-5: moneta requested + un-importable -> ratified verdict UNAVAILABLE, while
# write_plane keeps its own 'degraded' word (never rendered as ok).
# --------------------------------------------------------------------------- #

def test_health_row_attaches_unavailable_verdict_when_moneta_unimportable(
        tmp_path, monkeypatch):
    sm = _moneta_unavailable_row(tmp_path, monkeypatch)
    try:
        info = write_plane.store_health()
        # write_plane keeps its OWN word (its consumers read this) ...
        assert info["evaluated"] is True
        assert info["status"] == "degraded"
        assert info["serving_jsonl"] is True
        # ... and the ratified verdict rides alongside it.
        bh = info["backend_health"]
        assert bh["verdict"] == "UNAVAILABLE"      # the T3 predicate, literally
        assert bh["status"] == "UNAVAILABLE"       # store.py's word, preserved verbatim
        assert bh["verdict"] == bh["status"]       # the alias is not a fork
        assert bh["requested_backend"] == "moneta"
        assert bh["active_backend"] == "jsonl"
        assert bh["reason"]                        # names the requested-vs-served gap
    finally:
        _close(sm)


def test_unavailable_is_never_rendered_as_ok(tmp_path, monkeypatch):
    # The crucible criterion: UNAVAILABLE/BLOCKED never rendered as ok.
    sm = _moneta_unavailable_row(tmp_path, monkeypatch)
    try:
        info = write_plane.store_health()
        assert info["status"] != "ok"                       # top-level word
        assert info["backend_health"]["verdict"] != "ok"    # ratified verdict
        assert info["backend_health"]["verdict"] != "SUCCESS"
        assert info["backend_health"]["verdict"] in ports.STATUS
    finally:
        _close(sm)


def test_health_row_merges_embedder_fields_honest_none_on_jsonl(tmp_path, monkeypatch):
    sm = _moneta_unavailable_row(tmp_path, monkeypatch)
    try:
        info = write_plane.store_health()
        # The two W1 operator fields are merged at TOP level of the row.
        assert "embedder_id" in info
        assert "embedding_dim" in info
        # jsonl fallback has no embedder -> honest Nones, not fabricated values.
        assert info["embedder_id"] is None
        assert info["embedding_dim"] is None
        # The attached sub-dict carries the full five operator fields.
        assert FIVE_FIELDS <= set(info["backend_health"])
        assert isinstance(info["backend_health"]["row_count"], int)
    finally:
        _close(sm)


# --------------------------------------------------------------------------- #
# Healthy path -> SUCCESS with the operator fields present.
# --------------------------------------------------------------------------- #

def test_healthy_jsonl_row_rides_success_verdict_with_operator_fields(
        tmp_path, monkeypatch):
    sm = _jsonl_healthy_row(tmp_path, monkeypatch)
    try:
        info = write_plane.store_health()
        assert info["status"] == "ok"                       # write_plane's own healthy word
        bh = info["backend_health"]
        assert bh["verdict"] == "SUCCESS"
        assert bh["reason"] is None
        assert bh["requested_backend"] == "jsonl"
        assert bh["active_backend"] == "jsonl"
        # Operator fields present as keys (values honestly None on jsonl).
        assert "embedder_id" in info and "embedding_dim" in info
        assert FIVE_FIELDS <= set(bh)
    finally:
        _close(sm)


@pytest.mark.skipif(
    not _mr.moneta_available(),
    reason=f"Moneta not importable (set $MONETA_SRC). Last error: {_mr.import_error()}",
)
def test_healthy_moneta_row_shows_real_embedder_id_and_dim(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    sm = SynapseMemory(project_path=str(tmp_path / "proj"))
    monkeypatch.setattr(store_mod, "_global_synapse", sm)
    try:
        info = write_plane.store_health()
        bh = info["backend_health"]
        assert bh["verdict"] == "SUCCESS"
        assert bh["active_backend"] == "moneta"
        # Real embedder identity + dimension surface at the row (T3 healthy path).
        assert info["embedder_id"]                                     # truthy id
        assert isinstance(info["embedding_dim"], int) and info["embedding_dim"] > 0
        assert bh["embedder_id"] == info["embedder_id"]
        assert bh["embedding_dim"] == info["embedding_dim"]
    finally:
        _close(sm)


# --------------------------------------------------------------------------- #
# Vocabulary separation + observer law
# --------------------------------------------------------------------------- #

def test_two_vocabularies_stay_separate(tmp_path, monkeypatch):
    # write_plane speaks ok/degraded/unknown; the sub-dict speaks the ratified
    # SUCCESS/UNAVAILABLE/BLOCKED. This leg must not blur them.
    sm = _moneta_unavailable_row(tmp_path, monkeypatch)
    try:
        info = write_plane.store_health()
        assert info["status"] in WRITE_PLANE_WORDS
        assert info["backend_health"]["verdict"] in ports.STATUS
        assert info["backend_health"]["status"] in ports.STATUS
        # The ratified set is exactly the memory layer's declared vocabulary.
        assert store_mod._BACKEND_STATUS == ports.STATUS
    finally:
        _close(sm)


def test_no_live_store_attaches_no_backend_health(monkeypatch):
    # Observer law: no live store -> evaluated=False and NO fabricated backend
    # fields. The merge only runs on the evaluated path, so an empty process
    # never grows a phantom verdict.
    monkeypatch.setattr(store_mod, "_global_synapse", None)
    info = write_plane.store_health()
    assert info["evaluated"] is False
    assert "backend_health" not in info
    assert "embedder_id" not in info
    assert "embedding_dim" not in info
