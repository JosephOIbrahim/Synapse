#!/usr/bin/env python3
"""bench_scale — the scale-parameterized cost core (I1 design, R305 lane I1).

WHY THIS EXISTS
    docs/reviews/synapse-latency-report-2026-07-27.md:20 states T4 = "1-70 ms
    per op" with NO scene-scale term. That missing denominator is what let a
    6.9-7.7 s per-op cost coexist with a ledger calling the same bin "the 5%".
    This module supplies the denominator: it sweeps a scale axis and emits the
    CURVE (intercept + slope per counter), not a single endpoint.

THE AXIS IS AUTHORED ARRAY VOLUME, NOT PRIM COUNT
    The I1 design parameterized by prim count. H10 (harness/latency/LEDGER.md
    section 1, producer: C2 crucible live probe) refuted that as the central
    axis: 10,000 inline spheres = 10,626 prims = 358.8 ms, the SAME content
    instanceable = 101 prims = 5.0 ms, and a 4-prim PointInstancer at
    2,000,000 instances = 2,017.9 ms/op while a prim-count gate answers False
    (a 16,677x miss). The shipped gate now carries BOTH terms
    (shared/bridge.py::_stage_exceeds + ::_stage_volume_exceeds), so this
    bench carries both axes:

      AXIS_PRIMS   prims grow, authored volume held ~constant (scalar attrs)
      AXIS_VOLUME  prims held CONSTANT (4 — the C2 PointInstancer shape),
                   authored array elements grow. This is the axis the design
                   was blind to; sweeping it is what SHOWS the axis rather
                   than asserting it.

TWO TIERS, AND WHAT EACH MAY EMIT
    OFFLINE (this module)  no hou, no bridge process, no pxr, no socket.
        Emits COUNTS and derived slopes ONLY. It emits NO wall-clock key
        whatsoever: ``assert_record_honest`` rejects any record carrying a
        key with a time-ish TOKEN anywhere in it (``ms`` / ``sec`` /
        ``latency`` / ``duration`` / ``elapsed`` …, underscore-delimited, at
        any nesting depth), any share-of-turn field, any record with an empty
        producer, and any rung parameterized by prim count alone. An offline
        tier that reports latency numbers is the exact dishonesty this repo
        guards against.
    LIVE (arms in _benchmark_latency.py / _benchmark_api.py)
        Real bridge/Houdini. MAY emit wall-clock, each number tagged with the
        build it was measured on. Never produced by this module.

    A counted proxy is NOT a timer. ``flatten_exports`` counts CALLS to
    ``stage.Flatten().ExportToString()``; it does not and cannot price the
    bytes that call serializes. Reading a flat ``flatten_exports`` across a
    volume sweep as "volume is free" would be exactly the 07-27 error. The
    volume axis is visible here through the GATE RESPONSE (which mode ran,
    and therefore whether Flatten ran at all), not through the cost of a
    Flatten this instrument never times.

ONE COUNTER VOCABULARY
    The counters, the fakes and the module-attribute seam are IMPORTED from
    tests/perf_counters.py (the ARMED perf ratchet's instrument) rather than
    re-declared. Two vocabularies is how the ratchet and the bench drift
    apart. perf_counters.py is not modified by this module — the armed
    instrument stays byte-identical; this file only composes on top of it.
    The underscore-prefixed imports are deliberate: they are the seam, and
    copying them would fork the vocabulary.

NOT A GATE. The perf ratchet (harness/verify/perf_ratchet.py) is the gate;
this bench is the map. Nothing here reads or writes harness/verify/
perf_baseline.json.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

RECORD_SCHEMA = "bench_scale/record-v1"
CURVE_SCHEMA = "bench_scale/curve-v1"

# Doc-pinned Houdini target. harness/state/drop.json does not exist in this
# tree (checked 2026-08-02), so the pin is read from CLAUDE.md's stated target
# and the LIVE tier stamps whatever the running build actually reports. The
# drift is printed, never hidden.
DOC_PINNED_HOUDINI_BUILD = "22.0.368"


# ── perf_counters loader (same importlib-from-path pattern as
#    harness/verify/perf_ratchet.py::_load_perf_counters, so this works from
#    any cwd and under pytest alike) ───────────────────────────────────────────

def _load_perf_counters():
    mod = sys.modules.get("perf_counters")
    if mod is not None:
        return mod
    path = REPO / "tests" / "perf_counters.py"
    spec = importlib.util.spec_from_file_location("perf_counters", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["perf_counters"] = mod
    spec.loader.exec_module(mod)
    return mod


pc = _load_perf_counters()
COUNTERS = pc.COUNTERS  # the ONE vocabulary — never re-declared here


class BenchScaleError(RuntimeError):
    """A rung's premise did not hold, or an emitted record violated an
    honesty rule. An instrument that half-ran must never return numbers."""


# ── volume-bearing fakes (compose on perf_counters', never fork them) ────────

class _ArrayHandle:
    """A resolved Vt array handle stand-in. The bridge's volume probe only
    ever calls ``len()`` on it (shared/bridge.py::_stage_volume_exceeds:
    "element counts only, never element reads"), so a 4M-element rung costs
    one small object, not 4M cells. If the bridge ever starts READING
    elements, this raises rather than under-counting."""
    __slots__ = ("_n",)

    def __init__(self, n: int):
        self._n = n

    def __len__(self):
        return self._n

    def __iter__(self):
        raise BenchScaleError(
            "the bridge iterated an array handle — _stage_volume_exceeds is "
            "documented as len()-only; the fake is now under-counting")


class _VolumeAttr(pc._CountingAttr):
    """Authored ARRAY attribute of a declared element count. Counted through
    the inherited perf_counters vocabulary (attrs_examined on GetTypeName,
    value_reads on Get)."""
    __slots__ = ("_n", "_ts")

    def __init__(self, counters: dict, elements: int, time_samples: int = 0):
        super().__init__(counters, is_array=True)
        self._n = elements
        self._ts = time_samples

    def GetName(self):
        return "points"

    def Get(self, _time=None):
        self._c["value_reads"] += 1
        return _ArrayHandle(self._n)

    def GetTimeSamples(self):
        self._c["value_reads"] += 1
        return []

    def GetNumTimeSamples(self):
        # Deliberately uncounted, exactly as in perf_counters._CountingAttr —
        # structural metadata, not a value read. Do not fold it into
        # value_reads without promoting that as its own event.
        return self._ts


class _VolumePrim(pc._CountingPrim):
    """Flyweight prim carrying array attrs instead of the v1 scalar attr."""
    __slots__ = ()

    def __init__(self, counters: dict, elements: int, arrays_per_prim: int = 1,
                 time_samples: int = 0, path: str = "/perf/prim"):
        super().__init__(counters, path)
        self._attrs = tuple(_VolumeAttr(counters, elements, time_samples)
                            for _ in range(max(1, arrays_per_prim)))

    def GetAuthoredPropertyNames(self):
        self._c["prop_name_reads"] += 1
        return tuple(f"points{i}" for i in range(len(self._attrs)))


class _VolumeStage(pc._CountingStage):
    """Counting stage whose prims carry authored array volume."""
    __slots__ = ()

    def __init__(self, counters: dict, n_prims: int, elements: int,
                 arrays_per_prim: int = 1, time_samples: int = 0):
        super().__init__(counters, n_prims)
        self._prim = _VolumePrim(counters, elements, arrays_per_prim,
                                 time_samples)


def scalar_stage_factory():
    """AXIS_PRIMS factory: perf_counters' shipped v1 shape (one SCALAR attr
    per prim). Authored array volume is ZERO by construction, so the volume
    term stays silent and the prim term is the only axis moving."""
    def factory(counters, prims):
        return pc._CountingStage(counters, prims)
    return factory


def volume_stage_factory(elements: int, arrays_per_prim: int = 1,
                         time_samples: int = 0):
    """AXIS_VOLUME factory: prims stay wherever the caller puts them while
    authored array elements grow. ``elements`` is the per-attribute array
    length; authored volume = prims x arrays_per_prim x elements x
    max(1, time_samples), matching _stage_volume_exceeds' own arithmetic
    (shared/bridge.py: ``total += n * (ns if ns and ns > 0 else 1)``)."""
    def factory(counters, prims):
        return _VolumeStage(counters, prims, elements, arrays_per_prim,
                            time_samples)
    return factory


def authored_elements(prims: int, elements: int, arrays_per_prim: int = 1,
                      time_samples: int = 0) -> int:
    """The scale term the gate actually keys on. Mirrors the bridge's own
    accumulation so the rung's declared volume and the gate's measured volume
    cannot silently disagree."""
    return prims * max(1, arrays_per_prim) * elements * max(1, time_samples)


# ── the offline driver ──────────────────────────────────────────────────────

def measure_rung(prims: int, *, prim_threshold: int, volume_threshold: int,
                 stage_factory) -> tuple[dict[str, int], str]:
    """One bridge.execute() stage-touching op on the /mcp path against a
    counting fake stage. Returns (counters, observed stage_hash_mode).

    Drives the REAL, unmodified ``LosslessExecutionBridge.execute()`` through
    perf_counters' module-attribute seam (``_patched`` — never
    sys.modules['hou'], which is the documented fake-residency trap,
    tests/conftest.py). The volume threshold is re-pinned INSIDE the patched
    block because ``_stage_hash_volume_threshold()`` reads env at CALL time
    and ``_patched`` restores every pin it saved on exit.
    """
    counters = pc._new_counters()
    stage = stage_factory(counters, prims)
    lop = pc._make_lop(counters, stage)
    hou_obj = pc._CountingHou({"/stage": lop})
    with pc._patched(hou_obj, prim_threshold):
        os.environ[pc._ENV_VOLUME] = str(volume_threshold)
        bridge = pc.LosslessExecutionBridge()
        pc._wrap_scene_hash(bridge, counters)
        res = bridge.execute(pc._op(lambda: None, touches_stage=True,
                                    stage_path="/stage"))
        if not res.success:
            raise BenchScaleError(f"rung did not succeed: {res.error}")
        mode = res.integrity.stage_hash_mode
    return counters, mode


# ── producer stamping (Law 2) ───────────────────────────────────────────────

_BUILDER_SOURCES = (
    "_ArrayHandle", "_VolumeAttr", "_VolumePrim", "_VolumeStage",
    "scalar_stage_factory", "volume_stage_factory", "authored_elements",
    "measure_rung",
)


def builder_sha256() -> str:
    """sha256 over the SOURCE of every rung builder. Rows with differing
    builder_sha256 describe different scenes and may not share a curve —
    ``fit_curve`` refuses to mix them."""
    h = hashlib.sha256()
    for name in _BUILDER_SOURCES:
        h.update(inspect.getsource(globals()[name]).encode("utf-8"))
    return h.hexdigest()[:16]


def _git(*args) -> tuple[int, str]:
    try:
        p = subprocess.run(["git", *args], cwd=str(REPO), capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=30)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return p.returncode, (p.stdout or "").strip()


def _pxr_version() -> str | None:
    try:
        import pxr  # noqa: PLC0415
    except Exception:
        return None
    return str(getattr(pxr, "__version__", "present"))


def producer_stamp(cmd: str) -> dict:
    """Law 2: every emitted number carries the command that made it and the
    env pins that shaped it. ``assert_record_honest`` rejects a row with any
    of cmd / git / interpreter / builder_sha256 empty."""
    rc, sha = _git("rev-parse", "--short", "HEAD")
    rc_d, dirty = _git("status", "--porcelain")
    return {
        "cmd": cmd,
        "git": sha if rc == 0 and sha else "UNKNOWN",
        "git_dirty": bool(rc_d == 0 and dirty),
        "interpreter": f"{platform.python_implementation()} "
                       f"{platform.python_version()}",
        "pxr": _pxr_version(),
        "houdini": None,            # offline tier: no Houdini, stated as null
        "doc_pinned_houdini": DOC_PINNED_HOUDINI_BUILD,
        "host": platform.processor() or platform.machine(),
        "platform": platform.platform(),
        "builder_sha256": builder_sha256(),
        "producer_path": "scripts/bench_scale.py::measure_rung",
    }


def env_pins(prim_threshold: int, volume_threshold: int) -> dict:
    return {
        "SYNAPSE_STAGE_HASH_PRIM_THRESHOLD": str(prim_threshold),
        "SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD": str(volume_threshold),
        "SYNAPSE_STAGE_HASH_LARGE_MODE": "<unset>",
        "_note": "pinned per rung inside perf_counters._patched; the shipped "
                 "defaults are guarded separately by "
                 "harness/verify/perf_ratchet.py::check_pinned_constants",
    }


# ── honesty rules, enforced in code (not in prose) ──────────────────────────

# Token-boundary, not suffix-only: a suffix-anchored pattern let `ms_total`
# and `duration_of_hash` through, which is the whole class this rule exists to
# stop. Underscore-delimited tokens, matched anywhere in the key.
_WALLCLOCK_KEY = re.compile(
    r"(^|_)(ms|msec|msecs|sec|secs|second|seconds|ns|us|latency|elapsed"
    r"|duration|walltime|wallclock|wall_clock|perf_counter)($|_)",
    re.IGNORECASE)
_SHARE_KEY = re.compile(r"(share|percent|pct|_of_turn|fraction)", re.IGNORECASE)
_REQUIRED_PRODUCER = ("cmd", "git", "interpreter", "builder_sha256",
                      "producer_path")


def _walk_keys(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            here = f"{prefix}.{k}" if prefix else str(k)
            yield here, k, v
            yield from _walk_keys(v, here)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _walk_keys(v, f"{prefix}[{i}]")


def assert_record_honest(rec: dict) -> dict:
    """The emitter's hard gate. Raises BenchScaleError on:
      1. an OFFLINE record carrying ANY wall-clock-shaped key,
      2. ANY record carrying a share-of-turn / percent-of-wall-clock field,
      3. a missing/empty producer field (Law 2),
      4. a rung that declares a prim count but no authored_elements — a
         record parameterized by prims alone reproduces the exact blind spot
         this instrument exists to remove (H10).
    Returns the record so it can be used inline."""
    tier = rec.get("tier")
    for path, key, _v in _walk_keys(rec):
        if _SHARE_KEY.search(str(key)):
            raise BenchScaleError(
                f"record carries a share-of-turn/percent field {path!r}; no "
                f"tier of this bench may emit one (there is no absolute-"
                f"seconds producer for the LLM turn at HEAD)")
        if tier == "offline" and _WALLCLOCK_KEY.search(str(key)):
            raise BenchScaleError(
                f"OFFLINE record carries wall-clock key {path!r}; the offline "
                f"tier emits COUNTS ONLY — an offline tier that reports "
                f"latency numbers is the dishonesty this bench guards against")
    prod = rec.get("producer") or {}
    missing = [k for k in _REQUIRED_PRODUCER if not str(prod.get(k, "")).strip()]
    if missing:
        raise BenchScaleError(
            f"record producer missing {', '.join(missing)} — Law 2: no number "
            f"without a producer path beside it")
    rung = rec.get("rung") or {}
    if "prim_count" in rung and "authored_elements" not in rung:
        raise BenchScaleError(
            "rung declares prim_count with no authored_elements — a prim-only "
            "parameterization is the H10 blind spot (4-prim PointInstancer @ "
            "2M instances, 2017.9 ms/op, prim gate False)")
    return rec


# ── sweeps ──────────────────────────────────────────────────────────────────

AXIS_PRIMS = "prims"
AXIS_VOLUME = "authored_elements"

# The C2 PointInstancer shape: prim-LIGHT, value-HEAVY. Held constant across
# the whole volume sweep so the curve isolates the volume term.
VOLUME_AXIS_PRIMS = 4

# Straddles the SHIPPED prim default (10_000): _stage_exceeds fires on
# STRICTLY MORE than the threshold, so 10_000 is the last full-mode rung and
# 10_001 is the first reduced one. The adjacent pair is the gate boundary
# stated as an observation, not an assertion.
DEFAULT_PRIM_POINTS = (100, 1_000, 10_000, 10_001, 20_000)
# Straddles the SHIPPED volume default (500_000): these are per-attribute
# ARRAY LENGTHS, and authored volume = 4 prims x length -> 100k / 200k / 500k
# below, 1M / 4M above. 4M is the C2 repro's own volume.
DEFAULT_VOLUME_POINTS = (25_000, 50_000, 125_000, 250_000, 1_000_000)

SHIPPED_PRIM_THRESHOLD = 10_000
SHIPPED_VOLUME_THRESHOLD = 500_000


def sweep_prims(points=DEFAULT_PRIM_POINTS, *,
                prim_threshold: int = SHIPPED_PRIM_THRESHOLD,
                volume_threshold: int = SHIPPED_VOLUME_THRESHOLD,
                cmd: str = "") -> list[dict]:
    """AXIS_PRIMS: prims grow, authored array volume held at ZERO."""
    stamp = producer_stamp(cmd or "scripts/bench_scale.py sweep_prims")
    pins = env_pins(prim_threshold, volume_threshold)
    out = []
    for n in points:
        counters, mode = measure_rung(
            n, prim_threshold=prim_threshold,
            volume_threshold=volume_threshold,
            stage_factory=scalar_stage_factory())
        out.append(assert_record_honest({
            "schema": RECORD_SCHEMA,
            "tier": "offline",
            "mode": "count",
            "axis": AXIS_PRIMS,
            "rung": {
                "prim_count": n,
                "arrays_per_prim": 0,
                "array_len": 0,
                "time_samples": 0,
                "authored_elements": 0,
                "shape": "scalar_attr_per_prim",
            },
            "gate": {
                "prim_threshold": prim_threshold,
                "volume_threshold": volume_threshold,
                "large_mode": "reduced",
                "observed_mode": mode,
            },
            "counters": counters,
            "env_pins": pins,
            "producer": stamp,
        }))
    return out


def sweep_volume(points=DEFAULT_VOLUME_POINTS, *,
                 prims: int = VOLUME_AXIS_PRIMS, arrays_per_prim: int = 1,
                 time_samples: int = 0,
                 prim_threshold: int = SHIPPED_PRIM_THRESHOLD,
                 volume_threshold: int = SHIPPED_VOLUME_THRESHOLD,
                 cmd: str = "") -> list[dict]:
    """AXIS_VOLUME: prims held CONSTANT while authored array elements grow.

    This is the sweep the I1 design could not produce, because it
    parameterized by prim count alone. Holding prims at 4 means the PRIM term
    of the shipped gate can never fire — anything the curve shows is the
    volume term or nothing.
    """
    stamp = producer_stamp(cmd or "scripts/bench_scale.py sweep_volume")
    pins = env_pins(prim_threshold, volume_threshold)
    out = []
    for elements in points:
        vol = authored_elements(prims, elements, arrays_per_prim, time_samples)
        counters, mode = measure_rung(
            prims, prim_threshold=prim_threshold,
            volume_threshold=volume_threshold,
            stage_factory=volume_stage_factory(elements, arrays_per_prim,
                                               time_samples))
        out.append(assert_record_honest({
            "schema": RECORD_SCHEMA,
            "tier": "offline",
            "mode": "count",
            "axis": AXIS_VOLUME,
            "rung": {
                "prim_count": prims,
                "arrays_per_prim": arrays_per_prim,
                "array_len": elements,
                "time_samples": time_samples,
                "authored_elements": vol,
                "shape": "array_attr_per_prim (C2 PointInstancer shape)",
            },
            "gate": {
                "prim_threshold": prim_threshold,
                "volume_threshold": volume_threshold,
                "large_mode": "reduced",
                "observed_mode": mode,
            },
            "counters": counters,
            "env_pins": pins,
            "producer": stamp,
        }))
    return out


# ── the curve (intercept + slope per counter) ───────────────────────────────

def _monotonicity(ys) -> str:
    ups = any(b > a for a, b in zip(ys, ys[1:]))
    downs = any(b < a for a, b in zip(ys, ys[1:]))
    if ups and downs:
        return "non-monotonic"
    if ups:
        return "increasing"
    if downs:
        return "decreasing"
    return "flat"


def _least_squares(xs, ys) -> tuple[float, float, float]:
    """Returns (intercept, slope, r2).

    r2 is not decoration. Several counters here are SATURATING, not linear —
    ``attrs_examined`` caps at _STAGE_HASH_VOLUME_ATTR_BUDGET (4096) — and a
    bare slope on a saturating counter reads as a growth rate it does not
    have. r2 is what lets a reader see that before quoting the slope.
    """
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return my, 0.0, 1.0
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    if ss_tot == 0:
        return intercept, slope, 1.0
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    return intercept, slope, 1.0 - ss_res / ss_tot


def fit_curve(records: list[dict], *, cmd: str = "") -> dict:
    """Emit the CURVE, not the endpoints: per counter, an intercept + a slope
    per unit of the sweep's scale term, plus the monotonicity class and the
    gate regimes observed along the way.

    Refuses to fit across records built by different builders
    (``builder_sha256``) or different axes — two scenes are not one curve.
    Where a sweep CROSSES a gate regime the fit is piecewise-meaningless by
    construction; that is reported as ``regimes``/``regime_crossed``, never
    smoothed away.
    """
    if len(records) < 3:
        raise BenchScaleError(
            f"a curve needs >= 3 scale points, got {len(records)} — two "
            f"points are an endpoint pair, not a curve")
    axes = {r["axis"] for r in records}
    if len(axes) != 1:
        raise BenchScaleError(f"refusing to fit across axes {sorted(axes)}")
    builders = {r["producer"]["builder_sha256"] for r in records}
    if len(builders) != 1:
        raise BenchScaleError(
            f"refusing to fit across builder_sha256 {sorted(builders)} — rows "
            f"from different builders describe different scenes")
    axis = records[0]["axis"]
    key = "prim_count" if axis == AXIS_PRIMS else "authored_elements"
    xs = [r["rung"][key] for r in records]
    if sorted(xs) != xs or len(set(xs)) != len(xs):
        raise BenchScaleError(
            f"scale points are not strictly increasing: {xs}")
    modes = [r["gate"]["observed_mode"] for r in records]

    counters_out = {}
    for cname in COUNTERS:
        ys = [r["counters"][cname] for r in records]
        intercept, slope, r2 = _least_squares(xs, ys)
        counters_out[cname] = {
            "intercept": round(intercept, 6),
            "slope_per_unit": round(slope, 12),
            "r2": round(r2, 6),
            "monotonic": _monotonicity(ys),
            "values": ys,
        }

    # Per-regime fits. A single slope across a gate boundary is meaningless —
    # crossing the gate REMOVES Flatten calls and ADDS traversal passes, so
    # the global fit averages two different algorithms. The within-regime fit
    # is the one a reader may quote; it is also where the monotonicity
    # contract is asserted (tests/test_bench_scale.py).
    by_regime = {}
    for regime in dict.fromkeys(modes):
        idx = [i for i, m in enumerate(modes) if m == regime]
        rxs = [xs[i] for i in idx]
        rcounters = {}
        for cname in COUNTERS:
            rys = [records[i]["counters"][cname] for i in idx]
            if len(idx) >= 2:
                ri, rs, rr2 = _least_squares(rxs, rys)
            else:
                ri, rs, rr2 = float(rys[0]), 0.0, 1.0
            rcounters[cname] = {
                "intercept": round(ri, 6),
                "slope_per_unit": round(rs, 12),
                "r2": round(rr2, 6),
                "monotonic": _monotonicity(rys),
                "values": rys,
            }
        by_regime[regime] = {
            "scale_points": rxs,
            "n_points": len(idx),
            "fit_quality": ("curve" if len(idx) >= 3 else
                            "two-point slope" if len(idx) == 2 else
                            "single point - NOT a curve"),
            "counters": rcounters,
        }

    return assert_record_honest({
        "schema": CURVE_SCHEMA,
        "tier": "offline",
        "mode": "count",
        "axis": axis,
        "scale_key": key,
        "scale_points": xs,
        "regimes": modes,
        "regime_crossed": len(set(modes)) > 1,
        "gate": records[0]["gate"],
        "rung": {k: records[0]["rung"][k] for k in
                 ("prim_count", "authored_elements", "shape")},
        "held_constant": ({"authored_elements": 0} if axis == AXIS_PRIMS
                          else {"prim_count": records[0]["rung"]["prim_count"]}),
        "counters": counters_out,
        "by_regime": by_regime,
        "env_pins": records[0]["env_pins"],
        "producer": {**records[0]["producer"],
                     "cmd": cmd or records[0]["producer"]["cmd"],
                     "producer_path": "scripts/bench_scale.py::fit_curve"},
        "_precision_limit":
            "COUNTED PROXY, NOT WALL-CLOCK. flatten_exports counts CALLS to "
            "stage.Flatten().ExportToString(); it does not price the bytes "
            "that call serializes. On the volume axis the counters move "
            "because the GATE responds, not because this instrument timed a "
            "Flatten. Reading a flat counter as 'volume is free' is the "
            "07-27 error.",
    })


def run_offline(axis: str = "both", *, prim_points=DEFAULT_PRIM_POINTS,
                volume_points=DEFAULT_VOLUME_POINTS,
                prim_threshold: int = SHIPPED_PRIM_THRESHOLD,
                volume_threshold: int = SHIPPED_VOLUME_THRESHOLD,
                cmd: str = "") -> dict:
    """The whole offline tier: sweeps + curves, in one honest envelope."""
    out = {"schema": "bench_scale/run-v1", "tier": "offline", "mode": "count",
           "sweeps": {}, "curves": {}}
    if axis in ("prims", "both"):
        recs = sweep_prims(prim_points, prim_threshold=prim_threshold,
                           volume_threshold=volume_threshold, cmd=cmd)
        out["sweeps"][AXIS_PRIMS] = recs
        out["curves"][AXIS_PRIMS] = fit_curve(recs, cmd=cmd)
    if axis in ("volume", "both"):
        recs = sweep_volume(volume_points, prim_threshold=prim_threshold,
                            volume_threshold=volume_threshold, cmd=cmd)
        out["sweeps"][AXIS_VOLUME] = recs
        out["curves"][AXIS_VOLUME] = fit_curve(recs, cmd=cmd)
    return out


# ── human-readable rendering ────────────────────────────────────────────────

_HEADLINE_COUNTERS = ("flatten_exports", "value_reads", "prim_visits",
                      "stage_traversals", "attrs_examined", "prim_state_reads")


def render(run: dict, stream=sys.stdout) -> None:
    w = stream.write
    w("\n" + "=" * 78 + "\n")
    w("  SYNAPSE scale bench - OFFLINE tier (counts only, no wall-clock)\n")
    prod = None
    for axis, recs in run["sweeps"].items():
        prod = recs[0]["producer"]
        break
    if prod:
        w(f"  producer : {prod['producer_path']}\n")
        w(f"  git      : {prod['git']}{' (dirty)' if prod['git_dirty'] else ''}"
          f"   builder={prod['builder_sha256']}\n")
        w(f"  interp   : {prod['interpreter']}   pxr={prod['pxr']}   "
          f"houdini=None (offline)\n")
    w("=" * 78 + "\n")
    for axis, curve in run["curves"].items():
        recs = run["sweeps"][axis]
        held = ", ".join(f"{k}={v:,}" for k, v in curve["held_constant"].items())
        w(f"\n  AXIS = {axis}   HELD CONSTANT: {held}   "
          f"(gate prim={curve['gate']['prim_threshold']:,} "
          f"volume={curve['gate']['volume_threshold']:,})\n")
        w(f"  {'scale':>12}  {'mode':<10}  "
          + "  ".join(f"{c[:14]:>14}" for c in _HEADLINE_COUNTERS) + "\n")
        for r in recs:
            scale = r["rung"][curve["scale_key"]]
            w(f"  {scale:>12,}  {r['gate']['observed_mode']:<10}  "
              + "  ".join(f"{r['counters'][c]:>14,}"
                          for c in _HEADLINE_COUNTERS) + "\n")
        w(f"  {'CURVE':>12}  {'':<10}  "
          + "  ".join(
              f"{curve['counters'][c]['slope_per_unit']:>14.6g}"
              for c in _HEADLINE_COUNTERS) + "   <- slope / unit\n")
        w(f"  {'':>12}  {'':<10}  "
          + "  ".join(f"{curve['counters'][c]['monotonic'][:14]:>14}"
                      for c in _HEADLINE_COUNTERS) + "\n")
        if curve["regime_crossed"]:
            w(f"  REGIME CROSSED along this axis: "
              f"{' -> '.join(curve['regimes'])}\n")
            w("  The CURVE row above averages two algorithms and is NOT "
              "quotable. Per-regime slopes:\n")
            for regime, blk in curve["by_regime"].items():
                w(f"  {regime:>12}  {blk['fit_quality']:<10}  "
                  + "  ".join(
                      f"{blk['counters'][c]['slope_per_unit']:>14.6g}"
                      for c in _HEADLINE_COUNTERS)
                  + f"   n={blk['n_points']}\n")
    w("\n  " + run["curves"][next(iter(run["curves"]))]["_precision_limit"]
      .replace(". ", ".\n  ") + "\n")
    w("\n  T1_reference: UNAVAILABLE - no absolute-seconds producer for the "
      "LLM turn at HEAD.\n")
    w("=" * 78 + "\n\n")


# ── CLI arguments, shared by both root benches ──────────────────────────────

def int_list(raw: str) -> tuple[int, ...]:
    vals = tuple(int(p) for p in str(raw).replace(" ", "").split(",") if p)
    if not vals:
        raise argparse.ArgumentTypeError("expected a comma-separated int list")
    return vals


def add_scale_args(ap: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """The scale CLI surface, identical on _benchmark_latency.py and
    _benchmark_api.py so both transports carry the same axis."""
    g = ap.add_argument_group("scale bench (scripts/bench_scale.py)")
    g.add_argument("--tier", choices=("offline", "live"), default=None,
                   help="offline = counts only, no Houdini/bridge/pxr (this "
                        "is the CI-safe tier). live = real bridge (wall-clock "
                        "allowed, build-stamped). Omit for the legacy run.")
    g.add_argument("--axis", choices=("prims", "volume", "both"),
                   default="both",
                   help="volume = authored array elements with prims held "
                        "constant (the H10 axis); prims = prim count with "
                        "volume held at zero")
    g.add_argument("--scale", type=int_list, default=None, metavar="N,N,N",
                   help=f"prim-count sweep points "
                        f"(default {','.join(map(str, DEFAULT_PRIM_POINTS))})")
    g.add_argument("--volume", type=int_list, default=None, metavar="N,N,N",
                   help=f"authored array LENGTH per attribute, swept with "
                        f"prims held at {VOLUME_AXIS_PRIMS} "
                        f"(default {','.join(map(str, DEFAULT_VOLUME_POINTS))})")
    g.add_argument("--prim-threshold", type=int,
                   default=SHIPPED_PRIM_THRESHOLD,
                   help="SYNAPSE_STAGE_HASH_PRIM_THRESHOLD pin for the sweep")
    g.add_argument("--volume-threshold", type=int,
                   default=SHIPPED_VOLUME_THRESHOLD,
                   help="SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD pin for the sweep")
    g.add_argument("--json-out", default=None, metavar="PATH",
                   help="write the machine record here ('-' = stdout)")
    return ap


def run_from_args(args, cmd: str) -> int:
    """Shared --tier dispatch for both root benches. Returns an exit code."""
    if args.tier != "offline":
        raise BenchScaleError(
            "run_from_args only serves the offline tier; the live tier is the "
            "caller's transport arm")
    run = run_offline(
        args.axis,
        prim_points=args.scale or DEFAULT_PRIM_POINTS,
        volume_points=args.volume or DEFAULT_VOLUME_POINTS,
        prim_threshold=args.prim_threshold,
        volume_threshold=args.volume_threshold,
        cmd=cmd)
    if args.json_out:
        blob = json.dumps(run, indent=1, sort_keys=True)
        if args.json_out == "-":
            print(blob)
        else:
            Path(args.json_out).write_text(blob, encoding="utf-8")
            print(f"  wrote {args.json_out}")
    else:
        render(run)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="bench_scale",
        description="Scale-parameterized cost core (offline tier). "
                    "Counts only - never wall-clock.")
    add_scale_args(ap)
    args = ap.parse_args(argv)
    args.tier = "offline"
    try:
        return run_from_args(
            args,
            "python scripts/bench_scale.py " + " ".join(argv or sys.argv[1:]))
    except BenchScaleError as exc:
        # A refusal is a first-class outcome, not a crash. Say what was
        # refused and why, and emit no numbers.
        print(f"\n  REFUSED: {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
