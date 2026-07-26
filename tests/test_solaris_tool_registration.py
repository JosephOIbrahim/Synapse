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

H1 / Ruling 33 adds the RETURN half of the same contract. M5 pinned what goes
IN; nothing pinned what comes OUT, and `grep TOOL_RETURN` outside the schema
files found no consumers at all -- so the declared return contract could say
anything and no check disagreed.

  - test_schema_return_status_enum_matches_implementation fails when a tool's
    declared TOOL_RETURN status enum diverges from the statuses execute() can
    actually return, in EITHER direction. Both are real defects. A DECLARED
    status the code never emits (set_purpose's `already_set`, create_variants'
    `extended`) tells the model to branch on a value it will never see. An
    EMITTED status the schema never declares (`updated`, `unchanged`, `noop`)
    reaches the model unannounced. The schema is what the model is told a tool
    returns and it then reasons on that, so a drifted schema does not merely
    fail to document -- it actively misinforms. Correctness surface, not docs.
  - test_schema_return_keys_are_producible fails when TOOL_RETURN advertises a
    payload key that no return statement in execute() ever emits.
  - test_every_schema_return_contract_is_pinned fails when a sixth schema_*.py
    lands carrying TOOL_RETURN with nobody pinning it. Without it this file's
    coverage could silently stop covering, which is the R33 defect returning
    by a different door.
  - test_tool_audit_schema_declares_no_return_contract fails if tool_audit
    ever grows a TOOL_RETURN, an implementation module, or a registry entry.
    F2 established tool_audit is a Phase-2 design document and not a tool;
    that exclusion is asserted here rather than left as prose.

The expected status set is DERIVED FROM THE IMPLEMENTATION SOURCE and is never
written down in this file. A hand-copied literal would pin each schema against
this file's own opinion of the code: it would go red when a SCHEMA drifts but
stay green when an IMPLEMENTATION grows a new status -- which is exactly how
the drift under repair survived. Deriving it means a new `return {"status":
...}` inside execute() turns the pin red by itself (Ruling 34's mutation
standard). The derivation is deliberately strict: anything it cannot resolve
raises rather than returning a smaller set, because a silently-empty expected
set would make the comparison satisfiable and stop it being a check (Law 1).

Boundary note (VERIFIED-STATIC, handlers_solaris_tools.py:50): `_run_tool` is
`run_on_main(lambda: module.execute(params))` and every `_handle_solaris_*`
returns it verbatim -- no envelope, no exception-to-status conversion. So
TOOL_RETURN describes execute()'s dict exactly, which is why execute() is the
boundary these tests read.

