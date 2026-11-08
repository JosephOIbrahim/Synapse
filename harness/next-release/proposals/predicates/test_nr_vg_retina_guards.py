"""Closure predicate for NR-VG-RETINA-GUARDS (PROPOSED amendment; not in graph.json).

Flips green only when tests/test_retina_worker_boundary.py is committed with the
three guard tests named in the G0 receipt section 11
(test_in_host_retina_modules_cannot_reach_a_backend,
test_retina_worker_tree_imports_no_hou, test_host_payload_ships_no_new_retina_module)
AND harness/vision/retina_guards/mutation_receipt.json is committed, pins the guard
file by sha256, records the unmutated guard run as rc 0, and records each of the four
named mutations (t1 imported from t0; importlib.import_module of retina.t1 in t0;
hou imported inside a function in t1; a backend module appended to the host payload)
as turning a named guard red.

Red today: the guard file is not committed (marker below).

Reads committed files only (AST parse, sha256). It never runs the guards, imports
retina, touches a GPU, launches Houdini or uses the network.
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
MARKER = ("NR-VG-RETINA-GUARDS RED: guard tests tests/test_retina_worker_boundary.py "
          "are not committed")
GUARD = "tests/test_retina_worker_boundary.py"
RECEIPT = "harness/vision/retina_guards/mutation_receipt.json"
GUARD_TESTS = {
    "test_in_host_retina_modules_cannot_reach_a_backend",
    "test_retina_worker_tree_imports_no_hou",
    "test_host_payload_ships_no_new_retina_module",
}
MUTATIONS = {"t0_imports_t1", "t0_import_module_t1", "t1_imports_hou", "payload_adds_backend"}


def _committed(rel: str) -> bool:
    if not (ROOT / rel).is_file():
        return False
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", rel],
                       capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def _guard_bytes() -> bytes:
    if not _committed(GUARD):
        raise AssertionError(MARKER)
    return (ROOT / GUARD).read_bytes()


def test_guard_file_is_committed():
    assert _guard_bytes()


def test_guard_file_defines_the_three_guards():
    tree = ast.parse(_guard_bytes().decode("utf-8"))
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    missing = GUARD_TESTS - names
    assert not missing, f"guard tests missing: {sorted(missing)}"


def test_each_named_mutation_turns_a_guard_red():
    digest = hashlib.sha256(_guard_bytes()).hexdigest()
    assert _committed(RECEIPT), f"NR-VG-RETINA-GUARDS: no committed mutation receipt {RECEIPT}"
    r = json.loads((ROOT / RECEIPT).read_text(encoding="utf-8"))
    assert r.get("guard_sha256") == digest, "mutation receipt does not pin the committed guard file"
    assert r.get("unmutated_rc") == 0, "the unmutated guard run must pass"
    by_id = {m.get("id"): m for m in r.get("mutations", [])}
    assert MUTATIONS <= set(by_id), f"mutations missing: {sorted(MUTATIONS - set(by_id))}"
    for mid in MUTATIONS:
        m = by_id[mid]
        assert m.get("guard_rc") not in (None, 0), f"mutation {mid} did not turn the guards red"
        assert m.get("red_test") in GUARD_TESTS, f"mutation {mid} names no guard test"
