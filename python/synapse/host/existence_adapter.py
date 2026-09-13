"""Existence checks through live hou node-type and parameter-template tables.

Bare node-type names need runtime table checks: a documentation match is not an
API-symbol existence verdict. This oracle is host-only; cognitive tools remain
free of hou imports.

GRAPH-TRUTH-BUILD: 22.0.400
GRAPH-TRUTH-BUILD: 22.0.417
Receipts: harness/notes/graph_truth_22.0.400.json and
harness/notes/graph_truth_22.0.417.json.
Each headless receipt records dir() membership of the hou members used here,
positive box/scale and xform/t checks, and negative type/parameter fixtures.
The implementation hash is bound to both observed builds."""
from __future__ import annotations

import hou  # noqa: F401 — host layer; never imported by cognitive.*


class HouExistenceOracle:  # implements IExistenceOracle
    def _nodetype(self, node_type: str, category: str):
        cat = hou.nodeTypeCategories().get(category)
        if cat is None:
            return None
        return hou.nodeType(cat, node_type)   # None when the type is unknown

    def node_type_exists(self, node_type: str, category: str) -> bool:
        return self._nodetype(node_type, category) is not None

    def parameter_exists(self, node_type: str, category: str, parm_name: str) -> bool:
        nt = self._nodetype(node_type, category)
        if nt is None:
            return False
        try:
            return nt.parmTemplateGroup().find(parm_name) is not None
        except Exception:  # noqa: BLE001 — undeterminable => 'does not exist' (false-reject-safe)
            return False
