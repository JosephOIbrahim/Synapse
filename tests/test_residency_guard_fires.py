"""Fix-is-real probe for eval_backbone (S.5) — proves the FAKE_HOU_RESIDENCY_GUARD
actually FIRES, not merely that its marker string is present.

eval_backbone is a PRESENCE gate: it greens when tests/conftest.py contains the
`# FAKE_HOU_RESIDENCY_GUARD` marker and check_render names validate_frame. A bare marker
comment over a gutted hook would keep it green while the guard did nothing. This probe
closes that gap behaviorally: it copies the SHIPPED conftest (the real canonical planter
+ pytest_collection_finish hook — NOT a reimplementation) into an isolated tmp dir, drops
a rogue module that clobbers the canonical hou at import, and asserts an isolated child
`pytest --collect-only` exits 4 (pytest.UsageError). Subprocess isolation keeps the rogue
out of THIS suite's collection — the parent test passes by asserting the child failed. If
the shipped hook is ever deleted, the positive case flips off 4 and this probe reddens,
even though eval_backbone's marker leg would still read green.
"""
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_REAL_CONFTEST = _REPO / "tests" / "conftest.py"


def _collect_only(tmp_path):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-p", "no:cacheprovider", str(tmp_path)],
        cwd=str(tmp_path), capture_output=True, text=True)


def test_residency_guard_raises_on_rogue_planter(tmp_path):
    # Copy the SHIPPED guard (real canonical planter + pytest_collection_finish), not a reimpl —
    # so gutting the shipped hook reddens THIS probe.
    shutil.copy(_REAL_CONFTEST, tmp_path / "conftest.py")
    (tmp_path / "test_rogue_planter.py").write_text(textwrap.dedent('''
        import sys, types
        sys.modules["hou"] = types.ModuleType("hou")  # non-canonical: no __synapse_canonical__
        def test_noop():
            assert True
    '''), encoding="utf-8")
    proc = _collect_only(tmp_path)
    # pytest.UsageError == ExitCode.USAGE_ERROR == 4 — the exact code the guard raises.
    assert proc.returncode == 4, (
        f"expected UsageError exit 4 (guard fired), got {proc.returncode}\n"
        f"STDOUT:\n{proc.stdout[-2000:]}\nSTDERR:\n{proc.stderr[-2000:]}")
    assert "FAKE_HOU_RESIDENCY_GUARD" in (proc.stdout + proc.stderr), \
        "guard fired but did not name itself — check the hook's message"


def test_residency_guard_quiet_without_rogue(tmp_path):
    # Same shipped conftest, NO rogue planter -> the guard must NOT false-fire. A benign test
    # collects cleanly (exit 0). This negative case distinguishes a real guard regression
    # (positive case flips off 4) from a conftest-import regression (this case flips off 0).
    shutil.copy(_REAL_CONFTEST, tmp_path / "conftest.py")
    (tmp_path / "test_benign.py").write_text(
        "def test_noop():\n    assert True\n", encoding="utf-8")
    proc = _collect_only(tmp_path)
    assert proc.returncode == 0, (
        f"guard false-fired or conftest failed to import in isolation: exit {proc.returncode}\n"
        f"STDOUT:\n{proc.stdout[-2000:]}\nSTDERR:\n{proc.stderr[-2000:]}")
