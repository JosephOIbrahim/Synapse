"""
Worker Tool Policy -- ALLOWLIST gate for the autonomous panel worker.

The autonomous ClaudeWorker runs an LLM tool-use loop with no human in the
loop. Left unfiltered it arms the FULL registry tool set, including
``execute_python``/``execute_vex`` (arbitrary code) and destructive ops
(``delete_node``, renders, exports). The threat here is the LLM's own
autonomy, not a remote attacker -- so we filter ALWAYS, regardless of deploy
mode.

This module is the single source of truth for "may the worker use tool X?".
It builds its classification index from EXISTING data -- it invents no new
classification:

  * ``read_only`` / ``destructive`` flags from
    ``synapse.mcp._tool_registry.TOOL_DEFS``
  * a derived gate level per tool: ``bridge_adapter._TOOL_TO_OPERATION``
    maps tool -> operation_type, then ``shared.constants.OPERATION_GATES``
    maps operation_type -> gate ('inform'|'review'|'approve'|'critical').

Pure Python. Zero hou/Qt imports -- safe to import headlessly.
"""

from __future__ import annotations

import os
from copy import deepcopy

from synapse.mcp._tool_registry import TOOL_DEFS
from synapse.panel.bridge_adapter import _TOOL_TO_OPERATION
from synapse.recipes.contracts import RUN_RECIPE_TOOL_NAME
from synapse.recipes.authority import RUN_RECIPE_INPUT_SCHEMA

# OPERATION_GATES is the canonical op-name -> gate map. Import directly from
# the constants module (single source) rather than re-deriving.
try:
    from shared.constants import OPERATION_GATES
except ImportError:  # pragma: no cover - shared/ always on path in this repo
    OPERATION_GATES = {}


# =========================================================================
# Env-resolved policy mode
# =========================================================================

_ENV_VAR = "SYNAPSE_WORKER_TOOL_MODE"
_MODE_STRICT = "strict"
_MODE_STANDARD = "standard"
_MODE_UNRESTRICTED = "unrestricted"
_MODE_DEMO = "demo"
_VALID_MODES = (_MODE_STRICT, _MODE_STANDARD, _MODE_UNRESTRICTED, _MODE_DEMO)
_DEFAULT_MODE = _MODE_STANDARD
_PROFILE_ENV_VAR = "SYNAPSE_WORKER_TOOL_PROFILE"

# Knowledge-tool prefix: the 6 ``synapse_group_*`` tools have no TOOL_DEFS
# entry. They are read-only knowledge lookups (a description string back to
# the LLM, no mutation) -> always allowed.
_GROUP_PREFIX = "synapse_group_"

# Gate levels that DENY under 'standard' mode (anything riskier than 'inform').
_DENIED_GATES = frozenset({"review", "approve", "critical"})

# Composite Solaris BUILDERS the autonomous worker may emit despite their
# derived 'review' gate (build_from_manifest). Rationale (L4, signed off
# 2026-06-25): each is ONE undo-wrapped call composed entirely of inform-level
# primitives (create_node, connect_nodes, set_parameter) -- the same ops the
# worker is already permitted to do one at a time. Allowing the composite
# collapses a 25-turn imperative build (which hit the iteration cap without
# finishing) into ONE turn + ONE cook, granting NO capability the worker did
# not already have. Deliberately EXCLUDES execute_python/vex, delete, render,
# and export -- those stay gated. Scoped to standard mode (strict stays
# read-only-only). Does NOT touch the bridge /mcp consent gate (OPERATION_GATES).
_WORKER_BUILDER_ALLOWLIST = frozenset({
    "synapse_solaris_build_graph",
    "synapse_solaris_assemble_chain",
})


def resolve_mode(profile: str | None = None) -> str:
    """Resolve the active worker tool mode from the environment.

    Read fresh each call so tests (and live config changes) take effect
    without reimport. Only an ABSENT setting uses the legacy default.
    Explicit invalid values and conflicting profile selections fail closed.
    ``profile`` is a trusted host constraint; an environment setting cannot
    override it. The optional profile environment variable uses the same
    vocabulary as the mode (there was no legacy profile selector).
    """
    selections = [value for value in (
        profile, os.environ.get(_PROFILE_ENV_VAR), os.environ.get(_ENV_VAR)
    ) if value is not None]
    if not selections:
        return _DEFAULT_MODE
    normalized = [value.strip().lower() if isinstance(value, str) else ""
                  for value in selections]
    if any(value not in _VALID_MODES for value in normalized):
        return _MODE_STRICT
    if len(set(normalized)) != 1:
        return _MODE_STRICT
    return normalized[0]


# =========================================================================
# Classification index (built once from existing data)
# =========================================================================

