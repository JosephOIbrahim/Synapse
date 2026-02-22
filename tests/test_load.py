"""Load test for Synapse WebSocket server.

Standalone: python tests/test_load.py --connections 10 --requests-per-conn 50
Pytest:     SYNAPSE_LOAD_TEST=1 python -m pytest tests/test_load.py -v
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import statistics
import time
import uuid
from dataclasses import dataclass, field

import websockets

PROTOCOL_VERSION = "4.0.0"

WORKLOADS = [
    ("ping", {}, 0.70),
    ("get_scene_info", {}, 0.20),
    ("get_selection", {}, 0.10),
]


def _make_command(cmd_type: str, payload: dict, seq: int) -> str:
    return json.dumps({
        "type": cmd_type,
        "id": str(uuid.uuid4()),
        "payload": payload,
        "sequence": seq,
        "timestamp": time.time(),
        "protocol_version": PROTOCOL_VERSION,
    })


def _pick_workload() -> tuple[str, dict]:
    r = random.random()
    cumulative = 0.0
    for name, payload, weight in WORKLOADS:
        cumulative += weight
        if r <= cumulative:
            return name, payload
    return WORKLOADS[0][0], WORKLOADS[0][1]


@dataclass
class Stats:
    latencies: list[float] = field(default_factory=list)
    errors: int = 0
    conn_failures: int = 0


async def _worker(url: str, requests: int, stats: Stats) -> None:
    try:
        async with websockets.connect(url, open_timeout=10) as ws:
            for seq in range(requests):
                cmd_type, payload = _pick_workload()
                msg = _make_command(cmd_type, payload, seq)
                t0 = time.perf_counter()
                try:
                    await ws.send(msg)
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    elapsed = time.perf_counter() - t0
                    resp = json.loads(raw)
                    sent_id = json.loads(msg)["id"]
                    if resp.get("id") != sent_id or not resp.get("success", False):
                        stats.errors += 1
                    else:
                        stats.latencies.append(elapsed * 1000)
                except Exception:
                    stats.errors += 1
    except Exception:
        stats.conn_failures += 1


async def run_load_test(url: str, connections: int, requests_per_conn: int) -> Stats:
    stats = Stats()
    t0 = time.perf_counter()
    tasks = [_worker(url, requests_per_conn, stats) for _ in range(connections)]
    await asyncio.gather(*tasks)
    wall = time.perf_counter() - t0

    total = connections * requests_per_conn
    ok = len(stats.latencies)
    rps = ok / wall if wall > 0 else 0

    def pct(p: float) -> float:
        if not stats.latencies:
            return 0.0
        s = sorted(stats.latencies)
        idx = int(len(s) * p / 100)
        return s[min(idx, len(s) - 1)]

    print("\n" + "=" * 52)
    print(f" Synapse Load Test Results")
    print("=" * 52)
    print(f" {'URL':<25} {url}")
    print(f" {'Connections':<25} {connections}")
    print(f" {'Requests/conn':<25} {requests_per_conn}")
    print(f" {'Total requests':<25} {total}")
    print(f" {'Successful':<25} {ok}")
    print(f" {'Errors':<25} {stats.errors}")
    print(f" {'Connection failures':<25} {stats.conn_failures}")
    print("-" * 52)
    print(f" {'Wall time':<25} {wall:.2f}s")
    print(f" {'Requests/sec':<25} {rps:.1f}")
    print(f" {'p50 latency':<25} {pct(50):.2f}ms")
    print(f" {'p95 latency':<25} {pct(95):.2f}ms")
    print(f" {'p99 latency':<25} {pct(99):.2f}ms")
    if stats.latencies:
        print(f" {'mean latency':<25} {statistics.mean(stats.latencies):.2f}ms")
        print(f" {'stdev latency':<25} {statistics.stdev(stats.latencies) if len(stats.latencies) > 1 else 0:.2f}ms")
    print("=" * 52)
    return stats


# -- pytest entry point (skipped unless SYNAPSE_LOAD_TEST=1) --

try:
    import pytest

    @pytest.mark.skipif(
        os.environ.get("SYNAPSE_LOAD_TEST") != "1",
        reason="Set SYNAPSE_LOAD_TEST=1 to run load tests against a live server",
    )
    @pytest.mark.asyncio
    async def test_load_basic():
        stats = await run_load_test("ws://localhost:9999", connections=5, requests_per_conn=20)
        assert stats.conn_failures == 0, f"{stats.conn_failures} connection failures"
        assert stats.errors < 10, f"{stats.errors} errors (threshold: 10)"
except ImportError:
    pass


# -- CLI entry point --

def main() -> None:
    parser = argparse.ArgumentParser(description="Synapse WebSocket load test")
    parser.add_argument("--connections", type=int, default=10)
    parser.add_argument("--requests-per-conn", type=int, default=50)
    parser.add_argument("--url", default="ws://localhost:9999")
    args = parser.parse_args()
    asyncio.run(run_load_test(args.url, args.connections, args.requests_per_conn))


if __name__ == "__main__":
    main()
