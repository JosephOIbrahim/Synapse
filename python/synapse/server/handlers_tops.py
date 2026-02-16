"""
Synapse TOPS/PDG Handler Mixin

Extracted from handlers_render.py -- contains wedge and all tops_* handlers
for the SynapseHandler class.
"""

import time
from typing import Dict

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default
from ..core.determinism import round_float, kahan_sum
from .handler_helpers import _HOUDINI_UNAVAILABLE


class TopsHandlerMixin:
    """Mixin providing TOPs/PDG wedge and pipeline handlers."""

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

        result = hdefereval.executeInMainThreadWithResult(_run_wedge)
        return result

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

        return hdefereval.executeInMainThreadWithResult(_run)

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

        return hdefereval.executeInMainThreadWithResult(_run)

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

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_cook_node(self, payload: Dict) -> Dict:
        """Cook a TOP node, optionally generating work items only.

        Supports blocking (wait for cook) and non-blocking (fire-and-forget)
        modes. Use generate_only=True to create work items without cooking.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")
        generate_only = resolve_param_with_default(payload, "generate_only", False)
        blocking = resolve_param_with_default(payload, "blocking", True)
        top_down = resolve_param_with_default(payload, "top_down", True)

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            # Verify it has a PDG node
            pdg_node = node.getPDGNode()
            if pdg_node is None:
                raise ValueError(
                    f"The node at {node_path} isn't a TOP node or hasn't been "
                    "set up for PDG yet -- make sure it's inside a TOP network"
                )

            if generate_only:
                node.generateStaticItems()
                item_count = len(pdg_node.workItems)
                return {
                    "node": node_path,
                    "status": "generated",
                    "work_items": item_count,
                }

            node.cook(block=bool(blocking))
            item_count = len(pdg_node.workItems)
            return {
                "node": node_path,
                "status": "cooked" if blocking else "cooking",
                "work_items": item_count,
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_generate_items(self, payload: Dict) -> Dict:
        """Generate work items for a TOP node without cooking.

        Creates static work items based on the node's configuration.
        Useful for previewing what a node will produce before cooking.
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

            pdg_node = node.getPDGNode()
            if pdg_node is None:
                raise ValueError(
                    f"The node at {node_path} isn't a TOP node or hasn't been "
                    "set up for PDG yet -- make sure it's inside a TOP network"
                )

            node.generateStaticItems()
            item_count = len(pdg_node.workItems)
            return {
                "node": node_path,
                "status": "generated",
                "item_count": item_count,
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    # =========================================================================
    # TOPS / PDG HANDLERS -- Phase 2: Scheduler & Control
    # =========================================================================

    def _handle_tops_configure_scheduler(self, payload: Dict) -> Dict:
        """Configure the scheduler for a TOP network.

        Sets scheduler type, max concurrent processes, and working directory
        on the topnet's scheduler child node.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        topnet_path = resolve_param(payload, "topnet_path")
        scheduler_type = resolve_param_with_default(payload, "scheduler_type", "local")
        max_concurrent = resolve_param(payload, "max_concurrent", required=False)
        working_dir = resolve_param(payload, "working_dir", required=False)

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

            # Find scheduler child node
            scheduler_node = None
            for child in node.children():
                child_type = child.type().name().lower()
                if "scheduler" in child_type or child_type == "localscheduler":
                    scheduler_node = child
                    break

            if scheduler_node is None:
                raise ValueError(
                    f"Couldn't find a scheduler node inside {topnet_path} -- "
                    "make sure the TOP network has a scheduler (e.g. localscheduler)"
                )

            # Configure max concurrent processes
            if max_concurrent is not None:
                menu_parm = scheduler_node.parm("maxprocsmenu")
                if menu_parm:
                    menu_parm.set("custom")
                procs_parm = scheduler_node.parm("maxprocs")
                if procs_parm:
                    procs_parm.set(int(max_concurrent))

            # Configure working directory
            if working_dir is not None:
                wd_parm = scheduler_node.parm("pdg_workingdir")
                if wd_parm:
                    wd_parm.set(str(working_dir))

            result = {
                "topnet": topnet_path,
                "scheduler_node": scheduler_node.path(),
                "scheduler_type": scheduler_type,
                "status": "configured",
            }
            if max_concurrent is not None:
                result["max_concurrent"] = int(max_concurrent)
            if working_dir is not None:
                result["working_dir"] = str(working_dir)
            return result

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_cancel_cook(self, payload: Dict) -> Dict:
        """Cancel an active cook on a TOP node or network.

        For TOP networks: cancels the entire PDG graph context cook.
        For single TOP nodes: dirties the node to stop its cook.
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

            if cat == "TopNet":
                # Cancel the entire PDG graph context
                try:
                    ctx = node.getPDGGraphContext()
                    if ctx is not None:
                        ctx.cancelCook()
                except Exception:
                    # Fallback: dirty all children
                    for child in node.children():
                        pdg_node = child.getPDGNode()
                        if pdg_node is not None:
                            pdg_node.dirty(False)
            else:
                # Single TOP node -- dirty it to stop cooking
                pdg_node = node.getPDGNode()
                if pdg_node is not None:
                    pdg_node.dirty(False)

            return {
                "node": node_path,
                "status": "cancelled",
                "note": "Currently cooking items may finish before cancellation takes effect",
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_dirty_node(self, payload: Dict) -> Dict:
        """Dirty a TOP node, optionally including upstream nodes.

        Dirtying removes cached work item results, forcing a re-cook.
        Use dirty_upstream=True to also dirty all upstream dependencies.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")
        dirty_upstream = resolve_param_with_default(payload, "dirty_upstream", False)

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            pdg_node = node.getPDGNode()
            if pdg_node is not None:
                pdg_node.dirty(bool(dirty_upstream))
            else:
                # Fallback for nodes without PDG node
                try:
                    node.dirtyAllTasks(False)
                except AttributeError:
                    raise ValueError(
                        f"The node at {node_path} isn't a TOP node -- "
                        "make sure it's inside a TOP network"
                    )

            return {
                "node": node_path,
                "status": "dirtied",
                "dirty_upstream": bool(dirty_upstream),
            }

        return hdefereval.executeInMainThreadWithResult(_run)

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

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_batch_cook(self, payload: Dict) -> Dict:
        """Cook multiple TOP nodes in sequence, collecting results.

        Cooks each node in order and collects per-node results including
        status, work item counts, and cook times. Uses kahan_sum for
        stable total cook time aggregation (He2025).
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_paths = resolve_param(payload, "node_paths")
        blocking = resolve_param_with_default(payload, "blocking", True)
        stop_on_error = resolve_param_with_default(payload, "stop_on_error", True)

        if not isinstance(node_paths, list) or len(node_paths) == 0:
            raise ValueError(
                "The 'node_paths' parameter should be a list of TOP node paths"
            )

        def _run():
            results = []
            cook_times = []
            by_state = {}
            errors = []

            for node_path in node_paths:
                node = hou.node(node_path)
                if node is None:
                    err = f"Couldn't find a node at {node_path}"
                    if stop_on_error:
                        raise ValueError(err)
                    results.append({
                        "node": node_path,
                        "status": "error",
                        "error": err,
                        "cook_time": 0.0,
                    })
                    errors.append(node_path)
                    continue

                pdg_node = node.getPDGNode()
                if pdg_node is None:
                    err = f"The node at {node_path} isn't a TOP node"
                    if stop_on_error:
                        raise ValueError(err)
                    results.append({
                        "node": node_path,
                        "status": "error",
                        "error": err,
                        "cook_time": 0.0,
                    })
                    errors.append(node_path)
                    continue

                t0 = time.monotonic()
                try:
                    node.cook(block=bool(blocking))
                    elapsed = time.monotonic() - t0
                    item_count = len(pdg_node.workItems)

                    # Collect per-node state counts
                    node_states = {}
                    for wi in pdg_node.workItems:
                        sname = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                        node_states[sname] = node_states.get(sname, 0) + 1

                    for sname, count in sorted(node_states.items()):
                        by_state[sname] = by_state.get(sname, 0) + count

                    results.append({
                        "node": node_path,
                        "status": "cooked" if blocking else "cooking",
                        "work_items": item_count,
                        "cook_time": round_float(elapsed),
                    })
                    cook_times.append(elapsed)
                except Exception as e:
                    elapsed = time.monotonic() - t0
                    err = str(e)
                    if stop_on_error:
                        raise
                    results.append({
                        "node": node_path,
                        "status": "error",
                        "error": err,
                        "cook_time": round_float(elapsed),
                    })
                    cook_times.append(elapsed)
                    errors.append(node_path)

            total = kahan_sum(cook_times)
            cooked = sum(1 for r in results if r["status"] in ("cooked", "cooking"))
            summary = f"Cooked {cooked}/{len(node_paths)} nodes"
            if errors:
                summary += f", {len(errors)} error(s)"

            return {
                "nodes": results,
                "total_cook_time": round_float(total),
                "by_state": dict(sorted(by_state.items())),
                "summary": summary,
            }

        return hdefereval.executeInMainThreadWithResult(_run)

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

        return hdefereval.executeInMainThreadWithResult(_run)

    # =========================================================================
    # TOPS / PDG HANDLERS -- Phase 4: Autonomous Operations
    # =========================================================================

    def _handle_tops_cook_and_validate(self, payload: Dict) -> Dict:
        """Cook a TOP node with optional retry on failure (Item 15: self-healing).

        Blocking cook -> collect work item states -> if failures AND retries
        remaining -> dirty -> re-cook -> repeat. Returns per-attempt details
        and aggregate stats.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")
        max_retries = resolve_param_with_default(payload, "max_retries", 0)
        validate_states = resolve_param_with_default(payload, "validate_states", True)

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

            attempts = []
            total_elapsed_start = time.monotonic()

            for attempt_num in range(1, int(max_retries) + 2):
                t0 = time.monotonic()
                node.cook(block=True)
                cook_time = time.monotonic() - t0

                # Collect state counts
                by_state = {}
                failed_count = 0
                for wi in pdg_node.workItems:
                    sname = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                    by_state[sname] = by_state.get(sname, 0) + 1
                    if sname == "CookedFail":
                        failed_count += 1

                total_items = sum(by_state.values())
                attempt_info = {
                    "attempt": attempt_num,
                    "cook_time": round_float(cook_time),
                    "work_items": total_items,
                    "by_state": dict(sorted(by_state.items())),
                    "failed_items": failed_count,
                }

                if validate_states and failed_count > 0 and attempt_num <= int(max_retries):
                    attempt_info["status"] = "retry"
                    attempts.append(attempt_info)
                    # Dirty and retry
                    pdg_node.dirty(False)
                    continue
                else:
                    status = "success" if failed_count == 0 else "failed"
                    attempt_info["status"] = status
                    attempts.append(attempt_info)
                    break

            total_elapsed = time.monotonic() - total_elapsed_start
            all_cook_times = [a["cook_time"] for a in attempts]
            final_by_state = attempts[-1]["by_state"]

            return {
                "node": node_path,
                "status": attempts[-1]["status"],
                "attempts": attempts,
                "total_attempts": len(attempts),
                "total_cook_time": kahan_sum(all_cook_times),
                "total_elapsed": round_float(total_elapsed),
                "final_by_state": final_by_state,
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_diagnose(self, payload: Dict) -> Dict:
        """Diagnose failures on a TOP node -- inspect work items, scheduler,
        upstream dependencies, and generate actionable suggestions.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")
        include_scheduler = resolve_param_with_default(payload, "include_scheduler", True)
        include_dependencies = resolve_param_with_default(payload, "include_dependencies", True)

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

            node_type = node.type().name()

            # Collect work item states and details
            by_state = {}
            failed_details = []
            cook_times = []
            for wi in pdg_node.workItems:
                sname = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                by_state[sname] = by_state.get(sname, 0) + 1
                cook_times.append(getattr(wi, 'cookTime', 0.0))
                if sname == "CookedFail":
                    failed_details.append({
                        "id": wi.id,
                        "name": wi.name,
                        "state": sname,
                    })

            total_items = sum(by_state.values())
            total_cook_time = kahan_sum(cook_times)

            result = {
                "node": node_path,
                "node_type": node_type,
                "total_items": total_items,
                "by_state": dict(sorted(by_state.items())),
                "failed_items": len(failed_details),
                "failed_details": sorted(failed_details, key=lambda d: d["id"]),
                "total_cook_time": round_float(total_cook_time),
            }

            # Scheduler info
            if include_scheduler:
                scheduler_info = None
                parent = node.parent()
                if parent is not None:
                    for child in parent.children():
                        child_type = child.type().name().lower()
                        if "scheduler" in child_type or child_type == "localscheduler":
                            sched_info = {
                                "path": child.path(),
                                "type": child.type().name(),
                            }
                            procs_parm = child.parm("maxprocs")
                            if procs_parm is not None:
                                sched_info["max_procs"] = procs_parm.eval()
                            scheduler_info = sched_info
                            break
                result["scheduler"] = scheduler_info

            # Upstream dependency check
            if include_dependencies:
                upstream = []
                for conn in node.inputConnections():
                    inp_node = conn.inputNode()
                    inp_pdg = inp_node.getPDGNode()
                    inp_by_state = {}
                    has_failures = False
                    if inp_pdg is not None:
                        for wi in inp_pdg.workItems:
                            sname = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                            inp_by_state[sname] = inp_by_state.get(sname, 0) + 1
                            if sname == "CookedFail":
                                has_failures = True
                    upstream.append({
                        "path": inp_node.path(),
                        "type": inp_node.type().name(),
                        "by_state": dict(sorted(inp_by_state.items())),
                        "has_failures": has_failures,
                    })
                result["upstream"] = sorted(upstream, key=lambda u: u["path"])

            # Generate suggestions
            suggestions = []
            if len(failed_details) > 0:
                suggestions.append(
                    f"{len(failed_details)} work item(s) failed -- "
                    "check error messages in failed_details"
                )
            if total_items == 0:
                suggestions.append(
                    "No work items found -- the node may need to generate items first"
                )
            if include_dependencies:
                for u in result.get("upstream", []):
                    if u["has_failures"]:
                        suggestions.append(
                            f"Upstream node {u['path']} has failures -- fix upstream first"
                        )
            result["suggestions"] = sorted(suggestions)

            return result

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_pipeline_status(self, payload: Dict) -> Dict:
        """Full health check for a TOP network -- walk all child nodes,
        aggregate work item counts, detect issues, generate suggestions.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        topnet_path = resolve_param(payload, "topnet_path")
        include_items = resolve_param_with_default(payload, "include_items", False)

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

            nodes_info = []
            agg_by_state = {}
            all_cook_times = []
            total_items = 0
            issues = []

            for child in node.children():
                # Skip scheduler nodes
                child_type = child.type().name().lower()
                if "scheduler" in child_type or child_type == "localscheduler":
                    continue

                pdg_child = child.getPDGNode()
                child_by_state = {}
                child_cook_times = []
                child_total = 0
                child_items = []

                if pdg_child is not None:
                    for wi in pdg_child.workItems:
                        sname = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                        child_by_state[sname] = child_by_state.get(sname, 0) + 1
                        child_cook_times.append(getattr(wi, 'cookTime', 0.0))
                        if include_items:
                            child_items.append({
                                "id": wi.id,
                                "name": wi.name,
                                "state": sname,
                            })

                child_total = sum(child_by_state.values())
                child_cook_time = kahan_sum(child_cook_times)

                # Determine per-node health
                failed_count = child_by_state.get("CookedFail", 0)
                if failed_count > 0:
                    health = "error"
                    issues.append(f"{child.path()}: {failed_count} failed work item(s)")
                elif child_total == 0:
                    health = "empty"
                else:
                    health = "healthy"

                node_info = {
                    "path": child.path(),
                    "name": child.name(),
                    "type": child.type().name(),
                    "health": health,
                    "by_state": dict(sorted(child_by_state.items())),
                    "total_items": child_total,
                    "cook_time": round_float(child_cook_time),
                }
                if include_items and child_items:
                    node_info["items"] = child_items

                nodes_info.append(node_info)

                # Aggregate
                total_items += child_total
                all_cook_times.append(child_cook_time)
                for sname, count in sorted(child_by_state.items()):
                    agg_by_state[sname] = agg_by_state.get(sname, 0) + count

            # Overall health
            total_failed = agg_by_state.get("CookedFail", 0)
            if total_failed > 0:
                overall_health = "error"
            elif total_items == 0:
                overall_health = "empty"
            else:
                overall_health = "healthy"

            # Suggestions
            suggestions = []
            if total_failed > 0:
                suggestions.append(
                    f"{total_failed} total failed work item(s) -- "
                    "use tops_diagnose for details"
                )
            if total_items == 0:
                suggestions.append(
                    "No work items in the network -- "
                    "nodes may need to generate or cook first"
                )

            return {
                "topnet": topnet_path,
                "overall_health": overall_health,
                "node_count": len(nodes_info),
                "total_items": total_items,
                "by_state": dict(sorted(agg_by_state.items())),
                "total_cook_time": kahan_sum(all_cook_times),
                "nodes": sorted(nodes_info, key=lambda n: n["path"]),
                "issues": sorted(issues),
                "suggestions": sorted(suggestions),
            }

        return hdefereval.executeInMainThreadWithResult(_run)
