"""
H1 / CTO Ruling 33 — a tool's declared ``TOOL_RETURN`` status enum must equal
the set of status values its ``execute()`` can actually return.

WHY THIS IS A CORRECTNESS SURFACE, NOT DOCUMENTATION
----------------------------------------------------
``TOOL_RETURN`` is what the MODEL is told a tool gives back, and the model then
reasons on it — branches on it, reports it to the artist, decides whether to
retry. A drifted enum does not merely fail to document the tool; it actively
misinforms the caller about what it will receive. R33 found the whole
``schema_*.py`` family had ZERO consumers (``grep TOOL_RETURN`` outside the
schema files returned nothing), so ``set_purpose`` was free to drift from
``[set, already_set, not_found]`` to an implementation returning
``set|updated|unchanged|noop|not_found`` with nothing going red.

This file is that missing consumer.

HOW THESE FAIL (Constitution Law 1 — state the condition or it is a decoration)
-------------------------------------------------------------------------------
The pin is DERIVED, never transcribed. ``_status_contract_from_source`` reads
each implementation's ``execute()`` with ``ast`` and reports the status literals
it can actually return. Nothing here hardcodes an expected return set, so the
pin goes red from either direction:

  - Add, rename, or delete a ``"status"`` literal in any ``execute()`` and
    ``test_schema_status_enum_matches_implementation`` goes red for that tool
    until its schema is reconciled. This is the R34 mutation direction, and it
    was exercised against a deliberately broken implementation for all five —
    see ``harness/notes/receipts/H1.json``.
  - Edit a ``TOOL_RETURN`` enum away from what the code returns and the same
    test goes red. This is the direction that was live-drifted on arrival:
    ``set_purpose`` (3 declared vs 5 real) and ``create_variants``
    (``extended`` declared, never emitted) both failed here BEFORE their
    schemas were fixed.
  - Make a status undecidable — return a bare name, build the dict with ``**``
    unpacking, return a non-dict — and the reader RAISES rather than quietly
    pinning a smaller set. "I cannot read this" is a failure, not a pass.
  - Break the reader itself and its own calibration controls
    (``test_reader_recovers_*`` / ``test_reader_refuses_*``) go red. The
    instrument is checked before it is trusted, which is the paired negative
    control ``probe_phase3_layout`` was faulted for lacking.

WHY ``ast`` AND NOT A CALL
--------------------------
Calling ``execute()`` needs a live ``hou``; driving it with a ``MagicMock``
``hou`` is banned by Law 1 for host-behaviour assertions — it would assert our
assumptions back at us. The status literal in the source IS the fact under
test, so reading the literal is the honest measurement. Same idiom, and the
same reason, as ``test_solaris_tool_registration._registered_commands``.

SCOPE — WHAT THIS DELIBERATELY DOES NOT PIN
-------------------------------------------
``TOOL_RETURN["properties"]`` is pinned in ONE direction only: every declared
property must be emittable (``test_declared_return_properties_are_emittable``).
The reverse — every emitted key must be declared — is NOT asserted, and the
asymmetry is deliberate rather than lazy. JSON Schema ``properties`` is an open
map (no ``additionalProperties: false`` here), so an emitted-but-undeclared key
leaves the schema TRUE and merely under-documented. A declared-but-never-emitted
property makes the schema FALSE, which is the same defect class as the enum
drift. Only the false direction is pinned. The undeclared extras that exist
today (``strategy``, ``primitive_paths``, ``message``, ``reason``,
``configure_node``, ``prim_path``, ``usd_purpose``) are recorded as a finding in
the H1 receipt, not silently fixed here.

``schema_tool_audit`` is excluded, with evidence rather than by omission —
see ``test_tool_audit_is_a_design_document_not_a_tool``.

No ``hou`` is imported. These are structural assertions about source text.
"""

import ast
from pathlib import Path

import pytest

from synapse.mcp.tool_impls import solaris as _solaris_pkg


_PKG = Path(_solaris_pkg.__file__).resolve().parent

# The five REAL tools. Each has an implementation module `<name>.py` exposing
# validate/plan/execute, and a schema module `schema_<name>.py` exposing
# TOOL_RETURN. `tool_audit` is NOT here: it is a Phase-2 design document with
# neither, pinned as such below.
TOOLS = (
    "component_builder",
    "create_variants",
    "import_megascans",
    "scene_template",
    "set_purpose",
)

EXCLUDED_DESIGN_DOC = "tool_audit"


class UnreadableStatus(AssertionError):
    """The reader met a return shape it will not reduce to string literals.

    Subclasses ``AssertionError`` deliberately: a return the reader cannot
    decode is a FAILED pin, not an infrastructure hiccup. The alternative —
    skipping it and reporting the smaller set that remains — is precisely the
    D1 defect: a measurement that shrinks silently while still reporting green.
    """


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------

