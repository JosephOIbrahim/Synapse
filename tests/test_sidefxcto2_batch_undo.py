"""SIDEFXCTO-2 follow-up — a batch sub-command cannot turn undo grouping off.

Verifier counter-evidence (2026-11-20): a model-reachable ``synapse_batch``
call with envelope ``atomic=False`` and a sub ``execute_python`` carrying
``atomic=False`` returned ``success=True`` with zero undo groups — arbitrary
Python ran with nothing on the artist's undo stack.

The handler now strips every undo-toggle alias from each sub-command payload
before ``registry.invoke`` and opens the batch envelope group whenever Houdini
is available, whatever the payload's ``atomic`` says. These tests drive the
real handler end to end against a fake ``hou.undos`` that records every group
entry AND its nesting depth, so "executes grouped" is observed rather than
assumed from a default.
"""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from synapse.core.protocol import SynapseCommand


class _History:
    """hou.undos double: records group entries, depths, and step calls."""

    def __init__(self):
        self.depth = 0
        self.groups = []        # label per entry, in open order
        self.entry_depth = []   # nesting depth at entry (0 = top level)
        self.undo = []
        self.redo = []
        self.calls = []

    @contextmanager
    def group(self, label):
        self.groups.append(label)
        self.entry_depth.append(self.depth)
        self.depth += 1
        try:
            yield
        finally:
            self.depth -= 1

    def areEnabled(self):
        return True

    def undoLabels(self):
        return tuple(self.undo)

    def redoLabels(self):
        return tuple(self.redo)

    def performUndo(self):
        self.calls.append("undo")

    def performRedo(self):
        self.calls.append("redo")


@pytest.fixture
def env(monkeypatch):
    import synapse.server.handlers as handlers_mod

    history = _History()
    monkeypatch.setattr(
        handlers_mod, "hou", SimpleNamespace(undos=history), raising=False)
    monkeypatch.setattr(handlers_mod, "HOU_AVAILABLE", True)
    monkeypatch.setenv("SYNAPSE_LIVE_ENVELOPE", "0")
    handler = handlers_mod.SynapseHandler()
    # Provenance is out of scope here; execute the handler directly.
    monkeypatch.setattr(
        handler._registry._floor_gate, "wrap",
        lambda kind, payload, fn, **kw: fn(payload))
    monkeypatch.setattr(handler, "_submit_logs", lambda *a, **kw: None)
    return handler, history


def _run(handler, payload):
    return handler.handle(
        SynapseCommand(id="batch-r012", type="batch_commands", payload=payload))


def _one_step(cmd_type, cmd_payload, *, envelope_atomic=False):
    return {
        "commands": [{"type": cmd_type, "payload": cmd_payload}],
        "atomic": envelope_atomic,
    }


# ---------------------------------------------------------------------------
# The verifier's exact repro: batch envelope + sub-command both atomic:false
# ---------------------------------------------------------------------------

def test_batch_execute_python_atomic_false_still_opens_the_group(env):
    handler, history = env

    response = _run(handler, _one_step(
        "execute_python", {"content": "result = 7", "atomic": False}))

    assert response.success, response.error
    assert response.data["statuses"] == ["ok"]
    assert response.data["results"][0]["result"] == "7"
    # Non-empty groups and the canonical execute label, nested under the batch.
    assert history.groups == ["synapse_batch", "synapse_execute"]
    assert history.entry_depth == [0, 1]
    assert history.depth == 0


def test_batch_execute_python_use_undo_false_still_opens_the_group(env):
    handler, history = env

    response = _run(handler, _one_step(
        "execute_python", {"content": "result = 11", "use_undo": False}))

    assert response.success, response.error
    assert response.data["results"][0]["result"] == "11"
    assert "synapse_execute" in history.groups
    assert history.groups  # never zero
    assert history.depth == 0


def test_batch_envelope_atomic_false_alone_cannot_skip_the_group(env):
    handler, history = env

    response = _run(handler, _one_step(
        "execute_python", {"content": "result = 3"}))

    assert response.success, response.error
    assert history.groups == ["synapse_batch", "synapse_execute"]


# ---------------------------------------------------------------------------
# A nested batch re-applies the same strip at its own dispatch
# ---------------------------------------------------------------------------

def test_nested_batch_cannot_smuggle_the_toggle(env):
    handler, history = env

    response = _run(handler, {
        "commands": [{
            "type": "batch_commands",
            "payload": {
                "commands": [{
                    "type": "execute_python",
                    "payload": {"content": "result = 5", "use_undo": False},
                }],
                "atomic": False,
            },
        }],
        "atomic": False,
    })

    assert response.success, response.error
    inner = response.data["results"][0]
    assert inner["statuses"] == ["ok"]
    assert inner["results"][0]["result"] == "5"
    assert "synapse_execute" in history.groups
    assert history.depth == 0


