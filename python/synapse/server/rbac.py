"""
Synapse Role-Based Access Control (RBAC)

Per-user role enforcement for studio deployments.
Four roles (viewer/artist/lead/admin) with wildcard permission matching.

Local mode (default) skips RBAC entirely -- zero behavior change
for existing single-user setups.
"""

import fnmatch
import os
from enum import Enum
from typing import FrozenSet, Set


class Role(Enum):
    """User roles in ascending privilege order."""
    VIEWER = "viewer"     # Read-only: inspect, capture, query
    ARTIST = "artist"     # Read + write: create, edit, execute, render
    LEAD = "lead"         # Artist + user management
    ADMIN = "admin"       # Full access including server config


# ---------------------------------------------------------------------------
# Permission matrix
# ---------------------------------------------------------------------------
# Each role has an ALLOW set (with fnmatch wildcards) and a DENY set.
# Deny overrides allow. Roles are NOT cumulative by default -- each role
# defines its own full allow set for clarity and auditability.
# ---------------------------------------------------------------------------

# Read-only commands available to all roles including VIEWER
_VIEWER_COMMANDS: FrozenSet[str] = frozenset({
    "ping", "get_health", "get_help", "heartbeat",
    "get_parm", "get_scene_info", "get_selection",
    "get_stage_info", "get_usd_attribute",
    "context", "search", "recall",
    "capture_viewport",
    "knowledge_lookup",
    "inspect_selection", "inspect_scene", "inspect_node",
    "read_material",
    "validate_frame",
    "get_metrics", "router_stats", "list_recipes",
    "tops_get_work_items", "tops_get_dependency_graph", "tops_get_cook_stats",
    "tops_query_items",
    "tops_diagnose", "tops_pipeline_status",
    "memory_query", "memory_status",
})

# Write commands available to ARTIST and above
_ARTIST_COMMANDS: FrozenSet[str] = frozenset({
    "create_node", "delete_node", "connect_nodes",
    "set_parm", "set_keyframe",
    "execute_python", "execute_vex",
    "create_usd_prim", "modify_usd_prim", "set_usd_attribute",
    "reference_usd",
    "render", "render_settings", "wedge",
    "create_material", "assign_material",
    "add_memory", "decide",
    "batch_commands",
    "tops_cook_node", "tops_generate_items",
    "tops_configure_scheduler", "tops_cancel_cook", "tops_dirty_node",
    "tops_setup_wedge", "tops_batch_cook",
    "tops_cook_and_validate",
    "project_setup", "memory_write", "evolve_memory",
})

# User management commands available to LEAD and above
_LEAD_COMMANDS: FrozenSet[str] = frozenset({
    "manage_users",
    "list_sessions",
})

# Server configuration commands available to ADMIN only
_ADMIN_COMMANDS: FrozenSet[str] = frozenset({
    "server_config",
    "reload_config",
})


# Per-role allow sets (with wildcard patterns)
ROLE_PERMISSIONS: dict[str, tuple[FrozenSet[str], list[str]]] = {
    # (exact commands, wildcard patterns)
    "viewer": (_VIEWER_COMMANDS, ["inspect_*", "get_*", "tops_get_*", "tops_query_*"]),
    "artist": (
        _VIEWER_COMMANDS | _ARTIST_COMMANDS,
        ["inspect_*", "get_*", "tops_*", "memory_*"],
    ),
    "lead": (
        _VIEWER_COMMANDS | _ARTIST_COMMANDS | _LEAD_COMMANDS,
        ["inspect_*", "get_*", "tops_*", "memory_*", "manage_*", "list_*"],
    ),
    "admin": (
        _VIEWER_COMMANDS | _ARTIST_COMMANDS | _LEAD_COMMANDS | _ADMIN_COMMANDS,
        ["*"],  # Admin gets everything
    ),
}

# Per-role deny sets (overrides allow)
ROLE_DENIALS: dict[str, FrozenSet[str]] = {
    "viewer": frozenset({
        "execute_python", "execute_vex", "delete_node",
        "server_config", "manage_users", "reload_config",
    }),
    "artist": frozenset({
        "server_config", "manage_users", "reload_config",
    }),
    "lead": frozenset({
        "server_config", "reload_config",
    }),
    "admin": frozenset(),  # No denials for admin
}


def check_permission(role: Role, command: str) -> bool:
    """
    Check if a role is allowed to execute a command.

    Uses exact match first, then fnmatch wildcards. Deny set overrides allow.

    Args:
        role: The user's role
        command: The command type string (e.g. 'create_node')

    Returns:
        True if the role is permitted to execute the command
    """
    role_key = role.value

    # Check deny set first -- deny always wins
    denials = ROLE_DENIALS.get(role_key, frozenset())
    if command in denials:
        return False

    # Check exact match in allow set
    exact_commands, wildcard_patterns = ROLE_PERMISSIONS.get(role_key, (frozenset(), []))
    if command in exact_commands:
        return True

    # Check wildcard patterns
    for pattern in wildcard_patterns:
        if fnmatch.fnmatch(command, pattern):
            # Double-check the wildcard match isn't in the deny set
            # (already checked above, but defensive)
            return True

    return False


def get_role_permissions(role: Role) -> Set[str]:
    """
    Return the expanded exact permission set for a role.

    Does NOT expand wildcards (those match dynamically). Returns the
    explicit command set for inspection/debugging.

    Args:
        role: The role to inspect

    Returns:
        Set of explicitly permitted command strings
    """
    exact_commands, _ = ROLE_PERMISSIONS.get(role.value, (frozenset(), []))
    denials = ROLE_DENIALS.get(role.value, frozenset())
    return set(exact_commands) - set(denials)


def get_role_wildcard_patterns(role: Role) -> list[str]:
    """Return the wildcard patterns for a role."""
    _, patterns = ROLE_PERMISSIONS.get(role.value, (frozenset(), []))
    return list(patterns)


def is_rbac_enabled() -> bool:
    """
    Check if RBAC is enabled.

    RBAC is enabled when deploy mode is not 'local'.
    Local mode (default) skips RBAC entirely for backward compatibility.

    Returns:
        True if RBAC checks should be enforced
    """
    mode = os.environ.get("SYNAPSE_DEPLOY_MODE", "local").strip().lower()
    return mode != "local"


# Role hierarchy for comparison
_ROLE_HIERARCHY: dict[str, int] = {
    "viewer": 0,
    "artist": 1,
    "lead": 2,
    "admin": 3,
}


def role_at_least(role: Role, minimum: Role) -> bool:
    """
    Check if a role meets a minimum privilege level.

    Args:
        role: The user's current role
        minimum: The minimum required role

    Returns:
        True if role >= minimum in the hierarchy
    """
    return _ROLE_HIERARCHY.get(role.value, -1) >= _ROLE_HIERARCHY.get(minimum.value, 999)
