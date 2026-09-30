"""Level 1, R-6 (claude/LEVEL1_BLUEPRINT.md v1.1, section 2 "On the wire", rule 13).

A tool call that does not end ok comes back as a tool result flagged isError, as MCP specifies for
tool failures, on /mcp and on the stdio bridge. Its first text line reads
``<outcome>: <message> Next: <next>``, and the outcome object rides in ``_meta["synapse/outcome"]``.
JSON-RPC errors stay for protocol failures: a missing or unknown tool name, a session, and
read-only mode, whose message is its outcome line. The panel's client reads the flag. -32006 and
-32007, added in v5.87.0, are withdrawn.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from synapse.core import outcomes as O  # noqa: E402
from synapse.mcp import protocol as P  # noqa: E402
from synapse.mcp import server as S  # noqa: E402
from synapse.mcp._tool_registry import TOOL_DEFS  # noqa: E402
from synapse.mcp.read_only_mode import STOPS_ALWAYS_PASS  # noqa: E402

_CMD = {entry[0]: entry[1] for entry in TOOL_DEFS}
WRITE = sorted(name for name in _CMD
               if name not in S._READ_ONLY_TOOLS and name not in STOPS_ALWAYS_PASS)[0]
READ = "synapse_ping"


def _first_line(result: dict) -> str:
    return result["content"][0]["text"]


def _meta(result: dict) -> dict:
    return result["_meta"]["synapse/outcome"]


# ── The outcome line and the result ──────────────────────────────────────────────────────

def test_the_outcome_line_names_the_class_the_message_and_the_next_step():
    line = O.outcome_line(O.info("tool.failed", "Couldn't find a node").to_dict())
    assert line == "failed: Couldn't find a node Next: Read the error; it names what failed."


def test_a_message_that_names_its_own_fix_does_not_repeat_it():
    refusal = ("SYNAPSE is in read-only mode. Unset SYNAPSE_MCP_READ_ONLY in Houdini's "
               "environment to allow changes.")
    line = O.outcome_line(O.info("policy.read_only", refusal).to_dict())
    assert line == "refused: " + refusal


def test_an_outcome_line_is_never_prefixed_twice():
    for code in O.CODES:
        data = O.info(code, "Something happened").to_dict()
        line = O.outcome_line(data)
        assert O.outcome_line(data, line) == line
        assert O.describe(data, line) == line
        assert line.count(data["outcome"] + ":") == 1


def test_every_outcome_but_ok_sets_the_flag():
    for code, (outcome, _dispatched, _next) in O.CODES.items():
        result = O.tool_result(O.info(code, "m"))
        assert result["isError"] is True, code
        assert _first_line(result).startswith(outcome.value + ": "), code
        assert _meta(result)["code"] == code
    ok = O.tool_result({"outcome": "ok", "code": "x", "message": "m", "next": "", "dispatched": "yes"})
    assert ok["isError"] is False


def test_a_failed_result_keeps_its_non_text_content():
    result = O.tool_result(O.info("tool.failed", "m"), {"content": [
        {"type": "text", "text": "m"}, {"type": "image", "data": "b64", "mimeType": "image/png"}]})
    assert [item["type"] for item in result["content"]] == ["text", "image"]


def test_the_busy_and_needs_artist_codes_are_withdrawn():
    assert not hasattr(P, "SERVER_BUSY") and not hasattr(P, "NEEDS_ARTIST")
    assert set(P.OUTCOME_BY_JSONRPC_CODE) == {
        P.PARSE_ERROR, P.INVALID_REQUEST, P.METHOD_NOT_FOUND, P.INVALID_PARAMS, P.INTERNAL_ERROR,
        P.SAFETY_GUARD_REJECTION, P.NODE_NOT_FOUND, P.COOK_ERROR, P.SESSION_INVALID,
        P.READ_ONLY_REFUSED}


# ── /mcp ────────────────────────────────────────────────────────────────────────────────

def _server(**attrs):
    server = object.__new__(S.MCPServer)
    server._get_handler = lambda: None
    server._enable_resilience = False
    server._rate_limiter = None
    server._circuit_breaker = None
    server._latency_alpha, server._avg_latency = 0.2, 0.0
    server.broadcast_event = lambda *args, **kwargs: None
    for key, value in attrs.items():
        setattr(server, key, value)
    return server


def _dispatch_answers(monkeypatch, result):
    monkeypatch.delenv("SYNAPSE_MCP_READ_ONLY", raising=False)
    monkeypatch.setenv("SYNAPSE_LOOP_ENABLED", "0")
    monkeypatch.setattr(S, "_STALL_DETECT_AVAILABLE", False, raising=False)
    monkeypatch.setattr(S, "dispatch_tool", lambda handler, name, arguments: result)
    import synapse.server.main_thread as main_thread
    monkeypatch.setattr(main_thread, "run_on_main", lambda fn, **kwargs: fn())


def _failed(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": True}


def _call(server, name: str) -> dict:
    return server._handle_tools_call({"name": name, "arguments": {}})


@pytest.mark.parametrize("name, text, code, outcome", [
    (READ, "Couldn't find a node at /obj/x", "tool.failed", "failed"),
    (WRITE, "Couldn't find a node at /obj/x", "tool.failed", "failed"),
    (WRITE, "The main thread timeout was reached", "transport.timeout", "unknown_outcome"),
], ids=["read-failed", "change-failed", "change-timeout"])
def test_mcp_a_tool_failure_is_a_result_flagged_with_its_outcome(monkeypatch, name, text, code,
                                                                  outcome):
    _dispatch_answers(monkeypatch, _failed(text))
    result = _call(_server(), name)
    assert result["isError"] is True
    assert _first_line(result).startswith("%s: %s Next: " % (outcome, text))
    assert _meta(result)["code"] == code


def test_mcp_a_busy_server_is_a_retryable_result(monkeypatch):
    _dispatch_answers(monkeypatch, {"content": []})
    limiter = SimpleNamespace(acquire=lambda key: (False, {"reason": "r", "retry_after": 2.0}))
    result = _call(_server(_enable_resilience=True, _rate_limiter=limiter), WRITE)
    assert result["isError"] is True
    assert _first_line(result).startswith("retryable: ")
    assert (_meta(result)["code"], _meta(result)["retry_after_s"]) == ("server.busy", 2.0)


def test_mcp_a_failure_records_no_breaker_success(monkeypatch):
    _dispatch_answers(monkeypatch, _failed("Couldn't find a node at /obj/x"))
    calls = []
    breaker = SimpleNamespace(can_execute=lambda: (True, {}),
                              record_success=lambda: calls.append("success"),
                              record_failure=lambda: calls.append("failure"))
    for name in (READ, WRITE):
        _call(_server(_circuit_breaker=breaker), name)
    assert "success" not in calls


def test_mcp_a_success_is_not_flagged(monkeypatch):
    answer = {"content": [{"type": "text", "text": "{}"}]}
    _dispatch_answers(monkeypatch, answer)
    assert "isError" not in _call(_server(), READ)


def test_mcp_an_exception_in_a_tool_call_is_an_unknown_outcome_result(monkeypatch):
    monkeypatch.delenv("SYNAPSE_MCP_READ_ONLY", raising=False)

    def wedged(handler, name, arguments):
        raise RuntimeError("wedged")

    monkeypatch.setattr(S, "dispatch_tool", wedged)
    server = S.MCPServer(handler=SimpleNamespace(handle=lambda command: None))
    _, headers = server.handle_request(json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}).encode("utf-8"))
    reply, _ = server.handle_request(json.dumps({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": READ, "arguments": {}}}).encode("utf-8"),
        session_id=headers["Mcp-Session-Id"])
    answer = json.loads(reply)
    assert "error" not in answer
    result = answer["result"]
    assert result["isError"] is True
    assert _first_line(result).startswith("unknown_outcome: Internal error: wedged")
    assert _meta(result)["code"] == "tool.internal"


def test_mcp_an_unknown_tool_is_a_protocol_error():
    with pytest.raises(P.JsonRpcError) as caught:
        _call(_server(), "synapse_not_a_tool")
    assert caught.value.code == P.INVALID_PARAMS
    assert caught.value.data["outcome"]["code"] == "request.unknown_tool"


def test_mcp_every_listed_tool_is_known():
    from synapse.mcp.tools import get_tools, has_tool

    assert all(has_tool(tool["name"]) for tool in get_tools())


def test_mcp_read_only_keeps_its_code_and_its_message_is_the_outcome_line(monkeypatch):
    monkeypatch.setenv("SYNAPSE_MCP_READ_ONLY", "1")
    with pytest.raises(P.JsonRpcError) as caught:
        _call(_server(), WRITE)
    assert caught.value.code == P.READ_ONLY_REFUSED
    assert str(caught.value).startswith("refused: SYNAPSE is in read-only mode")
    assert "Next:" not in str(caught.value)
    assert caught.value.data["outcome"]["code"] == "policy.read_only"


# ── The panel's client ───────────────────────────────────────────────────────────────────

def _executor_namespace():
    """The panel client classes, loaded from source so stock Python never imports Qt."""
    import ast
    import http.client
    import threading
    import time
    from typing import Optional

    path = ROOT / "python" / "synapse" / "panel" / "tool_executor.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    wanted = {"MCPUnavailable", "MCPOutcomeUnknown", "_MCPLocalClient"}
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in wanted]
    ns = {"Optional": Optional, "threading": threading, "json": json, "http": http,
          "time": time, "sys": sys}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    return SimpleNamespace(**{k: ns[k] for k in wanted})


TE = _executor_namespace()


def _panel(monkeypatch, payload):
    client = TE._MCPLocalClient()
    posts = []
    monkeypatch.setattr(client, "_ensure_session", lambda: "s1")

    def post(body, headers=None, timeout=35.0):
        posts.append(body)
        return {"jsonrpc": "2.0", "id": 1, "result": payload}

    monkeypatch.setattr(client, "_post", post)
    return client, posts


def test_the_panel_raises_the_outcome_line_and_never_sends_the_call_again(monkeypatch):
    client, posts = _panel(monkeypatch, O.tool_result(O.info("tool.failed", "Couldn't find a node")))
    with pytest.raises(RuntimeError) as caught:
        client.call_tool(WRITE, {})
    assert str(caught.value) == ("failed: Couldn't find a node "
                                 "Next: Read the error; it names what failed.")
    assert len(posts) == 1


def test_the_panel_shows_a_read_only_refusal_once(monkeypatch):
    refused = O.info("policy.read_only", "SYNAPSE is in read-only mode. Unset "
                     "SYNAPSE_MCP_READ_ONLY in Houdini's environment to allow changes.").to_dict()
    line = O.outcome_line(refused)
    client = TE._MCPLocalClient()
    monkeypatch.setattr(client, "_ensure_session", lambda: "s1")
    monkeypatch.setattr(client, "_post", lambda body, headers=None, timeout=35.0: {
        "jsonrpc": "2.0", "id": 1,
        "error": {"code": P.READ_ONLY_REFUSED, "message": line, "data": {"outcome": refused}}})
    with pytest.raises(RuntimeError) as caught:
        client.call_tool(WRITE, {})
    assert str(caught.value) == line
    assert str(caught.value).startswith("refused: SYNAPSE is in read-only mode")


def test_the_panel_reads_the_first_text_when_there_is_no_meta(monkeypatch):
    client, _ = _panel(monkeypatch, _failed("plain failure"))
    with pytest.raises(RuntimeError, match="^plain failure$"):
        client.call_tool(WRITE, {})


def test_the_panel_returns_a_result_that_is_not_flagged(monkeypatch):
    answer = {"content": [{"type": "text", "text": "{}"}]}
    client, _ = _panel(monkeypatch, answer)
    assert client.call_tool(READ, {}) == answer


# ── The stdio bridge ─────────────────────────────────────────────────────────────────────

def _ms():
    pytest.importorskip("mcp")
    pytest.importorskip("websockets")
    import mcp_server as ms

    return ms


def _through_the_sdk(ms, name, arguments):
    """The result the pinned MCP SDK hands the client for this call."""
    from mcp import types

    request = types.CallToolRequest(method="tools/call", params=types.CallToolRequestParams(
        name=name, arguments=arguments))
    return asyncio.run(ms.server.request_handlers[types.CallToolRequest](request)).root


_RAISED = {
    "not-reachable": (lambda ms: ms._tagged(
        ConnectionError, "houdini.not_reachable", "Houdini isn't answering (refused)"),
        "unrecoverable", "houdini.not_reachable"),
    "reply-lost": (lambda ms: ms._tagged(
        ConnectionError, "transport.reply_lost", ms._lost_after_send("ping")),
        "unknown_outcome", "transport.reply_lost"),
    "read-timeout": (lambda ms: ms._tagged(
        TimeoutError, "transport.read_retry", "The ping command took too long to respond"),
        "retryable", "transport.read_retry"),
    "read-only": (lambda ms: ms._tagged(
        RuntimeError, O.info("policy.read_only", "refused").to_dict(), "refused"),
        "refused", "policy.read_only"),
    "failed": (lambda ms: ms._tagged(RuntimeError, "tool.failed", "Node not found: /obj/nope"),
               "failed", "tool.failed"),
}


@pytest.mark.parametrize("route", ["ported", "legacy"])
@pytest.mark.parametrize("case", sorted(_RAISED))
def test_stdio_every_failure_is_flagged_with_its_outcome_line(monkeypatch, route, case):
    ms = _ms()
    make, outcome, code = _RAISED[case]

    async def send(cmd_type, payload=None):
        raise make(ms)

    monkeypatch.setattr(ms, "send_command", send)
    if route == "legacy":
        monkeypatch.setattr(ms, "_PORTED_WAVE_TOOLS", frozenset())
    ms._ported_dispatcher = None
    result = _through_the_sdk(ms, READ, {})
    assert result.isError is True
    assert result.content[0].text.startswith(outcome + ": ")
    assert result.meta["synapse/outcome"]["code"] == code


def test_stdio_a_success_is_not_flagged(monkeypatch):
    ms = _ms()

    async def send(cmd_type, payload=None):
        return {"pong": True}

    monkeypatch.setattr(ms, "send_command", send)
    ms._ported_dispatcher = None
    result = _through_the_sdk(ms, READ, {})
    assert result.isError is False


def test_stdio_send_command_attaches_the_outcome_it_raises(monkeypatch):
    ms = _ms()

    async def refused():
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(ms, "_get_connection", refused)
    with pytest.raises(ConnectionError) as caught:
        asyncio.run(ms.send_command("ping", {}))
    assert caught.value.outcome["code"] == "houdini.not_reachable"
    assert str(caught.value) == O.outcome_line(caught.value.outcome)


# ── The cognitive layer carries the outcome ─────────────────────────────────────────────────

def test_the_dispatcher_keeps_the_outcome_an_exception_carried():
    from synapse.cognitive.dispatcher import Dispatcher

    carried = O.info("transport.reply_lost", "lost").to_dict()

    def lost():
        exc = ConnectionError("lost")
        exc.outcome = carried
        raise exc

    def plain():
        raise ValueError("x")

    dispatcher = Dispatcher(is_testing=True, tools={"lost": lost, "plain": plain})
    error = dispatcher.execute("lost", {})
    assert error.outcome == carried and error.to_dict()["outcome"] == carried
    error = dispatcher.execute("plain", {})
    assert error.outcome is None and "outcome" not in error.to_dict()


def test_the_passthrough_gives_an_argument_error_the_legacy_outcome():
    from synapse.cognitive.tools import ws_passthrough as W

    W.configure_transport(lambda command_type, payload: {"ok": True})
    try:
        tool = W.make_passthrough_tool("t", "c", lambda arguments: {"x": arguments["needed"]})
        with pytest.raises(KeyError) as caught:
            tool()
        assert caught.value.outcome == O.for_bad_arguments(KeyError("needed")).to_dict()
    finally:
        W.reset_transport()
