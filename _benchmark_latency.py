"""
Benchmark Synapse latency — measures round-trip time for each command type.
"""
import json
import time
import uuid
import statistics

from websockets.sync.client import connect

URL = "ws://localhost:9999"
WARMUP = 5
ITERATIONS = 50


def send_command(ws, cmd_type, payload=None):
    cmd_id = uuid.uuid4().hex[:16]
    command = {
        "id": cmd_id,
        "type": cmd_type,
        "payload": payload or {},
        "sequence": 0,
        "timestamp": time.time(),
        "protocol_version": "4.0.0",
    }
    start = time.perf_counter()
    ws.send(json.dumps(command))
    raw = ws.recv(timeout=10)
    elapsed = (time.perf_counter() - start) * 1000  # ms
    response = json.loads(raw)
    return elapsed, response.get("success", False), response.get("error")


def benchmark(ws, name, cmd_type, payload=None, iterations=ITERATIONS):
    # Warmup
    for _ in range(WARMUP):
        send_command(ws, cmd_type, payload)

    # Measure
    times = []
    last_err = None
    for _ in range(iterations):
        elapsed, ok, err = send_command(ws, cmd_type, payload)
        if ok:
            times.append(elapsed)
        else:
            last_err = err
        # No delay — rate limiter bumped for demo (100 per-client bucket)

    if not times:
        print(f"  {name:30s}  FAILED (0/{iterations})  err={last_err}")
        return
    if len(times) < iterations:
        print(f"  {name:30s}  (note: {iterations - len(times)} failures, err={last_err})")

    avg = statistics.mean(times)
    med = statistics.median(times)
    p95 = sorted(times)[int(len(times) * 0.95)]
    mn = min(times)
    mx = max(times)

    print(f"  {name:30s}  avg={avg:6.2f}ms  med={med:6.2f}ms  p95={p95:6.2f}ms  min={mn:5.2f}ms  max={mx:6.2f}ms  ({len(times)}/{iterations})")


def main():
    print(f"\n{'='*80}")
    print(f"  Synapse Latency Benchmark — {URL}")
    print(f"  {ITERATIONS} iterations per command, {WARMUP} warmup")
    print(f"{'='*80}\n")

    ws = connect(URL, open_timeout=5)

    benchmark(ws, "ping", "ping")
    benchmark(ws, "heartbeat", "heartbeat")
    benchmark(ws, "get_health", "get_health")
    benchmark(ws, "get_scene_info", "get_scene_info")
    benchmark(ws, "get_selection", "get_selection")

    # Create a test node for parm benchmarks
    send_command(ws, "execute_python", {"content": "import hou; hou.node('/obj').createNode('null','bench_node'); result='ok'"})

    benchmark(ws, "get_parm", "get_parm", {"node": "/obj/bench_node", "parm": "tx"})
    benchmark(ws, "set_parm", "set_parm", {"node": "/obj/bench_node", "parm": "tx", "value": 1.0})
    benchmark(ws, "execute_python (2+2)", "execute_python", {"content": "result = 2 + 2"})
    benchmark(ws, "execute_python (hou.ver)", "execute_python", {"content": "import hou; result = hou.applicationVersionString()"})
    try:
        benchmark(ws, "create+delete node", "execute_python", {"content": "import hou; n = hou.node('/obj').createNode('null','_tmp'); n.destroy(); result='ok'"})
    except TimeoutError:
        print(f"  {'create+delete node':30s}  TIMEOUT (Houdini main thread stall)")

    # Cleanup
    send_command(ws, "execute_python", {"content": "import hou; hou.node('/obj/bench_node').destroy(); result='ok'"})

    ws.close()

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
