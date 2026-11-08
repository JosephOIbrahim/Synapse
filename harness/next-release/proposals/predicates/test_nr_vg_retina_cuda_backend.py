"""Closure predicate for NR-VG-RETINA-CUDA-BACKEND (PROPOSED amendment; not in graph.json).

Flips green only when ADR-0002's Status line begins "**Status:** Accepted" in any letter
case (Joe's ratification; ADR-0001 records its ratification as "Accepted"), AND
retina/backend_cuda.py is committed but is never imported (statically, or through
importlib.import_module / __import__) by the in-host modules retina/__init__.py,
retina/t0.py, retina/events.py, retina/exr_header.py, and is absent from
installer/build_payload.py, AND harness/vision/retina_cuda_backend/backend_receipt.json
is committed, names exactly the R2 operations (absdiff, threshold, morphology_open,
morphology_close), pins the committed qualification receipt
harness/next-release/gpu_qualification.json by sha256, and names the tests proving that
an unavailable GPU operation yields an inconclusive check with a reason.

Red today: ADR-0002 is PROPOSED, not ratified (marker below).

Reads committed files only (text, AST, sha256). It never imports the backend or cv2,
touches a GPU, launches Houdini or uses the network.
"""
from __future__ import annotations

import ast
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
MARKER = "NR-VG-RETINA-CUDA-BACKEND RED: ADR-0002 is not ratified (its Status line does not begin Accepted)"
ADR = "docs/decisions/ADR-0002-retina-t1-optional-cuda-backend.md"
MODULE = "retina/backend_cuda.py"
RECEIPT = "harness/vision/retina_cuda_backend/backend_receipt.json"
QUAL = "harness/next-release/gpu_qualification.json"
IN_HOST = ("retina/__init__.py", "retina/t0.py", "retina/events.py", "retina/exr_header.py")
R2_OPS = {"absdiff", "threshold", "morphology_open", "morphology_close"}


def _committed(rel: str) -> bool:
    if not (ROOT / rel).is_file():
        return False
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", rel],
                       capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def _require_ratified() -> None:
    status = ""
    if _committed(ADR):
        for line in (ROOT / ADR).read_text(encoding="utf-8").splitlines():
            if line.startswith("**Status:**"):
                status = line
                break
    # Case-insensitive: the repo's only precedent, ADR-0001, reads "**Status:** Accepted" (review G5).
    if not status.lower().startswith("**status:** accepted"):
        raise AssertionError(MARKER)


def test_adr_0002_is_ratified():
    _require_ratified()


def test_backend_unreachable_from_the_in_host_modules():
    _require_ratified()
    assert _committed(MODULE), f"{MODULE} is not committed"
    for rel in IN_HOST:
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [a.name for a in node.names]
                assert not any("backend_cuda" in n for n in names), f"{rel} imports the backend"
            elif isinstance(node, ast.Import):
                assert not any("backend_cuda" in a.name for a in node.names), f"{rel} imports the backend"
            elif isinstance(node, ast.Call):
                f = node.func
                fname = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if fname in ("import_module", "__import__") and node.args:
                    arg = node.args[0]
                    # A constant target is checked by name; a computed target could be anything.
                    assert isinstance(arg, ast.Constant) and isinstance(arg.value, str),                         f"{rel} imports a computed module name dynamically"
                    assert "backend_cuda" not in arg.value, f"{rel} imports the backend dynamically"
    payload = (ROOT / "installer/build_payload.py").read_text(encoding="utf-8")
    assert "backend_cuda" not in payload, "the backend is on the host payload list"


def test_backend_receipt_covers_exactly_the_r2_chain():
    _require_ratified()
    assert _committed(RECEIPT), f"NR-VG-RETINA-CUDA-BACKEND: no committed backend receipt {RECEIPT}"
    r = json.loads((ROOT / RECEIPT).read_text(encoding="utf-8"))
    assert set(r.get("operations", [])) == R2_OPS, "operations must be exactly the R2 change-mask chain"
    assert _committed(QUAL), f"qualification receipt {QUAL} is not committed"
    assert r.get("qualification_receipt_sha256") == hashlib.sha256((ROOT / QUAL).read_bytes()).hexdigest(), \
        "backend receipt does not pin the committed qualification receipt"
    assert r.get("unavailable_is_inconclusive_tests"), "no test proves unavailable -> inconclusive with a reason"
