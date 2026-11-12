"""The root conftest must stamp every run with what it measured.

Why this file exists: two full-suite logs from 2026-11-12 could not prove which
commit or which interpreter produced them, and one was cited for a worktree it was
not produced from. The header is now the proof; these tests keep it honest.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytest.importorskip("pytest")

_spec = importlib.util.spec_from_file_location("synapse_root_conftest", ROOT / "conftest.py")
conftest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conftest)


def test_identity_records_a_commit_or_says_unknown():
    ident = conftest.identity()
    assert isinstance(ident["commit"], str)
    assert ident["commit"] == "UNKNOWN" or len(ident["commit"]) == 40, ident["commit"]


def test_identity_records_the_running_interpreter():
    ident = conftest.identity()
    assert ident["interpreter"] == f"{sys.implementation.name} {sys.version.split()[0]}"


def test_identity_records_the_dependency_set_that_changed_results():
    deps = conftest.identity()["deps"]
    for name in ("numpy", "cv2", "mcp", "pxr"):
        assert name in deps, f"{name} is not probed; that absence is what made today's numbers incomparable"
        assert deps[name] in (True, False, None)


def test_the_header_line_carries_commit_interpreter_and_deps():
    line = conftest._line(conftest.identity())
    assert "commit" in line and "at" in line
    for name in ("numpy", "cv2"):
        assert name + "=" in line, f"the header does not report {name}: {line}"


def test_the_header_never_publishes_a_home_directory(monkeypatch):
    """A log may be attached to a release; the machine's identity must not ride along."""
    ident = conftest.identity()
    line = conftest._line(ident)
    assert str(Path.home()) not in line
    assert "\\Users\\" not in line and "/Users/" not in line


def test_identity_never_raises_when_git_is_unavailable(monkeypatch):
    monkeypatch.setattr(conftest, "_git", lambda *a: "")
    ident = conftest.identity()
    assert ident["commit"] == "UNKNOWN"
    assert ident["dirty"] is False


def test_the_hook_is_reachable_by_pytest():
    """The hooks must exist where pytest looks for them: the root conftest."""
    for hook in ("pytest_configure", "pytest_report_header", "pytest_terminal_summary"):
        assert callable(getattr(conftest, hook, None)), hook
    assert (ROOT / "conftest.py").exists()


def test_the_report_header_hook_emits_the_line(monkeypatch):
    """_line working is not the same as the hook running. Pin the wiring."""
    class _Cfg:
        pass
    cfg = _Cfg()
    conftest.pytest_configure(cfg)
    lines = conftest.pytest_report_header(cfg)
    assert lines, "the report header hook returned nothing"
    assert "commit" in lines[0] and "numpy=" in lines[0], lines[0]
