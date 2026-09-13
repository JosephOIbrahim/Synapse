"""Connectivity checks through live hou introspection. host/ — hou allowed.

The oracle reads node types, input/output capacities, occupancy and live paths.
It creates no nodes. An occupancy read failure propagates so the validator can
refuse an unsafe overwrite.

GRAPH-TRUTH-BUILD: 22.0.400
GRAPH-TRUTH-BUILD: 22.0.417
Receipts: harness/notes/graph_truth_22.0.400.json and
harness/notes/graph_truth_22.0.417.json.
Each headless receipt records dir() membership of the hou members used here and
SOP arity, occupancy and path-resolution observations, bound to an implementation
hash. Type-level labels and typed wire compatibility remain unqualified; the
existing advisory/deferred behavior below is unchanged."""
from __future__ import annotations

import hou  # noqa: F401 — host layer; never imported by cognitive.*

# Categories whose wires carry data types (VOP/CHOP/SHOP; MAT-context nodes are
# Vop/Shop). Used by is_typed_category — a pure category-name decision.
_TYPED_CATEGORIES = frozenset({"Vop", "Chop", "Shop"})


class ConnectivityOracle:  # implements IConnectivityOracle
    # --- internal: (node_type, category) -> hou.NodeType | None (no mutation) ---
    def _nodetype(self, node_type: str, category: str):
        cat = hou.nodeTypeCategories().get(category)
        if cat is None:
            return None
        return hou.nodeType(cat, node_type)   # None when the type is unknown

    def input_arity(self, node_type: str, category: str) -> tuple[int, int]:
        nt = self._nodetype(node_type, category)
        if nt is None:
            # Unknown type: degrade to (0, 0). The validator then rejects any edge
            # into it (false-reject-safe). A truly-missing type is already caught
            # by the existence (P1) phase, so this is a belt-and-suspenders floor.
            return (0, 0)
        try:
            # The H22 receipt observes merge SOP max inputs = 9999. A finite
            # capacity works with the validator's index < max check.
            return (nt.minNumInputs(), nt.maxNumInputs())
        except Exception:  # noqa: BLE001 — degrade to no-inputs (false-reject-safe)
            return (0, 0)

    def input_labels(self, node_type: str, category: str) -> list[str]:
        # This type-only oracle does not consult an instance for labels.
        # P3c is advisory-only, so an empty list supplies no hint. H22 label
        # API availability is not qualified by the G2 receipt.
        return []

    def output_count(self, node_type: str, category: str) -> int:
        nt = self._nodetype(node_type, category)
        if nt is None:
            return 1   # degrade to the overwhelming single-output default
        try:
            return nt.maxNumOutputs()
        except Exception:  # noqa: BLE001
            return 1

    def is_typed_category(self, category: str) -> bool:
        return category in _TYPED_CATEGORIES

    def types_compatible(self, src_type: str, src_out: int,
                         tgt_type: str, tgt_in: int, category: str) -> bool:
        # Known limitation: no wire-data-type measurement is made here.
        # The existing policy defers typed-wire enforcement to build time.
        # Creating probe instances would violate this oracle's read-only role.
        # Typed-wire behavior on H22 remains UNKNOWN in the G2 receipt.
        return True

    def input_is_occupied(self, scene_path: str, input_index: int) -> bool:
        # 3d HALTS, never degrades to a false 'free'. A resolvable node's occupancy
        # is read deterministically from its live input connections. If that read
        # raises, we let it PROPAGATE — the validator's _safe_occupied() catches it
        # and fails safe to OCCUPIED (one fail-safe site, not two).
        node = hou.node(scene_path)
        if node is None:
            # No node => no live wiring to sever. The unresolvable path is reported
            # by P5; returning 'occupied' here would double-report it.
            return False
        return any(c.inputIndex() == input_index for c in node.inputConnections())

    def resolve_node_type(self, scene_path: str) -> tuple[str, str]:
        # (type_name, category_name). Raises on an unresolvable path — the validator
        # (P5 / _endpoint_type) catches that and reports a clean context error.
        node = hou.node(scene_path)
        if node is None:
            raise ValueError(f"path does not resolve in the live scene: {scene_path}")
        nt = node.type()
        return (nt.name(), nt.category().name())
