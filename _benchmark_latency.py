"""
Benchmark Synapse latency — measures round-trip time for each command type.

EXTENDED (R305 lane I1, 2026-08-02) with a SCALE AXIS. docs/BENCHMARK_DESIGN.md
freezes "extend, never rebuild" (:140), so everything below the legacy section
is additive: a no-argument run issues byte-for-byte the same op sequence it
always did (pinned by tests/test_bench_scale.py::TestLegacySequenceUnchanged).

TWO TIERS, and what each may emit:

  --tier offline   No Houdini, no bridge, no socket, no pxr. Emits COUNTS and
                   derived slopes ONLY, never a wall-clock key. This is the
                   tier that can gate CI. Implemented in scripts/bench_scale.py;
                   the honesty rules are enforced there in code
                   (bench_scale.assert_record_honest), not in prose here.

  --tier live      Real bridge over ws://localhost:9999. MAY emit wall-clock,
                   and every number is stamped with the Houdini build it was
                   measured on (read live from hou.applicationVersionString(),
                   never assumed). This host runs 22.0.397; CLAUDE.md's stated
                   target is 22.0.368 and harness/state/drop.json does not
                   exist in this tree — the drift is printed, not hidden.

  (default, no --tier)  the legacy transport run, unchanged.

THE AXIS IS AUTHORED ARRAY VOLUME, NOT PRIM COUNT. See scripts/bench_scale.py's
module docstring and harness/latency/LEDGER.md section 1 (producer: C2 crucible)
for why: a 4-prim PointInstancer at 2,000,000 instances costs 2,017.9 ms/op
while a prim-count gate answers False.

WHY THE LEGACY RUN IS BLIND TO ALL OF THIS (do not "fix" it here): the legacy
sequence benchmarks set_parm on an /obj null. `_infer_stage_touch`
(shared/bridge.py) only sets stage_path when a hou.LopNode appears within depth
3 downstream, so hash_target stays /obj and the stage block never runs. The
scale arm reaches the stage term by pointing at a LOP, not by changing that.
"""
import argparse
import hashlib
import importlib.util
import json
import statistics
import sys
import time
import uuid
from pathlib import Path

URL = "ws://localhost:9999"
WARMUP = 5
ITERATIONS = 50

REPO = Path(__file__).resolve().parent


def _connect(url=URL, open_timeout=5):
    """Open the WS connection.

    The websockets import is LAZY on purpose: `--help` and the entire offline
    tier must run where websockets is absent (hython, a pxr-less CI leg). A
    module-top import made `--help` exit non-zero there, which is exactly what
    harness/latency/verify.py::p5_offline_bench gates on.
    """
    from websockets.sync.client import connect  # noqa: PLC0415
    return connect(url, open_timeout=open_timeout)


def send_command(ws, cmd_type, payload=None, timeout=10):
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
    raw = ws.recv(timeout=timeout)
    elapsed = (time.perf_counter() - start) * 1000  # ms
    response = json.loads(raw)
    return elapsed, response.get("success", False), response.get("error")


def benchmark(ws, name, cmd_type, payload=None, iterations=ITERATIONS):
    # Warmup
    for _ in range(WARMUP):
        send_command(ws, cmd_type, payload)

    # Measure — COLD is the first measured call (D3), reported beside the warm
    # distribution rather than averaged into it.
    times = []
    last_err = None
    cold = None
    for _ in range(iterations):
        elapsed, ok, err = send_command(ws, cmd_type, payload)
        if ok:
            times.append(elapsed)
            if cold is None:
                cold = elapsed
        else:
            last_err = err
        # No delay — rate limiter bumped for demo (100 per-client bucket)

    if not times:
        print(f"  {name:30s}  FAILED (0/{iterations})  err={last_err}")
        return None
    if len(times) < iterations:
        print(f"  {name:30s}  (note: {iterations - len(times)} failures, err={last_err})")

    avg = statistics.mean(times)
    med = statistics.median(times)
    p95 = sorted(times)[int(len(times) * 0.95)]
    mn = min(times)
    mx = max(times)

    print(f"  {name:30s}  avg={avg:6.2f}ms  med={med:6.2f}ms  p95={p95:6.2f}ms  min={mn:5.2f}ms  max={mx:6.2f}ms  ({len(times)}/{iterations})")
    return {"op": name, "avg_ms": avg, "med_ms": med, "p95_ms": p95,
            "min_ms": mn, "max_ms": mx, "cold_ms": cold,
            "measured": len(times), "requested": iterations}


