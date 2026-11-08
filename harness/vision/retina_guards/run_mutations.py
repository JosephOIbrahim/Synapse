"""Mutation receipt for the RETINA worker-boundary guards (NR-VG-RETINA-GUARDS).

Proves each guard in tests/test_retina_worker_boundary.py can fail, using the named
mutations of the G0 receipt section 11, Slice 1 table
(docs/reviews/opencv51-gpu-g0-receipt-2026-11-07.md):

1. export the committed tree with ``git -C <repo> archive HEAD`` into ``<scratch>/export``,
   a folder outside the repository; the working tree is never mutated;
2. overlay the working guard file and run the guards unmutated: all three must pass;
3. per named mutation: apply it to the export only, prove by AST that it landed and that
   the file still parses, re-run the guards, record the exit code and which guard went
   red, then restore the file byte for byte;
4. run the guards unmutated once more, then write ``mutation_receipt.json`` beside this
   script. It pins the guard file by sha256 and names repo-relative paths and
   placeholders only.

Standard library only. From the repository root:

    python harness/vision/retina_guards/run_mutations.py --scratch <folder outside the repo>

Exits 0 only when every expectation held; the receipt records the outcome either way.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

GUARD = "tests/test_retina_worker_boundary.py"
RECEIPT = "harness/vision/retina_guards/mutation_receipt.json"
GUARD_TESTS = (
    "test_in_host_retina_modules_cannot_reach_a_backend",
    "test_retina_worker_tree_imports_no_hou",
    "test_host_payload_ships_no_new_retina_module",
)
PYTEST_ARGS = ("-m", "pytest", GUARD, "-q", "-p", "no:cacheprovider")
# An export-ignore attribute or a moved tree would let the guards pass on nothing.
REQUIRED_IN_EXPORT = (
    "retina/__init__.py", "retina/t0.py", "retina/events.py", "retina/exr_header.py",
    "retina/t1.py", "installer/build_payload.py", "tests/conftest.py", "pyproject.toml",
)
EXPORT_MARKER = ".retina_guards_export"
PAYLOAD_ANCHOR = '"retina/qc_profiles.toml",'
DRIVE_PATH = re.compile(r"[A-Za-z]:[\\/]")


def _newline(src: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in src else b"\n"


def _append(*lines: str):
    def apply(src: bytes) -> bytes:
        nl = _newline(src)
        head = src if src.endswith(b"\n") else src + nl
        return head + nl.join(line.encode("utf-8") for line in lines) + nl
    return apply


def _is_docstring(stmt: ast.stmt) -> bool:
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str))


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise SystemExit(f"mutation target: no module-level function {name}")


def _insert_in_function(name: str, line: str):
    """Insert ``line`` as the first statement of function ``name`` (after its
    docstring), at that statement's own indentation; located by AST, not line number."""
    def apply(src: bytes) -> bytes:
        fn = _function(ast.parse(src), name)
        body = fn.body
        if _is_docstring(body[0]) and len(body) == 1:
            at, col = body[0].end_lineno, body[0].col_offset
        else:
            stmt = body[1] if _is_docstring(body[0]) else body[0]
            if stmt.lineno == fn.lineno:
                raise SystemExit(f"mutation target: {name} has its body on the def line")
            at, col = stmt.lineno - 1, stmt.col_offset
        lines = src.splitlines(keepends=True)
        lines.insert(at, b" " * col + line.encode("utf-8") + _newline(src))
        return b"".join(lines)
    return apply


def _replace_once(old: str, new: str):
    def apply(src: bytes) -> bytes:
        if src.count(old.encode("utf-8")) != 1:
            raise SystemExit(f"mutation anchor {old!r} is not unique in its file")
        return src.replace(old.encode("utf-8"), new.encode("utf-8"))
    return apply


def _t0_imports_t1(tree: ast.Module) -> bool:
    return any(isinstance(n, ast.ImportFrom) and n.level == 1 and n.module is None
               and any(a.name == "t1" for a in n.names) for n in tree.body)


def _t0_import_module_t1(tree: ast.Module) -> bool:
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == "import_module" and isinstance(n.func.value, ast.Name)
               and n.func.value.id == "importlib" and len(n.args) == 1
               and isinstance(n.args[0], ast.Constant) and n.args[0].value == "retina.t1"
               for n in ast.walk(tree))


def _t1_require_imports_hou(tree: ast.Module) -> bool:
    return any(isinstance(n, ast.Import) and any(a.name == "hou" for a in n.names)
               for n in _function(tree, "_require").body)


def _payload_lists_backend(tree: ast.Module) -> bool:
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "RUNTIME_FILES" for t in stmt.targets):
            return any(isinstance(e, ast.Constant) and e.value == "retina/backend_cuda.py"
                       for e in getattr(stmt.value, "elts", ()))
    return False


