#!/usr/bin/env python3
"""SYNAPSE FORGE-Evaluator — the adversarial gate for the graph-synthesis relay.

This is the Boris-harness Evaluator, translated off Playwright/web onto SYNAPSE's
own truth criteria. It writes nothing, fixes nothing. It runs four hard gates and
emits a parsable manifest; any single FAIL flips gate_status to FAIL and the outer
loop feeds remediation[] verbatim into a fresh FORGE (Generator) instance.

    PYTHONPATH=python python HARNESS/forge_evaluator_gate.py --mile 1

Gates
  1 BOUNDARY      cognitive/* imports zero hou            (pre-existing repo artifact)
  2 DOD           the Mile-N definition-of-done tests      (spec §12)
  3 PHANTOM       no dead concepts / no known-absent hou   (SYNAPSE phantom discipline)
  4 MUTATION      validate-time is hou-free + side-effect-free (truth contract)

stdlib only — runs headless inside the harness with no extra deps.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COGNITIVE = REPO / "python" / "synapse" / "cognitive"

# Files this feature owns — the Evaluator scopes to the diff, not the whole repo.
FEATURE_FILES = [
    "python/synapse/cognitive/graph_proposal.py",
    "python/synapse/cognitive/graph_validator.py",
    "python/synapse/cognitive/interfaces.py",
    "python/synapse/cognitive/tools/propose_graph.py",
    "python/synapse/host/proposal_store.py",
    "python/synapse/host/existence_adapter.py",
    "python/synapse/host/graph_oracle.py",
    "python/synapse/host/graph_builder.py",
]

BOUNDARY_TEST = "tests/test_cognitive_boundary.py"
MILE_TESTS = {
    1: ["tests/test_graph_proposal_mile1.py"],
    2: ["tests/test_graph_oracle_mile2.py"],      # added at Mile 2
    3: ["tests/test_graph_builder_mile3.py"],     # added at Mile 3
}

# Concepts cut from the spec — reappearing is regression, not progress.
DEAD_CONCEPTS = ["new_branch"]
# Symbols confirmed ABSENT in H21.0.671 by dir() introspection — using them is phantom.
KNOWN_ABSENT_HOU = ["hou.pdg", "hou.secure", "hou.lopNetworks", "hou.updateGraphTick"]


def _run_pytest(paths: list[str]) -> tuple[bool, str]:
    # Inherit the FULL parent environment and only override PYTHONPATH. Passing a
    # minimal env dropped SYSTEMROOT on Windows, which breaks the child Python's
    # startup (random/socket init) before any test runs — making green tests look
    # red. Capture stderr too, so a real failure leaves a traceback, not "".
    env = {**os.environ, "PYTHONPATH": "python"}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *paths, "-q"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
    )
    combined = (proc.stdout + proc.stderr).strip().splitlines()
    tail = "\n".join(combined[-4:])
    return proc.returncode == 0, tail


def gate_boundary() -> tuple[bool, list[dict]]:
    ok, tail = _run_pytest([BOUNDARY_TEST])
    return ok, ([] if ok else [{"target_file": "python/synapse/cognitive/",
                                "issue": "hou import leaked into cognitive layer",
                                "evidence": tail}])


def gate_dod(mile: int) -> tuple[bool, list[dict]]:
    tests = MILE_TESTS.get(mile, [])
    present = [t for t in tests if (REPO / t).exists()]
    if not present:
        return False, [{"target_file": tests[0] if tests else f"mile {mile}",
                        "issue": f"Mile {mile} DoD test absent",
                        "evidence": "Generator must land the DoD test before the gate can pass"}]
    ok, tail = _run_pytest(present)
    return ok, ([] if ok else [{"target_file": present[0],
                                "issue": f"Mile {mile} DoD assertion failed",
                                "evidence": tail}])


def gate_phantom() -> tuple[bool, list[dict]]:
    remediation: list[dict] = []
    for rel in FEATURE_FILES:
        path = REPO / rel
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8")
        # Strip line comments so a documented prohibition (e.g. "do not
        # reintroduce new_branch") is not itself flagged. Real reintroductions
        # in code or string-value position survive the strip and still fail.
        src = "\n".join(ln.split("#", 1)[0] for ln in raw.splitlines())
        for dead in DEAD_CONCEPTS:
            for m in re.finditer(rf"\b{re.escape(dead)}\b", src):
                line = src[: m.start()].count("\n") + 1
                remediation.append({"target_file": rel,
                                    "issue": f"dead concept '{dead}' reintroduced (cut in v3)",
                                    "evidence": f"{rel}:{line}"})
        for sym in KNOWN_ABSENT_HOU:
            for m in re.finditer(rf"{re.escape(sym)}\b", src):
                line = src[: m.start()].count("\n") + 1
                remediation.append({"target_file": rel,
                                    "issue": f"phantom API '{sym}' — confirmed absent in H21.0.671",
                                    "evidence": f"{rel}:{line}"})
    return (not remediation), remediation


def gate_mutation() -> tuple[bool, list[dict]]:
    # Validate-time must be provably side-effect-free. Proxy: the cognitive tree
    # imports no hou (so it cannot touch a live scene), enforced structurally.
    remediation: list[dict] = []
    forbidden = re.compile(r"^\s*(?:import\s+hou\b|from\s+hou\b)", re.MULTILINE)
    for py in sorted(COGNITIVE.rglob("*.py")):
        src = py.read_text(encoding="utf-8")
        if forbidden.search(src):
            rel = py.relative_to(REPO)
            remediation.append({"target_file": str(rel),
                                "issue": "validate-time path can reach hou — mutation risk",
                                "evidence": f"{rel} imports hou"})
    return (not remediation), remediation


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mile", type=int, default=1)
    args = ap.parse_args()

    gates = {
        "boundary": gate_boundary(),
        "dod": gate_dod(args.mile),
        "phantom": gate_phantom(),
        "mutation": gate_mutation(),
    }

    scores = {name: ("PASS" if ok else "FAIL") for name, (ok, _) in gates.items()}
    remediation = [item for _, (_, items) in gates.items() for item in items]
    status = "PASS" if all(ok for ok, _ in gates.values()) else "FAIL"

    print("## FORGE-EVALUATOR REPORT")
    for name, verdict in scores.items():
        print(f"  [{verdict}] gate:{name}")
    print("\n## MANIFEST")
    print(json.dumps({"mile": args.mile, "gates": scores,
                      "gate_status": status, "remediation": remediation}, indent=2))
    # Non-zero exit lets the outer loop branch on FAIL without parsing stdout.
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
