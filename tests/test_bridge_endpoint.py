"""Tests for the discoverable bridge endpoint (self-healing port discovery).

Pure-Python — no hou, no real socket binding. The sidecar is redirected to a
tmp path via $SYNAPSE_BRIDGE_FILE so these never touch the real ~/.synapse.

Contract under test (python/synapse/server/bridge_endpoint.py):
  * publish -> resolve round-trips host/port
  * no sidecar -> (localhost, 9999)
  * $SYNAPSE_PORT honored when no sidecar
  * $SYNAPSE_BRIDGE_FILE override respected
  * atomic write leaves no .tmp behind
  * malformed/empty sidecar -> fallback, never raises
  * clear_endpoint only removes the own-pid entry
  * dead-pid sidecar is treated as stale (resolve falls back)
"""

from __future__ import annotations

import importlib.util
import json
import os

import pytest

# Load bridge_endpoint.py DIRECTLY from its file rather than via
# ``from synapse.server import bridge_endpoint``. The package import would run
# ``synapse.server.__init__``, which eagerly imports ``.websocket`` ->
# ``.handlers`` (both ``import hou``). This module sorts alphabetically AHEAD of
# the handler tests, so it would become the first importer of ``handlers`` with
# no ``hou`` present and strand ``handlers.hou`` for every later handler test —
# and any stub we install instead gets cached and breaks their own fakes. Since
# bridge_endpoint is a deliberately PURE stdlib leaf (no relative imports, no
# hou — so it works in both the Houdini-server and the separate MCP process), we
# exec it standalone: identical code, zero side imports, no pollution.
_BE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "python", "synapse", "server", "bridge_endpoint.py",
)
_spec = importlib.util.spec_from_file_location(
    "synapse_bridge_endpoint_under_test", _BE_PATH
)
be = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(be)


@pytest.fixture
def sidecar(tmp_path, monkeypatch):
    """Redirect the sidecar to a tmp file and clear $SYNAPSE_PORT.

    Yields the sidecar path. Leaves no real ~/.synapse artifacts.
    """
    path = tmp_path / "bridge.json"
    monkeypatch.setenv("SYNAPSE_BRIDGE_FILE", str(path))
    monkeypatch.delenv("SYNAPSE_PORT", raising=False)
    yield path


# ---------------------------------------------------------------------------
# bridge_file() path resolution
# ---------------------------------------------------------------------------

def test_bridge_file_honors_env_override(tmp_path, monkeypatch):
    override = tmp_path / "custom" / "bridge.json"
    monkeypatch.setenv("SYNAPSE_BRIDGE_FILE", str(override))
    assert be.bridge_file() == str(override)


def test_bridge_file_defaults_to_user_home(monkeypatch):
    monkeypatch.delenv("SYNAPSE_BRIDGE_FILE", raising=False)
    expected = os.path.join(os.path.expanduser("~"), ".synapse", "bridge.json")
    assert be.bridge_file() == expected


def test_bridge_file_anchor_is_home_not_cwd(monkeypatch):
    """The path must be home-anchored, not cwd-relative — the MCP process has
    a different cwd than the Houdini server process."""
    monkeypatch.delenv("SYNAPSE_BRIDGE_FILE", raising=False)
    path = be.bridge_file()
    assert os.path.isabs(path)
    assert path.startswith(os.path.expanduser("~"))


# ---------------------------------------------------------------------------
# publish -> resolve round-trip
# ---------------------------------------------------------------------------

def test_publish_resolve_roundtrip(sidecar):
    assert be.publish_endpoint("localhost", 48626, pid=os.getpid()) is True
    host, port = be.resolve_endpoint()
    assert host == "localhost"
    assert port == 48626


def test_publish_writes_expected_json(sidecar):
    be.publish_endpoint("127.0.0.1", 12345, pid=4242, protocol="5.4.0")
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["host"] == "127.0.0.1"
    assert data["port"] == 12345
    assert data["pid"] == 4242
    assert data["protocol"] == "5.4.0"
    assert "ts" in data and data["ts"]


def test_resolve_returns_published_nondefault_port(sidecar):
    """The whole point: after a failover the resolved port is NOT 9999."""
    be.publish_endpoint("localhost", 48626, pid=os.getpid())
    _, port = be.resolve_endpoint()
    assert port != be.DEFAULT_PORT
    assert port == 48626


# ---------------------------------------------------------------------------
# Backward-compat: no sidecar => exactly today's behavior
# ---------------------------------------------------------------------------

def test_resolve_no_sidecar_returns_default(sidecar):
    # sidecar fixture points at a nonexistent file and clears $SYNAPSE_PORT
    assert not sidecar.exists()
    host, port = be.resolve_endpoint()
    assert host == "localhost"
    assert port == 9999


