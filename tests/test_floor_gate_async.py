"""Tests for the FloorGate deferred-fsync durability split.

The provenance hook removes the synchronous ~3.5ms ``os.fsync`` from the dispatch
thread on the SUCCESS path WITHOUT weakening the audit guarantee
("provenance or it did not happen"). This pins the exact safety model:

* ERROR path: the failure record is written with ``fsync=True`` SYNCHRONOUSLY — durable
  on stable storage BEFORE the exception propagates, and NEVER handed to the background
  pool.
* SUCCESS path: content + final filename are committed SYNCHRONOUSLY (process-crash
  durable); only the ``os.fsync`` (power-loss durability) is deferred to the background
  executor — so the file is fully present the instant ``wrap`` returns, before the
  background fsync runs.
* ``flush_fsync()`` drains the pending background fsyncs (used by tests / atexit).
* Record ORDERING is fixed at submit time (op_id sequence + synchronous write+replace),
  unaffected by deferring the fsync.
* Task 2: a very large result digest is capped (length + head slice); small results keep
  the unchanged full-payload sha256.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading

import pytest

import synapse.core.floor_gate as fg
from synapse.core.floor_gate import FloorGate


def _records(provenance_dir):
    """All provenance records under ``provenance_dir``, sorted by filename."""
    out = []
    if not os.path.isdir(provenance_dir):
        return out
    for name in sorted(os.listdir(provenance_dir)):
        if name.endswith(".json"):
            with open(os.path.join(provenance_dir, name), encoding="utf-8") as fh:
                out.append(json.loads(fh.read()))
    return out


def _full_sha256(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


@pytest.fixture
def prov_dir(tmp_path, monkeypatch):
    """Point the FloorGate's provenance root at a tmp dir; default to async fsync."""
    d = tmp_path / "provenance"
    monkeypatch.setenv("SYNAPSE_PROVENANCE_DIR", str(d))
    monkeypatch.delenv("SYNAPSE_FLOOR_FSYNC_SYNC", raising=False)
    return str(d)


# ---------------------------------------------------------------------------
# ERROR path: synchronous + durable BEFORE the exception propagates
# ---------------------------------------------------------------------------

def test_error_path_is_sync_and_durable_before_raise(prov_dir, monkeypatch):
    """An op that raises records ``outcome='error'`` durably, and NEVER defers."""
    submits = []
    monkeypatch.setattr(fg, "_submit_fsync", lambda p: submits.append(p))

    gate = FloorGate()

    def boom(_payload):
        raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError, match="kaboom"):
        gate.wrap("delete_node", {"node": "/obj/x"}, boom)

    # The instant the exception surfaced the error record is already complete on disk.
    recs = _records(prov_dir)
    assert len(recs) == 1
    assert recs[0]["outcome"] == "error"
    assert recs[0]["error_type"] == "RuntimeError"
    # Error records are fsynced inline — the background pool is never used for them.
    assert submits == []


def test_error_path_calls_write_report_with_fsync_true(prov_dir, monkeypatch):
    """White-box: the error record's write goes through ``write_report(fsync=True)``."""
    import sys
    import synapse.cognitive.tools.write_report  # ensure the submodule is imported
    wr = sys.modules["synapse.cognitive.tools.write_report"]

    seen = []
    real = wr.write_report

    def spy(*a, **k):
        seen.append(k.get("fsync"))
        return real(*a, **k)

    monkeypatch.setattr(wr, "write_report", spy)

    gate = FloorGate()
    with pytest.raises(ValueError):
        gate.wrap("delete_node", {"n": 1}, lambda p: (_ for _ in ()).throw(ValueError("x")))

    assert seen == [True], "error path must fsync synchronously (durable before raise)"


# ---------------------------------------------------------------------------
# SUCCESS path: content present immediately, only the fsync is deferred
# ---------------------------------------------------------------------------

def test_success_path_calls_write_report_with_fsync_false(prov_dir, monkeypatch):
    """White-box: the success record's write defers the fsync (``fsync=False``)."""
    import sys
    import synapse.cognitive.tools.write_report  # ensure the submodule is imported
    wr = sys.modules["synapse.cognitive.tools.write_report"]

    seen = []
    real = wr.write_report

    def spy(*a, **k):
        seen.append(k.get("fsync"))
        return real(*a, **k)

    monkeypatch.setattr(wr, "write_report", spy)

    gate = FloorGate()
    gate.wrap("set_parm", {"a": 1}, lambda p: {"ok": True})
    fg.flush_fsync(timeout=5)

    assert seen == [False], "success path must defer the fsync off the dispatch thread"


