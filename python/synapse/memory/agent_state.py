"""
Synapse Agent State v2.0.0 -- USD-based agent execution tracking.

Stores task state, integrity metrics, routing decisions, handoff chains,
and session history in agent.usd. Uses pxr.Usd and pxr.Sdf (Houdini Python).

Schema v2.0.0 prim layout:
    /SYNAPSE/agent/                     status, version, current_plan, dispatched_agents
    /SYNAPSE/agent/tasks/               task_NNNN prims
    /SYNAPSE/agent/integrity/           session_fidelity, ops_total, ops_verified, anchor_violations
    /SYNAPSE/agent/routing_log/         decision_NNNN prims
    /SYNAPSE/agent/handoff_chain/       handoff_NNNN prims
    /SYNAPSE/agent/session_history/     session_NNNN prims
    /SYNAPSE/agent/verification_log/    verify_NNNN prims
    /SYNAPSE/memory/                    sessions/, decisions/, assets/, parameters/, wedges/
"""

import hashlib
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("synapse.agent_state")

try:
    from pxr import Usd, Sdf, Vt
    PXR_AVAILABLE = True
except ImportError:
    Usd = Sdf = Vt = None
    PXR_AVAILABLE = False

SCHEMA_VERSION = "2.0.0"
_PREV_VERSION = "0.1.0"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_prim_name(name: str) -> str:
    """Make a valid USD prim name from arbitrary input."""
    # Replace non-alphanumeric with underscore, ensure starts with letter
    clean = "".join(c if c.isalnum() else "_" for c in name)
    if clean and clean[0].isdigit():
        clean = "p_" + clean
    return clean or "unnamed"


def _counter_suffix(parent_prim, prefix: str) -> str:
    """Generate next sequential name like decision_0001 under parent."""
    existing = [c.GetName() for c in parent_prim.GetChildren()] if parent_prim.IsValid() else []
    matching = [n for n in existing if n.startswith(prefix)]
    idx = len(matching)
    return f"{prefix}{idx:04d}"


# ── Initialization ──────────────────────────────────────────────


