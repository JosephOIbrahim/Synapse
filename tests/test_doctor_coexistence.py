"""WS2 multi-client hardening — H5 doctor coexistence + main-thread checks.

_check_mcp_coexistence: resolves our actual bound port (injectable sidecar at
base/bridge.json, else the live resolver), confirms it accepts a connection,
and TCP-probes KNOWN_MCP_PORTS for foreign MCPs (fxhoudinimcp :8100 today).
Info/warn detail only — NEVER status "fail": a foreign MCP is a documented
coexistence hazard (docs/MCP_COEXISTENCE.md), not a broken seat.

_check_main_thread: surfaces stall_state() + dispatch_wait_stats() (H3).
"""

import importlib
import json
import socket

import pytest

from synapse.server import doctor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ephemeral_listener():
    """Bind + listen on an OS-assigned localhost port (connectable)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    return s, s.getsockname()[1]


def _closed_port():
    """An OS-assigned port that is immediately released (not connectable)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _write_sidecar(base, port):
    base.mkdir(parents=True, exist_ok=True)
    (base / "bridge.json").write_text(
        json.dumps({"host": "127.0.0.1", "port": port, "pid": None, "ts": "t"}),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# _check_mcp_coexistence
# ---------------------------------------------------------------------------

class TestMcpCoexistence:
    def test_foreign_port_detected_as_warn(self, tmp_path, monkeypatch):
        listener, port = _ephemeral_listener()
        try:
            monkeypatch.setattr(doctor, "KNOWN_MCP_PORTS", {port: "fxhoudinimcp"})
            base = tmp_path / ".synapse"
            _write_sidecar(base, _closed_port())  # our server: down is fine

            check = doctor._check_mcp_coexistence(base)
            assert check["status"] == "ok"  # never fail — info/warn only
            assert "fxhoudinimcp" in check["detail"]
            assert "MCP_COEXISTENCE" in check["detail"]
            assert check["result"]["foreign_detected"] == [
                f"fxhoudinimcp on :{port}"
            ]
        finally:
            listener.close()

    def test_no_foreign_ports_clean(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            doctor, "KNOWN_MCP_PORTS", {_closed_port(): "fxhoudinimcp"}
        )
        base = tmp_path / ".synapse"
        _write_sidecar(base, _closed_port())

        check = doctor._check_mcp_coexistence(base)
        assert check["status"] == "ok"
        assert check["result"]["foreign_detected"] == []
        assert "no known foreign MCP" in check["detail"]

    def test_own_port_reported_up_and_foreign_port_skipped_when_ours(
            self, tmp_path, monkeypatch):
        """Our own live endpoint reads as accepting; a KNOWN_MCP_PORTS entry
        equal to our own port is us, not a foreign MCP."""
        listener, port = _ephemeral_listener()
        try:
            monkeypatch.setattr(doctor, "KNOWN_MCP_PORTS", {port: "fxhoudinimcp"})
            base = tmp_path / ".synapse"
            _write_sidecar(base, port)  # the sidecar names OUR listener

            check = doctor._check_mcp_coexistence(base)
            assert check["status"] == "ok"
            assert check["result"]["our_endpoint_up"] is True
            assert check["result"]["our_port"] == port
            assert check["result"]["foreign_detected"] == []
        finally:
            listener.close()


# ---------------------------------------------------------------------------
# _check_main_thread
# ---------------------------------------------------------------------------

class TestMainThreadCheck:
    def test_ok_when_not_stalled(self):
        mt = importlib.import_module("synapse.server.main_thread")
        mt._record_success()  # ensure a clean detector
        check = doctor._check_main_thread()
        assert check["status"] == "ok"
        assert check["result"]["stall"]["stalled"] is False
        assert "dispatch_waits" in check["result"]
        assert check["detail"]

    def test_fail_when_stalled_with_attribution(self):
        mt = importlib.import_module("synapse.server.main_thread")
        try:
            mt._record_timeout(10.0)
            mt._record_timeout(10.0)
            check = doctor._check_main_thread()
            assert check["status"] == "fail"
            assert "another MCP client" in check["detail"]
            assert check["result"]["stall"]["consecutive_timeouts"] >= 2
        finally:
            mt._record_success()


# ---------------------------------------------------------------------------
# run_doctor wiring
# ---------------------------------------------------------------------------

def test_run_doctor_includes_new_checks(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNAPSE_ENCRYPTION_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    mt = importlib.import_module("synapse.server.main_thread")
    mt._record_success()

    result = doctor.run_doctor({}, home=tmp_path)
    names = [c["name"] for c in result["checks"]]
    assert "mcp_coexistence" in names
    assert "main_thread" in names
    # Truth contract holds for the new checks too
    for check in result["checks"]:
        if check["name"] in ("mcp_coexistence", "main_thread"):
            assert check["status"] in ("ok", "fail", "skipped")
            assert check["detail"]
