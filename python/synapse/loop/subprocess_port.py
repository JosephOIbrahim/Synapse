"""Bounded, local substrate IPC. No model calls or package installation."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import threading
import time

from .ports import PortResult


_STDOUT_LIMIT = 1048576
_STDERR_LIMIT = 65536


def _run_bounded(command, data, timeout):
    """Drain both pipes under byte caps, including while the child is running.

    stdin has its own writer so a child that stops reading cannot defeat the
    overall timeout. A budget breach kills this child; it is never retried.
    No reader retains more than its cap plus one fixed 16 KiB read chunk.
    """
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Substrate timeout must be a positive finite duration")
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, bufsize=0,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    deadline = time.monotonic() + timeout
    stdout, stderr = bytearray(), bytearray()
    failure, lock, wake = [], threading.Lock(), threading.Event()

    def fail(message):
        with lock:
            if not failure:
                failure.append(message)
        wake.set()

    def read(stream, captured, limit, name):
        try:
            while True:
                chunk = stream.read(16384)
                if not chunk:
                    return
                remaining = limit - len(captured)
                captured.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    fail(f"{name} exceeds {limit} byte limit")
                    return
        except (OSError, ValueError) as exc:
            fail(f"{name} read failed: {type(exc).__name__}")
        finally:
            stream.close()
            wake.set()

    def write():
        try:
            remaining = memoryview(data)
            while remaining:
                written = process.stdin.write(remaining)
                if not written:
                    raise BrokenPipeError("worker closed input")
                remaining = remaining[written:]
        except BrokenPipeError:
            pass  # The child's exit/status/response explains an early close.
        except (OSError, ValueError) as exc:
            fail(f"stdin write failed: {type(exc).__name__}")
        finally:
            process.stdin.close()
            wake.set()

    threads = [threading.Thread(target=read, args=(process.stdout, stdout, _STDOUT_LIMIT, "stdout"), daemon=True),
        threading.Thread(target=read, args=(process.stderr, stderr, _STDERR_LIMIT, "stderr"), daemon=True),
        threading.Thread(target=write, daemon=True)]
    try:
        for thread in threads:
            thread.start()
        while True:
            with lock:
                if failure:
                    raise RuntimeError(failure[0])
            if process.poll() is not None and all(not thread.is_alive() for thread in threads):
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            wake.wait(min(remaining, .02))
            wake.clear()
        return subprocess.CompletedProcess(command, process.returncode,
            bytes(stdout).decode("utf-8"), bytes(stderr).decode("utf-8", errors="replace"))
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=1)
        for thread in threads:
            if thread.ident is not None:
                thread.join(timeout=1)


class SubstrateWorker:
    """Run the configured source checkouts outside Houdini's Python namespace.

    Octavius currently exports a generic ``src`` package. Importing that into
    the artist's host would collide with other tools. The child uses the USD
    Python shipped with the artist's Houdini, explicitly configured by path.
    """

    def __init__(self, python=None, hanish_root=None, octavius_root=None, timeout=4.0):
        self.python = python or os.environ.get("SYNAPSE_LOOP_PYTHON")
        self.hanish_root = hanish_root or os.environ.get("SYNAPSE_HANISH_ROOT")
        self.octavius_root = octavius_root or os.environ.get("SYNAPSE_OCTAVIUS_ROOT")
        self.timeout = timeout

    def __call__(self, request):
        root = self.octavius_root if request["action"] == "compose" else self.hanish_root
        name = "Octavius" if request["action"] == "compose" else "Hanish"
        if not self.python or not root:
            return PortResult.unavailable(f"{name} worker is not configured")
        if not Path(self.python).is_file() or not Path(root).is_dir():
            return PortResult.unavailable(f"{name} worker paths are unavailable")
        request = dict(request, source_root=str(Path(root).resolve()))
        try:
            encoded = json.dumps(request, sort_keys=True, allow_nan=False)
            if len(encoded.encode("utf-8")) > 262144:
                return PortResult.blocked("Substrate request exceeds 256 KiB")
            process = _run_bounded(
                [self.python, "-I", "-B", str(Path(__file__).with_name("worker.py"))],
                encoded.encode("utf-8"), self.timeout,
            )
            if process.returncode:
                return PortResult.unavailable(f"{name} worker failed: {process.stderr[-1200:]}")
            result = json.loads(process.stdout)
            if result.get("status") not in {"SUCCESS", "UNAVAILABLE", "BLOCKED"}:
                raise ValueError("Invalid substrate response status")
            return PortResult(result["status"], result.get("payload"), result.get("error_message"))
        except Exception as exc:
            return PortResult.unavailable(f"{name} worker did not complete: {exc}")
