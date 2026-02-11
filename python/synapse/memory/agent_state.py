"""
Synapse Agent State -- USD-based agent execution tracking.

Stores task state, session history, and verification logs in agent.usd.
Uses pxr.Usd and pxr.Sdf (available in Houdini's Python).
"""

import logging
import os
import time
from typing import Dict, List, Optional, Any

logger = logging.getLogger("synapse.agent_state")

try:
    from pxr import Usd, Sdf
    PXR_AVAILABLE = True
except ImportError:
    PXR_AVAILABLE = False

SCHEMA_VERSION = "0.1.0"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def initialize_agent_usd(path: str) -> None:
    """Create fresh agent.usd with empty /SYNAPSE/agent prim hierarchy."""
    if not PXR_AVAILABLE:
        logger.warning("pxr not available -- writing USDA stub")
        _write_usda_stub(path)
        return

    stage = Usd.Stage.CreateNew(path)
    root = stage.DefinePrim("/SYNAPSE", "Xform")
    agent_prim = stage.DefinePrim("/SYNAPSE/agent", "Xform")
    agent_prim.CreateAttribute("synapse:status", Sdf.ValueTypeNames.String).Set("idle")
    agent_prim.CreateAttribute("synapse:version", Sdf.ValueTypeNames.String).Set(SCHEMA_VERSION)

    stage.DefinePrim("/SYNAPSE/agent/current_plan", "Xform")
    stage.DefinePrim("/SYNAPSE/agent/tasks", "Xform")
    stage.DefinePrim("/SYNAPSE/agent/verification_log", "Xform")
    stage.DefinePrim("/SYNAPSE/agent/session_history", "Xform")

    stage.GetRootLayer().customLayerData = {
        "synapse:version": SCHEMA_VERSION,
        "synapse:type": "agent_state",
    }
    stage.GetRootLayer().Save()
    logger.info("Initialized agent.usd: %s", path)


