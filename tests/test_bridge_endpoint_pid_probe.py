"""Regression pins for ``bridge_endpoint._pid_alive``.

Split from test_bridge_endpoint.py because these spawn real subprocesses; the
sibling module is pure-stdlib with no process side effects and stays that way.

Loads bridge_endpoint.py DIRECTLY by path for the same reason the sibling does:
importing ``synapse.server`` would run its ``__init__`` -> ``.websocket`` ->
``.handlers``, all of which ``import hou``, stranding ``handlers.hou`` for every
later handler test. bridge_endpoint is a pure stdlib leaf, so exec it standalone.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

import pytest

_BE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "python", "synapse", "server", "bridge_endpoint.py",
)
_spec = importlib.util.spec_from_file_location(
    "synapse_bridge_endpoint_pid_probe_under_test", _BE_PATH
)
be = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(be)


# ---------------------------------------------------------------------------
# Regression: _pid_alive must PROBE, never signal.
#
# CPython on Windows implements os.kill() via TerminateProcess(), passing the
# signal number as the process EXIT CODE. os.kill(pid, 0) therefore KILLS pid
# with exit code 0 instead of probing it. The pre-fix implementation used that
# call, so any liveness check terminated the process the sidecar named -- a
# live Houdini in production, and this test module's own pytest runner in CI
# (the run died at item 24 with no traceback on both 3.13 and 3.14).
#
# These pin the behaviour, not the implementation: probing must be observably
# side-effect free.
# ---------------------------------------------------------------------------


def test_pid_alive_does_not_kill_the_probed_process():
    """The load-bearing one: probing a live child must leave it running."""
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert be._pid_alive(proc.pid) is True
        assert be._pid_alive(proc.pid) is True
        assert proc.poll() is None, "_pid_alive terminated the process it probed"
    finally:
        proc.kill()
        proc.wait(timeout=10)


def test_pid_alive_self_is_true_and_non_fatal():
    """Probing our own pid must not terminate the interpreter running the suite."""
    assert be._pid_alive(os.getpid()) is True
    assert be._pid_alive(os.getpid()) is True


def test_pid_alive_exited_process_is_false():
    """A process that has exited reads as dead. Popen holds the handle open, so
    the exit code stays queryable and must not be mistaken for STILL_ACTIVE."""
    proc = subprocess.Popen(
        [sys.executable, "-c", "raise SystemExit(0)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    proc.wait(timeout=15)
    assert be._pid_alive(proc.pid) is False


def test_pid_alive_never_calls_os_kill_on_windows(monkeypatch):
    """Implementation guard: os.kill must not be reachable on nt. Signal
    delivery does not exist on Windows -- any os.kill there is a terminate."""
    if os.name != "nt":
        pytest.skip("nt-only invariant")

    def _forbidden(*_a, **_k):  # pragma: no cover - fails the test if reached
        raise AssertionError("_pid_alive called os.kill() on Windows")

    monkeypatch.setattr(os, "kill", _forbidden)
    assert be._pid_alive(os.getpid()) is True
