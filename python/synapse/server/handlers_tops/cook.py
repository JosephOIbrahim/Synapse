"""
Synapse TOPS/PDG Handler Mixin -- Cook

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


class TopsCookMixin:
    """Mixin providing TOPS/PDG cook handlers."""

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

            try:
                node.cook(block=bool(blocking))
            except Exception as e:
                logger.error("PDG cook failed for %s: %s", node_path, e)
                return {
                    "node": node_path,
                    "status": "error",
                    "work_items": len(pdg_node.workItems) if pdg_node else 0,
                    "error": str(e),
                }
            item_count = len(pdg_node.workItems)
            return {
                "node": node_path,
                "status": "cooked" if blocking else "cooking",
                "work_items": item_count,
            }

        return _run_in_main_thread_pdg(_run)


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

        return _run_in_main_thread_pdg(_run)

    # =========================================================================
    # TOPS / PDG HANDLERS -- Phase 2: Scheduler & Control
    # =========================================================================



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

        return _run_in_main_thread_pdg(_run)


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
                "note": (
                    "We've sent the cancel signal -- items already in progress "
                    "may finish up before stopping completely."
                ),
            }

        return _run_in_main_thread_pdg(_run)


    def _handle_tops_pause_cook(self, payload: Dict) -> Dict:
        """Pause an active cook on a TOP network.

        Pauses PDG cooking so the artist can inspect intermediate results.
        Work items currently in progress will finish, but no new items start.
        Use tops_resume_cook to continue.
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
            if cat != "TopNet":
                raise ValueError(
                    f"Pause requires a TOP network, but {node_path} is a {cat} -- "
                    "pass the topnet path instead of a single TOP node"
                )

            ctx = node.getPDGGraphContext()
            if ctx is None:
                raise ValueError(
                    f"No PDG context found on {node_path} -- "
                    "it may not have been cooked yet"
                )

            ctx.pauseCook()
            return {
                "node": node_path,
                "status": "paused",
                "note": (
                    "Cook is paused -- items already in progress will finish up. "
                    "Use tops_resume_cook when you're ready to continue."
                ),
            }

        return _run_in_main_thread_pdg(_run)


    def _handle_tops_resume_cook(self, payload: Dict) -> Dict:
        """Resume a paused cook on a TOP network."""
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
            if cat != "TopNet":
                raise ValueError(
                    f"Resume requires a TOP network, but {node_path} is a {cat} -- "
                    "pass the topnet path instead of a single TOP node"
                )

            ctx = node.getPDGGraphContext()
            if ctx is None:
                raise ValueError(
                    f"No PDG context found on {node_path} -- "
                    "it may not have been cooked yet"
                )

            ctx.resumeCook()
            return {
                "node": node_path,
                "status": "resumed",
                "note": "Cook resumed -- pending work items are being scheduled.",
            }

        return _run_in_main_thread_pdg(_run)


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

        return _run_in_main_thread_pdg(_run)

    # =========================================================================
    # TOPS / PDG HANDLERS -- Phase 3: Advanced
    # =========================================================================


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

        return _run_in_main_thread_pdg(_run)


