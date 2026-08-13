"""W3-DIM — the embedding-dim contract: index reads the provider, loud on mismatch.

The crux bug (docs/SYNAPSE-memory-engineering-spec.md S0/S2): a Moneta snapshot
persisted by one embedding provider (e.g. 384-dim SemanticEmbedder) is reopened
under a different provider (e.g. 256-dim HashEmbedder). Moneta rebuilds its
shadow vector index from the hydrated ECS by upserting each row's persisted
``semantic_vector`` against an index dim taken from the LIVE ``embedding_dim``;
the first mismatched upsert trips the vendor dim-guard
(``moneta/vector_index.py:112``) and ``Moneta(cfg)`` raises inside its own
constructor. Before this leg that aborted init and ``store._make_store``
degraded the whole seat to jsonl for a fully recoverable condition.

These tests pin the four targets:
  1. one dim authority — ``_resolve_embedding_dim`` reads the ACTIVE embedder,
     both construction paths feed from it.
  2. stale-snapshot rebuild — a dim-mismatched snapshot is rebuilt from source
     payloads at init (both directions), init succeeds, no memory lost.
  3. fallback honesty — a forced init failure serves jsonl and records
     ``backend_fallback`` (requested=moneta, served=jsonl); the doctor never
     shows a passing/in-use moneta.
  4. no papering — the vendor "embedding dim mismatch" ValueError never fires on
     the reopen path (the reconcile pre-empts it), and the reconcile itself is
     announced loudly in the log.
"""

import json
import logging
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import moneta_runtime as mr  # noqa: E402
from synapse.memory import store as store_mod  # noqa: E402
from synapse.memory.embedding import HashEmbedder, SemanticEmbedder  # noqa: E402
from synapse.memory.models import Memory, MemoryQuery, MemoryType  # noqa: E402
from synapse.memory.store import MemoryStore, SynapseMemory  # noqa: E402

_MONETA = mr.moneta_available()
_needs_moneta = pytest.mark.skipif(
    not _MONETA,
    reason=f"Moneta not importable (set $MONETA_SRC). Last error: {mr.import_error()}",
)


def _corpus():
    """A small fixed corpus exercising types, tags, keywords, recency."""
    return [
        Memory(content="render the karma beauty pass tonight",
               memory_type=MemoryType.ACTION, tags=["render", "karma"],
               keywords=["karma", "beauty"], created_at="2026-01-01T00:00:00Z"),
        Memory(content="Decision: use assemble_chain to wire the Solaris graph",
               memory_type=MemoryType.DECISION, tags=["ai_decision"],
               keywords=["assemble_chain", "solaris"], created_at="2026-01-02T00:00:00Z"),
        Memory(content="material binding failed on the hero asset",
               memory_type=MemoryType.ERROR, tags=["error", "material"],
               keywords=["material", "binding"], created_at="2026-01-03T00:00:00Z"),
        Memory(content="note about karma denoiser settings for the render",
               memory_type=MemoryType.NOTE, tags=["render"],
               keywords=["karma", "denoiser"], created_at="2026-01-04T00:00:00Z"),
    ]


def _snapshot_vector_dims(storage_dir: Path):
    """Every row's semantic_vector length in the persisted snapshot."""
    snap = Path(storage_dir) / ".moneta" / "snapshot.json"
    data = json.loads(snap.read_text(encoding="utf-8"))
    return [len(r["semantic_vector"]) for r in data.get("rows", [])]


def _seed_store(storage_dir: Path, dim: int) -> int:
    """Build a durable Moneta store at *dim*, deposit the corpus, persist, close.

    Returns the memory count so the reopen can assert nothing was lost.
    """
    from synapse.memory.moneta_store import MonetaBackedStore

    store = MonetaBackedStore.from_storage_dir(storage_dir, HashEmbedder(dim=dim))
    for m in _corpus():
        store.add(m)
    n = store.count()
    store.save()
    store.close()  # releases the Moneta URI lock so the reopen can re-acquire it
    return n


# --------------------------------------------------------------------------
# Target 1 — one dim authority
# --------------------------------------------------------------------------

@_needs_moneta
def test_resolve_embedding_dim_reads_the_active_provider():
    from synapse.memory.moneta_store import MonetaBackedStore as MBS

    assert MBS._resolve_embedding_dim(HashEmbedder(dim=256)) == 256
    assert MBS._resolve_embedding_dim(HashEmbedder(dim=384)) == 384
    # SemanticEmbedder's declared dim is its authority regardless of whether the
    # ONNX model is present (its fallback is HashEmbedder(dim=self.dim)).
    assert MBS._resolve_embedding_dim(SemanticEmbedder(dim=384)) == 384


@_needs_moneta
@pytest.mark.parametrize("bad", [0, -1, None, True, 3.0, "384"])
def test_resolve_embedding_dim_rejects_unusable_dims(bad):
    from synapse.memory.moneta_store import MonetaBackedStore as MBS

    class _Fake:
        id = "fake"
        dim = bad

    with pytest.raises(ValueError):
        MBS._resolve_embedding_dim(_Fake())


# --------------------------------------------------------------------------
# Target 2 — stale-snapshot rebuild, both directions (acceptance #2: test)
# --------------------------------------------------------------------------

