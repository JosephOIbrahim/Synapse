"""Thin host adapter for the supervised RETINA worker (NR-WORKER-SUPERVISED).

The host never touches pixels. This module writes a small request JSON, launches
the R4 CPU worker interpreter on ``retina/worker_entrypoint.py`` under a timeout,
kills it when the timeout passes, and validates the one result JSON the worker
writes beside the request. Only paths and small JSON cross the boundary (I-3).

Invariants:

* **I-1** Standard library only: no ``cv2``, no ``numpy``, no ``retina`` module,
  no ``hou``. The protocol constants below are copies of the worker's, kept in
  step by ``tests/test_retina_worker_contract.py``.
* **I-2** Refuses the main thread. A call on ``threading.main_thread()`` (Houdini's
  UI thread) raises :class:`MainThreadRefused` before anything is written or
  launched. Raising, not returning inconclusive, because the call is a caller bug
  that would block the UI for up to the timeout; it must fail loudly in
  development, not read as "the scan could not run".
* **D3** The interpreter is ``SYNAPSE_RETINA_WORKER_PYTHON``, an explicit path to an
  existing file. Unset, or not an existing file (a bare ``python`` included):
  inconclusive ``not_configured``. Nothing is discovered.
* **D4** Default timeout :data:`DEFAULT_TIMEOUT_S` (60 s), a safety bound, not a
  QC time budget.
* **I-7** A worker that cannot start, times out, floods its pipes, exits non-zero,
  or leaves a missing, oversized or garbled result gives an inconclusive result
  that says why. Only :class:`MainThreadRefused` and a bad ``timeout`` argument
  raise.

The worker runs as ``<python> -E -s -B -m retina.worker_entrypoint <request>`` with
the repository root (found from this file) as its working directory. ``-E``
ignores ``PYTHONPATH``/``PYTHONHOME``, which inside Houdini point at Houdini's own
Python; ``-s`` drops the user site; ``-B`` writes no bytecode into the tree.
(``-I`` is not used: it implies ``-P``, which removes the working directory from
``sys.path`` and with it ``retina``.)

Returned dict (also the shape of an adapter-side inconclusive)::

    {"protocol", "request_id", "op",
     "status": "ok"|"refused"|"error"|"inconclusive",
     "code": <str or None>, "pass": True|False|None, "reason": <str or None>,
     "check": {"name", "pass", "detail", ...}, "event": <tier-1 event or None>,
     "mask_path": <str or None>,
     "worker": {"python", "returncode", "elapsed_s", "stderr_tail"}}

``refused`` and ``error`` come from the worker; ``inconclusive`` from this adapter.
``event`` is None when the adapter, not the worker, wrote the result (it imports no
``retina`` module to build one); ``check`` is always present so a caller can roll it
up.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

#: Environment variable naming the worker interpreter (owner ruling D3).
ENV_VAR = "SYNAPSE_RETINA_WORKER_PYTHON"

#: Protocol tag; must equal ``retina.worker_entrypoint.PROTOCOL``.
PROTOCOL = "synapse.retina.worker/1"

#: Worker module, run with ``-m`` from the repository root.
WORKER_MODULE = "retina.worker_entrypoint"

#: Safety bound on one worker run, seconds (owner ruling D4).
DEFAULT_TIMEOUT_S = 60.0

#: Check names per op; must match the worker's ``CHECK_NAMES``.
CHECK_NAMES = {"fireflies": "firefly_scan"}

_STDOUT_LIMIT = 64 * 1024
_STDERR_LIMIT = 64 * 1024
_RESULT_LIMIT = 4 * 1024 * 1024
_STDERR_TAIL = 2000

_WORKER_STATUSES = ("ok", "refused", "error")
_VERDICTS = {True: "pass", False: "fail", None: "inconclusive"}

# python/synapse/host/retina_worker.py -> the repository root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class MainThreadRefused(RuntimeError):
    """The adapter was called on the main thread (I-2)."""


def _worker_argv(python: str, request_path: str) -> List[str]:
    """The worker command line. A seam: tests swap in stand-in commands."""
    return [python, "-E", "-s", "-B", "-m", WORKER_MODULE, request_path]


def _result_path_for(request_path: str) -> str:
    """Mirror of ``retina.worker_entrypoint.result_path_for``."""
    base = request_path[: -len(".json")] if request_path.lower().endswith(".json") else request_path
    return base + ".result.json"


def _check_name(op: str) -> str:
    return CHECK_NAMES.get(op, op or "worker")


def _inconclusive(request_id: str, op: str, code: str, reason: str,
                  worker: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "op": op,
        "status": "inconclusive",
        "code": code,
        "pass": None,
        "reason": reason,
        "check": {"name": _check_name(op), "pass": None, "detail": f"inconclusive: {reason}"},
        "event": None,
        "mask_path": None,
        "worker": worker,
    }


def _same_dir(a: str, b: str) -> bool:
    def norm(p: str) -> str:
        return os.path.normcase(os.path.dirname(os.path.realpath(p)))

    return norm(a) == norm(b)


def _validate_result(raw: Any, request_id: str, op: str, product: str) -> Optional[str]:
    """Why ``raw`` is not a valid answer to this request, or None when it is."""
    if not isinstance(raw, dict):
        return f"result is a JSON {type(raw).__name__}, not an object"
    if raw.get("protocol") != PROTOCOL:
        return f"result protocol {raw.get('protocol')!r} is not {PROTOCOL!r}"
    if raw.get("request_id") != request_id:
        return f"result answers request {raw.get('request_id')!r}, not {request_id!r}"
    if raw.get("op") != op:
        return f"result is for op {raw.get('op')!r}, not {op!r}"
    status = raw.get("status")
    if status not in _WORKER_STATUSES:
        return f"result status {status!r} is not one of {list(_WORKER_STATUSES)}"
    passed = raw.get("pass", "missing")
    if not (passed is True or passed is False or passed is None):
        return f"result pass {passed!r} is not true, false or null"
    reason = raw.get("reason")
    if passed is None:
        if not isinstance(reason, str) or not reason:
            return "result pass is null without a reason"
    elif reason is not None:
        return "result carries a reason with a pass/fail verdict"
    code = raw.get("code")
    if code is not None and not isinstance(code, str):
        return f"result code {code!r} is not a string"
    if status != "ok" and (passed is not None or not code):
        return f"a {status} result must have pass null and a code"
    check = raw.get("check")
    if not isinstance(check, dict):
        return "result has no check"
    if not isinstance(check.get("name"), str) or not isinstance(check.get("detail"), str):
        return "result check lacks a name or detail"
    if "pass" not in check or check["pass"] is not passed:
        return f"result check pass {check.get('pass')!r} disagrees with result pass {passed!r}"
    event = raw.get("event")
    if not isinstance(event, dict):
        return "result has no event"
    if event.get("ch") != "perception" or event.get("tier") != 1:
        return f"result event is not a tier-1 perception event (ch {event.get('ch')!r}, tier {event.get('tier')!r})"
    if event.get("checks") != [check]:
        return "result event does not carry exactly the result's check"
    if event.get("verdict") != _VERDICTS[passed]:
        return f"result event verdict {event.get('verdict')!r} disagrees with pass {passed!r}"
    mask = raw.get("mask_path")
    if mask is not None:
        if not isinstance(mask, str) or status != "ok":
            return "result mask_path is not a string on an ok result"
        if not _same_dir(mask, product):
            return f"result mask {mask!r} is not beside the frame {product!r}"
    return None


def _launch(argv: List[str], cwd: str, timeout: float) -> Dict[str, Any]:
    """Run ``argv`` with bounded pipes and a hard deadline (the pattern of
    ``synapse.loop.subprocess_port._run_bounded``, copied, not imported).

    Returns ``{"returncode", "stderr", "failure"}``; ``failure`` is None or one of
    ``("timeout", why)``, ``("output_limit", why)``, ``("launch_failed", why)``.
    The child is killed on every path that leaves it running.
    """
    try:
        process = subprocess.Popen(
            argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, ValueError) as exc:
        return {"returncode": None, "stderr": "",
                "failure": ("launch_failed", f"worker could not start: {type(exc).__name__}: {exc}")}
    deadline = time.monotonic() + timeout
    stdout, stderr = bytearray(), bytearray()
    failure: List[Any] = []
    lock, wake = threading.Lock(), threading.Event()

    def fail(code: str, message: str) -> None:
        with lock:
            if not failure:
                failure.append((code, message))
        wake.set()

    def read(stream: Any, captured: bytearray, limit: int, name: str) -> None:
        try:
            while True:
                chunk = stream.read(16384)
                if not chunk:
                    return
                remaining = limit - len(captured)
                captured.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    fail("output_limit", f"worker {name} exceeds {limit} byte limit; killed")
                    return
        except (OSError, ValueError) as exc:
            fail("output_limit", f"worker {name} read failed: {type(exc).__name__}")
        finally:
            stream.close()
            wake.set()

    threads = [
        threading.Thread(target=read, args=(process.stdout, stdout, _STDOUT_LIMIT, "stdout"), daemon=True),
        threading.Thread(target=read, args=(process.stderr, stderr, _STDERR_LIMIT, "stderr"), daemon=True),
    ]
    try:
        for thread in threads:
            thread.start()
        while True:
            with lock:
                if failure:
                    break
            if process.poll() is not None and all(not t.is_alive() for t in threads):
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                fail("timeout", f"worker timed out after {timeout:g} s; killed")
                break
            wake.wait(min(remaining, 0.02))
            wake.clear()
    finally:
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        for thread in threads:
            if thread.ident is not None:
                thread.join(timeout=1)
    return {
        "returncode": process.returncode,
        "stderr": bytes(stderr).decode("utf-8", errors="replace"),
        "failure": failure[0] if failure else None,
    }


def run_worker(op: str, product: str, *, roots: Sequence[str], subimage: int = 0,
               mask: str = "beside_frame", timeout: float = DEFAULT_TIMEOUT_S,
               work_dir: Optional[str] = None) -> Dict[str, Any]:
    """Run one worker request and return the validated result (module docstring).

    ``op`` is passed through unchanged: the worker owns the allowlist and refuses
    anything outside it. ``roots`` are the read-only roots the product must resolve
    inside. ``work_dir`` holds a per-call directory for the request and result
    (default: the system temp directory); it is removed afterwards. The mask, when
    the policy is ``beside_frame``, is written beside the frame and kept.

    Raises :class:`MainThreadRefused` on the main thread and :class:`ValueError`
    for a ``timeout`` that is not a positive finite number.
    """
    if threading.current_thread() is threading.main_thread():
        raise MainThreadRefused(
            "the RETINA worker adapter blocks for up to its timeout and refuses the main "
            "thread (I-2); call it from a worker thread")
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout) or timeout <= 0):
        raise ValueError(f"timeout must be a positive finite number of seconds, got {timeout!r}")

    request_id = uuid.uuid4().hex
    started = time.monotonic()
    worker: Dict[str, Any] = {"python": None, "returncode": None, "elapsed_s": 0.0, "stderr_tail": ""}

    def done(result: Dict[str, Any]) -> Dict[str, Any]:
        worker["elapsed_s"] = round(time.monotonic() - started, 3)
        return result

    python = os.environ.get(ENV_VAR, "")
    worker["python"] = python or None
    if not python or not os.path.isabs(python) or not os.path.isfile(python):
        return done(_inconclusive(
            request_id, op, "not_configured",
            f"worker not configured: {ENV_VAR} must name an existing interpreter by absolute "
            f"path (got {python!r}); no interpreter is discovered", worker))
    entry = os.path.join(_REPO_ROOT, *WORKER_MODULE.split(".")) + ".py"
    if not os.path.isfile(entry):
        return done(_inconclusive(request_id, op, "entrypoint_missing",
                                  f"worker entrypoint not found at {entry}", worker))

    product_abs = os.path.abspath(os.fspath(product))
    request = {
        "protocol": PROTOCOL,
        "request_id": request_id,
        "op": op,
        "product": product_abs,
        "subimage": subimage,
        "roots": [os.path.abspath(os.fspath(r)) for r in roots],
        "mask": mask,
        "now": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    call_dir = tempfile.mkdtemp(prefix="retina-worker-", dir=work_dir)
    try:
        request_path = os.path.join(call_dir, f"request-{request_id}.json")
        result_path = _result_path_for(request_path)
        with open(request_path, "w", encoding="utf-8") as fh:
            json.dump(request, fh)

        run = _launch(_worker_argv(python, request_path), _REPO_ROOT, float(timeout))
        worker["returncode"] = run["returncode"]
        worker["stderr_tail"] = run["stderr"][-_STDERR_TAIL:]
        if run["failure"] is not None:
            code, why = run["failure"]
            return done(_inconclusive(request_id, op, code, why, worker))
        if run["returncode"] != 0:
            tail = worker["stderr_tail"].strip().splitlines()[-1:] or [""]
            return done(_inconclusive(
                request_id, op, "worker_exit",
                f"worker exited with status {run['returncode']}: {tail[0]}", worker))
        if not os.path.isfile(result_path):
            return done(_inconclusive(request_id, op, "no_result",
                                      "worker exited 0 without writing a result", worker))
        size = os.path.getsize(result_path)
        if size > _RESULT_LIMIT:
            return done(_inconclusive(request_id, op, "bad_result",
                                      f"result is {size} bytes, over the {_RESULT_LIMIT} byte cap", worker))
        try:
            with open(result_path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError) as exc:
            return done(_inconclusive(request_id, op, "bad_result",
                                      f"result is not readable JSON: {type(exc).__name__}: {exc}", worker))
        why = _validate_result(raw, request_id, op, product_abs)
        if why is not None:
            return done(_inconclusive(request_id, op, "bad_result", why, worker))
        result = {key: raw[key] for key in
                  ("protocol", "request_id", "op", "status", "code", "pass", "reason",
                   "check", "event", "mask_path")}
        result["worker"] = worker
        return done(result)
    finally:
        shutil.rmtree(call_dir, ignore_errors=True)


def run_fireflies(product: str, *, roots: Sequence[str], subimage: int = 0,
                  timeout: float = DEFAULT_TIMEOUT_S,
                  work_dir: Optional[str] = None) -> Dict[str, Any]:
    """The firefly scan of one EXR part in the worker; mask written beside the frame."""
    return run_worker("fireflies", product, roots=roots, subimage=subimage,
                      mask="beside_frame", timeout=timeout, work_dir=work_dir)


__all__ = [
    "ENV_VAR",
    "PROTOCOL",
    "WORKER_MODULE",
    "DEFAULT_TIMEOUT_S",
    "MainThreadRefused",
    "run_worker",
    "run_fireflies",
]