# ---------------------------------------------------------------------------
# A normal mutation batch groups once, and its payload is stripped too
# ---------------------------------------------------------------------------

def test_normal_mutation_batch_groups_once(env):
    handler, history = env
    seen = []

    def _stub(payload):
        seen.append((history.depth, dict(payload)))
        return {"ok": True}

    handler._registry.register("create_node", _stub)
    sub_payload = {"parent": "/obj", "type": "geo",
                   "atomic": False, "use_undo": False}

    response = _run(handler, _one_step("create_node", sub_payload))

    assert response.success, response.error
    assert history.groups == ["synapse_batch"]
    assert history.entry_depth == [0]
    depth, payload = seen[0]
    assert depth == 1                       # the mutation ran grouped
    assert "atomic" not in payload and "use_undo" not in payload
    # The strip is a copy: the caller's payload is left as sent.
    assert sub_payload["atomic"] is False and sub_payload["use_undo"] is False
    assert response.data["statuses"] == ["ok"]


def test_execute_vex_in_a_batch_is_covered_by_the_envelope(env):
    handler, history = env

    handler._registry.register(
        "execute_vex", lambda payload: {"node": "(stub)"})

    response = _run(handler, _one_step(
        "execute_vex", {"snippet": "int x = 1;"}))

    assert response.success, response.error
    assert history.groups == ["synapse_batch"]
    assert history.entry_depth == [0]


# ---------------------------------------------------------------------------
# Malformed steps fail as data; they cannot smuggle the toggle or crash out
# ---------------------------------------------------------------------------

def test_malformed_command_entry_is_a_failed_step_not_a_bypass(env):
    handler, history = env

    response = _run(handler, {
        "commands": [
            "execute_python",
            {"type": "execute_python", "payload": "atomic = False"},
            {"type": "ping", "payload": {}},
        ],
        "atomic": False,
    })

    assert response.success, response.error
    assert response.data["statuses"] == ["error", "error", "ok"]
    assert response.data["results"][2]["pong"] is True
    assert history.groups == ["synapse_batch"]
    assert history.depth == 0


# ---------------------------------------------------------------------------
# The internal execute_python transports (mcp_server.py:798/:1011)
#
# Both are model-TRIGGERED but not model-PAYLOADED: the cognitive tool builds
# the script from validated arguments, and the transport closure builds the
# send_command payload with a literal atomic:False. The model has no atomic
# field to set. The Inspector script only reads; the BLOCKS script groups its
# own mutations under its own label, so atomic:False is not an ungrouped
# mutation path.
# ---------------------------------------------------------------------------

def test_cognitive_tools_expose_no_undo_or_code_input():
    from synapse.cognitive.tools.inspect_stage import INSPECT_STAGE_SCHEMA
    from synapse.cognitive.tools.apply_fixture import (
        APPLY_FIXTURE_SCHEMA, REMOVE_FIXTURE_SCHEMA)

    assert set(INSPECT_STAGE_SCHEMA["input_schema"]["properties"]) == {
        "target_path", "timeout"}
    for schema in (APPLY_FIXTURE_SCHEMA, REMOVE_FIXTURE_SCHEMA):
        assert set(schema["input_schema"]["properties"]) == {
            "fixture", "stage_path", "timeout"}


def test_internal_transports_build_the_execute_payload_themselves():
    """AST pin: the two payloads are literals; content is the generated script."""
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "mcp_server.py").read_text(
        encoding="utf-8")
    payloads = []
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "send_command" and len(node.args) >= 2):
            first = node.args[0]
            if isinstance(first, ast.Constant) and first.value == "execute_python":
                payloads.append(node.args[1])

    assert len(payloads) == 2, "expected the Inspector and BLOCKS transports"
    for payload in payloads:
        assert isinstance(payload, ast.Dict)
        assert [key.value for key in payload.keys] == ["content", "atomic"]
        content, atomic = payload.values
        assert isinstance(content, ast.Name) and content.id == "wrapped"
        assert isinstance(atomic, ast.Constant) and atomic.value is False


def test_blocks_runtime_groups_its_own_apply_and_remove():
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "python" / "synapse"
           / "blocks" / "runtime.py").read_text(encoding="utf-8")
    assert '_undo_group("SYNAPSE BLOCKS: apply %s" % result["fixture"])' in src
    assert '_undo_group("SYNAPSE BLOCKS: remove %s" % result["fixture"])' in src
