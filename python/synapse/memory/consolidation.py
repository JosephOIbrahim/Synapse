"""Memory consolidation — the charmeleon→charizard *store-consolidation* stage.

W3-EVOLVE. S6 Phase 4: "consolidation and pruning ... dry-run returns a prune
audit (what merges, what prunes, before/after counts); apply only when approved;
protected memories are never pruned."

Design — three hard guarantees, all structural (not conventional):

  1. **Dry-run mutates NOTHING.** :func:`plan_consolidation` is a pure function
     over a *list* of ``Memory`` objects (typically ``store.all()``). It never
     touches a store. The audit it returns carries the merge list, the prune
     list (ids), before/after counts, and an ``approval_token`` bound to *this*
     exact plan.
  2. **Apply requires an explicit, plan-bound approval token.**
     :func:`apply_consolidation` refuses loudly (``ConsolidationNotApproved``)
     when the token is absent OR does not match the freshly-recomputed plan of
     the current store — you can only approve the plan you previewed, over a
     store that has not changed since. This is preview-then-approve by
     construction; there is no auto-apply path.
  3. **Protected memories are never pruned.** :func:`is_protected` mirrors
     ``MonetaBackedStore._is_protected`` (moneta_store.py:420) exactly — a
     DECISION, a SHOW-tier memory, or a ``source == "gate"`` memory is never
     absorbed and never deleted, even when it is an exact duplicate. A protected
     duplicate is *forced* to be the group's survivor. A defence-in-depth check
     in apply aborts if a plan would ever prune a protected id.

Store-agnostic by construction: it drives the abstract ``MemoryStore`` public
surface (``all`` / ``get`` / ``update`` / ``delete`` / ``count`` / ``save``), so
it runs over the pre-migration JSONL ``MemoryStore`` (which the mission note
names as the machinery-proof surface). The append/consolidate Moneta backend
does not support selective ``delete``/``update``; apply over it raises
``ConsolidationUnsupported`` — the real Moneta corpus pass lands under W3-HARDEN
(per the mission note). The dry-run audit works over *both* backends.

Merge is provably lossless. Grouping is exact-normalized-content-per-type, so a
pruned duplicate's *content* is identical to its survivor's; before any delete,
the survivor absorbs the union of every member's tags / keywords / links /
node_paths and fills empty scalar fields from members; and the full pre-image
(``to_json``) of every pruned memory is captured in the audit AND written to a
backup file before mutation. Nothing merged is lost.

Name reconciliation: on the *scene-USD* axis, "charizard" == ``COMPOSED``
(shared/constants.py:300 — USD sublayer composition arcs). On the *memory-store*
axis this is the Phase-4 consolidation stage the spec (S6) names
"charmeleon-to-charizard evolution over the real store". Same Pokémon, two
distinct axes. This module is the store axis only; it never touches USD.

Native ``is_consolidated`` field: this module hard-prunes exact duplicates (their
content survives verbatim in the survivor), so it does not leave ``consolidated``
ghosts. The ``Memory.is_consolidated`` / ``consolidated_into`` hook remains free
for a future soft-merge mode (near-duplicate summarize-into-one), flagged as a
spawn.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from .models import Memory, MemoryTier, MemoryType

logger = logging.getLogger(__name__)


class ConsolidationNotApproved(RuntimeError):
    """apply_consolidation was called without a valid, plan-bound approval token."""


class ConsolidationUnsupported(RuntimeError):
    """The active backend cannot apply a selective consolidation (no delete)."""


# ---------------------------------------------------------------------------
# Protection — structural, mirrors MonetaBackedStore._is_protected
# ---------------------------------------------------------------------------

def is_protected(memory: Memory) -> bool:
    """A memory that consolidation must never absorb or prune.

    Identical predicate to ``MonetaBackedStore._is_protected`` (moneta_store.py:420)
    and to the deprecated evolver's "never prunes: decisions, unresolved blockers,
    asset references" rule: a DECISION, a SHOW-tier convention, or a
    human-gate-sourced memory is pinned.
    """
    return (
        memory.memory_type == MemoryType.DECISION
        or memory.tier == MemoryTier.SHOW
        or memory.source == "gate"
    )


def _norm(text: str) -> str:
    """Whitespace-collapsed, case-folded content — the duplicate identity."""
    return " ".join((text or "").split()).casefold()


def _merge_key(m: Memory):
    # Same type + same normalized content == a duplicate. Type keeps a DECISION
    # and a NOTE with coincidentally-equal text in separate groups (never merges
    # across a protection boundary silently).
    return (m.memory_type.value, _norm(m.content))


# ---------------------------------------------------------------------------
# Audit dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MergeGroup:
    """One duplicate-cluster folded into a single survivor.

    ``merged_ids`` are the ids that were (or would be) absorbed into
    ``survivor_id`` and then pruned — the merge list and the prune list are two
    views of the same event.
    """

    survivor_id: str
    merged_ids: List[str]
    key: str  # human-readable dup key (content head), for the reply/log
    preserved_tags: List[str]
    preserved_keywords: List[str]

    def to_dict(self) -> Dict:
        return {
            "survivor_id": self.survivor_id,
            "merged_ids": list(self.merged_ids),
            "key": self.key,
            "preserved_tags": list(self.preserved_tags),
            "preserved_keywords": list(self.preserved_keywords),
        }


@dataclass(frozen=True)
class ConsolidationAudit:
    """The full prune audit — what merges, what prunes, before/after counts."""

    merges: List[MergeGroup] = field(default_factory=list)
    pruned_ids: List[str] = field(default_factory=list)
    # Forensic pre-images of everything pruned (kept off the wire; in the backup).
    pruned_payloads: Dict[str, str] = field(default_factory=dict)
    protected_ids: List[str] = field(default_factory=list)
    count_before: int = 0
    count_after: int = 0
    dry_run: bool = True
    applied: bool = False
    approval_token: str = ""
    backup_path: Optional[str] = None
    reason: str = ""

    def to_dict(self) -> Dict:
        """JSON-safe reply shape for the MCP handler (heavy payloads excluded)."""
        return {
            "merges": [g.to_dict() for g in self.merges],
            "pruned_ids": list(self.pruned_ids),
            "protected_ids": list(self.protected_ids),
            "count_before": self.count_before,
            "count_after": self.count_after,
            "merged_count": len(self.pruned_ids),
            "dry_run": self.dry_run,
            "applied": self.applied,
            "approval_token": self.approval_token,
            "backup_path": self.backup_path,
            "reason": self.reason,
        }


def _plan_digest(merges: Sequence[MergeGroup]) -> str:
    """Order-independent 16-hex digest binding an approval to a specific plan."""
    payload = json.dumps(
        [[g.survivor_id, sorted(g.merged_ids)]
         for g in sorted(merges, key=lambda g: g.survivor_id)],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Planner — pure, mutates nothing
# ---------------------------------------------------------------------------

def plan_consolidation(memories: Sequence[Memory]) -> ConsolidationAudit:
    """Compute the consolidation plan for ``memories`` WITHOUT mutating anything.

    Deterministic and order-independent: memories are sorted by
    ``(created_at, id)`` before grouping, so the plan (and its ``approval_token``)
    is stable across repeated calls over the same corpus.
    """
    ordered = sorted(memories, key=lambda m: (m.created_at, m.id))

    groups: Dict[object, List[Memory]] = {}
    for m in ordered:
        groups.setdefault(_merge_key(m), []).append(m)

    merges: List[MergeGroup] = []
    pruned_ids: List[str] = []
    pruned_payloads: Dict[str, str] = {}
    protected_ids: List[str] = []

    for key, group in groups.items():
        if len(group) < 2:
            continue  # nothing to consolidate

        protected = [m for m in group if is_protected(m)]
        unprotected = [m for m in group if not is_protected(m)]

        if protected:
            # A protected duplicate is forced to survive — it becomes the
            # survivor; every OTHER protected duplicate also survives untouched
            # (protected is never absorbed). Only unprotected copies are folded in.
            survivor = protected[0]
            protected_ids.extend(m.id for m in protected)
            absorbed = unprotected
        else:
            survivor = group[0]
            absorbed = group[1:]

        if not absorbed:
            continue  # e.g. an all-protected cluster: recorded, nothing pruned

        preserved_tags = list(survivor.tags)
        preserved_keywords = list(survivor.keywords)
        for m in absorbed:
            for t in m.tags:
                if t not in preserved_tags:
                    preserved_tags.append(t)
            for k in m.keywords:
                if k not in preserved_keywords:
                    preserved_keywords.append(k)
            pruned_ids.append(m.id)
            pruned_payloads[m.id] = m.to_json()

        merges.append(MergeGroup(
            survivor_id=survivor.id,
            merged_ids=[m.id for m in absorbed],
            key=(key[1][:60] if isinstance(key, tuple) else str(key)),
            preserved_tags=preserved_tags,
            preserved_keywords=preserved_keywords,
        ))

    count_before = len(ordered)
    token = _plan_digest(merges)
    reason = (
        f"{len(pruned_ids)} duplicate(s) fold into {len(merges)} survivor(s); "
        f"{len(set(protected_ids))} protected memory(ies) preserved"
        if merges else "no duplicates found; nothing to consolidate"
    )
    return ConsolidationAudit(
        merges=merges,
        pruned_ids=pruned_ids,
        pruned_payloads=pruned_payloads,
        protected_ids=sorted(set(protected_ids)),
        count_before=count_before,
        count_after=count_before - len(pruned_ids),
        dry_run=True,
        applied=False,
        approval_token=token,
        backup_path=None,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Apply — approval-gated, backup-first, protected-safe
# ---------------------------------------------------------------------------

def _union_into(survivor: Memory, member: Memory) -> None:
    """Fold ``member``'s information into ``survivor`` — the lossless merge.

    Content is already identical (dedup key), so this preserves the metadata that
    can differ across identical-content copies: list fields are unioned; empty
    scalar fields are filled from the member; confidence takes the max.
    """
    for t in member.tags:
        if t not in survivor.tags:
            survivor.tags.append(t)
    for k in member.keywords:
        if k not in survivor.keywords:
            survivor.keywords.append(k)
    for np in member.node_paths:
        if np not in survivor.node_paths:
            survivor.node_paths.append(np)
    existing = {(l.target_id, l.link_type.value) for l in survivor.links}
    for l in member.links:
        sig = (l.target_id, l.link_type.value)
        if sig not in existing:
            survivor.links.append(l)
            existing.add(sig)
    survivor.confidence = max(survivor.confidence, member.confidence)
    if not survivor.summary and member.summary:
        survivor.summary = member.summary
    if not survivor.hip_file and member.hip_file:
        survivor.hip_file = member.hip_file
    if not survivor.agent_id and member.agent_id:
        survivor.agent_id = member.agent_id
    if survivor.frame is None and member.frame is not None:
        survivor.frame = member.frame
    if survivor.frame_range is None and member.frame_range is not None:
        survivor.frame_range = member.frame_range


def _backup(memories: Sequence[Memory], store, backup_dir: Optional[str],
            clock: Optional[Callable[[], str]]) -> str:
    """Snapshot every current memory to a JSONL backup BEFORE any mutation.

    Written to a dedicated ``consolidation_backups/`` subdir so it can never be
    mistaken for the store's own ``memory.jsonl``. The full pre-mutation corpus
    is recoverable from this file even for hard-pruned memories.
    """
    stamp = (clock or (lambda: time.strftime("%Y%m%d-%H%M%S", time.gmtime())))()
    base = backup_dir or getattr(store, "storage_dir", None) \
        or getattr(store, "_storage_dir", None) or "."
    d = Path(base) / "consolidation_backups"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"consolidation-backup-{stamp}.jsonl"
    # Never clobber a same-second backup: disambiguate by count.
    n = 0
    while path.exists():
        n += 1
        path = d / f"consolidation-backup-{stamp}-{n}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for m in memories:
            fh.write(m.to_json() + "\n")
    return str(path)


def apply_consolidation(store, *, approval_token: Optional[str],
                        backup_dir: Optional[str] = None,
                        _clock: Optional[Callable[[], str]] = None) -> ConsolidationAudit:
    """Apply the consolidation plan to ``store`` — only with a valid approval token.

    Order of gates is deliberate: the approval refusal fires FIRST, on every
    backend, so there is no backend on which an unapproved apply can mutate.
    """
    memories = store.all()
    plan = plan_consolidation(memories)

    # (1) Structural approval gate — preview-then-approve, no auto-apply path.
    if not approval_token:
        raise ConsolidationNotApproved(
            "consolidation apply REFUSED: no approval_token. Run a dry-run first "
            "and pass its approval_token back to approve THIS plan."
        )
    if approval_token != plan.approval_token:
        raise ConsolidationNotApproved(
            "consolidation apply REFUSED: approval_token does not match the current "
            f"plan (got {approval_token!r}, current plan is {plan.approval_token!r}). "
            "The store changed since preview, or the token is wrong — re-preview."
        )

    # (2) Backend capability — the Moneta store is append/consolidate: its
    #     delete()/update() raise. Selective apply over it is deferred to
    #     W3-HARDEN (mission note). Detect it the same way sleep_pass does.
    if hasattr(store, "run_sleep_pass"):
        raise ConsolidationUnsupported(
            "consolidation apply UNSUPPORTED on the append/consolidate Moneta "
            "backend (no selective delete). Dry-run audit is available; the real "
            "Moneta corpus pass lands under W3-HARDEN. Use synapse_sleep_pass for "
            "Moneta decay."
        )

    # (3) Defence in depth — a plan must never prune a protected memory.
    protected_now = {m.id for m in memories if is_protected(m)}
    unsafe = protected_now & set(plan.pruned_ids)
    if unsafe:
        raise ConsolidationNotApproved(
            f"consolidation apply ABORTED: plan would prune protected memories "
            f"{sorted(unsafe)} — refusing."
        )

    # (4) Backup BEFORE any mutation.
    backup_path = _backup(memories, store, backup_dir, _clock)

    # (5) Apply: union survivors, then hard-prune the absorbed duplicates.
    by_id = {m.id: m for m in memories}
    for g in plan.merges:
        survivor = by_id.get(g.survivor_id)
        if survivor is None:
            continue
        for mid in g.merged_ids:
            member = by_id.get(mid)
            if member is not None:
                _union_into(survivor, member)
        store.update(survivor)
    for mid in plan.pruned_ids:
        store.delete(mid)
    save = getattr(store, "save", None)
    if callable(save):
        save()

    count_after = store.count()
    logger.warning(
        "consolidation applied: pruned=%d survivors=%d before=%d after=%d backup=%s",
        len(plan.pruned_ids), len(plan.merges), plan.count_before, count_after,
        backup_path,
    )
    return ConsolidationAudit(
        merges=plan.merges,
        pruned_ids=plan.pruned_ids,
        pruned_payloads=plan.pruned_payloads,
        protected_ids=plan.protected_ids,
        count_before=plan.count_before,
        count_after=count_after,
        dry_run=False,
        applied=True,
        approval_token=plan.approval_token,
        backup_path=backup_path,
        reason=f"consolidated {len(plan.pruned_ids)} duplicate(s) into "
               f"{len(plan.merges)} survivor(s); {len(plan.protected_ids)} "
               f"protected preserved",
    )
