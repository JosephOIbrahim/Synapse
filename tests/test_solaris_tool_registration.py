"""
SR1 M1 — the Solaris NodeFlow tool family is registered, and the one broken
member is gated.

Pins two things that L2 finding F1 showed nobody was checking:

1. Four of the five tools resolve through the canonical registry AND have a
   server-side handler. A registry entry with no handler is a lie (Law 3).
2. `synapse_solaris_import_megascans` is NOT reachable from any transport.
   CTO Ruling 13, on finding F9 (REFUTED-LIVE on 22.0.368): it calls
   createNode() into a locked `componentgeometry` HDA and raises
   hou.PermissionError on every invocation, after partial state exists.

HOW THESE FAIL (Constitution Law 1 — state the failing condition):
  - test_active_* fail if a tool is dropped from TOOL_DEFS, renamed, or loses
    its handler method / reg.register line.
  - test_import_megascans_is_gated fails the moment anyone adds
    import_megascans to TOOL_DEFS or calls reg.register on it -- which is
    exactly the promotion a later mile must make deliberately, together with
    the F9+F3 repair and its live verifier.
  - test_gated_entry_is_shaped_like_a_real_entry fails if the pending tuple
    drifts out of the 8-field TOOL_DEFS shape, i.e. if promotion would break.

No `hou` is imported here. These are structural assertions about reachability,
not host-behaviour assertions -- mock-`hou` is neither used nor needed.
"""

import ast
import inspect
from pathlib import Path

import pytest

from synapse.mcp import _tool_registry as reg_mod


ACTIVE_TOOLS = {
    "synapse_solaris_component_builder": "solaris_component_builder",
    "synapse_solaris_scene_template": "solaris_scene_template",
    "synapse_solaris_create_variants": "solaris_create_variants",
    "synapse_solaris_set_purpose": "solaris_set_purpose",
}

GATED_TOOL = "synapse_solaris_import_megascans"
GATED_COMMAND = "solaris_import_megascans"

_HANDLERS_PY = Path(reg_mod.__file__).resolve().parents[1] / "server" / "handlers.py"


def _registered_commands() -> set[str]:
    """Every command string passed to reg.register(...) in handlers.py.

    Read from the source with ast rather than by instantiating the handler,
    which would require a live `hou`. The string literal is the fact under
    test, so reading the literal is the honest measurement.
    """
    tree = ast.parse(_HANDLERS_PY.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "register"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            found.add(node.args[0].value)
    return found


# ---------------------------------------------------------------------------
# The four that ship
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool_name,command", sorted(ACTIVE_TOOLS.items()))
def test_active_tool_is_in_the_registry(tool_name, command):
    assert tool_name in reg_mod.TOOL_NAMES
    assert tool_name in reg_mod.TOOL_JSON
    assert reg_mod.TOOL_DISPATCH[tool_name][0] == command


@pytest.mark.parametrize("tool_name", sorted(ACTIVE_TOOLS))
def test_active_tool_has_a_usable_input_schema(tool_name):
    schema = reg_mod.TOOL_JSON[tool_name]["inputSchema"]
    assert schema["type"] == "object"
    assert schema["properties"], f"{tool_name} advertises no parameters"
    for key in schema.get("required", []):
        assert key in schema["properties"], (
            f"{tool_name} requires '{key}' but does not declare it"
        )


@pytest.mark.parametrize("command", sorted(ACTIVE_TOOLS.values()))
def test_active_tool_has_a_handler_and_is_wired(command):
    """A registry entry with no handler is a lie."""
    from synapse.server.handlers_solaris_tools import SolarisToolsMixin

    assert hasattr(SolarisToolsMixin, f"_handle_{command}")
    assert command in _registered_commands(), (
        f"{command} is advertised by the registry but never reg.register()ed"
    )


def test_tool_modules_live_inside_the_installable_package():
    """L2 F1: the family used to sit in a repo-root shadow tree."""
    from synapse.mcp.tool_impls import solaris

    pkg = Path(solaris.__file__).resolve().parent
    assert pkg.parts[-4:] == ("synapse", "mcp", "tool_impls", "solaris"), pkg
    for name in ("component_builder", "create_variants", "import_megascans",
                 "scene_template", "set_purpose"):
        mod = __import__(f"synapse.mcp.tool_impls.solaris.{name}", fromlist=[name])
        for entry in ("validate", "plan", "execute"):
            assert callable(getattr(mod, entry)), f"{name}.{entry} missing"


# ---------------------------------------------------------------------------
# The one that does not (Ruling 13 / F9)
# ---------------------------------------------------------------------------

def test_import_megascans_is_gated():
    assert GATED_TOOL not in reg_mod.TOOL_NAMES
    assert GATED_TOOL not in reg_mod.TOOL_DISPATCH
    assert GATED_TOOL not in reg_mod.TOOL_JSON
    assert GATED_TOOL not in {t["name"] for t in reg_mod.TOOLS_LIST_CACHE}
    assert GATED_COMMAND not in _registered_commands(), (
        "import_megascans became reachable on the /synapse path. Ruling 13 "
        "requires F9 + F3 repaired and live-verified on 22.0.368 first."
    )


def test_gate_names_its_reason():
    assert GATED_TOOL in reg_mod.PENDING_TOOL_NAMES
    reason = reg_mod.PENDING_TOOL_REASONS[GATED_TOOL]
    assert "Ruling 13" in reason and "F9" in reason


def test_gated_entry_is_shaped_like_a_real_entry():
    """Promotion must be a move, not a rewrite."""
    pending = {d[0]: d for d in reg_mod.PENDING_TOOL_DEFS}
    entry = pending[GATED_TOOL]
    assert len(entry) == len(reg_mod.TOOL_DEFS[0]) == 8
    name, command, builder, desc, schema, ro, destructive, idempotent = entry
    assert command == GATED_COMMAND
    assert callable(builder)
    assert isinstance(desc, str) and desc
    assert schema["type"] == "object"
    assert set(schema["required"]) <= set(schema["properties"])
    assert all(isinstance(f, bool) for f in (ro, destructive, idempotent))


def test_gated_names_never_overlap_active_names():
    assert not (set(reg_mod.PENDING_TOOL_NAMES) & set(reg_mod.TOOL_NAMES))


def test_gated_handler_exists_so_promotion_is_registration_only():
    from synapse.server.handlers_solaris_tools import SolarisToolsMixin

    handler = getattr(SolarisToolsMixin, f"_handle_{GATED_COMMAND}", None)
    assert handler is not None
    assert "NOT reachable" in (inspect.getdoc(handler) or "")
