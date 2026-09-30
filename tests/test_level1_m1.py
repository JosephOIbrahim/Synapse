"""Level 1, M1 (claude/LEVEL1_BLUEPRINT.md, sections 2 and 5): one outcome vocabulary on every route.

Every refused or failed call says what happened and what to do next: on /mcp in the tool result
flagged isError (R-6, tests/test_level1_r6.py) or, for a protocol failure, in the JSON-RPC
error's data; on the WebSocket in the response's data; and in the text the stdio bridge and the
panel raise. The walk tests check that no JSON-RPC code and no client exception is left without an
outcome, so a new one cannot be added silently.
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
from synapse.core.protocol import SynapseResponse  # noqa: E402
from synapse.mcp import protocol as P  # noqa: E402
from synapse.mcp import server as S  # noqa: E402
from synapse.mcp._tool_registry import TOOL_DEFS  # noqa: E402
from synapse.mcp.read_only_mode import STOPS_ALWAYS_PASS  # noqa: E402

_CMD = {entry[0]: entry[1] for entry in TOOL_DEFS}
WRITE = sorted(name for name in _CMD
               if name not in S._READ_ONLY_TOOLS and name not in STOPS_ALWAYS_PASS)[0]


def _jsonrpc_codes():
    return {name: value for name, value in vars(P).items()
            if name.isupper() and isinstance(value, int) and -32768 <= value <= -32000}


# ── The vocabulary ───────────────────────────────────────────────────────────────────

def test_every_code_names_an_outcome_a_dispatch_state_and_a_next_step():
    for code, (outcome, dispatched, next_step) in O.CODES.items():
        assert isinstance(outcome, O.Outcome), code
        assert dispatched in O.DISPATCHED, code
        assert next_step.strip().endswith("."), code


def test_only_a_read_may_be_retried_after_it_may_have_run():
    for code, (outcome, dispatched, _next) in O.CODES.items():
        if outcome is O.Outcome.RETRYABLE and dispatched != "no":
            assert code == "transport.read_retry", code


def test_a_busy_answer_names_its_wait():
    busy = O.info("server.busy", "busy", retry_after_s=3.0)
    assert busy.next == "Wait 3 s, then send it again."
    assert busy.to_dict()["retry_after_s"] == 3.0


def test_describe_is_the_outcome_line():
    text = O.describe(O.info("policy.read_only", "refused").to_dict(), "refused")
    assert text.startswith("refused: refused Next: Unset SYNAPSE_MCP_READ_ONLY")
    assert O.describe(None, "plain") == "plain"


# ── /mcp: every JSON-RPC code maps, and every error carries its outcome ──────────────────

def test_every_jsonrpc_code_maps_to_an_outcome():
    codes = _jsonrpc_codes()
    assert set(codes.values()) == set(P.OUTCOME_BY_JSONRPC_CODE)
    for name, value in codes.items():
        assert P.OUTCOME_BY_JSONRPC_CODE[value] in O.CODES, name


def test_every_jsonrpc_error_carries_its_outcome():
    for name, value in _jsonrpc_codes().items():
        error = json.loads(P.jsonrpc_error(1, value, "m"))["error"]
        assert error["data"]["outcome"]["code"] == P.OUTCOME_BY_JSONRPC_CODE[value], name


def test_a_caller_that_knows_its_case_keeps_it():
    known = O.info("session.missing", "m").to_dict()
    error = json.loads(P.jsonrpc_error(1, P.SESSION_INVALID, "m", {"outcome": known, "detail": "x"}))["error"]
    assert error["data"]["outcome"]["code"] == "session.missing"
    assert error["data"]["detail"] == "x"


def _gate_server(**attrs):
    server = object.__new__(S.MCPServer)
    server._get_handler = lambda: None
    server._enable_resilience = True
    server._rate_limiter = None
    server._circuit_breaker = None
    for key, value in attrs.items():
        setattr(server, key, value)
    return server


def _busy(result):
    """A busy answer is a result flagged isError whose outcome is retryable (R-6)."""
    assert result["isError"] is True
    assert result["content"][0]["text"].startswith("retryable: ")
    return result["_meta"]["synapse/outcome"]


def test_the_rate_limiter_answers_busy_with_the_wait(monkeypatch):
    monkeypatch.delenv("SYNAPSE_MCP_READ_ONLY", raising=False)
    monkeypatch.setattr(S, "_STALL_DETECT_AVAILABLE", False, raising=False)
    limiter = SimpleNamespace(acquire=lambda key: (False, {"reason": "r", "retry_after": 3.0}))
    outcome = _busy(_gate_server(_rate_limiter=limiter)._handle_tools_call({"name": WRITE, "arguments": {}}))
    assert (outcome["code"], outcome["retry_after_s"]) == ("server.busy", 3.0)
    assert outcome["next"] == "Wait 3 s, then send it again."


def test_the_circuit_breaker_answers_busy_with_the_wait(monkeypatch):
    monkeypatch.delenv("SYNAPSE_MCP_READ_ONLY", raising=False)
    monkeypatch.setattr(S, "_STALL_DETECT_AVAILABLE", False, raising=False)
    breaker = SimpleNamespace(can_execute=lambda: (False, {"reason": "open", "retry_after": 30.0}))
    outcome = _busy(_gate_server(_circuit_breaker=breaker)._handle_tools_call({"name": WRITE, "arguments": {}}))
    assert (outcome["code"], outcome["retry_after_s"]) == ("server.busy", 30.0)


def test_a_stalled_main_thread_answers_houdini_busy(monkeypatch):
    monkeypatch.delenv("SYNAPSE_MCP_READ_ONLY", raising=False)
    monkeypatch.setattr(S, "_STALL_DETECT_AVAILABLE", True, raising=False)
    monkeypatch.setattr(S, "is_main_thread_stalled", lambda: True, raising=False)
    monkeypatch.setattr(S, "probe_main_thread", lambda: False, raising=False)
    monkeypatch.setattr(S, "stall_state", lambda: {"consecutive_timeouts": 3}, raising=False)
    outcome = _busy(_gate_server()._handle_tools_call({"name": WRITE, "arguments": {}}))
    assert outcome["code"] == "houdini.busy"


def test_a_missing_session_is_refused_and_an_unknown_one_is_retryable():
    server = object.__new__(S.MCPServer)
    server._sessions = SimpleNamespace(get_session=lambda session_id: None)
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode("utf-8")
    for session_id, code, outcome in ((None, "session.missing", "refused"),
                                      ("gone", "session.expired", "retryable")):
        reply, _headers = server.handle_request(body, session_id=session_id)
        found = json.loads(reply)["error"]["data"]["outcome"]
        assert (found["code"], found["outcome"]) == (code, outcome)


# ── WebSocket: every failed response carries an outcome ───────────────────────────────

@pytest.mark.parametrize("data, code", [
    (None, "tool.failed"),
    ({"read_only_mode": True}, "policy.read_only"),
    ({"retry_after": 2.0}, "server.busy"),
    ({"outcome": {"outcome": "refused", "code": "policy.rbac", "next": "Ask."}}, "policy.rbac"),
])
def test_every_failed_websocket_response_carries_an_outcome(data, code):
    wire = json.loads(SynapseResponse(id="c", success=False, error="no", data=data).to_json())
    assert wire["data"]["outcome"]["code"] == code


def test_a_success_is_left_as_it_is():
    wire = json.loads(SynapseResponse(id="c", success=True, data={"a": 1}).to_json())
    assert wire["data"] == {"a": 1}


# ── stdio bridge ─────────────────────────────────────────────────────────────────────────

def _mcp_server():
    pytest.importorskip("mcp")
    pytest.importorskip("websockets")
    import mcp_server as ms

    return ms


def test_stdio_says_what_to_do_when_houdini_is_not_answering(monkeypatch):
    ms = _mcp_server()

    async def refused():
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(ms, "_get_connection", refused)
    with pytest.raises(ConnectionError) as caught:
        asyncio.run(ms.send_command("ping", {}))
    assert caught.value.outcome["code"] == "houdini.not_reachable"
    assert str(caught.value).startswith("unrecoverable: ")
    assert "click Connect" in str(caught.value)


def test_stdio_passes_a_failure_outcome_through(monkeypatch):
    ms = _mcp_server()
    refusal = O.info("policy.read_only", "refused").to_dict()

    class _Socket:
        async def send(self, text):
            command = json.loads(text)
            ms._pending[command["id"]].set_result(
                {"success": False, "error": "refused", "data": {"outcome": refusal}})

        async def close(self):
            pass

    async def connection():
        return _Socket()

    monkeypatch.setattr(ms, "_get_connection", connection)
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(ms.send_command(_CMD[WRITE], {}))
    assert caught.value.outcome["code"] == "policy.read_only"
    assert str(caught.value).startswith("refused: refused Next: ")


# ── the panel's client ───────────────────────────────────────────────────────────────────

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


def test_the_panel_client_exceptions_declare_their_outcomes():
    assert O.for_exception(TE.MCPUnavailable("x")).outcome is O.Outcome.UNRECOVERABLE
    assert O.for_exception(TE.MCPOutcomeUnknown("x")).outcome is O.Outcome.UNKNOWN_OUTCOME


def test_the_panel_shows_the_next_step_of_a_refusal(monkeypatch):
    client = TE._MCPLocalClient()
    refusal = O.info("policy.read_only", "refused").to_dict()
    monkeypatch.setattr(client, "_ensure_session", lambda: "s1")
    monkeypatch.setattr(client, "_post", lambda body, headers=None, timeout=35.0: {
        "jsonrpc": "2.0", "id": 1,
        "error": {"code": P.READ_ONLY_REFUSED, "message": "refused", "data": {"outcome": refusal}}})
    with pytest.raises(RuntimeError) as caught:
        client.call_tool(WRITE, {})
    assert "Next: Unset SYNAPSE_MCP_READ_ONLY" in str(caught.value)
