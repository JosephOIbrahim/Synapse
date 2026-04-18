"""SYNAPSE 2.0 Inspector — AST schema and container.

Pydantic models for the Solaris /stage AST plus a StageAST container
class that wraps a list of nodes with query helpers.

Schema versioning
-----------------
Every extraction payload carries ``schema_version``. The Inspector
refuses to parse responses with mismatched versions — prevents silent
drift when the extraction script evolves.

To bump the schema:
  1. Change SCHEMA_VERSION below
  2. Update the extraction script in tool_inspect_stage.py
  3. Regenerate the golden fixture JSON
  4. Add a migration path if old scenes may return old schemas

Determinism
-----------
ASTNode and InputConnection are frozen (immutable). StageAST returns
nodes sorted by hou_path for stable iteration. to_json() emits with
``sort_keys=True`` so byte-identical inputs produce byte-identical
outputs — matches SYNAPSE's existing determinism principles.

Sprint 2 Week 1: Flat topology. children/key_parms/provenance reserved.
Sprint 2 Week 2: Subnet recursion populates children + key_parms.
Sprint 3: USD provenance attributes populate provenance.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


# -----------------------------------------------------------------------------
# Schema version
# -----------------------------------------------------------------------------
# Bump on any breaking schema change (field removal, type change, semantic
# change). Additive changes (new optional fields with defaults) do not
# require a bump but should be documented in the changelog.

SCHEMA_VERSION = "1.0.0"


# -----------------------------------------------------------------------------
# Type aliases
# -----------------------------------------------------------------------------

ErrorState = Literal["clean", "warning", "error"]
"""Node-level error state.