def _build_index() -> dict[str, dict]:
    """Map tool_name -> {'read_only': bool, 'gate': str|None} from TOOL_DEFS."""
    index: dict[str, dict] = {}
    for entry in TOOL_DEFS:
        name, _cmd, _builder, _desc, _schema, read_only, _destr, _idemp = entry
        op = _TOOL_TO_OPERATION.get(name)
        gate = OPERATION_GATES.get(op) if op else None
        index[name] = {"read_only": bool(read_only), "gate": gate}
    return index


_TOOL_INDEX: dict[str, dict] = _build_index()


# =========================================================================
# Public API
# =========================================================================

def demo_tool_definitions() -> list[dict]:
    """Demo advertisement; transport/registry registration is an integrator hookup."""
    reads = [{"name": entry[0], "description": entry[3], "input_schema": deepcopy(entry[4])}
             for entry in TOOL_DEFS
             if entry[5] and not entry[0].startswith(_GROUP_PREFIX) and entry[0] != RUN_RECIPE_TOOL_NAME]
    return reads + [{"name": RUN_RECIPE_TOOL_NAME,
                     "description": "Propose one declared Solaris recipe action. Render requires trusted human approval.",
                     "input_schema": deepcopy(RUN_RECIPE_INPUT_SCHEMA)}]


def is_tool_allowed_for_worker(tool_name: str, *, profile: str | None = None) -> tuple[bool, str]:
    """Decide whether the autonomous worker may invoke ``tool_name``.

    Returns ``(allowed, reason)``. ``reason`` is a one-line human-readable
    explanation, suitable for surfacing back to the LLM so it can re-plan.

    Policy by mode (``SYNAPSE_WORKER_TOOL_MODE``):

      * ``demo`` -- registered reads and the constrained recipe proposal only;
        group composites, generic mutation and unknown tools are denied.
      * ``unrestricted`` -- allow everything (restores pre-gate behavior for
        single-user-localhost operators who accept the risk).
      * ``strict`` -- allow read-only tools (and group knowledge) only.
      * ``standard`` (default) -- allow read-only tools, group knowledge, and
        tools whose derived gate is 'inform'. DENY anything gated
        review/approve/critical (execute_python, execute_vex, delete_node,
        renders, exports, prunes, pdg cooks) and any UNKNOWN tool
        (fail-closed).
    """
    mode = resolve_mode(profile)

    if mode == _MODE_DEMO:
        # This check precedes BOTH the legacy group exception and builder
        # allowlist. Advertising a tool (or bypassing that filter) grants no
        # authority. The one proposal interface validates again at the host.
        if tool_name == RUN_RECIPE_TOOL_NAME:
            return True, "demo mode: constrained recipe proposal"
        info = _TOOL_INDEX.get(tool_name)
        if not tool_name.startswith(_GROUP_PREFIX) and info and info["read_only"]:
            return True, "demo mode: registered read-only tool"
        return False, "demo mode: only registered reads and recipe proposals permitted"

    if mode == _MODE_UNRESTRICTED:
        return True, "unrestricted mode: all tools permitted"

    # Group knowledge tools are read-only by construction (no TOOL_DEFS entry).
    if tool_name.startswith(_GROUP_PREFIX):
        return True, "read-only knowledge group tool"

    info = _TOOL_INDEX.get(tool_name)
    if info is None:
        # Not in the registry and not a group tool -> fail closed.
        return False, "unknown tool (not in registry): denied by fail-closed policy"

    if info["read_only"]:
        return True, "read-only tool"

    # strict mode: nothing beyond read-only / knowledge.
    if mode == _MODE_STRICT:
        return False, "strict mode: only read-only tools permitted"

    # standard mode: explicit allowlist for the composite Solaris builders (L4).
    # 'review'-gated by derivation, but composites of inform-level, undo-wrapped
    # primitives -- see _WORKER_BUILDER_ALLOWLIST. Reached only for known
    # (registry) tools (the info-None fail-closed above already returned).
    if tool_name in _WORKER_BUILDER_ALLOWLIST:
        return True, ("composite Solaris builder (inform-level primitives, "
                      "undo-wrapped): permitted")

    # standard mode: gate-based.
    gate = info["gate"]
    if gate == "inform":
        return True, "inform-level mutation: permitted"
    if gate in _DENIED_GATES:
        return False, (
            f"gate '{gate}' requires human review -- the panel worker may not "
            "perform this op itself; do it in the native Houdini UI (or via a "
            "bridge /mcp consent-gated call)"
        )
    # Non-read-only tool with no derivable gate -> fail closed.
    return False, "unclassified mutation (no gate mapping): denied by fail-closed policy"


def denial_tool_result(tool_use_id: str, tool_name: str, reason: str) -> dict:
    """Build an Anthropic ``tool_result`` block reporting a policy denial.

    The LLM sees ``is_error=True`` + the reason, so it can re-plan rather than
    silently retry. The denied tool is NOT dispatched.
    """
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": (
            f"Tool '{tool_name}' is not permitted for the panel worker: "
            f"{reason}. Choose a different, lower-privilege approach."
        ),
        "is_error": True,
    }
