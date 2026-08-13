"""W3-HARDEN target 2 — concurrency: two sessions writing, and the ACTUAL
USD layer-merge semantics, OBSERVED (never asserted from USD documentation).

Spec ``docs/SYNAPSE-memory-engineering-spec.md`` §8: *"Concurrency: two sessions
writing don't clobber (confirm USD layer-merge semantics)."* Acceptance:
*"two concurrent writers: both memories present afterwards, observed merge
semantics receipted."*

Crucible criterion (W3-HARDEN mission): *"concurrency claims are observed, not
asserted from USD documentation — the test output is the receipt."*

What the test output RECEIPTS, all observed live on this build:
  * In-process, a 2nd handle on the same storage URI is REFUSED
    (``MonetaResourceLockedError``, moneta/api.py:199) — single-owner by
    construction, so there is never an in-process clobber.
  * The URI lock is PROCESS-LOCAL. Two separate OS processes on the same dir
    both open; the whole-ECS snapshot is last-writer-wins, so a deposit can be
    CLOBBERED. This is the boundary; the fix (a cross-process owner lock)
    belongs to W3-STORE which owns ``from_storage_dir`` (bus finding posted).
  * USD layer-merge: two memories authored to two DISTINCT sublayers compose
    into one root and BOTH survive — this is the "both present" mechanism the
    spec names, shown with real ``pxr``.
  * Two sessions SERIALIZED through the single-owner lock (write+close, then
    open+write) both survive — the intended single-user access pattern.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from synapse.memory import moneta_runtime as mr

pytestmark = pytest.mark.skipif(
    not mr.moneta_available(),
    reason=f"Moneta not importable ({mr.import_error()}) — concurrency semantics "
           "are UNKNOWN in this environment, not a pass",
)

from synapse.memory.moneta_store import MonetaBackedStore  # noqa: E402
from synapse.memory.models import Memory, MemoryType  # noqa: E402

try:
    from pxr import Sdf, Usd  # noqa: E402
    _PXR = True
except Exception:  # noqa: BLE001
    _PXR = False


def _mem(cid: str) -> Memory:
    return Memory(id=cid, content=cid, summary=cid, memory_type=MemoryType.NOTE)


# ---------------------------------------------------------------------------
# in-process: single-owner URI lock refuses a 2nd concurrent handle
# ---------------------------------------------------------------------------

def test_inprocess_second_handle_on_same_uri_is_refused(tmp_path):
    a = MonetaBackedStore.from_storage_dir(tmp_path)
    try:
        a.add(_mem("mem_A"))
        with pytest.raises(Exception) as exc:  # MonetaResourceLockedError
            MonetaBackedStore.from_storage_dir(tmp_path)
        assert "Locked" in type(exc.value).__name__ or "already held" in str(exc.value)
    finally:
        a.close()


# ---------------------------------------------------------------------------
# cross-process: the URI lock is process-local -> observe the clobber boundary
# ---------------------------------------------------------------------------

def test_cross_process_uri_lock_is_process_local(tmp_path):
    """RECEIPT: two OS processes both open the same store (no cross-process
    mutual exclusion), and the whole-ECS snapshot is last-writer-wins."""
    child = textwrap.dedent('''
        import sys
        sys.path.insert(0, "python")
        from synapse.memory.moneta_store import MonetaBackedStore
        from synapse.memory.models import Memory, MemoryType
        d, cid = sys.argv[1], sys.argv[2]
        try:
            s = MonetaBackedStore.from_storage_dir(d)
            s.add(Memory(id=cid, content=cid, summary=cid, memory_type=MemoryType.NOTE))
            s.close()
            print("OPENED_OK", cid)
        except Exception as e:
            print("REFUSED", cid, type(e).__name__)
    ''')
    cf = tmp_path / "child.py"
    cf.write_text(child)

    def spawn(cid):
        return subprocess.Popen(
            [sys.executable, str(cf), str(tmp_path), cid],
            cwd=str(Path.cwd()), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True)

    p1, p2 = spawn("mem_P1"), spawn("mem_P2")
    out = (p1.communicate()[0] or "") + (p2.communicate()[0] or "")
    opened = out.count("OPENED_OK")

    # The core observed finding: cross-process opens are NOT mutually excluded.
    assert opened == 2, (
        f"expected BOTH processes to open the same store (process-local lock), "
        f"got {opened}. Output:\n{out}")

    survivors = sorted(m.id for m in MonetaBackedStore.from_storage_dir(tmp_path).all())
    # Receipt the observed durability: with no cross-process lock, the snapshot
    # is last-writer-wins, so <2 survivors is the documented clobber; ==2 means
    # the two saves happened to serialize on disk. Either way this pins that the
    # protection does NOT come from a cross-process lock.
    assert 1 <= len(survivors) <= 2, survivors
    print(f"CROSS_PROCESS_SURVIVORS={survivors} "
          f"({'CLOBBER' if len(survivors) < 2 else 'serialized-safe'})")


# ---------------------------------------------------------------------------
# USD layer-merge: two memories in two distinct sublayers -> both survive
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _PXR, reason="pxr not importable — USD merge is UNKNOWN here")
def test_usd_layer_merge_composes_both_sublayers(tmp_path):
    """The 'both present' mechanism, observed with real USD composition: two
    sessions author to two different sublayers; the root composes both."""
    root = Sdf.Layer.CreateNew(str(tmp_path / "cortex_root.usda"))
    sub_a = Sdf.Layer.CreateNew(str(tmp_path / "cortex_session_a.usda"))
    sub_b = Sdf.Layer.CreateNew(str(tmp_path / "cortex_session_b.usda"))

    with Sdf.ChangeBlock():
        spec = Sdf.CreatePrimInLayer(sub_a, Sdf.Path("/Memory_A"))
        spec.specifier = Sdf.SpecifierDef
    with Sdf.ChangeBlock():
        spec = Sdf.CreatePrimInLayer(sub_b, Sdf.Path("/Memory_B"))
        spec.specifier = Sdf.SpecifierDef
    sub_a.Save()
    sub_b.Save()

    # Root references both sublayers — this is the merge.
    root.subLayerPaths[:] = [sub_a.identifier, sub_b.identifier]
    root.Save()

    stage = Usd.Stage.Open(root)
    paths = {p.GetPath().pathString for p in stage.Traverse()}
    assert "/Memory_A" in paths and "/Memory_B" in paths, (
        f"USD composition must merge both sublayers; saw {sorted(paths)}")


@pytest.mark.skipif(not _PXR, reason="pxr not importable — USD merge is UNKNOWN here")
def test_usd_same_sublayer_two_writers_do_not_merge(tmp_path):
    """The BOUNDARY, observed on DISK BYTES (bypassing pxr's in-process layer
    cache): two independent writers to the SAME file do NOT merge — the file
    ends up with at most one of the two prims, never both. This is the contrast
    that makes distinct sublayers (the test above) the safe pattern: composition
    merges, a shared file does not."""
    shared = str(tmp_path / "shared.usda")
    w1 = Sdf.Layer.CreateNew(shared)
    with Sdf.ChangeBlock():
        Sdf.CreatePrimInLayer(w1, Sdf.Path("/Memory_1")).specifier = Sdf.SpecifierDef
    w1.Save()

    # A second session that never saw w1's content, authoring over the same path.
    w2 = Sdf.Layer.CreateAnonymous()
    with Sdf.ChangeBlock():
        Sdf.CreatePrimInLayer(w2, Sdf.Path("/Memory_2")).specifier = Sdf.SpecifierDef
    w2.Export(shared)  # writes w2's whole content over the file

    disk = Path(shared).read_text(encoding="utf-8")
    has_1, has_2 = "Memory_1" in disk, "Memory_2" in disk
    # The receiptable invariant: a single shared file is NOT a merge surface.
    assert not (has_1 and has_2), (
        f"a shared file must not contain both independently-authored prims; "
        f"disk had Memory_1={has_1} Memory_2={has_2}")
    assert has_1 or has_2  # exactly one writer's content survives on disk


# ---------------------------------------------------------------------------
# serialized through the single-owner lock: both sessions' memories survive
# ---------------------------------------------------------------------------

def test_two_sessions_serialized_through_lock_both_survive(tmp_path):
    """The intended single-user pattern: the single-owner lock serializes access
    (session A closes before B opens), and BOTH deposits are present."""
    a = MonetaBackedStore.from_storage_dir(tmp_path)
    a.add(_mem("mem_sessionA"))
    a.close()  # release the URI lock

    b = MonetaBackedStore.from_storage_dir(tmp_path)
    b.add(_mem("mem_sessionB"))
    b.close()

    survivors = sorted(m.id for m in MonetaBackedStore.from_storage_dir(tmp_path).all())
    assert survivors == ["mem_sessionA", "mem_sessionB"], survivors