def initialize_agent_usd(path: str) -> None:
    """Create fresh agent.usd with v2.0.0 prim hierarchy."""
    if not PXR_AVAILABLE:
        logger.warning("pxr not available -- writing USDA stub")
        _write_usda_stub(path)
        return

    stage = Usd.Stage.CreateNew(path)
    root = stage.DefinePrim("/SYNAPSE", "Xform")

    # ── /SYNAPSE/agent ──
    agent = stage.DefinePrim("/SYNAPSE/agent", "Xform")
    agent.CreateAttribute("synapse:status", Sdf.ValueTypeNames.String).Set("idle")
    agent.CreateAttribute("synapse:version", Sdf.ValueTypeNames.String).Set(SCHEMA_VERSION)
    agent.CreateAttribute("synapse:dispatched_agents", Sdf.ValueTypeNames.StringArray).Set(
        Vt.StringArray()
    )

    # Sub-containers
    stage.DefinePrim("/SYNAPSE/agent/current_plan", "Xform")
    stage.DefinePrim("/SYNAPSE/agent/tasks", "Xform")

    # ── /SYNAPSE/agent/integrity ──
    integrity = stage.DefinePrim("/SYNAPSE/agent/integrity", "Xform")
    integrity.CreateAttribute("synapse:session_fidelity", Sdf.ValueTypeNames.Float).Set(1.0)
    integrity.CreateAttribute("synapse:operations_total", Sdf.ValueTypeNames.Int).Set(0)
    integrity.CreateAttribute("synapse:operations_verified", Sdf.ValueTypeNames.Int).Set(0)
    integrity.CreateAttribute("synapse:anchor_violations", Sdf.ValueTypeNames.Int).Set(0)

    # ── /SYNAPSE/agent/routing_log ──
    stage.DefinePrim("/SYNAPSE/agent/routing_log", "Xform")

    # ── /SYNAPSE/agent/handoff_chain ──
    stage.DefinePrim("/SYNAPSE/agent/handoff_chain", "Xform")

    # ── /SYNAPSE/agent/session_history ──
    stage.DefinePrim("/SYNAPSE/agent/session_history", "Xform")

    # ── /SYNAPSE/agent/verification_log ──
    stage.DefinePrim("/SYNAPSE/agent/verification_log", "Xform")

    # ── /SYNAPSE/memory (evolution target) ──
    stage.DefinePrim("/SYNAPSE/memory", "Xform")
    for sub in ("sessions", "decisions", "assets", "parameters", "wedges"):
        stage.DefinePrim(f"/SYNAPSE/memory/{sub}", "Xform")

    # Layer metadata
    stage.GetRootLayer().customLayerData = {
        "synapse:version": SCHEMA_VERSION,
        "synapse:type": "agent_state",
    }
    stage.GetRootLayer().Save()
    logger.info("Initialized agent.usd v%s: %s", SCHEMA_VERSION, path)


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
        f'        custom string synapse:status = "idle"\n'
        f'        custom string synapse:version = "{SCHEMA_VERSION}"\n'
        '        custom string[] synapse:dispatched_agents = []\n\n'
        '        def Xform "current_plan" {}\n'
        '        def Xform "tasks" {}\n\n'
        '        def Xform "integrity"\n'
        '        {\n'
        '            custom float synapse:session_fidelity = 1.0\n'
        '            custom int synapse:operations_total = 0\n'
        '            custom int synapse:operations_verified = 0\n'
        '            custom int synapse:anchor_violations = 0\n'
        '        }\n\n'
        '        def Xform "routing_log" {}\n'
        '        def Xform "handoff_chain" {}\n'
        '        def Xform "session_history" {}\n'
        '        def Xform "verification_log" {}\n'
        '    }\n\n'
        '    def Xform "memory"\n'
        '    {\n'
        '        def Xform "sessions" {}\n'
        '        def Xform "decisions" {}\n'
        '        def Xform "assets" {}\n'
        '        def Xform "parameters" {}\n'
        '        def Xform "wedges" {}\n'
        '    }\n'
        '}\n'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ── Migration ───────────────────────────────────────────────────


def migrate_to_v2(path: str) -> bool:
    """Migrate a v0.1.0 agent.usd to v2.0.0. Returns True if migration occurred."""
    if not PXR_AVAILABLE:
        logger.warning("pxr not available -- cannot migrate")
        return False

    if not os.path.exists(path):
        return False

    stage = Usd.Stage.Open(path)
    agent = stage.GetPrimAtPath("/SYNAPSE/agent")
    if not agent.IsValid():
        return False

    version_attr = agent.GetAttribute("synapse:version")
    current = version_attr.Get() if version_attr else None

    if current == SCHEMA_VERSION:
        return False  # Already v2

    # Add dispatched_agents if missing
    if not agent.GetAttribute("synapse:dispatched_agents"):
        agent.CreateAttribute("synapse:dispatched_agents", Sdf.ValueTypeNames.StringArray).Set(
            Vt.StringArray()
        )

    # Add integrity prim if missing
    integrity_path = "/SYNAPSE/agent/integrity"
    if not stage.GetPrimAtPath(integrity_path).IsValid():
        integrity = stage.DefinePrim(integrity_path, "Xform")
        integrity.CreateAttribute("synapse:session_fidelity", Sdf.ValueTypeNames.Float).Set(1.0)
        integrity.CreateAttribute("synapse:operations_total", Sdf.ValueTypeNames.Int).Set(0)
        integrity.CreateAttribute("synapse:operations_verified", Sdf.ValueTypeNames.Int).Set(0)
        integrity.CreateAttribute("synapse:anchor_violations", Sdf.ValueTypeNames.Int).Set(0)

    # Add routing_log if missing
    if not stage.GetPrimAtPath("/SYNAPSE/agent/routing_log").IsValid():
        stage.DefinePrim("/SYNAPSE/agent/routing_log", "Xform")

    # Add handoff_chain if missing
    if not stage.GetPrimAtPath("/SYNAPSE/agent/handoff_chain").IsValid():
        stage.DefinePrim("/SYNAPSE/agent/handoff_chain", "Xform")

    # Add memory hierarchy if missing
    if not stage.GetPrimAtPath("/SYNAPSE/memory").IsValid():
        stage.DefinePrim("/SYNAPSE/memory", "Xform")
        for sub in ("sessions", "decisions", "assets", "parameters", "wedges"):
            stage.DefinePrim(f"/SYNAPSE/memory/{sub}", "Xform")

    # Bump version
    if version_attr:
        version_attr.Set(SCHEMA_VERSION)
    else:
        agent.CreateAttribute("synapse:version", Sdf.ValueTypeNames.String).Set(SCHEMA_VERSION)

    stage.GetRootLayer().customLayerData = {
        "synapse:version": SCHEMA_VERSION,
        "synapse:type": "agent_state",
    }
    stage.GetRootLayer().Save()
    logger.info("Migrated agent.usd from %s to %s: %s", current, SCHEMA_VERSION, path)
    return True


