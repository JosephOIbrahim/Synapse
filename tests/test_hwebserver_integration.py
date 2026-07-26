"""
Synapse hwebserver Integration Test

This test must be run INSIDE Houdini (hython or graphical session).
It verifies the full hwebserver -> handler -> hou.* path.

Usage:
    # From Houdini Python Shell:
    import runpy; runpy.run_path("tests/test_hwebserver_integration.py")

    # From hython:
    hython tests/test_hwebserver_integration.py
"""

import asyncio
import json
import sys
import time

import pytest

try:
    import hwebserver
    _HAS_HWEBSERVER = True
except ImportError:
    _HAS_HWEBSERVER = False

pytestmark = pytest.mark.skipif(
    not _HAS_HWEBSERVER,
    reason="hwebserver not available (requires Houdini)"
)


def test_hwebserver_available():
    """Verify hwebserver module is importable."""
    try:
        import hwebserver
        print("PASS: hwebserver available")
        return True
    except ImportError:
        print("SKIP: hwebserver not available (not running inside Houdini)")
        return False


def test_adapter_import():
    """Verify adapter module loads without error."""
    try:
        from synapse.server.hwebserver_adapter import (
            start_hwebserver,
            stop_hwebserver,
            is_running,
            get_health,
            HWEBSERVER_AVAILABLE,
        )
        assert HWEBSERVER_AVAILABLE, "HWEBSERVER_AVAILABLE should be True inside Houdini"
        print("PASS: adapter module imported successfully")
        return True
    except Exception as e:
        print(f"FAIL: adapter import error: {e}")
        return False


def test_server_lifecycle():
    """Test start/stop/health cycle."""
    from synapse.server.hwebserver_adapter import (
        start_hwebserver,
        stop_hwebserver,
        is_running,
        get_health,
    )

    # Start
    start_hwebserver(port=9876)
    assert is_running(), "Server should be running after start"

    # Health
    health = get_health()
    assert health["backend"] == "hwebserver"
    assert health["running"] is True
    print(f"PASS: server started, health: {health}")

    # Stop
    stop_hwebserver()
    assert not is_running(), "Server should be stopped after stop"
    print("PASS: server stopped cleanly")
    return True


def test_websocket_roundtrip():
    """Test full WebSocket roundtrip: connect -> send command -> receive response."""
    import websockets

    from synapse.server.hwebserver_adapter import (
        start_hwebserver,
        stop_hwebserver,
    )

    PORT = 9877
    start_hwebserver(port=PORT)
    time.sleep(0.5)  # Let server bind

    async def _test():
        uri = f"ws://localhost:{PORT}/synapse"
        async with websockets.connect(uri) as ws:
            # Send ping command
            command = json.dumps({
                "type": "ping",
                "id": "test_ping_001",
                "payload": {},
                "sequence": 1,
                "timestamp": time.time(),
                "protocol_version": "4.0.0",
            })
            await ws.send(command)
            response = json.loads(await ws.recv())

            assert response["id"] == "test_ping_001", f"ID mismatch: {response['id']}"
            assert response["success"] is True, f"Ping failed: {response}"
            assert response["data"]["pong"] is True
            print(f"PASS: WebSocket roundtrip — ping response: {response['data']}")

            # Send get_scene_info (requires hou.*)
            command = json.dumps({
                "type": "get_scene_info",
                "id": "test_scene_001",
                "payload": {},
                "sequence": 2,
                "timestamp": time.time(),
                "protocol_version": "4.0.0",
            })
            await ws.send(command)
            response = json.loads(await ws.recv())

            assert response["success"] is True, f"get_scene_info failed: {response}"
            assert "hip_file" in response["data"]
            print(f"PASS: get_scene_info via hwebserver — HIP: {response['data']['hip_file']}")

    asyncio.run(_test())
    stop_hwebserver()
    return True


def run_all():
    """Run all integration tests."""
    print("=" * 60)
    print("Synapse hwebserver Integration Tests")
    print("=" * 60)

    if not test_hwebserver_available():
        print("\nSKIPPED: Run inside Houdini (hython or graphical)")
        return

    results = []
    for test_fn in [test_adapter_import, test_server_lifecycle, test_websocket_roundtrip]:
        try:
            results.append(test_fn())
        except Exception as e:
            print(f"FAIL: {test_fn.__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} passed")
    if passed == total:
        print("ALL INTEGRATION TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 60)


if __name__ == "__main__":
    run_all()
