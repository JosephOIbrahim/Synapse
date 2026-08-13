"""WriteThroughStore — Moneta active, JSONL as the automatic write-through net.

W3-MIGRATE target #4: after go-live the ACTIVE backend is Moneta, but every
write is *also* mirrored to the JSONL ``MemoryStore`` so a plain-text, decrypt-
free safety net is always current. This is the inverse of
:class:`shadow_store.ShadowMemoryStore` (which keeps JSONL primary + Moneta
shadow, for the pre-cutover measuring period):

  * Reads are served from the **primary** (Moneta) — the flipped, active backend.
  * Writes go to BOTH. The Moneta write propagates its failure (the caller must
    know if the active store rejected a write); the JSONL net write is ISOLATED
    and logged **loudly** — a net failure must never break the caller, but it is
    never silent either, because the net is the whole point of the flip.
  * No memory ever lands in ONLY one store: an ``add`` that reaches Moneta also
    reaches the JSONL net (or is loudly recorded as a net-write failure).

Reversibility: the JSONL net is a complete, authoritative ``MemoryStore``. To
fall back to JSONL-primary, set ``SYNAPSE_MEMORY_BACKEND=jsonl`` (store.py) —
this wrapper is discarded and the JSONL store it was feeding IS the memory. The
flip is therefore reversible by construction; the net is not a lossy mirror.

This is a composable wrapper over the PUBLIC store surfaces (``MonetaBackedStore``
+ ``MemoryStore``); it edits no store internals, so it composes cleanly with the
dim / kind / store legs. Pure-Python, zero ``hou``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .models import Memory, MemoryQuery, MemorySearchResult, MemoryType
from .moneta_store import MonetaUpdateNotSupported

logger = logging.getLogger(__name__)


@dataclass
class WriteThroughReport:
    """Running tally of the net's health (for probes / doctor readouts)."""

    writes: int = 0
    net_writes: int = 0
    net_write_errors: List[str] = field(default_factory=list)

    @property
    def net_armed(self) -> bool:
        """True while every write also reached the JSONL net."""
        return self.writes > 0 and self.net_writes == self.writes \
            and not self.net_write_errors

    def summary(self) -> dict:
        return {
            "writes": self.writes,
            "net_writes": self.net_writes,
            "net_write_errors": len(self.net_write_errors),
            "net_armed": self.net_armed,
        }


class WriteThroughStore:
    """Moneta-primary store that mirrors every write to a JSONL safety net."""

    def __init__(self, primary, net, *, report: Optional[WriteThroughReport] = None):
        self.primary = primary          # MonetaBackedStore (active / reads)
        self.net = net                  # MemoryStore (JSONL write-through net)
        self.report = report or WriteThroughReport()

    @classmethod
    def from_storage_dir(cls, storage_dir, embedder=None) -> "WriteThroughStore":
        """Wire Moneta + JSONL over ONE storage dir — the natural go-live layout
        (``memory.jsonl`` and ``.moneta/`` live side by side under the store)."""
        from .moneta_store import MonetaBackedStore
        from .store import MemoryStore
        storage_dir = Path(storage_dir)
        primary = MonetaBackedStore.from_storage_dir(storage_dir, embedder=embedder)
        net = MemoryStore(storage_dir, background_load=False)
        net._wait_loaded()
        return cls(primary, net)

    # -- write (both stores; net isolated + loud) ---------------------------

    def add(self, memory: Memory) -> str:
        result = self.primary.add(memory)   # active store; failure propagates
        self.report.writes += 1
        try:
            self.net.add(memory)
            self.net.save()                 # flush the net to disk immediately
            self.report.net_writes += 1
        except Exception as exc:            # net must never break the caller...
            self.report.net_write_errors.append(f"{type(exc).__name__}: {exc}")
            logger.error(                   # ...but is never silent (armed net!)
                "WRITE-THROUGH NET FAILED for %s (isolated): %s — the JSONL "
                "safety net did NOT receive this memory; investigate.",
                getattr(memory, "id", "<?>"), exc,
            )
        return result

    def save(self) -> None:
        self.primary.save()
        try:
            self.net.save()
        except Exception as exc:
            self.report.net_write_errors.append(f"save: {type(exc).__name__}: {exc}")
            logger.error("write-through net save() failed (isolated): %s", exc)

    def close(self) -> None:
        for store in (self.primary, self.net):
            close = getattr(store, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as exc:
                    logger.warning("close() failed on %s (isolated): %s", store, exc)

    # -- read (served from the ACTIVE backend: Moneta) ----------------------

    def count(self) -> int:
        return self.primary.count()

    def all(self) -> List[Memory]:
        return self.primary.all()

    def get(self, memory_id: str) -> Optional[Memory]:
        return self.primary.get(memory_id)

    def get_recent(self, limit: int = 10) -> List[Memory]:
        return self.primary.get_recent(limit)

    def get_by_type(self, memory_type: MemoryType) -> List[Memory]:
        return self.primary.get_by_type(memory_type)

    def get_by_tag(self, tag: str) -> List[Memory]:
        return self.primary.get_by_tag(tag)

    def get_linked(self, memory_id: str) -> List[Memory]:
        return self.primary.get_linked(memory_id)

    def search(self, query: MemoryQuery) -> List[MemorySearchResult]:
        return self.primary.search(query)

    # -- unsupported (the active backend is append/consolidate) --------------

    def update(self, memory: Memory):
        raise MonetaUpdateNotSupported(
            "WriteThroughStore is Moneta-active (append/consolidate); in-place "
            "update is not supported. Re-add as a new memory."
        )

    def delete(self, memory_id: str) -> bool:
        raise MonetaUpdateNotSupported(
            "WriteThroughStore does not support targeted delete; pruning is "
            "handled by the Moneta consolidation pass."
        )

    def clear(self):
        raise MonetaUpdateNotSupported(
            "WriteThroughStore.clear() is unsupported on live handles."
        )
