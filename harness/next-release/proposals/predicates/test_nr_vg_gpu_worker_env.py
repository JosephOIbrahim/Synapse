"""Closure predicate for NR-VG-GPU-WORKER-ENV (PROPOSED amendment; not in graph.json).

Flips green only when harness/vision/gpu_worker_env/worker_env_contract.json is
committed and names CPython 3.12.10, an OpenImageIO cp312 win_amd64 wheel, a NumPy 2.x
pin, and the committed build-lock receipt by sha256 (R4); the GPU requirements file it
names installs no opencv-python* package (the custom cv2 never shares a venv with the
stock wheel); the three shipped recipe files (retina/requirements.txt,
retina/setup_venv.py, retina/setup_venv.ps1) match, by sha256, the text an R4 review
signed off in the contract (no longer documenting a hython seed or a cp314 OIIO
wheel); and no non-comment requirement line pins a cp314 wheel.

Red today: the contract is not committed (marker below), and every test reaches that
marker first. Separately, the shipped recipe still documents a hython seed and names a
cp314 wheel, which R4 rules out (ADR-0002 "Consequences of R1-R4", item 3).

Static text reads only. It never creates a venv, runs pip, imports cv2 or OIIO,
touches a GPU, launches Houdini or uses the network.
"""
from __future__ import annotations

import hashlib
import json
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
MARKER = ("NR-VG-GPU-WORKER-ENV RED: no committed R4 worker-runtime contract "
          "harness/vision/gpu_worker_env/worker_env_contract.json")
CONTRACT = "harness/vision/gpu_worker_env/worker_env_contract.json"
BUILD_LOCK = "harness/vision/gpu_build_lock/build_lock_receipt.json"
RECIPE = ("retina/requirements.txt", "retina/setup_venv.py", "retina/setup_venv.ps1")


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
    c = _contract()
    assert isinstance(c, dict) and c, "the committed contract is empty"


def test_contract_names_the_r4_runtime():
    c = _contract()
    assert c.get("python") == "3.12.10", "R4: worker interpreter is not CPython 3.12.10"
    wheel = str(c.get("oiio_wheel", ""))
    assert wheel.lower().startswith("openimageio") and "cp312" in wheel and "win_amd64" in wheel, \
        "R4: OIIO must be the isolated cp312 win_amd64 wheel"
    assert str(c.get("numpy", "")).startswith("2."), "NumPy must be pinned inside >=2,<3"


def test_contract_pins_the_build_lock_by_digest():
    c = _contract()
    assert _committed(BUILD_LOCK), f"build-lock receipt {BUILD_LOCK} is not committed"
    digest = hashlib.sha256((ROOT / BUILD_LOCK).read_bytes()).hexdigest()
    assert c.get("build_lock_receipt_sha256") == digest, "contract does not pin the committed build-lock receipt"


def test_gpu_requirements_install_no_stock_opencv():
    rel = _contract().get("gpu_requirements")
    assert rel and _committed(rel), "the GPU requirements file named by the contract is not committed"
    lines = [ln.strip().lower() for ln in (ROOT / rel).read_text(encoding="utf-8").splitlines()]
    bad = [ln for ln in lines if ln and not ln.startswith("#") and ln.startswith("opencv")]
    assert not bad, f"GPU requirements install a stock OpenCV wheel: {bad}"


def test_shipped_recipe_no_longer_conflicts_with_r4():
    # Red today through the contract's own marker, not through a token search.
    c = _contract()
    # Whether the recipe's prose still documents a hython seed is a reviewed judgement, not
    # a token gate (a compliant line such as "never seed from hython (R4)" must not stay
    # red): the contract pins the exact reviewed text of each recipe file by sha256.
    pins = c.get("recipe_review_sha256", {})
    for rel in RECIPE:
        assert _committed(rel), f"{rel} is not committed"
        digest = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        assert pins.get(rel) == digest, f"{rel} differs from the text the R4 review signed off"
    # The one mechanical check: no requirement line (comments excluded) pins a cp314 wheel.
    req = (ROOT / "retina/requirements.txt").read_text(encoding="utf-8").lower().splitlines()
    bad = [n for n, ln in enumerate(req, 1) if ln.strip() and not ln.strip().startswith("#") and "cp314" in ln]
    assert not bad, f"retina/requirements.txt pins a cp314 wheel at lines {bad}"