# ── Task Operations ─────────────────────────────────────────────


def create_task(agent_usd_path: str, task_id: str, description: str) -> None:
    """Create a task prim under /SYNAPSE/agent/tasks/."""
    if not PXR_AVAILABLE:
        logger.warning("pxr not available -- cannot create task")
        return

    stage = Usd.Stage.Open(agent_usd_path)
    safe_id = _safe_prim_name(task_id)
    task = stage.DefinePrim(f"/SYNAPSE/agent/tasks/{safe_id}", "Xform")
    task.CreateAttribute("synapse:task_id", Sdf.ValueTypeNames.String).Set(task_id)
    task.CreateAttribute("synapse:description", Sdf.ValueTypeNames.String).Set(description)
    task.CreateAttribute("synapse:status", Sdf.ValueTypeNames.String).Set("pending")
    task.CreateAttribute("synapse:createdAt", Sdf.ValueTypeNames.String).Set(_now())
    stage.GetRootLayer().Save()


def update_task_status(agent_usd_path: str, task_id: str, status: str,
                       verification: Optional[Dict] = None) -> None:
    """Update task status: pending -> executing -> completed|failed."""
    if not PXR_AVAILABLE:
        return

    safe_id = _safe_prim_name(task_id)
    stage = Usd.Stage.Open(agent_usd_path)
    task = stage.GetPrimAtPath(f"/SYNAPSE/agent/tasks/{safe_id}")
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

    safe_id = _safe_prim_name(task_id)
    stage = Usd.Stage.Open(agent_usd_path)
    task = stage.GetPrimAtPath(f"/SYNAPSE/agent/tasks/{safe_id}")
    if task.IsValid():
        task.GetAttribute("synapse:status").Set("pending")
        stage.GetRootLayer().Save()


def abandon_task(agent_usd_path: str, task_id: str) -> None:
    """Abandon a suspended task."""
    if not PXR_AVAILABLE:
        return

    safe_id = _safe_prim_name(task_id)
    stage = Usd.Stage.Open(agent_usd_path)
    task = stage.GetPrimAtPath(f"/SYNAPSE/agent/tasks/{safe_id}")
    if task.IsValid():
        task.GetAttribute("synapse:status").Set("abandoned")
        task.CreateAttribute("synapse:abandonedAt", Sdf.ValueTypeNames.String).Set(_now())
        stage.GetRootLayer().Save()


# ── Integrity Tracking ──────────────────────────────────────────


