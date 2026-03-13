"""
Synapse TOPS/PDG Handler Mixin -- Wedge

Auto-extracted from the monolith handlers_tops.py.
"""

import time
from typing import Any, Dict, List, Optional

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ...core.aliases import resolve_param, resolve_param_with_default
from ...core.determinism import round_float, kahan_sum, deterministic_uuid
from ..handler_helpers import _HOUDINI_UNAVAILABLE
from ._common import _run_in_main_thread_pdg, _ensure_tops_warm_standby, _MAX_MONITOR_EVENTS


class TopsWedgeMixin:
    """Mixin providing TOPS/PDG wedge handlers."""

    def _handle_wedge(self, payload: Dict) -> Dict:
        """Run a TOPs/PDG wedge to explore parameter variations."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        top_path = resolve_param(payload, "node")  # TOP network or wedge node
        wedge_parm = resolve_param(payload, "parm", required=False)
        values = resolve_param(payload, "values", required=False)

        if values is not None and not isinstance(values, list):
            raise ValueError(
                "'values' should be a list (e.g. [0.5, 1.0, 2.0]) -- "
                "wrap your values in square brackets"
            )

        def _run_wedge():
            node = hou.node(top_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {top_path} -- "
                    "double-check the path to your TOP network or wedge node"
                )

            # If it's a TOP network, find or create wedge node
            if node.type().category().name() == "Top":
                # It's already a TOP node -- cook it
                node.cook(block=True)
                return {"node": top_path, "status": "cooked"}
            elif node.type().category().name() == "TopNet":
                # It's a TOP network -- find wedge nodes and cook
                wedge_nodes = [n for n in node.children() if "wedge" in n.type().name().lower()]
                if wedge_nodes:
                    wedge_nodes[0].cook(block=True)
                    return {"node": wedge_nodes[0].path(), "status": "cooked"}
                else:
                    raise ValueError(
                        f"Couldn't find a wedge node inside {top_path} -- "
                        "create a wedge TOP or point to one directly"
                    )
            else:
                raise ValueError(
                    f"The node at {top_path} isn't a TOP network -- "
                    "point to a TOP network or a specific wedge/TOP node"
                )

        result = _run_in_main_thread_pdg(_run_wedge)
        return result

    # =========================================================================
    # TOPS / PDG HANDLERS
    # =========================================================================



    # =========================================================================
    # TOPS / PDG HANDLERS -- Phase 3: Advanced
    # =========================================================================

    def _handle_tops_setup_wedge(self, payload: Dict) -> Dict:
        """Set up a Wedge TOP node for parameter variation exploration.

        Creates a wedge node inside a TOP network and configures its
        attributes (multiparm) for systematic parameter sweeps.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        topnet_path = resolve_param(payload, "topnet_path")
        wedge_name = resolve_param_with_default(payload, "wedge_name", "wedge1")
        attributes = resolve_param(payload, "attributes")

        if not isinstance(attributes, list) or len(attributes) == 0:
            raise ValueError(
                "The 'attributes' parameter should be a list of attribute definitions "
                "(each with name, type, start, end, steps)"
            )

        def _run():
            node = hou.node(topnet_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {topnet_path} -- "
                    "double-check the path exists"
                )

            cat = node.type().category().name()
            if cat not in ("TopNet",):
                raise ValueError(
                    f"The node at {topnet_path} is a {cat} node, not a TOP network -- "
                    "point to a topnet node (e.g. '/obj/topnet1')"
                )

            wedge_node = node.createNode("wedge", wedge_name)
            wedge_node.moveToGoodPosition()

            # Configure wedge attributes via multiparm
            sorted_attrs = sorted(attributes, key=lambda a: a.get("name", ""))
            num_attrs = len(sorted_attrs)
            multiparm = wedge_node.parm("wedgeattributes")
            if multiparm:
                multiparm.set(num_attrs)

            total_variations = 1
            attr_results = []
            for i, attr in enumerate(sorted_attrs):
                idx = i + 1  # 1-indexed multiparm
                attr_name = attr.get("name", f"attr_{i}")
                attr_type = attr.get("type", "float")
                start = attr.get("start", 0)
                end = attr.get("end", 1)
                steps = attr.get("steps", 5)

                # Set wedge attribute parameters
                name_parm = wedge_node.parm(f"name{idx}")
                if name_parm:
                    name_parm.set(attr_name)

                type_parm = wedge_node.parm(f"type{idx}")
                if type_parm:
                    type_map = {"float": 0, "int": 1, "string": 2}
                    type_parm.set(type_map.get(attr_type, 0))

                start_parm = wedge_node.parm(f"range{idx}x")
                if start_parm:
                    start_parm.set(float(start))

                end_parm = wedge_node.parm(f"range{idx}y")
                if end_parm:
                    end_parm.set(float(end))

                steps_parm = wedge_node.parm(f"steps{idx}")
                if steps_parm:
                    steps_parm.set(int(steps))

                total_variations *= int(steps)
                attr_results.append({
                    "name": attr_name,
                    "type": attr_type,
                    "start": round_float(float(start)),
                    "end": round_float(float(end)),
                    "steps": int(steps),
                })

            return {
                "topnet": topnet_path,
                "wedge_node": wedge_node.path(),
                "attributes": attr_results,
                "total_variations": total_variations,
            }

        return _run_in_main_thread_pdg(_run)


