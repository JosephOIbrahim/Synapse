"""Tests for synapse_ws.py — WebSocket client wire format and error handling."""

import asyncio
import json
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Add agent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from synapse_ws import (
    SynapseClient,
    SynapseConnectionError,
    SynapseExecutionError,
    PROTOCOL_VERSION,
    _get_auth_key,
)


# ── Helpers ──────────────────────────────────────────────────


def _make_response(command_id: str, success: bool = True, data=None, error=None):
    """Build a SynapseResponse JSON string matching the wire format."""
    return json.dumps({
        "id": command_id,
        "success": success,
        "data": data,
        "error": error,
        "sequence": 0,
        "timestamp": 1234567890.0,
        "protocol_version": PROTOCOL_VERSION,
    })


# ── Connection tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_connect_success():
    """Client connects and sets _connected flag."""
    mock_ws = AsyncMock()
    with patch("synapse_ws.websockets") as mock_websockets:
        mock_websockets.connect = AsyncMock(return_value=mock_ws)
        client = SynapseClient()
        result = await client.connect()
        assert result is True
        assert client._connected is True


@pytest.mark.asyncio
async def test_connect_timeout():
    """Client raises SynapseConnectionError on timeout."""
    with patch("synapse_ws.websockets") as mock_websockets:
        mock_websockets.connect = AsyncMock(side_effect=asyncio.TimeoutError())
        client = SynapseClient()
        # The connect method wraps asyncio.wait_for which raises TimeoutError
        # but SynapseClient catches it via the except block
        with pytest.raises(SynapseConnectionError, match="Couldn't reach"):
            await client.connect()


@pytest.mark.asyncio
async def test_connect_refused():
    """Client raises SynapseConnectionError on connection refused."""
    with patch("synapse_ws.websockets") as mock_websockets:
        mock_websockets.connect = AsyncMock(side_effect=ConnectionRefusedError("refused"))
        client = SynapseClient()
        with pytest.raises(SynapseConnectionError, match="Connection to Synapse failed"):
            await client.connect()


@pytest.mark.asyncio
async def test_disconnect():
    """Client disconnects cleanly."""
    mock_ws = AsyncMock()
    client = SynapseClient()
    client._ws = mock_ws
    client._connected = True
    await client.disconnect()
    assert client._connected is False
    mock_ws.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_context_manager():
    """async with SynapseClient() connects and disconnects."""
    mock_ws = AsyncMock()
    with patch("synapse_ws.websockets") as mock_websockets:
        mock_websockets.connect = AsyncMock(return_value=mock_ws)
        async with SynapseClient() as client:
            assert client._connected is True
        mock_ws.close.assert_awaited_once()


# ── Wire format tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_ping_wire_format():
    """Ping sends correct SynapseCommand format and returns data."""
    mock_ws = AsyncMock()

    sent_messages = []

    async def capture_send(msg):
        sent_messages.append(json.loads(msg))

    mock_ws.send = capture_send

    async def mock_recv():
        # Return response matching the command ID from the sent message
        cmd = sent_messages[-1]
        return _make_response(cmd["id"], data={"pong": True, "protocol_version": "4.0.0"})

    mock_ws.recv = mock_recv

    client = SynapseClient()
    client._ws = mock_ws
    client._connected = True

    result = await client.ping()

    # Verify command wire format
    cmd = sent_messages[0]
    assert cmd["type"] == "ping"
    assert len(cmd["id"]) == 16  # hex UUID prefix
    assert cmd["payload"] == {}
    assert cmd["sequence"] == 0
    assert cmd["protocol_version"] == PROTOCOL_VERSION
    assert "timestamp" in cmd

    # Verify response
    assert result["pong"] is True


@pytest.mark.asyncio
async def test_execute_python_wire_format():
    """execute_python sends code as payload.content (not payload.code)."""
    mock_ws = AsyncMock()
    sent_messages = []

    async def capture_send(msg):
        sent_messages.append(json.loads(msg))

    mock_ws.send = capture_send

    async def mock_recv():
        cmd = sent_messages[-1]
        return _make_response(cmd["id"], data={"result": 42})

    mock_ws.recv = mock_recv

    client = SynapseClient()
    client._ws = mock_ws
    client._connected = True

    result = await client.execute_python("result = 42")

    # Verify the key field is "content" not "code"
    cmd = sent_messages[0]
    assert cmd["type"] == "execute_python"
    assert cmd["payload"]["content"] == "result = 42"
    assert "code" not in cmd["payload"]

    # Verify result extraction
    assert result == 42


