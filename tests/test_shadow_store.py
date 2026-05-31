"""Mile 5 — shadow dual-write + parity diff harness.

Pins: writes hit both stores, reads come from the primary, the parity report
reflects real agreement, and a failing shadow can NEVER break the caller or
the primary. Because the Moneta adapter's search is parity-by-construction
(Mile 4), the report should read 1.0 over a representative query set -- the
evidence that justifies cutover (AP5 / FC3).
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import moneta_runtime as mr  # noqa: E402
from synapse.memory.embedding import HashEmbedder  # noqa: E402
from synapse.memory.models import Memory, MemoryQuery, MemoryType  # noqa: E402
from synapse.memory.store import MemoryStore  # noqa: E402
from synapse.memory.shadow_store import ShadowMemoryStore, ParityReport  # noqa: E402

pytestmark = pytest.mark.skipif(
    not mr.moneta_available(),
    reason=f"Moneta not importable (set $MONETA_SRC). Last error: {mr.import_error()}",
)

DIM = 256


def _corpus():
    return [
        Memory(content="render the karma beauty pass tonight",
               memory_type=MemoryType.ACTION, tags=["render", "karma"],
               keywords=["karma"], created_at="2026-01-01T00:00:00Z"),
        Memory(content="Decision: use assemble_chain to wire Solaris",
               memory_type=MemoryType.DECISION, tags=["ai_decision"],
               keywords=["assemble_chain"], created_at="2026-01-02T00:00:00Z"),
        Memory(content="material binding failed on hero asset",
               memory_type=MemoryType.ERROR, tags=["error"],
               keywords=["material"], created_at="2026-01-03T00:00:00Z"),
        Memory(content="karma denoiser note for the render",
               memory_type=MemoryType.NOTE, tags=["render"],
               keywords=["denoiser"], created_at="2026-01-04T00:00:00Z"),
    ]


def _shadow(tmp_path):
    from synapse.memory.moneta_store import MonetaBackedStore
    primary = MemoryStore(tmp_path / ".synapse")
    shadow = MonetaBackedStore(mr.make_ephemeral(embedding_dim=DIM), HashEmbedder(dim=DIM))
    return ShadowMemoryStore(primary, shadow)


def test_dual_write_and_reads_serve_primary(tmp_path):
    s = _shadow(tmp_path)
    for m in _corpus():
        s.add(m)
    assert s.count() == 4
    assert s.primary.count() == 4
    assert s.shadow.count() == 4
    # reads come from primary
    assert [m.id for m in s.get_recent(2)] == [m.id for m in s.primary.get_recent(2)]


def test_parity_report_is_perfect_over_query_set(tmp_path):
    s = _shadow(tmp_path)
    for m in _corpus():
        s.add(m)
    queries = [
        MemoryQuery(text="karma"),
        MemoryQuery(text="render", limit=2),
        MemoryQuery(tags=["render"]),
        MemoryQuery(memory_types=[MemoryType.DECISION]),
        MemoryQuery(text="material", tags=["error"]),
    ]
    s.count()
    s.get_recent(10)
    s.get_by_type(MemoryType.DECISION)
    for q in queries:
        s.search(q)

    rep = s.report
    assert rep.comparisons >= len(queries) + 3
    assert rep.parity_ratio == 1.0, rep.mismatches
    assert rep.write_errors == []


def test_shadow_write_failure_is_isolated(tmp_path):
    # A shadow that raises on every write must not disturb the primary path.
    class Boom:
        def add(self, memory):
            raise RuntimeError("shadow exploded")
        def save(self):
            raise RuntimeError("shadow exploded")

    primary = MemoryStore(tmp_path / ".synapse")
    s = ShadowMemoryStore(primary, Boom())
    rid = s.add(_corpus()[0])  # must succeed despite shadow blowing up
    assert rid is not None
    assert s.primary.count() == 1
    assert len(s.report.write_errors) >= 1


def test_shadow_read_failure_is_isolated(tmp_path):
    class HalfBroken:
        def add(self, memory):
            return memory.id
        def count(self):
            raise RuntimeError("shadow count broke")

    primary = MemoryStore(tmp_path / ".synapse")
    s = ShadowMemoryStore(primary, HalfBroken())
    s.add(_corpus()[0])
    assert s.count() == 1  # primary answer still returned
    assert len(s.report.write_errors) >= 1


def test_parity_report_records_real_mismatch():
    rep = ParityReport()
    rep.record("count", 5, 5)
    rep.record("count", 5, 4)
    assert rep.comparisons == 2
    assert rep.matches == 1
    assert rep.parity_ratio == 0.5
    assert rep.mismatches == [("count", 5, 4)]
