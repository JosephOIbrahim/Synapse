"""W3-STORE — materialize cortex_root.usda: typed root, write/query, dual-write.

Pins the wave's contract (self-contained brief; the cited spec doc is absent
from this worktree, so these tests ARE the executable contract):

  target 1  on init the store creates cortex_root.usda at the resolved usd_root
            with a typed MonetaMemory root prim carrying a ``version`` attribute
  target 2  write(kind,id,payload) -> a typed prim keyed by (kind,id); query
            walks the typed prims back (round-trip)
  target 3  DUAL-WRITE: every moneta add ALSO lands in the JSONL MemoryStore,
            byte-for-byte, via its own unchanged write path
  target 4  the key.fingerprint sidecar is written on first use so the doctor's
            memory_key_fingerprint check moves no_sidecar -> match
  acc. 1    doctor schema_in_use=True AND memory_key_fingerprint != no_sidecar
  acc. 4    the JSONL write path is behaviourally unchanged (safety net untouched)

Runs wherever Moneta + pxr are importable; skips cleanly otherwise.
"""

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import moneta_runtime as mr  # noqa: E402
from synapse.memory.embedding import HashEmbedder  # noqa: E402
from synapse.memory.models import Memory, MemoryType  # noqa: E402
from synapse.memory.store import MemoryStore, _get_crypto  # noqa: E402

DIM = 256

usd_required = pytest.mark.skipif(
    not mr.usd_author_available(),
    reason="pxr not importable — cortex authoring is a no-op here",
)
moneta_required = pytest.mark.skipif(
    not mr.moneta_available(),
    reason=f"Moneta not importable (set $MONETA_SRC). Last error: {mr.import_error()}",
)


def _mem(content="use assemble_chain to wire the Solaris graph",
         mtype=MemoryType.DECISION):
    return Memory(content=content, memory_type=mtype,
                  created_at="2026-01-02T00:00:00Z")


# ---------------------------------------------------------------------------
# UsdCortexStore — the write side (targets 1 + 2)
# ---------------------------------------------------------------------------

@usd_required
def test_cortex_init_authors_typed_root_with_version(tmp_path):
    """target 1: init creates cortex_root.usda at the resolved usd_root with a
    typed MonetaMemory root prim carrying a version attribute."""
    base = tmp_path / ".moneta"
    c = mr.UsdCortexStore(str(base))
    assert c.available
    assert c.path == str(base / mr.USD_ROOT_FILENAME)
    assert os.path.exists(c.path) and os.path.getsize(c.path) > 0

    root = c.stage.GetPrimAtPath(mr.CORTEX_ROOT_PATH)
    assert root.IsValid()
    assert str(root.GetTypeName()) == "MonetaMemory"
    assert root.GetAttribute("version").Get() == mr.CORTEX_STORE_VERSION

    # An empty (root-only) store already satisfies the doctor's condition 4.
    assert mr.schema_in_use(usd_root=str(base)) is True


@usd_required
def test_cortex_write_query_roundtrip(tmp_path):
    """target 2 + acceptance 2: write a memory, the .usda exists non-empty,
    query returns it (round-trip)."""
    base = tmp_path / ".moneta"
    c = mr.UsdCortexStore(str(base))
    payload = '{"id":"mem_abc","content":"hello"}'
    prim_path = c.write("decision", "mem_abc", payload)
    assert prim_path == "/MonetaMemory/decision/mem_abc"
    assert os.path.getsize(c.path) > 0

    rows = c.query()
    assert len(rows) == 1
    assert rows[0]["kind"] == "decision"
    assert rows[0]["id"] == "mem_abc"
    assert rows[0]["payload"] == payload  # literal byte-for-byte in the USD attr

    got = c.get("decision", "mem_abc")
    assert got is not None and got["payload"] == payload
    assert c.get("decision", "missing") is None
    assert c.query(kind="note") == []  # filter works


@usd_required
def test_cortex_keyed_by_kind_and_id(tmp_path):
    """(kind, id) is the key — same id under two kinds are distinct prims."""
    c = mr.UsdCortexStore(str(tmp_path / ".moneta"))
    c.write("decision", "mem_x", "d")
    c.write("note", "mem_x", "n")
    assert c.count() == 2
    assert c.get("decision", "mem_x")["payload"] == "d"
    assert c.get("note", "mem_x")["payload"] == "n"


@usd_required
def test_cortex_write_is_idempotent_per_key(tmp_path):
    c = mr.UsdCortexStore(str(tmp_path / ".moneta"))
    c.write("decision", "mem_x", "v1")
    c.write("decision", "mem_x", "v2")
    assert c.count() == 1
    assert c.get("decision", "mem_x")["payload"] == "v2"


@usd_required
def test_cortex_persists_across_reopen(tmp_path):
    base = tmp_path / ".moneta"
    c1 = mr.UsdCortexStore(str(base))
    c1.write("action", "mem_y", "payload-y")
    c1.close()

    c2 = mr.UsdCortexStore(str(base))
    rows = c2.query()
    assert len(rows) == 1 and rows[0]["id"] == "mem_y"
    # version + typed root survive the reopen
    root = c2.stage.GetPrimAtPath(mr.CORTEX_ROOT_PATH)
    assert str(root.GetTypeName()) == "MonetaMemory"
    assert root.GetAttribute("version").Get() == mr.CORTEX_STORE_VERSION


