"""Typed per-kind memory schema (W3-KIND, Blueprint P3).

Recall routes on *type*, not on a free-text scan. This module is the single
declaration of which typed fields each memory *kind* carries beyond the base
fields every memory has. It is the schema half of W3-KIND; the routing half
lives in ``SynapseMemory.search(memory_types=)`` / ``SynapseMemory.recall(kinds=)``,
which resolve a kind filter through the store's ``by_type`` index (store.py)
instead of scanning the whole store.

Design invariants
-----------------
* **Additive.** The per-kind fields are OPTIONAL attributes on :class:`Memory`
  (all defaulted), so a memory that never sets them round-trips unchanged and
  no base field is renamed or dropped. This module adds a *view* over those
  fields; it stores nothing itself.
* **Pure-Python.** No ``hou`` / ``pxr`` imports -- safe on the ephemeral/CI
  path and importable anywhere ``models`` is.
* **Total over kinds.** The five kinds the W3-KIND spec enumerates as carrying
  a typed schema are note / context / reference / task / decision. Every other
  :class:`MemoryType` member is still registered (with an empty extra-set) so a
  kind filter over ANY type is well-defined and never falls through to a scan.

Spec table (source: mission W3-KIND anchor S4 Phase 2)::

    decision  -> reasoning + alternatives
    task      -> status
    reference -> ref_uri            (the external file / URL / asset)
    note      -> (base only)
    context   -> (base only)
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .models import Memory, MemoryType

# Fields every memory carries regardless of kind (the base prim).
BASE_FIELDS: Tuple[str, ...] = (
    "id", "created_at", "updated_at", "content", "memory_type", "tier",
    "summary", "keywords", "tags", "source",
)

# Per-kind DISTINCT typed fields (beyond BASE_FIELDS). This is the spec table.
# note/context carry only the base set. The remaining MemoryType members are
# registered with an empty extra-set so routing over any kind stays total.
KIND_FIELDS: Dict[MemoryType, Tuple[str, ...]] = {
    MemoryType.NOTE: (),
    MemoryType.CONTEXT: (),
    MemoryType.REFERENCE: ("ref_uri",),
    MemoryType.TASK: ("status",),
    MemoryType.DECISION: ("reasoning", "alternatives"),
    # Remaining members -- registered, no distinct typed fields (yet).
    MemoryType.ACTION: (),
    MemoryType.FEEDBACK: (),
    MemoryType.ERROR: (),
    MemoryType.SUMMARY: (),
}

# The five kinds the W3-KIND spec enumerates as carrying a typed schema.
SPEC_KINDS: Tuple[MemoryType, ...] = (
    MemoryType.NOTE,
    MemoryType.CONTEXT,
    MemoryType.REFERENCE,
    MemoryType.TASK,
    MemoryType.DECISION,
)


def kind_fields(memory_type: MemoryType) -> Tuple[str, ...]:
    """Distinct typed field names for a kind (beyond :data:`BASE_FIELDS`)."""
    return KIND_FIELDS.get(memory_type, ())


def schema_fields(memory_type: MemoryType) -> Tuple[str, ...]:
    """Full typed field set for a kind = base + kind-specific."""
    return BASE_FIELDS + kind_fields(memory_type)


def typed_fields(memory: Memory) -> Dict[str, Any]:
    """Project a memory's kind-specific typed fields into a dict.

    Only the fields THIS kind declares are returned, read off the typed
    attributes on :class:`Memory` -- so a decision yields
    ``{reasoning, alternatives}`` and a task yields ``{status}``. Recall/search
    use it to present the typed prim without re-parsing content text.
    """
    return {
        name: getattr(memory, name, None)
        for name in kind_fields(memory.memory_type)
    }


def resolve_kinds(raw) -> Tuple[List[MemoryType], List[str]]:
    """Split requested kinds into ``(valid MemoryType, invalid str)``.

    The negative-control helper. An unknown kind lands in ``invalid`` so the
    caller can fail loud (empty result + reported invalid kinds) instead of
    silently widening to a full-store scan. Accepts :class:`MemoryType` members
    or their ``.value`` strings, in any mix.
    """
    valid: List[MemoryType] = []
    invalid: List[str] = []
    for k in (raw or []):
        if isinstance(k, MemoryType):
            valid.append(k)
            continue
        try:
            valid.append(MemoryType(str(k)))
        except ValueError:
            invalid.append(str(k))
    return valid, invalid
