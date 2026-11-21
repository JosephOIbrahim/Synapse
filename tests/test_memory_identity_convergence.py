"""R-033 -- the Moneta primary must not accept duplicate memory identities.

A ``Memory`` id is content-addressed (``models.Memory._generate_id``: content +
created_at + memory_type, created_at at whole-second resolution), so the same
content stored in the same second collides by construction. ``add()`` used to
deposit a second row under that id without a word. Both of the primary's
strict consumers then reject the whole store:

  * ``memory_lifecycle._records()`` -- ``len(ids) != len(set(ids))`` (the
    save-a-scene transition is broken until the rows are converged);
  * ``MonetaBackedStore.add_durable_if_absent()`` -- ``len(matches) != 1``.

The repair has two halves, both in-product -- no CLI, no live-host refusal:

  * ``add()`` on an existing identity CONVERGES on an identical payload and
    raises the typed :class:`DuplicateMemoryIdentityError` on a conflicting
    one (Moneta is append/consolidate and cannot express an update, so keeping
    either copy silently would lose the other);
  * ``duplicate_identities()`` / ``repair_duplicate_identities()`` detect and
    converge pre-existing duplicate rows on the LIVE engine under the store
    lock, and ``memory_lifecycle._records`` heals through them.

Fakes only. Nothing here imports ``moneta``: the handle is a double, so these
tests run on the stock interpreter the way the store's other fake-handle
suites do (``test_prune_audit_on_failure.py`` is the shape).
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory.embedding import HashEmbedder  # noqa: E402
from synapse.memory.models import Memory, MemoryType  # noqa: E402
from synapse.memory.moneta_store import (  # noqa: E402
    DuplicateMemoryIdentityError,
    MonetaBackedStore,
)

STAMP = "2026-11-20T00:00:00Z"


class _FakeRow:
    """One ECS row: the attributes the adapter reads and removes."""

    def __init__(self, entity_id, payload):
        self.entity_id = entity_id
        self.payload = payload


class _FakeECS:
    """Rows keyed by entity id, deposited and removable like Moneta's ECS."""

    def __init__(self):
        self._rows = {}
        self._next = 0

    @property
    def n(self):
        return len(self._rows)

    def iter_rows(self):
        return list(self._rows.values())

    def deposit(self, payload, embedding, protected_floor=0.0):
        self._next += 1
        entity_id = f"eid-{self._next:03d}"
        self._rows[entity_id] = _FakeRow(entity_id, payload)

    def remove(self, entity_id):
        del self._rows[entity_id]


class _Durability:
    """Counts snapshots; the store only needs ``snapshot_ecs``."""

    def __init__(self):
        self.snapshots = 0

    def snapshot_ecs(self, ecs):
        self.snapshots += 1


class _FakeHandle:
    def __init__(self, rows=(), *, durable=True):
        self.ecs = _FakeECS()
        for row in rows:
            self.ecs._rows[row.entity_id] = row
        self.durability = _Durability() if durable else None

    def deposit(self, payload, embedding, protected_floor=0.0):
        self.ecs.deposit(payload, embedding, protected_floor=protected_floor)


def _store(rows=(), *, durable=True):
    handle = _FakeHandle(rows, durable=durable)
    return MonetaBackedStore(handle, HashEmbedder(dim=8)), handle


def _row(entity_id, memory):
    return _FakeRow(entity_id, memory.to_json())


def _duplicated_store(*, durable=True):
    """One id on two rows (rich + stripped) plus an untouched singleton."""
    rich = Memory(id="mem_dup", content="Decision: keep the warm rim light",
                  memory_type=MemoryType.DECISION, created_at=STAMP,
                  tags=["decision", "lighting"], source="user")
    stripped = Memory(id="mem_dup", content="Decision: keep the warm rim light",
                      memory_type=MemoryType.DECISION, created_at=STAMP,
                      tags=[], source="auto")
    single = Memory(id="mem_single", content="a note with one row",
                    memory_type=MemoryType.NOTE, created_at=STAMP)
    store, handle = _store(
        [_row("eid-rich", rich), _row("eid-stripped", stripped),
         _row("eid-single", single)],
        durable=durable,
    )
    return store, handle, rich, stripped, single


