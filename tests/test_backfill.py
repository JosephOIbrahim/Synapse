"""Mile 8 — backfill JSONL -> Moneta: count-agnostic, backup-first, reversible."""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import moneta_runtime as mr  # noqa: E402
from synapse.memory.models import Memory, MemoryType  # noqa: E402
from synapse.memory.store import MemoryStore  # noqa: E402
from synapse.memory.backfill import backfill_to_moneta  # noqa: E402

pytestmark = pytest.mark.skipif(
    not mr.moneta_available(),
    reason=f"Moneta not importable (set $MONETA_SRC). Last error: {mr.import_error()}",
)


def _seed_jsonl(storage_dir, n_notes=5, n_decisions=2):
    src = MemoryStore(storage_dir)
    src._wait_loaded()
    for i in range(n_notes):
        src.add(Memory(content=f"note {i}", memory_type=MemoryType.NOTE,
                       created_at=f"2026-02-0{i + 1}T00:00:00Z"))
    for i in range(n_decisions):
        src.add(Memory(content=f"decision {i}", memory_type=MemoryType.DECISION))
    src.save()
    return n_notes + n_decisions


def test_dry_run_writes_nothing(tmp_path):
    storage = tmp_path / ".synapse"
    total = _seed_jsonl(storage)
    report = backfill_to_moneta(storage, dry_run=True)
    assert report["source_count"] == total
    assert report["would_deposit"] == total
    assert report["deposited"] == 0
    # No moneta store created on a dry run.
    assert not (storage / ".moneta" / "snapshot.json").exists()


def test_execute_backfills_and_verifies(tmp_path):
    storage = tmp_path / ".synapse"
    total = _seed_jsonl(storage)
    report = backfill_to_moneta(storage, dry_run=False)
    assert report["source_count"] == total
    assert report["deposited"] == total
    assert report["verified"] is True


def test_backup_is_taken_and_source_intact(tmp_path):
    storage = tmp_path / ".synapse"
    _seed_jsonl(storage)
    jsonl = storage / "memory.jsonl"
    before = jsonl.read_bytes()
    report = backfill_to_moneta(storage, dry_run=False, backup=True)
    assert report["backup"] is not None
    assert Path(report["backup"]).exists()
    assert jsonl.read_bytes() == before  # source untouched (reversible)


def test_content_round_trips_through_backfill(tmp_path):
    from synapse.memory.moneta_store import MonetaBackedStore
    storage = tmp_path / ".synapse"
    _seed_jsonl(storage, n_notes=3, n_decisions=1)
    backfill_to_moneta(storage, dry_run=False)
    # Re-open the moneta store and confirm the decision survived with content.
    store = MonetaBackedStore.from_storage_dir(storage)
    try:
        decisions = store.get_by_type(MemoryType.DECISION)
        assert len(decisions) == 1
        assert decisions[0].content == "decision 0"
    finally:
        store.close()


def test_empty_store_backfills_to_zero(tmp_path):
    storage = tmp_path / ".synapse"
    MemoryStore(storage).save()  # empty store
    report = backfill_to_moneta(storage, dry_run=False)
    assert report["source_count"] == 0
    assert report["deposited"] == 0
    assert report["verified"] is True
