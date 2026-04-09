"""
Synapse TOPS/PDG Handler Mixin

Extracted from handlers_render.py -- contains wedge and all tops_* handlers
for the SynapseHandler class.
"""

import os
import time
import threading
from typing import Any, Dict, List, Optional

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

import logging

from ...core.aliases import resolve_param, resolve_param_with_default
from ...core.determinism import round_float, kahan_sum, deterministic_uuid
from ..handler_helpers import _HOUDINI_UNAVAILABLE

logger = logging.getLogger("synapse.handlers.tops")

# Maximum number of monitor events kept in memory per monitor stream.
# Prevents unbounded growth during large cooks (thousands of work items).
# Override via SYNAPSE_MONITOR_EVENT_CAP environment variable.
_MAX_MONITOR_EVENTS = int(os.environ.get("SYNAPSE_MONITOR_EVENT_CAP", "5000"))


# =========================================================================
# PDG-aware execution — extended timeout for graph context initialization
# =========================================================================

# Default timeout for hdefereval calls in PDG handlers (seconds).
# PDG graph context initialization (getPDGGraphContext / getPDGNode on first
# access) can block Houdini's main thread for 5-15s, which exceeds the normal
# hdefereval timeout and causes the WebSocket connection to drop.
try:
    from shared.constants import PDG_DEFER_TIMEOUT as _PDG_DEFER_TIMEOUT
except ImportError:
    _PDG_DEFER_TIMEOUT = 60.0


def _run_in_main_thread_pdg(func, timeout=None):
    """Execute a function on Houdini's main thread with PDG-aware timeout.

    Wraps hdefereval.executeInMainThreadWithResult with a longer default
    timeout suitable for PDG operations. PDG graph context initialization
    (triggered by getPDGGraphContext, getPDGNode, cook, generateStaticItems)
    can block the main thread for 5-15 seconds on first access per session.

    Args:
        func: Callable to run on the main thread. Takes no arguments.
        timeout: Override timeout in seconds. Defaults to _PDG_DEFER_TIMEOUT.

    Returns:
        The return value of func.

    Raises:
        RuntimeError: If the main thread does not respond within timeout.
        Any exception raised by func is re-raised.
    """
    import hdefereval

    effective_timeout = timeout if timeout is not None else _PDG_DEFER_TIMEOUT

    # hdefereval.executeInMainThreadWithResult blocks until the main thread
    # executes func. It does NOT accept a timeout parameter — the timeout is
    # enforced at the WebSocket/MCP layer (_SLOW_COMMANDS). What we can do
    # here is log timing to help diagnose stalls.
    t0 = time.monotonic()
    try:
        result = hdefereval.executeInMainThreadWithResult(func)
    except Exception:
        elapsed = time.monotonic() - t0
        if elapsed > 5.0:
            logger.warning(
                "PDG main-thread operation took %.1fs before failing "
                "(PDG graph context initialization may have stalled)",
                elapsed,
            )
        raise

    elapsed = time.monotonic() - t0
    if elapsed > 5.0:
        logger.info(
            "PDG main-thread operation completed in %.1fs "
            "(likely includes graph context cold-start)",
            elapsed,
        )
    return result


# =========================================================================
# TOPS Warm Standby — auto-create local scheduler on first TOPS tool use
# =========================================================================

_tops_warm_standby_lock = threading.Lock()
_tops_warm_standby_done: Dict[str, bool] = {}


def _ensure_tops_warm_standby(topnet_path: str) -> Optional[Dict]:
    """Ensure a local scheduler exists in the given TOP network.

    Called automatically on first TOPS tool use for a given topnet.
    Creates a default local scheduler if none exists, configured with
    sensible defaults (max procs = CPU count - 2, minimum 1).

    Args:
        topnet_path: Path to the TOP network node.

    Returns:
        Dict with scheduler info if created, None if already existed.
    """
    if not HOU_AVAILABLE:
        return None

    # Fast path: already warmed for this topnet
    if topnet_path in _tops_warm_standby_done:
        return None

    with _tops_warm_standby_lock:
        # Double-check after acquiring lock
        if topnet_path in _tops_warm_standby_done:
            return None

        node = hou.node(topnet_path)
        if node is None:
            return None

        cat = node.type().category().name()
        if cat != "TopNet":
            # Not a topnet — try parent
            parent = node.parent()
            if parent is not None and parent.type().category().name() == "TopNet":
                topnet_path = parent.path()
                node = parent
            else:
                _tops_warm_standby_done[topnet_path] = True
                return None

        # Check if scheduler already exists
        for child in node.children():
            child_type = child.type().name().lower()
            if "scheduler" in child_type or child_type == "localscheduler":
                _tops_warm_standby_done[topnet_path] = True
                return None

        # No scheduler found — create one with sensible defaults
        env_procs = os.environ.get("SYNAPSE_TOPS_MAX_PROCS")
        if env_procs is not None:
            max_procs = max(1, int(env_procs))
        else:
            cpu_count = os.cpu_count() or 4
            max_procs = max(1, cpu_count - 2)

        scheduler = node.createNode("localscheduler", "localscheduler")
        scheduler.moveToGoodPosition()

        # Configure max concurrent processes
        menu_parm = scheduler.parm("maxprocsmenu")
        if menu_parm:
            menu_parm.set("custom")
        procs_parm = scheduler.parm("maxprocs")
        if procs_parm:
            procs_parm.set(max_procs)

        _tops_warm_standby_done[topnet_path] = True
        return {
            "scheduler_created": True,
            "scheduler_path": scheduler.path(),
            "max_procs": max_procs,
        }


