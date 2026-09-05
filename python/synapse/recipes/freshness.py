"""Event coverage plus a scoped observation decides whether evidence is current.

Never hash a full USD stage per UI frame. ``freshness`` is for action preflight
and consumes a cheap, host-owned instance fingerprint, NOT authored_baseline
(the last committed digest is not an observation). Use ``periodic_recheck`` for
supplementary scoped observations: it enforces at least one second between
calls, including failures. None of these functions call Houdini or USD.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import threading
import time
from typing import Callable, Protocol

from .contracts import EvidenceFreshness, OperationState, RecipeInstance, RunReceipt
from .receipt import timestamp, utc_now


class InstanceFingerprint(Protocol):
    def __call__(self, instance: RecipeInstance) -> str | None:
        """Current observed scoped fingerprint, or None if it is not measured."""
        ...


INVALIDATING_EVENTS = frozenset({"scene_load", "undo", "redo", "owned_edit", "dependency_change"})
MIN_RECHECK_INTERVAL = 1.0


@dataclass(frozen=True)
class Invalidation:
    event: str
    at: datetime
    instance_id: str | None


class EvidenceTracker:
    """One scene session's event history; disconnected/missing tracking is UNKNOWN.

    ``tracking_complete=True`` is an assertion by the trusted event adapter that
    ALL invalidation sources have continuous coverage from ``tracking_since``.
    Reconnecting starts a new coverage interval; it cannot certify old receipts.
    A scene load is global even if the caller supplies an instance ID. Unknown
    event scope is global, conservatively invalidating every affected receipt.
    """

    def __init__(self, fingerprint: InstanceFingerprint | None = None, *,
                 tracking_complete: bool = False, tracking_since: str | None = None,
                 min_interval: float = 2.0, clock: Callable[[], float] = time.monotonic):
        if not math.isfinite(min_interval) or min_interval < MIN_RECHECK_INTERVAL:
            raise ValueError("min_interval must be finite and at least one second")
        self._fingerprint = fingerprint
        self._complete = bool(tracking_complete)
        self._since = timestamp(tracking_since or utc_now())
        self._events: list[Invalidation] = []
        self._interval = min_interval
        self._clock = clock
        self._last_recheck: float | None = None
        self._lock = threading.RLock()

    def set_tracking(self, complete: bool, *, since: str | None = None) -> None:
        """Report a tracking gap/reconnect; do not retroactively close a gap."""
        with self._lock:
            self._complete = bool(complete)
            self._since = max(self._since, timestamp(since or utc_now()))

    def invalidate(self, event: str, *, at: str | None = None,
                   instance_id: str | None = None) -> None:
        if event not in INVALIDATING_EVENTS:
            raise ValueError(f"unknown invalidation event: {event}")
        with self._lock:
            self._events.append(Invalidation(event, timestamp(at or utc_now()),
                                             None if event == "scene_load" else instance_id))

    def freshness(self, receipt: RunReceipt, instance: RecipeInstance) -> EvidenceFreshness:
        with self._lock:
            if (receipt.instance_id != instance.instance_id or receipt.recipe_id != instance.recipe_id
                    or receipt.recipe_version != instance.recipe_version):
                return EvidenceFreshness.STALE
            if receipt.completed_at is None or receipt.operation_state != OperationState.TERMINAL:
                return EvidenceFreshness.UNKNOWN
            try:
                completed = timestamp(receipt.completed_at)
            except (ValueError, TypeError, AttributeError):
                return EvidenceFreshness.UNKNOWN
            if completed > timestamp(utc_now()):
                return EvidenceFreshness.UNKNOWN
            if any(event.at >= completed and event.instance_id in (None, instance.instance_id)
                   for event in self._events):
                return EvidenceFreshness.STALE
            if receipt.revision_after is not None and receipt.revision_after != instance.graph_revision:
                return EvidenceFreshness.STALE
            if not self._complete or self._since > completed or self._fingerprint is None:
                return EvidenceFreshness.UNKNOWN
            try:
                current = self._fingerprint(instance)
            except Exception:
                return EvidenceFreshness.UNKNOWN
            # A reentrant host observation may deliver an invalidation or tracking gap.
            if any(event.at >= completed and event.instance_id in (None, instance.instance_id)
                   for event in self._events):
                return EvidenceFreshness.STALE
            if not self._complete or self._since > completed:
                return EvidenceFreshness.UNKNOWN
            if not isinstance(current, str) or not current or not receipt.fingerprint_after:
                return EvidenceFreshness.UNKNOWN
            return (EvidenceFreshness.CURRENT if current == receipt.fingerprint_after
                    else EvidenceFreshness.STALE)

    def periodic_recheck(self, observe: Callable[[], None]) -> bool:
        """Run one scoped host observation at most once per min_interval.

        True means the hook ran, never that evidence passed. The host owns
        main-thread scheduling. An observation failure opens a tracking gap.
        An event does not bypass the throttle; action preflight is separate.
        """
        with self._lock:
            now = self._clock()
            if self._last_recheck is not None and now - self._last_recheck < self._interval:
                return False
            self._last_recheck = now
            try:
                observe()
            except Exception:
                self.set_tracking(False)
                raise
            return True
