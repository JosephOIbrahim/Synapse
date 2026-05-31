"""FU-1 — Memory.id includes created_at on the defaulted path.

Before the __post_init__ reorder, _generate_id() ran while created_at was still
"" (defaulted afterward), so the id was time-independent and identical
content+type collided forever. After the reorder, a defaulted created_at
participates, so the same content logged at different times gets distinct ids.

This is proven deterministically by mocking the timestamp source (two distinct
defaulted timestamps -> two distinct ids). The test FAILS before the fix.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import models  # noqa: E402
from synapse.memory.models import Memory, MemoryType  # noqa: E402


def test_defaulted_created_at_participates_in_id(monkeypatch):
    # Two memories created at different (defaulted) times must get distinct ids.
    stamps = iter(["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"])
    monkeypatch.setattr(models.time, "strftime", lambda *a, **k: next(stamps))
    a = Memory(content="Executed: execute_python", memory_type=MemoryType.ACTION)
    b = Memory(content="Executed: execute_python", memory_type=MemoryType.ACTION)
    assert a.created_at != b.created_at
    assert a.id != b.id  # would be EQUAL before the reorder (created_at ignored)


def test_explicit_created_at_participates_in_id():
    a = Memory(content="x", memory_type=MemoryType.NOTE, created_at="2026-01-01T00:00:00Z")
    b = Memory(content="x", memory_type=MemoryType.NOTE, created_at="2026-01-02T00:00:00Z")
    assert a.id != b.id


def test_same_content_same_second_still_collides():
    # Documented residual: within the SAME second (same defaulted created_at),
    # identical content+type still shares an id. Full uniqueness (time_ns/uuid)
    # is the deferred entropy follow-up.
    a = Memory(content="dup", memory_type=MemoryType.NOTE, created_at="2026-01-01T00:00:00Z")
    b = Memory(content="dup", memory_type=MemoryType.NOTE, created_at="2026-01-01T00:00:00Z")
    assert a.id == b.id


def test_explicit_id_is_never_regenerated():
    m = Memory(id="my-explicit-id", content="x", memory_type=MemoryType.NOTE)
    assert m.id == "my-explicit-id"
