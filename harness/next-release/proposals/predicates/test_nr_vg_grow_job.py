"""Closure predicate for NR-VG-GROW-JOB (PROPOSED amendment; not in graph.json).

Flips green only when harness/vision/grow_job/grow_job_contract.json is committed and
records: publication order products -> manifest -> completion marker; the tests that
reject a stale completion marker and a partial product; a separate-process sandbox
with zero production scene writes and the evidence for it; a Stop that cancels owned
work, keeps the last complete candidate and marks incomplete products unusable;
resource admission (one GPU-heavy job at a time) with a tested refusal; Joe's ruling
on who edits the registry and panel files (OD-06); and the node's three files
(python/synapse/server/handlers_grow.py, python/synapse/panel/grow_panel.py,
tests/test_grow_job_contract.py) are committed.

Red today: the contract is not committed (marker below).

Reads committed files only. It never starts a job, launches Houdini, renders,
touches a GPU or uses the network.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MARKER = ("NR-VG-GROW-JOB RED: no committed Grow job contract "
          "harness/vision/grow_job/grow_job_contract.json")
CONTRACT = "harness/vision/grow_job/grow_job_contract.json"
FILES = ("python/synapse/server/handlers_grow.py", "python/synapse/panel/grow_panel.py",
         "tests/test_grow_job_contract.py")


def _committed(rel: str) -> bool:
    if not (ROOT / rel).is_file():
        return False
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", rel],
                       capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def _contract() -> dict:
    if not _committed(CONTRACT):
        raise AssertionError(MARKER)
    return json.loads((ROOT / CONTRACT).read_text(encoding="utf-8"))


def test_contract_is_committed():
    assert isinstance(_contract(), dict)


def test_atomic_publication_and_stale_rejection():
    p = _contract().get("publication", {})
    assert p.get("order") == ["products", "manifest", "completion_marker"], "completion marker must publish last"
    assert p.get("stale_marker_rejected_test") and p.get("partial_product_rejected_test"), \
        "no tests for stale-marker and partial-product rejection"


def test_sandbox_never_writes_production():
    s = _contract().get("sandbox", {})
    assert s.get("process") == "separate", "the sandbox must be a separate process"
    assert s.get("production_scene_writes") == 0 and s.get("evidence_ref"), "production scene writes not shown to be zero"


def test_stop_and_admission():
    c = _contract()
    st = c.get("stop", {})
    assert st.get("cancels_owned_work") is True and st.get("keeps_last_complete") is True \
        and st.get("marks_incomplete_unusable") is True, "Stop semantics incomplete"
    ad = c.get("admission", {})
    assert ad.get("one_gpu_heavy_job") is True and ad.get("refusal_tested") is True, "resource admission not tested"


def test_registration_ruling_and_files():
    assert _contract().get("registration_ruling"), "no owner ruling on the registry and panel files (OD-06)"
    for rel in FILES:
        assert _committed(rel), f"{rel} is not committed"