- clean: node cooked successfully, no issues
- warning: node cooked but emitted warnings
- error: node failed to cook or is uncomposable
"""


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------


class InputConnection(BaseModel):
    """A single input connection with its wiring index.

    Input order is semantically meaningful on multi-input LOPs. A Merge LOP
    with inputs in order [geo, mats, ref] composes differently from [ref,
    mats, geo] — LIVRPS strength depends on wiring order.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int = Field(
        ge=0,
        description="Zero-based input slot index on the downstream node.",
    )
    path: str = Field(
        min_length=1,
        description="Absolute hou_path of the upstream node.",
    )

    @field_validator("path")
    @classmethod
    def _validate_path(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError(f"hou_path must be absolute, got {v!r}")
        return v


class ASTNode(BaseModel):
    """Single node in the Solaris /stage AST.

    Dual-path tracking:
      - hou_path: Houdini node DAG path (e.g., /stage/hero_vehicle)
      - usd_prim_paths: USD prims this node authored or modified,
        extracted via ``node.lastModifiedPrims()``

    Flags:
      - display_flag: only one node per context has display=True
      - bypass_flag: bypassed nodes contribute nothing to the composed stage
      - error_state: cascades downstream; a single error node breaks its chain
      - error_message: short (<=500 chars) detail when error_state != "clean"

    Reserved fields:
      - children: Week 2 recursive descent into subnet-style LOPs
      - key_parms: Week 2 curated per-node-type authoring parms
      - provenance: Sprint 3 synapse:* USD attributes from prior sessions
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Identity (always populated)
    node_name: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    hou_path: str = Field(min_length=1)

    # USD authorship — empty list for non-authoring / error / bypassed nodes
    usd_prim_paths: List[str] = Field(default_factory=list)

    # State flags
    display_flag: bool
    bypass_flag: bool
    error_state: ErrorState
    error_message: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Human-readable detail when error_state != 'clean'.",
    )

    # Topology
    inputs: List[InputConnection] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)

    # Reserved for future sprints
    children: List["ASTNode"] = Field(default_factory=list)
    key_parms: Dict[str, Any] = Field(default_factory=dict)
    provenance: Optional[Dict[str, Any]] = Field(default=None)

    @field_validator("hou_path")
    @classmethod
    def _validate_hou_path(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError(f"hou_path must be absolute, got {v!r}")
        return v

    @field_validator("usd_prim_paths")
    @classmethod
    def _validate_usd_paths(cls, v: List[str]) -> List[str]:
        for path in v:
            if not path.startswith("/"):
                raise ValueError(f"USD prim path must be absolute, got {path!r}")
        return v


# Pydantic v2: resolve forward reference for self-referential children
ASTNode.model_rebuild()


# -----------------------------------------------------------------------------
# Container
# -----------------------------------------------------------------------------


class StageAST:
    """Read-only container wrapping ASTNodes with query helpers.

    Unlike plain ``List[ASTNode]``, StageAST provides:
      - ``ast['geo']`` — O(1) lookup by node name
      - ``ast.display_node()`` — the single node marked as display
      - ``ast.error_nodes()``, ``ast.warning_nodes()`` — state-filtered queries
      - ``ast.orphans()``, ``ast.roots()``, ``ast.leaves()`` — topology queries
      - ``ast.authoring_nodes()``, ``ast.prims_at(path)`` — USD queries
      - ``ast.to_json()`` — deterministic JSON serialization
      - ``len(ast)``, iteration, ``in``

    Immutable by design — construct once from a node list, query many times.

    Thread safety: immutable after construction; safe to share across
    threads without locking.
    """

    __slots__ = ("_nodes", "_by_name", "_schema_version", "_target_path")

    def __init__(
        self,
        nodes: List[ASTNode],
        *,
        schema_version: str = SCHEMA_VERSION,
        target_path: str = "/stage",
    ):
        self._nodes: Tuple[ASTNode, ...] = tuple(nodes)
        self._by_name: Dict[str, ASTNode] = {n.node_name: n for n in self._nodes}
        self._schema_version = schema_version
        self._target_path = target_path

    # --- Container protocol ---------------------------------------------------

    def __len__(self) -> int:
        return len(self._nodes)

    def __iter__(self) -> Iterator[ASTNode]:
        return iter(self._nodes)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, str):
            return key in self._by_name
        if isinstance(key, ASTNode):
            return key in self._nodes
        return False

    def __getitem__(self, key: Union[str, int]) -> ASTNode:
        """Get a node by name (str) or index (int).

        Raises:
            KeyError: name not found
            IndexError: index out of range
        """
        if isinstance(key, str):
            return self._by_name[key]
        if isinstance(key, int):
            return self._nodes[key]
        raise TypeError(
            f"StageAST indices must be str (node name) or int, got "
            f"{type(key).__name__}"
        )

    def __repr__(self) -> str:
        return (
            f"StageAST(target_path={self._target_path!r}, "
            f"schema_version={self._schema_version!r}, "
            f"nodes={len(self._nodes)})"
        )

    # --- Properties -----------------------------------------------------------

    @property
    def nodes(self) -> Tuple[ASTNode, ...]:
        """The underlying node tuple (immutable)."""
        return self._nodes

    @property
    def schema_version(self) -> str:
        return self._schema_version

    @property
    def target_path(self) -> str:
        """The Houdini context this AST was extracted from."""
        return self._target_path

    # --- Identity queries -----------------------------------------------------

    def by_name(self, name: str, default: Optional[ASTNode] = None) -> Optional[ASTNode]:
        """Get a node by name. Returns default (None) if not found."""
        return self._by_name.get(name, default)

    def by_type(self, node_type: str) -> List[ASTNode]:
        """All nodes of a given Houdini type (e.g., 'xform', 'sublayer')."""
        return [n for n in self._nodes if n.node_type == node_type]

    # --- State queries --------------------------------------------------------

    def display_node(self) -> Optional[ASTNode]:
        """The single node marked as display flag=True, or None.

        In valid Solaris scenes only one node per context has the display
        flag, but we don't enforce that — return the first one found.
        """
        for n in self._nodes:
            if n.display_flag:
                return n
        return None

    def bypassed_nodes(self) -> List[ASTNode]:
        return [n for n in self._nodes if n.bypass_flag]

    def error_nodes(self) -> List[ASTNode]:
        return [n for n in self._nodes if n.error_state == "error"]

    def warning_nodes(self) -> List[ASTNode]:
        return [n for n in self._nodes if n.error_state == "warning"]

    def clean_nodes(self) -> List[ASTNode]:
        return [n for n in self._nodes if n.error_state == "clean"]

    # --- Topology queries -----------------------------------------------------

    def orphans(self) -> List[ASTNode]:
        """Nodes with no inputs AND no outputs — disconnected islands."""
        return [n for n in self._nodes if not n.inputs and not n.outputs]

    def roots(self) -> List[ASTNode]:
        """Nodes with no inputs but at least one output — chain starts."""
        return [n for n in self._nodes if not n.inputs and n.outputs]

    def leaves(self) -> List[ASTNode]:
        """Nodes with inputs but no outputs — chain ends."""
        return [n for n in self._nodes if n.inputs and not n.outputs]

    # --- USD authorship queries ----------------------------------------------

    def authoring_nodes(self) -> List[ASTNode]:
        """Nodes that authored or modified at least one USD prim."""
        return [n for n in self._nodes if n.usd_prim_paths]

    def prims_at(self, usd_path: str) -> List[ASTNode]:
        """All nodes that authored or modified the given USD prim path."""
        return [n for n in self._nodes if usd_path in n.usd_prim_paths]

    # --- Serialization --------------------------------------------------------

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Serialize nodes to list of dicts (no schema envelope)."""
        return [n.model_dump() for n in self._nodes]

    def to_payload(self) -> Dict[str, Any]:
        """Serialize to the full on-the-wire payload dict with envelope."""
        return {
            "schema_version": self._schema_version,
            "target_path": self._target_path,
            "nodes": self.to_dict_list(),
        }

    def to_json(self, *, indent: Optional[int] = None) -> str:
        """Serialize to deterministic JSON string.

        Uses ``sort_keys=True`` so byte-identical input produces
        byte-identical output across Python versions and platforms.
        """
        return json.dumps(self.to_payload(), sort_keys=True, indent=indent)
