"""W3-MIGRATE — JSONL→Moneta copy-and-verify, ids preserved, flip with fallback.

Pins the four acceptance predicates:
  #1 backup of every source exists AND originals are byte-untouched after a run
  #2 count of JSONL memories == count of Moneta rows (from disk) after migration
  #3 >=5 spot-checked memories match field-for-field across stores
  #4 post-flip, a new write lands in Moneta AND in JSONL (write-through armed)

plus the collision policy (#5 keep-both-never-overwrite), idempotency (guards the
append-only double-count), and dim-safety (a 256-dim store is not crashed by the
384-dim default).

Pure-logic tests (backup gate, census parsing, disk helpers, dedup planning via
dry-run) run everywhere. Tests that deposit into a live Moneta target skip
cleanly when Moneta is unavailable, exactly like the moneta/shadow/backfill tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from synapse.memory import migrate
from synapse.memory.models import Memory, MemoryType, MemoryTier
from synapse.memory import moneta_runtime as _mr

_HAS_MONETA = _mr.moneta_available()
moneta = pytest.mark.skipif(
    not _HAS_MONETA, reason=f"Moneta unavailable: {_mr.import_error()}"
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_source_store(store_dir: Path, memories):
    """Build a JSONL MemoryStore on disk holding *memories* (bytes flushed)."""
    from synapse.memory.store import MemoryStore
    store_dir.mkdir(parents=True, exist_ok=True)
    src = MemoryStore(store_dir, background_load=False)
    src._wait_loaded()
    for m in memories:
        src.add(m)
    src.save()
    return src


def _mem(content, mtype=MemoryType.NOTE, **kw):
    return Memory(content=content, memory_type=mtype, **kw)


# ===========================================================================
# 1) HARD BACKUP GATE  (acceptance #1)
# ===========================================================================

def _seed_store_dir(d: Path, jsonl="a\nb\n", snapshot=None, md="# ctx\n"):
    d.mkdir(parents=True, exist_ok=True)
    (d / "memory.jsonl").write_text(jsonl, encoding="utf-8")
    (d / "context.md").write_text(md, encoding="utf-8")
    mdir = d / ".moneta"
    mdir.mkdir(exist_ok=True)
    snap = snapshot or {"snapshot_version": 1, "rows": []}
    (mdir / "snapshot.json").write_text(json.dumps(snap), encoding="utf-8")


def test_backup_gate_copies_and_byte_verifies(tmp_path):
    s1 = tmp_path / "store1" / ".synapse"
    s2 = tmp_path / "store2" / ".synapse"
    _seed_store_dir(s1, jsonl="one\ntwo\n")
    _seed_store_dir(s2, jsonl="x\n")
    backup_root = tmp_path / "backups"

    manifest = migrate.backup_memory_stores(
        [str(s1), str(s2)], str(backup_root), dry_run=False
    )
    assert manifest.ok
    assert all(b.verified for b in manifest.stores)
    # every source file exists byte-identical under the backup root
    for b in manifest.stores:
        for rel, sha in b.source_sha.items():
            copied = Path(b.backup) / rel
            assert copied.is_file()
            assert migrate._sha256_file(copied) == sha


def test_backup_gate_proves_sources_untouched_and_detects_drift(tmp_path):
    s1 = tmp_path / "store1" / ".synapse"
    _seed_store_dir(s1, jsonl="one\ntwo\n")
    manifest = migrate.backup_memory_stores(
        [str(s1)], str(tmp_path / "backups"), dry_run=False
    )
    # nothing touched the source -> byte-untouched proof holds (acceptance #1)
    ok, changed = migrate.verify_sources_untouched(manifest)
    assert ok and changed == []
    # mutate a source AFTER the run -> the check must catch it (no false green)
    (s1 / "memory.jsonl").write_text("one\ntwo\nthree\n", encoding="utf-8")
    ok2, changed2 = migrate.verify_sources_untouched(manifest)
    assert not ok2 and any("memory.jsonl" in c for c in changed2)


def test_backup_gate_blocks_on_missing_source(tmp_path):
    manifest = migrate.backup_memory_stores(
        [str(tmp_path / "does_not_exist")], str(tmp_path / "b"), dry_run=False
    )
    assert not manifest.ok
    assert manifest.stores[0].error


def test_backup_gate_dry_run_writes_nothing(tmp_path):
    s1 = tmp_path / "store1" / ".synapse"
    _seed_store_dir(s1)
    backup_root = tmp_path / "backups"
    manifest = migrate.backup_memory_stores([str(s1)], str(backup_root), dry_run=True)
    assert manifest.ok  # dry-run "ok" == would-succeed
    assert not backup_root.exists()  # nothing written
    assert manifest.stores[0].source_sha  # but the baseline was recorded


# ===========================================================================
# disk helpers + census parsing (pure, no Moneta)
# ===========================================================================

def test_disk_helpers(tmp_path):
    d = tmp_path / ".synapse"
    _seed_store_dir(
        d, jsonl="a\n\nb\n",
        snapshot={"rows": [
            {"payload": json.dumps({"id": "mem_1"}), "semantic_vector": [0.0] * 256},
            {"payload": json.dumps({"id": "mem_2"}), "semantic_vector": [0.0] * 256},
        ]},
    )
    assert migrate.count_jsonl_lines(d) == 2          # blank line ignored
    assert len(migrate.read_snapshot_rows(d)) == 2
    assert migrate.snapshot_dim(d) == 256
    assert migrate._payload_id({"payload": json.dumps({"id": "mem_9"})}) == "mem_9"


def test_census_parsing_selects_memory_bearing(tmp_path):
    census = {
        "entries": [{"value": {"stores": [
            {"path": "/real/a/.synapse", "classification": "real",
             "entry_counts": {"memory_jsonl_lines": 5, "moneta_rows": 0}},
            {"path": "/real/b/.synapse", "classification": "real",
             "entry_counts": {"memory_jsonl_lines": 0, "moneta_rows": 3}},
            {"path": "/real/empty/.synapse", "classification": "real",
             "entry_counts": {"memory_jsonl_lines": 0, "moneta_rows": 0}},
            {"path": "/tmp/pytest/.synapse", "classification": "test",
             "entry_counts": {"memory_jsonl_lines": 9, "moneta_rows": 0}},
        ]}}]
    }
    cp = tmp_path / "census.json"
    cp.write_text(json.dumps(census), encoding="utf-8")
    assert len(migrate.real_stores_from_census(cp)) == 3          # excludes 'test'
    bearing = {s["path"] for s in migrate.memory_bearing_stores(cp)}
    assert bearing == {"/real/a/.synapse", "/real/b/.synapse"}    # excludes empty


def test_export_dry_run_plans_without_moneta(tmp_path):
    """dry-run export classifies memories with no Moneta dependency."""
    src = tmp_path / "src" / ".synapse"
    _make_source_store(src, [_mem("alpha"), _mem("beta"), _mem("gamma")])
    tgt = tmp_path / "tgt" / ".synapse"
    rep = migrate.export_jsonl_to_moneta(src, tgt, dry_run=True)
    assert rep.error is None
    assert rep.source_count == 3
    assert rep.source_jsonl_lines == 3
    assert rep.added == 3                    # fresh target -> all planned as new
    assert rep.target_count_before == 0


# ===========================================================================
# 2) EXPORT count parity + id preservation  (acceptance #2, target #2)
# ===========================================================================

@moneta
def test_export_fresh_target_count_parity_and_ids(tmp_path):
    src = tmp_path / "src" / ".synapse"
    mems = [_mem(f"memory number {i}", tags=[f"t{i}"]) for i in range(12)]
    _make_source_store(src, mems)
    tgt = tmp_path / "tgt" / ".synapse"

    rep = migrate.export_jsonl_to_moneta(src, tgt, dry_run=False)
    assert rep.error is None, rep.error
    assert rep.added == 12
    # count parity recomputed FROM DISK (snapshot.json), not from the report
    rows = migrate.read_snapshot_rows(tgt)
    assert len(rows) == 12
    src_ids = {m.id for m in mems}
    tgt_ids = {migrate._payload_id(r) for r in rows}
    assert tgt_ids == src_ids                # every id preserved, none dropped


@moneta
def test_verify_export_count_parity_and_spot_check(tmp_path):
    """acceptance #2 (count) + #3 (>=5 field-by-field spot-checks)."""
    src = tmp_path / "src" / ".synapse"
    mems = [
        _mem(f"content body {i}", mtype=MemoryType.DECISION if i % 2 else MemoryType.NOTE,
             tags=[f"tag{i}"], keywords=[f"kw{i}"], summary=f"summary {i}")
        for i in range(8)
    ]
    _make_source_store(src, mems)
    tgt = tmp_path / "tgt" / ".synapse"
    migrate.export_jsonl_to_moneta(src, tgt, dry_run=False)

    vr = migrate.verify_export(src, tgt, spot_check=5)
    assert vr.error is None, vr.error
    assert vr.count_parity                    # every source id present as a row
    assert vr.ids_missing_from_target == []
    assert len(vr.spot_checks) == 5
    assert vr.spot_ok                         # all 5 match field-for-field
    for sc in vr.spot_checks:
        assert sc.matched, sc.mismatched_fields


