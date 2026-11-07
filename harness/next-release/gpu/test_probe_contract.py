"""Behavioural closure checks for the NR-GPU-FEASIBILITY receipt.

The node's graph predicate is ``test -f harness/next-release/gpu_feasibility.json``,
which only proves the file exists - it returned 0 even while B1 was still open.
This file is the real closure predicate: it fails whenever the receipt stops
recording the evidence the node says it produced.

Each test names the condition under which the receipt would stop satisfying the
contract, so a change to the receipt (or a regression to a file-exists gate)
turns the line red instead of silently green.

Run:  python -m pytest harness/next-release/gpu/test_probe_contract.py -q
"""

import json
import re
from pathlib import Path

import pytest

# harness/next-release/gpu/test_probe_contract.py -> harness/next-release/gpu_feasibility.json
RECEIPT_PATH = Path(__file__).resolve().parents[1] / "gpu_feasibility.json"


@pytest.fixture(scope="module")
def receipt():
    """Load the committed receipt once; a missing or malformed file is a failure."""
    assert RECEIPT_PATH.is_file(), f"receipt not found at {RECEIPT_PATH}"
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


def _blockers_by_id(receipt):
    return {block.get("id"): block for block in receipt.get("blockers", [])}


def _probe_commands(probe):
    commands = probe.get("commands") if isinstance(probe, dict) else None
    assert isinstance(commands, list) and commands, (
        "round_two_probe.commands must be a non-empty list"
    )
    return commands


def _is_nvcc_command(command):
    return "nvcc" in str(command.get("cmd", "")).lower()


def _is_run_command(command):
    cmd = str(command.get("cmd", "")).lower()
    # The nvcc line also contains "vectorAdd.exe" via its -o flag, so exclude it.
    return "vectoradd.exe" in cmd and not _is_nvcc_command(command)


def test_b1_is_resolved(receipt):
    """B1 is the showstopper: an 'open' or missing B1 must fail closure."""
    b1 = _blockers_by_id(receipt).get("B1")
    assert b1 is not None, "blockers[] has no B1 entry"
    assert b1.get("status") == "resolved", (
        f"B1.status is {b1.get('status')!r}, expected 'resolved'"
    )
    assert b1.get("resolution"), "a resolved B1 must record how it was resolved"


def test_round_two_probe_records_sm89_compile_with_exit_zero(receipt):
    """The probe must record an actual nvcc sm_89 compile that succeeded."""
    probe = receipt.get("round_two_probe")
    assert isinstance(probe, dict) and probe, "round_two_probe block is missing"

    compiles = [c for c in _probe_commands(probe) if _is_nvcc_command(c)]
    assert compiles, "no nvcc compile command recorded under round_two_probe"

    sm89_compiles = [c for c in compiles if "-arch=sm_89" in str(c.get("cmd", ""))]
    assert sm89_compiles, "no compile command records -arch=sm_89"

    assert any(c.get("exit_code") == 0 for c in sm89_compiles), (
        "no -arch=sm_89 compile recorded exit_code 0; "
        f"recorded: {[c.get('exit_code') for c in sm89_compiles]}"
    )


def test_round_two_probe_records_a_zero_mismatch_run(receipt):
    """A compile alone is not a run: the probe must show the binary executed."""
    probe = receipt.get("round_two_probe")
    assert isinstance(probe, dict) and probe, "round_two_probe block is missing"

    runs = [c for c in _probe_commands(probe) if _is_run_command(c)]
    assert runs, "no vectorAdd.exe run command recorded under round_two_probe"

    successful_runs = []
    for command in runs:
        if command.get("exit_code") != 0:
            continue
        match = re.search(r"mismatches=(\d+)", str(command.get("stdout", "")))
        if match and int(match.group(1)) == 0:
            successful_runs.append(command)

    assert successful_runs, (
        "no run recorded both exit_code 0 and zero mismatches; "
        f"runs: {[(c.get('exit_code'), c.get('stdout')) for c in runs]}"
    )


def test_verdict_is_feasible_unproven_not_feasible(receipt):
    """The whole point of the receipt is that the chain is NOT yet proven."""
    verdict = receipt.get("verdict")
    assert isinstance(verdict, dict), "verdict block is missing"
    assert verdict.get("state") == "feasible-unproven", (
        f"verdict.state is {verdict.get('state')!r}; "
        "a 'feasible' claim would outrun the evidence"
    )


def test_not_proven_is_a_non_empty_list(receipt):
    """An unproven build route must still enumerate what it has not proven."""
    not_proven = receipt.get("verdict", {}).get("not_proven")
    assert isinstance(not_proven, list), "verdict.not_proven must be a list"
    assert not_proven, "verdict.not_proven must not be empty"