# ---------------------------------------------------------------------------
# add(): converge on an identical identity, refuse a conflicting one
# ---------------------------------------------------------------------------

def test_add_same_identity_twice_converges_to_one_record():
    """The literal predicate: add the same identity twice, one record remains."""
    store, handle = _store()
    first = Memory(content="same content, same second",
                   memory_type=MemoryType.DECISION, created_at=STAMP)
    second = Memory(content="same content, same second",
                    memory_type=MemoryType.DECISION, created_at=STAMP)
    assert first.id == second.id, "test precondition: the ids collide"

    assert store.add(first) == first.id
    assert store.add(second) == first.id

    assert store.count() == 1, "an identical identity must converge, not duplicate"
    assert len(handle.ecs.iter_rows()) == 1
    assert store.get(first.id).to_json() == first.to_json(), (
        "the surviving record must be the caller's record"
    )


def test_add_same_identity_with_different_payload_is_a_typed_refusal():
    """A same-id, different-payload write is an UPDATE Moneta cannot express."""
    store, handle = _store()
    original = Memory(id="mem_collision", content="the original decision",
                      memory_type=MemoryType.DECISION, created_at=STAMP)
    conflicting = Memory(id="mem_collision", content="a different decision",
                         memory_type=MemoryType.DECISION, created_at=STAMP)

    store.add(original)
    with pytest.raises(DuplicateMemoryIdentityError) as caught:
        store.add(conflicting)

    assert caught.value.memory_id == "mem_collision"
    assert caught.value.existing_payloads == [original.to_json()]
    assert isinstance(caught.value, ValueError), (
        "existing ValueError handlers must keep working"
    )
    assert store.count() == 1, "a refused write must not deposit a row"
    assert store.get("mem_collision").content == "the original decision", (
        "a refusal must leave the stored record untouched"
    )


def test_add_on_an_already_duplicated_identity_is_a_typed_refusal():
    """add() cannot paper over an invariant the store already violates."""
    rich = Memory(id="mem_dup", content="Decision: keep the warm rim light",
                  memory_type=MemoryType.DECISION, created_at=STAMP,
                  tags=["decision"], source="user")
    store, handle = _store([_row("eid-1", rich), _row("eid-2", rich)])

    with pytest.raises(DuplicateMemoryIdentityError):
        store.add(Memory(id="mem_dup", content="Decision: keep the warm rim light",
                         memory_type=MemoryType.DECISION, created_at=STAMP,
                         tags=["decision"], source="user"))

    assert store.count() == 2, "the pre-existing rows are left for the repair"


def test_add_never_duplicates_a_readable_identity_around_a_corrupt_row():
    """One unreadable row is skipped, never treated as the whole engine."""
    store, handle = _store([_FakeRow("eid-corrupt", "{not json")])
    memory = Memory(id="mem_new", content="a new note", created_at=STAMP)

    store.add(memory)

    assert store.count() == 2
    assert store.get(memory.id).to_json() == memory.to_json()


# ---------------------------------------------------------------------------
# in-product detection
# ---------------------------------------------------------------------------

def test_duplicate_identities_reports_live_duplicates_and_keeps_the_rich_copy():
    store, handle, rich, stripped, single = _duplicated_store()

    report = store.duplicate_identities()

    assert [entry["memory_id"] for entry in report] == ["mem_dup"]
    assert report[0]["rows"] == 2
    assert report[0]["distinct_payloads"] == 2
    assert report[0]["keep_entity_id"] == "eid-rich", (
        "the survivor must be chosen by primary_repair's richness rule"
    )
    assert report[0]["drop_entity_ids"] == ["eid-stripped"]
    assert store.count() == 3, "detection never mutates"


def test_duplicate_identities_is_empty_on_a_clean_store():
    store, handle = _store([_row("eid-1", Memory(id="mem_one", content="one",
                                                 created_at=STAMP))])
    assert store.duplicate_identities() == []


# ---------------------------------------------------------------------------
# in-product remediation
# ---------------------------------------------------------------------------

