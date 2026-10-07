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
from ._common import _run_in_main_thread_pdg, _ensure_tops_warm_standby, _MAX_MONITOR_EVENTS, logger


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
                node.cookWorkItems(block=True)
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
        emit work_item_started, work_item_completed (``cached`` when served
        from cache), work_item_failed, work_item_cancelled, cook_progress,
        cook_complete and cook_error events. ``cook_state`` reads cooking,
        complete, complete_with_errors or error.

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

        def _summary(monitor):
            # Running counters over the monitor's whole life, never recomputed
            # from the event buffer: the buffer is trimmed past
            # _MAX_MONITOR_EVENTS and would undercount.
            with monitor["lock"]:
                c = dict(monitor["counts"])
            return {
                "completed": c["completed"],
                "cached": c["cached"],
                "failed": c["failed"],
                "cancelled": c["cancelled"],
                "total_processed": c["completed"] + c["cached"] + c["failed"] + c["cancelled"],
            }

        def _report_flags(monitor, result):
            with monitor["lock"]:
                cook_state = monitor.get("cook_state")
                cook = dict(monitor["cook_counts"])
                truncated = monitor.get("was_truncated")
                callback_error = monitor.get("callback_error")
            if cook_state:
                result["cook_state"] = cook_state
                # The most recent cook on its own; "summary" spans every cook
                # since start.
                result["last_cook"] = cook
            if truncated:
                result["events_truncated"] = True
                result["events_truncated_note"] = (
                    f"Event buffer exceeded {_MAX_MONITOR_EVENTS} — oldest "
                    "events were dropped; the summary counts are unaffected. "
                    "Increase SYNAPSE_MONITOR_EVENT_CAP or reduce cook complexity."
                )
            if callback_error:
                # The callback hit an event it could not read; say so instead
                # of letting an empty event list look like a quiet cook.
                result["callback_error"] = callback_error
            return result

        if action == "stop":
            if not monitor_id:
                raise ValueError(
                    "Couldn't find monitor -- "
                    "please provide the monitor_id returned when you started monitoring"
                )
            monitor = self._tops_monitors.get(monitor_id)
            if monitor is None:
                raise ValueError(
                    f"Couldn't find monitor '{monitor_id}' -- "
                    "it may have already been stopped"
                )

            # Unregister callbacks in main thread, each from the object it was
            # registered on (captured at start; never re-read from the node).
            def _stop():
                removal_errors: List[str] = []
                still_attached: List[Any] = []
                for emitter, h in monitor.get("callback_handlers") or []:
                    try:
                        emitter.removeEventHandler(h)
                    except Exception as exc:
                        # Keep going: one stuck handler must not leave the others attached.
                        still_attached.append((emitter, h))
                        removal_errors.append(f"removeEventHandler failed: {type(exc).__name__}: {exc}")
                        logger.warning("tops_monitor_stream stop: %s", removal_errors[-1])
                monitor["callback_handlers"] = still_attached

                with monitor["lock"]:
                    n_events = len(monitor.get("events", []))
                elapsed = time.monotonic() - monitor.get("start_time", time.monotonic())
                result = {
                    "monitor_id": monitor_id,
                    "status": "stop_incomplete" if still_attached else "stopped",
                    "elapsed_seconds": round_float(elapsed),
                    "events_collected": n_events,
                    "summary": _summary(monitor),
                }
                if removal_errors:
                    # A handler still attached keeps firing; the monitor is kept
                    # so the same monitor_id can retry the stop.
                    result["handler_removal_errors"] = removal_errors
                    result["note"] = ("Some PDG handlers are still attached; call stop again "
                                      "with this monitor_id to retry")
                return _report_flags(monitor, result)

            # Drop the record only once every handler is detached: a marshal
            # that times out mid-cook, or a removal that fails, leaves handlers
            # attached, and the caller must be able to retry with this id.
            result = _run_in_main_thread_pdg(_stop)
            if result.get("status") == "stopped":
                self._tops_monitors.pop(monitor_id, None)
            return result

        if action == "status":
            if not monitor_id or monitor_id not in self._tops_monitors:
                raise ValueError(
                    f"Couldn't find monitor '{monitor_id}' -- "
                    "check the monitor_id returned when you started monitoring"
                )

            monitor = self._tops_monitors[monitor_id]
            with monitor["lock"]:
                events = list(monitor.get("events", []))  # snapshot; the cook thread appends
            elapsed = time.monotonic() - monitor.get("start_time", time.monotonic())
            return _report_flags(monitor, {
                "monitor_id": monitor_id,
                "status": "active",
                "elapsed_seconds": round_float(elapsed),
                "events_collected": len(events),
                "latest_events": events[-10:] if events else [],
                "summary": _summary(monitor),
            })

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

            import pdg as _pdg

            # A TOP network is monitored through its TOP children; a TOP node
            # through itself. On H22.0.400 the graph context never delivers
            # WorkItemStateChange or NodeProgressUpdate (live hython probe
            # 2026-10-07: 0 events on the context, 130 and 11 on the pdg.Node
            # for the same cooks), so item and progress handlers always go on
            # pdg.Nodes.
            is_network = False
            try:
                is_network = node.childTypeCategory() == hou.topNodeTypeCategory()
            except Exception as exc:
                logger.debug("tops_monitor_stream: childTypeCategory unreadable on %s: %s", node_path, exc)
            if is_network:
                pdg_nodes = []
                for child in node.children():
                    get_pdg = getattr(child, "getPDGNode", None)
                    pn = get_pdg() if get_pdg is not None else None
                    if pn is not None:
                        pdg_nodes.append(pn)
                if not pdg_nodes:
                    raise ValueError(
                        f"The network at {node_path} has no TOP nodes set up for PDG "
                        "yet -- cook or generate it once, or monitor one of its TOP nodes"
                    )
                ctx = pdg_nodes[0].context
                if ctx is None:
                    raise RuntimeError(
                        f"Couldn't start monitoring {node_path} -- its TOP nodes have "
                        "no PDG graph context, so the end of a cook cannot be seen"
                    )
            else:
                pn = node.getPDGNode()
                if pn is None:
                    raise ValueError(
                        f"The node at {node_path} isn't a TOP node or hasn't been "
                        "set up for PDG yet -- make sure it's inside a TOP network"
                    )
                pdg_nodes = [pn]

            mid = f"monitor-{deterministic_uuid(f'tops_monitor_{node_path}')[:8]}"
            if mid in self._tops_monitors:
                # One monitor per path. A second start would otherwise attach
                # a second set of handlers and orphan the first.
                return {
                    "monitor_id": mid,
                    "node": node_path,
                    "status": "already_monitoring",
                    "note": "This node already has a monitor; use action='status' "
                            "or action='stop' with this monitor_id",
                }

            events_list: List[Dict] = []
            start_time = time.monotonic()
            _zero = {"completed": 0, "cached": 0, "failed": 0, "cancelled": 0}
            # The record stored in self._tops_monitors; the callback updates it,
            # so it must exist before the callback does. PDG may call back from
            # its own threads, so every read-modify-write holds the lock.
            monitor: Dict[str, Any] = {
                "node_path": node_path,
                "pdg_node": pdg_nodes[0],
                "events": events_list,
                "start_time": start_time,
                "counts": dict(_zero),       # every cook since start
                "cook_counts": dict(_zero),  # the current (or last) cook only
                "lock": threading.Lock(),
            }
            ws = _pdg.workItemState
            terminal = ("complete", "complete_with_errors", "error")

            def _total_items():
                return sum(len(getattr(p, 'workItems', None) or []) for p in pdg_nodes)

            def _progress_row(name, elapsed):
                # Caller holds the lock.
                cc = monitor["cook_counts"]
                processed = sum(cc.values())
                total = _total_items()
                return {
                    "type": "cook_progress",
                    "node": name,
                    "processed": processed,
                    "failed": cc["failed"],
                    "total": total,
                    "percent": round_float(min(processed / total, 1.0) * 100.0 if total > 0 else 0.0),
                    "timestamp": round_float(elapsed),
                }

            def _on_event(event):
                """PDG event callback -- must not block the cook thread."""
                try:
                    etype = event.type
                    elapsed = time.monotonic() - start_time
                    with monitor["lock"]:
                        # Cap event list to prevent unbounded memory growth.
                        # Keep the last 80% to avoid trimming on every single event.
                        if len(events_list) > _MAX_MONITOR_EVENTS:
                            events_list[:] = events_list[-(int(_MAX_MONITOR_EVENTS * 0.8)):]
                            monitor["was_truncated"] = True
                        if (etype in (_pdg.EventType.WorkItemStateChange, _pdg.EventType.NodeProgressUpdate)
                                and monitor.get("cook_state") in terminal):
                            # The first item or progress event after a cook ended
                            # starts a new cook: per-cook progress and state reset.
                            monitor["cook_counts"] = dict(_zero)
                            monitor["cook_state"] = "cooking"
                        elif monitor.get("cook_state") is None and etype != _pdg.EventType.CookComplete:
                            monitor["cook_state"] = "cooking"
                        counts, cook_counts = monitor["counts"], monitor["cook_counts"]

                        if etype == _pdg.EventType.WorkItemStateChange:
                            # H22 pdg.Event carries workItemId + currentState, not a
                            # workItem object (probe 2026-10-06, hython 22.0.400).
                            state = event.currentState
                            item_id = event.workItemId
                            wi = None
                            try:
                                wi = event.context.graph.workItemById(item_id)
                            except Exception as exc:
                                # The event still counts; only frame/duration/outputs go missing.
                                logger.debug("tops_monitor_stream: workItemById(%s) failed: %s", item_id, exc)
                                wi = None
                            item_info = {
                                "item_id": item_id,
                                "node": event.node.name if event.node else node_path,
                                "frame": getattr(wi, 'frame', None),
                                "timestamp": round_float(elapsed),
                            }

                            if state == ws.Cooking:
                                item_info["type"] = "work_item_started"
                                events_list.append(item_info)

                            elif state in (ws.CookedSuccess, ws.CookedCache):
                                key = "cached" if state == ws.CookedCache else "completed"
                                counts[key] += 1
                                cook_counts[key] += 1
                                item_info["type"] = "work_item_completed"
                                if key == "cached":
                                    item_info["cached"] = True
                                duration = getattr(wi, 'cookDuration', None)
                                if duration is not None:
                                    item_info["duration_seconds"] = round_float(duration)
                                # Try to get output path from result data
                                try:
                                    outputs = wi.resultData if wi is not None else None
                                    if outputs:
                                        item_info["output_path"] = str(outputs[0])
                                except Exception as exc:
                                    logger.debug("tops_monitor_stream: resultData unreadable for %s: %s", item_id, exc)
                                events_list.append(item_info)

                            elif state == ws.CookedFail:
                                counts["failed"] += 1
                                cook_counts["failed"] += 1
                                item_info["type"] = "work_item_failed"
                                # On H22.0.400 the failing event's message is empty
                                # and work items have no lastError; the error text
                                # is in the item's log (live probe 2026-10-07).
                                text = getattr(event, 'message', None) or None
                                if not text and wi is not None:
                                    log_text = getattr(wi, 'logMessages', None) or ""
                                    text = str(log_text).strip()[-500:] or None
                                item_info["error_message"] = text
                                events_list.append(item_info)

                            elif state == ws.CookedCancel:
                                counts["cancelled"] += 1
                                cook_counts["cancelled"] += 1
                                item_info["type"] = "work_item_cancelled"
                                events_list.append(item_info)

                        elif etype == _pdg.EventType.NodeProgressUpdate:
                            # H22 has no CookProgress event and pdg.Event carries no
                            # counts: processed comes from this cook's counters, the
                            # total from the monitored nodes' work item lists.
                            pnode = event.node
                            events_list.append(_progress_row(pnode.name if pnode else node_path, elapsed))

                        elif etype == _pdg.EventType.CookComplete:
                            if monitor.get("cook_state") not in terminal:
                                # A failed item does not raise CookError on H22, so the
                                # end state says whether this cook had failures.
                                failed = monitor["cook_state"] == "error" or monitor["cook_counts"]["failed"] > 0
                                monitor["cook_state"] = "complete_with_errors" if failed else "complete"
                                # H22 coalesces progress updates when items finish
                                # together; the cook's end always gets a final row.
                                events_list.append(_progress_row(node_path, elapsed))
                                events_list.append({
                                    "type": "cook_complete",
                                    "cook_state": monitor["cook_state"],
                                    "total_time_seconds": round_float(elapsed),
                                    "results_summary": {
                                        "total_events": len(events_list),
                                    },
                                    "timestamp": round_float(elapsed),
                                })

                        elif etype == _pdg.EventType.CookError:
                            # A node or scheduler error can end a cook with no work
                            # item reaching CookedFail.
                            monitor["cook_state"] = "error"
                            events_list.append({
                                "type": "cook_error",
                                "node": event.node.name if event.node else node_path,
                                "message": getattr(event, 'message', None) or None,
                                "timestamp": round_float(elapsed),
                            })

                except Exception as exc:
                    # Never raise into the cook thread, but never hide it either:
                    # keep the first failure for status/stop to report.
                    if "callback_error" not in monitor:
                        monitor["callback_error"] = f"{type(exc).__name__}: {exc}"
                        logger.warning("tops_monitor_stream callback failed on %s: %s",
                                       node_path, monitor["callback_error"])

            # Item and progress events on every monitored pdg.Node. Cook-level
            # events on the node for a single node (verified live), and once
            # on the graph context for a network, so each cook ends once.
            # pdg.EventType members do not combine with `|`, so it is one
            # addEventHandler call per (emitter, type); each returns the
            # handler object removeEventHandler needs.
            item_types = (_pdg.EventType.WorkItemStateChange, _pdg.EventType.NodeProgressUpdate)
            cook_types = (_pdg.EventType.CookComplete, _pdg.EventType.CookError)
            plan = [(p, t) for p in pdg_nodes for t in item_types]
            plan += [(ctx if is_network else pdg_nodes[0], t) for t in cook_types]

            def _remove_handlers(handlers):
                for emitter, h in handlers:
                    try:
                        emitter.removeEventHandler(h)
                    except Exception as exc:
                        # Rolling back a failed start; the original error is what gets raised.
                        logger.warning("tops_monitor_stream rollback: removeEventHandler failed: %s", exc)

            handlers: List[Any] = []
            try:
                for emitter, etype in plan:
                    handlers.append((emitter, emitter.addEventHandler(_on_event, etype)))
            except Exception as exc:
                _remove_handlers(handlers)
                raise RuntimeError(
                    f"Couldn't start monitoring {node_path} -- registering the "
                    f"PDG event handler failed: {type(exc).__name__}: {exc}"
                ) from exc

            try:
                monitor["callback_handlers"] = handlers
                self._tops_monitors[mid] = monitor
            except Exception:
                # If storage fails, unregister the callbacks to prevent leak
                _remove_handlers(handlers)
                raise

            return {
                "monitor_id": mid,
                "node": node_path,
                "status": "monitoring",
                "nodes_monitored": [getattr(p, 'name', None) for p in pdg_nodes],
                "note": "Use tops_monitor_stream with action='status' to check events, "
                        "or action='stop' to end monitoring and get results",
            }

        return _run_in_main_thread_pdg(_start)


