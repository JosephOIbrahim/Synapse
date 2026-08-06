"""M5 BLOCKS -- the Dispatcher seam (D4).

Covers the cognitive adapter (``synapse.cognitive.tools.apply_fixture``) and
its wiring into ``mcp_server.py``. No Houdini, no ``mcp`` import: the server
side is source-scanned, matching the precedent in
``tests/test_phase0c_doc1_toolcount.py`` (the ``mcp`` library is red on CI --
see the DOC-1 note there -- so an import-based assertion here would fail for
reasons unrelated to this seam).
"""

from __future__ import annotations

import ast
import json
from importlib import import_module
from pathlib import Path

import pytest

from synapse.blocks import fixtures as fx_mod

# NOT ``from synapse.cognitive.tools import apply_fixture``: that package's
# __init__ re-exports the FUNCTION ``apply_fixture``, which shadows the
# submodule of the same name (the pre-existing shape ``inspect_stage`` already
# has). import_module resolves through sys.modules and returns the module.
tool = import_module("synapse.cognitive.tools.apply_fixture")

REPO = Path(__file__).resolve().parent.parent
TOOL_SRC = (REPO / "python" / "synapse" / "cognitive" / "tools"
            / "apply_fixture.py").read_text(encoding="utf-8")
SERVER_SRC = (REPO / "mcp_server.py").read_text(encoding="utf-8")


class Recorder:
    """A transport that records what it was handed and returns a canned body."""

    def __init__(self, body="{}", accept_timeout=True):
        self.body = body
        self.accept_timeout = accept_timeout
        self.calls = []

    def __call__(self, code, **kwargs):
        if "timeout" in kwargs and not self.accept_timeout:
            raise TypeError("transport() got an unexpected keyword 'timeout'")
        self.calls.append((code, kwargs))
        return self.body


def boom(code, **kwargs):
    raise AssertionError(
        "transport was called -- validation must reject before anything is "
        "shipped into the Houdini process"
    )


def unwrap(payload: str) -> str:
    """Recover the script from wrap_script_base64's one-line exec() form:
    ``exec(__import__('base64').b64decode('<b64>').decode('utf-8'))``."""
    import base64
    import re
    m = re.search(r"b64decode\('([A-Za-z0-9+/=]+)'\)", payload)
    assert m, f"payload is not the base64 exec wrapper: {payload[:120]!r}"
    return base64.b64decode(m.group(1)).decode("utf-8")


# ---------------------------------------------------------------- schemas


@pytest.mark.parametrize("schema", [
    tool.APPLY_FIXTURE_SCHEMA, tool.REMOVE_FIXTURE_SCHEMA,
])
def test_schema_shape_matches_the_dispatcher_contract(schema):
    """Dispatcher.tool_schemas() reads exactly these two keys; a schema
    missing either is dispatchable but invisible to the agent loop."""
    assert set(schema) == {"description", "input_schema"}
    assert schema["description"].strip()
    assert schema["input_schema"]["required"] == ["fixture"]
    assert set(schema["input_schema"]["properties"]) == {
        "fixture", "stage_path", "timeout",
    }
    json.dumps(schema)


def test_apply_schema_states_the_rulings_the_agent_must_not_guess():
    """The agent only ever sees this text. Fails if the idempotence or the
    collision behaviour stops being stated, at which point the model starts
    inventing delete-and-rebuild."""
    d = tool.APPLY_FIXTURE_SCHEMA["description"]
    assert "zero operations" in d
    assert "NOTHING is created or deleted" in d
    assert "never modified or deleted" in d


# ---------------------------------------------------------------- boundary


def test_cognitive_tool_never_imports_the_hou_touching_runtime():
    """The reconciler runtime imports ``hou``. If this adapter imported it,
    the MCP server process (no Houdini) would fail at import and the
    cognitive-boundary lint would go red. Parsed with ast so the module name
    appearing inside the injected-script TEMPLATE does not false-positive.
    """
    banned = {"synapse.blocks.runtime", "hou"}
    hits = []
    for node in ast.walk(ast.parse(TOOL_SRC)):
        if isinstance(node, ast.Import):
            hits += [a.name for a in node.names if a.name in banned]
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "") in banned:
                hits.append(node.module)
    assert hits == [], f"cognitive adapter imports host-only modules: {hits}"


def test_injected_script_is_flat():
    """The bridge execs injected code with exec(code, G, L) where G is not L.
    A ``def`` in the script would resolve its names via __globals__ and never
    see the script's own imports -- the exact NameError class documented in
    synapse/inspector/tool_inspect_stage.py. Fails if one is introduced."""
    template = tool._SCRIPT_TEMPLATE
    rendered = template % {"fn": "apply_fixture", "name": "x", "stage": "/stage"}
    assert "def " not in rendered and "class " not in rendered
    ast.parse(rendered)          # and it must be valid Python


# ---------------------------------------------------------------- validation


@pytest.mark.parametrize("bad", [
    "../evil", "Solaris.Basic", "sol aris", "a'; import os; '", "", "..",
    "solaris/basic",
])
def test_bad_fixture_name_never_reaches_the_transport(bad):
    with pytest.raises(tool.BlocksToolError):
        tool.apply_fixture(bad, execute_python_fn=boom)


