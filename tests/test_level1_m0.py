"""Level 1, M0 (claude/LEVEL1_BLUEPRINT.md): the three transport bugs.

F1a  The panel's client cleared its session on -32003, which is COOK_ERROR, so an expired session
     (SESSION_INVALID, -32004) was never replaced and every call said "Unknown session" until the
     panel restarted. It now starts a new session and sends the call once more.
F1b  POST /mcp answered a request refused at the session gate with HTTP 200. The MCP Streamable
     HTTP transport says 400 for a missing session and 404 for an unknown one, and 404 is what
     tells a client to initialize again. The JSON-RPC body stays.
F2   The stdio bridge re-sent a command after the connection dropped, even when the send had
     completed and the command may have run. Now only a command that cannot change anything is
     sent again.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from synapse.mcp import protocol as P  # noqa: E402
from synapse.mcp import resend_policy as RP  # noqa: E402
from synapse.mcp import server as S  # noqa: E402
from synapse.mcp._tool_registry import TOOL_DEFS  # noqa: E402
from synapse.mcp.read_only_mode import STOPS_ALWAYS_PASS  # noqa: E402

def _executor_namespace():
    """The panel client classes, loaded from source so stock Python never imports Qt
    (the loader tests/test_mcp_local_client_available.py uses)."""
    import ast
    import http.client
    import threading
    import time
    from typing import Optional

    path = ROOT / "python" / "synapse" / "panel" / "tool_executor.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    wanted = {"MCPUnavailable", "MCPOutcomeUnknown", "_MCPLocalClient"}
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in wanted]
    assert {n.name for n in nodes} == wanted
    ns = {"Optional": Optional, "threading": threading, "json": json, "http": http,
          "time": time, "sys": sys}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    return SimpleNamespace(**{k: ns[k] for k in wanted}, http=http)


TE = _executor_namespace()
_CMD = {entry[0]: entry[1] for entry in TOOL_DEFS}
READ = sorted(name for name in _CMD if S.is_transport_fast_path(name))[0]
WRITE = sorted(name for name in _CMD
               if name not in S._READ_ONLY_TOOLS and name not in STOPS_ALWAYS_PASS)[0]


# ── F2, the policy: which commands may be sent again ─────────────────────────────────

def test_a_command_that_never_left_may_be_sent_again():
    assert RP.may_resend(_CMD[WRITE], sent=False)


def test_a_sent_change_is_never_sent_again():
    assert not RP.may_resend(_CMD[WRITE], sent=True)


def test_a_sent_read_may_be_sent_again():
    assert RP.may_resend(_CMD[READ], sent=True)


def test_a_sent_stop_may_be_sent_again():
    for name in sorted(STOPS_ALWAYS_PASS):
        assert RP.may_resend(_CMD[name], sent=True), name


def test_protocol_commands_pass_and_unknown_commands_do_not():
    assert RP.may_resend("ping", sent=True)
    assert not RP.may_resend("no_such_command_type", sent=True)


# ── F2, the stdio bridge itself ──────────────────────────────────────────────────────

class _DroppingSocket:
    """A WebSocket whose first send lands and then loses the reply."""

    def __init__(self, ms):
        self.ms, self.sent = ms, []

    async def send(self, text):
        command = json.loads(text)
        self.sent.append(command["id"])
        future = self.ms._pending[command["id"]]
        if len(self.sent) == 1:
            future.set_exception(ConnectionError("dropped after the send"))
        else:
            future.set_result({"success": True, "data": {"ok": 1}})

    async def close(self):
        pass


def _stdio(monkeypatch):
    pytest.importorskip("mcp")
    pytest.importorskip("websockets")
    import mcp_server as ms

    socket = _DroppingSocket(ms)

    async def _connection():
        return socket

    monkeypatch.setattr(ms, "_get_connection", _connection)
    return ms, socket


def test_stdio_never_sends_a_possibly_run_change_twice(monkeypatch):
    ms, socket = _stdio(monkeypatch)
    with pytest.raises(ConnectionError, match="may have run"):
        asyncio.run(ms.send_command(_CMD[WRITE], {}))
    assert len(socket.sent) == 1


def test_stdio_sends_a_read_again_after_a_drop(monkeypatch):
    ms, socket = _stdio(monkeypatch)
    assert asyncio.run(ms.send_command(_CMD[READ], {})) == {"ok": 1}
    assert len(socket.sent) == 2


# ── F1a, the panel's client ──────────────────────────────────────────────────────────

def _reply_error(code, message="refused"):
    return {"jsonrpc": "2.0", "id": 1, "error": {"code": code, "message": message}}


def _reply_ok():
    return {"jsonrpc": "2.0", "id": 1, "result": {"content": [], "isError": False}}


def _client(monkeypatch, replies):
    client = TE._MCPLocalClient()
    names = iter(["s1", "s2", "s3"])
    started, posted = [], []

    def ensure():
        with client._lock:
            if client._session_id is None:
                client._session_id = next(names)
                started.append(client._session_id)
            return client._session_id

    def post(body, headers=None, timeout=35.0):
        posted.append((headers or {}).get("Mcp-Session-Id"))
        return replies.pop(0)

    monkeypatch.setattr(client, "_ensure_session", ensure)
    monkeypatch.setattr(client, "_post", post)
    return client, started, posted


def test_an_expired_session_is_replaced_and_the_call_sent_once_more(monkeypatch):
    client, started, posted = _client(
        monkeypatch, [_reply_error(P.SESSION_INVALID, "Unknown session: s1"), _reply_ok()])
    assert client.call_tool("houdini_scene_info", {}) == {"content": [], "isError": False}
    assert started == ["s1", "s2"]
    assert posted == ["s1", "s2"]


def test_two_session_refusals_in_a_row_are_an_error_not_a_loop(monkeypatch):
    client, started, posted = _client(
        monkeypatch, [_reply_error(P.SESSION_INVALID), _reply_error(P.SESSION_INVALID), _reply_ok()])
    with pytest.raises(RuntimeError):
        client.call_tool("houdini_scene_info", {})
    assert len(posted) == 2


def test_a_cook_error_keeps_the_session(monkeypatch):
    client, started, posted = _client(monkeypatch, [_reply_error(P.COOK_ERROR, "cook failed"), _reply_ok()])
    with pytest.raises(RuntimeError, match="cook failed"):
        client.call_tool("houdini_scene_info", {})
    assert posted == ["s1"]
    assert client._session_id == "s1"


class _Response:
    def __init__(self, status, text):
        self.status, self._text = status, text

    def read(self):
        return self._text.encode("utf-8")

    def getheader(self, name):
        return None


def _connection_answering(status, text):
    class _Connection:
        def __init__(self, *args, **kwargs):
            pass

        def connect(self):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return _Response(status, text)

        def close(self):
            pass

    return _Connection


@pytest.mark.parametrize("status", [400, 404])
def test_a_session_gate_status_reads_as_session_invalid_whatever_the_body(monkeypatch, status):
    client = TE._MCPLocalClient()
    client._port = 1
    monkeypatch.setattr(TE.http.client, "HTTPConnection", _connection_answering(status, "Not Found"))
    reply = client._post({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {}},
                         headers={"Mcp-Session-Id": "s1"})
    assert reply["error"]["code"] == P.SESSION_INVALID
    assert reply["id"] == 7


# ── F1b, the server's session gate ───────────────────────────────────────────────────

def _server():
    server = object.__new__(S.MCPServer)
    server._sessions = SimpleNamespace(get_session=lambda session_id: None)
    return server


def test_an_unknown_session_is_404_and_a_missing_one_400_with_the_jsonrpc_body():
    server = _server()
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode("utf-8")
    for session_id, expected in (("gone", 404), (None, 400)):
        response_body, headers = server.handle_request(body, session_id=session_id)
        data, status, content_type, extra = S._post_response(response_body, headers)
        assert status == expected
        assert S.HTTP_STATUS_KEY not in extra
        assert json.loads(data)["error"]["code"] == P.SESSION_INVALID


# ── Constants, not literals (rule 3) ─────────────────────────────────────────────────

_LITERAL = re.compile(r"[=(,\[{:]\s*-32\d{3}\b")


def test_no_jsonrpc_code_is_written_as_a_literal_outside_protocol():
    files = [ROOT / "mcp_server.py", *sorted(ROOT.glob("mcp_tools_*.py"))]
    files += [p for p in sorted((ROOT / "python" / "synapse").rglob("*.py")) if "_vendor" not in p.parts]
    hits = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if rel == "python/synapse/mcp/protocol.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if _LITERAL.search(line.split("#", 1)[0]):
                hits.append("%s:%d" % (rel, number))
    assert not hits, hits
