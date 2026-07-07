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

from synapse.mcp._tool_registry import TOOL_DEFS
from synapse.panel.bridge_adapter import _TOOL_TO_OPERATION

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
_VALID_MODES = (_MODE_STRICT, _MODE_STANDARD, _MODE_UNRESTRICTED)
_DEFAULT_MODE = _MODE_STANDARD

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


def resolve_mode() -> str:
    """Resolve the active worker tool mode from the environment.

    Read fresh each call so tests (and live config changes) take effect
    without reimport. Unknown values fall back to the safe default.
    """
    raw = os.environ.get(_ENV_VAR, "").strip().lower()
    if raw in _VALID_MODES:
        return raw
    return _DEFAULT_MODE


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

def is_tool_allowed_for_worker(tool_name: str) -> tuple[bool, str]:
    """Decide whether the autonomous worker may invoke ``tool_name``.

    Returns ``(allowed, reason)``. ``reason`` is a one-line human-readable
    explanation, suitable for surfacing back to the LLM so it can re-plan.

    Policy by mode (``SYNAPSE_WORKER_TOOL_MODE``):

      * ``unrestricted`` -- allow everything (restores pre-gate behavior for
        single-user-localhost operators who accept the risk).
      * ``strict`` -- allow read-only tools (and group knowledge) only.
      * ``standard`` (default) -- allow read-only tools, group knowledge, and
        tools whose derived gate is 'inform'. DENY anything gated
        review/approve/critical (execute_python, execute_vex, delete_node,
        renders, exports, prunes, pdg cooks) and any UNKNOWN tool
        (fail-closed).
    """
    mode = resolve_mode()

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
            f"gate '{gate}' requires human review -- denied to the autonomous "
            "worker (no human-in-the-loop on this path)"
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
            f"Tool '{tool_name}' is not permitted for the autonomous worker: "
            f"{reason}. Choose a different, lower-privilege approach."
        ),
        "is_error": True,
    }