@pytest.mark.parametrize("bad", ["stage", "/stage;rm", "/", "", "/st age"])
def test_bad_stage_path_never_reaches_the_transport(bad):
    with pytest.raises(tool.BlocksToolError):
        tool.apply_fixture("solaris.basic", bad, execute_python_fn=boom)


def test_name_regex_matches_the_fixture_loaders():
    """The adapter carries its own copy of the name pattern because that is
    where the value becomes injected source. Fails if the two drift, which
    would mean a name the loader accepts and the adapter rejects, or worse,
    the reverse."""
    assert tool._VALID_NAME_RE.pattern == fx_mod._VALID_NAME_RE.pattern


# ---------------------------------------------------------------- round-trip


def test_happy_path_ships_the_right_script_and_returns_the_result():
    body = json.dumps({"applied": True, "ops": 6, "collisions": [],
                       "box": "BLOCKS_solaris_basic", "per_node": []})
    rec = Recorder(body)
    out = tool.apply_fixture("solaris.basic", "/stage", execute_python_fn=rec)
    assert out["applied"] is True and out["ops"] == 6

    code, kwargs = rec.calls[0]
    assert kwargs["timeout"] == tool.DEFAULT_TIMEOUT_SECONDS
    inner = unwrap(code)
    assert "_syn_blocks_rt.apply_fixture('solaris.basic', stage_path='/stage')" in inner


def test_remove_ships_the_remove_entry_point():
    rec = Recorder(json.dumps({"status": "removed"}))
    tool.remove_fixture("solaris.basic", execute_python_fn=rec)
    inner = unwrap(rec.calls[0][0])
    assert "_syn_blocks_rt.remove_fixture(" in inner


def test_collision_is_data_not_an_exception():
    """A collision must arrive as an ordinary result so the agent can read it
    and choose. Fails if the adapter starts routing it to an error path."""
    body = json.dumps({"status": "collision", "applied": False, "ops": 0,
                       "collisions": [{"name": "camera"}], "box": "B",
                       "per_node": []})
    out = tool.apply_fixture("solaris.basic", execute_python_fn=Recorder(body))
    assert out["status"] == "collision" and out["ops"] == 0


def test_houdini_side_exception_becomes_a_typed_error_with_traceback():
    body = json.dumps({"synapse_error": "StageNotFoundError",
                       "message": "'/stage' is not present",
                       "traceback": "Traceback ..."})
    with pytest.raises(tool.BlocksHoudiniError) as e:
        tool.apply_fixture("solaris.basic", execute_python_fn=Recorder(body))
    assert e.value.error_type == "StageNotFoundError"
    assert e.value.traceback


@pytest.mark.parametrize("body,fragment", [
    ("", "empty response"),
    ("   ", "empty response"),
    ("not json at all", "not valid JSON"),
    ("[1, 2]", "root must be an object"),
])
def test_malformed_responses_are_typed_failures(body, fragment):
    """Fails if a garbled response is silently treated as a result -- the
    'advisory note on a success status' defect Law 3 names."""
    with pytest.raises(tool.BlocksToolError) as e:
        tool.apply_fixture("solaris.basic", execute_python_fn=Recorder(body))
    assert fragment in str(e.value)


def test_legacy_transport_without_timeout_kwarg_still_works():
    rec = Recorder(json.dumps({"ok": True}), accept_timeout=False)
    assert tool.apply_fixture("solaris.basic", execute_python_fn=rec) == {"ok": True}


# ---------------------------------------------------------------- server wiring


def test_mcp_server_registers_both_tools_on_the_dispatcher_seam():
    """D4: pure function under the cognitive layer, schema registered
    alongside, adapter branch swapped -- asserted against the source the
    server actually runs."""
    for token in (
        "from synapse.cognitive.tools.apply_fixture import",
        "_BLOCKS_APPLY_TOOL_NAME = \"synapse_apply_fixture\"",
        "_BLOCKS_REMOVE_TOOL_NAME = \"synapse_remove_fixture\"",
        "_blocks_configure_transport(_sync_transport)",
        "if name in _BLOCKS_TOOL_NAMES:",
        "return await _blocks_call_tool(name, arguments)",
    ):
        assert token in SERVER_SRC, f"mcp_server.py no longer wires: {token!r}"


def test_blocks_tools_are_registered_with_their_schemas():
    """A tool without a schema is dispatchable but invisible to the agent
    loop (Dispatcher.tool_schemas). Fails if the schemas= argument is
    dropped."""
    block = SERVER_SRC.split("def _get_blocks_dispatcher", 1)[1].split(
        "async def _blocks_call_tool", 1)[0]
    assert "schemas={" in block
    assert "_APPLY_FIXTURE_SCHEMA" in block and "_REMOVE_FIXTURE_SCHEMA" in block


def test_blocks_tools_are_not_in_the_dispatch_registry():
    """stdio-local tools must never double-register as WS handlers -- the
    same relationship test_phase0c_doc1_toolcount.py pins for the Inspector."""
    from synapse.mcp._tool_registry import TOOL_DEFS
    names = {t[0] for t in TOOL_DEFS}
    assert not names & {"synapse_apply_fixture", "synapse_remove_fixture"}