MUTATIONS = (
    {"id": "t0_imports_t1", "file": "retina/t0.py",
     "change": "append a module-level `from . import t1`",
     "inserted": ["from . import t1  # mutation t0_imports_t1"],
     "expected_red_test": GUARD_TESTS[0], "landed": _t0_imports_t1},
    {"id": "t0_import_module_t1", "file": "retina/t0.py",
     "change": "append a module-level `importlib.import_module(\"retina.t1\")` (with `import importlib`)",
     "inserted": ["import importlib",
                  "importlib.import_module(\"retina.t1\")  # mutation t0_import_module_t1"],
     "expected_red_test": GUARD_TESTS[0], "landed": _t0_import_module_t1},
    {"id": "t1_imports_hou", "file": "retina/t1.py",
     "change": "insert `import hou` as the first statement of function `_require`, after its docstring",
     "inserted": ["import hou  # mutation t1_imports_hou"],
     "expected_red_test": GUARD_TESTS[1], "landed": _t1_require_imports_hou},
    {"id": "payload_adds_backend", "file": "installer/build_payload.py",
     "change": "append \"retina/backend_cuda.py\" to the RUNTIME_FILES literal, after \"retina/qc_profiles.toml\"",
     "inserted": ["\"retina/backend_cuda.py\","],
     "expected_red_test": GUARD_TESTS[2], "landed": _payload_lists_backend},
)
MUTATIONS[0]["apply"] = _append(*MUTATIONS[0]["inserted"])
MUTATIONS[1]["apply"] = _append(*MUTATIONS[1]["inserted"])
MUTATIONS[2]["apply"] = _insert_in_function("_require", MUTATIONS[2]["inserted"][0])
MUTATIONS[3]["apply"] = _replace_once(PAYLOAD_ANCHOR, PAYLOAD_ANCHOR + ' "retina/backend_cuda.py",')


