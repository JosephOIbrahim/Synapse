"""
synapse_planner.py -- Multi-goal planner for the Synapse Agent.

Decomposes a high-level VFX goal into ordered sub-goals with dependency
tracking and DAG validation. The planner uses a single LLM call to
break down the goal, then the agent executes sub-goals in topological order.

Part of Sprint C: Agent SDK v2.
"""

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("synapse.planner")


# ---------------------------------------------------------------------------
# deterministic_uuid — copied from synapse.core.determinism (agent SDK is
# standalone and should not depend on the Synapse package import path).
# Source: SYNAPSE/python/synapse/core/determinism.py
# ---------------------------------------------------------------------------

def deterministic_uuid(content: str, namespace: str = "") -> str:
    """Generate a deterministic UUID from content string.

    Uses SHA-256 truncated to 32 hex chars. Same input always produces
    the same output (He2025 compliance).
    """
    raw = f"{namespace}:{content}" if namespace else content
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

@dataclass
class SubGoal:
    """A single actionable step within a plan."""

    id: str
    description: str
    tools_hint: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    verification: str = ""
    max_retries: int = 2
    status: str = "pending"  # pending | running | completed | failed
    error: str = ""
    attempts: int = 0

    def to_dict(self) -> dict:
        """Serialize with sorted keys (He2025)."""
        return {
            "attempts": self.attempts,
            "depends_on": sorted(self.depends_on),
            "description": self.description,
            "error": self.error,
            "id": self.id,
            "max_retries": self.max_retries,
            "status": self.status,
            "tools_hint": sorted(self.tools_hint),
            "verification": self.verification,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SubGoal":
        """Deserialize from dict."""
        return cls(
            id=d["id"],
            description=d["description"],
            tools_hint=d.get("tools_hint", []),
            depends_on=d.get("depends_on", []),
            verification=d.get("verification", ""),
            max_retries=d.get("max_retries", 2),
            status=d.get("status", "pending"),
            error=d.get("error", ""),
            attempts=d.get("attempts", 0),
        )


@dataclass
class Plan:
    """A decomposed goal with ordered sub-goals."""

    goal: str
    sub_goals: list[SubGoal]
    created_at: float = field(default_factory=time.monotonic)
    goal_hash: str = ""

    def __post_init__(self):
        if not self.goal_hash:
            self.goal_hash = goal_hash(self.goal)

    def to_dict(self) -> dict:
        """Serialize with sorted keys (He2025)."""
        return {
            "created_at": self.created_at,
            "goal": self.goal,
            "goal_hash": self.goal_hash,
            "sub_goals": [sg.to_dict() for sg in self.sub_goals],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        """Deserialize from dict."""
        return cls(
            goal=d["goal"],
            sub_goals=[SubGoal.from_dict(sg) for sg in d.get("sub_goals", [])],
            created_at=d.get("created_at", 0.0),
            goal_hash=d.get("goal_hash", ""),
        )

    def pending_goals(self) -> list[SubGoal]:
        """Return sub-goals with status == 'pending'."""
        return [sg for sg in self.sub_goals if sg.status == "pending"]

    def next_ready(self) -> "SubGoal | None":
        """Return the first pending sub-goal whose dependencies are all completed."""
        completed_ids = {sg.id for sg in self.sub_goals if sg.status == "completed"}
        for sg in self.sub_goals:
            if sg.status == "pending":
                if all(dep in completed_ids for dep in sg.depends_on):
                    return sg
        return None


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def goal_hash(goal: str) -> str:
    """Content-based hash for checkpoint naming. Case-insensitive."""
    return deterministic_uuid(goal.strip().lower(), namespace="goal")


def validate_dag(sub_goals: list[SubGoal]) -> bool:
    """Validate no cycles in dependency graph using Kahn's algorithm.

    Returns True if valid DAG.
    Raises ValueError with cycle info if cycles detected.
    """
    if not sub_goals:
        return True

    ids = {sg.id for sg in sub_goals}

    # Check all dependencies reference valid IDs
    for sg in sub_goals:
        for dep in sg.depends_on:
            if dep not in ids:
                raise ValueError(
                    f"Sub-goal '{sg.description}' depends on unknown ID '{dep}'"
                )
            if dep == sg.id:
                raise ValueError(
                    f"Sub-goal '{sg.description}' has a self-reference dependency"
                )

    # Kahn's algorithm
    in_degree = {sg.id: 0 for sg in sub_goals}
    adjacency = {sg.id: [] for sg in sub_goals}

    for sg in sub_goals:
        for dep in sg.depends_on:
            adjacency[dep].append(sg.id)
            in_degree[sg.id] += 1

    queue = sorted([nid for nid, deg in in_degree.items() if deg == 0])
    visited = 0

    while queue:
        current = queue.pop(0)
        visited += 1
        for neighbor in sorted(adjacency[current]):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
        queue.sort()  # Stable ordering for determinism

    if visited != len(sub_goals):
        cycle_nodes = [nid for nid, deg in in_degree.items() if deg > 0]
        raise ValueError(
            f"Dependency cycle detected involving sub-goals: {cycle_nodes}"
        )

    return True


def topological_order(sub_goals: list[SubGoal]) -> list[SubGoal]:
    """Return sub-goals in valid execution order (respecting depends_on).

    Uses Kahn's algorithm with stable sort on ID for determinism.
    """
    if not sub_goals:
        return []

    validate_dag(sub_goals)

    id_to_goal = {sg.id: sg for sg in sub_goals}
    in_degree = {sg.id: 0 for sg in sub_goals}
    adjacency = {sg.id: [] for sg in sub_goals}

    for sg in sub_goals:
        for dep in sg.depends_on:
            adjacency[dep].append(sg.id)
            in_degree[sg.id] += 1

    queue = sorted([nid for nid, deg in in_degree.items() if deg == 0])
    result = []

    while queue:
        current = queue.pop(0)
        result.append(id_to_goal[current])
        for neighbor in sorted(adjacency[current]):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
        queue.sort()

    return result


# ---------------------------------------------------------------------------
# Plan Creation (LLM Call)
# ---------------------------------------------------------------------------

PLANNING_SYSTEM_PROMPT = """You are a VFX pipeline planner. Given a user's goal and the
current Houdini scene context, decompose the goal into 3-8 ordered sub-goals.

Return ONLY a JSON array of objects. No other text, no markdown fences.

Each object must have these fields:
- "description": what to do (natural language, specific and actionable)
- "tools_hint": list of Synapse tool names likely needed (e.g. ["synapse_execute", "synapse_inspect_node"])
- "depends_on": list of indices (0-based) of sub-goals that must complete first (empty list if none)
- "verification": how to check this sub-goal succeeded (e.g. "Node /stage/key_light exists and has exposure > 0")

Available tools: synapse_ping, synapse_scene_info, synapse_inspect_scene,
synapse_inspect_selection, synapse_inspect_node, synapse_execute,
synapse_render_preview, synapse_knowledge_lookup, synapse_project_setup,
synapse_memory_write, synapse_memory_query, synapse_memory_status,
synapse_tops_cook, synapse_tops_status, synapse_tops_diagnose,
synapse_tops_wedge, synapse_tops_work_items, synapse_tops_cook_stats,
synapse_capture_viewport, synapse_batch

Rules:
- Keep sub-goals atomic: each should be completable in 3-10 tool calls
- Always start with an inspection/orientation sub-goal
- End with a verification/validation sub-goal
- Dependencies form a DAG (no cycles)
- Be specific about node paths, parameter names, and expected values
"""


async def create_plan(client: Any, goal: str, scene_context: dict, model: str = "claude-opus-4-6-20250929") -> Plan:
    """Single LLM call to decompose goal into sub-goals.

    Args:
        client: Anthropic client instance.
        goal: The user's high-level goal.
        scene_context: Scene info dict from synapse_scene_info.
        model: Model to use for planning.

    Returns:
        A Plan with validated sub-goals in DAG order.
    """
    user_message = (
        f"GOAL: {goal}\n\n"
        f"SCENE CONTEXT:\n{json.dumps(scene_context, indent=2, default=str)}\n\n"
        "Decompose this goal into 3-8 sub-goals. Return ONLY a JSON array."
    )

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=PLANNING_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    response_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            response_text += block.text

    return parse_plan_response(response_text, goal)


def parse_plan_response(response_text: str, goal: str) -> Plan:
    """Extract JSON array from LLM response, build Plan.

    Handles: bare JSON array, markdown code fences, mixed text.
    Raises ValueError if parsing fails.
    """
    text = response_text.strip()

    # Try to extract from markdown code fences
    import re
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Find the JSON array
    bracket_start = text.find("[")
    bracket_end = text.rfind("]")
    if bracket_start == -1 or bracket_end == -1 or bracket_end <= bracket_start:
        raise ValueError(f"Couldn't find a JSON array in the planning response")

    json_text = text[bracket_start:bracket_end + 1]

    try:
        raw_goals = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in planning response: {e}")

    if not isinstance(raw_goals, list) or len(raw_goals) == 0:
        raise ValueError("Planning response must be a non-empty JSON array")

    # Build SubGoal list with deterministic IDs
    sub_goals = []
    id_map = {}  # index -> id mapping for depends_on resolution

    for i, raw in enumerate(raw_goals):
        description = raw.get("description", f"Step {i + 1}")
        sg_id = deterministic_uuid(description, namespace="subgoal")
        id_map[i] = sg_id
        sub_goals.append(SubGoal(
            id=sg_id,
            description=description,
            tools_hint=raw.get("tools_hint", []),
            depends_on=[],  # resolve after all IDs are known
            verification=raw.get("verification", ""),
        ))

    # Resolve index-based depends_on to ID-based
    for i, raw in enumerate(raw_goals):
        raw_deps = raw.get("depends_on", [])
        for dep_idx in raw_deps:
            if isinstance(dep_idx, int) and 0 <= dep_idx < len(sub_goals):
                sub_goals[i].depends_on.append(id_map[dep_idx])

    # Validate DAG
    validate_dag(sub_goals)

    return Plan(goal=goal, sub_goals=sub_goals)
