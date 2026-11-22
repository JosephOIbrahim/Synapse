"""The auth handshake works whichever WebSocket frame type carries it (v5.104.1).

Seat, 2026-11-22: v5.104.0 minted ~/.synapse/auth.key, so the Houdini server asked
for auth for the first time. mcp_server.py sent its ``authenticate`` message with
``_dumps`` (bytes, so a BINARY frame), and the hwebserver adapter's ``receive``
returned early on any binary frame. Every key-holding client then waited 5 s and
failed with "didn't respond to authentication". A live probe on 22.0.400 showed it:
a binary auth frame got no reply, and the same JSON as text got auth_success.

Both sides are pinned here:
  * the client sends a TEXT frame;
  * the server decodes a UTF-8 binary frame, so older clients still authenticate,
    and decoding never skips the auth gate.

Standalone: no hou, no hwebserver, no network. The adapter's ``receive`` is
AST-extracted like tests/test_r015_service_error_breaker.py does.
"""
from __future__ import annotations

import ast
import asyncio
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

from synapse.server.auth import AUTH_COMMAND_TYPE, authenticate

ROOT = Path(__file__).resolve().parents[1]
KEY = "frame-type-test-key-0123456789abcdef"


def _receive():
    path = ROOT / "python/synapse/server/hwebserver_adapter.py"
    node = next(n for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "receive")
    ns = {
        "__name__": "synapse.server.hwebserver_adapter",
        "__package__": "synapse.server",
        "json": json,
        "logger": logging.getLogger("auth-frame-test"),
        "AUTH_COMMAND_TYPE": AUTH_COMMAND_TYPE,
        "authenticate": authenticate,
        "PROTOCOL_VERSION": "4.0.0",
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
    return ns["receive"]


def _connection():
    sent, closed = [], []

    async def send(text, **kwargs):
        sent.append(json.loads(text))

    async def close(*args, **kwargs):
        closed.append(args)

    conn = SimpleNamespace(_authenticated=False, _auth_key=KEY, _client_id="frame-test",
                           send=send, close=close)
    return conn, sent, closed


def _auth_frame(key=KEY):
    return json.dumps({"type": AUTH_COMMAND_TYPE, "id": "auth-handshake", "payload": {"key": key}},
                      sort_keys=True)


def test_text_auth_frame_authenticates():
    conn, sent, closed = _connection()
    asyncio.run(_receive()(conn, text_data=_auth_frame()))
    assert conn._authenticated is True
    assert [m["type"] for m in sent] == ["auth_success"]
    assert closed == []


def test_binary_auth_frame_authenticates():
    conn, sent, closed = _connection()
    asyncio.run(_receive()(conn, bytes_data=_auth_frame().encode("utf-8")))
    assert conn._authenticated is True
    assert [m["type"] for m in sent] == ["auth_success"]
    assert closed == []


def test_binary_auth_frame_with_wrong_key_is_refused_and_closed():
    conn, sent, closed = _connection()
    asyncio.run(_receive()(conn, bytes_data=_auth_frame("not-the-key").encode("utf-8")))
    assert conn._authenticated is False
    assert [m["type"] for m in sent] == ["auth_failed"]
    assert len(closed) == 1


def test_non_utf8_binary_frame_neither_authenticates_nor_raises():
    conn, sent, closed = _connection()
    asyncio.run(_receive()(conn, bytes_data=b"\xff\xfe\x00not-json"))
    assert conn._authenticated is False
    assert sent == []


def test_a_binary_command_before_auth_cannot_skip_the_gate():
    conn, sent, closed = _connection()
    command = json.dumps({"type": "ping", "id": "p1", "payload": {}})
    asyncio.run(_receive()(conn, bytes_data=command.encode("utf-8")))
    assert conn._authenticated is False
    assert [m["type"] for m in sent] == ["auth_failed"]


# ---------------------------------------------------------------------------
# Client side: mcp_server._auth_handshake sends a TEXT frame
# ---------------------------------------------------------------------------

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _FakeWS:
    def __init__(self):
        self.sent = []
        self._inbox = [json.dumps({"type": "auth_required", "protocol_version": "4.0.0"}),
                       json.dumps({"type": "auth_success", "success": True})]

    async def recv(self):
        return self._inbox.pop(0)

    async def send(self, frame):
        self.sent.append(frame)


def test_client_sends_the_auth_frame_as_text(monkeypatch):
    import mcp_server  # a real import: a skip here would hide the client side
    monkeypatch.setattr(mcp_server, "_get_auth_key", lambda: KEY)
    ws = _FakeWS()
    asyncio.run(mcp_server._auth_handshake(ws))
    assert len(ws.sent) == 1
    assert isinstance(ws.sent[0], str), "a bytes frame goes out as BINARY, which the server ignored"
    msg = json.loads(ws.sent[0])
    assert msg["type"] == AUTH_COMMAND_TYPE and msg["payload"]["key"] == KEY
