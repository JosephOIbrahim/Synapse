"""
Benchmark Synapse apiFunction (HTTP) latency vs WebSocket.

Compares round-trip time for HTTP POST /api vs ws:// for each command type.
Run after starting both servers in Houdini.

EXTENDED (R305 lane I1, 2026-08-02) with the SAME scale CLI surface as
_benchmark_latency.py, so both transports carry an identical scale axis and
the D1 op-set alignment survives. A no-argument run issues byte-for-byte the
same op sequence it always did (pinned by tests/test_bench_scale.py).

The offline tier here is the same shared core (scripts/bench_scale.py) — it is
transport-independent by construction, so there is exactly one implementation
and no chance of the two scripts measuring different things. The LIVE HTTP arm
is NOT implemented here: see the module note at run_scale() for why that is a
stated gap rather than a silent one.
"""

import argparse
import importlib.util
import json
import sys
import time
import statistics
import urllib.error
import urllib.parse   # NOT redundant: call_api uses urllib.parse.urlencode
                      # and only ever worked because importing urllib.request
                      # binds `parse` on the package as a side effect.
import urllib.request
from pathlib import Path

API_URL = "http://localhost:8008/api"
WARMUP = 5
ITERATIONS = 50

REPO = Path(__file__).resolve().parent


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


def legacy_main():
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


# ── SCALE EXTENSION (shared core — see _benchmark_latency.py) ───────────────

def _load_bench_scale():
    """Import the shared scale core by path (scripts/ is not a package)."""
    mod = sys.modules.get("bench_scale")
    if mod is not None:
        return mod
    path = REPO / "scripts" / "bench_scale.py"
    spec = importlib.util.spec_from_file_location("bench_scale", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bench_scale"] = mod
    spec.loader.exec_module(mod)
    return mod


def build_parser():
    ap = argparse.ArgumentParser(
        prog="_benchmark_api.py",
        description="SYNAPSE HTTP apiFunction benchmark. With no arguments it "
                    "runs the legacy op sequence unchanged. --tier offline "
                    "runs the shared scale bench with no Houdini, no server "
                    "and no pxr (counts only, never wall-clock).",
        epilog="scale axis = AUTHORED ARRAY VOLUME, not prim count "
               "(harness/latency/LEDGER.md section 1). "
               "Core: scripts/bench_scale.py")
    ap.add_argument("--iterations", type=int, default=ITERATIONS)
    try:
        _load_bench_scale().add_scale_args(ap)
    except Exception as exc:                       # noqa: BLE001
        # --help must never exit non-zero for want of the core.
        g = ap.add_argument_group("scale bench (CORE UNAVAILABLE)")
        g.add_argument("--tier", choices=("offline", "live"), default=None)
        g.add_argument("--axis", default="both")
        g.add_argument("--scale", default=None, metavar="N,N,N")
        g.add_argument("--volume", default=None, metavar="N,N,N")
        g.add_argument("--prim-threshold", type=int, default=10_000)
        g.add_argument("--volume-threshold", type=int, default=500_000)
        g.add_argument("--json-out", default=None)
        g.description = (f"scripts/bench_scale.py did not import "
                         f"({type(exc).__name__}: {exc}) — --tier is inert")
    return ap


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        legacy_main()
        return 0
    args = build_parser().parse_args(argv)
    if args.tier is None:
        legacy_main()
        return 0
    if args.tier == "offline":
        # The offline tier is TRANSPORT-INDEPENDENT: it drives
        # LosslessExecutionBridge.execute() against a counting fake, with no
        # socket of any kind. Both scripts therefore share one implementation
        # and cannot measure different things.
        bench = _load_bench_scale()
        try:
            return bench.run_from_args(
                args, "python _benchmark_api.py " + " ".join(argv))
        except bench.BenchScaleError as exc:
            print(f"\n  REFUSED: {exc}\n", file=sys.stderr)
            return 1
    # STATED GAP, not a silent one: there is no LIVE HTTP scale arm. The live
    # scale arm lives in _benchmark_latency.py (WS). Building a second live
    # arm here would duplicate the rung builder, and a duplicated builder is
    # how two transports start describing two different scenes.
    print("\n  --tier live is not implemented for the HTTP arm.")
    print("  Use: python _benchmark_latency.py --tier live   (WS transport)")
    print("  Reason: one rung builder, one scene. A second live builder here "
          "would fork it.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
