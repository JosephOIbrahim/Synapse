"""Closure predicate for NR-VG-GPU-CANARY (PROPOSED amendment; not in graph.json).

Flips green only when harness/vision/gpu_canary/canary_receipt.json is committed and
records: a reference to Joe's definition of demo v1 with demo v1 complete; Joe's
approval with a date; a non-empty list of approved scenes, none of them production;
at least one run whose backend witness shows each R2 operation (absdiff, threshold,
morphology_open, morphology_close) dispatched on cuda with the loaded modules listed;
render, cancel and contention probe results; and a disable-and-rollback demonstration
with before and after evidence.

Red today: the receipt is not committed (marker below).

Reads committed files only. It never runs the worker, a render or a GPU call,
launches Houdini or uses the network.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MARKER = ("NR-VG-GPU-CANARY RED: no committed canary receipt "
          "harness/vision/gpu_canary/canary_receipt.json")
RECEIPT = "harness/vision/gpu_canary/canary_receipt.json"
R2_OPS = ("absdiff", "threshold", "morphology_open", "morphology_close")


def _committed(rel: str) -> bool:
    if not (ROOT / rel).is_file():
        return False
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", rel],
                       capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def _receipt() -> dict:
    if not _committed(RECEIPT):
        raise AssertionError(MARKER)
    return json.loads((ROOT / RECEIPT).read_text(encoding="utf-8"))


def test_canary_receipt_is_committed():
    assert isinstance(_receipt(), dict)


def test_demo_v1_and_approval():
    r = _receipt()
    d = r.get("demo_v1", {})
    assert d.get("definition_ref") and d.get("complete") is True, "demo v1 is undefined or incomplete"
    a = r.get("approval", {})
    assert a.get("by") == "Joe" and a.get("date"), "no canary approval by Joe"


def test_scenes_are_approved_and_non_production():
    scenes = _receipt().get("scenes", [])
    assert scenes and all(s.get("production") is False and s.get("approved") is True for s in scenes), \
        "canary scenes must be approved and non-production"


def test_each_run_witnesses_cuda_dispatch():
    runs = _receipt().get("runs", [])
    assert runs, "no canary runs"
    for run in runs:
        w = run.get("backend_witness", {})
        for op in R2_OPS:
            assert w.get("dispatch", {}).get(op) == "cuda", f"{op} did not dispatch on cuda"
        assert w.get("loaded_modules"), "backend witness lists no loaded modules"


def test_probes_and_rollback_demonstrated():
    r = _receipt()
    probes = r.get("probes", {})
    for p in ("render", "cancel", "contention"):
        assert probes.get(p, {}).get("result"), f"no {p} probe result"
    rb = r.get("disable_and_rollback", {})
    assert rb.get("demonstrated") is True and rb.get("before_ref") and rb.get("after_ref"), \
        "disable and rollback not demonstrated with before and after evidence"