@usd_required
def test_cortex_root_resolution_accepts_file_or_dir(tmp_path):
    """A usd_root ending in .usda is the file; anything else is the dir."""
    as_dir = mr.UsdCortexStore(str(tmp_path / "a" / ".moneta"))
    assert as_dir.path.endswith(mr.USD_ROOT_FILENAME)
    explicit = mr.UsdCortexStore(str(tmp_path / "b" / "cortex_root.usda"))
    assert explicit.path.endswith("cortex_root.usda")
    assert not explicit.path.endswith(
        os.path.join("cortex_root.usda", mr.USD_ROOT_FILENAME)
    )


# ---------------------------------------------------------------------------
# MonetaBackedStore integration — dual-write + sidecar (targets 3 + 4)
# ---------------------------------------------------------------------------

def _moneta_store(storage_dir, *, dual_write_jsonl=True):
    from synapse.memory.moneta_store import MonetaBackedStore
    return MonetaBackedStore.from_storage_dir(
        storage_dir, embedder=HashEmbedder(dim=DIM),
        dual_write_jsonl=dual_write_jsonl,
    )


@moneta_required
@usd_required
def test_add_mirrors_to_cortex_moneta_and_jsonl(tmp_path):
    """target 3 + acceptance 3: one add lands in moneta, cortex, AND jsonl."""
    storage = tmp_path / ".synapse"
    storage.mkdir()
    store = _moneta_store(str(storage))
    m = _mem()
    store.add(m)

    # moneta (primary substrate)
    assert store.count() == 1

    # cortex (typed USD), keyed by (kind, id) with payload == to_json()
    row = store._cortex.get("decision", m.id)
    assert row is not None
    assert row["payload"] == m.to_json()
    assert mr.schema_in_use(usd_root=str(storage / ".moneta")) is True

    # jsonl safety net (byte-for-byte)
    verify = MemoryStore(str(storage), background_load=False)
    loaded = verify.get(m.id)
    assert loaded is not None
    assert loaded.to_json() == m.to_json()


@moneta_required
def test_dual_write_is_a_plain_memorystore(tmp_path):
    """acceptance 4 (check): the safety net is an unmodified MemoryStore writing
    the standard memory.jsonl — the JSONL write path is untouched."""
    storage = tmp_path / ".synapse"
    storage.mkdir()
    store = _moneta_store(str(storage))
    assert isinstance(store._jsonl_net, MemoryStore)
    store.add(_mem())
    assert (storage / "memory.jsonl").exists()


@moneta_required
def test_no_memory_lands_only_in_moneta(tmp_path):
    """crucible #2: a write where a memory lands ONLY in moneta is a BLOCK.
    Every memory added must be recoverable from the JSONL store."""
    storage = tmp_path / ".synapse"
    storage.mkdir()
    store = _moneta_store(str(storage))
    ids = []
    for i in range(5):
        m = _mem(content=f"decision number {i}")
        store.add(m)
        ids.append(m.id)
    verify = MemoryStore(str(storage), background_load=False)
    for mid in ids:
        assert verify.get(mid) is not None, f"{mid} missing from the JSONL safety net"


@moneta_required
@pytest.mark.skipif(_get_crypto() is None, reason="cryptography not installed")
def test_key_fingerprint_sidecar_written_on_first_use(tmp_path):
    """target 4 + acceptance 1b: the sidecar appears on first add and the
    doctor's memory_key_fingerprint check no longer reports no_sidecar."""
    storage = tmp_path / ".synapse"
    storage.mkdir()
    store = _moneta_store(str(storage))

    sidecar = storage / "key.fingerprint"
    assert not sidecar.exists()  # not written before any use
    store.add(_mem())
    assert sidecar.exists()
    assert sidecar.read_text(encoding="utf-8").strip() == _get_crypto().fingerprint()

    from synapse.server import doctor
    res = doctor.check_memory_key_fingerprint(storage_dir=storage)
    assert res["reason"] != "no_sidecar"
    assert res["status"] == "match"


# ---------------------------------------------------------------------------
# Regression / seam guards
# ---------------------------------------------------------------------------

@moneta_required
def test_shadow_backend_does_not_double_write(tmp_path, monkeypatch):
    """The shadow backend already wraps a JSONL primary; MonetaBackedStore must
    NOT add a second JSONL sink there (would double-write memory.jsonl)."""
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "shadow")
    from synapse.memory.moneta_store import MonetaBackedStore
    store = MonetaBackedStore.from_storage_dir(
        str(tmp_path / ".synapse"), embedder=HashEmbedder(dim=DIM),
    )  # dual_write_jsonl=None -> derived from env == 'shadow' -> off
    assert store._jsonl_net is None


@moneta_required
def test_moneta_backend_env_enables_dual_write(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    from synapse.memory.moneta_store import MonetaBackedStore
    store = MonetaBackedStore.from_storage_dir(
        str(tmp_path / ".synapse"), embedder=HashEmbedder(dim=DIM),
    )  # dual_write_jsonl=None -> derived from env == 'moneta' -> on
    assert isinstance(store._jsonl_net, MemoryStore)


@moneta_required
def test_injected_handle_has_no_secondary_sinks():
    """An ephemeral, caller-injected handle (the existing test path) keeps the
    pure engine-only adapter: no cortex, no dual-write. No behaviour change."""
    from synapse.memory.moneta_store import MonetaBackedStore
    handle = mr.make_ephemeral(embedding_dim=DIM)
    store = MonetaBackedStore(handle, HashEmbedder(dim=DIM))
    assert store._cortex is None
    assert store._jsonl_net is None
    store.add(_mem())  # still works — engine-only
    assert store.count() == 1
