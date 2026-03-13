"""
Synapse TOPS/PDG Handler Mixin -- Work Items

Auto-extracted from the monolith handlers_tops.py.
"""

import time
import re
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


class TopsWorkItemsMixin:
    """Mixin providing TOPS/PDG work items handlers."""


    # =========================================================================
    # TOPS / PDG HANDLERS
    # =========================================================================

    def _handle_tops_get_work_items(self, payload: Dict) -> Dict:
        """Get work items from a TOP node with optional state filtering.

        Returns work item details including id, index, name, state, cook time,
        and optionally attributes. Useful for inspecting what a TOP node produced.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")
        state_filter = resolve_param_with_default(payload, "state_filter", "all")
        include_attrs = resolve_param_with_default(payload, "include_attributes", True)
        limit = resolve_param_with_default(payload, "limit", 100)

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            pdg_node = node.getPDGNode()
            if pdg_node is None:
                raise ValueError(
                    f"The node at {node_path} isn't a TOP node or hasn't been "
                    "set up for PDG yet -- make sure it's inside a TOP network"
                )

            # Map state names to pdg.workItemState values
            import pdg as _pdg
            state_map = {
                "cooked": _pdg.workItemState.CookedSuccess,
                "failed": _pdg.workItemState.CookedFail,
                "cooking": _pdg.workItemState.Cooking,
                "scheduled": _pdg.workItemState.Scheduled,
                "uncooked": _pdg.workItemState.Uncooked,
                "cancelled": _pdg.workItemState.CookedCancel,
            }

            all_items = pdg_node.workItems
            items = []
            for wi in all_items:
                # Apply state filter
                if state_filter != "all":
                    expected_state = state_map.get(state_filter.lower())
                    if expected_state is not None and wi.state != expected_state:
                        continue

                item = {
                    "id": wi.id,
                    "index": wi.index,
                    "name": wi.name,
                    "state": wi.state.name if hasattr(wi.state, 'name') else str(wi.state),
                    "cook_time": round_float(getattr(wi, 'cookTime', 0.0)),
                }

                if include_attrs:
                    attrs = {}
                    try:
                        for attr in wi.attribs:
                            try:
                                attrs[attr.name] = attr.values()
                            except Exception:
                                attrs[attr.name] = str(attr)
                    except Exception:
                        pass
                    item["attributes"] = attrs

                items.append(item)
                if len(items) >= int(limit):
                    break

            return {
                "node": node_path,
                "total_items": len(all_items),
                "returned": len(items),
                "filter": state_filter,
                "items": items,
            }

        return _run_in_main_thread_pdg(_run)


    def _handle_tops_get_dependency_graph(self, payload: Dict) -> Dict:
        """Get the dependency graph for a TOP network.

        Returns nodes with their types, work item counts by state, and
        edges representing connections between TOP nodes.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        topnet_path = resolve_param(payload, "topnet_path")
        depth = resolve_param_with_default(payload, "depth", -1)

        def _run():
            node = hou.node(topnet_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {topnet_path} -- "
                    "double-check the path exists"
                )

            # Verify it's a TOP network
            cat = node.type().category().name()
            if cat not in ("TopNet", "Top"):
                raise ValueError(
                    f"The node at {topnet_path} is a {cat} node, not a TOP network -- "
                    "point to a topnet node (e.g. '/obj/topnet1')"
                )

            children = node.children()
            nodes = []
            edges = []

            for child in children:
                node_info = {
                    "name": child.name(),
                    "path": child.path(),
                    "type": child.type().name(),
                }

                # Get work item counts by state if PDG node exists
                pdg_node = child.getPDGNode()
                if pdg_node is not None:
                    by_state = {}
                    for wi in pdg_node.workItems:
                        state_name = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                        by_state[state_name] = by_state.get(state_name, 0) + 1
                    node_info["work_items"] = dict(sorted(by_state.items()))
                    node_info["total_items"] = sum(by_state.values())
                else:
                    node_info["work_items"] = {}
                    node_info["total_items"] = 0

                nodes.append(node_info)

                # Build edges from input connections
                for conn in child.inputConnections():
                    edges.append({
                        "from": conn.inputNode().path(),
                        "to": child.path(),
                        "input_index": conn.inputIndex(),
                        "output_index": conn.outputIndex(),
                    })

            return {
                "topnet": topnet_path,
                "node_count": len(nodes),
                "nodes": nodes,
                "edges": edges,
            }

        return _run_in_main_thread_pdg(_run)


    def _handle_tops_get_cook_stats(self, payload: Dict) -> Dict:
        """Get cook statistics for a TOP node or network.

        For a single TOP node: work item counts by state and total cook time.
        For a TOP network: aggregate stats across all child nodes.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            cat = node.type().category().name()

            def _node_stats(n):
                """Get stats for a single TOP node."""
                pdg_node = n.getPDGNode()
                if pdg_node is None:
                    return {"name": n.name(), "path": n.path(), "by_state": {}, "total_items": 0, "cook_time": 0.0}
                by_state = {}
                cook_times = []
                for wi in pdg_node.workItems:
                    state_name = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                    by_state[state_name] = by_state.get(state_name, 0) + 1
                    cook_times.append(getattr(wi, 'cookTime', 0.0))
                return {
                    "name": n.name(),
                    "path": n.path(),
                    "by_state": dict(sorted(by_state.items())),
                    "total_items": sum(by_state.values()),
                    "cook_time": kahan_sum(cook_times),
                }

            if cat == "TopNet":
                # Aggregate over children
                node_stats = []
                agg_by_state = {}
                cook_times = []
                total_items = 0
                for child in node.children():
                    s = _node_stats(child)
                    node_stats.append(s)
                    cook_times.append(s["cook_time"])
                    total_items += s["total_items"]
                    for state, count in sorted(s["by_state"].items()):
                        agg_by_state[state] = agg_by_state.get(state, 0) + count
                return {
                    "node": node_path,
                    "is_network": True,
                    "total_items": total_items,
                    "by_state": dict(sorted(agg_by_state.items())),
                    "total_cook_time": kahan_sum(cook_times),
                    "nodes": node_stats,
                }
            else:
                s = _node_stats(node)
                return {
                    "node": node_path,
                    "is_network": False,
                    "total_items": s["total_items"],
                    "by_state": s["by_state"],  # already sorted by _node_stats
                    "total_cook_time": s["cook_time"],
                    "nodes": [s],
                }

        return _run_in_main_thread_pdg(_run)


    def _handle_tops_query_items(self, payload: Dict) -> Dict:
        """Query work items by attribute value with filter operators.

        Searches work items on a TOP node for those matching a condition
        on a specific attribute. Supports eq, gt, lt, gte, lte, contains,
        and regex operators.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval
        import re

        node_path = resolve_param(payload, "node")
        attr_name = resolve_param(payload, "query_attribute")
        filter_op = resolve_param_with_default(payload, "filter_op", "eq")
        filter_value = resolve_param(payload, "filter_value")

        valid_ops = ("eq", "gt", "lt", "gte", "lte", "contains", "regex")
        if filter_op not in valid_ops:
            raise ValueError(
                f"Unknown filter operator '{filter_op}'. "
                f"Available: {', '.join(valid_ops)}"
            )

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            pdg_node = node.getPDGNode()
            if pdg_node is None:
                raise ValueError(
                    f"The node at {node_path} isn't a TOP node or hasn't been "
                    "set up for PDG yet"
                )

            all_items = pdg_node.workItems
            matched = []

            for wi in all_items:
                # Find the attribute
                attr_val = None
                for attr in getattr(wi, 'attribs', []):
                    if attr.name == attr_name:
                        vals = attr.values()
                        attr_val = vals[0] if len(vals) == 1 else vals
                        break

                if attr_val is None:
                    continue

                # Apply filter
                try:
                    if filter_op == "eq" and attr_val == filter_value:
                        pass
                    elif filter_op == "gt" and float(attr_val) > float(filter_value):
                        pass
                    elif filter_op == "lt" and float(attr_val) < float(filter_value):
                        pass
                    elif filter_op == "gte" and float(attr_val) >= float(filter_value):
                        pass
                    elif filter_op == "lte" and float(attr_val) <= float(filter_value):
                        pass
                    elif filter_op == "contains" and str(filter_value) in str(attr_val):
                        pass
                    elif filter_op == "regex" and re.search(str(filter_value), str(attr_val)):
                        pass
                    else:
                        continue
                except (TypeError, ValueError):
                    continue

                # Round float values in output (He2025)
                display_val = round_float(attr_val) if isinstance(attr_val, float) else attr_val

                matched.append({
                    "id": wi.id,
                    "name": wi.name,
                    "state": wi.state.name if hasattr(wi.state, 'name') else str(wi.state),
                    "attribute_value": display_val,
                })

            return {
                "node": node_path,
                "attribute": attr_name,
                "operator": filter_op,
                "value": filter_value,
                "matched_count": len(matched),
                "total_count": len(all_items),
                "items": matched,
            }

        return _run_in_main_thread_pdg(_run)

    # =========================================================================
    # TOPS / PDG HANDLERS -- Phase 4: Autonomous Operations
    # =========================================================================