No `hou` is imported here. These are structural assertions about reachability
and about declared contracts, not host-behaviour assertions -- mock-`hou` is
neither used nor needed. Reading the implementation with `ast` instead of
importing and calling it is the same choice `_registered_commands` makes
below: the source literal is the fact under test, so reading the literal is
the honest measurement, and it needs no live host.
"""

import ast
import importlib
import inspect
from pathlib import Path

import pytest

from synapse.mcp import _tool_registry as reg_mod
from synapse.mcp.tool_impls import solaris as _solaris_pkg


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


# ---------------------------------------------------------------------------
# R33 — the declared TOOL_RETURN contract must equal what execute() returns
# ---------------------------------------------------------------------------

_SOLARIS_DIR = Path(_solaris_pkg.__file__).resolve().parent

# The five REAL tools: each has a schema_*.py declaring TOOL_RETURN AND an
# implementation module exposing execute(). `tool_audit` is deliberately
# absent -- F2 established it is a Phase-2 design document with no
# validate/plan/execute and no implementation module, so there is nothing for
# a return contract to be checked against.
# test_tool_audit_schema_declares_no_return_contract asserts that exclusion
# rather than assuming it, and test_every_schema_return_contract_is_pinned
# stops this tuple from silently falling behind the directory.
RETURN_CONTRACT_TOOLS = (
    "component_builder",
    "create_variants",
    "import_megascans",
    "scene_template",
    "set_purpose",
)


class SchemaContractUnreadable(AssertionError):
    """The return contract could not be derived from the source.

    Deliberately an AssertionError so the pin goes RED. The failure mode this
    guards against is the derivation quietly returning a SMALLER set when it
    meets a shape it does not understand: the enum comparison would then be
    measuring the reader's blind spot rather than the code, and would pass for
    the wrong reason. Law 1 -- a check that cannot fail is a decoration, and a
    check that fails OPEN is worse than one that fails closed.
    """


def _execute_fn(mod_name: str) -> ast.FunctionDef:
    """The module-level `execute` of a Solaris tool, as AST."""
    path = _SOLARIS_DIR / f"{mod_name}.py"
    if not path.exists():
        raise SchemaContractUnreadable(f"no implementation module at {path}")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "execute":
            return node
    raise SchemaContractUnreadable(
        f"{mod_name}.py declares no module-level execute()"
    )


def _own_returns(fn: ast.FunctionDef):
    """Every `return` belonging to `fn` itself.

    Does not descend into a nested def/lambda: those returns belong to the
    inner callable, not to execute(), and counting them would attribute a
    status to a contract that never carries it.
    """
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Return):
            yield node
        stack.extend(ast.iter_child_nodes(node))


def _string_values(node, where: str) -> set:
    """Every string literal `node` can evaluate to.

    Handles the ternary the status field is actually written with in
    set_purpose (`"unchanged" if ... else "updated" if ... else "set"`), which
    carries three reachable values in one expression. Anything else raises: a
    computed status (an f-string, a dict lookup, a bare name) cannot be
    resolved from source, and guessing would be inventing the contract.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.IfExp):
        return (_string_values(node.body, where)
                | _string_values(node.orelse, where))
    raise SchemaContractUnreadable(
        f"{where}: status is not a resolvable string literal "
        f"({type(node).__name__} at line {getattr(node, 'lineno', '?')}). "
        "Keep the status a literal, or teach this reader the new shape."
    )


def _implemented_return_contract(mod_name: str):
    """(status values, payload keys) execute() can hand back, read from source.

    NOT read from the schema. The schema is the thing under test.
    """
    fn = _execute_fn(mod_name)
    statuses = set()
    keys = set()
    seen_returns = 0

    for ret in _own_returns(fn):
        where = f"{mod_name}.execute() line {ret.lineno}"
        if ret.value is None:
            raise SchemaContractUnreadable(
                f"{where}: bare `return` yields None, which no TOOL_RETURN "
                "can describe"
            )
        if not isinstance(ret.value, ast.Dict):
            raise SchemaContractUnreadable(
                f"{where}: returns {type(ret.value).__name__}, not a dict "
                "literal -- the return contract cannot be read from source"
            )
        seen_returns += 1
        status_expr = None
        for key, val in zip(ret.value.keys, ret.value.values):
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                raise SchemaContractUnreadable(
                    f"{where}: non-literal key in the returned dict"
                )
            keys.add(key.value)
            if key.value == "status":
                status_expr = val
        if status_expr is None:
            raise SchemaContractUnreadable(
                f"{where}: returned dict carries no 'status' key"
            )
        statuses |= _string_values(status_expr, where)

    if not seen_returns:
        raise SchemaContractUnreadable(
            f"{mod_name}.execute() has no return statement at all"
        )
    if not statuses:
        raise SchemaContractUnreadable(
            f"{mod_name}.execute() yielded an empty status set"
        )
    return statuses, keys


def _declared_return_properties(mod_name: str) -> dict:
    """The TOOL_RETURN properties a schema module advertises to the model."""
    mod = importlib.import_module(
        f"synapse.mcp.tool_impls.solaris.schema_{mod_name}"
    )
    declared = getattr(mod, "TOOL_RETURN", None)
    if not isinstance(declared, dict):
        raise SchemaContractUnreadable(
            f"schema_{mod_name}.py declares no TOOL_RETURN dict"
        )
    props = declared.get("properties")
    if not isinstance(props, dict):
        raise SchemaContractUnreadable(
            f"schema_{mod_name}.TOOL_RETURN declares no properties"
        )
    return props


