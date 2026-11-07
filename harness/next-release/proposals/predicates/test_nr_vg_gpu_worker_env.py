"""Closure predicate for NR-VG-GPU-WORKER-ENV (PROPOSED amendment; not in graph.json).

Flips green only when harness/vision/gpu_worker_env/worker_env_contract.json is
committed and names CPython 3.12.10, an OpenImageIO cp312 win_amd64 wheel, a NumPy 2.x
pin, and the committed build-lock receipt by sha256 (R4); the GPU requirements file it
names installs no opencv-python* package (the custom cv2 never shares a venv with the
stock wheel); and the three shipped recipe files (retina/requirements.txt,
retina/setup_venv.py, retina/setup_venv.ps1) no longer document a hython seed or a
cp314 OIIO wheel.

Red today: the contract is not committed (marker below). Independently, the shipped
recipe still documents a hython seed and names a cp314 wheel, which R4 rules out.

Static text reads only. It never creates a venv, runs pip, imports cv2 or OIIO,
touches a GPU, launches Houdini or uses the network.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
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
    assert isinstance(_contract(), dict)


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
    conflicts = []
    for rel in RECIPE:
        text = (ROOT / rel).read_text(encoding="utf-8").lower() if (ROOT / rel).is_file() else ""
        for n, line in enumerate(text.splitlines(), 1):
            if "hython" in line or "cp314" in line:
                conflicts.append(f"{rel}:{n}")
    assert not conflicts, "R4 conflict (hython seed or cp314 wheel) at " + ", ".join(conflicts)