# ===========================================================================
# idempotency + keep-both collision  (target #5, guards the double-count)
# ===========================================================================

@moneta
def test_export_is_idempotent(tmp_path):
    src = tmp_path / "src" / ".synapse"
    mems = [_mem(f"m{i}") for i in range(5)]
    _make_source_store(src, mems)
    tgt = tmp_path / "tgt" / ".synapse"

    r1 = migrate.export_jsonl_to_moneta(src, tgt, dry_run=False)
    assert r1.added == 5
    r2 = migrate.export_jsonl_to_moneta(src, tgt, dry_run=False)  # re-run
    assert r2.added == 0                       # nothing re-deposited
    assert r2.skipped_identical == 5
    assert len(migrate.read_snapshot_rows(tgt)) == 5   # NOT doubled to 10


@moneta
def test_keep_both_on_id_collision_never_overwrites(tmp_path):
    tgt = tmp_path / "tgt" / ".synapse"
    # target seeded from source A: id mem_x, content "A"
    srcA = tmp_path / "a" / ".synapse"
    _make_source_store(srcA, [_mem("A", id="mem_x")])
    migrate.export_jsonl_to_moneta(srcA, tgt, dry_run=False)
    # source B: SAME id mem_x, DIFFERENT content -> collision
    srcB = tmp_path / "b" / ".synapse"
    _make_source_store(srcB, [_mem("B-different", id="mem_x")])
    rep = migrate.export_jsonl_to_moneta(srcB, tgt, dry_run=False)

    assert rep.kept_both == ["mem_x"]
    rows = migrate.read_snapshot_rows(tgt)
    assert len(rows) == 2                      # BOTH kept, never overwritten
    payloads = {json.loads(r["payload"])["content"] for r in rows}
    assert payloads == {"A", "B-different"}    # the original survives intact


