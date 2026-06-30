"""Graph-synthesis proposal contract. PURE PYTHON — ZERO hou IMPORTS.

The model designs a declarative structural skeleton; this module is the data
shape it emits. Construction mutates nothing. Spec §4 (v3) + amendments 1,3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeKind(str, Enum):
    NEW = "new"
    EXISTING = "existing"


class MergeStrategy(str, Enum):
    MERGE = "merge"                          # add nodes under an existing parent
    REPLACE_CHILDREN = "replace_children"    # clear + rebuild (APPROVE-gated)
    # NB: "new_branch" was removed in v3 (undefined) — do not reintroduce here.


@dataclass
class ProposedNode:
    node_id: str                             # local ref; edges reference this, uniformly
    kind: NodeKind
    node_category: str                       # "Sop" | "Lop" | "Dop" | "Vop" | ...
    node_type: str = ""                      # NEW: type to create. EXISTING: advisory only
    friendly_name: str = ""                  # NEW only; ignored for EXISTING
    parameter_overrides: dict[str, Any] = field(default_factory=dict)  # MUST be empty if EXISTING
    scene_path: str | None = None            # REQUIRED iff kind == EXISTING (absolute live path)
    position: tuple[float, float] | None = None


@dataclass
class ProposedEdge:
    source_node_id: str                      # references a ProposedNode.node_id (new OR existing)
    source_output_index: int
    target_node_id: str
    target_input_index: int
    # Amendment 3: an existing node may be source OR target. Occupied-input guard
    # (P3d) applies to the TARGET side only — outputs fan out freely.


@dataclass
class GraphProposal:
    proposal_id: str
    network_type: str                        # "SOP" | "SOLARIS" | "DOP" | "COP" | "VOP" | "MAT"
    parent_path: str
    nodes: list[ProposedNode]
    edges: list[ProposedEdge]
    natural_language_intent: str
    model_id: str
    merge_strategy: MergeStrategy = MergeStrategy.MERGE
    houdini_version_stamp: str = ""          # secondary drift check (§7)
    scout_snapshot_id: str = ""              # symbol-table version used to ground
    scene_fingerprint: str = ""              # node-graph state hash (§7); set at validate-time


# --- validation result types (also contract; the validator returns these) ---

class ValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


@dataclass
class ValidationIssue:
    where: str                               # node_id, edge repr, or path
    message: str                             # human + model readable


@dataclass
class ValidationReport:
    status: ValidationStatus
    proposal_id: str
    errors: list[ValidationIssue] = field(default_factory=list)      # hard fails — all at once
    advisories: list[ValidationIssue] = field(default_factory=list)  # P3c labels, type-mismatch (Amd 7)
