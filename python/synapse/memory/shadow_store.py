"""ShadowMemoryStore — dual-write + parity diff harness (Mile 5).

The safe path to cutover. A ``ShadowMemoryStore`` wraps a **primary** store
(the authoritative JSONL ``MemoryStore``) and a **shadow** store (the
``MonetaBackedStore``):

  * Writes go to BOTH. Shadow write failures are isolated and recorded -- they
    can never break the caller or the primary.
  * Reads are served from the PRIMARY, so production behavior is byte-for-byte
    unchanged during the shadow period.
  * Each read is also run against the shadow and diffed into a
    :class:`ParityReport`. Once parity holds over real traffic (AP5 / FC3),
    the cutover (read from shadow) is justified by evidence, not hope.

Comparison can be turned off (``compare_reads=False``) to dual-write with no
read overhead.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from .models import Memory, MemoryQuery, MemorySearchResult, MemoryType

logger = logging.getLogger(__name__)


@dataclass
class ParityReport:
    """Accumulates primary-vs-shadow agreement across reads."""

    comparisons: int = 0
    matches: int = 0
    mismatches: List[Tuple[str, Any, Any]] = field(default_factory=list)
    write_errors: List[str] = field(default_factory=list)

    def record(self, method: str, primary: Any, shadow: Any) -> None:
        self.comparisons += 1
        if primary == shadow:
            self.matches += 1
        else:
            self.mismatches.append((method, primary, shadow))

    def record_write_error(self, exc: BaseException) -> None:
        self.write_errors.append(f"{type(exc).__name__}: {exc}")

    @property
    def parity_ratio(self) -> float:
        return self.matches / self.comparisons if self.comparisons else 1.0

    def summary(self) -> dict:
        return {
            "comparisons": self.comparisons,
            "matches": self.matches,
            "parity_ratio": self.parity_ratio,
            "mismatch_count": len(self.mismatches),
            "write_errors": len(self.write_errors),
        }


def _ids(memories) -> List[str]:
    return [m.id for m in memories]


def _ranking(results) -> List[Tuple[str, float]]:
    return [(r.memory.id, round(r.score, 9)) for r in results]


class ShadowMemoryStore:
    """Primary-authoritative store that mirrors writes to a shadow and diffs reads."""

    def __init__(self, primary, shadow, *, report: Optional[ParityReport] = None,
                 compare_reads: bool = True):
        self.primary = primary
        self.shadow = shadow
        self.report = report or ParityReport()
        self.compare_reads = compare_reads

    # -- write (dual; shadow isolated) --------------------------------------

    def add(self, memory: Memory) -> str:
        result = self.primary.add(memory)
        self._shadow_write(lambda: self.shadow.add(memory))
        return result

    def _shadow_write(self, op) -> None:
        try:
            op()
        except Exception as exc:  # never let the shadow break the caller
            self.report.record_write_error(exc)
            logger.warning("shadow write failed (isolated): %s", exc)

    # -- read (serve primary; diff shadow) ----------------------------------

    def count(self) -> int:
        p = self.primary.count()
        if self.compare_reads:
            self._compare("count", p, lambda: self.shadow.count())
        return p

    def get_recent(self, limit: int = 10) -> List[Memory]:
        p = self.primary.get_recent(limit)
        if self.compare_reads:
            self._compare("get_recent", _ids(p), lambda: _ids(self.shadow.get_recent(limit)))
        return p

    def get_by_type(self, memory_type: MemoryType) -> List[Memory]:
        p = self.primary.get_by_type(memory_type)
        if self.compare_reads:
            self._compare("get_by_type", sorted(_ids(p)),
                          lambda: sorted(_ids(self.shadow.get_by_type(memory_type))))
        return p

    def search(self, query: MemoryQuery) -> List[MemorySearchResult]:
        p = self.primary.search(query)
        if self.compare_reads:
            self._compare("search", _ranking(p), lambda: _ranking(self.shadow.search(query)))
        return p

    def _compare(self, method: str, primary_value, shadow_thunk) -> None:
        try:
            shadow_value = shadow_thunk()
        except Exception as exc:
            self.report.record_write_error(exc)
            logger.warning("shadow read failed (isolated): %s", exc)
            return
        self.report.record(method, primary_value, shadow_value)

    # -- passthrough reads (no diff) ----------------------------------------

    def get(self, memory_id: str) -> Optional[Memory]:
        return self.primary.get(memory_id)

    def all(self) -> List[Memory]:
        return self.primary.all()

    def get_by_tag(self, tag: str) -> List[Memory]:
        return self.primary.get_by_tag(tag)

    def get_linked(self, memory_id: str) -> List[Memory]:
        return self.primary.get_linked(memory_id)

    # -- lifecycle (mirror to both; shadow isolated) ------------------------

    def save(self) -> None:
        self.primary.save()
        self._shadow_write(lambda: self.shadow.save())

    def update(self, memory: Memory):
        self.primary.update(memory)
        self._shadow_write(lambda: self.shadow.update(memory))

    def delete(self, memory_id: str) -> bool:
        result = self.primary.delete(memory_id)
        self._shadow_write(lambda: self.shadow.delete(memory_id))
        return result

    def clear(self):
        self.primary.clear()
        self._shadow_write(lambda: self.shadow.clear())
