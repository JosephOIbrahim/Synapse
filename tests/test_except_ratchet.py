"""Ratchet test: silent broad-except detector.

The ratchet ensures no new silent exception handlers are introduced.

Controls run on a TEMPORARY root with a TEMPORARY baseline (never the tracked
fixture): the positive control proves check mode exits 1 on a newly planted
swallow, and the fail-closed control proves an unparsable file is reported and
exits 1. An autouse guard asserts the tracked baseline bytes are unchanged after
every test — the previous positive control re-baselined the real tree on each
run and dirtied a tracked file (BP11-HARDFIX defect 7 / CRUX H-M3).
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "except_ratchet.py"
TRACKED_BASELINE = REPO_ROOT / "tests" / "fixtures" / "except_ratchet_baseline.json"


def _run(*args, cwd=REPO_ROOT):
    """Run the ratchet script with the given CLI args."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


@pytest.fixture(autouse=True)
def _tracked_baseline_untouched():
    """Guard: no test in this module may mutate the tracked baseline fixture."""
    before = TRACKED_BASELINE.read_bytes() if TRACKED_BASELINE.exists() else None
    yield
    after = TRACKED_BASELINE.read_bytes() if TRACKED_BASELINE.exists() else None
    assert after == before, (
        "a ratchet test mutated the tracked baseline fixture "
        f"{TRACKED_BASELINE.name}; controls must use a temporary baseline"
    )


def test_except_ratchet_passes_on_clean_tree():
    """Baseline: ratchet check should pass on the repo at its current state."""
    result = _run()
    assert result.returncode == 0, f"Ratchet check failed: {result.stdout}\n{result.stderr}"
    assert "OK" in result.stdout


def test_positive_control_detects_new_silent_handler(tmp_path):
    """A newly planted silent broad-except makes CHECK MODE exit 1.

    Runs entirely on a temporary tree with a temporary baseline, so the tracked
    baseline is never rewritten and the check-mode failure path is exercised
    directly (not inferred from a re-baseline).
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    # A broad handler that logs is NOT silent -> baseline records nothing for it.
    (pkg / "clean.py").write_text(
        "def f():\n    try:\n        pass\n    except Exception as e:\n        print(e)\n",
        encoding="utf-8",
    )
    baseline = tmp_path / "baseline.json"

    common = ["--root", str(pkg), "--rel-base", str(tmp_path), "--baseline", str(baseline)]

    # Baseline the clean tree, then confirm check mode passes on it.
    assert _run(*common, "--write-baseline").returncode == 0
    clean = _run(*common)
    assert clean.returncode == 0, (clean.stdout, clean.stderr)
    assert "OK" in clean.stdout

    # Plant a new silent broad handler; check mode must now fail.
    (pkg / "swallow.py").write_text(
        "def g():\n    try:\n        pass\n    except Exception:\n        pass\n",
        encoding="utf-8",
    )
    dirty = _run(*common)
    assert dirty.returncode == 1, (
        "check mode must exit 1 on a newly introduced silent handler; "
        f"stdout={dirty.stdout!r}"
    )
    assert "pkg/swallow.py" in dirty.stdout


def test_fail_closed_on_unparsable_file(tmp_path):
    """A file the ratchet cannot parse is reported UNPARSED and exits 1.

    Fail-open (returning ``(0, 0)`` for an unparsable file) is exactly how a
    broken module slipped the gate before (BP11-HARDFIX defect 6).
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "broken.py").write_text("def busted(:\n    return None\n", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"_rule": "test", "files": {}}', encoding="utf-8")

    common = ["--root", str(pkg), "--rel-base", str(tmp_path), "--baseline", str(baseline)]

    check = _run(*common)
    assert check.returncode == 1, "ratchet must fail closed on an unparsable file"
    assert "UNPARSED" in check.stdout
    assert "pkg/broken.py" in check.stdout

    # Fail closed in write-baseline mode too: it must not bake in a clean 0.
    write = _run(*common, "--write-baseline")
    assert write.returncode == 1
    assert "UNPARSED" in write.stdout


def test_negative_control_logging_is_not_silent():
    """Verify that handlers with logging calls are not counted as silent."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(
            "\ndef test_func():\n    try:\n        do_something()\n"
            "    except Exception as e:\n        print(\"Error occurred:\", e)\n"
        )
        temp_file = f.name

    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from except_ratchet import analyze_file

        broad_cnt, silent_cnt = analyze_file(Path(temp_file))
        assert broad_cnt == 1, f"Expected 1 broad handler, got {broad_cnt}"
        assert silent_cnt == 0, f"Expected 0 silent (has logging), got {silent_cnt}"
    finally:
        os.unlink(temp_file)


def test_analyze_file_raises_on_unparsable(tmp_path):
    """The reader raises RatchetUnparsable instead of returning a clean 0."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from except_ratchet import analyze_file, RatchetUnparsable

    bad = tmp_path / "bad.py"
    bad.write_text("def busted(:\n", encoding="utf-8")
    with pytest.raises(RatchetUnparsable):
        analyze_file(bad)


def test_identify_files_have_zero_baseline():
    """Verify every python/synapse/identify/ file has baseline of 0."""
    if TRACKED_BASELINE.exists():
        with open(TRACKED_BASELINE, "r", encoding="utf-8") as f:
            baseline = json.load(f)

        files = baseline.get("files", {})
        identify_files = [f for f in files if "python/synapse/identify/" in f]

        for filepath in identify_files:
            count = files[filepath]
            assert count == 0, f"Identify file {filepath} should have 0 silent handlers, has {count}"
