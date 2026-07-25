"""
RELAY-SOLARIS L2 — verifier for ``tool_audit``.

STRUCTURAL NOTE (FINDING F2): ``tool_audit`` is NOT a tool. Unlike the other
five it has no implementation module, no ``validate``/``plan``/``execute``, and
it is absent from ``synapse/mcp/tools/solaris/__init__.py``'s import list. What
exists is ``schema_tool_audit.py``: a Phase-2 *design document* holding a
``TOOL_AUDIT`` dict that maps 8 NodeFlow patterns to the tools that were
supposed to be built. There is no network for it to emit, so the
connected/composes/prim-count triad does not apply.

What IS verifiable, and what this module verifies, is whether the audit's
claims are TRUE: every tool the audit names as delivered must actually be
reachable from the live MCP tool registry. That turns a stale planning
document into a checkable contract -- and it is how this leg produced
FINDING F1 (all five Solaris tools are unregistered orphans).
"""

from __future__ import annotations

from typing import Any, Dict, List

from synapse.validation.solaris import verify_wiring_common as common

TOOL = "tool_audit"

#: The live MCP tool registry, the authority on what is actually reachable.
REGISTRY_PATH = (common._REPO / "python" / "synapse" / "mcp" / "_tool_registry.py")

#: The orphan tree's own package __init__, the authority on what it exports.
TOOLS_INIT = common.TOOLS_DIR / "__init__.py"

#: tool_audit has no implementation module. Pinned so that changes.
HAS_IMPLEMENTATION = False


def load_audit() -> Dict[str, Any]:
    """Load the TOOL_AUDIT design dict from schema_tool_audit.py."""
    return dict(common.load_tool("schema_tool_audit").TOOL_AUDIT)


def claimed_new_tools() -> List[str]:
    """Every tool name the audit claims as NEW/delivered."""
    names: List[str] = []
    for entry in load_audit().values():
        name = entry.get("new_tool")
        if name and name not in names:
            names.append(name)
    return sorted(names)


def registry_text() -> str:
    return REGISTRY_PATH.read_text(encoding="utf-8", errors="replace")


def verify_structure() -> Dict[str, Any]:
    """tool_audit's own shape: a document, not a tool."""
    checks: List[common.Check] = []

    impl = common.TOOLS_DIR / "tool_audit.py"
    checks.append(common.Check(
        "no_implementation_module", impl.exists() is HAS_IMPLEMENTATION,
        f"{impl.name} exists={impl.exists()} (pinned {HAS_IMPLEMENTATION}) -- "
        "tool_audit is a design document, not a tool (F2)",
    ))

    exported = TOOLS_INIT.read_text(encoding="utf-8", errors="replace")
    checks.append(common.Check(
        "not_exported_as_tool", "tool_audit" not in exported.split("__all__")[-1],
        "tool_audit is absent from the solaris package __all__, as expected",
    ))

    audit = load_audit()
    checks.append(common.Check(
        "audit_non_empty", len(audit) > 0, f"{len(audit)} patterns mapped",
    ))
    for key, entry in audit.items():
        checks.append(common.Check(
            f"{key}:has_action", bool(entry.get("action")),
            f"action={entry.get('action')!r}",
        ))
    return common.result(TOOL + ":structure", checks, tier="static")


def verify_registration() -> Dict[str, Any]:
    """Are the tools the audit claims actually registered? (F1 evidence.)"""
    text = registry_text()
    checks = [
        common.Check(f"registered[{name}]", name in text,
                     f"{name} {'found in' if name in text else 'ABSENT from'} "
                     f"_tool_registry.py")
        for name in claimed_new_tools()
    ]
    return common.result(TOOL + ":registration", checks, tier="static")


def unregistered_tools() -> List[str]:
    """The audit-claimed tools that no live MCP path can reach (F1)."""
    text = registry_text()
    return [n for n in claimed_new_tools() if n not in text]
