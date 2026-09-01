#!/usr/bin/env python
"""BP2-LATENCY - memory latency receipt (deposit / recall / close-reopen-recall).

ONE script, two ways to run it - the same false-green lesson probe_silent_recall
teaches (docs/BATTLEPLAN.md:41): a number that only exists under the shim is not
a demo number. So this file runs BOTH places and stamps WHICH one it ran in, and
the build is READ from hou in-process (never typed) so the stamp equals the build
that took the timings (BP2-LATENCY crucible criterion #2).

  1. HEADLESS (agent lane), through the hytest shim:

       SYNAPSE_HYTHON="C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe" \
       python .synapse/hytest.py \
           harness/battleplan/notes/memory_latency_probe.py \
           -o python_files=memory_latency_probe.py -s

     -> runs under Houdini's hython (pytest collects test_memory_latency), writes
        harness/battleplan/runs/<date>/memory_latency_hython.json
        (a meta row, one row per timed op, an optional bucket-pass row, DONE last).
     The SYNAPSE_HYTHON pin targets the wave build (22.0.400) so the agent half
     matches Joe's .400 GUI half; hytest still validates it (pytest+PySide6) and
     falls back to newest-usable if that env is thin (.synapse/hytest.py:30-76).

  2. GUI (Joe's hands), pasted into the .400 Houdini Python shell:

       Windows menu > Python Shell (or the Python Source Editor). Paste this whole
       file and run. It prints the rows and, if it can locate the repo, writes
       harness/battleplan/runs/<date>/memory_latency_gui.json.

Timed ops (public MemoryPort surface ONLY - synapse.loop.ports; nothing under
python/synapse/memory/ is touched, so `git diff master..HEAD -- python/synapse/
memory/` stays empty), each repeated 5x, p50 + p95 per op:

  open                       MemoryPort(uri) bind (store open == reopen: same call)
  deposit                    port.deposit_settlement(known,"HIT") to ack (durable
                             on SUCCESS: MonetaBackedStore.add -> save() synchronous)
  recall                     port.query_and_filter([],[]) of the known deposit
  close                      MemoryPort.release(uri)
  layer_check                after reopen, cortex_root.usda in stage.GetLayerStack()
                             (USD sense), else the ECS layer-observable / recall hit
  recall_after_reopen        query_and_filter([],[]) after the reopen
  reopen_with_memory_layer   composite = close + open + layer_check + recall_after_reopen

Camera budgets (docs/BATTLEPLAN.md sec.2 call 8; proposed, ratification Joe's):
  deposit ack <= 500 ms  ·  recall p95 <= 1500 ms  ·  reopen-with-memory-layer
  <= 3000 ms  ·  demo scene  ·  N <= 200 memories.
Over budget on any op -> a SECOND timed pass (bucket_pass) isolates exactly one
bucket from {embedding time · stage-layer compose (Flatten class) · sync JSONL I/O
· lock wait · predicate scan}; no bucket is ever named without that row (crucible
criterion #5). Under budget -> the finding says so and proposes no fix.

HONESTY: headless Moneta may not bind (UNAVAILABLE by construction). That IS a
measurement - every latency field renders literal "UNKNOWN", availability is
recorded UNAVAILABLE, and UNKNOWN is never coerced to a number and never a pass
(BP2-LATENCY.md:73-76). deposit SUCCESS + empty recall is the silent-empty defect
this wave exists to kill, so recall verifies the KNOWN id returned, not just a
non-empty payload.

Read-only w.r.t. product code: imports SYNAPSE's own MemoryPort and changes
nothing in it. Writes only its run artifact under harness/battleplan/runs/ and a
scratch Moneta store under a temp dir it deletes. Every hou/pxr/synapse import is
guarded and done inside a function, so the module imports cleanly under stock
CPython too (availability then UNAVAILABLE, all ops UNKNOWN).
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

UNKNOWN = "UNKNOWN"

# Camera budgets, ms (docs/BATTLEPLAN.md sec.2 call 8). Op -> budget it is judged
# against. Ops with budget None are timed and reported but gate nothing directly.
BUDGET_MS = {
    "deposit": 500.0,
    "recall": 1500.0,
    "recall_after_reopen": 1500.0,
    "reopen_with_memory_layer": 3000.0,
}

REPEATS = 5
# N the recall/deposit numbers are measured at. The budget is stated at N <= 200,
# so seed near the ceiling: an "under budget" claim then holds at the worst case
# the budget allows, not only at N=1. Override for a fast smoke run.
SEED_N = int(os.environ.get("BP2_LATENCY_SEED_N", "195"))


# --------------------------------------------------------------------------- #
# environment / build / paths (runtime truth, never typed)
# --------------------------------------------------------------------------- #

def _detect_env() -> str:
    """'gui' when a Houdini UI is available, else 'hython' (the shim lane)."""
    try:
        import hou
        return "gui" if hou.isUIAvailable() else "hython"
    except Exception:
        return "hython"  # no hou at all -> headless posture


def _build():
    """hou.applicationVersionString() read at runtime. UNKNOWN when hou absent.

    Crucible anchor: the stamp must equal what the process that took the timings
    observes, so it is READ, never assumed."""
    try:
        import hou
        return hou.applicationVersionString()
    except Exception:
        return UNKNOWN


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


def _run_date() -> str:
    d = os.environ.get("BP2_RUN_DATE") or os.environ.get("BP1_RUN_DATE")
    if d:
        return d
    from datetime import date
    return date.today().isoformat()


def _repo_root():
    """Repo root from this file's location, or None when pasted (no __file__).

    harness/battleplan/notes/memory_latency_probe.py -> parents[3] = repo root."""
    f = globals().get("__file__")
    if not f:
        return None
    try:
        root = Path(f).resolve().parents[3]
        if (root / "harness" / "battleplan").is_dir():
            return root
    except Exception:
        pass
    return None


def _bootstrap_synapse() -> None:
    """Make `import synapse` resolve. Under the shim, pyproject pythonpath=['python']
    already does this; when pasted in the GUI the package env's PYTHONPATH does.
    Belt-and-suspenders for a bare run: insert <repo>/python ONLY if synapse is not
    already importable, so the live GUI package is never shadowed by this worktree."""
    try:
        import synapse  # noqa: F401
        return
    except Exception:
        pass
    root = _repo_root()
    if root is None:
        return
    py = root / "python"
    if py.is_dir() and str(py) not in sys.path:
        sys.path.insert(0, str(py))


def _claim_id_of(row):
    """Extract claim_id from a recall/raw row. Settlement fields are JSON-serialized
    inside payload.content (a string); there is no top-level payload.claim_id. This
    corrects the BP1 G4 false-negative (BP1_G4_FALSE_FAIL.md). Forward-compat: honor
    a flattened claim_id if the shape ever changes."""
    p = row.get("payload") or {}
    cid = p.get("claim_id")
    if cid:
        return cid
    try:
        return json.loads(p.get("content") or "{}").get("claim_id")
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# timing / statistics
# --------------------------------------------------------------------------- #

def _pctl(sorted_ms, q):
    """House percentile idiom (harness/notes/gate01_ipc_latency.py:68-74):
    sorted[int(n*q)-1], clamped into range. Small-n aware."""
    n = len(sorted_ms)
    if n == 0:
        return UNKNOWN
    idx = int(n * q) - 1
    if idx < 0:
        idx = 0
    if idx > n - 1:
        idx = n - 1
    return round(sorted_ms[idx], 3)


def _stats(samples_ms):
    """p50/p95/min/max over a list of wall_ms. UNKNOWN for every derived field
    when there are no samples (an op that could not run)."""
    clean = [s for s in samples_ms if isinstance(s, (int, float))]
    if not clean:
        return {
            "samples_ms": samples_ms,
            "p50_ms": UNKNOWN, "p95_ms": UNKNOWN,
            "min_ms": UNKNOWN, "max_ms": UNKNOWN, "n": 0,
        }
    s = sorted(clean)
    return {
        "samples_ms": [round(x, 3) for x in samples_ms],
        "p50_ms": round(statistics.median(s), 3),
        "p95_ms": _pctl(s, 0.95),
        "min_ms": round(s[0], 3),
        "max_ms": round(s[-1], 3),
        "n": len(clean),
    }


def _op_row(op, samples_ms, extra=None):
    st = _stats(samples_ms)
    budget = BUDGET_MS.get(op)
    over = None
    if budget is not None and isinstance(st["p95_ms"], (int, float)):
        over = st["p95_ms"] > budget
    row = {
        "kind": "op", "op": op,
        "budget_ms": budget if budget is not None else UNKNOWN,
        "over_budget": over if over is not None else UNKNOWN,
    }
    row.update(st)
    if extra:
        row.update(extra)
    return row


# --------------------------------------------------------------------------- #
# health line (backend / embedder id / dim / N) - read off the live handle
# --------------------------------------------------------------------------- #

def _health_line(handle):
    """backend + embedder id + dim + N from the bound store handle. Each field is
    measured or literal UNKNOWN - never guessed."""
    hl = {"backend": UNKNOWN, "embedder_id": UNKNOWN, "dim": UNKNOWN, "N": UNKNOWN}
    if handle is None:
        return hl
    try:
        hl["backend"] = type(handle).__name__
    except Exception:
        pass
    try:
        hl["embedder_id"] = getattr(handle, "embedder_id", UNKNOWN) or UNKNOWN
    except Exception:
        pass
    try:
        emb = getattr(handle, "_embedder", None)
        d = getattr(emb, "dim", None)
        hl["dim"] = d if isinstance(d, int) else UNKNOWN
    except Exception:
        pass
    try:
        hl["N"] = handle.count()
    except Exception:
        pass
    return hl


# --------------------------------------------------------------------------- #
# the measurement
# --------------------------------------------------------------------------- #

def _fresh_uri():
    import tempfile
    tmp = tempfile.mkdtemp(prefix="bp2_latency_")
    return tmp


def _bind(MemoryPort, MONETA_URI_SCHEME, tmp):
    uri = MONETA_URI_SCHEME + Path(tmp).as_posix()
    return uri


def measure():
    """Run the full latency measurement in-process. Returns (meta, op_rows,
    bucket_row_or_None). Never raises for an unavailable substrate - that path
    returns availability=UNAVAILABLE with every op UNKNOWN."""
    environment = _detect_env()
    build = _build()
    meta = {
        "kind": "meta", "leg": "BP2-LATENCY",
        "environment": environment, "build": build,
        "run_label": os.environ.get("BP2_LATENCY_LABEL", "default"),
        "repeats": REPEATS, "seed_n_target": SEED_N,
        "budgets_ms": dict(BUDGET_MS),
        "availability": UNKNOWN, "bind_status": UNKNOWN, "bind_reason": UNKNOWN,
        "backend": UNKNOWN, "embedder_id": UNKNOWN, "dim": UNKNOWN,
        "N": UNKNOWN, "N_after": UNKNOWN,
        "cold_open_ms": UNKNOWN, "seed_wall_ms": UNKNOWN, "seed_error": None,
        "started": _now_iso(),
    }
    op_rows = []
    bucket_row = None
    port = None
    uri = None
    tmp = None

    try:
        _bootstrap_synapse()
        from synapse.loop.ports import MemoryPort, MONETA_URI_SCHEME
        import uuid

        tmp = _fresh_uri()
        uri = _bind(MemoryPort, MONETA_URI_SCHEME, tmp)
        meta["store_dir"] = tmp

        # cold open (once): the very first bind, measured for context. The repeated
        # 'open' op below re-binds after release (store-open == reopen: same call).
        MemoryPort.release(uri)
        t0 = time.perf_counter()
        port = MemoryPort(uri)
        meta["cold_open_ms"] = round((time.perf_counter() - t0) * 1000.0, 3)

        if port.handle is None:
            # UNAVAILABLE by construction (headless Moneta). Record it as a
            # measurement: every latency field UNKNOWN, availability UNAVAILABLE.
            probe = port.query_and_filter([], [])
            meta["availability"] = "UNAVAILABLE"
            meta["bind_status"] = getattr(probe, "status", UNKNOWN)
            meta["bind_reason"] = getattr(probe, "error_message", UNKNOWN)
            meta["reason"] = (
                "MemoryPort did not bind a store handle: headless Moneta is "
                "UNAVAILABLE by construction (BP2-LATENCY.md note; STATE.json "
                "substrate_presence). No op can be timed -> UNKNOWN, never a "
                "number, never a pass.")
            for op in ("open", "deposit", "recall", "close", "layer_check",
                       "recall_after_reopen", "reopen_with_memory_layer"):
                op_rows.append(_op_row(op, [UNKNOWN] * REPEATS,
                                       {"note": "UNAVAILABLE: substrate did not bind"}))
            meta["finished"] = _now_iso()
            return meta, op_rows, bucket_row

        meta["availability"] = "AVAILABLE"
        meta["bind_status"] = "SUCCESS"
        hl = _health_line(port.handle)
        meta.update({k: hl[k] for k in ("backend", "embedder_id", "dim")})
        meta["N"] = hl["N"]

        # ------------------------------------------------------------------ #
        # seed to N_target (not timed as a budget op; wall recorded for context)
        # ------------------------------------------------------------------ #
        seed_t0 = time.perf_counter()
        seeded = 0
        try:
            start_n = port.handle.count()
            target = max(start_n, SEED_N)
            while port.handle.count() < target:
                sid = "BP2-LAT-seed-" + uuid.uuid4().hex[:10]
                r = port.deposit_settlement(sid, "HIT")
                if getattr(r, "status", None) != "SUCCESS":
                    meta["seed_error"] = (
                        "seed deposit returned %s (%s); stopped seeding at N=%d"
                        % (getattr(r, "status", "?"),
                           getattr(r, "error_message", "?"),
                           port.handle.count()))
                    break
                seeded += 1
                if seeded % 50 == 0:
                    print("# seeded %d (N=%d)" % (seeded, port.handle.count()))
        except Exception as e:
            meta["seed_error"] = "%s: %s" % (type(e).__name__, e)
        meta["seed_wall_ms"] = round((time.perf_counter() - seed_t0) * 1000.0, 3)
        try:
            meta["N"] = port.handle.count()
        except Exception:
            pass

        # ------------------------------------------------------------------ #
        # main pass: 5 repeats, time each op
        # ------------------------------------------------------------------ #
        samples = {k: [] for k in (
            "open", "deposit", "recall", "close", "layer_check",
            "recall_after_reopen", "reopen_with_memory_layer")}
        recall_hits = []
        reopen_recall_hits = []
        layer_methods = []
        last_known = None

        cortex = Path(tmp) / ".moneta" / "cortex_root.usda"

        def _timed(fn):
            t = time.perf_counter()
            out = fn()
            return (time.perf_counter() - t) * 1000.0, out

        for r in range(REPEATS):
            known = "BP2-LAT-known-%d-%s" % (r, uuid.uuid4().hex[:8])
            last_known = known

            # deposit (to ack; durable on SUCCESS)
            dt, dep = _timed(lambda: port.deposit_settlement(known, "HIT"))
            samples["deposit"].append(dt if getattr(dep, "status", None) == "SUCCESS"
                                      else UNKNOWN)

            # recall of the known deposit
            dt, rec = _timed(lambda: port.query_and_filter([], []))
            if getattr(rec, "status", None) == "SUCCESS":
                samples["recall"].append(dt)
                mems = (rec.payload or {}).get("filtered_memories", [])
                recall_hits.append(any(_claim_id_of(m) == known for m in mems))
            else:
                samples["recall"].append(UNKNOWN)
                recall_hits.append(UNKNOWN)

            # close -> reopen -> layer_check -> recall_after_reopen (the composite)
            dt_close, _ = _timed(lambda: MemoryPort.release(uri))
            samples["close"].append(dt_close)

            # reopen == store-open: the same MemoryPort(uri) bind call, timed.
            t = time.perf_counter()
            port = MemoryPort(uri)
            dt_open = (time.perf_counter() - t) * 1000.0
            samples["open"].append(dt_open if port.handle is not None else UNKNOWN)

            # layer_check: USD cortex layer in stack (stage-compose cost), else the
            # backend-agnostic ECS/recall-hit observability. Same method all repeats
            # where possible; method recorded per repeat.
            dt_layer, method, layer_ok = _timed_layer_check(port, uri, cortex, known)
            samples["layer_check"].append(dt_layer)
            layer_methods.append(method)

            # recall after reopen (did the deposit survive the reopen?)
            dt, rec2 = _timed(lambda: port.query_and_filter([], []))
            if getattr(rec2, "status", None) == "SUCCESS":
                samples["recall_after_reopen"].append(dt)
                mems2 = (rec2.payload or {}).get("filtered_memories", [])
                reopen_recall_hits.append(any(_claim_id_of(m) == known for m in mems2))
            else:
                samples["recall_after_reopen"].append(UNKNOWN)
                reopen_recall_hits.append(UNKNOWN)

            # composite reopen-with-memory-layer
            parts = [dt_close, dt_open, dt_layer,
                     samples["recall_after_reopen"][-1]]
            if all(isinstance(p, (int, float)) for p in parts):
                samples["reopen_with_memory_layer"].append(sum(parts))
            else:
                samples["reopen_with_memory_layer"].append(UNKNOWN)

        try:
            meta["N_after"] = port.handle.count()
        except Exception:
            pass

        op_rows.append(_op_row("open", samples["open"],
                               {"note": "store-open == reopen (MemoryPort(uri) bind); "
                                        "cold_open_ms in meta is the first cold bind"}))
        op_rows.append(_op_row("deposit", samples["deposit"],
                               {"durable_on_success": True}))
        op_rows.append(_op_row("recall", samples["recall"],
                               {"known_recalled": recall_hits}))
        op_rows.append(_op_row("close", samples["close"]))
        op_rows.append(_op_row("layer_check", samples["layer_check"],
                               {"method": layer_methods}))
        op_rows.append(_op_row("recall_after_reopen", samples["recall_after_reopen"],
                               {"known_recalled": reopen_recall_hits}))
        op_rows.append(_op_row("reopen_with_memory_layer",
                               samples["reopen_with_memory_layer"],
                               {"composite_of": ["close", "open", "layer_check",
                                                 "recall_after_reopen"]}))

        # ------------------------------------------------------------------ #
        # bucket pass (T2): only if some op is over its budget
        # ------------------------------------------------------------------ #
        over_ops = [r["op"] for r in op_rows
                    if r.get("over_budget") is True]
        meta["over_budget_ops"] = over_ops
        if over_ops:
            bucket_row = _bucket_pass(port, uri, tmp, last_known, over_ops)
            meta["named_bucket"] = bucket_row.get("named_bucket", UNKNOWN)
        else:
            meta["named_bucket"] = "none (under budget)"

        meta["finished"] = _now_iso()
        return meta, op_rows, bucket_row

    except Exception as e:
        meta["availability"] = meta.get("availability") or UNKNOWN
        meta["exception"] = "%s: %s" % (type(e).__name__, e)
        if not op_rows:
            for op in ("open", "deposit", "recall", "close", "layer_check",
                       "recall_after_reopen", "reopen_with_memory_layer"):
                op_rows.append(_op_row(op, [UNKNOWN] * REPEATS,
                                       {"note": "probe exception before/at this op"}))
        meta["finished"] = _now_iso()
        return meta, op_rows, bucket_row
    finally:
        _cleanup_store(uri, tmp)


def _timed_layer_check(port, uri, cortex, known):
    """Time the layer-in-stack check for one repeat. Returns (wall_ms, method,
    ok). Prefers the USD cortex-layer-stack check (a real stage-compose cost that
    belongs to the reopen budget); falls back to a backend-agnostic recall-hit
    observability check when pxr/cortex is absent."""
    t = time.perf_counter()
    method = UNKNOWN
    ok = UNKNOWN
    try:
        if cortex.is_file():
            try:
                from pxr import Usd
                method = "usd_layer_stack"
                stage = Usd.Stage.Open(cortex.as_posix())
                ids = []
                if stage is not None:
                    for lyr in stage.GetLayerStack():
                        try:
                            ids.append(lyr.identifier)
                        except Exception:
                            pass
                ok = any("cortex" in (i or "").lower() for i in ids)
            except Exception:
                method = "recall_hit_fallback"
                rec = port.query_and_filter([], [])
                mems = (getattr(rec, "payload", None) or {}).get("filtered_memories", [])
                ok = any(_claim_id_of(m) == known for m in mems)
        else:
            method = "recall_hit_fallback"
            rec = port.query_and_filter([], [])
            mems = (getattr(rec, "payload", None) or {}).get("filtered_memories", [])
            ok = any(_claim_id_of(m) == known for m in mems)
    except Exception as e:
        method = "error:%s" % type(e).__name__
        ok = UNKNOWN
    return (time.perf_counter() - t) * 1000.0, method, ok


def _bucket_pass(port, uri, tmp, known, over_ops):
    """Second timed pass (T2): isolate exactly one bucket for the over-budget op(s).
    Each candidate bucket is timed x REPEATS; the named bucket is the one whose row
    best accounts for the overage. Buckets attempted:
      embedding_time      port.handle._embedder.embed(text)
      sync_jsonl_io       port.handle.save() (synchronous snapshot write / durability)
      predicate_scan      port._fetch_raw_memories([]) (raw fetch, pre-filter)
      filter_delta        query_and_filter - raw fetch  (PG-DRM predicate/utility filter)
      stage_layer_compose Usd.Stage.Open(cortex).Flatten().ExportToString() (Flatten class)
    lock_wait is not isolable through a public call and is only named with direct
    evidence; absent that it is reported UNKNOWN and never named (criterion #5)."""
    row = {"kind": "bucket_pass", "over_ops": over_ops,
           "buckets_ms": {}, "named_bucket": UNKNOWN, "evidence": {},
           "vocabulary": ["embedding time", "stage-layer compose (Flatten class)",
                          "sync JSONL I/O", "lock wait", "predicate scan"]}
    handle = port.handle
    cortex = Path(tmp) / ".moneta" / "cortex_root.usda"

    def rep(fn):
        out = []
        for _ in range(REPEATS):
            t = time.perf_counter()
            try:
                fn()
                out.append((time.perf_counter() - t) * 1000.0)
            except Exception:
                out.append(UNKNOWN)
        return _stats(out)

    # embedding time
    try:
        emb = getattr(handle, "_embedder", None)
        if emb is not None and hasattr(emb, "embed"):
            row["buckets_ms"]["embedding_time"] = rep(
                lambda: emb.embed("BP2 latency bucket probe query text"))
    except Exception as e:
        row["evidence"]["embedding_time_error"] = "%s: %s" % (type(e).__name__, e)

    # sync JSONL I/O / durability (the snapshot write)
    try:
        if hasattr(handle, "save"):
            row["buckets_ms"]["sync_jsonl_io"] = rep(lambda: handle.save())
    except Exception as e:
        row["evidence"]["sync_jsonl_io_error"] = "%s: %s" % (type(e).__name__, e)

    # predicate scan (raw fetch, pre-filter) and filter delta
    raw_stats = None
    try:
        if hasattr(port, "_fetch_raw_memories"):
            raw_stats = rep(lambda: port._fetch_raw_memories([]))
            row["buckets_ms"]["predicate_scan"] = raw_stats
    except Exception as e:
        row["evidence"]["predicate_scan_error"] = "%s: %s" % (type(e).__name__, e)
    try:
        full_stats = rep(lambda: port.query_and_filter([], []))
        row["evidence"]["query_and_filter_ms"] = full_stats
        if raw_stats and isinstance(full_stats.get("p50_ms"), (int, float)) \
                and isinstance(raw_stats.get("p50_ms"), (int, float)):
            row["buckets_ms"]["filter_delta"] = {
                "p50_ms": round(full_stats["p50_ms"] - raw_stats["p50_ms"], 3),
                "p95_ms": (round(full_stats["p95_ms"] - raw_stats["p95_ms"], 3)
                           if isinstance(full_stats.get("p95_ms"), (int, float))
                           and isinstance(raw_stats.get("p95_ms"), (int, float))
                           else UNKNOWN),
                "note": "query_and_filter minus raw fetch = PG-DRM predicate/utility filter",
            }
    except Exception as e:
        row["evidence"]["filter_delta_error"] = "%s: %s" % (type(e).__name__, e)

    # stage-layer compose (Flatten class)
    try:
        if cortex.is_file():
            from pxr import Usd

            def _flatten():
                st = Usd.Stage.Open(cortex.as_posix())
                if st is not None:
                    st.Flatten().ExportToString()
            row["buckets_ms"]["stage_layer_compose"] = rep(_flatten)
        else:
            row["evidence"]["stage_layer_compose"] = (
                "no cortex_root.usda authored (use_real_usd fell back or pxr absent) "
                "-> Flatten class not on this store's path")
    except Exception as e:
        row["evidence"]["stage_layer_compose_error"] = "%s: %s" % (type(e).__name__, e)

    # name the single dominant bucket by p95 (only among buckets that produced a
    # number). This is the isolating row the crucible requires before any name.
    bucket_label = {
        "embedding_time": "embedding time",
        "sync_jsonl_io": "sync JSONL I/O",
        "predicate_scan": "predicate scan",
        "filter_delta": "predicate scan",
        "stage_layer_compose": "stage-layer compose (Flatten class)",
    }
    best_key, best_p95 = None, -1.0
    for k, st in row["buckets_ms"].items():
        p = st.get("p95_ms")
        if isinstance(p, (int, float)) and p > best_p95:
            best_key, best_p95 = k, p
    if best_key is not None:
        row["named_bucket"] = bucket_label[best_key]
        row["named_bucket_key"] = best_key
        row["named_bucket_p95_ms"] = best_p95
        row["evidence"]["rule"] = (
            "dominant bucket = largest isolated p95 among buckets that produced a "
            "number; exactly one named (BP2-LATENCY crucible criterion #5)")
    else:
        row["evidence"]["rule"] = ("no bucket produced a number; no bucket named "
                                   "(criterion #5) - over-budget cause UNKNOWN")
    return row


def _cleanup_store(uri, tmp):
    try:
        if uri is not None:
            from synapse.loop.ports import MemoryPort
            MemoryPort.release(uri)
    except Exception:
        pass
    try:
        if tmp:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# emit / orchestration
# --------------------------------------------------------------------------- #

def _verdict(meta, op_rows):
    if meta.get("availability") == "UNAVAILABLE":
        return "UNAVAILABLE"
    over = [r["op"] for r in op_rows if r.get("over_budget") is True]
    if over:
        return "over_budget"
    # under-budget only if every budgeted op produced a p95 number that is under
    budgeted = [r for r in op_rows if isinstance(r.get("budget_ms"), (int, float))]
    if budgeted and all(isinstance(r.get("p95_ms"), (int, float))
                        and r["over_budget"] is False for r in budgeted):
        return "under_budget"
    return "UNKNOWN"


def emit(meta, op_rows, bucket_row, write=True):
    for r in [meta] + op_rows + ([bucket_row] if bucket_row else []):
        print(json.dumps(r, ensure_ascii=False))
    verdict = _verdict(meta, op_rows)
    path = None
    root = _repo_root()
    if write and root is not None:
        run_dir = root / "harness" / "battleplan" / "runs" / _run_date()
        run_dir.mkdir(parents=True, exist_ok=True)
        env = meta.get("environment", "hython")
        # A non-default run_label (e.g. "provisioned") suffixes the filename so the
        # mission's default agent-lane artifact memory_latency_<env>.json is never
        # overwritten by a differently-provisioned investigation run.
        label = meta.get("run_label", "default")
        suffix = "" if label in ("default", "", None) else ("_" + str(label))
        path = run_dir / ("memory_latency_%s%s.json" % (env, suffix))
        sentinel = {
            "sentinel": "DONE",
            "leg": "BP2-LATENCY",
            "environment": env,
            "run_label": label,
            "build": meta.get("build"),
            "availability": meta.get("availability"),
            "N": meta.get("N"),
            "backend": meta.get("backend"),
            "embedder_id": meta.get("embedder_id"),
            "dim": meta.get("dim"),
            "repeats": meta.get("repeats"),
            "verdict": verdict,
            "over_budget_ops": meta.get("over_budget_ops", []),
            "named_bucket": meta.get("named_bucket", UNKNOWN),
            "row_count": 1 + len(op_rows) + (1 if bucket_row else 0),
            "completed": _now_iso(),
        }
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
            for r in op_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            if bucket_row:
                f.write(json.dumps(bucket_row, ensure_ascii=False) + "\n")
            f.write(json.dumps(sentinel, ensure_ascii=False) + "\n")  # DONE last
        print("# wrote %s" % path.as_posix())
    print("# environment=%s build=%s availability=%s verdict=%s bucket=%s"
          % (meta.get("environment"), meta.get("build"),
             meta.get("availability"), verdict, meta.get("named_bucket", UNKNOWN)))
    return path, verdict


def run_probe():
    return measure()


# pytest entry point: collected by the hytest shim (hython -m pytest). The probe
# RUNNING is the pass contract; latency numbers and availability are DATA, never
# asserted - UNKNOWN/UNAVAILABLE are legitimate measurements this test must not
# coerce. It asserts only the SHAPE of the receipt.
def test_memory_latency():
    meta, op_rows, bucket_row = run_probe()
    assert isinstance(meta, dict) and meta.get("leg") == "BP2-LATENCY", meta
    assert meta.get("environment") in ("hython", "gui"), meta
    assert meta.get("availability") in ("AVAILABLE", "UNAVAILABLE", UNKNOWN), meta
    assert len(op_rows) == 7, [r.get("op") for r in op_rows]
    for r in op_rows:
        assert set(("kind", "op", "budget_ms", "over_budget", "samples_ms",
                    "p50_ms", "p95_ms", "min_ms", "max_ms", "n")).issubset(r.keys()), r
        assert len(r["samples_ms"]) == REPEATS, r
    path, verdict = emit(meta, op_rows, bucket_row, write=True)
    assert path is not None, "repo root unresolved under the shim"
    lines = [ln for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]
    # meta + 7 op rows + optional bucket + DONE
    assert len(lines) in (9, 10), len(lines)
    assert json.loads(lines[-1]).get("sentinel") == "DONE", lines[-1]


if __name__ == "__main__":
    _meta, _ops, _bucket = run_probe()
    emit(_meta, _ops, _bucket, write=True)
