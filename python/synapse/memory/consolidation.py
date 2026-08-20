"""Memory consolidation — the charmeleon→charizard *store-consolidation* audit.

W3-EVOLVE. S6 Phase 4: "consolidation and pruning ... dry-run returns a prune
audit (what merges, what prunes, before/after counts) ... protected memories
are never pruned."

RETIRED 2026-08-20 (RETIREMENT agent, refactor/memory-v51-substrates): this
module used to also carry an ``apply_consolidation`` mutator gated by a manual
approval-token string — a human-in-the-loop "preview, copy the token, paste it
back to approve" step. THE LOOP v5.1 mandates a decay-driven memory lifecycle
with no interactive evolution stages, and that token gate (plus its sole
caller, ``server/handlers_memory.py::_handle_evolve_consolidate``, and the
``synapse_evolve_memory`` MCP tool that fronted it) has been removed. The
sanctioned mutator is ``_handle_sleep_pass`` / ``store.run_sleep_pass()`` (a
real consent gate via the execution bridge, not a copy-pasted string).

What survives here is the *read-only* half, which was never the interactive
part:

  1. **Dry-run mutates NOTHING.** :func:`plan_consolidation` is a pure function
     over a *list* of ``Memory`` objects (typically ``store.all()``). It never
     touches a store. The audit it returns carries the merge list, the prune
     list (ids), and before/after counts.
  2. **Protected memories are never pruned.** :func:`is_protected` mirrors
     ``MonetaBackedStore._is_protected`` (moneta_store.py:420) exactly — a
     DECISION, a SHOW-tier memory, or a ``source == "gate"`` memory is never
     absorbed and never deleted, even when it is an exact duplicate. A protected
     duplicate is *forced* to be the group's survivor.

Store-agnostic by construction: the plan is computed over whatever ``Sequence
[Memory]`` is handed in (typically ``store.all()``), so it works over any
backend's public surface without needing ``delete``/``update``. The dry-run
audit works over both the pre-migration JSONL ``MemoryStore`` and the Moneta
backend.

Name reconciliation: on the *scene-USD* axis, "charizard" == ``COMPOSED``
(shared/constants.py:300 — USD sublayer composition arcs). On the *memory-store*
axis this is the Phase-4 consolidation stage the spec (S6) names
"charmeleon-to-charizard evolution over the real store". Same Pokémon, two
distinct axes. This module is the store axis only; it never touches USD.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .models import Memory, MemoryTier, MemoryType

logger = logging.getLogger(__name__)


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
            "backup_path": self.backup_path,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Planner — pure, mutates nothing
# ---------------------------------------------------------------------------

def plan_consolidation(memories: Sequence[Memory]) -> ConsolidationAudit:
    """Compute the consolidation plan for ``memories`` WITHOUT mutating anything.

    Deterministic and order-independent: memories are sorted by
    ``(created_at, id)`` before grouping, so the plan is stable across repeated
    calls over the same corpus.
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
        backup_path=None,
        reason=reason,
    )


# NOTE: the mutating counterpart to this planner — `apply_consolidation`, gated
# by a manual approval-token string the caller had to copy from a prior
# dry-run — was retired 2026-08-20 along with the `synapse_evolve_memory` MCP
# tool that fronted it. It had no caller left once that tool and its handler
# (`_handle_evolve_consolidate`) were removed, so it was deleted outright
# rather than left reachable-but-ungated. The sanctioned mutator is the
# decay-driven `_handle_sleep_pass` / `store.run_sleep_pass()` path, which has
# its own real consent gate via the execution bridge (see server/handlers_
# memory.py). `plan_consolidation` above remains: it is pure and read-only,
# and was never the interactive half of this module.