def _execute_fn(src: str, label: str) -> ast.FunctionDef:
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == "execute":
            return node
    raise UnreadableStatus(f"{label}: no module-level execute() to read")


def _string_literals(node: ast.AST, label: str, lineno: int) -> set:
    """Reduce a ``status`` value expression to the strings it can evaluate to.

    Handles plain literals and conditionals over literals — ``set_purpose``
    returns a nested ternary. Anything else raises: guessing at a computed
    status is how a contract test starts agreeing with whatever it finds.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.IfExp):
        return (_string_literals(node.body, label, lineno)
                | _string_literals(node.orelse, label, lineno))
    raise UnreadableStatus(
        f"{label} line {lineno}: 'status' is a {type(node).__name__}, not a "
        f"string literal or a conditional over string literals. The reader "
        f"will not guess. Return a literal status, or teach _string_literals "
        f"this shape on purpose."
    )


def _return_dicts(src: str, label: str) -> list:
    """[(lineno, declared_keys, status_value_node)] for every return in execute().

    ``ast.walk`` descends into nested definitions on purpose. A nested helper
    that returns a non-dict will raise here rather than be skipped: loud and
    wrong beats quiet and shrinking. If that ever fires on an innocent
    refactor, hoist the helper to module scope — do not loosen the reader.
    """
    fn = _execute_fn(src, label)
    returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
    if not returns:
        raise UnreadableStatus(f"{label}: execute() contains no return statement")

    out = []
    for ret in returns:
        if ret.value is None:
            raise UnreadableStatus(
                f"{label} line {ret.lineno}: bare `return` yields None, which "
                f"carries no status at all."
            )
        if not isinstance(ret.value, ast.Dict):
            raise UnreadableStatus(
                f"{label} line {ret.lineno}: execute() returns a "
                f"{type(ret.value).__name__}, not a dict literal — the reader "
                f"cannot see what status it carries."
            )
        keys, status_node = set(), None
        for key, value in zip(ret.value.keys, ret.value.values):
            if key is None:
                raise UnreadableStatus(
                    f"{label} line {ret.lineno}: `**` unpacking hides keys the "
                    f"reader cannot enumerate."
                )
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                raise UnreadableStatus(
                    f"{label} line {ret.lineno}: non-literal dict key "
                    f"({type(key).__name__})."
                )
            keys.add(key.value)
            if key.value == "status":
                status_node = value
        if status_node is None:
            raise UnreadableStatus(
                f"{label} line {ret.lineno}: return dict declares no 'status' "
                f"key, so a caller branching on status gets a KeyError."
            )
        out.append((ret.lineno, keys, status_node))
    return out


def _status_contract_from_source(src: str, label: str) -> set:
    """Every status string ``execute()`` can return, read from source."""
    return set().union(*(
        _string_literals(node, label, lineno)
        for lineno, _keys, node in _return_dicts(src, label)
    ))


def _impl_source(tool: str) -> str:
    return (_PKG / f"{tool}.py").read_text(encoding="utf-8")


def status_contract(tool: str) -> set:
    return _status_contract_from_source(_impl_source(tool), f"{tool}.execute()")


def returned_keys(tool: str) -> set:
    return set().union(*(
        keys for _lineno, keys, _node in
        _return_dicts(_impl_source(tool), f"{tool}.execute()")
    ))


def _tool_return(tool: str) -> dict:
    name = f"schema_{tool}"
    mod = __import__(f"synapse.mcp.tool_impls.solaris.{name}", fromlist=[name])
    return mod.TOOL_RETURN


def declared_status_enum(tool: str) -> set:
    return set(_tool_return(tool)["properties"]["status"]["enum"])


# ---------------------------------------------------------------------------
# Anti-vacuity: neither side may be empty
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool", TOOLS)
def test_schema_declares_a_nonempty_status_enum(tool):
    """`set() == set()` would pass while pinning nothing. Guard both sides."""
    assert declared_status_enum(tool), (
        f"schema_{tool}.TOOL_RETURN declares an empty status enum"
    )


@pytest.mark.parametrize("tool", TOOLS)
def test_implementation_emits_a_nonempty_status_set(tool):
    """If the reader ever returns nothing, the match test passes vacuously."""
    assert status_contract(tool), (
        f"{tool}.execute() yielded no readable status literals"
    )


# ---------------------------------------------------------------------------
# The R33 pin
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool", TOOLS)
def test_schema_status_enum_matches_implementation(tool):
    """The declared enum IS the claim. It must equal what execute() emits.

    Fails when the schema advertises a status the tool cannot produce (the
    caller waits for a branch that never arrives) or hides one it does produce
    (the caller meets an undocumented status and has no branch for it). Both
    are live misinformation, not stale docs.
    """
    declared = declared_status_enum(tool)
    emitted = status_contract(tool)
    assert declared == emitted, (
        f"{tool}: schema declares {sorted(declared)}, execute() returns "
        f"{sorted(emitted)} — "
        f"declared-but-never-returned={sorted(declared - emitted)}, "
        f"returned-but-undeclared={sorted(emitted - declared)}"
    )


@pytest.mark.parametrize("tool", TOOLS)
def test_declared_return_properties_are_emittable(tool):
    """No fictional keys: a declared property must appear in some return.

    One direction only — see the module docstring. A declared key the tool
    never emits is a promise the caller can wait on forever.
    """
    declared = set(_tool_return(tool)["properties"])
    emitted = returned_keys(tool)
    assert declared <= emitted, (
        f"{tool}: TOOL_RETURN declares properties execute() never returns: "
        f"{sorted(declared - emitted)}"
    )


# ---------------------------------------------------------------------------
# The exclusion, evidenced rather than assumed (brief item 2 / finding F2)
# ---------------------------------------------------------------------------

def test_tool_audit_is_a_design_document_not_a_tool():
    """F2: `tool_audit` has no implementation, so it gets no return pin.

    Written as a test rather than a comment so the exclusion EXPIRES on its
    own: the day someone gives tool_audit a real implementation module, this
    goes red and says to add it to TOOLS. An exclusion nobody can notice
    becoming wrong is how a five-tool contract quietly becomes a four-tool one.
    """
    assert not (_PKG / f"{EXCLUDED_DESIGN_DOC}.py").exists(), (
        f"{EXCLUDED_DESIGN_DOC}.py now exists — it is a tool, not a design "
        f"document. Add it to TOOLS and give schema_{EXCLUDED_DESIGN_DOC} a "
        f"TOOL_RETURN."
    )
    name = f"schema_{EXCLUDED_DESIGN_DOC}"
    mod = __import__(f"synapse.mcp.tool_impls.solaris.{name}", fromlist=[name])
    assert not hasattr(mod, "TOOL_RETURN"), (
        f"{name} now declares TOOL_RETURN; if it returns anything it needs the "
        f"same pin as the other five."
    )
    assert EXCLUDED_DESIGN_DOC not in TOOLS


def test_every_pinned_tool_has_both_modules():
    """The `schema_<tool>.py` convention TOOLS relies on actually holds."""
    for tool in TOOLS:
        assert (_PKG / f"{tool}.py").exists(), f"{tool}.py missing"
        assert (_PKG / f"schema_{tool}.py").exists(), f"schema_{tool}.py missing"


# ---------------------------------------------------------------------------
# Reader calibration — the instrument is checked before it is trusted
# ---------------------------------------------------------------------------

_GOOD = '''
def execute(params):
    if params.get("a"):
        return {"status": "not_found", "message": "no"}
    return {"status": "created", "path": "/x"}
'''

_TERNARY = '''
def execute(params):
    return {"status": ("unchanged" if a else "updated" if b else "set")}
'''


def test_reader_recovers_a_known_status_set():
    """Positive control: a source whose answer we know independently."""
    assert _status_contract_from_source(_GOOD, "<good>") == {"not_found", "created"}


def test_reader_reads_nested_conditional_statuses():
    """set_purpose returns a nested ternary; missing a branch would under-pin."""
    assert _status_contract_from_source(_TERNARY, "<ternary>") == {
        "unchanged", "updated", "set",
    }


@pytest.mark.parametrize("label,src", [
    ("computed-status", 'def execute(p):\n    return {"status": _compute()}\n'),
    ("name-status", 'def execute(p):\n    return {"status": result}\n'),
    ("dict-unpacking", 'def execute(p):\n    return {**base, "status": "set"}\n'),
    ("no-status-key", 'def execute(p):\n    return {"path": "/x"}\n'),
    ("bare-return", 'def execute(p):\n    return\n'),
    ("non-dict-return", 'def execute(p):\n    return build(p)\n'),
    ("no-returns", 'def execute(p):\n    raise RuntimeError("x")\n'),
    ("no-execute", 'def plan(p):\n    return {"status": "set"}\n'),
    ("non-literal-key", 'def execute(p):\n    return {KEY: "set", "status": "a"}\n'),
])
def test_reader_refuses_what_it_cannot_read(label, src):
    """Negative controls: every shape the reader must refuse rather than guess.

    Without these the reader could regress into returning ``set()`` for an
    unparseable module and every match test would go green on nothing.
    """
    with pytest.raises(UnreadableStatus):
        _status_contract_from_source(src, f"<{label}>")


def test_reader_reads_the_real_modules_without_raising():
    """The five ship in a shape the reader handles — no silent skips today."""
    for tool in TOOLS:
        assert status_contract(tool), tool
