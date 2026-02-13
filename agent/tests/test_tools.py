"""Tests for synapse_tools.py — tool definitions and execution dispatch."""

import asyncio
import json
import sys
import os
import pytest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from synapse_tools import (
    TOOL_DEFINITIONS,
    execute_tool,
    set_client,
    get_client,
)
from synapse_ws import SynapseClient, SynapseExecutionError


# ── Tool definition tests ────────────────────────────────────


def test_tool_definitions_count():
    """All expected tools are defined."""
    names = [t["name"] for t in TOOL_DEFINITIONS]
    assert "synapse_ping" in names
    assert "synapse_scene_info" in names
    assert "synapse_inspect_scene" in names
    assert "synapse_inspect_selection" in names
    assert "synapse_inspect_node" in names
    assert "synapse_execute" in names
    assert "synapse_render_preview" in names
    assert "synapse_knowledge_lookup" in names
    assert "synapse_project_setup" in names
    assert "synapse_memory_write" in names
    assert "synapse_memory_query" in names
    assert "synapse_memory_status" in names
    # 12 original + 8 TOPS/viewport/batch tools
    assert "synapse_tops_cook" in names
    assert "synapse_tops_status" in names
    assert "synapse_tops_diagnose" in names
    assert "synapse_tops_wedge" in names
    assert "synapse_tops_work_items" in names
    assert "synapse_tops_cook_stats" in names
    assert "synapse_capture_viewport" in names
    assert "synapse_batch" in names
    assert len(names) == 20


def test_tool_definitions_have_required_fields():
    """Each tool has name, description, and input_schema."""
    for tool in TOOL_DEFINITIONS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"


def test_execute_tool_requires_code():
    """synapse_execute has 'code' as required input."""
    execute_tool_def = next(t for t in TOOL_DEFINITIONS if t["name"] == "synapse_execute")
    assert "code" in execute_tool_def["input_schema"]["required"]


def test_inspect_node_requires_path():
    """synapse_inspect_node has 'node_path' as required input."""
    tool_def = next(t for t in TOOL_DEFINITIONS if t["name"] == "synapse_inspect_node")
    assert "node_path" in tool_def["input_schema"]["required"]


# ── Client management tests ──────────────────────────────────


def test_get_client_without_init_raises():
    """get_client raises if set_client was never called."""
    import synapse_tools
    old = synapse_tools._client
    synapse_tools._client = None
    try:
        with pytest.raises(RuntimeError, match="not initialized"):
            get_client()
    finally:
        synapse_tools._client = old


# ── Tool execution tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_ping():
    """synapse_ping returns connected status."""
    mock_client = AsyncMock(spec=SynapseClient)
    mock_client.ping = AsyncMock(return_value={"pong": True, "protocol_version": "4.0.0"})
    set_client(mock_client)

    result = await execute_tool("synapse_ping", {})
    data = json.loads(result)
    assert data["status"] == "connected"


@pytest.mark.asyncio
async def test_execute_scene_info():
    """synapse_scene_info returns scene data."""
    mock_client = AsyncMock(spec=SynapseClient)
    mock_client.scene_info = AsyncMock(return_value={"hip_file": "test.hip", "fps": 24})
    set_client(mock_client)

    result = await execute_tool("synapse_scene_info", {})
    data = json.loads(result)
    assert data["fps"] == 24


@pytest.mark.asyncio
async def test_execute_synapse_execute():
    """synapse_execute returns execution result."""
    mock_client = AsyncMock(spec=SynapseClient)
    mock_client.execute_python = AsyncMock(return_value="/stage/test_null")
    set_client(mock_client)

    result = await execute_tool("synapse_execute", {
        "code": "result = ensure_node('/stage', 'null', 'test').path()",
        "description": "Create test null",
    })
    data = json.loads(result)
    assert data["executed"] is True
    assert data["result"] == "/stage/test_null"


