"""In-memory validated-proposal store on the daemon. Non-persistent across panel
restarts. Amendment 5: instantiate REJECTS unknown ids; store has TTL + size cap.

Lives under host/ (it's daemon state) but imports no hou — it is pure stdlib."""
from __future__ import annotations

import time


class ProposalStore:
    def __init__(self, ttl_seconds: int = 1800, max_entries: int = 256):
        self._ttl = ttl_seconds
        self._cap = max_entries
        self._data: dict[str, tuple[float, object]] = {}   # proposal_id -> (stored_at, proposal)

    def put(self, proposal) -> None:
        self._evict_expired()
        # Cap breach evicts the oldest entry (FIFO by store time) before insert,
        # so a flood of proposals can never grow the daemon unbounded.
        if proposal.proposal_id not in self._data and len(self._data) >= self._cap:
            oldest = min(self._data, key=lambda k: self._data[k][0])
            del self._data[oldest]
        self._data[proposal.proposal_id] = (time.monotonic(), proposal)

    def get(self, proposal_id: str):
        self._evict_expired()
        entry = self._data.get(proposal_id)
        return entry[1] if entry else None

    def _evict_expired(self) -> None:
        now = time.monotonic()
        dead = [k for k, (stored_at, _) in self._data.items() if now - stored_at > self._ttl]
        for k in dead:
            del self._data[k]
