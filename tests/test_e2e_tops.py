"""End-to-end smoke test for the TOPS/PDG pipeline.

Requires a live Houdini session with SYNAPSE running on ws://localhost:9999/synapse.
Marked @pytest.mark.integration so it's excluded from CI.

Test sequence:
1. Create topnet with genericgenerator via execute_python
2. tops_generate_items -> verify status
3. tops_cook_node (blocking) -> verify cooked
4. tops_get_work_items -> verify items returned
5. tops_get_cook_stats -> verify stats
6. tops_get_dependency_graph -> verify structure
7. tops_dirty_node -> verify dirtied
8. Cleanup: delete_node
"""

import asyncio
import json
import os

import pytest

# Skip entire module unless explicitly running integration tests
# (i.e. `pytest -m integration`).  The marker alone doesn't skip.
if not os.environ.get("SYNAPSE_INTEGRATION"):
    pytest.skip(
        "Set SYNAPSE_INTEGRATION=1 to run live integration tests",
        allow_module_level=True,
    )

pytestmark = pytest.mark.integration

# Try to import websockets — skip if not installed
try:
    import websockets
except ImportError:
    pytest.skip("websockets not installed", allow_module_level=True)

# pytest-asyncio strict mode requires this decorator for async fixtures
try:
    from pytest_asyncio import fixture as async_fixture
except ImportError:
    async_fixture = pytest.fixture


SYNAPSE_URL = os.environ.get(
    "SYNAPSE_URL",
    f"ws://localhost:{os.environ.get('SYNAPSE_PORT', '9999')}"
    f"{os.environ.get('SYNAPSE_PATH', '/synapse')}",
)

_call_id = 0


def _next_id():
    global _call_id
    _call_id += 1
    return f"e2e-tops-{_call_id}"


async def send(ws, cmd_type: str, payload: dict) -> dict:
    """Send a command and wait for response."""
    msg = json.dumps({
        "type": cmd_type,
        "id": _next_id(),
        "payload": payload,
        "protocol_version": "4.0.0",
    }, sort_keys=True)
    await ws.send(msg)
    resp_raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
    resp = json.loads(resp_raw)
    assert resp.get("success", False), f"{cmd_type} failed: {resp.get('error')}"
    return resp.get("data", {})


@async_fixture
async def ws():
    """Connect to SYNAPSE WebSocket server."""
    async with websockets.connect(
        SYNAPSE_URL,
        open_timeout=5.0,
        close_timeout=2.0,
    ) as connection:
        # Verify connection
        data = await send(connection, "ping", {})
        assert data.get("pong") is True
        yield connection


class TestE2ETops:
    """Full TOPS pipeline smoke test."""

    @pytest.mark.asyncio
    async def test_tops_pipeline(self, ws):
        # 1. Create a topnet with a genericgenerator via execute_python
        code = """
import hou
topnet = hou.node('/obj').createNode('topnet', 'e2e_topnet')
gen = topnet.createNode('genericgenerator', 'gen1')
gen.parm('itemcount').set(3)
result = topnet.path()
"""
        data = await send(ws, "execute_python", {"content": code})
        topnet_path = "/obj/e2e_topnet"

        try:
            # 2. Generate items
            data = await send(ws, "tops_generate_items", {
                "node": f"{topnet_path}/gen1",
            })
            assert data["status"] == "generated"
            assert data["item_count"] >= 0  # May be 0 before cook

            # 3. Cook node (blocking)
            data = await send(ws, "tops_cook_node", {
                "node": f"{topnet_path}/gen1",
                "blocking": True,
            })
            assert data["status"] == "cooked"

            # 4. Get work items
            data = await send(ws, "tops_get_work_items", {
                "node": f"{topnet_path}/gen1",
            })
            assert data["total_items"] >= 1

            # 5. Get cook stats
            data = await send(ws, "tops_get_cook_stats", {
                "node": f"{topnet_path}/gen1",
            })
            assert data["total_items"] >= 1
            assert "total_cook_time" in data

            # 6. Get dependency graph
            data = await send(ws, "tops_get_dependency_graph", {
                "topnet_path": topnet_path,
            })
            assert data["node_count"] >= 1
            assert len(data["nodes"]) >= 1

            # 7. Dirty node
            data = await send(ws, "tops_dirty_node", {
                "node": f"{topnet_path}/gen1",
            })
            assert data["status"] == "dirtied"

        finally:
            # 8. Cleanup
            await send(ws, "delete_node", {"node": topnet_path})
