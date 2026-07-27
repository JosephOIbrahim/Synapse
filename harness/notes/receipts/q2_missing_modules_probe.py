"""Q2 producer: enumerate every third-party top-level module the repo imports,
then try to import each under THIS interpreter and record the ImportError.

Run under both interpreters to get the environment-gap delta:

    python                                  harness/notes/receipts/q2_missing_modules_probe.py
    "<HFS>/bin/hython.exe"                  harness/notes/receipts/q2_missing_modules_probe.py

Membership is decided by actually importing, never by inference. Output is JSON
on stdout: {interpreter, version, importable[], missing{name: error}}.
"""
import ast
import json
import os
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCAN = [ROOT / "tests", ROOT / "python" / "synapse", ROOT / "harness" / "verify"]

# Self-anchoring: the worktree's own package wins over any editable install.
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(1, str(ROOT))

# Anything the repo ships itself is not a third-party gap.
LOCAL = {"synapse", "shared", "tests", "panel", "conftest", "harness", "host", "scripts"}
STDLIB = set(getattr(sys, "stdlib_module_names", ()))


def top_level_imports():
    names = set()
    for base in SCAN:
        if not base.exists():
            continue
        for f in base.rglob("*.py"):
            if "_vendor" in f.parts:
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        names.add(a.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0 and node.module:
                        names.add(node.module.split(".")[0])
    return names


def main():
    # SYNAPSE_Q2_PREIMPORT=1 reproduces test conditions: conftest imports synapse,
    # which is what activates the vendored dependency tree (synapse/_vendor). The
    # missing-list differs between the two modes and only the pre-import mode is
    # the honest answer for "what do the tests see".
    vendor_risk = None
    if os.environ.get("SYNAPSE_Q2_PREIMPORT") == "1":
        import synapse
        vendor_risk = getattr(synapse, "_VENDOR_ABI_RISK", None)

    cands = sorted(n for n in top_level_imports()
                   if n and not n.startswith("_") and n not in STDLIB and n not in LOCAL)
    importable, missing = [], {}
    for n in cands:
        try:
            __import__(n)
            importable.append(n)
        except BaseException as e:  # SystemExit/licence errors count as unavailable
            missing[n] = f"{type(e).__name__}: {str(e)[:160]}"
    print(json.dumps({
        "producer": "harness/notes/receipts/q2_missing_modules_probe.py",
        "interpreter": sys.executable,
        "version": sys.version.split()[0],
        "preimport_synapse": os.environ.get("SYNAPSE_Q2_PREIMPORT") == "1",
        "vendor_abi_risk": vendor_risk,
        "candidates": len(cands),
        "importable": importable,
        "missing": missing,
    }, indent=2))


if __name__ == "__main__":
    main()
