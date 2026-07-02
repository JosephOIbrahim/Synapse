"""synapse_propose_graph tool entry. Validates a GraphProposal; mutates nothing.
Mirrors the existing scout / inspect_stage cognitive-tool pattern. ZERO hou IMPORTS.

Construction is a SEPARATE, APPROVE-gated step (Mile 3, host/graph_builder). This
tool only proves a proposal is sound and parks it for later instantiation."""
from __future__ import annotations

from ..graph_proposal import (
    GraphProposal,
    MergeStrategy,
    NodeKind,
    ProposedEdge,
    ProposedNode,
    ValidationStatus,
)
from ..graph_validator import GraphValidator

SYNAPSE_PROPOSE_GRAPH_SCHEMA = {
    "name": "synapse_propose_graph",
    "description": "Validate a declarative graph proposal against the live runtime; mutates nothing.",
    "input_schema": {
        "type": "object",
        "properties": {"proposal": {"type": "object"}},
        "required": ["proposal"],
    },
}

# Host wiring injects the validator + store once at daemon start; the tool itself
# stays import-pure (no hou). configure() is the single injection seam.
_VALIDATOR: GraphValidator | None = None
_STORE = None


def configure(validator: GraphValidator, store) -> None:
    global _VALIDATOR, _STORE
    _VALIDATOR = validator
    _STORE = store


def _node_from_dict(d: dict) -> ProposedNode:
    pos = d.get("position")
    return ProposedNode(
        node_id=d["node_id"],
        kind=NodeKind(d["kind"]),
        node_category=d["node_category"],
        node_type=d.get("node_type", ""),
        friendly_name=d.get("friendly_name", ""),
        parameter_overrides=d.get("parameter_overrides") or {},
        scene_path=d.get("scene_path"),
        position=(float(pos[0]), float(pos[1])) if pos else None,
    )


def _edge_from_dict(d: dict) -> ProposedEdge:
    return ProposedEdge(
        source_node_id=d["source_node_id"],
        source_output_index=int(d.get("source_output_index", 0)),
        target_node_id=d["target_node_id"],
        target_input_index=int(d.get("target_input_index", 0)),
        # U.1: optional declared slot label — P3e verifies it against the
        # connectivity catalog when the target type is known.
        target_input_label=str(d.get("target_input_label", "") or ""),
    )


def _proposal_from_dict(d: dict) -> GraphProposal:
    return GraphProposal(
        proposal_id=d["proposal_id"],
        network_type=d["network_type"],
        parent_path=d["parent_path"],
        nodes=[_node_from_dict(n) for n in d.get("nodes", [])],
        edges=[_edge_from_dict(e) for e in d.get("edges", [])],
        natural_language_intent=d.get("natural_language_intent", ""),
        model_id=d.get("model_id", ""),
        merge_strategy=MergeStrategy(d.get("merge_strategy", "merge")),
        houdini_version_stamp=d.get("houdini_version_stamp", ""),
        scout_snapshot_id=d.get("scout_snapshot_id", ""),
        scene_fingerprint=d.get("scene_fingerprint", ""),
    )


def synapse_propose_graph(proposal: dict) -> dict:
    if _VALIDATOR is None or _STORE is None:
        raise RuntimeError(
            "synapse_propose_graph not configured — host must call "
            "configure(validator, store) at daemon start"
        )
    p = _proposal_from_dict(proposal)
    report = _VALIDATOR.validate(p)
    if report.status is ValidationStatus.VALID:
        _STORE.put(p)   # only sound proposals are parked for instantiation
    return {
        "status": report.status.value,
        "proposal_id": p.proposal_id,
        "errors": [{"where": e.where, "message": e.message} for e in report.errors],
        "advisories": [{"where": a.where, "message": a.message} for a in report.advisories],
    }
