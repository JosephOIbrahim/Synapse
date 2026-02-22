"""
Benchmark Synapse apiFunction (HTTP) latency vs WebSocket.

Compares round-trip time for HTTP POST /api vs ws:// for each command type.
Run after starting both servers in Houdini.
"""

import json
import time
import statistics
import urllib.request
import urllib.error

API_URL = "http://localhost:8008/api"
WARMUP = 5
ITERATIONS = 50


def call_api(function_name, kwargs=None):
    """Call a synapse.* apiFunction via HTTP POST."""
    payload = json.dumps([function_name, [], kwargs or {}]).encode()
    data = urllib.parse.urlencode({"json": payload.decode()}).encode()
    start = time.perf_counter()
    req = urllib.request.Request(API_URL, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
    elapsed = (time.perf_counter() - start) * 1000
    return elapsed, result


def benchmark(name, function_name, kwargs=None, iterations=ITERATIONS):
    """Benchmark a single apiFunction call."""
    # Warmup
    for _ in range(WARMUP):
        try:
            call_api(function_name, kwargs)
        except Exception:
            pass

    # Measure
    times = []
    last_err = None
    for _ in range(iterations):
        try:
            elapsed, result = call_api(function_name, kwargs)
            times.append(elapsed)
        except Exception as e:
            last_err = str(e)

    if not times:
        print(f"  {name:30s}  FAILED (0/{iterations})  err={last_err}")
        return
    if len(times) < iterations:
        print(f"  {name:30s}  (note: {iterations - len(times)} failures)")

    avg = statistics.mean(times)
    med = statistics.median(times)
    p95 = sorted(times)[int(len(times) * 0.95)]
    mn = min(times)
    mx = max(times)

    print(
        f"  {name:30s}  avg={avg:6.2f}ms  med={med:6.2f}ms  "
        f"p95={p95:6.2f}ms  min={mn:5.2f}ms  max={mx:6.2f}ms  "
        f"({len(times)}/{iterations})"
    )


def main():
    print(f"\n{'='*80}")
    print(f"  Synapse apiFunction (HTTP) Benchmark -- {API_URL}")
    print(f"  {ITERATIONS} iterations per command, {WARMUP} warmup")
    print(f"{'='*80}\n")

    # Test connectivity
    try:
        _, result = call_api("synapse.ping")
        print(f"  Connected: protocol={result.get('protocol_version', '?')}\n")
    except Exception as e:
        print(f"  Connection failed: {e}")
        print(f"  Start the API server in Houdini first:")
        print(f"    from synapse.server.api_adapter import start_api_server")
        print(f"    start_api_server(port=8008)")
        return

    benchmark("ping", "synapse.ping")
    benchmark("get_health", "synapse.get_health")
    benchmark("get_scene_info", "synapse.get_scene_info")
    benchmark("get_selection", "synapse.get_selection")

    # Create test node
    try:
        call_api("synapse.create_node", {"parent": "/obj", "type": "null", "name": "api_bench_node"})
    except Exception:
        pass

    benchmark("get_parm", "synapse.get_parm", {"node": "/obj/api_bench_node", "parm": "tx"})
    benchmark("set_parm", "synapse.set_parm", {"node": "/obj/api_bench_node", "parm": "tx", "value": 1.0})
    benchmark("execute_python (2+2)", "synapse.execute_python", {"code": "result = 2 + 2"})
    benchmark("execute_python (hou.ver)", "synapse.execute_python", {"code": "import hou; result = hou.applicationVersionString()"})

    # Cleanup
    try:
        call_api("synapse.delete_node", {"node": "/obj/api_bench_node"})
    except Exception:
        pass

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