# ===========================================================================
# dim safety — a 256-dim target is not crashed by the 384-dim default
# ===========================================================================

@moneta
def test_export_pins_existing_dim_no_crash(tmp_path):
    from synapse.memory.embedding import HashEmbedder
    tgt = tmp_path / "tgt" / ".synapse"
    # seed the target at 256-dim explicitly
    srcA = tmp_path / "a" / ".synapse"
    _make_source_store(srcA, [_mem("first")])
    r0 = migrate.export_jsonl_to_moneta(srcA, tgt, embedder=HashEmbedder(), dry_run=False)
    assert r0.error is None and r0.embedding_dim == 256
    assert migrate.snapshot_dim(tgt) == 256
    # now export MORE with embedder=None: the exporter must detect 256 and pin,
    # NOT open at the 384 default (which would crash Moneta's hydrate).
    srcB = tmp_path / "b" / ".synapse"
    _make_source_store(srcB, [_mem("second")])
    r1 = migrate.export_jsonl_to_moneta(srcB, tgt, dry_run=False)  # embedder=None
    assert r1.error is None, r1.error
    assert r1.embedding_dim == 256
    assert len(migrate.read_snapshot_rows(tgt)) == 2


# ===========================================================================
# 4) WRITE-THROUGH PROBE — post-flip a write lands in BOTH  (acceptance #4)
# ===========================================================================

@moneta
def test_writethrough_write_lands_in_moneta_and_jsonl(tmp_path):
    from synapse.memory.writethrough_store import WriteThroughStore
    from synapse.memory.embedding import HashEmbedder
    from synapse.memory.store import MemoryStore

    store_dir = tmp_path / "live" / ".synapse"
    store_dir.mkdir(parents=True)
    wt = WriteThroughStore.from_storage_dir(store_dir, embedder=HashEmbedder())
    try:
        m = _mem("a memory written after the flip", tags=["golive"])
        wt.add(m)
        wt.save()
        assert wt.count() >= 1                 # reads served from Moneta (active)
    finally:
        wt.close()

    # INDEPENDENT disk proof: the id is in BOTH stores (fallback armed)
    moneta_ids = {migrate._payload_id(r) for r in migrate.read_snapshot_rows(store_dir)}
    assert m.id in moneta_ids                  # landed in Moneta

    net = MemoryStore(store_dir, background_load=False)
    net._wait_loaded()
    jsonl_ids = {x.id for x in net.all()}
    assert m.id in jsonl_ids                    # landed in JSONL net
    assert wt.report.net_armed


@moneta
def test_writethrough_net_write_is_isolated_and_loud(tmp_path, caplog):
    """A net failure never breaks the caller, but is recorded (never silent)."""
    from synapse.memory.writethrough_store import WriteThroughStore, WriteThroughReport

    class _BoomNet:
        def add(self, memory):
            raise IOError("disk full")

        def save(self):
            pass

    class _OKPrimary:
        def __init__(self):
            self.added = []

        def add(self, memory):
            self.added.append(memory.id)
            return memory.id

        def save(self):
            pass

    wt = WriteThroughStore(_OKPrimary(), _BoomNet(), report=WriteThroughReport())
    m = _mem("survives a net failure")
    # caller is NOT broken by the net failure
    assert wt.add(m) == m.id
    assert m.id in wt.primary.added            # active write still happened
    assert not wt.report.net_armed             # but the net is flagged un-armed
    assert wt.report.net_write_errors          # and the failure is recorded
