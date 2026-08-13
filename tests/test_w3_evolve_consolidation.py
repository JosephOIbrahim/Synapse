"""W3-EVOLVE — charmeleon->charizard store consolidation.

Pins the four acceptance predicates AND the crucible re-attacks:

  acc1  dry-run returns the audit (before/after counts + pruned ids) and a store
        diff shows ZERO mutation
  acc2  apply without the approval token refuses loudly
  acc3  a protected memory survives an approved consolidation run
  acc4  an approved run demonstrably reduces count with the audit trail intact

  crucible  merge preserves information (no field loss)
  crucible  apply-without-approval / wrong-token / protected-prune are structurally
            impossible

Runs standalone (no ``hou`` — conftest plants a fake). The store under test is
the pre-migration JSONL ``MemoryStore``, which the mission note names as the
machinery-proof surface; a Moneta-skip class proves the append/consolidate
backend degrades honestly.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory.consolidation import (  # noqa: E402
    ConsolidationNotApproved,
    ConsolidationUnsupported,
    apply_consolidation,
    is_protected,
    plan_consolidation,
)
from synapse.memory.models import Memory, MemoryTier, MemoryType  # noqa: E402
from synapse.memory.store import MemoryStore  # noqa: E402


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------

def _mem(content, *, mtype=MemoryType.NOTE, tier=MemoryTier.SHOT, source="user",
         tags=None, keywords=None, created_at="2026-01-01T00:00:00Z") -> Memory:
    return Memory(
        content=content, memory_type=mtype, tier=tier, source=source,
        tags=list(tags or []), keywords=list(keywords or []), created_at=created_at,
    )


def _store(tmp_path) -> MemoryStore:
    s = MemoryStore(tmp_path / ".synapse", background_load=False)
    s._wait_loaded()
    return s


def _snapshot(store):
    """id -> serialized payload, plus the raw count: the zero-mutation witness."""
    return {m.id: m.to_json() for m in store.all()}, store.count()


# --------------------------------------------------------------------------
# is_protected predicate (structural exclusion)
# --------------------------------------------------------------------------

def test_is_protected_predicate():
    assert is_protected(_mem("x", mtype=MemoryType.DECISION)) is True
    assert is_protected(_mem("x", tier=MemoryTier.SHOW)) is True
    assert is_protected(_mem("x", source="gate")) is True
    assert is_protected(_mem("x")) is False  # plain NOTE/user/SHOT


# --------------------------------------------------------------------------
# acc1 — dry-run returns the audit AND mutates nothing
# --------------------------------------------------------------------------

def test_dry_run_returns_audit_and_zero_mutation(tmp_path):
    store = _store(tmp_path)
    store.add(_mem("duplicate note about karma", created_at="2026-01-01T00:00:00Z"))
    store.add(_mem("duplicate note about karma", created_at="2026-01-02T00:00:00Z"))
    store.add(_mem("a unique observation", created_at="2026-01-03T00:00:00Z"))

    before_payloads, before_count = _snapshot(store)

    audit = plan_consolidation(store.all())

    # audit shape
    assert audit.dry_run is True and audit.applied is False
    assert audit.count_before == 3
    assert audit.count_after == 2          # one duplicate folds away
    assert len(audit.pruned_ids) == 1
    assert len(audit.merges) == 1
    assert audit.merges[0].merged_ids == audit.pruned_ids
    assert audit.approval_token           # a plan-bound token was produced

    # ZERO mutation: payloads and count are byte-identical after the dry-run
    after_payloads, after_count = _snapshot(store)
    assert after_payloads == before_payloads
    assert after_count == before_count == 3


def test_dry_run_token_is_stable(tmp_path):
    store = _store(tmp_path)
    store.add(_mem("dup", created_at="2026-01-01T00:00:00Z"))
    store.add(_mem("dup", created_at="2026-01-02T00:00:00Z"))
    a = plan_consolidation(store.all())
    b = plan_consolidation(store.all())
    assert a.approval_token == b.approval_token   # deterministic, order-independent


# --------------------------------------------------------------------------
# acc2 + crucible — apply without / with a wrong token refuses loudly
# --------------------------------------------------------------------------

def test_apply_without_token_refuses(tmp_path):
    store = _store(tmp_path)
    store.add(_mem("dup", created_at="2026-01-01T00:00:00Z"))
    store.add(_mem("dup", created_at="2026-01-02T00:00:00Z"))
    before = _snapshot(store)

    with pytest.raises(ConsolidationNotApproved):
        apply_consolidation(store, approval_token=None)
    with pytest.raises(ConsolidationNotApproved):
        apply_consolidation(store, approval_token="")

    assert _snapshot(store) == before    # refusal never mutated the store


def test_apply_wrong_token_refuses(tmp_path):
    store = _store(tmp_path)
    store.add(_mem("dup", created_at="2026-01-01T00:00:00Z"))
    store.add(_mem("dup", created_at="2026-01-02T00:00:00Z"))
    before = _snapshot(store)

    with pytest.raises(ConsolidationNotApproved):
        apply_consolidation(store, approval_token="deadbeefdeadbeef")

    assert _snapshot(store) == before


# --------------------------------------------------------------------------
# acc3 + acc4 — protected survives; approved run reduces count; audit intact
# --------------------------------------------------------------------------

def test_protected_survives_and_count_reduces(tmp_path):
    store = _store(tmp_path)
    # A gate-sourced convention (protected) duplicated by a user note (unprotected).
    protected = _mem("show-wide naming convention", source="gate",
                     created_at="2026-01-02T00:00:00Z")
    dup = _mem("show-wide naming convention", source="user",
               created_at="2026-01-01T00:00:00Z")   # earlier, but NOT the survivor
    unique = _mem("standalone note", created_at="2026-01-03T00:00:00Z")
    for m in (protected, dup, unique):
        store.add(m)
    assert store.count() == 3

    plan = plan_consolidation(store.all())
    # the protected memory is never in the prune set; the unprotected dup is
    assert protected.id not in plan.pruned_ids
    assert dup.id in plan.pruned_ids

    audit = apply_consolidation(store, approval_token=plan.approval_token)

    ids_after = {m.id for m in store.all()}
    assert protected.id in ids_after            # acc3: protected survives
    assert dup.id not in ids_after              # its unprotected duplicate pruned
    assert unique.id in ids_after
    assert store.count() == 2                   # acc4: count demonstrably reduced
    assert audit.applied is True
    assert audit.count_before == 3 and audit.count_after == 2
    assert audit.backup_path and Path(audit.backup_path).exists()  # audit trail intact
    assert audit.merges[0].survivor_id == protected.id             # protected forced survivor


def test_all_unprotected_duplicates_reduce_by_count(tmp_path):
    store = _store(tmp_path)
    for i in range(4):
        store.add(_mem("same repeated note", created_at=f"2026-01-0{i+1}T00:00:00Z"))
    store.add(_mem("different note", created_at="2026-02-01T00:00:00Z"))
    assert store.count() == 5

    plan = plan_consolidation(store.all())
    assert len(plan.pruned_ids) == 3            # 4 dups -> 1 survivor
    audit = apply_consolidation(store, approval_token=plan.approval_token)
    assert store.count() == 2
    assert audit.count_after == 2


# --------------------------------------------------------------------------
# crucible — merge preserves information (no field loss is a BLOCK)
# --------------------------------------------------------------------------

def test_merge_preserves_information(tmp_path):
    store = _store(tmp_path)
    survivor = _mem("shared content", tags=["alpha"], keywords=["ka"],
                    created_at="2026-01-01T00:00:00Z")   # earliest -> survivor
    absorbed = _mem("shared content", tags=["beta"], keywords=["kb"],
                    created_at="2026-01-02T00:00:00Z")
    store.add(survivor)
    store.add(absorbed)

    plan = plan_consolidation(store.all())
    apply_consolidation(store, approval_token=plan.approval_token)

    kept = store.get(survivor.id)
    assert kept is not None
    assert set(kept.tags) >= {"alpha", "beta"}          # union, nothing dropped
    assert set(kept.keywords) >= {"ka", "kb"}
    # the pruned copy's full pre-image is captured in the audit trail
    assert absorbed.id in plan.pruned_payloads


# --------------------------------------------------------------------------
# crucible — protected is NEVER pruned, even as an exact duplicate
# --------------------------------------------------------------------------

def test_protected_never_pruned_even_as_duplicate(tmp_path):
    store = _store(tmp_path)
    # mixed corpus with protected duplicates on every protection route
    store.add(_mem("decision text", mtype=MemoryType.DECISION, created_at="2026-01-01T00:00:00Z"))
    store.add(_mem("decision text", mtype=MemoryType.DECISION, created_at="2026-01-02T00:00:00Z"))
    store.add(_mem("show note", tier=MemoryTier.SHOW, created_at="2026-01-03T00:00:00Z"))
    store.add(_mem("show note", tier=MemoryTier.SHOW, created_at="2026-01-04T00:00:00Z"))

    plan = plan_consolidation(store.all())
    # every pruned id belongs to an UNprotected memory
    by_id = {m.id: m for m in store.all()}
    assert all(not is_protected(by_id[pid]) for pid in plan.pruned_ids)
    # an all-protected duplicate cluster prunes nothing
    assert plan.pruned_ids == []
    assert plan.count_before == plan.count_after == 4


def test_protected_wins_survivor_over_earlier_unprotected(tmp_path):
    store = _store(tmp_path)
    unprot = _mem("policy line", source="user", created_at="2026-01-01T00:00:00Z")
    prot = _mem("policy line", source="gate", created_at="2026-01-05T00:00:00Z")
    store.add(unprot)
    store.add(prot)
    plan = plan_consolidation(store.all())
    assert plan.merges[0].survivor_id == prot.id   # protected wins despite being later
    assert unprot.id in plan.pruned_ids


# --------------------------------------------------------------------------
# handler surface — synapse_evolve_memory routes target_stage=charizard
# --------------------------------------------------------------------------

def _handler():
    from synapse.server import handlers as handlers_mod
    return handlers_mod.SynapseHandler()


def _bind_store(h, store, monkeypatch):
    monkeypatch.setattr(
        h, "_get_bridge",
        lambda: SimpleNamespace(_synapse=SimpleNamespace(store=store)),
    )


def test_handler_dry_run_audit(tmp_path, monkeypatch):
    store = _store(tmp_path)
    store.add(_mem("dup", created_at="2026-01-01T00:00:00Z"))
    store.add(_mem("dup", created_at="2026-01-02T00:00:00Z"))
    before = _snapshot(store)

    h = _handler()
    _bind_store(h, store, monkeypatch)
    out = h._handle_evolve_memory({"target_stage": "charizard", "dry_run": True})

    assert out["stage"] == "charizard"
    assert out["dry_run"] is True
    assert out["count_before"] == 2 and out["count_after"] == 1
    assert len(out["pruned_ids"]) == 1
    assert out["approval_token"]
    assert _snapshot(store) == before          # handler dry-run: zero mutation


def test_handler_apply_without_token_refuses(tmp_path, monkeypatch):
    store = _store(tmp_path)
    store.add(_mem("dup", created_at="2026-01-01T00:00:00Z"))
    store.add(_mem("dup", created_at="2026-01-02T00:00:00Z"))
    before = _snapshot(store)

    h = _handler()
    _bind_store(h, store, monkeypatch)
    out = h._handle_evolve_memory({"target_stage": "charizard", "dry_run": False})

    assert out["applied"] is False
    assert out["refused"] is True
    assert "REFUSED" in out["error"]
    assert _snapshot(store) == before          # loud refusal, no mutation


def test_handler_apply_with_token_reduces_and_protects(tmp_path, monkeypatch):
    store = _store(tmp_path)
    store.add(_mem("convention", source="gate", created_at="2026-01-02T00:00:00Z"))
    store.add(_mem("convention", source="user", created_at="2026-01-01T00:00:00Z"))
    protected_id = next(m.id for m in store.all() if m.source == "gate")

    h = _handler()
    _bind_store(h, store, monkeypatch)

    preview = h._handle_evolve_memory({"target_stage": "charizard", "dry_run": True})
    token = preview["approval_token"]
    out = h._handle_evolve_memory(
        {"target_stage": "charizard", "dry_run": False, "approval_token": token})

    assert out["applied"] is True
    assert out["count_before"] == 2 and out["count_after"] == 1
    assert protected_id in {m.id for m in store.all()}   # protected survived the apply


def test_handler_no_store_is_honest(tmp_path, monkeypatch):
    h = _handler()
    monkeypatch.setattr(h, "_get_bridge",
                        lambda: SimpleNamespace(_synapse=SimpleNamespace(store=None)))
    out = h._handle_evolve_memory({"target_stage": "charizard", "dry_run": True})
    assert out["ran"] is False and "no active memory store" in out["reason"]


def test_handler_charizard_routes_and_default_does_not(tmp_path, monkeypatch):
    h = _handler()
    # charizard routes to the consolidation handler
    monkeypatch.setattr(h, "_handle_evolve_consolidate", lambda p: {"routed": True})
    assert h._handle_evolve_memory({"target_stage": "charizard"}) == {"routed": True}

    # a non-charizard call NEVER routes to consolidation (regression guard on the
    # untouched charmander->charmeleon path)
    called = {"v": False}
    monkeypatch.setattr(h, "_handle_evolve_consolidate",
                        lambda p: called.__setitem__("v", True) or {})
    try:
        h._handle_evolve_memory({"target_stage": "charmeleon", "dry_run": True})
    except Exception:
        pass  # the markdown path may need Houdini; we only assert routing here
    assert called["v"] is False


# --------------------------------------------------------------------------
# Moneta backend — honest degradation (dry-run works, apply is UNKNOWN)
# --------------------------------------------------------------------------

class TestMonetaBackendDegradesHonestly:
    """The append/consolidate Moneta store supports the dry-run audit but not a
    selective apply — that lands under W3-HARDEN. Skips cleanly without Moneta."""

    def _moneta_store(self):
        from synapse.memory import moneta_runtime as mr
        if not mr.moneta_available():
            pytest.skip(f"Moneta not importable: {mr.import_error()}")
        from synapse.memory.embedding import HashEmbedder
        from synapse.memory.moneta_store import MonetaBackedStore
        handle = mr.make_ephemeral(embedding_dim=256)
        return MonetaBackedStore(handle, HashEmbedder(dim=256))

    def test_dry_run_audit_works_over_moneta(self):
        store = self._moneta_store()
        store.add(_mem("dup", created_at="2026-01-01T00:00:00Z"))
        store.add(_mem("dup", created_at="2026-01-02T00:00:00Z"))
        audit = plan_consolidation(store.all())
        assert len(audit.pruned_ids) == 1      # pure planner needs only all()

    def test_apply_over_moneta_is_unsupported(self):
        store = self._moneta_store()
        store.add(_mem("dup", created_at="2026-01-01T00:00:00Z"))
        store.add(_mem("dup", created_at="2026-01-02T00:00:00Z"))
        token = plan_consolidation(store.all()).approval_token
        with pytest.raises(ConsolidationUnsupported):
            apply_consolidation(store, approval_token=token)
