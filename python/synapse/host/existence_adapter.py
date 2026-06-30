"""IExistenceOracle backing — HOU-BACKED. host/ — hou allowed.

§2.6 PREFLIGHT RESULT (observed + smoke-tested against the live scout this Mile):
``synapse_scout`` returns a STRUCTURED verdict (``symbols[].exists_in_runtime``)
PLUS retrieval ``hits`` — but the structured verdict is built by matching DOTTED
Python API symbols (``hou.*``/``pdg.*``/``pxr.*``). A BARE node-type name (``box``)
is not a dotted symbol, so a node-type query returns an EMPTY ``symbols`` array
and the only fallback signal is documented-presence in the hits. That fallback
was smoke-tested and FALSE-NEGATIVES real types:

    node_type_exists("box","Sop")  -> False   # via the scout doc-presence wrapper

So scout cannot be the authoritative node-type existence oracle.

PIVOT (deliver-and-surface): the IExistenceOracle question — does SOP type ``box``
exist, does it carry parameter ``X`` — IS an ``hou`` question
(``hou.nodeType(category, name)`` / ``NodeType.parmTemplateGroup().find(...)``),
exactly symmetric with graph_oracle.py's hou-backed ConnectivityOracle. This ships
that hou-backed oracle, every symbol dir()-confirmed against LIVE H21.0.671 (probed
this session: hou.nodeType -> box True / frobnicate False; parmTemplateGroup().find
-> 't' True, 'scale' True, 'zzz_nope' False).

SURFACED FOR ARCHITECT RATIFICATION: this is a deviation from the settled
"scout-backed existence" Target — scout proved unable to serve it. The alternative
to a hou-backed oracle is giving scout a real node-type index. Flagging, not
halting (the panel review judged deliver-and-surface cleaner than a loud stub,
since both sanctioned scout heuristics genuinely false-negative real types). Scout
remains the COGNITIVE-layer pre-grounding tool (the model calls it before
proposing); this is the HOST-layer runtime check.

NOT wired into the MCP registry this Mile; the DoD injects a mock existence oracle.
Live end-to-end through the interactive bridge is the owed residual (graph_oracle
shares the same hou surface; both verified read-only this session)."""
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