def log_integrity(agent_usd_path: str, operation_type: str, agent_id: str,
                  fidelity: float, anchors_hold: bool,
                  scene_hash_before: str = "", scene_hash_after: str = "",
                  delta_hash: str = "") -> None:
    """Record an integrity observation from an IntegrityBlock.

    Updates running counters on /SYNAPSE/agent/integrity and tracks
    the minimum session fidelity (worst-case indicator).
    """
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    integrity = stage.GetPrimAtPath("/SYNAPSE/agent/integrity")
    if not integrity.IsValid():
        logger.warning("integrity prim missing -- run migrate_to_v2")
        return

    # Increment operations_total
    total_attr = integrity.GetAttribute("synapse:operations_total")
    total = (total_attr.Get() or 0) + 1
    total_attr.Set(total)

    # Increment operations_verified if fidelity == 1.0
    if fidelity == 1.0:
        verified_attr = integrity.GetAttribute("synapse:operations_verified")
        verified_attr.Set((verified_attr.Get() or 0) + 1)

    # Increment anchor_violations if anchors didn't hold
    if not anchors_hold:
        violations_attr = integrity.GetAttribute("synapse:anchor_violations")
        violations_attr.Set((violations_attr.Get() or 0) + 1)

    # Track minimum session fidelity
    fidelity_attr = integrity.GetAttribute("synapse:session_fidelity")
    current_fidelity = fidelity_attr.Get()
    if current_fidelity is None or fidelity < current_fidelity:
        fidelity_attr.Set(fidelity)

    stage.GetRootLayer().Save()


def get_integrity(agent_usd_path: str) -> Dict[str, Any]:
    """Read current integrity counters."""
    result = {
        "session_fidelity": 1.0,
        "operations_total": 0,
        "operations_verified": 0,
        "anchor_violations": 0,
    }
    if not PXR_AVAILABLE or not os.path.exists(agent_usd_path):
        return result

    try:
        stage = Usd.Stage.Open(agent_usd_path)
        integrity = stage.GetPrimAtPath("/SYNAPSE/agent/integrity")
        if not integrity.IsValid():
            return result

        for key in result:
            attr = integrity.GetAttribute(f"synapse:{key}")
            if attr:
                val = attr.Get()
                if val is not None:
                    result[key] = val
    except Exception as e:
        logger.warning("Could not read integrity: %s", e)

    return result


# ── Routing Log ─────────────────────────────────────────────────


def log_routing_decision(agent_usd_path: str, fingerprint: str,
                         primary_agent: str, advisory_agent: Optional[str],
                         method: str) -> str:
    """Append a routing decision to /SYNAPSE/agent/routing_log/.

    Returns the prim name of the logged decision.
    """
    if not PXR_AVAILABLE:
        return ""

    stage = Usd.Stage.Open(agent_usd_path)
    parent = stage.GetPrimAtPath("/SYNAPSE/agent/routing_log")
    if not parent.IsValid():
        logger.warning("routing_log prim missing -- run migrate_to_v2")
        return ""

    name = _counter_suffix(parent, "decision_")
    prim = stage.DefinePrim(f"/SYNAPSE/agent/routing_log/{name}", "Xform")
    prim.CreateAttribute("synapse:fingerprint", Sdf.ValueTypeNames.String).Set(fingerprint)
    prim.CreateAttribute("synapse:primary_agent", Sdf.ValueTypeNames.String).Set(primary_agent)
    prim.CreateAttribute("synapse:advisory_agent", Sdf.ValueTypeNames.String).Set(
        advisory_agent or ""
    )
    prim.CreateAttribute("synapse:method", Sdf.ValueTypeNames.String).Set(method)
    prim.CreateAttribute("synapse:timestamp", Sdf.ValueTypeNames.String).Set(_now())

    stage.GetRootLayer().Save()
    return name


def get_routing_log(agent_usd_path: str) -> List[Dict[str, str]]:
    """Read all routing decisions."""
    if not PXR_AVAILABLE or not os.path.exists(agent_usd_path):
        return []

    try:
        stage = Usd.Stage.Open(agent_usd_path)
        parent = stage.GetPrimAtPath("/SYNAPSE/agent/routing_log")
        if not parent.IsValid():
            return []

        results = []
        for child in parent.GetChildren():
            entry = {"name": child.GetName()}
            for key in ("fingerprint", "primary_agent", "advisory_agent", "method", "timestamp"):
                attr = child.GetAttribute(f"synapse:{key}")
                entry[key] = attr.Get() if attr else ""
            results.append(entry)
        return results
    except Exception as e:
        logger.warning("Could not read routing log: %s", e)
        return []


