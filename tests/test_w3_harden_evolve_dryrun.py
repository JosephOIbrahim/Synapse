"""W3-HARDEN target 4 — post-migration consolidation: a dry-run over the real
corpus produces a sane audit and mutates NOTHING. Closes the W3-EVOLVE note
(*"the real corpus pass lands under W3-HARDEN acceptance"*).

Spec ``docs/SYNAPSE-memory-engineering-spec.md`` §6 Phase 4 / §8 Phase 6.
Acceptance: *"post-migration evolve dry-run returns a sane audit over the real
corpus."*

The dry-run uses Moneta's OWN read-only projection — ``ConsolidationRunner.
classify(ecs)`` (moneta/consolidation.py:99) — which returns ``(prune_ids,
stage_ids)`` WITHOUT mutating. This is the primitive Moneta itself names for a
true preview: its ``run_pass(sequential_writer=None)`` is NOT read-only — it
"still prunes" (consolidation.py:143). We therefore never call ``run_pass`` and
never ``save()``; the audit is a pure classification over a point-in-time view.

Skipped cleanly (house rule: unobtainable -> UNKNOWN, never a silent pass) when
Moneta is not importable.
"""

from __future__ import annotations

import inspect
import json
import shutil
from pathlib import Path

import pytest

from synapse.memory import moneta_runtime as mr

pytestmark = pytest.mark.skipif(
    not mr.moneta_available(),
    reason=f"Moneta not importable ({mr.import_error()}) — consolidation dry-run "
           "is UNKNOWN in this environment, not a pass",
)

from synapse.memory.embedding import HashEmbedder  # noqa: E402
from synapse.memory.models import Memory, MemoryType  # noqa: E402
from synapse.memory.moneta_store import MonetaBackedStore  # noqa: E402


def _mem(cid: str, content: str, mtype=MemoryType.NOTE) -> Memory:
    return Memory(id=cid, content=content, summary=content, memory_type=mtype)


def _dry_run_audit(store: MonetaBackedStore) -> dict:
    """Non-destructive consolidation audit over a live store, via classify().

    Mirrors what ``run_sleep_pass`` would report (before/after counts + prune
    ids) but calls ONLY the read-only classifier — no prune, no stage-commit,
    no snapshot. The projected count is what a real pass WOULD leave.
    """
    handle = store._handle
    ecs = handle.ecs
    count_before = ecs.n
    prune_ids, stage_ids = handle.consolidation.classify(ecs)  # read-only
    return {
        "count_before": count_before,
        "would_prune_ids": [str(x) for x in prune_ids],
        "would_stage_ids": [str(x) for x in stage_ids],
        "projected_count_after": count_before - len(prune_ids),
    }


def _find_real_corpus() -> Path | None:
    """Locate a real on-disk Moneta corpus (``<dir>/.moneta/snapshot.json``).

    Searches the worktree and the enclosing main repo — the corpus is runtime
    data (typically gitignored) so it lives in the checkout that has been run,
    not necessarily this worktree. None -> the real-corpus pass is UNKNOWN here.
    """
    here = Path(__file__).resolve()
    candidates = []
    for anc in here.parents:
        candidates.append(anc / ".synapse" / "corpus")
        # the main repo above a .claude/worktrees/<name> layout
        if anc.name == "worktrees":
            candidates.append(anc.parent.parent / ".synapse" / "corpus")
    candidates.append(Path.cwd() / ".synapse" / "corpus")
    for c in candidates:
        if (c / ".moneta" / "snapshot.json").exists():
            return c
    return None


def _corpus_vector_dim(corpus: Path) -> int | None:
    data = json.loads((corpus / ".moneta" / "snapshot.json").read_text(encoding="utf-8"))
    rows = data.get("rows", [])
    if not rows:
        return None
    return len(rows[0].get("semantic_vector", []))


# ---------------------------------------------------------------------------
# THE real-corpus pass: a sane audit, zero mutation.
# ---------------------------------------------------------------------------

def test_dry_run_over_real_corpus_is_sane_and_non_mutating(tmp_path):
    corpus = _find_real_corpus()
    if corpus is None:
        pytest.skip("no on-disk real corpus found — real-corpus dry-run UNKNOWN here")
    dim = _corpus_vector_dim(corpus)
    if dim is None:
        pytest.skip("real corpus is empty — nothing to audit")

    # Copy so the shared real store is NEVER touched (data safety), and read it
    # with an embedder whose dim matches the stored vectors (matching the reader
    # to existing data — the vector dim is W3-DIM's concern, not the audit's;
    # classify() does not use vectors at all).
    work = tmp_path / "corpus"
    shutil.copytree(corpus, work)
    snap = work / ".moneta" / "snapshot.json"

    store = MonetaBackedStore.from_storage_dir(work, embedder=HashEmbedder(dim=dim))
    try:
        ids_before = sorted(m.id for m in store.all())
        count_before = store.count()
        bytes_after_open = snap.read_bytes()

        audit = _dry_run_audit(store)

        bytes_after_dryrun = snap.read_bytes()
        ids_after = sorted(m.id for m in store.all())
        count_after = store.count()

        # --- sane audit ---
        assert count_before > 0, "expected a populated real corpus"
        assert audit["count_before"] == count_before
        assert isinstance(audit["would_prune_ids"], list)
        assert isinstance(audit["would_stage_ids"], list)
        assert audit["projected_count_after"] == count_before - len(audit["would_prune_ids"])
        assert 0 <= audit["projected_count_after"] <= count_before

        # --- ZERO mutation: the dry-run wrote nothing to disk and removed
        #     nothing from the store (a store diff shows zero mutation) ---
        assert bytes_after_dryrun == bytes_after_open, "dry-run must not write the snapshot"
        assert ids_after == ids_before, "dry-run must not add/remove memories"
        assert count_after == count_before
    finally:
        store.close()


