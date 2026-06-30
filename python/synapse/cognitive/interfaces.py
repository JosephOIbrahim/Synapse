"""Protocols the validator depends on. Host implements them; cognitive stays pure.
Spec §5.3 + amendments 1,2. ZERO hou IMPORTS (Protocols only)."""
from __future__ import annotations

from typing import Protocol


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
