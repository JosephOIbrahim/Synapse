"""HTTP header names are case-insensitive (RFC 9110 section 5.1).

Found 2026-09-28 while connecting Claude Code to SYNAPSE's /mcp endpoint. Node's MCP
client sends ``mcp-session-id`` in lowercase, and the handler's
``request.headers().get("Mcp-Session-Id")`` missed it, so every call after initialize
failed with "Missing Mcp-Session-Id header. Send initialize first." A lowercase
``origin`` also read as "no Origin" and skipped the DNS-rebinding check.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from synapse.server.auth import header_value  # noqa: E402


@pytest.mark.parametrize("sent", ["Mcp-Session-Id", "mcp-session-id", "MCP-SESSION-ID", "mCp-SeSsIoN-iD"])
def test_header_value_ignores_case(sent):
    assert header_value({sent: "abc"}, "Mcp-Session-Id") == "abc"


def test_header_value_defaults():
    assert header_value({}, "Origin", "") == ""
    assert header_value(None, "Origin", "x") == "x"
    assert header_value({"Other": "1"}, "Origin") is None
    assert header_value({1: "not a name"}, "Origin", "") == ""


def test_exact_case_wins():
    assert header_value({"origin": "b", "Origin": "a"}, "Origin") == "a"


def test_no_case_sensitive_header_reads_left():
    for rel in ("python/synapse/mcp/server.py", "python/synapse/server/hwebserver_adapter.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert ".headers().get(" not in src, rel


# The /mcp handler only exists when hwebserver imports, so drive it in a child process
# with a minimal stand-in for hwebserver. Every header is sent in lowercase, as Node does.
_PROBE = r"""
import json, sys, types
captured = {}
hw = types.ModuleType("hwebserver")
def urlHandler(path, **kw):
    def deco(fn):
        captured[path] = fn
        return fn
    return deco
class Response:
    def __init__(self, body="", status=200, content_type="text/plain"):
        self.body, self.status, self.content_type, self.headers = body, status, content_type, {}
    def setHeader(self, key, value):
        self.headers[key] = value
class WebSocket:
    pass
hw.urlHandler, hw.Response, hw.WebSocket = urlHandler, Response, WebSocket
hw.webSocket = lambda *a, **k: (lambda cls: cls)
sys.modules["hwebserver"] = hw
import synapse.mcp.server
handler = captured["/mcp"]
class Req:
    def __init__(self, headers, body):
        self._h, self._b = headers, body
    def method(self):
        return "POST"
    def headers(self):
        return self._h
    def body(self):
        return self._b
def post(msg, headers):
    return handler(Req(headers, json.dumps(msg).encode("utf-8")))
auth = "Bearer header-case-test-key"
init = post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "t", "version": "0"}}},
            {"content-type": "application/json", "authorization": auth})
sid = init.headers.get("Mcp-Session-Id")
listed = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
              {"mcp-session-id": sid, "authorization": auth})
evil = post({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}},
            {"mcp-session-id": sid, "authorization": auth, "origin": "http://evil.example"})
nokey = post({"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}},
             {"mcp-session-id": sid})
print("RESULT " + json.dumps({
    "init": init.status, "sid": bool(sid),
    "list": listed.status, "tools": '"tools"' in (listed.body or ""),
    "evil": evil.status, "nokey": nokey.status}))
"""


def test_mcp_handler_accepts_lowercase_headers(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "python"), env.get("PYTHONPATH", "")])
    env["SYNAPSE_API_KEY"] = "header-case-test-key"
    env.pop("SYNAPSE_DEPLOY_MODE", None)
    env["HOME"] = env["USERPROFILE"] = str(tmp_path)
    proc = subprocess.run([sys.executable, "-c", _PROBE], cwd=str(tmp_path), env=env,
                          capture_output=True, text=True, timeout=180)
    lines = [l for l in proc.stdout.splitlines() if l.startswith("RESULT ")]
    assert lines, proc.stdout[-2000:] + proc.stderr[-2000:]
    got = json.loads(lines[-1][len("RESULT "):])
    assert got["init"] == 200 and got["sid"], got
    assert got["list"] == 200 and got["tools"], got      # lowercase mcp-session-id + authorization
    assert got["evil"] == 403, got                       # lowercase origin is still checked
    assert got["nokey"] == 401, got                      # auth still required