# ── Handoff Chain ───────────────────────────────────────────────


def log_handoff(agent_usd_path: str, from_agent: str, to_agent: str,
                task_id: str, fidelity_at_handoff: float) -> str:
    """Append a handoff record to /SYNAPSE/agent/handoff_chain/.

    Returns the prim name of the logged handoff.
    """
    if not PXR_AVAILABLE:
        return ""

    stage = Usd.Stage.Open(agent_usd_path)
    parent = stage.GetPrimAtPath("/SYNAPSE/agent/handoff_chain")
    if not parent.IsValid():
        logger.warning("handoff_chain prim missing -- run migrate_to_v2")
        return ""

    name = _counter_suffix(parent, "handoff_")
    prim = stage.DefinePrim(f"/SYNAPSE/agent/handoff_chain/{name}", "Xform")
    prim.CreateAttribute("synapse:from_agent", Sdf.ValueTypeNames.String).Set(from_agent)
    prim.CreateAttribute("synapse:to_agent", Sdf.ValueTypeNames.String).Set(to_agent)
    prim.CreateAttribute("synapse:task_id", Sdf.ValueTypeNames.String).Set(task_id)
    prim.CreateAttribute("synapse:fidelity_at_handoff", Sdf.ValueTypeNames.Float).Set(
        fidelity_at_handoff
    )
    prim.CreateAttribute("synapse:timestamp", Sdf.ValueTypeNames.String).Set(_now())

    stage.GetRootLayer().Save()
    return name


def get_handoff_chain(agent_usd_path: str) -> List[Dict[str, Any]]:
    """Read the full handoff chain."""
    if not PXR_AVAILABLE or not os.path.exists(agent_usd_path):
        return []

    try:
        stage = Usd.Stage.Open(agent_usd_path)
        parent = stage.GetPrimAtPath("/SYNAPSE/agent/handoff_chain")
        if not parent.IsValid():
            return []

        results = []
        for child in parent.GetChildren():
            entry: Dict[str, Any] = {"name": child.GetName()}
            for key in ("from_agent", "to_agent", "task_id", "timestamp"):
                attr = child.GetAttribute(f"synapse:{key}")
                entry[key] = attr.Get() if attr else ""
            fid_attr = child.GetAttribute("synapse:fidelity_at_handoff")
            entry["fidelity_at_handoff"] = fid_attr.Get() if fid_attr else 0.0
            results.append(entry)
        return results
    except Exception as e:
        logger.warning("Could not read handoff chain: %s", e)
        return []


# ── Dispatched Agents ───────────────────────────────────────────


def set_dispatched_agents(agent_usd_path: str, agents: List[str]) -> None:
    """Update the list of currently dispatched agents."""
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    agent_prim = stage.GetPrimAtPath("/SYNAPSE/agent")
    if not agent_prim.IsValid():
        return

    attr = agent_prim.GetAttribute("synapse:dispatched_agents")
    if not attr:
        attr = agent_prim.CreateAttribute("synapse:dispatched_agents", Sdf.ValueTypeNames.StringArray)
    attr.Set(Vt.StringArray(agents))
    stage.GetRootLayer().Save()


def get_dispatched_agents(agent_usd_path: str) -> List[str]:
    """Read current dispatched agents list."""
    if not PXR_AVAILABLE or not os.path.exists(agent_usd_path):
        return []

    try:
        stage = Usd.Stage.Open(agent_usd_path)
        attr = stage.GetPrimAtPath("/SYNAPSE/agent").GetAttribute("synapse:dispatched_agents")
        if attr:
            val = attr.Get()
            return list(val) if val else []
    except Exception as e:
        logger.warning("Could not read dispatched agents: %s", e)
    return []


