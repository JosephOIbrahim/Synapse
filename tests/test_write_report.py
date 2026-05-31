"""Off-thread report writing — pure file I/O that never blocks on Houdini's
main thread (fixes the execute_python-based report-write hang).

The decisive test, `test_handler_writes_without_touching_main_thread`, sabotages
`run_on_main` to raise: the handler must still succeed, proving it does not
marshal the write onto the (blockable) main thread.
"""

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.cognitive.tools.write_report import ReportPathError, write_report  # noqa: E402


# --------------------------------------------------------------------------- #
# pure tool — confinement, atomicity, round-trip
# --------------------------------------------------------------------------- #

def test_writes_file(tmp_path):
    r = write_report("sub/report.md", "# Hello", base_dir=str(tmp_path))
    assert r["ok"] is True
    assert (tmp_path / "sub" / "report.md").read_text(encoding="utf-8") == "# Hello"
    assert r["bytes_written"] == len("# Hello".encode("utf-8"))
    assert Path(r["path"]) == (tmp_path / "sub" / "report.md").resolve()


def test_rejects_traversal(tmp_path):
    with pytest.raises(ReportPathError):
        write_report("../escape.md", "x", base_dir=str(tmp_path))
    with pytest.raises(ReportPathError):
        write_report("a/../../escape.md", "x", base_dir=str(tmp_path))


def test_rejects_absolute(tmp_path):
    with pytest.raises(ReportPathError):
        write_report(str(tmp_path / "abs.md"), "x", base_dir=str(tmp_path))
    with pytest.raises(ReportPathError):
        write_report("C:/evil.md" if os.name == "nt" else "/evil.md", "x", base_dir=str(tmp_path))


def test_overwrite_false_guards(tmp_path):
    write_report("o.md", "1", base_dir=str(tmp_path))
    with pytest.raises(ReportPathError):
        write_report("o.md", "2", overwrite=False, base_dir=str(tmp_path))
    assert (tmp_path / "o.md").read_text(encoding="utf-8") == "1"


def test_atomic_leaves_no_tmp_on_success(tmp_path):
    write_report("a/b/c.md", "data", base_dir=str(tmp_path))
    assert not list(tmp_path.rglob("*.tmp"))


def test_missing_base_dir_raises():
    with pytest.raises(ReportPathError):
        write_report("x.md", "y", base_dir=None)


def test_unicode_round_trips(tmp_path):
    txt = "café 🧠 déjà — multi\nline report"
    write_report("u.md", txt, base_dir=str(tmp_path))
    assert (tmp_path / "u.md").read_text(encoding="utf-8") == txt


# --------------------------------------------------------------------------- #
# WS handler — writes OFF the main thread (the regression that fixes the hang)
# --------------------------------------------------------------------------- #

def test_handler_writes_without_touching_main_thread(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_REPORTS_DIR", str(tmp_path))
    from synapse.server import handlers as handlers_mod
    import synapse.server.main_thread as mt

    def _boom(*a, **k):
        raise AssertionError("write_report must NOT marshal through the main thread")

    monkeypatch.setattr(mt, "run_on_main", _boom)

    handler = handlers_mod.SynapseHandler()
    result = handler._handle_write_report({"relative_path": "report.md", "content": "ok"})
    assert result["ok"] is True
    assert (tmp_path / "report.md").read_text(encoding="utf-8") == "ok"


def test_handler_confines_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_REPORTS_DIR", str(tmp_path))
    from synapse.server import handlers as handlers_mod
    handler = handlers_mod.SynapseHandler()
    # Catch ValueError (ReportPathError's base) — immune to the module-identity
    # mismatch when the handler imports write_report at call time under a
    # different sys.path than this test's collection-time import.
    with pytest.raises(ValueError) as ei:
        handler._handle_write_report({"relative_path": "../../etc/passwd", "content": "x"})
    assert "escapes base" in str(ei.value) or "traversal" in str(ei.value)


def test_handler_default_base_is_repo_docs(monkeypatch):
    monkeypatch.delenv("SYNAPSE_REPORTS_DIR", raising=False)
    from synapse.server import handlers as handlers_mod
    handler = handlers_mod.SynapseHandler()
    marker = "._synapse_offthread_probe.md"
    result = handler._handle_write_report({"relative_path": marker, "content": "probe"})
    written = Path(result["path"])
    try:
        assert written.parent.name == "docs"  # default base = <repo>/docs
        assert written.read_text(encoding="utf-8") == "probe"
    finally:
        if written.exists():
            written.unlink()
