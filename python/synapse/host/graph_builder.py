"""Atomic instantiation from a VALIDATED proposal. host/ — hou allowed.

Re-run validation UNCONDITIONALLY (§7 TOCTOU guard) against the *current* live
scene before building. Then ONE undo block: create NEW nodes (topological order;
EXISTING already placed) -> set parms (NEW only) -> connect edges -> close ->
emit a best-effort provenance receipt. Truth contract: read back every parm set
and every connection made; the result reports the ACTUAL observed state, never an
unobserved claim.

hou symbols used here are dir()-confirmed against LIVE Houdini 21.0.671 at the
bench (instance-level for the SWIG methods the type-introspection table misses):
  hou.node, hou.undos.group, hou.Node.createNode, hou.Node.setInput,
  hou.Node.parm / .parmTuple (instance methods), hou.Node.path, hou.Node.type,
  hou.Node.inputConnections, hou.Parm.set/.eval, hou.ParmTuple.eval,
  hou.NodeConnection.inputIndex/.outputIndex/.inputNode.
None of the four quarantined phantoms (the pdg module, the secure namespace, the
lop-network accessor, the graph-tick updater) appear here.

Not imported by the Mile-1 cognitive path; filled at the bench in Mile 3."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from synapse.cognitive.graph_proposal import (
    GraphProposal,
    NodeKind,
    ValidationStatus,
)

# §12 import guard — the module must import HEADLESS (the gated test drives it with
# a fake hou). On ImportError the name is None; production runs inside Houdini 21.
try:  # pragma: no cover — exercised both ways across environments
    import hou
except ImportError:  # headless / CI — the gated test injects a fake hou
    hou = None  # type: ignore[assignment]


class InstantiationStatus(str, Enum):
    BUILT = "built"        # the graph was constructed and read back clean
    REJECTED = "rejected"  # unknown proposal_id — nothing to build (amendment 5)
    HALTED = "halted"      # TOCTOU re-validation INVALID — scene changed; zero mutation
    FAILED = "failed"      # build raised mid-way; rolled back to ZERO net mutation


@dataclass
class InstantiationResult:
    status: InstantiationStatus
    proposal_id: str
    message: str = ""
    created_paths: list[str] = field(default_factory=list)          # observed node.path() of NEW nodes
    parameters_set: list[dict[str, Any]] = field(default_factory=list)  # observed parm readback
    connections: list[dict[str, Any]] = field(default_factory=list)     # observed wiring readback
    revert: str = ""                                                # single Ctrl+Z hint
    errors: list[dict[str, str]] = field(default_factory=list)      # re-validation issues on HALT

    def ok(self) -> bool:
        return self.status is InstantiationStatus.BUILT


def _default_validator_factory():
    # Production construction site: the SAME hou-backed Mile-2 oracles the daemon
    # grounded with, NOT a scout adapter. Imported lazily so the module stays
    # headless-importable (these host oracles import hou at module load).
    from synapse.cognitive.graph_validator import GraphValidator
    from synapse.host.existence_adapter import HouExistenceOracle
    from synapse.host.graph_oracle import ConnectivityOracle

    return GraphValidator(HouExistenceOracle(), ConnectivityOracle())


class GraphBuilder:
    """Constructs a validated GraphProposal into the live scene, atomically.

    Inject `store` (the SAME ProposalStore the propose tool parks into) and,
    optionally, a `validator_factory` (() -> GraphValidator) and a
    `provenance_writer` (callable(dict) -> None). Defaults build the hou-backed
    production stack; the gated test injects fakes for all three.
    """

    def __init__(
        self,
        store,
        validator_factory: Callable[[], Any] | None = None,
        *,
        provenance_writer: Callable[[dict], None] | None = None,
    ):
        self._store = store
        self._validator_factory = validator_factory or _default_validator_factory
        self._provenance = provenance_writer

    # ------------------------------------------------------------------ public
    def instantiate(self, proposal_id: str) -> InstantiationResult:
        # 1. Look up. Unknown id -> clean rejection, ZERO mutation, NEVER enter the
        #    undo group (amendment 5).
        proposal = self._store.get(proposal_id)
        if proposal is None:
            return InstantiationResult(
                status=InstantiationStatus.REJECTED,
                proposal_id=proposal_id,
                message=f"unknown proposal_id '{proposal_id}' — nothing to build",
            )

        # 2. TOCTOU guard — re-validate UNCONDITIONALLY against the CURRENT live
        #    scene before any mutation. A node deleted between propose and
        #    instantiate makes P5 resolve_node_type raise -> INVALID -> HALT here,
        #    ZERO mutation, undo group never entered. (The §7 scene_fingerprint
        #    baseline is inert at park — residual f — so the re-validate is the
        #    working TOCTOU guard; a fingerprint compare is recomputed only if a
        #    live baseline was stamped, which it is not yet.)
        validator = self._validator_factory()
        report = validator.validate(proposal)
        if report.status is not ValidationStatus.VALID:
            return InstantiationResult(
                status=InstantiationStatus.HALTED,
                proposal_id=proposal_id,
                message="re-validation INVALID — scene changed since propose; zero mutation",
                errors=[{"where": e.where, "message": e.message} for e in report.errors],
            )

        # 3. ONE undo group wraps the WHOLE mutation (single Ctrl+Z reverts).
        by_id = {n.node_id: n for n in proposal.nodes}
        created: dict[str, Any] = {}          # node_id -> live hou.Node (NEW only)
        parameters_set: list[dict[str, Any]] = []
        connections: list[dict[str, Any]] = []
        undo_label = f"SYNAPSE graph synth {proposal_id}"
        build_error: Exception | None = None
        created_paths: list[str] = []

        with hou.undos.group(undo_label):
            parent = hou.node(proposal.parent_path)
            try:
                # 3a. create NEW nodes in topological order (EXISTING already
                #     placed — never recreate).
                for node_id in self._topo_order_new(proposal):
                    n = by_id[node_id]
                    created[node_id] = parent.createNode(
                        n.node_type, n.friendly_name or None
                    )

                # 3b. set parms on NEW nodes ONLY (EXISTING carry no overrides per
                #     contract). Read each back immediately (truth contract).
                for node_id, node in created.items():
                    n = by_id[node_id]
                    for parm_name, value in n.parameter_overrides.items():
                        parameters_set.append(
                            self._set_and_read(node, parm_name, value)
                        )

                # 3c. connect edges: source_output_index -> target_input_index. NEW
                #     endpoints resolve to the freshly created node; EXISTING resolve
                #     by live scene_path.
                for e in proposal.edges:
                    src = self._resolve(e.source_node_id, by_id, created)
                    tgt = self._resolve(e.target_node_id, by_id, created)
                    tgt.setInput(e.target_input_index, src, e.source_output_index)

                # 3d. read back every connection AFTER all wiring (truth contract).
                for e in proposal.edges:
                    tgt = self._resolve(e.target_node_id, by_id, created)
                    connections.append(self._read_connection(tgt, e.target_input_index))

                created_paths = [created[nid].path() for nid in created]
            except Exception as exc:  # noqa: BLE001 — any build-time failure rolls back
                # MAJOR FIX: the validator defers wire-type compatibility to build-
                # time setInput, and createNode can fail under TOCTOU, so the build
                # can raise mid-way. Roll back INSIDE the undo group — destroy the
                # NEW nodes we created (EXISTING are never touched) so the group nets
                # to ZERO mutation — then surface a structured FAILED result instead
                # of propagating an uncaught exception and leaving orphan nodes.
                build_error = exc
                for node in list(created.values()):
                    try:
                        node.destroy()
                    except Exception:  # noqa: BLE001 — best-effort cleanup
                        pass
                created.clear()
                parameters_set.clear()
                connections.clear()
                created_paths = []

        if build_error is not None:
            return InstantiationResult(
                status=InstantiationStatus.FAILED,
                proposal_id=proposal_id,
                message=f"build failed and was rolled back (zero net mutation): {build_error}",
            )

        # 4. Provenance receipt — BEST-EFFORT, never blocks the build.
        self._emit_provenance(proposal, created_paths, undo_label)

        # 5. Truth contract — the result carries only observed state.
        return InstantiationResult(
            status=InstantiationStatus.BUILT,
            proposal_id=proposal_id,
            message=f"instantiated {len(created_paths)} new node(s) under {proposal.parent_path}",
            created_paths=created_paths,
            parameters_set=parameters_set,
            connections=connections,
            revert=f"single undo reverts: '{undo_label}'",
        )

    # ------------------------------------------------------------- internals
    @staticmethod
    def _topo_order_new(proposal: GraphProposal) -> list[str]:
        # Kahn over NEW nodes only (EXISTING are already placed and impose no
        # creation-order constraint). Edges among NEW nodes give the partial order;
        # declaration order is the deterministic tiebreak. Validation already
        # guaranteed acyclicity (P4); leftovers (defensive) append in decl order.
        new_ids = [n.node_id for n in proposal.nodes if n.kind is NodeKind.NEW]
        new_set = set(new_ids)
        indeg = {nid: 0 for nid in new_ids}
        adj: dict[str, list[str]] = {nid: [] for nid in new_ids}
        for e in proposal.edges:
            if e.source_node_id in new_set and e.target_node_id in new_set:
                adj[e.source_node_id].append(e.target_node_id)
                indeg[e.target_node_id] += 1
        queue = [nid for nid in new_ids if indeg[nid] == 0]
        order: list[str] = []
        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for m in adj[nid]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    queue.append(m)
        if len(order) < len(new_ids):
            order += [nid for nid in new_ids if nid not in order]
        return order

    @staticmethod
    def _resolve(node_id: str, by_id: dict, created: dict):
        # NEW -> freshly created node; EXISTING -> live node at its scene_path.
        n = by_id[node_id]
        if n.kind is NodeKind.NEW:
            return created[node_id]
        return hou.node(n.scene_path)

    @staticmethod
    def _set_and_read(node, parm_name: str, value: Any) -> dict[str, Any]:
        # Set a scalar parm or a parm tuple, then read it back. Never claim a value
        # we did not observe — a missing template surfaces as observed=None.
        record: dict[str, Any] = {
            "path": node.path(), "parm": parm_name, "requested": value, "observed": None,
        }
        parm = node.parm(parm_name)
        if parm is not None:
            parm.set(value)
            record["observed"] = parm.eval()
            return record
        tup = node.parmTuple(parm_name)
        if tup is not None:
            tup.set(value)
            record["observed"] = tuple(tup.eval())
        return record

    @staticmethod
    def _read_connection(tgt, input_index: int) -> dict[str, Any]:
        # Read the live wiring at this input index back from the scene.
        record: dict[str, Any] = {
            "target": tgt.path(), "input_index": input_index,
            "wired": False, "source": None, "source_output": None,
        }
        for c in tgt.inputConnections():
            if c.inputIndex() == input_index:
                record.update(
                    wired=True,
                    source=c.inputNode().path(),
                    source_output=c.outputIndex(),
                )
                break
        return record

    def _emit_provenance(self, proposal: GraphProposal, created_paths: list[str], undo_label: str) -> None:
        # Provenance-or-it-didn't-happen, but never block the build on it. If a host
        # wired an agent.usd / agent_state writer, call it; otherwise this is the
        # documented seam where production attaches one. (Residual: the agent.usd
        # provenance writers are dormant — no live caller yet — so default is a no-op.)
        if self._provenance is None:
            return
        try:
            self._provenance({
                "decision": f"instantiate graph proposal {proposal.proposal_id}",
                "reasoning": proposal.natural_language_intent,
                "parent_path": proposal.parent_path,
                "created_paths": created_paths,
                "model_id": proposal.model_id,
                "revert": f"single undo: '{undo_label}'",
            })
        except Exception:  # noqa: BLE001 — provenance is best-effort, never gate-blocking
            pass
