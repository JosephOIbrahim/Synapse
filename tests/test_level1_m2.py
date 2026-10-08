"""Level 1, M2: the preflight inside synapse_health (ruling R-5), and the gate the transports run.

claude/LEVEL1_BLUEPRINT.md section 3. Before a session's first change, and again after any
retryable or unrecoverable outcome, SYNAPSE checks that Houdini can take a change: its main thread
answers within 250 ms, no scene is loading, undo is on, and the stdio bridge runs the same SYNAPSE
release as Houdini. A check that fails, or cannot be observed, refuses the change before it is
sent and names the fix. Reads and stop controls always pass. synapse_health reports the same checks
on demand, with read-only mode, free disk and RAM. The scene check (8) waits for R-7.

Houdini sits behind one seam, the hop; these tests give it a fake one. Without Houdini in the
process there is no hop, and the gate does not apply.
"""
from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import synapse  # noqa: E402
from synapse.core import outcomes as O  # noqa: E402
from synapse.core import preflight as PF  # noqa: E402
from synapse.core.protocol import SynapseCommand, SynapseResponse  # noqa: E402
from synapse.mcp import read_only_mode as RO  # noqa: E402
from synapse.mcp import server as S  # noqa: E402
from synapse.mcp._tool_registry import TOOL_DEFS  # noqa: E402
from synapse.server import preflight_gate as G  # noqa: E402

_CMD = {entry[0]: entry[1] for entry in TOOL_DEFS}
CHANGE = "houdini_set_parm"
READ = "synapse_ping"
STOP = "tops_cancel_cook"
FARM = "synapse_farm_submit"
READY = {"loading": False, "undo_enabled": True, "hip_path": "C:/show/shot/shot.hip"}


@pytest.fixture(autouse=True)
def _fresh():
    PF.reset()
    yield
    PF.reset()


class Hop:
    """A fake hop onto Houdini's main thread: it counts its calls and answers as told."""

    def __init__(self, facts=None, error=None):
        self.facts = dict(READY if facts is None else facts)
        self.error = error
        self.calls = 0

    def __call__(self, timeout_s):
        self.calls += 1
        assert timeout_s == PF.PROBE_TIMEOUT_S == 0.25
        if self.error is not None:
            raise self.error
        return dict(self.facts)


def _houdini(monkeypatch, hop):
    """This process has Houdini, and *hop* is its main thread."""
    monkeypatch.setattr(G, "houdini_hop", lambda: hop)
    return hop


def _refused(outcome, code, category):
    assert outcome is not None, "the change was admitted"
    data = outcome if isinstance(outcome, dict) else outcome.to_dict()
    assert (data["code"], data["outcome"], data["dispatched"]) == (code, category, "no")
    assert data["message"].endswith("The change was not sent.")
    return data


# ── The checks ───────────────────────────────────────────────────────────────────────────

def test_a_change_is_exactly_what_read_only_mode_refuses(monkeypatch):
    """The two rules never disagree about what a change is. Reads and stops always pass; the gate
    also lets farm controls through (test_farm_controls_pass_without_a_hop)."""
    monkeypatch.setenv(RO.ENV, "1")
    for name in _CMD:
        assert RO.is_change(name) == bool(RO.refusal_for_tool(name)), name
    assert RO.is_change(CHANGE) and RO.is_change(FARM)
    assert not RO.is_change(READ) and not RO.is_change("synapse_health")
    assert not any(RO.is_change(name) for name in RO.STOPS_ALWAYS_PASS)


def test_a_ready_houdini_admits_the_change_with_one_hop():
    hop = Hop()
    assert PF.gate(hop) is None
    assert hop.calls == 1


