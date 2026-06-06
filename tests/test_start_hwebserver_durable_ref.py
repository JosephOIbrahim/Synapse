"""Regression test: the websocket-fallback start path retains a durable
reference to the SynapseServer so Python's garbage collector can never reap
the live server out from under its serve_forever() daemon thread.

Root cause (panel-gc): ``synapse.server.start_hwebserver.main()`` built the
fallback ``SynapseServer`` as a bare local. ``SynapseServer.start()`` spins a
``daemon=True`` thread blocked in ``serve_forever()``; the only owner of the
server object was that local, so once ``main()`` returned GC was free to reap
the server and the :9999 bridge died silently (hand-worked-around with
``builtins._synapse_manual_srv = srv``). The fix pins the server on a
module-global hard reference. These tests pin the contract WITHOUT a live
Houdini, a real socket, or a real websocket server.
"""

from __future__ import annotations

import gc
import importlib
import sys
import types

import pytest


def _fake_adapter():
    """A drop-in ``synapse.server.hwebserver_adapter`` whose
    ``start_hwebserver`` is a harmless no-op.

    Pre-installing this in ``sys.modules`` lets us import the
    ``start_hwebserver`` module (which auto-runs ``main()`` at import time)
    along the hwebserver branch — so the import itself never binds a real
    socket or constructs a real websocket server.
    """
    mod = types.ModuleType("synapse.server.hwebserver_adapter")
    mod.start_hwebserver = lambda *a, **k: None  # type: ignore[attr-defined]
    mod.HWEBSERVER_AVAILABLE = True  # type: ignore[attr-defined]
    return mod


@pytest.fixture
def fresh_module(monkeypatch):
    """Import ``synapse.server.start_hwebserver`` fresh with a stubbed
    hwebserver adapter so import-time ``main()`` is a no-op.

    Restores ``sys.modules`` afterwards so the durable module-global we set
    during the test cannot leak its server into later tests.
    """
    monkeypatch.setitem(
        sys.modules, "synapse.server.hwebserver_adapter", _fake_adapter()
    )
    # Drop any previously-imported copy so the import (and its auto-start)
    # re-runs under our stub.
    monkeypatch.delitem(
        sys.modules, "synapse.server.start_hwebserver", raising=False
    )
    mod = importlib.import_module("synapse.server.start_hwebserver")
    # Import-time main() went down the (stubbed) hwebserver branch, so the
    # fallback reference must still be empty.
    assert mod.get_running_server() is None
    return mod


class _FakeServer:
    """Stand-in for SynapseServer: records that start() was called and is
    weakly trackable so we can prove GC does NOT reap it once retained."""

    instances = 0

    def __init__(self, *args, **kwargs):
        type(self).instances += 1
        self.started = False
        self.init_kwargs = kwargs

    def start(self):
        self.started = True


def _install_fallback_websocket(monkeypatch, server_cls):
    """Force ``main()`` down the websocket-fallback branch by making the
    adapter's ``start_hwebserver`` raise ImportError, and inject a fake
    ``synapse.server.websocket`` module exposing ``server_cls``."""
    bad_adapter = types.ModuleType("synapse.server.hwebserver_adapter")

    def _boom(*a, **k):
        raise ImportError("hwebserver not available — must run inside Houdini")

    bad_adapter.start_hwebserver = _boom  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules, "synapse.server.hwebserver_adapter", bad_adapter
    )

    fake_ws = types.ModuleType("synapse.server.websocket")
    fake_ws.SynapseServer = server_cls  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "synapse.server.websocket", fake_ws)


def test_fallback_server_retained_in_module_global(fresh_module, monkeypatch):
    """After ``main()`` takes the websocket fallback, the server it started
    is held by a module-global hard reference (durable across GC)."""
    _FakeServer.instances = 0
    _install_fallback_websocket(monkeypatch, _FakeServer)

    fresh_module.main()

    server = fresh_module.get_running_server()
    assert server is not None, (
        "fallback websocket server was not retained — GC bug regressed"
    )
    assert isinstance(server, _FakeServer)
    assert server.started is True, "retained server must have been start()ed"
    # The module-global IS the durable reference.
    assert fresh_module._fallback_server is server


def test_retained_server_survives_gc(fresh_module, monkeypatch):
    """A full gc.collect() must NOT reap the retained server — the whole
    point of the fix. We track it by identity through the module global."""
    _FakeServer.instances = 0
    _install_fallback_websocket(monkeypatch, _FakeServer)

    fresh_module.main()
    retained_id = id(fresh_module.get_running_server())

    # Drop every other local handle, then hammer the collector.
    for _ in range(3):
        gc.collect()

    survivor = fresh_module.get_running_server()
    assert survivor is not None
    assert id(survivor) == retained_id, (
        "retained server was reaped / replaced after gc.collect() — "
        "the module-global hard reference did not hold"
    )


def test_get_running_server_accessor_exists(fresh_module):
    """The host/panel layer recovers the server via this accessor instead of
    scanning gc.get_objects() for a zombie. Pin the public surface."""
    assert hasattr(fresh_module, "get_running_server")
    assert callable(fresh_module.get_running_server)
