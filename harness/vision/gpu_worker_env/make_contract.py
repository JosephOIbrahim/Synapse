#!/usr/bin/env python
"""Write the R4 worker-runtime contract for NR-VG-GPU-WORKER-ENV.

Output: ``harness/vision/gpu_worker_env/worker_env_contract.json``, the record the
closure predicate ``harness/next-release/proposals/predicates/test_nr_vg_gpu_worker_env.py``
reads. It names the GPU worker runtime ruled by R4 (owner ruling 2026-11-07,
ADR-0002): CPython 3.12.10, NumPy 2.4.4 and the isolated cp312 win_amd64
OpenImageIO 3.1.15.0 wheel (both hash-pinned in ``requirements-gpu.txt``), with
cv2 supplied only by the locked custom OpenCV 5.1 CUDA build. It pins, by sha256
of the bytes on disk (the same bytes the predicate hashes):

* the build-lock receipt ``harness/vision/gpu_build_lock/build_lock_receipt.json``;
* the GPU requirements file;
* the three RETINA recipe files, as the R4 review signed them off.

Run it from the checkout after the build-lock receipt is committed::

    python harness/vision/gpu_worker_env/make_contract.py --cuda-path-at-build "<CUDA_PATH at build>"

It exits 2 and writes nothing when the receipt is absent (checked first, before
any git call), when the receipt contradicts R4 (binding interpreter not 3.12.10,
a different worker venv, or cv2 outside it), when the GPU requirements file drops
a pin or installs an opencv-python* package, when the CUDA path is missing,
relative or names a user folder, or when any pinned input is untracked or differs
from HEAD (a pin of uncommitted text would pass the predicate on this checkout
only). The output carries no timestamp, so a re-run over the same inputs is
byte-identical.

Standard library only. It reads files and runs read-only git queries; it never
creates a venv, runs pip, imports cv2 or OIIO, or touches a GPU.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CONTRACT = "harness/vision/gpu_worker_env/worker_env_contract.json"
BUILD_LOCK = "harness/vision/gpu_build_lock/build_lock_receipt.json"
GPU_REQUIREMENTS = "harness/vision/gpu_worker_env/requirements-gpu.txt"
RECIPE = ("retina/requirements.txt", "retina/setup_venv.py", "retina/setup_venv.ps1")

# The R4 runtime as the orchestrator record of 2026-11-08 fixed it: a fresh
# CPython 3.12.10 venv, filled with pip --no-index from these hash-checked wheels.
PYTHON = "3.12.10"
PYTHON_BASE_SHA256 = "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a"
NUMPY = "2.4.4"
NUMPY_WHEEL = "numpy-2.4.4-cp312-cp312-win_amd64.whl"
NUMPY_WHEEL_SHA256 = "b5f0362dc928a6ecd9db58868fca5e48485205e3855957bdedea308f8672ea4a"
OIIO = "3.1.15.0"
OIIO_WHEEL = "openimageio-3.1.15.0-cp312-cp312-win_amd64.whl"
OIIO_WHEEL_SHA256 = "ef6ee4f6c0480cf9ec657e3fc83fd6779aac7462a0d14d3ed35e2d23610e8c04"
# The declared GPU worker venv, under the ruled build root (R3).
WORKER_VENV = "E:/OpenCV5.1_Prep/02_OpenCV_Setup/worker/py312-cuda133-worker"


class ContractError(RuntimeError):
    """A refusal: the contract would pin something R4 or the predicate rules out."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _norm(path: object) -> str:
    return str(path or "").strip().replace("\\", "/").rstrip("/").lower()


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ContractError(f"cannot run git to verify the committed state: {exc}") from exc