@_needs_moneta
@pytest.mark.parametrize("seed_dim,live_dim", [(384, 256), (256, 384)])
def test_stale_snapshot_dim_is_rebuilt_at_init(tmp_path, seed_dim, live_dim, caplog):
    from synapse.memory.moneta_store import MonetaBackedStore

    # 1) seed a snapshot at seed_dim and confirm it persisted at that dim.
    n = _seed_store(tmp_path, seed_dim)
    assert n == len(_corpus())
    assert set(_snapshot_vector_dims(tmp_path)) == {seed_dim}

    # 2) reopen under a DIFFERENT provider. This must NOT abort into jsonl: the
    #    reconcile rebuilds the derived vectors at the live dim first.
    with caplog.at_level(logging.WARNING):
        reopened = MonetaBackedStore.from_storage_dir(
            tmp_path, HashEmbedder(dim=live_dim)
        )

    try:
        # init succeeded on the Moneta backend (not a fallback object).
        assert isinstance(reopened, MonetaBackedStore)
        # no memory lost — the payloads are the source of truth.
        assert reopened.count() == n
        # the persisted snapshot is now uniformly at the live dim.
        assert set(_snapshot_vector_dims(tmp_path)) == {live_dim}
        # vector recall works under the live provider (no dim ValueError).
        results = reopened.search(MemoryQuery(text="karma render", limit=5))
        assert results, "expected keyword/vector recall to return the render memories"
        # target 4: the vendor mismatch ValueError NEVER surfaced; the reconcile
        # announced itself instead.
        text = caplog.text.lower()
        assert "embedding dim mismatch" not in text
        assert "snapshot dim reconcile" in text
    finally:
        reopened.close()


@_needs_moneta
def test_reconcile_is_noop_when_dims_already_match(tmp_path):
    """Fast path: a snapshot already at the live dim is not rewritten."""
    from synapse.memory.moneta_store import MonetaBackedStore

    _seed_store(tmp_path, 256)
    snap = tmp_path / ".moneta" / "snapshot.json"
    before = snap.read_bytes()

    # Same-dim reconcile returns None and touches nothing.
    summary = MonetaBackedStore._reconcile_snapshot_dim(snap, HashEmbedder(dim=256))
    assert summary is None
    assert snap.read_bytes() == before

    # A mismatch returns a summary describing the rebuild.
    summary = MonetaBackedStore._reconcile_snapshot_dim(snap, HashEmbedder(dim=384))
    assert summary is not None
    assert summary["from_dim"] == 256 and summary["to_dim"] == 384
    assert summary["rebuilt"] == len(_corpus())
    assert set(_snapshot_vector_dims(tmp_path)) == {384}


@_needs_moneta
def test_reconcile_absent_snapshot_is_noop(tmp_path):
    from synapse.memory.moneta_store import MonetaBackedStore

    missing = tmp_path / ".moneta" / "snapshot.json"
    assert MonetaBackedStore._reconcile_snapshot_dim(missing, HashEmbedder(dim=256)) is None


# --------------------------------------------------------------------------
# Target 3 — fallback honesty (acceptance #3: test)
# --------------------------------------------------------------------------

def _make_store_isolated(storage_dir):
    """Call SynapseMemory._make_store without a full (hou-touching) __init__."""
    sm = SynapseMemory.__new__(SynapseMemory)
    return sm._make_store(storage_dir)


def test_forced_init_failure_serves_jsonl_and_records_fallback(tmp_path, monkeypatch):
    """A Moneta init failure must serve jsonl AND record it honestly.

    Robust whether or not Moneta is importable on this seat: when it is, we force
    ``from_storage_dir`` to raise; when it is not, ``_make_store`` takes its
    not-importable arm. Both must land on jsonl with a ``backend_fallback`` whose
    requested=moneta / served=jsonl — the store never claims moneta while serving
    jsonl.
    """
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")

    if _MONETA:
        from synapse.memory.moneta_store import MonetaBackedStore

        def _boom(storage_dir, *a, **k):
            raise RuntimeError("simulated dim-contract init failure")

        monkeypatch.setattr(MonetaBackedStore, "from_storage_dir", staticmethod(_boom))

    store = _make_store_isolated(tmp_path)

    # Served backend is jsonl.
    assert isinstance(store, MemoryStore)
    # ...and the fallback is recorded, not silent.
    fb = store_mod.backend_fallback()
    assert fb is not None
    assert fb["requested"] == "moneta"
    assert fb["served"] == "jsonl"
    assert fb["reason"]  # a non-empty cause is always carried


def test_doctor_never_shows_in_use_moneta_after_fallback(tmp_path, monkeypatch):
    """The doctor's moneta_substrate check must fail (not ok, not in_use) when a
    fallback was recorded — a green light over jsonl is the exact bug to avoid."""
    doctor = pytest.importorskip("synapse.server.doctor")
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")

    if _MONETA:
        from synapse.memory.moneta_store import MonetaBackedStore

        def _boom(storage_dir, *a, **k):
            raise RuntimeError("simulated dim-contract init failure")

        monkeypatch.setattr(MonetaBackedStore, "from_storage_dir", staticmethod(_boom))

    # Trigger the fallback record in this process.
    store = _make_store_isolated(tmp_path)
    assert isinstance(store, MemoryStore)

    check = doctor._check_moneta_substrate()
    assert check["status"] == "fail"
    assert "fell back to jsonl" in check["detail"].lower()
    # The fail arm returns before any schema probe, so nothing reports moneta as
    # registered-and-in-use.
    assert check.get("result", {}).get("schema_in_use") is not True