def _child_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    # A stray GIT_DIR or GIT_WORK_TREE would point git at some other repository.
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(extra or {})
    return env


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                         env=_child_env(), timeout=120)
    if out.returncode:
        raise SystemExit(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout.strip()


def _inside(child: Path, parent: Path) -> bool:
    c, p = os.path.normcase(str(child)), os.path.normcase(str(parent))
    try:
        return os.path.commonpath([c, p]) == p
    except ValueError:  # different drives
        return False


def _export(root: Path, export: Path) -> None:
    proc = subprocess.Popen(["git", "-C", str(root), "archive", "--format=tar", "HEAD"],
                            stdout=subprocess.PIPE, env=_child_env())
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(export, filter="data")
            else:
                tar.extractall(export)
    finally:
        proc.stdout.close()
        rc = proc.wait()
    if rc:
        raise SystemExit(f"git archive exited {rc}")


def _run_guards(export: Path, scratch: Path, label: str) -> dict:
    junit = scratch / f"junit-{label}.xml"
    if junit.exists():
        junit.unlink()
    tmp = scratch / "tmp"
    tmp.mkdir(exist_ok=True)
    env = _child_env({
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": os.pathsep.join((str(export / "python"), str(export))),
        "TEMP": str(tmp), "TMP": str(tmp), "SYNAPSE_LOG_DIR": str(tmp),
    })
    proc = subprocess.run([sys.executable, *PYTEST_ARGS, f"--junitxml={junit}"], cwd=export,
                          env=env, capture_output=True, encoding="utf-8", errors="replace",
                          timeout=900)
    outcomes: dict[str, str] = {}
    messages: dict[str, str] = {}
    if junit.is_file():
        for case in ET.parse(junit).getroot().iter("testcase"):
            name = case.get("name", "")
            outcomes[name] = "passed"
            for tag, state in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
                found = case.find(tag)
                if found is not None:
                    outcomes[name] = state
                    messages[name] = found.get("message") or ""
                    break
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    summary = re.sub(r"\s+in\s+[\d.]+s\b.*$", "", lines[-1].strip("= ")) if lines else ""
    return {"rc": proc.returncode, "outcomes": outcomes, "messages": messages, "summary": summary}


def _scrub(message: str, tokens: tuple[tuple[Path, str], ...]) -> str:
    first = message.strip().splitlines()[0] if message.strip() else ""
    for path, token in tokens:
        for form in (str(path), path.as_posix()):
            first = first.replace(form, token)
    return DRIVE_PATH.sub("<abs>/", first)[:600]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mutation receipt for the RETINA worker-boundary guards.")
    parser.add_argument("--scratch", required=True,
                        help="absolute folder outside the repository; the export lands in <scratch>/export")
    args = parser.parse_args(argv)
    root = Path(_git(Path(__file__).resolve().parent, "rev-parse", "--show-toplevel")).resolve()
    scratch = Path(args.scratch)
    if not scratch.is_absolute():
        raise SystemExit("--scratch must be an absolute path")
    scratch = scratch.resolve()
    if _inside(scratch, root) or _inside(root, scratch):
        raise SystemExit("--scratch must lie outside the repository and must not contain it")
    export = scratch / "export"
    if export.exists():
        if not (export / EXPORT_MARKER).is_file():
            raise SystemExit("<scratch>/export exists and is not an export this runner made; refusing to delete it")
        shutil.rmtree(export)
    export.mkdir(parents=True)
    (export / EXPORT_MARKER).write_text("scratch export made by run_mutations.py\n", encoding="utf-8")

    commit = _git(root, "rev-parse", "HEAD")
    _export(root, export)
    missing = [p for p in REQUIRED_IN_EXPORT if not (export / p).is_file()]
    if missing:
        raise SystemExit(f"the export is missing {missing}; a guard run on it would prove nothing")
    guard_bytes = (root / GUARD).read_bytes()
    (export / GUARD).write_bytes(guard_bytes)
    tokens = ((export, "<export>"), (scratch, "<scratch>"), (root, "<repo>"))
    all_passed = {t: "passed" for t in GUARD_TESTS}

    unmutated = _run_guards(export, scratch, "unmutated")
    ok = unmutated["rc"] == 0 and unmutated["outcomes"] == all_passed
    records = []
    for m in MUTATIONS:
        path = export / m["file"]
        pristine = path.read_bytes()
        mutated = m["apply"](pristine)
        # A mutation that does not parse would turn a guard red for the wrong reason.
        landed = mutated != pristine and m["landed"](ast.parse(mutated, filename=m["file"]))
        path.write_bytes(mutated)
        try:
            run = _run_guards(export, scratch, m["id"])
        finally:
            path.write_bytes(pristine)
        restored = path.read_bytes() == pristine
        red = sorted(n for n, s in run["outcomes"].items() if s in ("failed", "error"))
        expected = m["expected_red_test"]
        red_test = expected if expected in red else (red[0] if red else None)
        only_expected = red == [expected]
        records.append({
            "id": m["id"], "file": m["file"], "change": m["change"], "inserted": m["inserted"],
            "mutated_file_parses": True, "mutation_landed": landed,
            "guard_rc": run["rc"], "red_test": red_test, "red_tests": red,
            "expected_red_test": expected, "only_expected_guard_red": only_expected,
            "outcomes": run["outcomes"], "summary": run["summary"],
            "failure": _scrub(run["messages"].get(red_test or "", ""), tokens),
            "restored_byte_identical": restored,
        })
        ok = ok and landed and restored and run["rc"] not in (None, 0) and only_expected
    final = _run_guards(export, scratch, "final")
    ok = ok and final["rc"] == 0 and final["outcomes"] == all_passed

    try:
        pytest_version = importlib.metadata.version("pytest")
    except importlib.metadata.PackageNotFoundError:
        pytest_version = "unknown"
    receipt = {
        "schema": "nr-vg-retina-guards/mutation-receipt/1",
        "node": "NR-VG-RETINA-GUARDS",
        "spec": "docs/reviews/opencv51-gpu-g0-receipt-2026-11-07.md, section 11, Slice 1",
        "guard_file": GUARD,
        "guard_sha256": hashlib.sha256(guard_bytes).hexdigest(),
        "guard_tests": list(GUARD_TESTS),
        "exported_commit": commit,
        "interpreter": {"implementation": platform.python_implementation(),
                        "version": platform.python_version(), "sys_version": sys.version},
        "pytest_version": pytest_version,
        "platform": platform.platform(terse=True),
        "commands": {
            "runner": "<python> harness/vision/retina_guards/run_mutations.py --scratch <scratch>  (cwd <repo>)",
            "export": f"git -C <repo> archive --format=tar HEAD  (extracted into <export>; <repo>/{GUARD} copied over <export>/{GUARD})",
            "guards": f"<python> {' '.join(PYTEST_ARGS)} --junitxml=<scratch>/junit-<label>.xml  (cwd <export>)",
        },
        "guard_environment": {
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": f"<export>/python{os.pathsep}<export>",
            "TEMP": "<scratch>/tmp", "TMP": "<scratch>/tmp", "SYNAPSE_LOG_DIR": "<scratch>/tmp",
            "GIT_*": "removed",
        },
        "placeholders": {
            "<python>": "the interpreter named under interpreter (the runner's own)",
            "<repo>": "the repository root, from git rev-parse --show-toplevel",
            "<scratch>": "the --scratch folder, outside the repository",
            "<export>": "<scratch>/export, a fresh git archive of exported_commit",
            "<label>": "unmutated, each mutation id, then final",
        },
        "unmutated_rc": unmutated["rc"],
        "unmutated_outcomes": unmutated["outcomes"],
        "unmutated_summary": unmutated["summary"],
        "mutations": records,
        "final_unmutated_rc": final["rc"],
        "final_unmutated_outcomes": final["outcomes"],
        "all_expectations_met": ok,
    }
    text = json.dumps(receipt, indent=2) + "\n"
    leaked = [f for p, _ in tokens for f in (str(p), p.as_posix()) if f in text]
    if leaked or DRIVE_PATH.search(text):
        raise SystemExit("refusing to write a receipt that names an absolute path")
    (root / RECEIPT).write_bytes(text.encode("utf-8"))
    print(f"unmutated rc {unmutated['rc']} {unmutated['outcomes']}")
    for r in records:
        print(f"{r['id']}: guard_rc {r['guard_rc']} red {r['red_tests']} landed {r['mutation_landed']} "
              f"restored {r['restored_byte_identical']}")
    print(f"final rc {final['rc']}; all_expectations_met {ok}; wrote {RECEIPT}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
