"""Closure predicate for NR-GPU-QUALIFICATION (DRAFT carried inside the PROPOSED amendment).

Proposed to replace `test -f harness/next-release/gpu_qualification.json`. It lands only
in the commit where Joe merges the predicate change, at the path that change names.

Flips green only when harness/next-release/gpu_qualification.json is committed and:
- pins the committed build-lock receipt harness/vision/gpu_build_lock/build_lock_receipt.json
  by sha256, so the qualified artifact is the one built under E:/OpenCV5.1_Prep (R3);
- records each R2 change-mask operation (absdiff, threshold, morphology_open,
  morphology_close) dispatched on cuda, with a backend witness naming the loaded
  modules and cv2.__file__ (R2);
- pins a committed, frozen profile harness/next-release/gpu/qualification_profile.json by
  sha256, and for every fixture the profile lists records a GPU mask digest equal to the
  profile's expected digest and to the cpu_reference digest. The fixture set and the
  identical-mask-bytes criterion are G0-PROPOSED (G0 receipt, slice 2; report 02-ops
  section 7), not ruled; the NaN-in-luma fixture is INFERENCE (a threshold-parity hazard);
- records a cpu_reference identity equal to the one the profile records as ruled by Joe
  (OD-10, open), never the user-site cv2 4.12.0.

Red today: the qualification receipt is not committed (marker below). Whether the
masked meanStdDev census is replaced or kept beside this chain is ADR-0002 decision 14
(OD-22, open); this draft qualifies the change-mask chain only.

Reads committed files only (JSON, sha256). It never imports cv2, touches a GPU,
builds, installs, launches Houdini or uses the network.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    """Find the repository root from the working directory, never from this file's
    location, so the predicate keeps working wherever it is moved (review G1)."""
    here = Path.cwd().resolve()
    for p in (here, *here.parents):
        if (p / ".git").exists() and (p / "harness" / "next-release" / "graph.json").is_file():
            return p
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=60)
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip()).resolve()
    raise AssertionError("repository root not found: run this predicate from inside the SYNAPSE checkout")


ROOT = _repo_root()
MARKER = ("NR-GPU-QUALIFICATION RED: no committed qualification receipt "
          "harness/next-release/gpu_qualification.json")
RECEIPT = "harness/next-release/gpu_qualification.json"
PROFILE = "harness/next-release/gpu/qualification_profile.json"
BUILD_LOCK = "harness/vision/gpu_build_lock/build_lock_receipt.json"
R2_OPS = ("absdiff", "threshold", "morphology_open", "morphology_close")
# G0-proposed fixtures (G0 receipt slice 2; 02-ops section 7). Not ruled.
G0_PROPOSED_FIXTURES = {
    "edges_and_corners", "diff_at_threshold", "diff_one_ulp_below", "diff_one_ulp_above",
    "non_contiguous_odd_stride", "size_not_multiple_of_16_or_32", "empty_change_set",
}
# INFERENCE: a NaN in a luma plane is a CPU-versus-CUDA threshold-parity hazard.
INFERENCE_FIXTURES = {"nan_in_luma_plane"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _committed(rel: str) -> bool:
    if not (ROOT / rel).is_file():
        return False
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", rel],
                       capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def _sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def _receipt() -> dict:
    if not _committed(RECEIPT):
        raise AssertionError(MARKER)
    return json.loads((ROOT / RECEIPT).read_text(encoding="utf-8"))


def _profile(r: dict) -> dict:
    assert _committed(PROFILE), f"frozen qualification profile {PROFILE} is not committed"
    assert r.get("profile_sha256") == _sha(PROFILE), "receipt does not pin the frozen profile"
    return json.loads((ROOT / PROFILE).read_text(encoding="utf-8"))


def test_qualification_receipt_is_committed():
    r = _receipt()
    assert isinstance(r, dict) and r, "the committed receipt is empty"


def test_artifact_is_the_locked_e_build():
    r = _receipt()
    assert _committed(BUILD_LOCK), f"build-lock receipt {BUILD_LOCK} is not committed"
    assert r.get("build_lock_sha256") == _sha(BUILD_LOCK), "R3: receipt does not pin the committed build-lock receipt"


def test_r2_operations_dispatched_on_cuda_with_witness():
    w = _receipt().get("backend_witness", {})
    for op in R2_OPS:
        assert w.get("dispatch", {}).get(op) == "cuda", f"R2: {op} did not dispatch on cuda"
    assert w.get("loaded_modules") and w.get("cv2_file"), "backend witness lists no loaded modules or cv2.__file__"


def test_fixture_masks_match_the_frozen_profile():
    r = _receipt()
    p = _profile(r)
    expected = p.get("fixtures", {})
    missing = (G0_PROPOSED_FIXTURES | INFERENCE_FIXTURES) - set(expected)
    assert not missing, f"profile lacks fixtures: {sorted(missing)}"
    got = r.get("fixtures", {})
    for fid, exp in expected.items():
        want = str(exp.get("expected_mask_sha256", ""))
        assert HEX64.match(want), f"profile fixture {fid} has no expected mask digest"
        rec = got.get(fid, {})
        assert rec.get("gpu_mask_sha256") == want, f"fixture {fid}: GPU mask differs from the frozen expectation"
        assert rec.get("cpu_mask_sha256") == want, f"fixture {fid}: cpu_reference mask differs from the frozen expectation"


def test_cpu_reference_identity_is_ruled():
    r = _receipt()
    ruling = _profile(r).get("cpu_reference_ruling", {})
    assert ruling.get("by") == "Joe" and ruling.get("date") and ruling.get("identity"), \
        "cpu_reference identity not ruled (OD-10)"
    ident = str(r.get("cpu_reference", {}).get("identity", ""))
    assert ident == ruling["identity"], "receipt cpu_reference differs from the ruled identity"
    assert "4.12.0" not in ident, "the user-site cv2 4.12.0 is never the oracle"
