"""W3-KIND — typed schema per kind (acceptance CHECK: per-kind fields).

Pins the schema half of the mission:
  * the per-kind field table matches the spec — decision carries
    reasoning+alternatives, task carries status, reference carries ref_uri;
  * the typed fields are REAL, round-tripping attributes on Memory;
  * the addition is ADDITIVE — an old payload written before these fields
    existed still deserializes, and no base field is renamed or dropped;
  * kind_schema.typed_fields projects only THIS kind's declared fields.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import kind_schema as ks  # noqa: E402
from synapse.memory.models import Memory, MemoryType  # noqa: E402


# --------------------------------------------------------------------------
# Acceptance CHECK: per-kind fields match the spec table
# --------------------------------------------------------------------------

def test_decision_kind_carries_reasoning_and_alternatives():
    assert ks.KIND_FIELDS[MemoryType.DECISION] == ("reasoning", "alternatives")


def test_task_kind_carries_status():
    assert ks.KIND_FIELDS[MemoryType.TASK] == ("status",)


def test_reference_kind_carries_ref_uri():
    assert ks.KIND_FIELDS[MemoryType.REFERENCE] == ("ref_uri",)


def test_note_and_context_carry_base_only():
    assert ks.KIND_FIELDS[MemoryType.NOTE] == ()
    assert ks.KIND_FIELDS[MemoryType.CONTEXT] == ()


def test_registry_is_total_over_every_memory_type():
    # A kind filter over ANY MemoryType must be well-defined (never fall through
    # to a scan because the kind is unregistered).
    for mt in MemoryType:
        assert mt in ks.KIND_FIELDS, mt
        assert isinstance(ks.kind_fields(mt), tuple)


def test_spec_kinds_are_exactly_the_five():
    assert ks.SPEC_KINDS == (
        MemoryType.NOTE, MemoryType.CONTEXT, MemoryType.REFERENCE,
        MemoryType.TASK, MemoryType.DECISION,
    )


def test_schema_fields_is_base_plus_kind_specific():
    assert ks.schema_fields(MemoryType.DECISION) == (
        ks.BASE_FIELDS + ("reasoning", "alternatives")
    )
    assert ks.schema_fields(MemoryType.NOTE) == ks.BASE_FIELDS


# --------------------------------------------------------------------------
# The typed fields are real, round-tripping attributes on Memory
# --------------------------------------------------------------------------

def test_decision_typed_fields_round_trip_through_json():
    d = Memory(
        content="use karma xpu",
        memory_type=MemoryType.DECISION,
        reasoning="faster on the rtx 4090",
        alternatives=["mantra", "karma cpu"],
    )
    back = Memory.from_json(d.to_json())
    assert back.reasoning == "faster on the rtx 4090"
    assert back.alternatives == ["mantra", "karma cpu"]


def test_task_status_round_trips():
    t = Memory(content="bake the sim", memory_type=MemoryType.TASK, status="blocked")
    assert Memory.from_json(t.to_json()).status == "blocked"


def test_reference_ref_uri_round_trips():
    r = Memory(
        content="brand deck",
        memory_type=MemoryType.REFERENCE,
        ref_uri="file:///show/refs/brand.pdf",
    )
    assert Memory.from_json(r.to_json()).ref_uri == "file:///show/refs/brand.pdf"


def test_typed_fields_view_returns_only_this_kinds_fields():
    d = Memory(content="c", memory_type=MemoryType.DECISION,
               reasoning="why", alternatives=["a"])
    assert ks.typed_fields(d) == {"reasoning": "why", "alternatives": ["a"]}

    t = Memory(content="c", memory_type=MemoryType.TASK, status="started")
    assert ks.typed_fields(t) == {"status": "started"}

    n = Memory(content="c", memory_type=MemoryType.NOTE)
    assert ks.typed_fields(n) == {}


# --------------------------------------------------------------------------
# Additivity: old payloads still load; nothing renamed or dropped
# --------------------------------------------------------------------------

def test_old_payload_without_typed_fields_loads_with_defaults():
    # A payload written BEFORE W3-KIND existed (no typed keys at all).
    legacy = {
        "id": "mem_legacy",
        "created_at": "2026-01-01T00:00:00Z",
        "content": "legacy note",
        "memory_type": "note",
        "tier": "shot",
    }
    m = Memory.from_dict(legacy)
    assert m.reasoning == ""
    assert m.alternatives == []
    assert m.status == ""
    assert m.ref_uri == ""


def test_no_base_field_was_dropped_or_renamed():
    # Every field the pre-W3-KIND schema serialized must still be present.
    base_keys = {
        "id", "created_at", "updated_at", "content", "memory_type", "tier",
        "summary", "keywords", "tags", "links", "hip_file", "hip_version",
        "frame", "frame_range", "node_paths", "source", "agent_id",
        "confidence", "embedding", "is_consolidated", "consolidated_into",
    }
    d = Memory(content="c", memory_type=MemoryType.NOTE).to_dict()
    missing = base_keys - set(d)
    assert not missing, f"dropped/renamed base fields: {missing}"


def test_typed_fields_do_not_change_the_memory_id():
    # The id hashes content+created_at+type only; adding typed fields must not
    # churn ids (round-trip identity + no accidental collisions/splits).
    ts = "2026-02-02T02:02:02Z"
    plain = Memory(content="same", memory_type=MemoryType.DECISION, created_at=ts)
    typed = Memory(content="same", memory_type=MemoryType.DECISION, created_at=ts,
                   reasoning="r", alternatives=["a", "b"])
    assert plain.id == typed.id