def test_success_content_present_before_background_fsync(prov_dir, monkeypatch):
    """The record + content exist the instant ``wrap`` returns, before the bg fsync runs.

    Gate the background fsync on an Event so the test can observe the window in which the
    file is already on disk (process-crash durable) while the deferred fsync has NOT yet
    completed — proving the write+replace is synchronous and only the fsync deferred.
    """
    started = threading.Event()
    release = threading.Event()
    done = threading.Event()
    real_do_fsync = fg._do_fsync

    def gated(path):
        started.set()
        release.wait(5)
        real_do_fsync(path)
        done.set()

    monkeypatch.setattr(fg, "_do_fsync", gated)

    gate = FloorGate()
    gate.wrap("set_parm", {"a": 1}, lambda p: {"ok": True})

    # Synchronously durable for a process crash: content + final filename already present.
    recs = _records(prov_dir)
    assert len(recs) == 1 and recs[0]["outcome"] == "ok"

    # The fsync was handed to the background pool (off the dispatch thread) and is gated.
    assert started.wait(5), "deferred fsync should run on a background thread"
    assert not done.is_set(), "fsync must NOT have completed inline on the dispatch thread"

    release.set()
    fg.flush_fsync(timeout=5)
    assert done.is_set(), "flush_fsync must drain the pending background fsync"


def test_flush_fsync_drains_pending(prov_dir):
    """``flush_fsync`` waits for the deferred fsyncs of several success ops."""
    gate = FloorGate()
    for i in range(5):
        gate.wrap("set_parm", {"i": i}, lambda p: {"ok": True})

    fg.flush_fsync(timeout=5)  # must return after all deferred fsyncs complete
    assert len(_records(prov_dir)) == 5


def test_sync_env_flag_makes_fsync_inline(prov_dir, monkeypatch):
    """``$SYNAPSE_FLOOR_FSYNC_SYNC`` forces the fsync inline (deterministic tests)."""
    monkeypatch.setenv("SYNAPSE_FLOOR_FSYNC_SYNC", "1")
    ran = []
    monkeypatch.setattr(fg, "_do_fsync", lambda p: ran.append(p))

    gate = FloorGate()
    gate.wrap("set_parm", {"a": 1}, lambda p: {"ok": True})

    # Inline: the fsync already executed on the dispatch thread before wrap returned.
    assert len(ran) == 1


# ---------------------------------------------------------------------------
# Ordering preserved (sequence assigned at submit time, not write time)
# ---------------------------------------------------------------------------

def test_record_ordering_preserved(prov_dir):
    """Records keep submit-order via the op_id sequence, independent of deferred fsync."""
    gate = FloorGate()
    call_order = []

    def fn(_payload):
        # ``current_op_id`` is this op's own freshly-minted id (set by wrap around fn).
        call_order.append(FloorGate.current_op_id())
        return {"ok": True}

    for i in range(8):
        gate.wrap("set_parm", {"i": i}, fn)
    fg.flush_fsync(timeout=5)

    recs = _records(prov_dir)
    assert len(recs) == 8

    def seq(op_id):
        return int(op_id.rsplit("-", 1)[1])

    disk_order = [r["op_id"] for r in sorted(recs, key=lambda r: seq(r["op_id"]))]
    # The on-disk sequence order matches the order the ops were submitted.
    assert disk_order == call_order
    # And the sequence numbers are strictly increasing (monotonic, minted at submit time).
    seqs = [seq(o) for o in disk_order]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)


# ---------------------------------------------------------------------------
# Task 2: large-result digest is capped; small results unchanged
# ---------------------------------------------------------------------------

def test_small_result_digest_is_full_sha256(prov_dir):
    """Normal results keep the exact full-payload sha256 (unchanged behavior)."""
    result = {"status": "ok", "count": 7, "nested": {"k": "v"}}
    gate = FloorGate()
    gate.wrap("create_node", {"a": 1}, lambda p: result)
    fg.flush_fsync(timeout=5)

    rec = _records(prov_dir)[0]
    assert rec["result_digest"] == _full_sha256(result)


def test_large_result_digest_is_capped(prov_dir):
    """A 127KB-class result is digested over a bounded summary, not the whole payload."""
    big = {"dump": "x" * 200_000}  # serialized well past the cap threshold
    gate = FloorGate()
    gate.wrap("create_node", {"a": 1}, lambda p: big)
    fg.flush_fsync(timeout=5)

    rec = _records(prov_dir)[0]
    # Still a clean sha256 hex, but NOT the full-payload digest.
    assert len(rec["result_digest"]) == 64
    assert rec["result_digest"] != _full_sha256(big)
    # Deterministic + sensitive to size/head: identical large result hashes the same...
    assert fg._result_digest(big) == rec["result_digest"]
    # ...and a different head produces a different capped digest.
    other = {"dump": "y" * 200_000}
    assert fg._result_digest(other) != rec["result_digest"]


def test_result_digest_threshold_boundary(prov_dir):
    """At/under the threshold -> full sha256; just over -> capped (different) digest."""
    cap = fg.RESULT_DIGEST_MAX_BYTES
    # A plain string serializes to its bytes + 2 surrounding quotes.
    at = "a" * (cap - 2)               # serialized length == cap -> full hash
    over = "b" * (cap + 10)            # serialized length > cap  -> capped hash
    assert fg._result_digest(at) == _full_sha256(at)
    assert fg._result_digest(over) != _full_sha256(over)
