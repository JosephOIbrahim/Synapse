"""Real, disposable child processes; no actual substrate or memory store."""
import sys

import pytest

from synapse.loop.subprocess_port import SubstrateWorker


@pytest.mark.parametrize("stream,size", [("stdout", 1048576 + 8192), ("stderr", 65536 + 8192)])
def test_noisy_dependency_is_stopped_at_stream_budget(tmp_path, stream, size):
    package = tmp_path / "hanish"
    package.mkdir()
    (package / "__init__.py").write_text(
        "import sys,time\n"
        f"sys.{stream}.buffer.write(b'x' * {size})\n"
        f"sys.{stream}.flush()\n"
        "time.sleep(10)\n"
        "raise ImportError('synthetic dependency has no API')\n", encoding="utf-8")
    result = SubstrateWorker(sys.executable, str(tmp_path), timeout=2)(
        {"action": "status", "ledger_dir": str(tmp_path / "unused-ledger")})
    assert result.status == "UNAVAILABLE"
    assert stream in result.error_message and "exceeds" in result.error_message, result


def test_substrate_timeout_remains_unavailable(tmp_path):
    package = tmp_path / "hanish"
    package.mkdir()
    (package / "__init__.py").write_text("import time\ntime.sleep(10)\n", encoding="utf-8")
    result = SubstrateWorker(sys.executable, str(tmp_path), timeout=.15)(
        {"action": "status", "ledger_dir": str(tmp_path / "unused-ledger")})
    assert result.status == "UNAVAILABLE"
    assert "timed out" in result.error_message.lower(), result


def test_request_budget_refuses_before_launch(tmp_path, monkeypatch):
    import synapse.loop.subprocess_port as ipc
    monkeypatch.setattr(ipc.subprocess, "Popen", lambda *a, **k: pytest.fail("oversized request launched"))
    result = SubstrateWorker(sys.executable, str(tmp_path))({"action": "status", "input": "x" * 262145})
    assert result.status == "BLOCKED"


def test_both_pipes_drain_through_exact_byte_caps():
    from synapse.loop.subprocess_port import _run_bounded
    code = ("import sys; data=sys.stdin.buffer.read(); "
        "sys.stdout.buffer.write(data); "
        "sys.stderr.buffer.write(b'e'*65536); "
        "sys.stdout.buffer.write(b'o'*(1048576-len(data)))")
    result = _run_bounded([sys.executable, "-I", "-c", code], b"input", 3)
    assert result.returncode == 0
    assert result.stdout.startswith("input") and len(result.stdout) == 1048576
    assert result.stderr == "e" * 65536


def test_nonreading_child_times_out_and_releases_all_pipe_workers(monkeypatch):
    import synapse.loop.subprocess_port as ipc
    original = ipc.threading.Thread
    workers = []
    def track(*args, **kwargs):
        thread = original(*args, **kwargs)
        workers.append(thread)
        return thread
    monkeypatch.setattr(ipc.threading, "Thread", track)
    with pytest.raises(ipc.subprocess.TimeoutExpired):
        ipc._run_bounded([sys.executable, "-I", "-c", "import time;time.sleep(10)"], b"x" * 262144, .15)
    assert len(workers) == 3 and all(not thread.is_alive() for thread in workers)


def test_child_exit_and_bounded_error_text_are_retained():
    from synapse.loop.subprocess_port import _run_bounded
    result = _run_bounded([sys.executable, "-I", "-c",
        "import sys;sys.stderr.write('synthetic failure');sys.exit(7)"], b"", 2)
    assert result.returncode == 7 and result.stderr == "synthetic failure"


@pytest.mark.parametrize("duration", [0, -1, float("inf"), float("nan"), True])
def test_invalid_timeout_cannot_create_unbounded_child(duration, monkeypatch):
    import synapse.loop.subprocess_port as ipc
    monkeypatch.setattr(ipc.subprocess, "Popen", lambda *a, **k: pytest.fail("invalid timeout launched"))
    with pytest.raises(ValueError, match="positive finite"):
        ipc._run_bounded([sys.executable], b"", duration)