@pytest.mark.asyncio
async def test_execute_python_dry_run():
    """dry_run parameter is forwarded in payload."""
    mock_ws = AsyncMock()
    sent_messages = []

    async def capture_send(msg):
        sent_messages.append(json.loads(msg))

    mock_ws.send = capture_send

    async def mock_recv():
        cmd = sent_messages[-1]
        return _make_response(cmd["id"], data={"valid": True})

    mock_ws.recv = mock_recv

    client = SynapseClient()
    client._ws = mock_ws
    client._connected = True

    await client.execute_python("x = 1", dry_run=True)

    cmd = sent_messages[0]
    assert cmd["payload"]["dry_run"] is True


@pytest.mark.asyncio
async def test_execute_python_atomic_false():
    """atomic=False is forwarded in payload."""
    mock_ws = AsyncMock()
    sent_messages = []

    async def capture_send(msg):
        sent_messages.append(json.loads(msg))

    mock_ws.send = capture_send

    async def mock_recv():
        cmd = sent_messages[-1]
        return _make_response(cmd["id"], data={"result": None})

    mock_ws.recv = mock_recv

    client = SynapseClient()
    client._ws = mock_ws
    client._connected = True

    await client.execute_python("x = 1", atomic=False)

    cmd = sent_messages[0]
    assert cmd["payload"]["atomic"] is False


# ── Error handling tests ─────────────────────────────────────


@pytest.mark.asyncio
async def test_execution_error():
    """Server-side errors raise SynapseExecutionError."""
    mock_ws = AsyncMock()
    sent_messages = []

    async def capture_send(msg):
        sent_messages.append(json.loads(msg))

    mock_ws.send = capture_send

    async def mock_recv():
        cmd = sent_messages[-1]
        return _make_response(cmd["id"], success=False, error="NameError: name 'x' is not defined")

    mock_ws.recv = mock_recv

    client = SynapseClient()
    client._ws = mock_ws
    client._connected = True

    with pytest.raises(SynapseExecutionError, match="NameError"):
        await client.execute_python("x")


@pytest.mark.asyncio
async def test_not_connected_error():
    """Calling methods before connect() raises SynapseConnectionError."""
    client = SynapseClient()
    with pytest.raises(SynapseConnectionError, match="Not connected"):
        await client.ping()


@pytest.mark.asyncio
async def test_response_id_matching():
    """Client discards stale responses and waits for matching ID."""
    mock_ws = AsyncMock()
    sent_messages = []
    recv_count = 0

    async def capture_send(msg):
        sent_messages.append(json.loads(msg))

    mock_ws.send = capture_send

    async def mock_recv():
        nonlocal recv_count
        recv_count += 1
        cmd = sent_messages[-1]
        if recv_count == 1:
            # Return a stale response with wrong ID
            return _make_response("stale_id_00000", data={"stale": True})
        else:
            # Return correct response
            return _make_response(cmd["id"], data={"correct": True})

    mock_ws.recv = mock_recv

    client = SynapseClient()
    client._ws = mock_ws
    client._connected = True

    result = await client.ping()
    assert result["correct"] is True
    assert recv_count == 2  # First was discarded


# ── High-level API tests ─────────────────────────────────────


@pytest.mark.asyncio
async def test_scene_info():
    """scene_info sends get_scene_info command."""
    mock_ws = AsyncMock()
    sent_messages = []

    async def capture_send(msg):
        sent_messages.append(json.loads(msg))

    mock_ws.send = capture_send

    async def mock_recv():
        cmd = sent_messages[-1]
        return _make_response(cmd["id"], data={
            "hip_file": "/test/scene.hip",
            "fps": 24.0,
            "frame_range": [1, 100],
        })

    mock_ws.recv = mock_recv

    client = SynapseClient()
    client._ws = mock_ws
    client._connected = True

    result = await client.scene_info()
    assert sent_messages[0]["type"] == "get_scene_info"
    assert result["fps"] == 24.0


@pytest.mark.asyncio
async def test_inspect_scene():
    """inspect_scene sends correct command with optional parameters."""
    mock_ws = AsyncMock()
    sent_messages = []

    async def capture_send(msg):
        sent_messages.append(json.loads(msg))

    mock_ws.send = capture_send

    async def mock_recv():
        cmd = sent_messages[-1]
        return _make_response(cmd["id"], data={"nodes": []})

    mock_ws.recv = mock_recv

    client = SynapseClient()
    client._ws = mock_ws
    client._connected = True

    await client.inspect_scene(root="/stage", max_depth=2, context_filter="Lop")

    cmd = sent_messages[0]
    assert cmd["type"] == "inspect_scene"
    assert cmd["payload"]["root"] == "/stage"
    assert cmd["payload"]["max_depth"] == 2
    assert cmd["payload"]["context_filter"] == "Lop"


