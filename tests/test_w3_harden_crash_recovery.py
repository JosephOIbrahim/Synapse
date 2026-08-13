"""W3-HARDEN target 1 — crash recovery: a write interrupted mid-stage leaves the
root intact and the last durable state readable.

Spec ``docs/SYNAPSE-memory-engineering-spec.md`` §8: *"Crash-recovery: partial
stage writes don't corrupt the root."* Acceptance: *"kill-mid-write then reopen:
root parses, last durable memory readable, no corruption."*

The mechanism under test (VERIFIED live, not asserted from docs):
  * Moneta ``durability.snapshot_ecs`` writes ``snapshot.json.tmp`` -> ``fsync``
    -> ``os.replace`` (atomic). An interruption before the replace leaves the
    previous good ``snapshot.json`` untouched — never a torn root.
    (moneta/durability.py:108-116)
  * ``MonetaBackedStore.add()`` snapshots synchronously on EVERY deposit, so the
    "last durable state" is the last completed deposit (moneta_store.py:445-456).
  * On reopen, ``MonetaBackedStore._quarantine_if_corrupt`` runs BEFORE Moneta's
    bare ``json.load`` hydrate, so even a somehow-torn root is renamed aside and
    the store opens fresh rather than crashing (moneta_store.py:319-350).

Skipped cleanly (house rule: unobtainable -> UNKNOWN, never a silent pass) when
Moneta is not importable in this environment.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from synapse.memory import moneta_runtime as mr

pytestmark = pytest.mark.skipif(
    not mr.moneta_available(),
    reason=f"Moneta not importable ({mr.import_error()}) — crash-recovery is "
           "UNKNOWN in this environment, not a pass",
)

from synapse.memory.moneta_store import MonetaBackedStore  # noqa: E402
from synapse.memory.models import Memory, MemoryType  # noqa: E402


def _mem(cid: str, content: str) -> Memory:
    return Memory(id=cid, content=content, summary=content,
                  memory_type=MemoryType.NOTE)


def _reopen_ids(storage_dir) -> list:
    store = MonetaBackedStore.from_storage_dir(storage_dir)
    try:
        return sorted(m.id for m in store.all())
    finally:
        store.close()


# ---------------------------------------------------------------------------
# in-process: a snapshot whose atomic replace is interrupted leaves the prior
# durable root intact and readable.
# ---------------------------------------------------------------------------

def test_interrupted_replace_leaves_prior_durable_state_readable(tmp_path, monkeypatch):
    import moneta.durability as _dur

    store = MonetaBackedStore.from_storage_dir(tmp_path)
    store.add(_mem("mem_A", "durable first deposit"))  # save() completes -> A durable
    assert store.count() == 1

    # Now interrupt the NEXT snapshot exactly at the atomic replace, as a hard
    # crash would. save() swallows the failure (a failed persist must not crash
    # the panel) — the point is the ON-DISK root is untouched. The interruption
    # stays in force through close() too: a real crash never gets a clean
    # re-persist of B, so neither does this model (removing the restore is what
    # separates "crash" from "handled error then tidy shutdown").
    def boom_replace(src, dst, *a, **k):
        raise RuntimeError("simulated crash at os.replace")

    monkeypatch.setattr(_dur.os, "replace", boom_replace)
    store.add(_mem("mem_B", "deposit whose persist is interrupted"))
    store.close()  # close()'s own save() also fails (caught); B never persists

    # Reopen: the root parses, the last DURABLE deposit (A) is readable, and no
    # corruption (B's interrupted write never replaced the good root).
    snap = tmp_path / ".moneta" / "snapshot.json"
    assert snap.exists(), "the prior good root must still be on disk"
    json.loads(snap.read_text(encoding="utf-8"))  # parses -> not torn
    assert _reopen_ids(tmp_path) == ["mem_A"]


# ---------------------------------------------------------------------------
# true hard kill: os._exit() at the exact os.replace instant of the 2nd deposit.
# ---------------------------------------------------------------------------

def test_hard_kill_at_replace_instant_preserves_last_durable(tmp_path):
    child = textwrap.dedent('''
        import os, sys
        sys.path.insert(0, "python")
        from synapse.memory.moneta_store import MonetaBackedStore
        from synapse.memory.models import Memory, MemoryType
        import moneta.durability as _dur
        d = sys.argv[1]
        def mk(cid): return Memory(id=cid, content=cid, summary=cid, memory_type=MemoryType.NOTE)
        s = MonetaBackedStore.from_storage_dir(d)
        s.add(mk("mem_A"))                     # A durably saved (replace #1 ok)
        _armed = {"go": False}
        _real = _dur.os.replace
        def killing_replace(src, dst, *a, **k):
            if _armed["go"]:
                os._exit(137)                  # hard death mid-write, before replace
            return _real(src, dst, *a, **k)
        _dur.os.replace = killing_replace
        _armed["go"] = True
        s.add(mk("mem_B"))                     # dies inside this deposit's snapshot
        print("CHILD-SURVIVED-UNEXPECTEDLY")   # must never print
    ''')
    cf = tmp_path / "killchild.py"
    cf.write_text(child)
    proc = subprocess.run([sys.executable, str(cf), str(tmp_path)],
                          cwd=str(Path.cwd()),
                          capture_output=True, text=True)
    assert "CHILD-SURVIVED-UNEXPECTEDLY" not in proc.stdout, proc.stdout
    assert proc.returncode == 137, (proc.returncode, proc.stdout, proc.stderr)

    snap = tmp_path / ".moneta" / "snapshot.json"
    assert snap.exists()
    json.loads(snap.read_text(encoding="utf-8"))     # root parses after hard kill
    assert _reopen_ids(tmp_path) == ["mem_A"]         # last durable readable


# ---------------------------------------------------------------------------
# belt-and-suspenders: a genuinely torn root is quarantined on reopen, not
# loaded and not crashed.
# ---------------------------------------------------------------------------

def test_torn_root_is_quarantined_on_reopen(tmp_path):
    base = tmp_path / ".moneta"
    base.mkdir(parents=True)
    snap = base / "snapshot.json"
    snap.write_text('{"snapshot_version": 1, "rows": [ {"entity_id": ', encoding="utf-8")

    store = MonetaBackedStore.from_storage_dir(tmp_path)  # must NOT crash
    try:
        assert store.count() == 0  # started fresh rather than loading the torn root
    finally:
        store.close()
    quarantined = list(base.glob("snapshot.json.corrupt-*"))
    assert quarantined, "a torn root must be quarantined, not silently discarded"


def test_orphan_tmp_is_never_loaded_as_root(tmp_path):
    store = MonetaBackedStore.from_storage_dir(tmp_path)
    store.add(_mem("mem_A", "the real durable root"))
    store.close()

    base = tmp_path / ".moneta"
    # A leftover partial tmp from an earlier interrupted write, full of garbage.
    (base / "snapshot.json.tmp").write_text("GARBAGE NOT JSON", encoding="utf-8")

    assert _reopen_ids(tmp_path) == ["mem_A"]  # the .tmp is ignored; A survives


# ---------------------------------------------------------------------------
# pin the write primitive: the snapshot is written tmp-first then os.replace'd
# (a regression to a direct in-place write would reintroduce the torn-root risk)
# ---------------------------------------------------------------------------

def test_snapshot_write_primitive_is_tmp_then_atomic_replace(tmp_path, monkeypatch):
    import moneta.durability as _dur

    seen = {}
    real_replace = _dur.os.replace

    def spy_replace(src, dst, *a, **k):
        seen["src"] = str(src)
        seen["dst"] = str(dst)
        return real_replace(src, dst, *a, **k)

    monkeypatch.setattr(_dur.os, "replace", spy_replace)
    store = MonetaBackedStore.from_storage_dir(tmp_path)
    store.add(_mem("mem_A", "x"))
    store.close()

    assert seen.get("src", "").endswith(".tmp"), seen
    assert seen.get("dst", "").endswith("snapshot.json"), seen
