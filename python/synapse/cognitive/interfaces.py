"""Protocols the cognitive layer depends on. Host implements the oracles; cognitive stays pure.
Spec §5.3 + amendments 1,2; the tool-provider seam is D-H22-1. ZERO hou IMPORTS (Protocols only)."""
from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


class IExistenceOracle(Protocol):
    """Symbol/parameter existence against the live runtime (scout-backed).
    Real surface confirmed by §2.6 preflight; mockable for Mile 1."""

    def node_type_exists(self, node_type: str, category: str) -> bool: ...
    def parameter_exists(self, node_type: str, category: str, parm_name: str) -> bool: ...


class IConnectivityOracle(Protocol):
    """Live node-type introspection. Host-implemented (hou.*).
    Confirm every backing symbol via §2.5 preflight before host fills it."""

    def input_arity(self, node_type: str, category: str) -> tuple[int, int]: ...     # (min, max); max may be variadic sentinel
    def input_labels(self, node_type: str, category: str) -> list[str]: ...
    def output_count(self, node_type: str, category: str) -> int: ...
    def is_typed_category(self, category: str) -> bool: ...                          # True: VOP/MAT/CHOP
    def types_compatible(self, src_type: str, src_out: int,
                         tgt_type: str, tgt_in: int, category: str) -> bool: ...     # typed categories only
    def input_is_occupied(self, scene_path: str, input_index: int) -> bool: ...      # existing-node target (P3d)
    def resolve_node_type(self, scene_path: str) -> tuple[str, str]: ...             # (type_name, category_name); Amendment 1


# ── D-H22-1 · the tool-provider seam ─────────────────────────────────────────
# Typed from the OBSERVED shape of ApexMCPProvider (providers/apex_mcp.py:53),
# which satisfies IToolProvider unmodified. ToolDef/Envelope are the plain dicts
# the provider already returns (not new classes) — adopted as aliases so the
# contract documents the shape without forcing any change on the provider.

ToolDef = dict[str, Any]      # one tool: {"name": str, "input_schema": ...}         apex_mcp.py:74
Envelope = dict[str, Any]     # {"observed","source","tool","args_digest","ts",...}  apex_mcp.py:89


@runtime_checkable
class IToolProvider(Protocol):
    """A source of tools — native handlers and foreign MCPs alike (D-H22-1).

    Written down, not invented: ApexMCPProvider already honours this contract
    (``id`` :56, ``list_tools`` :73, ``call_tool`` :81). ``@runtime_checkable``
    lets the contract test assert conformance at runtime. ZERO hou."""

    id: str

    def list_tools(self) -> list[ToolDef]: ...

    def call_tool(self, name: str, args: Optional[dict] = None) -> Envelope: ...