@pytest.mark.asyncio
async def test_create_node():
    """create_node sends correct payload."""
    mock_ws = AsyncMock()
    sent_messages = []

    async def capture_send(msg):
        sent_messages.append(json.loads(msg))

    mock_ws.send = capture_send

    async def mock_recv():
        cmd = sent_messages[-1]
        return _make_response(cmd["id"], data={"path": "/stage/test_null", "type": "null"})

    mock_ws.recv = mock_recv

    client = SynapseClient()
    client._ws = mock_ws
    client._connected = True

    result = await client.create_node("/stage", "null", "test_null")
    cmd = sent_messages[0]
    assert cmd["type"] == "create_node"
    assert cmd["payload"]["parent"] == "/stage"
    assert cmd["payload"]["type"] == "null"
    assert cmd["payload"]["name"] == "test_null"


# -- Authentication handshake tests ----------------------------------------


@pytest.mark.asyncio
async def test_auth_handshake_no_auth_required():
    """When server doesn't send auth_required, connect succeeds normally."""
    mock_ws = AsyncMock()
    # Server doesn't send auth_required — recv times out
    mock_ws.recv = AsyncMock(side_effect=asyncio.TimeoutError())

    with patch("synapse_ws.websockets") as mock_websockets:
        mock_websockets.connect = AsyncMock(return_value=mock_ws)
        client = SynapseClient()
        result = await client.connect()
        assert result is True
        assert client._connected is True


@pytest.mark.asyncio
async def test_auth_handshake_success():
    """Client completes auth handshake when server requires it."""
    mock_ws = AsyncMock()
    recv_calls = []

    async def mock_recv():
        recv_calls.append(1)
        if len(recv_calls) == 1:
            return json.dumps({"type": "auth_required", "message": "Authentication required"})
        else:
            return json.dumps({"type": "auth_success", "success": True})

    mock_ws.recv = mock_recv
    sent = []
    async def mock_send(msg):
        sent.append(json.loads(msg))
    mock_ws.send = mock_send

    with patch("synapse_ws.websockets") as mock_websockets, \
         patch("synapse_ws._get_auth_key", return_value="test-secret-key"):
        mock_websockets.connect = AsyncMock(return_value=mock_ws)
        client = SynapseClient()
        result = await client.connect()
        assert result is True
        # Verify authenticate command was sent
        assert len(sent) == 1
        assert sent[0]["type"] == "authenticate"
        assert sent[0]["payload"]["key"] == "test-secret-key"


@pytest.mark.asyncio
async def test_auth_handshake_failed():
    """Client raises SynapseConnectionError when auth fails."""
    mock_ws = AsyncMock()
    recv_calls = []

    async def mock_recv():
        recv_calls.append(1)
        if len(recv_calls) == 1:
            return json.dumps({"type": "auth_required"})
        else:
            return json.dumps({"type": "auth_failed", "error": "Invalid API key"})

    mock_ws.recv = mock_recv
    mock_ws.send = AsyncMock()

    with patch("synapse_ws.websockets") as mock_websockets, \
         patch("synapse_ws._get_auth_key", return_value="wrong-key"):
        mock_websockets.connect = AsyncMock(return_value=mock_ws)
        client = SynapseClient()
        with pytest.raises(SynapseConnectionError, match="Authentication failed"):
            await client.connect()


@pytest.mark.asyncio
async def test_auth_handshake_no_key_configured():
    """Client raises SynapseConnectionError when auth required but no key."""
    mock_ws = AsyncMock()
    mock_ws.recv = AsyncMock(
        return_value=json.dumps({"type": "auth_required"})
    )

    with patch("synapse_ws.websockets") as mock_websockets, \
         patch("synapse_ws._get_auth_key", return_value=None):
        mock_websockets.connect = AsyncMock(return_value=mock_ws)
        client = SynapseClient()
        with pytest.raises(SynapseConnectionError, match="no API key"):
            await client.connect()


def test_get_auth_key_env_var():
    """_get_auth_key reads from SYNAPSE_API_KEY env var."""
    with patch.dict(os.environ, {"SYNAPSE_API_KEY": "env-key-123"}):
        assert _get_auth_key() == "env-key-123"


def test_get_auth_key_none():
    """_get_auth_key returns None when no key configured."""
    with patch.dict(os.environ, {}, clear=True), \
         patch("synapse_ws.os.path.exists", return_value=False):
        assert _get_auth_key() is None
