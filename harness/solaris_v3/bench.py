"""Solaris v3 measurement scaffolding. No host imports, renders or inferred data.

Run with no arguments for an entirely UNMEASURED report. Measured samples need
explicit conditions and provenance. p95 is the empirical nearest-rank quantile.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
import statistics
import subprocess
import time
from pathlib import Path


METRICS = {
    "build_to_stage_s": "seconds: request start to verified stage availability",
    "render_cold_s": "seconds: approved cold job start to terminal output validation",
    "render_warm_s": "seconds: approved warm job start to terminal output validation",
    "peak_memory_bytes": "bytes: maximum observed process RSS in the measured interval",
    "peak_vram_bytes": "bytes: maximum observed device memory.used in the measured interval",
    "cancellation_s": "seconds: cancellation requested to confirmed terminal job state",
    "walk_completion_s": "seconds: manual walk timer; completion recorded separately",
}


def distribution(samples):
    values = list(samples)
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("samples must be finite nonnegative numbers")
        if not math.isfinite(value) or value < 0:
            raise ValueError("samples must be finite nonnegative numbers")
    values.sort()
    if not values:
        return {"n": 0, "min": None, "median": None, "p95": None}
    return {"n": len(values), "min": values[0], "median": statistics.median(values),
            "p95": values[math.ceil(0.95 * len(values)) - 1]}


class Benchmark:
    def __init__(self, *, frame=None, seed=None, engine=None, assets=None):
        self._conditions = copy.deepcopy({"frame": frame, "seed": seed, "engine": engine,
                                          "asset_set": assets})
        self.samples = {key: [] for key in METRICS}

    @property
    def conditions(self):
        return copy.deepcopy(self._conditions)

    def _require_pins(self):
        frame, seed = self.conditions["frame"], self.conditions["seed"]
        if isinstance(frame, bool) or not isinstance(frame, (int, float)) or not math.isfinite(frame):
            raise ValueError("measured samples require a finite pinned frame")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("measured samples require an integer pinned seed")
        if not isinstance(self.conditions["engine"], str) or not self.conditions["engine"].strip():
            raise ValueError("measured samples require a pinned engine")
        assets = self.conditions["asset_set"]
        if not isinstance(assets, dict) or not assets or not all(
            isinstance(k, str) and k and isinstance(v, str) and len(v) == 64
            and all(c in "0123456789abcdef" for c in v) for k, v in assets.items()
        ):
            raise ValueError("measured samples require asset names and SHA-256 digests")

    def record(self, metric, value, *, source, completed=None):
        if metric not in self.samples:
            raise ValueError(f"unknown metric: {metric}")
        self._require_pins()
        distribution([value])
        if not isinstance(source, str) or not source.strip():
            raise ValueError("a measurement requires source/log provenance")
        sample = {"value": value, "source": source}
        if metric == "walk_completion_s":
            if not isinstance(completed, bool):
                raise ValueError("manual walk needs explicit completed true/false")
            sample.update(completed=completed, within_fifteen_minutes=completed and value <= 15 * 60)
        self.samples[metric].append(sample)

    def measure(self, metric, operation, *, source, clock=time.perf_counter):
        """Time a caller-supplied bounded operation through its verified endpoint.

        The callback must return True only after that endpoint is established.
        Exceptions and incomplete jobs record no latency. No cook-time adapter.
        """
        if metric not in {"build_to_stage_s", "render_cold_s", "render_warm_s", "cancellation_s"}:
            raise ValueError("measure accepts only operation latency metrics")
        self._require_pins()
        started = clock()
        if operation() is not True:
            return False
        self.record(metric, clock() - started, source=source)
        return True

    def record_peaks(self, readings, *, source):
        """A repeat's sampled peaks, never hardware capacity or an inferred maximum.

        Readings must name the same process and GPU UUID throughout. Missing
        samples invalidate that metric for this repeat; other metrics survive.
        """
        readings = list(readings)
        if not readings:
            return
        for field, metric, identity in (
            ("rss_bytes", "peak_memory_bytes", "pid"),
            ("vram_used_bytes", "peak_vram_bytes", "gpu_uuid"),
        ):
            values = [r.get(field) for r in readings]
            identities = [r.get(identity) for r in readings]
            if any(v is None for v in values) or any(v is None for v in identities):
                continue
            if any(v != identities[0] for v in identities):
                raise ValueError("memory samples changed process/device identity")
            distribution(values)
            self.record(metric, max(values), source=source)

    def report(self):
        return {
            "schema_version": 1, "kind": "BENCH", "conditions": self.conditions,
            "quantile_method": "nearest-rank: sorted[ceil(0.95*n)-1]",
            "limitations": ["Sampled memory peaks may miss spikes between samples.",
                            "Device VRAM includes other processes; it is not per-render allocation.",
                            "BENCH measurements do not promote GATE rows."],
            "metrics": {key: {"status": "MEASURED" if values else "UNMEASURED",
                              "definition": METRICS[key], "samples": copy.deepcopy(values),
                              **distribution(v["value"] for v in values)}
                        for key, values in self.samples.items()},
        }


def memory_sample(pid, gpu_uuid=None):
    """Bounded read-only OS probe, following host/cache_host_probe.py's tool path.

    That existing helper measures memory.total (capacity), so cannot measure a
    peak. Here memory.used is queried explicitly. No host or GUI access.
    """
    result = {"pid": pid, "gpu_uuid": gpu_uuid, "rss_bytes": None,
              "vram_used_bytes": None, "observed_at_ns": time.time_ns(), "reasons": []}
    try:
        import psutil
        result["rss_bytes"] = psutil.Process(pid).memory_info().rss
    except (ImportError, OSError) as exc:
        result["reasons"].append(f"RSS unavailable: {exc}")
    except Exception as exc:
        # psutil.NoSuchProcess/AccessDenied are optional dependency exceptions.
        result["reasons"].append(f"RSS unavailable: {type(exc).__name__}: {exc}")
    tool = shutil.which("nvidia-smi")
    if not tool or not gpu_uuid:
        result["reasons"].append("VRAM unavailable: nvidia-smi and an explicit GPU UUID are required")
        return result
    try:
        proc = subprocess.run([tool, "--query-gpu=uuid,memory.used", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, timeout=5, check=False)
        if proc.returncode:
            raise ValueError(f"nvidia-smi exited {proc.returncode}: {proc.stderr.strip()}")
        for line in proc.stdout.splitlines():
            uuid, used = (part.strip() for part in line.split(","))
            if uuid == gpu_uuid:
                value = float(used) * 1024 * 1024
                distribution([value])
                result["vram_used_bytes"] = int(value)
                break
        if result["vram_used_bytes"] is None:
            raise ValueError("requested GPU UUID not observed")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result["reasons"].append(f"VRAM unavailable: {exc}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, help="JSON with conditions and explicit samples")
    args = parser.parse_args(argv)
    bench = Benchmark()
    if args.samples:
        data = json.loads(args.samples.read_text(encoding="utf-8"))
        conditions = data["conditions"]
        bench = Benchmark(frame=conditions["frame"], seed=conditions["seed"],
                          engine=conditions["engine"], assets=conditions["asset_set"])
        for sample in data["samples"]:
            bench.record(**sample)
    print(json.dumps(bench.report(), indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
