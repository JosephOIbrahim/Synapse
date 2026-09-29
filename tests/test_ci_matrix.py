"""CI runs on every OS artists use (CRUX H-M2).

The job matrix in ``.github/workflows/ci.yml`` is the only thing that makes CI
run on Windows and macOS as well as Linux, and no tracked test pinned it: a
matrix that quietly dropped Windows would have passed. These pins fail instead.
"""
from __future__ import annotations

import re
from pathlib import Path

CI = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
OSES = {"ubuntu-latest", "macos-latest", "windows-latest"}


def _inline_list(text: str, key: str) -> set:
    found = re.search(rf"^\s*{key}:\s*\[([^\]]*)\]", text, re.M)
    assert found, f"no inline `{key}: [...]` list in {CI.name}"
    return {item.strip().strip("\"'") for item in found.group(1).split(",") if item.strip()}


def test_the_matrix_names_linux_macos_and_windows():
    assert _inline_list(CI.read_text(encoding="utf-8"), "os") >= OSES


def test_the_job_runs_on_the_matrix_os():
    assert "runs-on: ${{ matrix.os }}" in CI.read_text(encoding="utf-8")


def test_the_matrix_tests_more_than_one_python():
    assert len(_inline_list(CI.read_text(encoding="utf-8"), "python-version")) >= 2
