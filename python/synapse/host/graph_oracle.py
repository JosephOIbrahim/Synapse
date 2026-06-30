"""Implements IConnectivityOracle via hou.* introspection. host/ — hou allowed.

Every hou symbol used here is dir()-confirmed against LIVE Houdini 21.0.671
(Mile-2 §2.5 preflight: harness/notes/verified_connectivity_21.0.671.json,
cross-checked against the committed scout symbol table). The four phantom symbols
the Evaluator quarantines (the pdg module, the secure namespace, the lop-network
accessor, the graph-tick updater) are NOT used here; neither are the type-level
input/output label methods, which 21.0.671 also lacks (labels are instance-only).

Graceful degradation: a false REJECT is cheaper than a false pass (the system has
an imperative fallback) — EXCEPT input_is_occupied, which must HALT rather than
degrade to a false 'free', because its downside is severing the artist's live
wiring.

Read-only by construction: NO method here creates, deletes, or mutates a node.
The connectivity logic (arity, occupied-input, resolve) was exercised read-only
against real node types headless in 21.0.671 (see the §2.5 artifact).

Verification residual: the methods were confirmed under headless hython 21.0.671;
the interactive WS-bridge path calls the identical hou APIs and is owed a live
end-to-end pass once the graphical bridge is restored."""
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
            # 21.0.671: variadic inputs report a large finite cap (merge=9999,
            # add[VOP]=2048), NOT a sentinel — the validator's 'index < max' check
            # handles that natively.
            return (nt.minNumInputs(), nt.maxNumInputs())
        except Exception:  # noqa: BLE001 — degrade to no-inputs (false-reject-safe)
            return (0, 0)

    def input_labels(self, node_type: str, category: str) -> list[str]:
        # Type-level labels are PHANTOM in 21.0.671 (hou.NodeType.inputLabels /
        # .outputLabels are absent — §2.5). Labels exist only on a live instance
        # (hou.Node.inputLabels), which a TYPE oracle has none of, and synthesizing
        # one would mutate the scene. P3c is advisory-only, so no labels => no hint.
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
        # KNOWN GAP, documented deliberately. 21.0.671 exposes VOP wire data types
        # only on COOKED INSTANCES (§2.5: a fresh VopNode reads 'undef'); there is
        # no non-mutating, type-level wire-compatibility surface. The two ways to
        # force a verdict are both wrong here: a blanket False would false-reject
        # EVERY typed edge (unusable), and an instance probe would have to CREATE
        # nodes (a read-only oracle must not mutate). So wire-type enforcement is
        # DEFERRED to Mile-3 build time, where hou.Node.setInput() rejects an
        # incompatible connection natively. Unlike input_is_occupied, a miss here
        # severs nothing — Houdini catches it at build — so we return True (do not
        # block) rather than the usual false-reject-safe default.
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
