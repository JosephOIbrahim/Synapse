"""
Synapse TOPS/PDG Handler Mixin -- Diagnostics

Auto-extracted from the monolith handlers_tops.py.
"""

import time
import os
import threading
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


class TopsDiagnosticsMixin:
    """Mixin providing TOPS/PDG diagnostics handlers."""


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

        return _run_in_main_thread_pdg(_run)


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

        return _run_in_main_thread_pdg(_run)


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

        return _run_in_main_thread_pdg(_run)

    # =========================================================================
    # TOPS / PDG HANDLERS -- Phase 5: Streaming & Render Integration
    # =========================================================================



    # =========================================================================
    # TOPS / PDG HANDLERS -- Phase 5: Streaming & Render Integration
    # =========================================================================

    def _handle_tops_monitor_stream(self, payload: Dict) -> Dict:
        """Start or stop event-driven monitoring of TOPS cook progress.

        Push-based alternative to polling: registers PDG event callbacks that
        emit work_item_started, work_item_completed, work_item_failed,
        cook_progress, and cook_complete events.

        The callback does NOT block the TOPS cook thread -- events are
        enqueued and can be retrieved via the returned monitor_id.

        Args (in payload):
            node: TOP node or network path to monitor.
            action: 'start' to begin monitoring, 'stop' to end it.
            monitor_id: Required for 'stop' -- the ID returned by 'start'.

        Returns:
            On start: monitor_id and status.
            On stop: final stats and collected events summary.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")
        action = resolve_param_with_default(payload, "action", "start")
        monitor_id = resolve_param(payload, "monitor_id", required=False)

        if action not in ("start", "stop", "status"):
            raise ValueError(
                f"Unknown action '{action}' -- use 'start', 'stop', or 'status'"
            )

        # Instance-level monitor storage
        if not hasattr(self, "_tops_monitors"):
            self._tops_monitors: Dict[str, Dict[str, Any]] = {}

        if action == "stop":
            if not monitor_id:
                raise ValueError(
                    "Couldn't find monitor -- "
                    "please provide the monitor_id returned when you started monitoring"
                )
            monitor = self._tops_monitors.pop(monitor_id, None)
            if monitor is None:
                raise ValueError(
                    f"Couldn't find monitor '{monitor_id}' -- "
                    "it may have already been stopped"
                )

            # Unregister callback in main thread
            def _stop():
                callback_id = monitor.get("callback_id")
                pdg_node = monitor.get("pdg_node")
                if callback_id is not None and pdg_node is not None:
                    try:
                        import pdg as _pdg
                        ctx = pdg_node.context
                        if ctx is not None:
                            ctx.removeEventHandler(callback_id)
                    except Exception:
                        pass  # Best-effort cleanup

                events = monitor.get("events", [])
                elapsed = time.monotonic() - monitor.get("start_time", time.monotonic())

                # Build summary from collected events
                completed = sum(1 for e in events if e.get("type") == "work_item_completed")
                failed = sum(1 for e in events if e.get("type") == "work_item_failed")
                total = completed + failed

                result = {
                    "monitor_id": monitor_id,
                    "status": "stopped",
                    "elapsed_seconds": round_float(elapsed),
                    "events_collected": len(events),
                    "summary": {
                        "completed": completed,
                        "failed": failed,
                        "total_processed": total,
                    },
                }
                if monitor.get("was_truncated"):
                    result["events_truncated"] = True
                    result["events_truncated_note"] = (
                        f"Event buffer exceeded {_MAX_MONITOR_EVENTS} — oldest "
                        "events were dropped. Increase SYNAPSE_MONITOR_EVENT_CAP "
                        "or reduce cook complexity."
                    )
                return result

            return _run_in_main_thread_pdg(_stop)

        if action == "status":
            if not monitor_id or monitor_id not in self._tops_monitors:
                raise ValueError(
                    f"Couldn't find monitor '{monitor_id}' -- "
                    "check the monitor_id returned when you started monitoring"
                )

            monitor = self._tops_monitors[monitor_id]
            events = monitor.get("events", [])
            elapsed = time.monotonic() - monitor.get("start_time", time.monotonic())
            completed = sum(1 for e in events if e.get("type") == "work_item_completed")
            failed = sum(1 for e in events if e.get("type") == "work_item_failed")

            return {
                "monitor_id": monitor_id,
                "status": "active",
                "elapsed_seconds": round_float(elapsed),
                "events_collected": len(events),
                "latest_events": events[-10:] if events else [],
                "summary": {
                    "completed": completed,
                    "failed": failed,
                    "total_processed": completed + failed,
                },
            }

        # action == "start"
        def _start():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            # Warm standby: ensure scheduler exists
            parent = node.parent()
            if parent is not None:
                topnet = parent if parent.type().category().name() == "TopNet" else node
                _ensure_tops_warm_standby(topnet.path())

            pdg_node = node.getPDGNode()
            if pdg_node is None:
                raise ValueError(
                    f"The node at {node_path} isn't a TOP node or hasn't been "
                    "set up for PDG yet -- make sure it's inside a TOP network"
                )

            import pdg as _pdg

            mid = f"monitor-{deterministic_uuid(f'tops_monitor_{node_path}')[:8]}"
            events_list: List[Dict] = []
            start_time = time.monotonic()
            total_items = [0]  # mutable for closure

            def _on_event(event):
                """PDG event callback -- must not block the cook thread."""
                try:
                    # Cap event list to prevent unbounded memory growth.
                    # Keep the last 80% to avoid trimming on every single event.
                    if len(events_list) > _MAX_MONITOR_EVENTS:
                        events_list[:] = events_list[-(int(_MAX_MONITOR_EVENTS * 0.8)):]
                        monitor["was_truncated"] = True

                    etype = event.type
                    now = time.monotonic()
                    elapsed = now - start_time

                    if etype == _pdg.EventType.WorkItemStateChange:
                        wi = event.workItem
                        if wi is None:
                            return
                        state = wi.state
                        item_info = {
                            "item_id": wi.id,
                            "node": event.node.name if event.node else node_path,
                            "frame": getattr(wi, 'frame', None),
                            "timestamp": round_float(elapsed),
                        }

                        if state == _pdg.workItemState.Cooking:
                            item_info["type"] = "work_item_started"
                            events_list.append(item_info)

                        elif state == _pdg.workItemState.CookedSuccess:
                            item_info["type"] = "work_item_completed"
                            item_info["duration_seconds"] = round_float(
                                getattr(wi, 'cookTime', 0.0)
                            )
                            # Try to get output path from result data
                            try:
                                outputs = wi.resultData
                                if outputs:
                                    item_info["output_path"] = str(outputs[0]) if outputs else ""
                            except Exception:
                                pass
                            events_list.append(item_info)

                        elif state == _pdg.workItemState.CookedFail:
                            item_info["type"] = "work_item_failed"
                            item_info["error_message"] = getattr(wi, 'lastError', "Unknown error")
                            events_list.append(item_info)

                    elif etype == _pdg.EventType.CookProgress:
                        completed = getattr(event, 'completedCount', 0)
                        total = getattr(event, 'totalCount', 0)
                        total_items[0] = total
                        pct = round_float((completed / total * 100.0) if total > 0 else 0.0)
                        events_list.append({
                            "type": "cook_progress",
                            "completed": completed,
                            "total": total,
                            "percent": pct,
                            "timestamp": round_float(elapsed),
                        })

                    elif etype == _pdg.EventType.CookComplete:
                        events_list.append({
                            "type": "cook_complete",
                            "total_time_seconds": round_float(elapsed),
                            "results_summary": {
                                "total_events": len(events_list),
                            },
                            "timestamp": round_float(elapsed),
                        })

                except Exception:
                    pass  # Never block the cook thread

            # Register callback on the PDG graph context
            ctx = pdg_node.context
            callback_id = None
            if ctx is not None:
                try:
                    callback_id = ctx.addEventHandler(
                        _on_event,
                        _pdg.EventType.WorkItemStateChange
                        | _pdg.EventType.CookProgress
                        | _pdg.EventType.CookComplete,
                    )
                except Exception:
                    # Fallback: some PDG versions use different API
                    pass

            try:
                self._tops_monitors[mid] = {
                    "node_path": node_path,
                    "pdg_node": pdg_node,
                    "callback_id": callback_id,
                    "events": events_list,
                    "start_time": start_time,
                }
            except Exception:
                # If storage fails, unregister the callback to prevent leak
                if callback_id is not None and ctx is not None:
                    try:
                        ctx.removeEventHandler(callback_id)
                    except Exception:
                        pass
                raise

            return {
                "monitor_id": mid,
                "node": node_path,
                "status": "monitoring",
                "note": "Use tops_monitor_stream with action='status' to check events, "
                        "or action='stop' to end monitoring and get results",
            }

        return _run_in_main_thread_pdg(_start)


