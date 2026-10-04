"""B2: an error is never a success.

BRIDGE-13: a memory handler whose tracker result carries ``error`` used to be
wrapped by handle() as success=True, so a store that could not be read looked
like a store with nothing in it. BRIDGE-15: the integrity bridge finalized a
handler response whose ``success`` was False as a verified operation.

BRIDGE-10 (a retried change applying twice) is deliberately NOT fixed by
caching replies per command id: recipes and the parser derive the id from the
payload (routing/recipes/base.py, routing/parser.py), so the same build asked
for twice carries the same id, and a reply cache would answer the second ask
without building. ``test_command_ids_are_not_unique_per_request`` pins that
reason.

Pure Python: no hou.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from synapse.core.errors import SynapseServiceError, SynapseUserError
from synapse.server.handlers_memory import MemoryHandlerMixin, _fail_on_error

ROOT = Path(__file__).resolve().parent.parent


def test_a_clean_result_passes_through_unchanged():
    result = {"found": False, "count": 0, "matches": []}
    assert _fail_on_error(result) is result
    assert _fail_on_error(None) is None


@pytest.mark.parametrize("text", [
    "Memory not available",
    "Decision persistence failed: disk full",
    "boom",
])
def test_a_store_failure_raises_a_service_error(text):
    with pytest.raises(SynapseServiceError, match=text.split(":")[0]):
        _fail_on_error({"error": text, "found": False})


@pytest.mark.parametrize("text", [
    "no valid kind in ['bogus']",
    "Decision scope must be scene or project",
    "A decision must contain readable text",
    "scope must be scene, project, or all",
])
def test_a_caller_mistake_raises_a_user_error(text):
    with pytest.raises(SynapseUserError):
        _fail_on_error({"error": text})


class _Bridge:
    def __init__(self, result):
        self._result = result

    def handle_memory_search(self, payload):
        return dict(self._result)

    handle_memory_add = handle_memory_decide = handle_memory_recall = handle_memory_search


class _Handler(MemoryHandlerMixin):
    def __init__(self, result):
        self._bridge_obj = _Bridge(result)

    def _memory_on_main(self, callback):  # no main-thread hop in a unit test
        return callback(self._bridge_obj)


@pytest.mark.parametrize("name", [
    "_handle_memory_search", "_handle_memory_add",
    "_handle_memory_decide", "_handle_memory_recall",
])
def test_every_bridged_memory_handler_fails_on_a_dead_store(name):
    handler = _Handler({"error": "Memory not available", "found": False})
    with pytest.raises(SynapseServiceError):
        getattr(handler, name)({"query": "anything", "scope": "scene"})


def test_recall_with_no_match_is_still_a_success():
    handler = _Handler({"found": False, "count": 0, "matches": []})
    assert handler._handle_memory_recall({"query": "x", "scope": "scene"})["found"] is False


def test_the_bridge_does_not_finalize_a_failed_handler_response():
    """Both execute paths check ``success is False`` before _finalize."""
    source = (ROOT / "shared" / "bridge.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    checked = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ("_execute_houdini", "_execute_history"):
            body = ast.get_source_segment(source, node)
            checked[node.name] = 'getattr(result, "success", None) is False' in body
    assert checked == {"_execute_houdini": True, "_execute_history": True}


def test_command_ids_are_not_unique_per_request():
    """Why there is no reply cache keyed on command id (BRIDGE-10)."""
    for rel in ("python/synapse/routing/recipes/base.py", "python/synapse/routing/parser.py"):
        assert "id=deterministic_uuid(" in (ROOT / rel).read_text(encoding="utf-8"), rel