# ---------------------------------------------------------------------------
# A hermetic corpus of real memory content — always runs (portable evidence).
# ---------------------------------------------------------------------------

def test_dry_run_over_built_corpus_is_sane_and_non_mutating(tmp_path):
    store = MonetaBackedStore.from_storage_dir(tmp_path, embedder=HashEmbedder(dim=256))
    try:
        store.add(_mem("mem_note1", "karma xpu render settings for the hero shot"))
        store.add(_mem("mem_dec1", "chose usdrender_rop over usdrender", MemoryType.DECISION))
        store.add(_mem("mem_ctx1", "solaris stage has 3 mesh prims, no UVs"))
        count_before = store.count()
        assert count_before == 3

        snap = tmp_path / ".moneta" / "snapshot.json"
        bytes_before = snap.read_bytes()
        audit = _dry_run_audit(store)
        assert snap.read_bytes() == bytes_before  # dry-run wrote nothing

        assert audit["count_before"] == 3
        # fresh deposits are high-utility -> nothing prunes; a healthy corpus's
        # sane audit is "nothing to remove".
        assert audit["would_prune_ids"] == []
        assert audit["projected_count_after"] == 3
        assert store.count() == 3  # unmutated
    finally:
        store.close()


# ---------------------------------------------------------------------------
# the audit is NON-TRIVIAL: it detects a prunable entity, and still removes
# nothing (dry-run).
# ---------------------------------------------------------------------------

def test_dry_run_detects_prunable_without_removing(tmp_path):
    import time

    store = MonetaBackedStore.from_storage_dir(tmp_path, embedder=HashEmbedder(dim=256))
    try:
        store.add(_mem("mem_fresh", "a fresh, high-utility memory"))
        # Age the entity far into the future so its utility decays below the
        # prune threshold (utility<0.1 AND attended<3 -> prune candidate).
        handle = store._handle
        handle.ecs.decay_all(handle.decay.lambda_, time.time() + 10**9)

        n_before = handle.ecs.n
        audit = _dry_run_audit(store)

        assert len(audit["would_prune_ids"]) >= 1, "audit must detect the aged entity"
        assert handle.ecs.n == n_before, "classify() must not remove anything"
        assert store.count() == n_before
        assert store.get("mem_fresh") is not None  # still present after the dry-run
    finally:
        store.close()


# ---------------------------------------------------------------------------
# the spec's ONE ROOT CAUSE, live: a dim-mismatched reader cannot open the
# corpus. Documents that W3-DIM (Phase 0) has not landed in this base.
# ---------------------------------------------------------------------------

def test_dim_mismatch_is_the_documented_root_cause(tmp_path):
    corpus = _find_real_corpus()
    if corpus is None:
        pytest.skip("no on-disk real corpus — cannot demonstrate the dim seam here")
    dim = _corpus_vector_dim(corpus)
    if dim is None:
        pytest.skip("real corpus empty")
    work = tmp_path / "corpus"
    shutil.copytree(corpus, work)

    wrong_dim = dim + 128  # deterministically not the corpus's stored dim
    with pytest.raises(Exception) as exc:
        MonetaBackedStore.from_storage_dir(work, embedder=HashEmbedder(dim=wrong_dim))
    assert "dim mismatch" in str(exc.value), str(exc.value)


# ---------------------------------------------------------------------------
# the existing synapse_evolve_memory dry-run is structurally non-mutating
# (static pin: the dry_run branch returns BEFORE any evolve/author call)
# ---------------------------------------------------------------------------

def test_existing_evolve_memory_dry_run_is_structurally_non_mutating():
    from synapse.server.handlers_memory import MemoryHandlerMixin

    src = inspect.getsource(MemoryHandlerMixin._handle_evolve_memory)
    # The dry_run early-return must precede the only authoring call.
    dry_idx = src.find('if dry_run:')
    evolve_idx = src.find('evolve_to_structured')
    assert dry_idx != -1, "evolve handler must have a dry_run branch"
    assert evolve_idx == -1 or dry_idx < evolve_idx, (
        "the dry_run branch must return before the authoring call — a dry-run "
        "that can reach evolve_to_structured is not a dry-run")
