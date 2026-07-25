"""
SR1 M5 — ALL FIVE Solaris NodeFlow tools are registered, and the exposed MCP
schema agrees with each implementation's accepted-parameter contract.

M1 pinned four-registered + one-gated. Ruling 13's gate on
`synapse_solaris_import_megascans` (L2 finding F9) is now discharged: F9
(createNode into the locked `componentgeometry` HDA) and F3 (orphaned material
Reference LOP) are repaired and proven by live 22.0.368 oracles in
tests/solaris/. This file pins the promotion with the same rigour it
previously pinned the gate.

HOW THESE FAIL (Constitution Law 1 — state the failing condition):
  - test_active_* fail if any of the five is dropped from TOOL_DEFS, renamed,
    or loses its handler method / reg.register line. import_megascans is now
    one of the five, so un-registering it is RED, not silent.
  - test_schema_matches_implementation_contract (C3) fails when a tool's
    advertised inputSchema properties diverge from its module KNOWN_PARAMS.
    That divergence is F8 at the MCP boundary: a caller passing `parent_path`
    through a `parent`-only schema gets neither the raise nor the parent it
    asked for -- it silently builds into /stage.
  - test_gate_mechanism_survives_the_promotion fails if PENDING_TOOL_DEFS is
    deleted or a pending entry leaks into dispatch: the mechanism must stay
    usable for the next gated tool.

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
    "synapse_solaris_import_megascans": "solaris_import_megascans",
}

PROMOTED_TOOL = "synapse_solaris_import_megascans"
PROMOTED_COMMAND = "solaris_import_megascans"

# tool name -> implementation module holding the KNOWN_PARAMS contract.
# create_variants / set_purpose define no KNOWN_PARAMS set (they take an
# explicit component_path, not a parent) and are excluded rather than faked.
CONTRACT_MODULES = {
    "synapse_solaris_component_builder": "component_builder",
    "synapse_solaris_scene_template": "scene_template",
    "synapse_solaris_import_megascans": "import_megascans",
}

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
# The five that ship
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
# C3 — the advertised schema must equal the accepted-parameter contract
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool_name,mod_name", sorted(CONTRACT_MODULES.items()))
def test_schema_matches_implementation_contract(tool_name, mod_name):
    """Ruling 15 convergence has to reach the MCP boundary, not stop at the impl.

    Fails if the schema advertises a key validate() would reject, or hides a
    key validate() accepts. Both directions are real bugs: the first makes a
    documented call raise `unknown parameter(s)`, the second makes a converged
    key (`parent_path`) unreachable through MCP, so the tool silently builds
    into /stage.
    """
    mod = __import__(f"synapse.mcp.tool_impls.solaris.{mod_name}",
                     fromlist=[mod_name])
    advertised = set(reg_mod.TOOL_JSON[tool_name]["inputSchema"]["properties"])
    accepted = set(mod.KNOWN_PARAMS)
    assert advertised == accepted, (
        f"{tool_name}: schema-only={sorted(advertised - accepted)}, "
        f"impl-only={sorted(accepted - advertised)}"
    )


@pytest.mark.parametrize("tool_name,mod_name", sorted(CONTRACT_MODULES.items()))
def test_converged_parent_key_is_advertised(tool_name, mod_name):
    """C3 named the concrete failure: `parent_path` absent from the schema."""
    mod = __import__(f"synapse.mcp.tool_impls.solaris.{mod_name}",
                     fromlist=[mod_name])
    assert mod.PARENT_KEYS[0] == "parent_path"
    props = reg_mod.TOOL_JSON[tool_name]["inputSchema"]["properties"]
    for key in mod.PARENT_KEYS:
        assert key in props, f"{tool_name} does not advertise {key}"


# ---------------------------------------------------------------------------
# The promotion (Ruling 13 / F9 + F3 discharged)
# ---------------------------------------------------------------------------

def test_import_megascans_is_registered():
    """The M1 gate, inverted. Ruling 13's condition is met and recorded."""
    assert PROMOTED_TOOL in reg_mod.TOOL_NAMES
    assert reg_mod.TOOL_DISPATCH[PROMOTED_TOOL][0] == PROMOTED_COMMAND
    assert PROMOTED_TOOL in reg_mod.TOOL_JSON
    assert PROMOTED_TOOL in {t["name"] for t in reg_mod.TOOLS_LIST_CACHE}
    assert PROMOTED_COMMAND in _registered_commands()
    assert PROMOTED_TOOL not in reg_mod.PENDING_TOOL_NAMES
    assert PROMOTED_TOOL not in reg_mod.PENDING_TOOL_REASONS


def test_all_five_resolve_through_the_registry():
    """Baton M1's oracle, now whole: all five, one path, no exceptions."""
    assert len(ACTIVE_TOOLS) == 5
    assert set(ACTIVE_TOOLS) <= set(reg_mod.TOOL_NAMES)


def test_gate_mechanism_survives_the_promotion():
    """Emptying the list must not delete the machinery the next gate needs."""
    assert isinstance(reg_mod.PENDING_TOOL_DEFS, list)
    assert isinstance(reg_mod.PENDING_TOOL_REASONS, dict)
    assert reg_mod.PENDING_TOOL_NAMES == sorted(
        d[0] for d in reg_mod.PENDING_TOOL_DEFS
    )
    for entry in reg_mod.PENDING_TOOL_DEFS:
        assert len(entry) == len(reg_mod.TOOL_DEFS[0]) == 8
        assert entry[0] not in reg_mod.TOOL_NAMES
        assert reg_mod.PENDING_TOOL_REASONS.get(entry[0]), (
            f"{entry[0]} is gated with no reason on record"
        )


def test_gated_names_never_overlap_active_names():
    assert not (set(reg_mod.PENDING_TOOL_NAMES) & set(reg_mod.TOOL_NAMES))


def test_promoted_handler_no_longer_advertises_itself_as_unreachable():
    from synapse.server.handlers_solaris_tools import SolarisToolsMixin

    handler = getattr(SolarisToolsMixin, f"_handle_{PROMOTED_COMMAND}", None)
    assert handler is not None
    assert "NOT reachable" not in (inspect.getdoc(handler) or "")
