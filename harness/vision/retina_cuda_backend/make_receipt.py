"""Write backend_receipt.json for NR-VG-RETINA-CUDA-BACKEND (standard library only).

The receipt pins what the node's closure predicate checks:

- ``operations``: read from ``retina/backend_cuda.py`` by AST (never imported).
- ``unavailable_is_inconclusive_tests``: the ``test_unavailable_*`` node ids in
  ``tests/test_retina_backend_cuda.py``, read by AST. Those tests prove that an
  unavailable GPU operation yields an inconclusive check with a reason.
- ``qualification_receipt_sha256``: sha256 of the bytes of
  ``harness/next-release/gpu_qualification.json`` as checked out, the same bytes the
  predicate hashes.

It refuses to write while the qualification receipt is absent, so it never writes a
receipt that pins nothing. It writes no timestamp, so the same tree gives the same
bytes. It runs no test, imports nothing from the repository, touches no GPU and uses
no network.

Usage, from anywhere inside the checkout:

    python harness/vision/retina_cuda_backend/make_receipt.py           # write
    python harness/vision/retina_cuda_backend/make_receipt.py --check   # exit 1 on drift
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RECEIPT = HERE / "backend_receipt.json"
NODE = "NR-VG-RETINA-CUDA-BACKEND"
MODULE = "retina/backend_cuda.py"
TESTS = "tests/test_retina_backend_cuda.py"
QUAL = "harness/next-release/gpu_qualification.json"
PRODUCER = "harness/vision/retina_cuda_backend/make_receipt.py"
UNAVAILABLE_PREFIX = "test_unavailable_"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _operations() -> list:
    tree = ast.parse((ROOT / MODULE).read_text(encoding="utf-8"))
    for node in tree.body:
        target = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        if isinstance(target, ast.Name) and target.id == "OPERATIONS":
            return list(ast.literal_eval(value))
    raise SystemExit(f"{MODULE}: no module-level OPERATIONS assignment")


def _unavailable_tests() -> list:
    tree = ast.parse((ROOT / TESTS).read_text(encoding="utf-8"))
    names = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(UNAVAILABLE_PREFIX)
    ]
    if not names:
        raise SystemExit(f"{TESTS}: no {UNAVAILABLE_PREFIX}* tests")
    return [f"{TESTS}::{name}" for name in names]


def _committed(rel: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", rel],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode == 0


def build() -> dict:
    qual = ROOT / QUAL
    if not qual.is_file():
        raise SystemExit(
            f"refusing to write the backend receipt: {QUAL} does not exist. "
            "Commit the GPU qualification receipt first; the backend receipt pins it by sha256."
        )
    return {
        "schema": 1,
        "node": NODE,
        "producer": PRODUCER,
        "module": MODULE,
        "module_sha256": _sha256(ROOT / MODULE),
        "tests_file": TESTS,
        "tests_sha256": _sha256(ROOT / TESTS),
        "operations": _operations(),
        "unavailable_is_inconclusive_tests": _unavailable_tests(),
        "qualification_receipt": QUAL,
        "qualification_receipt_sha256": _sha256(qual),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare with the existing receipt instead of writing")
    args = parser.parse_args(argv)

    text = json.dumps(build(), indent=2) + "\n"
    if args.check:
        current = RECEIPT.read_text(encoding="utf-8") if RECEIPT.is_file() else None
        if current != text:
            print(f"DRIFT: {RECEIPT.relative_to(ROOT).as_posix()} does not match the tree", file=sys.stderr)
            return 1
        print(f"OK: {RECEIPT.relative_to(ROOT).as_posix()} matches the tree")
        return 0

    for rel in (MODULE, TESTS, QUAL):
        if not _committed(rel):
            print(f"warning: {rel} is not committed; the closure predicate reads committed files", file=sys.stderr)
    with open(RECEIPT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"wrote {RECEIPT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