def test_a_ready_answer_is_remembered_for_ten_seconds(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(PF, "_clock", lambda: clock[0])
    hop = Hop()
    assert PF.gate(hop) is None and PF.gate(hop) is None
    assert hop.calls == 1
    clock[0] += PF.CACHE_S + 0.5
    assert PF.gate(hop) is None
    assert hop.calls == 2
    PF.invalidate()
    assert PF.gate(hop) is None
    assert hop.calls == 3


def test_a_failing_answer_is_never_remembered():
    busy = Hop(error=TimeoutError("busy"))
    PF.gate(busy)
    PF.gate(busy)
    assert busy.calls == 2
    loading = Hop(dict(READY, loading=True))
    _refused(PF.gate(loading), "scene.loading", "retryable")
    loading.facts["loading"] = False
    assert PF.gate(loading) is None
    assert loading.calls == 2


def test_a_first_miss_is_retryable_and_a_second_in_a_row_needs_the_artist():
    hop = Hop(error=TimeoutError("busy"))
    first = _refused(PF.gate(hop), "houdini.busy", "retryable")
    assert first["retry_after_s"] == 5.0 and first["next"] == "Wait 5 s, then send it again."
    second = _refused(PF.gate(hop), "houdini.not_answering", "needs_artist")
    assert "open dialog" in second["next"]


def test_an_answer_resets_the_count_of_misses():
    busy, ready = Hop(error=TimeoutError("busy")), Hop()
    _refused(PF.gate(busy), "houdini.busy", "retryable")
    assert PF.gate(ready) is None
    PF.invalidate()
    _refused(PF.gate(busy), "houdini.busy", "retryable")


def test_a_loading_scene_is_retryable():
    _refused(PF.gate(Hop(dict(READY, loading=True))), "scene.loading", "retryable")


def test_undo_off_needs_the_artist_and_names_the_fix():
    data = _refused(PF.gate(Hop(dict(READY, undo_enabled=False))), "scene.undo_off", "needs_artist")
    assert "undoctrl on" in data["next"]


@pytest.mark.parametrize("hop", [
    Hop({"hip_path": "x.hip"}),
    Hop(error=PF.ProbeError("hou.hipFile is unavailable")),
    Hop(error=AttributeError("module 'hou' has no attribute 'undos'")),
], ids=["unreadable-answer", "probe-error", "missing-hom"])
def test_a_check_that_cannot_be_observed_blocks_the_change(hop):
    """UNKNOWN blocks, like FAIL (blueprint rule 5)."""
    _refused(PF.gate(hop), "preflight.blocked", "unrecoverable")


def test_a_version_mismatch_is_refused_before_any_hop_and_names_the_older_side():
    hop = Hop()
    data = _refused(PF.gate(hop, client_version="5.80.0", server_version="5.87.0"),
                    "version.mismatch", "unrecoverable")
    assert "5.80.0" in data["message"] and "5.87.0" in data["message"]
    assert data["next"] == "Restart the MCP client so its bridge loads SYNAPSE 5.87.0, as Houdini does."
    newer = _refused(PF.gate(hop, client_version="5.88.0", server_version="5.87.0"),
                     "version.mismatch", "unrecoverable")
    assert newer["next"] == "Restart Houdini so it loads SYNAPSE 5.88.0, as the bridge does."
    assert hop.calls == 0
    assert PF.gate(hop, client_version="5.87.0", server_version="5.87.0") is None
    assert PF.gate(hop, client_version=None, server_version="5.87.0") is None


# ── The readiness section of synapse_health ─────────────────────────────────────────────

def _checks(report):
    return {check["name"]: check for check in report["checks"]}


def test_readiness_names_every_check_in_order():
    report = PF.readiness(Hop(), server_version="5.87.0",
                          resources=lambda hip: {"hip_dir": hip, "ram_available_bytes": None})
    assert [check["name"] for check in report["checks"]] == [
        "bridge.alive", "session.valid", "houdini.responsive", "scene.writable",
        "version.match", "mode", "resources"]
    assert (report["result"], report["outcome"]) == ("ready", None)
    assert _checks(report)["resources"]["evidence"] == {
        "hip_dir": READY["hip_path"], "ram_available_bytes": None}


@pytest.mark.parametrize("hop, kwargs, result, code", [
    (Hop(error=TimeoutError("busy")), {}, "blocked", "houdini.busy"),
    (Hop(dict(READY, loading=True)), {}, "blocked", "scene.loading"),
    (Hop(dict(READY, undo_enabled=False)), {}, "degraded", "scene.undo_off"),
    (Hop(), {"client_version": "5.80.0"}, "degraded", "version.mismatch"),
    (Hop(), {"read_only": True}, "degraded", None),
], ids=["busy", "loading", "undo-off", "version", "read-only"])
def test_readiness_is_blocked_or_degraded_with_the_failing_check(hop, kwargs, result, code):
    report = PF.readiness(hop, server_version="5.87.0", **kwargs)
    assert report["result"] == result
    assert (report["outcome"] or {}).get("code") == code


def test_readiness_without_houdini_says_so():
    report = PF.readiness(None, server_version="5.87.0")
    checks = _checks(report)
    assert checks["houdini.responsive"]["status"] == PF.NOT_APPLICABLE
    assert checks["scene.writable"]["status"] == PF.NOT_APPLICABLE
    assert checks["version.match"]["status"] == PF.NOT_APPLICABLE
    assert report["result"] == "ready"


def test_resources_measure_the_scene_folder_and_never_guess(tmp_path):
    measured = G.measure_resources(str(tmp_path / "shot.hip"))
    assert measured["hip_dir"] == str(tmp_path)
    assert measured["hip_free_bytes"] > 0
    assert measured["cache_root"] == str(tmp_path / "cache")
    assert measured["cache_free_bytes"] > 0          # measured on the nearest existing folder
    assert measured["ram_available_bytes"] is None or measured["ram_available_bytes"] > 0
    unknown = G.measure_resources(None)
    assert unknown["hip_free_bytes"] is None and unknown["cache_free_bytes"] is None


def test_synapse_health_carries_readiness_beside_its_old_keys(monkeypatch):
    from synapse.server.handlers import SynapseHandler

    _houdini(monkeypatch, Hop())
    monkeypatch.setattr(G, "measure_resources", lambda hip: {"hip_dir": "C:/show/shot"})
    health = SynapseHandler._handle_get_health(None, {"client_version": "0.0.1"})
    assert {"healthy", "houdini_available", "protocol_version", "write_plane"} <= set(health)
    readiness = health["readiness"]
    assert readiness["result"] == "degraded"
    assert readiness["outcome"]["code"] == "version.mismatch"
    assert _checks(readiness)["version.match"]["evidence"] == {
        "bridge": "0.0.1", "houdini": synapse.__version__}


def test_synapse_health_still_passes_the_read_only_fence(monkeypatch):
    """R-5: preflight lives in synapse_health, which read-only mode lets through."""
    monkeypatch.setenv(RO.ENV, "1")
    assert RO.refusal_for_tool("synapse_health") is None
    assert "synapse_preflight" not in _CMD


# ── The real hop ─────────────────────────────────────────────────────────────────────────

class _FakeHou:
    class Error(Exception):
        pass

    hipFile = SimpleNamespace(isLoadingHipFile=lambda: False, path=lambda: "C:/show/a.hip")
    undos = SimpleNamespace(areEnabled=lambda: True)


def test_a_stand_in_hou_is_not_houdini(monkeypatch):
    """The suite's stand-in hou (tests/conftest.py) must never switch the gate on."""
    stand_in = types.ModuleType("hou")
    stand_in.hipFile, stand_in.undos = Mock(), Mock()
    monkeypatch.setitem(sys.modules, "hou", stand_in)
    assert G._houdini() is None and G.houdini_hop() is None
    stand_in.__file__ = "C:/Houdini/houdini/python3.13libs/hou.py"
    assert G._houdini() is stand_in and callable(G.houdini_hop())


def test_the_hop_asks_the_main_thread_without_feeding_the_stall_detector(monkeypatch):
    from synapse.server import main_thread

    monkeypatch.setattr(G, "_houdini", lambda: _FakeHou)
    run = Mock(side_effect=lambda fn, **kwargs: fn())
    monkeypatch.setattr(main_thread, "run_on_main", run)
    hop = G.houdini_hop()
    assert hop(0.25) == {"loading": False, "undo_enabled": True, "hip_path": "C:/show/a.hip"}
    assert run.call_args.kwargs == {"timeout": 0.25, "record_stall": False, "record_wait": False,
                                    "label": "preflight"}
    run.side_effect = main_thread.MainThreadTimeout("busy")
    with pytest.raises(TimeoutError):
        hop(0.25)
    run.side_effect = _FakeHou.Error("no scene")
    with pytest.raises(PF.ProbeError):
        hop(0.25)
    run.side_effect = ImportError("No module named 'hdefereval'")   # hython: read in place
    assert hop(0.25)["hip_path"] == "C:/show/a.hip"


# ── The gate on /mcp ─────────────────────────────────────────────────────────────────────

def _mcp(monkeypatch, resilience=False):
    dispatch = Mock(return_value={"content": [{"type": "text", "text": "{}"}]})
    monkeypatch.setattr(S, "dispatch_tool", dispatch)
    server = S.MCPServer(handler=SimpleNamespace(handle=Mock()))
    server._enable_resilience = resilience
    return server, dispatch, server._sessions.create_session({})


def _rpc(server, session_id, name, number=[0]):
    number[0] += 1
    body = json.dumps({"jsonrpc": "2.0", "id": number[0], "method": "tools/call",
                       "params": {"name": name, "arguments": {}}}).encode()
    reply, _headers = server.handle_request(body, session_id=session_id)
    return json.loads(reply)["result"]


def _meta(result):
    return result["_meta"]["synapse/outcome"]


def test_mcp_checks_a_sessions_first_change_once(monkeypatch):
    hop = _houdini(monkeypatch, Hop())
    server, dispatch, sid = _mcp(monkeypatch)
    assert not _rpc(server, sid, CHANGE).get("isError")
    assert not _rpc(server, sid, CHANGE).get("isError")
    assert hop.calls == 1 and dispatch.call_count == 2
    other = server._sessions.create_session({})
    PF.invalidate()
    assert not _rpc(server, other, CHANGE).get("isError")
    assert hop.calls == 2


def test_mcp_a_refused_change_is_never_sent_and_feeds_no_breaker(monkeypatch):
    hop = _houdini(monkeypatch, Hop(error=TimeoutError("busy")))
    server, dispatch, sid = _mcp(monkeypatch, resilience=True)
    server._rate_limiter = SimpleNamespace(acquire=lambda _key: (True, {}))
    server._circuit_breaker = Mock(can_execute=Mock(return_value=(True, {})))
    for name, code in ((CHANGE, "houdini.busy"), ("houdini_create_node", "houdini.not_answering")):
        result = _rpc(server, sid, name)
        assert result["isError"] is True
        _refused(_meta(result), code, _meta(result)["outcome"])
        assert result["content"][0]["text"].startswith(_meta(result)["outcome"] + ": ")
    assert dispatch.call_count == 0 and hop.calls == 2
    server._circuit_breaker.record_failure.assert_not_called()
    server._circuit_breaker.record_success.assert_not_called()


def test_mcp_reads_and_stop_controls_pass_while_houdini_is_not_ready(monkeypatch):
    hop = _houdini(monkeypatch, Hop(error=TimeoutError("busy")))
    server, dispatch, sid = _mcp(monkeypatch)
    for name in (READ, STOP):
        assert not _rpc(server, sid, name).get("isError"), name
    assert hop.calls == 0 and dispatch.call_count == 2


def test_farm_controls_pass_without_a_hop(monkeypatch):
    """A farm launch never waits on Houdini's main thread (the stall gates exempt it too), so the
    preflight does not hold it back, and reads nothing of the session for it."""
    hop = _houdini(monkeypatch, Hop(error=TimeoutError("busy")))
    server, dispatch, sid = _mcp(monkeypatch)
    assert RO.is_change(FARM)
    assert not _rpc(server, sid, FARM).get("isError")
    assert dispatch.call_count == 1
    assert G.admit(SimpleNamespace(), FARM) is None
    bare = object.__new__(S.MCPServer)
    assert S._preflight_refusal(bare, FARM, None) is None and bare.__dict__ == {}
    assert hop.calls == 0


def test_mcp_a_retryable_outcome_makes_the_next_change_check_again(monkeypatch):
    hop = _houdini(monkeypatch, Hop())
    server, dispatch, sid = _mcp(monkeypatch, resilience=True)
    server._circuit_breaker = None
    allowed = [True]
    server._rate_limiter = SimpleNamespace(acquire=lambda _key: (allowed[0], {"retry_after": 1.0}))
    assert not _rpc(server, sid, CHANGE).get("isError")
    assert hop.calls == 1
    allowed[0] = False
    assert _meta(_rpc(server, sid, CHANGE))["code"] == "server.busy"
    allowed[0] = True
    assert not _rpc(server, sid, CHANGE).get("isError")
    assert hop.calls == 2


def test_mcp_a_call_without_a_session_keeps_the_flag_on_the_server(monkeypatch):
    hop = _houdini(monkeypatch, Hop())
    server, dispatch, _sid = _mcp(monkeypatch)
    for _ in range(2):
        assert not server._handle_tools_call({"name": CHANGE, "arguments": {}}).get("isError")
    assert hop.calls == 1 and dispatch.call_count == 2


def test_the_gate_reads_nothing_without_houdini(monkeypatch):
    """No hop, no gate: a bare server (as other tests build it) is not touched."""
    monkeypatch.setattr(G, "houdini_hop", lambda: None)
    bare = object.__new__(S.MCPServer)
    assert S._preflight_refusal(bare, CHANGE, "mcp-session-x") is None
    assert bare.__dict__ == {}
    _houdini(monkeypatch, Hop(error=TimeoutError("busy")))
    refused = S._preflight_refusal(bare, CHANGE, None)
    assert refused["isError"] is True and _meta(refused)["code"] == "houdini.busy"


def test_the_ready_path_costs_one_hop_and_no_disk_or_ram_reads(monkeypatch):
    """Blueprint rule 9, pinned by structure rather than by a clock."""
    hop = _houdini(monkeypatch, Hop())
    monkeypatch.setattr(G.shutil, "disk_usage", Mock(side_effect=AssertionError("disk read")))
    monkeypatch.setattr(G, "_ram_available", Mock(side_effect=AssertionError("RAM read")))
    holder = SimpleNamespace()
    assert G.admit(holder, CHANGE) is None and holder.preflight_due is False
    assert G.admit(holder, CHANGE) is None
    assert hop.calls == 1


def test_mcp_puts_the_gate_after_the_resilience_gates_and_before_every_dispatch():
    text = Path(S.__file__).read_text(encoding="utf-8")
    gate = text.index("refused = _preflight_refusal(self, tool_name, session_id)")
    assert text.index('if is_transport_fast_path(tool_name) or tool_name == "synapse_farm_cancel":') < gate
    assert text.index("# 3. Circuit breaker") < gate
    assert gate < text.index("if is_farm_control(tool_name):", gate)
    assert gate < text.index("_dispatch_doctor_off_main(handler, tool_name, arguments)", gate)


# ── The gate on the WebSocket routes ────────────────────────────────────────────────────

def _websocket(handler_response=None):
    from synapse.server import websocket as transport

    handler = SimpleNamespace(handle=Mock(return_value=handler_response or SynapseResponse(
        id="r", success=True, data={})))
    server = object.__new__(transport.SynapseServer)
    server._handler, server._session_manager = handler, None
    server._enable_resilience = False
    server._circuit_breaker = None
    server._avg_latency, server._latency_alpha = 0.0, 0.2

    def send(command_type, version=None):
        sent = []
        message = {"type": command_type, "id": "r", "payload": {}}
        if version:
            message["synapse_version"] = version
        server._handle_message(SimpleNamespace(send=lambda value: sent.append(json.loads(value))),
                               json.dumps(message), "local")
        return sent[0]

    return server, handler, send


def test_websocket_a_change_is_refused_before_the_handler(monkeypatch):
    hop = _houdini(monkeypatch, Hop(error=TimeoutError("busy")))
    _server, handler, send = _websocket()
    refused = send(_CMD[CHANGE])
    assert refused["success"] is False
    _refused(refused["data"]["outcome"], "houdini.busy", "retryable")
    assert refused["error"] == refused["data"]["outcome"]["message"]
    assert handler.handle.call_count == 0
    assert send(_CMD[READ])["success"] is True
    assert send(_CMD[STOP])["success"] is True
    assert handler.handle.call_count == 2 and hop.calls == 1


def test_websocket_a_stale_bridge_is_refused_with_the_fix(monkeypatch):
    _houdini(monkeypatch, Hop())
    _server, handler, send = _websocket()
    stale = send(_CMD[CHANGE], version="0.0.1")
    _refused(stale["data"]["outcome"], "version.mismatch", "unrecoverable")
    assert "Restart the MCP client" in stale["data"]["outcome"]["next"]
    assert handler.handle.call_count == 0
    assert send(_CMD[CHANGE], version=synapse.__version__)["success"] is True
    assert handler.handle.call_count == 1


def test_websocket_checks_a_connections_first_change_and_again_after_trouble(monkeypatch):
    hop = _houdini(monkeypatch, Hop())
    server, handler, send = _websocket()
    assert send(_CMD[CHANGE])["success"] and send(_CMD[CHANGE])["success"]
    assert hop.calls == 1
    handler.handle.return_value = SynapseResponse(id="r", success=False, error="busy",
                                                  data={"retry_after": 1.0})
    assert send(_CMD[CHANGE])["data"]["outcome"]["code"] == "server.busy"
    handler.handle.return_value = SynapseResponse(id="r", success=True, data={})
    assert send(_CMD[CHANGE])["success"]
    assert hop.calls == 2


def test_websocket_farm_controls_pass_without_a_hop(monkeypatch):
    from synapse.panel import bridge_adapter as adapter

    monkeypatch.setattr(adapter, "get_bridge", lambda: SimpleNamespace(
        authorize_external_operation=lambda _operation: True))
    hop = _houdini(monkeypatch, Hop(error=TimeoutError("busy")))
    server, handler, send = _websocket()
    assert send(_CMD[FARM])["success"] is True
    assert handler.handle.call_count == 1
    assert hop.calls == 0 and "_preflight_holders" not in server.__dict__


def test_the_hwebserver_websocket_route_runs_the_same_gate():
    """The in-Houdini route cannot run here (it needs hwebserver), so its source is pinned:
    the gate runs after the read-only fence and before the handler is reached."""
    text = (Path(S.__file__).resolve().parents[1] / "server" / "hwebserver_adapter.py").read_text(
        encoding="utf-8")
    fence = text.index("refusal = _read_only_refusal_for_command(command.type)")
    gate = text.index("refused = _preflight_refusal_for(self, command)")
    assert fence < gate < text.index("# Lazy session creation") < text.index(
        "response = handler.handle(command)", gate)
    assert text.index("_preflight_note_for(self, response)") > gate


# ── The stdio bridge carries its version ────────────────────────────────────────────────

def test_a_command_carries_the_bridge_version_only_when_it_has_one():
    stamped = SynapseCommand.from_json(json.dumps({"type": "set_parm", "id": "1",
                                                   "synapse_version": "5.87.0"}))
    assert stamped.client_version == "5.87.0"
    assert json.loads(stamped.to_json())["synapse_version"] == "5.87.0"
    plain = SynapseCommand.from_json(json.dumps({"type": "set_parm", "id": "1"}))
    assert plain.client_version is None and "synapse_version" not in json.loads(plain.to_json())


class _AnsweringSocket:
    def __init__(self, ms):
        self.ms, self.sent = ms, []

    async def send(self, text):
        command = json.loads(text)
        self.sent.append(command)
        self.ms._pending[command["id"]].set_result({"success": True, "data": {"ok": 1}})

    async def close(self):
        pass


def test_the_stdio_bridge_stamps_the_version_it_started_with(monkeypatch):
    pytest.importorskip("mcp")
    pytest.importorskip("websockets")
    import mcp_server as ms

    socket = _AnsweringSocket(ms)

    async def connection():
        return socket

    monkeypatch.setattr(ms, "_get_connection", connection)
    assert ms._SYNAPSE_VERSION == synapse.__version__
    asyncio.run(ms.send_command(_CMD[CHANGE], {"node": "/obj/a"}))
    asyncio.run(ms.send_command("get_health", {}))
    change, health = socket.sent
    assert change["synapse_version"] == health["synapse_version"] == synapse.__version__
    assert change["payload"] == {"node": "/obj/a"}
    assert health["payload"] == {"client_version": synapse.__version__}
