"""Implements IConnectivityOracle via hou.* introspection. host/ — hou allowed.

Fill ONLY against §2.5-confirmed symbols (the candidate list is unverified until
dir()-introspected against live H21.0.671). Graceful degradation: a false REJECT
is cheaper than a false pass (an imperative fallback exists) — EXCEPT
input_is_occupied, which HALTS rather than degrades, because its downside is
severing the artist's existing wiring.

Not imported by the Mile-1 cognitive path; filled at the bench in Mile 2."""
from __future__ import annotations

import hou  # noqa: F401 — host layer; never imported by cognitive.*


class ConnectivityOracle:  # implements IConnectivityOracle
    def input_arity(self, node_type: str, category: str) -> tuple[int, int]:
        raise NotImplementedError("Mile 2 — §2.5-confirmed hou introspection")

    def input_labels(self, node_type: str, category: str) -> list[str]:
        raise NotImplementedError("Mile 2 — §2.5-confirmed hou introspection")

    def output_count(self, node_type: str, category: str) -> int:
        raise NotImplementedError("Mile 2 — §2.5-confirmed hou introspection")

    def is_typed_category(self, category: str) -> bool:
        raise NotImplementedError("Mile 2 — §2.5-confirmed hou introspection")

    def types_compatible(self, src_type: str, src_out: int,
                         tgt_type: str, tgt_in: int, category: str) -> bool:
        raise NotImplementedError("Mile 2 — typed categories only (VOP/MAT/CHOP)")

    def input_is_occupied(self, scene_path: str, input_index: int) -> bool:
        raise NotImplementedError("Mile 2 — HALTS, never degrades (P3d)")

    def resolve_node_type(self, scene_path: str) -> tuple[str, str]:
        raise NotImplementedError("Mile 2 — hou.node(scene_path).type(); return (type.name(), type.category().name())")