# ── LEGACY RUN — frozen. Changing this sequence breaks the "extend, never
#    rebuild" pin in tests/test_bench_scale.py. ───────────────────────────────

def legacy_main():
    print(f"\n{'='*80}")
    print(f"  Synapse Latency Benchmark — {URL}")
    print(f"  {ITERATIONS} iterations per command, {WARMUP} warmup")
    print(f"{'='*80}\n")

    ws = _connect(URL, open_timeout=5)

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


# ── SCALE EXTENSION ─────────────────────────────────────────────────────────

def _load_bench_scale():
    """Import the shared scale core by path (scripts/ is not a package —
    same importlib pattern harness/verify/perf_ratchet.py uses for
    tests/perf_counters.py)."""
    mod = sys.modules.get("bench_scale")
    if mod is not None:
        return mod
    path = REPO / "scripts" / "bench_scale.py"
    spec = importlib.util.spec_from_file_location("bench_scale", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bench_scale"] = mod
    spec.loader.exec_module(mod)
    return mod


def _call(ws, cmd_type, payload=None, timeout=10):
    """Full-response sibling of send_command. send_command returns only
    (elapsed, success, error) and DISCARDS the payload, which is right for the
    timing loop and useless for reading a value back. Kept separate so the
    legacy timing path stays byte-identical."""
    command = {
        "id": uuid.uuid4().hex[:16], "type": cmd_type,
        "payload": payload or {}, "sequence": 0, "timestamp": time.time(),
        "protocol_version": "4.0.0",
    }
    ws.send(json.dumps(command))
    return json.loads(ws.recv(timeout=timeout))


# The LIVE rung builder, kept as one reviewable source string so it can be
# hashed into every live record. It is NOT the offline builder and must never
# be presented as one: the offline tier drives a counting fake, this authors a
# real USD stage. Live records therefore carry cross_tier_comparable=False.
#
# Straight-line by construction: the bridge injects scripts under
# exec(code, G, L) with G is not L, so a helper function defined here could not
# see these top-level names (the split-scope trap).
LIVE_RUNG_BUILDER = r'''
import hou
stage_net = hou.node("/stage")
old = hou.node("/stage/sbench")
if old is not None:
    old.destroy()
n = stage_net.createNode("pythonscript", "sbench")
n.parm("python").set("""
from pxr import UsdGeom, Sdf, Vt
node = hou.pwd()
stage = node.editableStage()
for i in range(%(PRIMS)d):
    p = UsdGeom.Xform.Define(stage, "/sbench/p%%d" %% i)
    a = p.GetPrim().CreateAttribute("points", Sdf.ValueTypeNames.Float3Array)
    a.Set(Vt.Vec3fArray(%(ELEMENTS)d))
""")
n.cook(force=True)
# READ THE RUNG BACK — a rung reports its VERIFIED size, never its requested
# size. A build that silently produced a different stage must not be graphed.
st = n.stage()
prims = 0
elements = 0
for pr in st.TraverseAll():
    prims += 1
    for at in pr.GetAuthoredAttributes():
        try:
            tn = at.GetTypeName()
            if not getattr(tn, "isArray", False):
                continue
            v = at.Get()
            if v is not None:
                elements += len(v)
        except Exception:
            pass
result = {"prim_count_verified": prims, "authored_elements_verified": elements,
          "node": n.path()}
'''

LIVE_BUILDER_SHA = hashlib.sha256(
    LIVE_RUNG_BUILDER.encode("utf-8")).hexdigest()[:16]


def _live_scale_arm(args, bench, cmd):
    """The LIVE tier. Emits wall-clock, every number stamped with the build it
    was measured on, and every rung reporting its VERIFIED size.

    UNEXERCISED at authoring time: no bridge was reachable in the lane that
    wrote this (R305 lane I1). It is shipped as an ARM, not as a RESULT — no
    number produced by this function exists anywhere in this repo, and none
    may be quoted until someone runs it against a live session.

    Scope, stated: this arm measures the live WS transport envelope, which
    CANNOT pay the stage-hash cost (integrity_envelope.py:219 passes
    include_stage=False). Reaching the stage term needs the in-process L0b arm
    (bridge.execute under hython) — not built here, recorded as a followup
    rather than faked with a stage-touching op this path never charges for.
    """
    try:
        ws = _connect(URL, open_timeout=5)
    except Exception as exc:                       # noqa: BLE001
        print(f"\n  LIVE TIER UNAVAILABLE — no bridge at {URL}: "
              f"{type(exc).__name__}: {exc}")
        print("  Refusing to emit live numbers. Start Houdini + the SYNAPSE "
              "server, or use --tier offline.")
        return 2

    resp = _call(ws, "execute_python",
                 {"content": "import hou; "
                             "result = hou.applicationVersionString()"})
    build = str(((resp.get("data") or {}).get("result")
                 if isinstance(resp.get("data"), dict)
                 else resp.get("result")) or "UNKNOWN")

    print(f"\n{'='*80}")
    print(f"  SYNAPSE scale bench — LIVE tier ({URL})")
    print(f"  houdini_build_measured : {build}")
    print(f"  doc_pinned_build       : {bench.DOC_PINNED_HOUDINI_BUILD}"
          f"   (harness/state/drop.json ABSENT in this tree)")
    if build != bench.DOC_PINNED_HOUDINI_BUILD:
        print(f"  BUILD DRIFT: measured {build} != doc-pinned "
              f"{bench.DOC_PINNED_HOUDINI_BUILD}. Every number below is a "
              f"{build} number, and must be cited as one.")
    print(f"{'='*80}\n")

    _call(ws, "execute_python",
          {"content": "import hou; p=hou.node('/obj');"
                      " p.node('bench_node') or p.createNode('null',"
                      "'bench_node'); result='ok'"})

    points = args.volume or bench.DEFAULT_VOLUME_POINTS
    prims = bench.VOLUME_AXIS_PRIMS
    rows = []
    for elements in points:
        code = LIVE_RUNG_BUILDER % {"PRIMS": prims, "ELEMENTS": elements}
        # The rung build holds Houdini's main thread; it gets its own timeout
        # rather than the 10 s read default.
        built = _call(ws, "execute_python", {"content": code}, timeout=600)
        if not built.get("success"):
            print(f"  rung array_len={elements}: BUILD FAILED "
                  f"({built.get('error')}) — skipped, no number emitted")
            continue
        payload = built.get("data") if isinstance(built.get("data"), dict) \
            else built
        verified = payload.get("result") if isinstance(
            payload.get("result"), dict) else {}
        v_prims = verified.get("prim_count_verified")
        v_elems = verified.get("authored_elements_verified")
        if v_prims is None or v_elems is None:
            print(f"  rung array_len={elements}: rung size could not be read "
                  f"back — skipped. A rung reports its VERIFIED size or it "
                  f"does not report.")
            continue
        print(f"\n  --- rung: prims_verified={v_prims} "
              f"authored_elements_verified={v_elems:,} "
              f"(requested {bench.authored_elements(prims, elements):,}) ---")
        row = {
            "schema": bench.RECORD_SCHEMA, "tier": "live", "mode": "envelope",
            "axis": bench.AXIS_VOLUME,
            "rung": {"prim_count": v_prims, "prim_count_requested": prims,
                     "arrays_per_prim": 1, "array_len": elements,
                     "time_samples": 0,
                     "authored_elements": v_elems,
                     "authored_elements_requested":
                         bench.authored_elements(prims, elements),
                     "shape": "Lop/pythonscript authored Float3Array"},
            "houdini_build_measured": build,
            "cross_tier_comparable": False,
            "_cross_tier_note":
                "the LIVE builder authors a real USD stage; the OFFLINE "
                "builder drives a counting fake. Different builder_sha256 by "
                "construction — these rows may NOT share a curve with offline "
                "rows (bench_scale.fit_curve refuses the mix).",
            "_stage_term_note":
                "live WS transport only. The stage-hash term is ABSENT BY "
                "CONSTRUCTION on this path "
                "[python/synapse/server/integrity_envelope.py:219].",
            "producer": {**bench.producer_stamp(cmd),
                         "houdini": build,
                         "builder_sha256": LIVE_BUILDER_SHA,
                         "producer_path":
                             "_benchmark_latency.py::_live_scale_arm"},
            "timings_ms": {},
        }
        for label, ctype, payload_ in (
                ("ping", "ping", None),
                ("get_scene_info", "get_scene_info", None),
                ("get_parm", "get_parm",
                 {"node": "/obj/bench_node", "parm": "tx"}),
                ("set_parm (/obj null)", "set_parm",
                 {"node": "/obj/bench_node", "parm": "tx", "value": 1.0}),
        ):
            stats = benchmark(ws, label, ctype, payload_,
                              iterations=args.iterations)
            if stats:
                row["timings_ms"][label] = stats
        rows.append(row)

    _call(ws, "execute_python",
          {"content": "import hou; n=hou.node('/stage/sbench');"
                      " n and n.destroy();"
                      " b=hou.node('/obj/bench_node'); b and b.destroy();"
                      " result='ok'"})
    ws.close()

    print("\n  live_stage_term = ABSENT BY CONSTRUCTION "
          "[python/synapse/server/integrity_envelope.py:219 — the live WS "
          "envelope calls _compute_scene_hash(target, include_stage=False)]")
    print("  A flat envelope cost across these rungs is therefore a RESULT, "
          "not a null measurement.")
    print("  T1_reference: UNAVAILABLE — no absolute-seconds producer for the "
          "LLM turn at HEAD.\n")

    if args.json_out:
        blob = json.dumps({"schema": "bench_scale/run-v1", "tier": "live",
                           "rows": rows}, indent=1, sort_keys=True)
        if args.json_out == "-":
            print(blob)
        else:
            Path(args.json_out).write_text(blob, encoding="utf-8")
            print(f"  wrote {args.json_out}")
    return 0 if rows else 1


def build_parser():
    ap = argparse.ArgumentParser(
        prog="_benchmark_latency.py",
        description="SYNAPSE WS latency benchmark. With no arguments it runs "
                    "the legacy transport sequence unchanged. --tier offline "
                    "runs the scale bench with no Houdini, no bridge and no "
                    "pxr (counts only, never wall-clock).",
        epilog="scale axis = AUTHORED ARRAY VOLUME, not prim count "
               "(harness/latency/LEDGER.md section 1). "
               "Core: scripts/bench_scale.py")
    ap.add_argument("--iterations", type=int, default=ITERATIONS,
                    help="measured calls per op on the live tier")
    try:
        _load_bench_scale().add_scale_args(ap)
    except Exception as exc:                       # noqa: BLE001
        # --help must NEVER exit non-zero for want of the core — that is the
        # single thing harness/latency/verify.py::p5_offline_bench gates on.
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
        # No arguments => the legacy run, byte-for-byte. No parsing, no
        # branching, no chance of drift.
        legacy_main()
        return 0
    args = build_parser().parse_args(argv)
    if args.tier is None:
        legacy_main()
        return 0
    bench = _load_bench_scale()
    cmd = "python _benchmark_latency.py " + " ".join(argv)
    try:
        if args.tier == "offline":
            return bench.run_from_args(args, cmd)
        return _live_scale_arm(args, bench, cmd)
    except bench.BenchScaleError as exc:
        print(f"\n  REFUSED: {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