def uncommitted(root: Path, rels) -> list[str]:
    """Pinned inputs that are not committed as-is: untracked, or different from HEAD.

    The tracked test is the predicate's own (``git ls-files --error-unmatch``);
    the content test diffs the working tree against HEAD. Raises ContractError
    when git cannot answer.
    """
    rels = list(rels)
    bad = []
    for rel in rels:
        r = _git(root, "ls-files", "--error-unmatch", "--", rel)
        if r.returncode == 1:
            bad.append(f"{rel} (not tracked)")
        elif r.returncode != 0:
            raise ContractError(f"git cannot verify {rel}: {r.stderr.strip() or r.returncode}")
    if bad:
        return bad
    r = _git(root, "diff", "--name-only", "HEAD", "--", *rels)
    if r.returncode != 0:
        raise ContractError(f"git diff against HEAD failed: {r.stderr.strip() or r.returncode}")
    return [f"{line.strip()} (differs from HEAD)" for line in r.stdout.splitlines() if line.strip()]


def _read_receipt(root: Path) -> tuple[dict, str]:
    path = root / BUILD_LOCK
    if not path.is_file():
        raise ContractError(
            f"build-lock receipt {BUILD_LOCK} is absent; run this only after "
            "NR-VG-GPU-BUILD-LOCK has committed it"
        )
    raw = path.read_bytes()
    try:
        receipt = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"build-lock receipt is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(receipt, dict):
        raise ContractError("build-lock receipt is not a JSON object")
    return receipt, hashlib.sha256(raw).hexdigest()


def _check_receipt(receipt: dict) -> None:
    """Cross-check the receipt fields the build-lock predicate defines against R4."""
    py = receipt.get("python")
    version = py.get("version") if isinstance(py, dict) else None
    if version != PYTHON:
        raise ContractError(f"build-lock receipt python.version is {version!r}, not {PYTHON} (R4)")
    inst = receipt.get("install")
    inst = inst if isinstance(inst, dict) else {}
    venv = _norm(inst.get("worker_venv"))
    if venv != _norm(WORKER_VENV):
        raise ContractError(
            f"build-lock receipt install.worker_venv is {inst.get('worker_venv')!r}, "
            f"not the declared worker venv {WORKER_VENV}"
        )
    if not _norm(inst.get("cv2_file")).startswith(venv + "/"):
        raise ContractError(
            f"build-lock receipt install.cv2_file {inst.get('cv2_file')!r} is not inside the worker venv"
        )


def _check_gpu_requirements(root: Path) -> str:
    path = root / GPU_REQUIREMENTS
    if not path.is_file():
        raise ContractError(f"{GPU_REQUIREMENTS} is absent")
    lines = [ln.strip().lower() for ln in path.read_text(encoding="utf-8").splitlines()]
    live = [ln for ln in lines if ln and not ln.startswith("#")]
    # The predicate's own rule: no non-comment line may start with "opencv".
    stock = [ln for ln in live if ln.startswith("opencv")]
    if stock:
        raise ContractError(f"{GPU_REQUIREMENTS} installs a stock OpenCV wheel: {stock}")
    text = "\n".join(live)
    for needle in (
        f"numpy=={NUMPY}",
        f"--hash=sha256:{NUMPY_WHEEL_SHA256}",
        f"openimageio=={OIIO}",
        f"--hash=sha256:{OIIO_WHEEL_SHA256}",
    ):
        if needle not in text:
            raise ContractError(f"{GPU_REQUIREMENTS} lacks the R4 pin {needle}")
    return _sha256(path)


def _check_cuda_path(value: str) -> str:
    v = (value or "").strip()
    if not v:
        raise ContractError(
            "--cuda-path-at-build is required: the CUDA_PATH value the OpenCV build ran with"
        )
    if not re.match(r"^[A-Za-z]:[\\/]", v):
        raise ContractError(f"--cuda-path-at-build must be an absolute Windows path, got {v!r}")
    if re.search(r"[\\/]users([\\/]|$)", v, re.IGNORECASE):
        raise ContractError("--cuda-path-at-build names a user folder; it cannot enter a public repo")
    return v.replace("\\", "/").rstrip("/")