def _write_usda_stub(path: str) -> None:
    """Fallback: write minimal USDA text when pxr unavailable."""
    content = (
        '#usda 1.0\n'
        '(\n'
        f'    customLayerData = {{\n'
        f'        string "synapse:version" = "{SCHEMA_VERSION}"\n'
        f'        string "synapse:type" = "agent_state"\n'
        f'    }}\n'
        ')\n\n'
        'def Xform "SYNAPSE"\n'
        '{\n'
        '    def Xform "agent"\n'
        '    {\n'
        '        custom string synapse:status = "idle"\n'
        '    }\n'
        '}\n'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def create_task(agent_usd_path: str, task_id: str, description: str) -> None:
    """Create a task prim under /SYNAPSE/agent/tasks/."""
    if not PXR_AVAILABLE:
        logger.warning("pxr not available -- cannot create task")
        return

    stage = Usd.Stage.Open(agent_usd_path)
    task = stage.DefinePrim(f"/SYNAPSE/agent/tasks/{task_id}", "Xform")
    task.CreateAttribute("synapse:description", Sdf.ValueTypeNames.String).Set(description)
    task.CreateAttribute("synapse:status", Sdf.ValueTypeNames.String).Set("pending")
    task.CreateAttribute("synapse:createdAt", Sdf.ValueTypeNames.String).Set(_now())
    stage.GetRootLayer().Save()


def update_task_status(agent_usd_path: str, task_id: str, status: str,
                       verification: Dict = None) -> None:
    """Update task status: pending -> executing -> completed|failed."""
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    task = stage.GetPrimAtPath(f"/SYNAPSE/agent/tasks/{task_id}")
    if not task.IsValid():
        logger.warning("Task not found: %s", task_id)
        return

    task.GetAttribute("synapse:status").Set(status)

    if status == "completed":
        task.CreateAttribute("synapse:completedAt", Sdf.ValueTypeNames.String).Set(_now())
    elif status == "failed":
        task.CreateAttribute("synapse:failedAt", Sdf.ValueTypeNames.String).Set(_now())

    if verification:
        task.CreateAttribute("synapse:verificationResult", Sdf.ValueTypeNames.String).Set(
            verification.get("result", "unknown")
        )

    stage.GetRootLayer().Save()


def suspend_all_tasks(agent_usd_path: str) -> None:
    """Mark all pending/executing tasks as suspended. Called on disconnect."""
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    tasks_prim = stage.GetPrimAtPath("/SYNAPSE/agent/tasks")
    if not tasks_prim.IsValid():
        return

    now = _now()
    for task in tasks_prim.GetChildren():
        status_attr = task.GetAttribute("synapse:status")
        if status_attr and status_attr.Get() in ("pending", "executing"):
            status_attr.Set("suspended")
            task.CreateAttribute("synapse:suspendedAt", Sdf.ValueTypeNames.String).Set(now)

    stage.GetRootLayer().Save()


def resume_task(agent_usd_path: str, task_id: str) -> None:
    """Resume a suspended task -- set status back to pending."""
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    task = stage.GetPrimAtPath(f"/SYNAPSE/agent/tasks/{task_id}")
    if task.IsValid():
        task.GetAttribute("synapse:status").Set("pending")
        stage.GetRootLayer().Save()


def abandon_task(agent_usd_path: str, task_id: str) -> None:
    """Abandon a suspended task."""
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    task = stage.GetPrimAtPath(f"/SYNAPSE/agent/tasks/{task_id}")
    if task.IsValid():
        task.GetAttribute("synapse:status").Set("abandoned")
        task.CreateAttribute("synapse:abandonedAt", Sdf.ValueTypeNames.String).Set(_now())
        stage.GetRootLayer().Save()


def load_agent_state(claude_dir: str) -> Dict[str, Any]:
    """Load agent state from agent.usd."""
    path = os.path.join(os.path.normpath(claude_dir), "agent.usd")
    state = {
        "status": "idle",
        "has_suspended_tasks": False,
        "suspended_count": 0,
        "suspended_tasks": [],
    }

    if not os.path.exists(path) or not PXR_AVAILABLE:
        return state

    try:
        stage = Usd.Stage.Open(path)
        agent_prim = stage.GetPrimAtPath("/SYNAPSE/agent")
        if agent_prim.IsValid():
            status_attr = agent_prim.GetAttribute("synapse:status")
            if status_attr:
                state["status"] = status_attr.Get() or "idle"

        tasks_prim = stage.GetPrimAtPath("/SYNAPSE/agent/tasks")
        if tasks_prim.IsValid():
            for task in tasks_prim.GetChildren():
                task_status = task.GetAttribute("synapse:status").Get()
                if task_status == "suspended":
                    desc_attr = task.GetAttribute("synapse:description")
                    state["suspended_tasks"].append({
                        "id": task.GetName(),
                        "description": desc_attr.Get() if desc_attr else "",
                    })

        state["suspended_count"] = len(state["suspended_tasks"])
        state["has_suspended_tasks"] = state["suspended_count"] > 0

    except Exception as e:
        logger.warning("Could not load agent state: %s", e)

    return state


def log_session(agent_usd_path: str, summary: Dict[str, Any]) -> None:
    """Write session summary to /SYNAPSE/agent/session_history/."""
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    now = _now()
    session_id = "session_" + now.replace("-", "_").replace(":", "_").replace("T", "_").rstrip("Z")

    prim = stage.DefinePrim(f"/SYNAPSE/agent/session_history/{session_id}", "Xform")
    prim.CreateAttribute("synapse:startTime", Sdf.ValueTypeNames.String).Set(
        summary.get("start_time", "")
    )
    prim.CreateAttribute("synapse:endTime", Sdf.ValueTypeNames.String).Set(
        summary.get("end_time", now)
    )
    prim.CreateAttribute("synapse:tasksCompleted", Sdf.ValueTypeNames.Int).Set(
        summary.get("tasks_completed", 0)
    )
    prim.CreateAttribute("synapse:tasksFailed", Sdf.ValueTypeNames.Int).Set(
        summary.get("tasks_failed", 0)
    )
    prim.CreateAttribute("synapse:tasksSuspended", Sdf.ValueTypeNames.Int).Set(
        summary.get("tasks_suspended", 0)
    )
    prim.CreateAttribute("synapse:summary", Sdf.ValueTypeNames.String).Set(
        summary.get("summary_text", "")
    )

    stage.GetRootLayer().Save()


def write_verification(agent_usd_path: str, task_id: str,
                       before_state: str, after_state: str,
                       checks: List, result: str) -> None:
    """Write verification log entry for a task."""
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    now = _now()
    verify_id = f"verify_{task_id}_{now.replace('-','').replace(':','').replace('T','_').rstrip('Z')}"

    prim = stage.DefinePrim(f"/SYNAPSE/agent/verification_log/{verify_id}", "Xform")
    prim.CreateAttribute("synapse:taskId", Sdf.ValueTypeNames.String).Set(task_id)
    prim.CreateAttribute("synapse:beforeState", Sdf.ValueTypeNames.String).Set(before_state)
    prim.CreateAttribute("synapse:afterState", Sdf.ValueTypeNames.String).Set(after_state)
    prim.CreateAttribute("synapse:checks", Sdf.ValueTypeNames.String).Set(str(checks))
    prim.CreateAttribute("synapse:result", Sdf.ValueTypeNames.String).Set(result)

    stage.GetRootLayer().Save()
