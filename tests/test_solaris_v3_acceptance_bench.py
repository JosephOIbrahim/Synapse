"""Synthetic BENCH controls; these do not qualify Solaris product gates."""
import hashlib
import json
from types import SimpleNamespace

import contextlib
import io
import unittest
from unittest.mock import patch

from harness.solaris_v3 import bench


def pinned():
    return bench.Benchmark(frame=7, seed=41, engine="synthetic-test",
                           assets={"synthetic": hashlib.sha256(b"fixture").hexdigest()})


def test_headless_defaults_are_unmeasured():
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert bench.main([]) == 0
    report = json.loads(output.getvalue())
    assert report["kind"] == "BENCH"
    for metric in report["metrics"].values():
        assert metric["status"] == "UNMEASURED"
        assert metric["n"] == 0
        assert metric["min"] is metric["median"] is metric["p95"] is None


def test_distribution_is_independently_hand_computed():
    # Sorted 1..20: min=1; central pair 10,11 averages 10.5;
    # empirical CDF first reaches 95% at observation 19 (19/20).
    assert bench.distribution(reversed(range(1, 21))) == {
        "n": 20, "min": 1, "median": 10.5, "p95": 19}
    assert bench.distribution([8]) == {"n": 1, "min": 8, "median": 8, "p95": 8}


def test_invalid_samples_refuse():
    for value in [True, "3", -1, float("nan"), float("inf")]:
        with unittest.TestCase().assertRaises(ValueError):
            bench.distribution([value])


def test_pins_and_provenance_are_required():
    with unittest.TestCase().assertRaisesRegex(ValueError, "frame"):
        bench.Benchmark().record("build_to_stage_s", 2, source="synthetic")
    with unittest.TestCase().assertRaisesRegex(ValueError, "provenance"):
        pinned().record("build_to_stage_s", 2, source="")


def test_failed_or_incomplete_operation_never_records_latency():
    measurement = pinned()
    assert measurement.measure("render_cold_s", lambda: False, source="synthetic") is False
    with unittest.TestCase().assertRaises(RuntimeError):
        measurement.measure("render_cold_s", lambda: (_ for _ in ()).throw(RuntimeError()), source="synthetic")
    assert measurement.report()["metrics"]["render_cold_s"]["status"] == "UNMEASURED"


def test_successful_endpoint_and_cold_warm_separation():
    measurement = pinned()
    ticks = iter([10, 14, 25, 26])
    measurement.measure("render_cold_s", lambda: True, source="synthetic", clock=lambda: next(ticks))
    measurement.measure("render_warm_s", lambda: True, source="synthetic", clock=lambda: next(ticks))
    report = measurement.report()["metrics"]
    assert report["render_cold_s"]["median"] == 4
    assert report["render_warm_s"]["median"] == 1
    assert report["build_to_stage_s"]["status"] == "UNMEASURED"


def test_walk_time_is_not_completion():
    measurement = pinned()
    with unittest.TestCase().assertRaisesRegex(ValueError, "completed"):
        measurement.record("walk_completion_s", 40, source="manual")
    for elapsed, completed in [(40, False), (900, True), (901, True)]:
        measurement.record("walk_completion_s", elapsed, source="manual", completed=completed)
    assert [s["within_fifteen_minutes"] for s in measurement.samples["walk_completion_s"]] == [False, True, False]


def test_peak_sampling_requires_stable_identity_and_complete_reads():
    measurement = pinned()
    measurement.record_peaks([
        {"pid": 12, "rss_bytes": 30, "gpu_uuid": "gpu", "vram_used_bytes": None},
        {"pid": 12, "rss_bytes": 25, "gpu_uuid": "gpu", "vram_used_bytes": 60},
    ], source="synthetic")
    report = measurement.report()["metrics"]
    assert report["peak_memory_bytes"]["median"] == 30
    assert report["peak_vram_bytes"]["status"] == "UNMEASURED"
    with unittest.TestCase().assertRaisesRegex(ValueError, "identity"):
        measurement.record_peaks([{"pid": 1, "rss_bytes": 2}, {"pid": 2, "rss_bytes": 3}], source="synthetic")


def test_vram_probe_queries_used_not_total_and_converts_mib():
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="gpu-other, 100\ngpu-chosen, 3\n", stderr="")
    with patch.object(bench.shutil, "which", return_value="nvidia-smi"), patch.object(bench.subprocess, "run", run):
        reading = bench.memory_sample(-1, "gpu-chosen")
    assert reading["vram_used_bytes"] == 3 * 1024 * 1024
    assert calls[0][0][1] == "--query-gpu=uuid,memory.used"
    assert calls[0][1]["timeout"] == 5


def test_absent_gpu_is_unknown_not_zero():
    with patch.object(bench.shutil, "which", return_value=None):
        reading = bench.memory_sample(-1, "gpu")
    assert reading["vram_used_bytes"] is None
    assert reading["reasons"]


def test_condition_and_report_mutations_do_not_relabel_samples():
    assets = {"synthetic": hashlib.sha256(b"fixture").hexdigest()}
    measurement = bench.Benchmark(frame=7, seed=41, engine="synthetic", assets=assets)
    measurement.record("build_to_stage_s", 2, source="synthetic")
    assets["synthetic"] = "changed"
    report = measurement.report()
    report["conditions"]["frame"] = 500
    report["metrics"]["build_to_stage_s"]["samples"][0]["value"] = 99
    assert measurement.report()["conditions"]["frame"] == 7
    assert measurement.report()["conditions"]["asset_set"]["synthetic"] != "changed"
    assert measurement.report()["metrics"]["build_to_stage_s"]["samples"][0]["value"] == 2


def load_tests(loader, tests, pattern):
    # Real unittest execution of the same functions; pytest also collects them.
    return unittest.TestSuite(unittest.FunctionTestCase(value) for name, value
                              in globals().items() if name.startswith("test_"))
