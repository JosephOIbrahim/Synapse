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

# Per-test rather than module-wide: test_backfill_without_moneta_degrades_loudly
# below must RUN when Moneta is absent -- that is the case it pins.
needs_moneta = pytest.mark.skipif(
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


@needs_moneta
def test_dry_run_writes_nothing(tmp_path):
    storage = tmp_path / ".synapse"
    total = _seed_jsonl(storage)
    report = backfill_to_moneta(storage, dry_run=True)
    assert report["source_count"] == total
    assert report["would_deposit"] == total
    assert report["deposited"] == 0
    # No moneta store created on a dry run.
    assert not (storage / ".moneta" / "snapshot.json").exists()


@needs_moneta
def test_execute_backfills_and_verifies(tmp_path):
    storage = tmp_path / ".synapse"
    total = _seed_jsonl(storage)
    report = backfill_to_moneta(storage, dry_run=False)
    assert report["source_count"] == total
    assert report["deposited"] == total
    assert report["verified"] is True


@needs_moneta
def test_backup_is_taken_and_source_intact(tmp_path):
    storage = tmp_path / ".synapse"
    _seed_jsonl(storage)
    jsonl = storage / "memory.jsonl"
    before = jsonl.read_bytes()
    report = backfill_to_moneta(storage, dry_run=False, backup=True)
    assert report["backup"] is not None
    assert Path(report["backup"]).exists()
    assert jsonl.read_bytes() == before  # source untouched (reversible)


@needs_moneta
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


@needs_moneta
def test_empty_store_backfills_to_zero(tmp_path):
    storage = tmp_path / ".synapse"
    MemoryStore(storage).save()  # empty store
    report = backfill_to_moneta(storage, dry_run=False)
    assert report["source_count"] == 0
    assert report["deposited"] == 0
    assert report["verified"] is True


@needs_moneta
def test_source_intact_under_production_backend_env(tmp_path, monkeypatch):
    """B5 (2026-09-05): the source memory.jsonl must survive a real backfill
    under the env production actually runs with.

    ``packages/synapse.json`` ships ``SYNAPSE_MEMORY_BACKEND=moneta``, and
    ``MonetaBackedStore.from_storage_dir`` gates its W3-STORE JSONL dual-write
    on exactly that value. Before the fix the backfill opened the destination
    store on the SOURCE dir with dual-write on, so every deposit was appended
    back into the file being read (7 lines -> 14 on one run) -- and CI never
    saw it because the workflow never set the variable. This test sets it
    itself so the verdict does not depend on the caller's shell."""
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    storage = tmp_path / ".synapse"
    total = _seed_jsonl(storage)
    jsonl = storage / "memory.jsonl"
    before = jsonl.read_bytes()
    lines_before = len(before.splitlines())
    assert lines_before == total

    report = backfill_to_moneta(storage, dry_run=False, backup=True)

    assert report["verified"] is True
    after = jsonl.read_bytes()
    assert len(after.splitlines()) == lines_before, (
        f"source memory.jsonl grew {lines_before} -> {len(after.splitlines())} "
        "lines: the destination store dual-wrote back into the source"
    )
    assert after == before
    # The backup must be a copy of the source as it was, and still is.
    assert Path(report["backup"]).read_bytes() == before


def test_backfill_without_moneta_degrades_loudly(tmp_path, monkeypatch):
    """When Moneta is not importable a real backfill must RAISE, never report
    ``verified`` against a store that does not exist. Runs on every seat --
    including the CI legs with no Moneta deploy key -- by simulating absence
    at the seam ``from_storage_dir`` consults."""
    monkeypatch.setattr(mr, "moneta_available", lambda: False)
    monkeypatch.setattr(mr, "import_error", lambda: "simulated: moneta absent")
    storage = tmp_path / ".synapse"
    _seed_jsonl(storage)
    jsonl = storage / "memory.jsonl"
    before = jsonl.read_bytes()

    # Dry run needs no backend and must still work.
    assert backfill_to_moneta(storage, dry_run=True)["would_deposit"] == 7

    with pytest.raises(RuntimeError, match="not importable"):
        backfill_to_moneta(storage, dry_run=False)

    assert jsonl.read_bytes() == before
    assert not (storage / ".moneta" / "snapshot.json").exists()