# ── Session History ─────────────────────────────────────────────


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


# ── Verification Log ────────────────────────────────────────────


def write_verification(agent_usd_path: str, task_id: str,
                       before_state: str, after_state: str,
                       checks: List, result: str) -> None:
    """Write verification log entry for a task."""
    if not PXR_AVAILABLE:
        return

    stage = Usd.Stage.Open(agent_usd_path)
    now = _now()
    verify_id = f"verify_{_safe_prim_name(task_id)}_{now.replace('-','').replace(':','').replace('T','_').rstrip('Z')}"

    prim = stage.DefinePrim(f"/SYNAPSE/agent/verification_log/{verify_id}", "Xform")
    prim.CreateAttribute("synapse:taskId", Sdf.ValueTypeNames.String).Set(task_id)
    prim.CreateAttribute("synapse:beforeState", Sdf.ValueTypeNames.String).Set(before_state)
    prim.CreateAttribute("synapse:afterState", Sdf.ValueTypeNames.String).Set(after_state)
    prim.CreateAttribute("synapse:checks", Sdf.ValueTypeNames.String).Set(str(checks))
    prim.CreateAttribute("synapse:result", Sdf.ValueTypeNames.String).Set(result)

    stage.GetRootLayer().Save()


# ── Load Full State ─────────────────────────────────────────────


def load_agent_state(claude_dir: str) -> Dict[str, Any]:
    """Load full agent state from agent.usd (v2.0.0 aware)."""
    path = os.path.join(os.path.normpath(claude_dir), "agent.usd")
    state: Dict[str, Any] = {
        "version": SCHEMA_VERSION,
        "status": "idle",
        "has_suspended_tasks": False,
        "suspended_count": 0,
        "suspended_tasks": [],
        "dispatched_agents": [],
        "integrity": {
            "session_fidelity": 1.0,
            "operations_total": 0,
            "operations_verified": 0,
            "anchor_violations": 0,
        },
        "routing_decisions": 0,
        "handoffs": 0,
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

            version_attr = agent_prim.GetAttribute("synapse:version")
            if version_attr:
                state["version"] = version_attr.Get() or _PREV_VERSION

            dispatched_attr = agent_prim.GetAttribute("synapse:dispatched_agents")
            if dispatched_attr:
                val = dispatched_attr.Get()
                state["dispatched_agents"] = list(val) if val else []

        # Suspended tasks
        tasks_prim = stage.GetPrimAtPath("/SYNAPSE/agent/tasks")
        if tasks_prim.IsValid():
            for task in tasks_prim.GetChildren():
                status_a = task.GetAttribute("synapse:status")
                if status_a and status_a.Get() == "suspended":
                    desc_attr = task.GetAttribute("synapse:description")
                    state["suspended_tasks"].append({
                        "id": task.GetName(),
                        "description": desc_attr.Get() if desc_attr else "",
                    })

        state["suspended_count"] = len(state["suspended_tasks"])
        state["has_suspended_tasks"] = state["suspended_count"] > 0

        # Integrity
        integrity_prim = stage.GetPrimAtPath("/SYNAPSE/agent/integrity")
        if integrity_prim.IsValid():
            for key in ("session_fidelity", "operations_total", "operations_verified", "anchor_violations"):
                attr = integrity_prim.GetAttribute(f"synapse:{key}")
                if attr:
                    val = attr.Get()
                    if val is not None:
                        state["integrity"][key] = val

        # Routing log count
        routing_prim = stage.GetPrimAtPath("/SYNAPSE/agent/routing_log")
        if routing_prim.IsValid():
            state["routing_decisions"] = len(list(routing_prim.GetChildren()))

        # Handoff count
        handoff_prim = stage.GetPrimAtPath("/SYNAPSE/agent/handoff_chain")
        if handoff_prim.IsValid():
            state["handoffs"] = len(list(handoff_prim.GetChildren()))

    except Exception as e:
        logger.warning("Could not load agent state: %s", e)

    return state