def test_repair_duplicate_identities_is_a_dry_run_by_default():
    store, handle, rich, stripped, single = _duplicated_store()

    report = store.repair_duplicate_identities()

    assert report["applied"] is False
    assert report["duplicate_ids"] == ["mem_dup"]
    assert report["rows_to_drop"] == 1
    assert report["remaining_duplicate_ids"] == ["mem_dup"], (
        "a dry run must not imply the duplicates are gone"
    )
    assert handle.ecs.n == 3, "a dry run must not touch the engine"
    assert store.get("mem_dup") is not None


def test_repair_duplicate_identities_converges_in_product():
    store, handle, rich, stripped, single = _duplicated_store()

    report = store.repair_duplicate_identities(apply=True)

    assert report["applied"] is True
    assert report["kept"] == {"mem_dup": "eid-rich"}
    assert [d["entity_id"] for d in report["dropped"]] == ["eid-stripped"]
    assert report["dropped"][0]["payload"] == stripped.to_json(), (
        "the dropped payload must be captured -- a repair that deletes "
        "silently is the next incident"
    )
    assert handle.ecs.n == 2
    assert store.duplicate_identities() == []
    assert report["remaining_duplicate_ids"] == []
    assert store.get("mem_dup").tags == ["decision", "lighting"]
    assert report["persistence"] == "snapshot"
    assert handle.durability.snapshots >= 1, "the converged state must be persisted"


def test_repair_reports_honestly_when_the_handle_cannot_persist():
    store, handle, rich, stripped, single = _duplicated_store(durable=False)

    report = store.repair_duplicate_identities(apply=True)

    assert report["applied"] is True
    assert report["persistence"] == "not_durable", (
        "an ephemeral repair is real in memory and cannot be persisted; the "
        "report must say so rather than imply a snapshot"
    )
    assert handle.ecs.n == 2


def test_repair_removes_the_dropped_entity_from_the_vector_index_first():
    store, handle, rich, stripped, single = _duplicated_store()
    deleted = []
    handle.vector_index = SimpleNamespace(delete=deleted.append)

    report = store.repair_duplicate_identities(apply=True)

    assert report["applied"] is True
    assert deleted == ["eid-stripped"], (
        "a vector entry left behind would let recall surface a removed row"
    )


def test_repair_refuses_an_id_whose_vector_entry_cannot_be_removed():
    store, handle, rich, stripped, single = _duplicated_store()

    class _BrokenIndex:
        def delete(self, entity_id):
            raise RuntimeError("vector index offline")

    handle.vector_index = _BrokenIndex()

    report = store.repair_duplicate_identities(apply=True)

    assert report["applied"] is False
    assert report["refusals"] and "vector index delete failed" in report["refusals"][0]
    assert report["remaining_duplicate_ids"] == ["mem_dup"], (
        "a refused id is still a live duplicate and the report must say so"
    )
    assert handle.ecs.n == 3, "a refused id keeps every row"


def test_repair_of_a_clean_store_is_a_no_op():
    store, handle = _store([_row("eid-1", Memory(id="mem_one", content="one",
                                                 created_at=STAMP))])
    report = store.repair_duplicate_identities(apply=True)
    assert report["applied"] is False
    assert report["duplicate_ids"] == []
    assert handle.ecs.n == 1


# ---------------------------------------------------------------------------
# the product path that was broken: memory_lifecycle._records
# ---------------------------------------------------------------------------

def test_lifecycle_save_transition_heals_duplicates_in_product():
    """``_records`` raised "Source memory has duplicate identities" forever.

    The offline CLI cannot help a live host; the store's own repair can. The
    transition must return the healed corpus instead of failing the save.
    """
    from synapse.host import memory_lifecycle

    store, handle, rich, stripped, single = _duplicated_store()

    records = memory_lifecycle._records(SimpleNamespace(store=store))

    assert sorted(m.id for m in records) == ["mem_dup", "mem_single"]
    assert store.duplicate_identities() == []
    assert handle.ecs.n == 2
    assert store.get("mem_dup").tags == ["decision", "lighting"]
    ids = [m.id for m in records]
    assert len(ids) == len(set(ids)), "the strict invariant the transition needs"