@pytest.mark.parametrize("mod_name", RETURN_CONTRACT_TOOLS)
def test_schema_return_status_enum_matches_implementation(mod_name):
    """R33: the advertised status enum IS the set execute() can return.

    Fails when the two diverge in either direction. Demonstrated RED before
    the repair on BOTH drifted schemas: set_purpose declared
    [set, already_set, not_found] against an implementation returning
    set/updated/unchanged/noop/not_found, and create_variants declared an
    `extended` it has never emitted.
    """
    props = _declared_return_properties(mod_name)
    status = props.get("status")
    if not isinstance(status, dict) or "enum" not in status:
        raise SchemaContractUnreadable(
            f"schema_{mod_name}.TOOL_RETURN.properties.status declares no enum"
        )
    declared = set(status["enum"])
    implemented, _ = _implemented_return_contract(mod_name)

    assert declared == implemented, (
        f"{mod_name}: TOOL_RETURN status enum has drifted from execute().\n"
        f"  declared but never returned: {sorted(declared - implemented)}\n"
        f"  returned but never declared: {sorted(implemented - declared)}\n"
        "The schema is what the model is told this tool returns. Fix the "
        "schema to match the implementation, not the reverse."
    )


@pytest.mark.parametrize("mod_name", RETURN_CONTRACT_TOOLS)
def test_schema_return_keys_are_producible(mod_name):
    """Every advertised payload key must be one execute() can actually emit.

    One direction only, and deliberately so. A DECLARED key nothing returns is
    unambiguously drift -- the model is promised a field it will never get.
    The reverse (a returned key the schema omits) is a design question about
    which fields are contract and which are incidental; Article I sends that
    to for_ruling rather than deciding it here.
    """
    declared = set(_declared_return_properties(mod_name))
    _, producible = _implemented_return_contract(mod_name)

    assert declared <= producible, (
        f"{mod_name}: TOOL_RETURN advertises key(s) execute() never emits: "
        f"{sorted(declared - producible)}"
    )


def test_every_schema_return_contract_is_pinned():
    """A new schema declaring TOOL_RETURN cannot arrive unpinned.

    R33's defect was not one bad enum -- it was ZERO consumers. Fixing five
    enums while leaving a sixth schema free to drift would rebuild the same
    hole. Fails the day a schema_*.py gains a TOOL_RETURN without an entry in
    RETURN_CONTRACT_TOOLS, or the day a pinned one leaves the directory.
    """
    on_disk = {
        path.stem[len("schema_"):]
        for path in _SOLARIS_DIR.glob("schema_*.py")
        if "TOOL_RETURN" in path.read_text(encoding="utf-8")
    }
    assert on_disk == set(RETURN_CONTRACT_TOOLS), (
        f"unpinned schema return contracts: "
        f"{sorted(on_disk - set(RETURN_CONTRACT_TOOLS))}; "
        f"pinned but gone from disk: "
        f"{sorted(set(RETURN_CONTRACT_TOOLS) - on_disk)}"
    )


def test_tool_audit_schema_declares_no_return_contract():
    """F2: tool_audit is a Phase-2 design document, not a tool.

    It has no validate/plan/execute and no implementation module, so it has no
    return contract to check and is excluded from the pins above. Asserting it
    here makes the exclusion falsifiable: red the day someone gives tool_audit
    a TOOL_RETURN, an implementation, or a registry entry -- any of which
    would make it a tool the pins are silently not covering.
    """
    audit = _SOLARIS_DIR / "schema_tool_audit.py"
    assert audit.exists(), "schema_tool_audit.py vanished -- F2 needs restating"
    assert "TOOL_RETURN" not in audit.read_text(encoding="utf-8"), (
        "schema_tool_audit.py now declares a return contract; if tool_audit "
        "became a tool it needs an implementation and a pin, and if it did "
        "not, that declaration is exactly the unconsumed schema R33 removed"
    )
    assert not (_SOLARIS_DIR / "tool_audit.py").exists(), (
        "an implementation module appeared -- F2's premise no longer holds"
    )
    assert "synapse_solaris_tool_audit" not in reg_mod.TOOL_NAMES
    assert "synapse_solaris_tool_audit" not in reg_mod.PENDING_TOOL_NAMES