def build_contract(root: Path, *, cuda_path_at_build: str, check_committed: bool = True) -> dict:
    """Assemble the contract, or raise ContractError. Writes nothing."""
    root = Path(root)
    receipt, receipt_sha = _read_receipt(root)  # first refusal: no receipt, no contract
    _check_receipt(receipt)
    gpu_sha = _check_gpu_requirements(root)
    cuda_path = _check_cuda_path(cuda_path_at_build)
    missing = [rel for rel in RECIPE if not (root / rel).is_file()]
    if missing:
        raise ContractError(f"recipe files absent: {missing}")
    if check_committed:
        bad = uncommitted(root, (BUILD_LOCK, GPU_REQUIREMENTS, *RECIPE))
        if bad:
            raise ContractError("pinned inputs are not committed as-is: " + ", ".join(bad))
    return {
        "schema": "synapse.vision.gpu_worker_env.contract/1",
        "node": "NR-VG-GPU-WORKER-ENV",
        "ruling": (
            "R4 (owner, 2026-11-07): worker runtime CPython 3.12.10 with the isolated cp312 "
            "OpenImageIO wheel, not a hython-seeded venv and not the cp314 wheel"
        ),
        "python": PYTHON,
        "python_implementation": "cpython",
        "python_base_interpreter_sha256": PYTHON_BASE_SHA256,
        "numpy": NUMPY,
        "numpy_wheel": NUMPY_WHEEL,
        "numpy_wheel_sha256": NUMPY_WHEEL_SHA256,
        "oiio": OIIO,
        "oiio_wheel": OIIO_WHEEL,
        "oiio_wheel_sha256": OIIO_WHEEL_SHA256,
        "cv2": (
            "the locked custom OpenCV 5.1 CUDA build only, placed by its cmake --install; "
            "the worker venv holds no opencv-python* package"
        ),
        "worker_venv": WORKER_VENV,
        "worker_venv_source": (
            "orchestrator record 2026-11-08: a fresh CPython 3.12.10 venv (ADR-0002 decision 17, "
            "option b); the decision is the owner's"
        ),
        "build_lock_receipt": BUILD_LOCK,
        "build_lock_receipt_sha256": receipt_sha,
        "gpu_requirements": GPU_REQUIREMENTS,
        "gpu_requirements_sha256": gpu_sha,
        "recipe_review_sha256": {rel: _sha256(root / rel) for rel in RECIPE},
        "cuda_dll_policy": {
            "loader": (
                "The installed cv2 loader config adds os.path.join(CUDA_PATH, 'bin/x64') for "
                "CUDA >= 13, falling back to the toolkit root recorded at configure when CUDA_PATH "
                "is unset; at import, cv2/__init__.py passes each path to os.add_dll_directory and "
                "prepends it to PATH, which child processes inherit (G0 receipt section 6, row "
                "DLL resolution)."
            ),
            "cuda_path_at_build": cuda_path,
            "cuda_path_source": "argument --cuda-path-at-build to make_contract.py",
            "dll_dir_at_build": cuda_path + "/bin/x64",
            "launcher_rule": (
                "A worker launcher must set CUDA_PATH to cuda_path_at_build before cv2 is "
                "imported and must not inherit the machine value: the CUDA runtime DLLs are "
                "named by major version only (cudart64_13.dll), so another 13.x toolkit that "
                "moves CUDA_PATH would swap the runtime under the locked artifact."
            ),
            "decision": (
                "ADR-0002 decision 18 option (a), as the NR-VG-GPU-WORKER-ENV brief specifies; "
                "the decision itself is the owner's"
            ),
        },
        "generated_by": "harness/vision/gpu_worker_env/make_contract.py",
    }


def write_contract(root: Path, contract: dict) -> Path:
    """Write the contract atomically, LF only, so a re-run is byte-identical."""
    out = Path(root) / CONTRACT
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_bytes((json.dumps(contract, indent=2, ensure_ascii=True) + "\n").encode("utf-8"))
    os.replace(tmp, out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write the R4 GPU worker-runtime contract.")
    ap.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[3]),
        help="repository root (default: the checkout holding this script)",
    )
    ap.add_argument(
        "--cuda-path-at-build",
        default="",
        help="the CUDA_PATH value the OpenCV build ran with (the v13.3 toolkit root)",
    )
    args = ap.parse_args(argv)
    try:
        contract = build_contract(Path(args.root), cuda_path_at_build=args.cuda_path_at_build)
    except ContractError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {write_contract(Path(args.root), contract)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
