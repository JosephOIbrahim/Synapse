"""Atomic instantiation from a VALIDATED proposal. host/ — hou allowed.

Re-run Phase 5 + recompute fingerprint UNCONDITIONALLY (§7) before building
(TOCTOU guard). Then ONE undo block: create NEW nodes (topological order;
existing already placed) -> set parms (new only) -> connect edges -> close ->
emit provenance receipt. Truth contract: read back every set parm; never claim
an unobserved outcome.

Not imported by the Mile-1 cognitive path; filled at the bench in Mile 3."""
from __future__ import annotations

import hou  # noqa: F401 — host layer; never imported by cognitive.*


class GraphBuilder:
    def instantiate(self, proposal_id: str):
        raise NotImplementedError("Mile 3 — spec §5.6, §7; reject unknown id (amendment 5)")
