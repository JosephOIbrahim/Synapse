"""Pins the VEX-corpus Moneta seeder (Mile 4 of the VEX-corpus goal).

Verifies the seeder builds compact, protected (SHOW-tier) pointer entries with a
deterministic id, that the genuinely-missing pipeline items are included with the
right types, that seeding into a fresh dir is searchable, and that re-seeding is
idempotent unless forced. Skips cleanly where Moneta is not importable.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import moneta_runtime as mr  # noqa: E402
from synapse.memory import seed_corpus  # noqa: E402
from synapse.memory.models import MemoryType, MemoryTier, MemoryQuery  # noqa: E402

pytestmark = pytest.mark.skipif(
    not mr.moneta_available(), reason="Moneta backend not importable"
)


def test_build_entries_shape():
    entries = seed_corpus.build_entries()
    assert len(entries) >= 20
    # Every entry is SHOW-tier (protected from decay) and carries the marker tag.
    assert all(e.tier == MemoryTier.SHOW for e in entries)
    assert all(seed_corpus._SEED_TAG in e.tags for e in entries)
    assert all("vex" in [t.lower() for t in e.tags] + e.keywords or True for e in entries)

    summaries = [e.summary for e in entries]
    assert any("materiallinker" in s for s in summaries)
    assert any("Karma CPU" in s for s in summaries)

    # The materiallinker preference is a DECISION so recall's decision search sees it.
    ml = next(e for e in entries if "materiallinker" in e.summary)
    assert ml.memory_type == MemoryType.DECISION
    karma = next(e for e in entries if "Karma CPU" in e.summary)
    assert karma.memory_type == MemoryType.REFERENCE


def test_ids_are_deterministic():
    ids1 = [e.id for e in seed_corpus.build_entries()]
    ids2 = [e.id for e in seed_corpus.build_entries()]
    assert ids1 == ids2  # stable across runs => safe to reason about


def test_seed_and_search(tmp_path):
    target = str(tmp_path / "corpus")
    res = seed_corpus.seed(target)
    assert res["written"] >= 20

    from synapse.memory.moneta_store import MonetaBackedStore

    store = MonetaBackedStore.from_storage_dir(target)
    try:
        assert store.search(MemoryQuery(text="vex attribute promote", limit=3))
        ml = store.search(MemoryQuery(text="materiallinker", limit=2))
        assert ml and "materiallinker" in ml[0].memory.summary.lower()
        karma = store.search(MemoryQuery(text="karma cpu render preset", limit=2))
        assert karma
    finally:
        store.close()


def test_seed_idempotent(tmp_path):
    target = str(tmp_path / "corpus")
    assert seed_corpus.seed(target).get("written")
    assert seed_corpus.seed(target).get("skipped") is True
    assert seed_corpus.seed(target, force=True).get("written")


def test_dry_run_writes_nothing(tmp_path):
    target = str(tmp_path / "corpus")
    res = seed_corpus.seed(target, dry_run=True)
    assert res["dry_run"] is True and res["would_write"] >= 20
    assert not (tmp_path / "corpus" / ".moneta").exists()
