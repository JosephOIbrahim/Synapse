"""SIDEFXCTO-1 / R-011: the hwebserver listens on loopback and authenticates.

Pins, in stock Python (no Houdini):

* the posture rules — local mode resolves to 127.0.0.1, a non-loopback bind is
  an explicit opt-in and is refused with no auth key;
* the settings handed to ``hwebserver.run`` — ``ADDRESS`` and ``ALLOWED_HOSTS``
  are what stop Houdini's own 0.0.0.0 default (the H22 vendor help for
  ``setSettingsForPort`` documents both keys);
* the start path — a refused posture never calls ``run``; the default port is
  still 9999; a studio bind reports its address in health;
* Doctor — a port that accepts on a non-loopback local address is a failure;
* ``/mcp`` — a key file minted by the installer is enforced as Bearer auth
  (the child-process probe is the tests/test_mcp_header_case.py idiom, because
  the URL handler only exists when ``hwebserver`` imports).
"""
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from synapse.server import bind_posture
from synapse.server.bind_posture import (
    BindPostureError,
    enforce_bind_posture,
    hwebserver_settings,
    is_loopback_address,
    resolve_listen_address,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Posture rules
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("address", [
    "127.0.0.1", "127.0.0.5", "127.255.255.254", "::1", "[::1]",
    "localhost", "LOCALHOST", " 127.0.0.1 ",
])
def test_loopback_addresses_are_recognized(address):
    assert is_loopback_address(address) is True


@pytest.mark.parametrize("address", [
    "0.0.0.0", "::", "192.168.1.20", "10.0.0.4", "169.254.1.2",
    "example.com", "", None,
])
def test_non_loopback_addresses_are_not(address):
    assert is_loopback_address(address) is False


def test_local_mode_resolves_to_loopback_by_default():
    assert resolve_listen_address(env={}) == "127.0.0.1"
    assert resolve_listen_address(mode="local", env={}) == "127.0.0.1"


def test_studio_mode_resolves_to_the_any_address():
    assert resolve_listen_address(mode="studio-lan", env={}) == "0.0.0.0"
    assert resolve_listen_address(mode="studio-vpn", env={}) == "0.0.0.0"


def test_local_mode_refuses_a_non_loopback_bind_without_opt_in():
    with pytest.raises(BindPostureError) as excinfo:
        resolve_listen_address(env={"SYNAPSE_BIND_ADDRESS": "0.0.0.0"})
    assert "SYNAPSE_ALLOW_LAN" in str(excinfo.value)


def test_local_mode_allows_a_non_loopback_bind_with_opt_in():
    assert resolve_listen_address(
        env={"SYNAPSE_BIND_ADDRESS": "0.0.0.0", "SYNAPSE_ALLOW_LAN": "1",
             "SYNAPSE_DEPLOY_MODE": "local"}) == "0.0.0.0"


def test_explicit_loopback_bind_always_passes():
    assert resolve_listen_address(
        env={"SYNAPSE_BIND_ADDRESS": "127.0.0.1"}) == "127.0.0.1"


def test_enforce_refuses_non_loopback_without_a_key():
    enforce_bind_posture("127.0.0.1", None)  # loopback needs no key
    with pytest.raises(BindPostureError) as excinfo:
        enforce_bind_posture("0.0.0.0", None)
    message = str(excinfo.value)
    assert "auth.key" in message
    assert "SYNAPSE_API_KEY" in message
    enforce_bind_posture("0.0.0.0", "a-key")  # with a key the bind is allowed


def test_settings_pin_the_loopback_bind_and_hosts():
    settings = hwebserver_settings("127.0.0.1", 9999)
    assert settings["ADDRESS"] == "127.0.0.1"
    assert settings["PORT"] == 9999
    hosts = settings["ALLOWED_HOSTS"]
    assert "127.0.0.1" in hosts and "localhost" in hosts
    assert "127.0.0.1:9999" in hosts and "localhost:9999" in hosts  # literal comparisons too
    assert "*" not in hosts


def test_settings_keep_the_permissive_host_list_for_a_lan_bind():
    settings = hwebserver_settings("0.0.0.0", 9999)
    assert settings["ADDRESS"] == "0.0.0.0"
    assert settings["ALLOWED_HOSTS"] == ["*"]


# ---------------------------------------------------------------------------
# start_hwebserver wiring (fake hwebserver, no Houdini)
# ---------------------------------------------------------------------------

class _FakeHwebserver(ModuleType):
    def __init__(self):
        super().__init__("hwebserver")
        self.run_calls = []
        self.shutdown_requests = 0

    def run(self, **kwargs):
        self.run_calls.append(kwargs)

    def requestShutdown(self):
        self.shutdown_requests += 1


@pytest.fixture
def isolated_home(monkeypatch, tmp_path):
    """No real ~/.synapse/auth.key: HOME/USERPROFILE point at a scratch dir."""
    from synapse.server import auth

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("SYNAPSE_API_KEY", raising=False)
    monkeypatch.delenv("SYNAPSE_BIND_ADDRESS", raising=False)
    monkeypatch.delenv("SYNAPSE_ALLOW_LAN", raising=False)
    monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", "local")
    auth.reset_auth_cache()
    yield tmp_path
    auth.reset_auth_cache()


@pytest.fixture
def transport(monkeypatch, isolated_home):
    """Import the real adapter and neutralize everything start() constructs."""
    from synapse.core import logfile
    from synapse.server import freeze_chain, live_metrics, telemetry_dump
    from synapse.server import hwebserver_adapter as adapter

    fake = _FakeHwebserver()
    # The name only exists when the real module imported inside Houdini.
    monkeypatch.setattr(adapter, "hwebserver", fake, raising=False)
    monkeypatch.setattr(adapter, "HWEBSERVER_AVAILABLE", True)
    monkeypatch.setattr(
        adapter, "SynapseHandler",
        lambda: SimpleNamespace(set_metrics_aggregator=lambda aggregator: None))
    monkeypatch.setattr(adapter, "RateLimiter", lambda: object())
    monkeypatch.setattr(adapter, "BackpressureController", lambda: object())

    class _Breaker:
        def __init__(self, name=""):
            self.name = name
            self.state = SimpleNamespace(value="closed")

    monkeypatch.setattr(adapter, "CircuitBreaker", _Breaker)
    monkeypatch.setattr(
        live_metrics, "MetricsAggregator",
        lambda: SimpleNamespace(start=lambda: None, stop=lambda: None))
    monkeypatch.setattr(freeze_chain, "register_transport_breaker", lambda breaker: None)
    monkeypatch.setattr(freeze_chain, "unregister_transport_breaker", lambda breaker: None)
    monkeypatch.setattr(logfile, "ensure_file_logging", lambda: None)
    monkeypatch.setattr(telemetry_dump, "start_periodic_flush", lambda: None)

    published = []
    monkeypatch.setattr(adapter, "publish_endpoint",
                        lambda host, port, **kwargs: published.append((host, port, kwargs)))
    monkeypatch.setattr(adapter, "clear_endpoint", lambda pid: None)
    for name, value in (("_running", False), ("_port", 0), ("_bound_address", None),
                        ("_handler", None), ("_rate_limiter", None),
                        ("_backpressure", None), ("_metrics_aggregator", None),
                        ("_circuit_breaker", None)):
        monkeypatch.setattr(adapter, name, value)

    return SimpleNamespace(adapter=adapter, fake=fake, published=published)


def test_default_port_is_unchanged():
    from synapse.server.hwebserver_adapter import start_hwebserver

    assert inspect.signature(start_hwebserver).parameters["port"].default == 9999


def test_local_start_asks_houdini_to_bind_loopback(transport):
    transport.adapter.start_hwebserver(port=9999, enable_rate_limiter=False)

    assert len(transport.fake.run_calls) == 1
    call = transport.fake.run_calls[0]
    assert call["port"] == 9999
    settings = call["settings"]
    assert settings["ADDRESS"] == "127.0.0.1"
    assert settings["PORT"] == 9999
    assert "127.0.0.1" in settings["ALLOWED_HOSTS"]
    assert "*" not in settings["ALLOWED_HOSTS"]

    health = transport.adapter.get_health()
    assert health["running"] is True
    assert health["port"] == 9999
    assert health["address"] == "127.0.0.1"
    assert transport.adapter.get_listen_address() == "127.0.0.1"
    assert transport.published[-1][0] == "127.0.0.1"


def test_non_loopback_start_without_key_refuses_before_any_bind(transport):
    with pytest.raises(BindPostureError) as excinfo:
        transport.adapter.start_hwebserver(port=9999, bind_address="0.0.0.0")
    assert "auth.key" in str(excinfo.value)
    assert transport.fake.run_calls == []
    assert transport.adapter.is_running() is False


def test_env_non_loopback_without_opt_in_refuses(transport, monkeypatch):
    monkeypatch.setenv("SYNAPSE_BIND_ADDRESS", "0.0.0.0")
    with pytest.raises(BindPostureError):
        transport.adapter.start_hwebserver(port=9999, enable_rate_limiter=False)
    assert transport.fake.run_calls == []


def test_studio_mode_with_key_binds_the_any_address(transport, monkeypatch):
    from synapse.server import auth

    monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", "studio-lan")
    monkeypatch.setenv("SYNAPSE_API_KEY", "studio-test-key")
    auth.reset_auth_cache()

    transport.adapter.start_hwebserver(port=9999, enable_rate_limiter=False)

    settings = transport.fake.run_calls[0]["settings"]
    assert settings["ADDRESS"] == "0.0.0.0"
    assert settings["ALLOWED_HOSTS"] == ["*"]
    # An any-address cannot be dialled: discovery publishes the local name.
    assert transport.published[-1][0] == "localhost"


def test_local_start_with_a_key_stays_on_loopback(transport, monkeypatch):
    from synapse.server import auth

    monkeypatch.setenv("SYNAPSE_API_KEY", "local-test-key")
    auth.reset_auth_cache()

    transport.adapter.start_hwebserver(port=9999, enable_rate_limiter=False)
    assert transport.fake.run_calls[0]["settings"]["ADDRESS"] == "127.0.0.1"


# ---------------------------------------------------------------------------
# Doctor asserts the bound address
# ---------------------------------------------------------------------------

@pytest.fixture
def no_live_adapter(monkeypatch):
    """Sidecar-only doctor tests: a loaded adapter must not claim it is running."""
    adapter = sys.modules.get("synapse.server.hwebserver_adapter")
    if adapter is not None:
        monkeypatch.setattr(adapter, "_running", False, raising=False)


def test_doctor_fails_when_a_non_loopback_address_accepts(monkeypatch, tmp_path,
                                                          no_live_adapter):
    from synapse.server import doctor

    (tmp_path / "bridge.json").write_text(
        json.dumps({"host": "127.0.0.1", "port": 9999}), encoding="utf-8")
    monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", "local")
    monkeypatch.setattr(doctor, "_local_non_loopback_addresses", lambda: ["192.168.1.20"])
    monkeypatch.setattr(doctor, "_probe_tcp",
                        lambda host, port, timeout=0.25: True)

    check = doctor._check_bind_address(tmp_path)
    assert check["status"] == "fail"
    assert "192.168.1.20" in check["detail"]


def test_doctor_reports_ok_for_a_loopback_only_listener(monkeypatch, tmp_path,
                                                        no_live_adapter):
    from synapse.server import doctor

    (tmp_path / "bridge.json").write_text(
        json.dumps({"host": "127.0.0.1", "port": 9999}), encoding="utf-8")
    monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", "local")
    monkeypatch.setattr(doctor, "_local_non_loopback_addresses", lambda: ["192.168.1.20"])
    monkeypatch.setattr(doctor, "_probe_tcp",
                        lambda host, port, timeout=0.25: host == "127.0.0.1")

    check = doctor._check_bind_address(tmp_path)
    assert check["status"] == "ok"
    assert "127.0.0.1:9999" in check["detail"]


def test_doctor_fails_when_the_adapter_reports_a_non_loopback_bind(monkeypatch, tmp_path):
    from synapse.server import doctor

    fake_adapter = SimpleNamespace(_running=True, _bound_address="0.0.0.0", _port=9999)
    monkeypatch.setitem(sys.modules, "synapse.server.hwebserver_adapter", fake_adapter)
    monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", "local")
    monkeypatch.setattr(doctor, "_local_non_loopback_addresses", lambda: [])
    monkeypatch.setattr(doctor, "_probe_tcp", lambda host, port, timeout=0.25: True)

    check = doctor._check_bind_address(tmp_path)
    assert check["status"] == "fail"
    assert "0.0.0.0" in check["detail"]


def test_doctor_skips_when_no_listener_reports(monkeypatch, tmp_path):
    from synapse.server import doctor

    monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", "local")
    monkeypatch.setattr(doctor, "_local_non_loopback_addresses", lambda: [])
    monkeypatch.setattr(doctor, "_probe_tcp", lambda host, port, timeout=0.25: False)

    check = doctor._check_bind_address(tmp_path)
    assert check["status"] == "skipped"


def test_doctor_ignores_a_stale_sidecar_while_nothing_listens(monkeypatch, tmp_path,
                                                              no_live_adapter):
    from synapse.server import doctor

    (tmp_path / "bridge.json").write_text(
        json.dumps({"host": "0.0.0.0", "port": 9999}), encoding="utf-8")
    monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", "local")
    monkeypatch.setattr(doctor, "_local_non_loopback_addresses", lambda: [])
    monkeypatch.setattr(doctor, "_probe_tcp", lambda host, port, timeout=0.25: False)

    check = doctor._check_bind_address(tmp_path)
    assert check["status"] == "skipped"


# ---------------------------------------------------------------------------
# /mcp uses the installer-minted key file (child process: urlHandler exists
# only when hwebserver imports)
# ---------------------------------------------------------------------------

_MCP_PROBE = r"""
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
init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "t", "version": "0"}}}
nokey = handler(Req({"content-type": "application/json"},
                    json.dumps(init).encode("utf-8")))
print("RESULT " + json.dumps({"status": nokey.status, "body": (nokey.body or "")[:120]}))
"""


def test_mcp_requires_bearer_when_the_installer_minted_a_key(tmp_path):
    key_path = tmp_path / ".synapse" / "auth.key"
    key_path.parent.mkdir(parents=True)
    key_path.write_text("installer-minted-key\n", encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "python"), env.get("PYTHONPATH", "")])
    env["HOME"] = env["USERPROFILE"] = str(tmp_path)
    env.pop("SYNAPSE_API_KEY", None)
    env.pop("SYNAPSE_DEPLOY_MODE", None)
    proc = subprocess.run([sys.executable, "-c", _MCP_PROBE], cwd=str(tmp_path),
                          env=env, capture_output=True, text=True, timeout=180)
    lines = [line for line in proc.stdout.splitlines() if line.startswith("RESULT ")]
    assert lines, proc.stdout[-2000:] + proc.stderr[-2000:]
    result = json.loads(lines[-1][len("RESULT "):])
    assert result["status"] == 401, result
    assert "Unauthorized" in result["body"]
