"""
Synapse Graph-Synthesis Handler Mixin

Routes BOTH halves of graph synthesis through HOST command handlers that run IN
the Houdini process:

  - ``propose_graph``     — validate a declarative proposal against the LIVE
                            runtime (hou-backed oracles) and park it if VALID.
  - ``instantiate_graph`` — build a previously-VALIDATED proposal into the scene.

Both drive the shared graph-synthesis runtime
(``synapse.host.graph_synth_runtime``). They run in the SAME process and so share
THAT PROCESS'S single ``ProposalStore`` — that is the real invariant: propose
parks an id into the one store, instantiate resolves the same id from it.

Why propose lives HERE (not as an in-process cognitive tool like scout): its
grounding is a LIVE ``hou`` oracle (``HouExistenceOracle`` / ``ConnectivityOracle``)
that imports ``hou`` at construction, NOT a local corpus. The mcp_server process
has no ``hou`` and forwards over WebSocket to a SEPARATE Houdini process's store —
so propose, exactly like the build half, MUST run in the Houdini process and
reach both transports the same way (in-process daemon handler + /mcp -> WS).

Both handlers marshal onto Houdini's main thread via ``run_on_main``. Provenance
is AUTOMATIC: the FloorGate wraps every registered command at the registry's
``invoke()`` (Tier-0), so these handlers need no separate provenance writer. No
consent gate — the live /synapse path is single-user-localhost auto-approve by
design (propose mutates nothing; instantiate's undo group reverts the build).
"""

from typing import Any, Dict

from ..core.errors import SynapseUserError


class GraphSynthHandlerMixin:
    """Mixin providing the propose + instantiate graph-synthesis handlers."""

    def _handle_propose_graph(self, payload: Dict) -> Dict[str, Any]:
        """Validate a declarative graph proposal against the LIVE runtime and
        park it (if VALID) for later instantiation. Read-only — it validates +
        parks, it does NOT mutate the scene.

        This runs IN the Houdini process because propose's grounding is a live
        ``hou`` oracle (built lazily by ``wire_propose``), symmetric to
        ``_handle_instantiate_graph``. ``wire_propose()`` is idempotent and
        succeeds here because ``hou`` IS present; calling it lazily in the
        handler (rather than at daemon boot) keeps boot independent of it.
        """
        proposal = payload.get("proposal")
        if not isinstance(proposal, dict) or not proposal:
            raise SynapseUserError(
                "propose_graph needs a 'proposal' object "
                "(the declarative GraphProposal to validate)."
            )

        from .main_thread import run_on_main
        from synapse.host import graph_synth_runtime

        def _on_main():
            # Lazy + idempotent: configures the propose tool with the hou-backed
            # validator and the SHARED store. Succeeds here (hou present); a
            # headless/no-hou context leaves it unconfigured and the call below
            # raises a legible 'not configured' rather than failing at boot.
            graph_synth_runtime.wire_propose()
            from synapse.cognitive.tools import propose_graph

            return propose_graph.synapse_propose_graph(proposal)

        return run_on_main(_on_main)

    def _handle_instantiate_graph(self, payload: Dict) -> Dict[str, Any]:
        """Instantiate a previously-VALIDATED graph proposal by id.

        The hou work (createNode/setInput/undos.group) lives deep in
        GraphBuilder, which carries its own §12 import guard and TOCTOU
        re-validation; this handler only marshals onto the main thread and
        serializes the result.
        """
        proposal_id = payload.get("proposal_id")
        if not isinstance(proposal_id, str) or not proposal_id:
            raise SynapseUserError(
                "instantiate_graph needs a 'proposal_id' string "
                "(the id returned by synapse_propose_graph)."
            )

        from .main_thread import run_on_main
        from synapse.host import graph_synth_runtime

        def _on_main():
            result = graph_synth_runtime.instantiate(proposal_id)
            return graph_synth_runtime.result_to_dict(result)

        return run_on_main(_on_main)
