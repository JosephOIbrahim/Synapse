"""Adapts scout's confirmed surface to IExistenceOracle. host/ — hou allowed.

If §2.6 shows scout returns a structured exists verdict -> thin pass-through.
If scout returns retrieval chunks -> wrap: query scout, check the symbol appears.
Either way this is the ONLY place the real scout interface is touched.

Bench-gated: the real wiring needs the live RAG/scout surface (§2.6 preflight),
so this stays a loud stub until run against the running daemon. Mile 1's DoD
injects a mock existence oracle instead, so the cognitive path is fully tested
without this adapter."""
from __future__ import annotations


class ScoutExistenceAdapter:  # implements IExistenceOracle
    def node_type_exists(self, node_type: str, category: str) -> bool:
        raise NotImplementedError("Mile 1/2 — wire to confirmed scout surface (§2.6, at the bench)")

    def parameter_exists(self, node_type: str, category: str, parm_name: str) -> bool:
        raise NotImplementedError("Mile 1/2 — wire to confirmed scout surface (§2.6, at the bench)")