def test_resolve_honors_synapse_port_when_no_sidecar(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_BRIDGE_FILE", str(tmp_path / "absent.json"))
    monkeypatch.setenv("SYNAPSE_PORT", "55001")
    host, port = be.resolve_endpoint()
    assert host == "localhost"
    assert port == 55001


def test_resolve_explicit_default_port_overrides_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_BRIDGE_FILE", str(tmp_path / "absent.json"))
    monkeypatch.setenv("SYNAPSE_PORT", "55001")
    _, port = be.resolve_endpoint(default_port=7777)
    assert port == 7777


def test_resolve_malformed_synapse_port_falls_back_to_9999(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_BRIDGE_FILE", str(tmp_path / "absent.json"))
    monkeypatch.setenv("SYNAPSE_PORT", "not-a-number")
    _, port = be.resolve_endpoint()
    assert port == 9999


# ---------------------------------------------------------------------------
# Atomic write: no .tmp left behind
# ---------------------------------------------------------------------------

def test_atomic_write_leaves_no_tmp(sidecar, tmp_path):
    be.publish_endpoint("localhost", 9999, pid=os.getpid())
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []
    assert sidecar.exists()


def test_publish_overwrite_is_atomic(sidecar, tmp_path):
    be.publish_endpoint("localhost", 1111, pid=os.getpid())
    be.publish_endpoint("localhost", 2222, pid=os.getpid())
    _, port = be.resolve_endpoint()
    assert port == 2222
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


# ---------------------------------------------------------------------------
# Malformed / empty sidecar -> fallback, never raises
# ---------------------------------------------------------------------------

def test_resolve_malformed_sidecar_falls_back(sidecar):
    sidecar.write_text("{ this is not valid json", encoding="utf-8")
    host, port = be.resolve_endpoint()
    assert (host, port) == ("localhost", 9999)


def test_resolve_empty_sidecar_falls_back(sidecar):
    sidecar.write_text("", encoding="utf-8")
    host, port = be.resolve_endpoint()
    assert (host, port) == ("localhost", 9999)


def test_resolve_sidecar_missing_keys_falls_back(sidecar):
    sidecar.write_text(json.dumps({"protocol": "4.0.0"}), encoding="utf-8")
    host, port = be.resolve_endpoint()
    assert (host, port) == ("localhost", 9999)


def test_resolve_sidecar_non_dict_falls_back(sidecar):
    sidecar.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    host, port = be.resolve_endpoint()
    assert (host, port) == ("localhost", 9999)


def test_resolve_sidecar_non_int_port_falls_back(sidecar):
    sidecar.write_text(
        json.dumps({"host": "localhost", "port": "abc"}), encoding="utf-8"
    )
    host, port = be.resolve_endpoint()
    assert (host, port) == ("localhost", 9999)


def test_publish_never_raises_on_bad_dir(tmp_path, monkeypatch):
    # Parent path is an existing FILE, so makedirs + write under it must fail.
    # publish must return False, not raise.
    blocker = tmp_path / "iam_a_file"
    blocker.write_text("not a directory", encoding="utf-8")
    bad = blocker / "bridge.json"  # treats a file as a directory
    monkeypatch.setenv("SYNAPSE_BRIDGE_FILE", str(bad))
    assert be.publish_endpoint("localhost", 9999, pid=os.getpid()) is False


# ---------------------------------------------------------------------------
# clear_endpoint: own-pid only
# ---------------------------------------------------------------------------

def test_clear_endpoint_removes_own_pid(sidecar):
    be.publish_endpoint("localhost", 9999, pid=os.getpid())
    assert sidecar.exists()
    assert be.clear_endpoint(os.getpid()) is True
    assert not sidecar.exists()


def test_clear_endpoint_keeps_other_pid(sidecar):
    other_pid = 999999  # not us
    be.publish_endpoint("localhost", 9999, pid=other_pid)
    assert be.clear_endpoint(os.getpid()) is False
    assert sidecar.exists()  # someone else's entry — left intact


def test_clear_endpoint_none_pid_removes_unconditionally(sidecar):
    be.publish_endpoint("localhost", 9999, pid=12345)
    assert be.clear_endpoint(None) is True
    assert not sidecar.exists()


def test_clear_endpoint_no_sidecar_returns_false(sidecar):
    assert not sidecar.exists()
    assert be.clear_endpoint(os.getpid()) is False


def test_clear_endpoint_pidless_entry_not_clobbered(sidecar):
    # A sidecar with no recorded pid is NOT removed by a pid-scoped clear —
    # we can't prove ownership, so we don't clobber it.
    sidecar.write_text(
        json.dumps({"host": "localhost", "port": 9999}), encoding="utf-8"
    )
    assert be.clear_endpoint(os.getpid()) is False
    assert sidecar.exists()


# ---------------------------------------------------------------------------
# Dead-pid sidecar is stale
# ---------------------------------------------------------------------------

def test_resolve_dead_pid_is_stale(sidecar):
    # PID 999999 is (almost certainly) not running -> treat sidecar as stale.
    be.publish_endpoint("localhost", 48626, pid=999999)
    host, port = be.resolve_endpoint()
    assert (host, port) == ("localhost", 9999)


def test_resolve_live_pid_is_honored(sidecar):
    be.publish_endpoint("localhost", 48626, pid=os.getpid())
    host, port = be.resolve_endpoint()
    assert (host, port) == ("localhost", 48626)


def test_resolve_no_pid_entry_is_honored(sidecar):
    # No pid recorded -> we can't disprove liveness -> honor the entry.
    sidecar.write_text(
        json.dumps({"host": "localhost", "port": 48626, "pid": None}),
        encoding="utf-8",
    )
    host, port = be.resolve_endpoint()
    assert (host, port) == ("localhost", 48626)


def test_resolve_negative_pid_is_stale(sidecar):
    sidecar.write_text(
        json.dumps({"host": "localhost", "port": 48626, "pid": -1}),
        encoding="utf-8",
    )
    host, port = be.resolve_endpoint()
    assert (host, port) == ("localhost", 9999)