@pytest.mark.asyncio
async def test_execute_synapse_execute_error():
    """synapse_execute returns error info on failure."""
    mock_client = AsyncMock(spec=SynapseClient)
    mock_client.execute_python = AsyncMock(
        side_effect=SynapseExecutionError("NameError: 'x' undefined")
    )
    set_client(mock_client)

    result = await execute_tool("synapse_execute", {
        "code": "x",
        "description": "Bad code",
    })
    data = json.loads(result)
    assert data["executed"] is False
    assert "NameError" in data["error"]
    assert data["rolled_back"] is True


@pytest.mark.asyncio
async def test_execute_unknown_tool():
    """Unknown tool returns error."""
    mock_client = AsyncMock(spec=SynapseClient)
    set_client(mock_client)

    result = await execute_tool("nonexistent_tool", {})
    data = json.loads(result)
    assert "error" in data
    assert "Unknown tool" in data["error"]


@pytest.mark.asyncio
async def test_execute_inspect_node():
    """synapse_inspect_node passes correct args to client."""
    mock_client = AsyncMock(spec=SynapseClient)
    mock_client.inspect_node = AsyncMock(return_value={"path": "/stage/light", "type": "distantlight"})
    set_client(mock_client)

    result = await execute_tool("synapse_inspect_node", {"node_path": "/stage/light"})
    data = json.loads(result)
    assert data["path"] == "/stage/light"
    mock_client.inspect_node.assert_awaited_once_with(
        node="/stage/light",
        include_code=True,
        include_geometry=True,
        include_expressions=True,
    )


# ── TOPS / Pipeline tool execution tests ──────────────────────


@pytest.mark.asyncio
async def test_execute_tops_cook():
    """synapse_tops_cook passes correct args to client."""
    mock_client = AsyncMock(spec=SynapseClient)
    mock_client.tops_cook = AsyncMock(return_value={"status": "cooked", "items": 10})
    set_client(mock_client)

    result = await execute_tool("synapse_tops_cook", {
        "node": "/obj/topnet1/ropfetch1",
        "max_retries": 2,
        "validate_states": True,
    })
    data = json.loads(result)
    assert data["status"] == "cooked"
    mock_client.tops_cook.assert_awaited_once_with(
        node="/obj/topnet1/ropfetch1", max_retries=2, validate=True,
    )


@pytest.mark.asyncio
async def test_execute_tops_status():
    """synapse_tops_status passes correct args to client."""
    mock_client = AsyncMock(spec=SynapseClient)
    mock_client.tops_status = AsyncMock(return_value={"healthy": True, "nodes": 5})
    set_client(mock_client)

    result = await execute_tool("synapse_tops_status", {
        "topnet_path": "/obj/topnet1",
    })
    data = json.loads(result)
    assert data["healthy"] is True
    mock_client.tops_status.assert_awaited_once_with(
        topnet_path="/obj/topnet1", include_items=False,
    )


@pytest.mark.asyncio
async def test_execute_capture_viewport():
    """synapse_capture_viewport passes format arg."""
    mock_client = AsyncMock(spec=SynapseClient)
    mock_client.capture_viewport = AsyncMock(return_value={"image_path": "/tmp/capture.jpg"})
    set_client(mock_client)

    result = await execute_tool("synapse_capture_viewport", {"format": "jpeg"})
    data = json.loads(result)
    assert data["image_path"] == "/tmp/capture.jpg"


@pytest.mark.asyncio
async def test_execute_batch():
    """synapse_batch passes commands to client."""
    mock_client = AsyncMock(spec=SynapseClient)
    mock_client.batch_commands = AsyncMock(return_value={"results": [{"ok": True}]})
    set_client(mock_client)

    result = await execute_tool("synapse_batch", {
        "commands": [{"type": "ping"}],
    })
    data = json.loads(result)
    assert data["results"][0]["ok"] is True
    mock_client.batch_commands.assert_awaited_once_with(
        commands=[{"type": "ping"}], atomic=True, stop_on_error=False,
    )
