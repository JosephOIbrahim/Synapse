"""Cold journal resolution must never call Houdini from an MCP worker."""
from pathlib import Path
import queue
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from synapse.panel import session_journal as journal
from synapse.server import main_thread


def worker_result(callback, callbacks):
    values, errors = [], []

    def run():
        try:
            values.append(callback())
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    deadline = time.monotonic() + 5
    while worker.is_alive() and time.monotonic() < deadline:
        try:
            callbacks.get(timeout=0.02)()
        except queue.Empty:
            pass
    worker.join(0.1)
    assert not worker.is_alive(), "journal dispatch did not complete"
    assert not errors
    return values[0]


@pytest.fixture
def cold_journal(tmp_path, monkeypatch):
    callbacks, reads = queue.Queue(), []
    scene = tmp_path / "scene"
    scene.mkdir()

    def hip_path():
        reads.append(threading.get_ident())
        return str(scene / "demo.hip")

    monkeypatch.setattr(journal, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(journal, "hou", SimpleNamespace(hipFile=SimpleNamespace(path=hip_path)))
    monkeypatch.setattr(journal, "_journal_instance", None)
    monkeypatch.setattr(journal.tempfile, "gettempdir", lambda: str(tmp_path / "fallback"))
    monkeypatch.setitem(sys.modules, "hdefereval", SimpleNamespace(executeDeferred=callbacks.put))
    return callbacks, reads, scene


def test_cold_worker_journal_reads_scene_on_main_and_writes_selected_log(cold_journal):
    callbacks, reads, scene = cold_journal

    def log():
        result = journal.get_journal()
        result.log_tool("synapse_recall", {"query": "coral"}, {}, duration_ms=1)
        return result

    result = worker_result(log, callbacks)
    assert reads == [threading.main_thread().ident]
    assert Path(result._log_dir) == scene / "claude"
    assert "TOOL synapse_recall" in (scene / "claude" / "journal.log").read_text(encoding="utf-8")


def test_unavailable_dispatch_falls_back_without_calling_houdini(cold_journal, monkeypatch, tmp_path):
    callbacks, reads, _ = cold_journal

    def unavailable(*args, **kwargs):
        raise RuntimeError("Injected unavailable main-thread dispatch")

    monkeypatch.setattr(main_thread, "run_on_main", unavailable)
    result = worker_result(journal.get_journal, callbacks)
    assert reads == []
    assert Path(result._log_dir) == tmp_path / "fallback" / "synapse_journal"


def test_explicit_log_directory_never_reads_houdini(cold_journal, tmp_path):
    callbacks, reads, _ = cold_journal
    explicit = tmp_path / "explicit"
    result = worker_result(lambda: journal.get_journal(str(explicit)), callbacks)
    assert reads == []
    assert Path(result._log_dir) == explicit


def test_negative_control_direct_dispatch_exposes_worker_scene_read(cold_journal, monkeypatch):
    callbacks, reads, scene = cold_journal
    # Remove the dispatch boundary only in test memory. The same fake host
    # records the former off-main read, proving the positive test is sensitive.
    monkeypatch.setattr(main_thread, "run_on_main", lambda fn, **kwargs: fn())
    result = worker_result(journal.get_journal, callbacks)
    assert len(reads) == 1 and reads[0] != threading.main_thread().ident
    assert Path(result._log_dir) == scene / "claude"
