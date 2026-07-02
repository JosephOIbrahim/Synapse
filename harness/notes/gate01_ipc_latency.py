"""Gate-0.1 IPC latency spike — the sidecar's transport cost, measured.

The sidecar arm of gate-0.1 (harness/notes/gate-0.1-sidecar-vs-abi3.md) moves
the brain (agent_loop — zero hou imports) into its own pinned-cp311 process,
talking to the Houdini host over localhost WebSocket (the bridge_endpoint /
mcp_server transport). The unmeasured number the decision needs is the IPC
round-trip cost that path adds per brain call. Houdini is NOT in that loop, so
this spike measures the real thing without it: cross-process localhost WS echo
round-trips (same ``websockets`` library the transport uses), at payload sizes
bracketing real traffic (a tool call ~256 B; a tool result ~4 KB; a fat
observation/scene summary ~64 KB), JSON-wrapped like the live envelope.

Usage:
    python harness/notes/gate01_ipc_latency.py            # run the spike
    python harness/notes/gate01_ipc_latency.py --serve N  # (internal) server on port N

Prints one JSON report; append the summary to gate-0.1-sidecar-vs-abi3.md.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import subprocess
import sys
import time

PORT = 19_777
ROUNDS = 200
WARMUP = 10
PAYLOAD_SIZES = (256, 4_096, 65_536)


async def _serve(port: int) -> None:
    import websockets

    async def echo(ws):
        async for msg in ws:
            await ws.send(msg)

    async with websockets.serve(echo, "127.0.0.1", port, max_size=None):
        print("READY", flush=True)
        await asyncio.Future()  # run until killed


async def _measure(port: int) -> dict:
    import websockets

    results: dict = {}
    async with websockets.connect(
        f"ws://127.0.0.1:{port}", max_size=None
    ) as ws:
        for size in PAYLOAD_SIZES:
            envelope = json.dumps(
                {"id": 1, "type": "brain_answers", "payload": "x" * size}
            )
            for _ in range(WARMUP):
                await ws.send(envelope)
                await ws.recv()
            times = []
            for _ in range(ROUNDS):
                t0 = time.perf_counter()
                await ws.send(envelope)
                reply = await ws.recv()
                json.loads(reply)  # include deserialize, like the live path
                times.append((time.perf_counter() - t0) * 1000.0)
            times.sort()
            results[f"{size}B"] = {
                "p50_ms": round(statistics.median(times), 3),
                "p95_ms": round(times[int(len(times) * 0.95) - 1], 3),
                "p99_ms": round(times[int(len(times) * 0.99) - 1], 3),
                "max_ms": round(times[-1], 3),
            }
    return results


def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == "--serve":
        asyncio.run(_serve(int(sys.argv[2])))
        return 0

    server = subprocess.Popen(
        [sys.executable, __file__, "--serve", str(PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert server.stdout is not None
        line = server.stdout.readline().strip()
        if line != "READY":
            print(json.dumps({"error": f"server failed to start: {line!r}"}))
            return 1
        results = asyncio.run(_measure(PORT))
        print(
            json.dumps(
                {
                    "spike": "gate01_ipc_latency",
                    "transport": "cross-process localhost WebSocket (websockets lib)",
                    "python": sys.version.split()[0],
                    "rounds_per_size": ROUNDS,
                    "results": results,
                },
                indent=2,
            )
        )
        return 0
    finally:
        server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
