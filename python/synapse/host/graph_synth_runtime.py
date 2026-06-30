"""Shared graph-synthesis runtime — the SINGLE source of the one ProposalStore
that the cognitive ``synapse_propose_graph`` tool parks validated proposals into
AND that the host ``instantiate_graph`` handler builds from.

CRITICAL INVARIANT
------------------
propose (configure) and build MUST share ONE ProposalStore, or every
``proposal_id`` parked by propose misses at build time. This module holds that
one store; both wirings import it from here. ``wire_propose()`` configures the
propose tool with that store; ``instantiate()`` drives a GraphBuilder bound to
the SAME store.

§12 import guard
----------------
host/ — hou is ALLOWED here, but the hou-backed oracles
(``HouExistenceOracle`` / ``ConnectivityOracle``) import ``hou`` AT
CONSTRUCTION. So everything is built LAZILY behind a re-entrant lock: the module
imports cleanly headless (CI / stock-Python), and the hou touch only happens the
first time ``wire_propose()`` or ``instantiate()`` actually runs — inside
Houdini 21. ``GraphBuilder`` / ``ProposalStore`` are stdlib-only at import (the
former carries its own ``try: import hou`` guard), so the top-level imports are
headless-safe.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

from synapse.host.graph_builder import GraphBuilder, InstantiationResult
from synapse.host.proposal_store import ProposalStore

logger = logging.getLogger(__name__)

# Lazily-constructed singletons. The lock is RE-ENTRANT because wire_propose()
# and _get_builder() both acquire it and then call _get_store(), which acquires
# it again — a plain Lock would self-deadlock.
_lock = threading.RLock()
_store: Optional[ProposalStore] = None
_builder: Optional[GraphBuilder] = None
_propose_wired = False


def _get_store() -> ProposalStore:
    """The ONE shared store. Constructed once, on first access."""
    global _store
    with _lock:
        if _store is None:
            _store = ProposalStore()
        return _store


def _build_validator():
    """Build the hou-backed validator (the SAME oracles GraphBuilder grounds
    with). Imported lazily so the module stays headless-importable — these host
    oracles import ``hou`` at module load. Also used AS the GraphBuilder's
    re-validation factory so oracle construction is single-sourced here."""
    from synapse.cognitive.graph_validator import GraphValidator
    from synapse.host.existence_adapter import HouExistenceOracle
    from synapse.host.graph_oracle import ConnectivityOracle

    return GraphValidator(HouExistenceOracle(), ConnectivityOracle())


def wire_propose() -> None:
    """Configure ``synapse_propose_graph`` with the hou-backed validator and the
    SHARED store. Idempotent — safe to call on every daemon start and on first
    MCP use; the configure() injection only fires once.

    §12 DEGRADE: the validator is built from the hou-backed oracles, which import
    ``hou`` at construction. In a headless/no-hou context (e.g. a daemon built with
    ``boot_gate=False`` for tests) that import raises — so we SWALLOW it, leave the
    tool UNCONFIGURED, and DO NOT set ``_propose_wired`` (a later call inside real
    Houdini re-attempts and succeeds). The daemon's Dispatcher must still build
    even when graph synthesis can't ground — an unconfigured propose tool simply
    raises 'not configured' on call, never at boot."""
    global _propose_wired
    with _lock:
        if _propose_wired:
            return
        try:
            from synapse.cognitive.tools import propose_graph

            validator = _build_validator()
        except Exception:
            logger.warning(
                "graph_synth propose wiring deferred — hou-backed oracles "
                "unavailable (headless?); synapse_propose_graph stays unconfigured",
                exc_info=True,
            )
            return
        propose_graph.configure(validator, _get_store())
        _propose_wired = True


def _agent_usd_provenance(payload: Dict[str, Any]) -> None:
    """Best-effort BUILD-provenance writer wired into the GraphBuilder.

    Honors the "provenance or it didn't happen" convention for the mutation by
    appending the build receipt to $HIP/claude/agent.usd's
    /SYNAPSE/memory/decisions. Mirrors mcp/session.py's canonical agent.usd
    ensure-pattern (hip/job -> ensure_scene_structure -> agent_usd -> writer).

    It MUST NEVER raise: provenance is best-effort and a write failure must not
    block or fail a build (the build completes + returns BUILT regardless). The
    hou + scene_memory + agent_state imports are LAZY so this module stays
    headless-importable.
    """
    try:
        import os

        import hou  # host context — hou allowed; lazy so module imports headless

        from synapse.memory.scene_memory import ensure_scene_structure
        from synapse.memory.agent_state import log_decision

        hip_path = hou.hipFile.path()
        job_path = hou.getenv("JOB", os.path.dirname(hip_path))
        paths = ensure_scene_structure(hip_path, job_path)
        agent_usd = paths.get("agent_usd", "")
        if agent_usd and os.path.exists(agent_usd):
            log_decision(agent_usd, payload)
    except Exception:  # noqa: BLE001 — best-effort; build must never block on provenance
        logger.warning(
            "build provenance write to agent.usd failed (best-effort, build unaffected)",
            exc_info=True,
        )


def _get_builder() -> GraphBuilder:
    """The ONE GraphBuilder, bound to the SHARED store. Its re-validation factory
    is ``_build_validator`` (the same oracles), so the store is the only shared
    state the propose path and the build path co-own. The build's mutation
    provenance is wired to ``_agent_usd_provenance`` (best-effort agent.usd
    receipt — never blocks the build)."""
    global _builder
    with _lock:
        if _builder is None:
            _builder = GraphBuilder(
                _get_store(),
                validator_factory=_build_validator,
                provenance_writer=_agent_usd_provenance,
            )
        return _builder


def result_to_dict(r: InstantiationResult) -> Dict[str, Any]:
    """Serialize an InstantiationResult for the WS response (JSON-safe — the
    status enum is flattened to its string value)."""
    return {
        "status": r.status.value,
        "proposal_id": r.proposal_id,
        "message": r.message,
        "created_paths": r.created_paths,
        "parameters_set": r.parameters_set,
        "connections": r.connections,
        "revert": r.revert,
        "errors": r.errors,
        "ok": r.ok(),
    }


def instantiate(proposal_id: str) -> InstantiationResult:
    """Drive the shared-store GraphBuilder. The proposal_id resolves against the
    SAME store propose parked into — that is the shared-store invariant."""
    return _get_builder().instantiate(proposal_id)


def reset() -> None:
    """Test/diagnostic helper — drop the lazily-built singletons so a fresh test
    constructs a clean store/builder/propose wiring. Not used in production."""
    global _store, _builder, _propose_wired
    with _lock:
        _store = None
        _builder = None
        _propose_wired = False
