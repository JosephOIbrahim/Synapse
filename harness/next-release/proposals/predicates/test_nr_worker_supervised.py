"""Closure predicate for NR-WORKER-SUPERVISED (owner rulings 2026-11-10, D2 behavioural).

Done when RETINA's vision chain runs in a supervised worker through one thin host
adapter:

* ``python/synapse/host/retina_worker.py`` refuses the main thread (I-2), launches the
  interpreter named by ``SYNAPSE_RETINA_WORKER_PYTHON`` (no discovery, D3), and turns a
  worker it had to kill on timeout into an inconclusive result while the child dies
  (D4: 60 s default; injected short here);
* ``retina/worker_entrypoint.py`` takes one request, refuses an op outside the
  allowlist ``{"fireflies"}`` and a product outside the declared read-only roots
  (I-6), and writes one result the adapter validates;
* a result that does not answer this request is inconclusive, never accepted (I-7).

Red when written (on 28e41797): neither file exists, so every test fails with
ModuleNotFoundError when it imports the adapter.

Stock Python only, no environment variable needed: the stock interpreter stands in
for the worker (it has no OpenImageIO, so a scan ends in an honest error result),
and faults come from stand-in commands swapped in through the adapter's
``_worker_argv`` seam. Never launches Houdini, touches a GPU or uses the network.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest


def _repo_root() -> Path:
    """Find the repository root from the working directory, never from this file's
    location, so the predicate keeps working wherever it is moved."""
    here = Path.cwd().resolve()
    for p in (here, *here.parents):
        if (p / ".git").exists() and (p / "harness" / "next-release" / "graph.json").is_file():
            return p
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=60)
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip()).resolve()
    raise AssertionError("repository root not found: run this predicate from inside the SYNAPSE checkout")


ROOT = _repo_root()
for _p in (str(ROOT / "python"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ENV = "SYNAPSE_RETINA_WORKER_PYTHON"


def _adapter():
    import synapse.host.retina_worker as rw

    assert Path(rw.__file__).resolve().is_relative_to(ROOT), (
        f"imported the adapter from {rw.__file__}, not from {ROOT}")
    return rw


def _off_main(fn, *args, **kwargs):
    box = {}

    def target():
        try:
            box["value"] = fn(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 - re-raised below
            box["error"] = exc

    t = threading.Thread(target=target)
    t.start()
    t.join(180)
    assert not t.is_alive()
    if "error" in box:
        raise box["error"]
    return box["value"]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV, sys.executable)
    root = tmp_path / "renders"
    root.mkdir()
    product = root / "beauty.0001.exr"
    product.write_bytes(b"not an exr")
    return root, product, tmp_path


def test_protocol_round_trip(setup):
    root, product, work = setup
    rw = _adapter()
    r = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(work))
    assert r["op"] == "fireflies" and r["request_id"]
    assert r["status"] == "error" and r["pass"] is None and r["reason"], r
    assert r["worker"]["returncode"] == 0
    assert r["check"]["name"] == "firefly_scan" and r["check"]["pass"] is None
    assert r["event"]["tier"] == 1 and r["event"]["verdict"] == "inconclusive"


def test_allowlist_refusal(setup):
    root, product, work = setup
    rw = _adapter()
    r = _off_main(rw.run_worker, "exec_python", str(product), roots=[str(root)], work_dir=str(work))
    assert (r["status"], r["code"], r["pass"]) == ("refused", "op_not_allowed", None), r


def test_root_refusal(setup):
    root, _product, work = setup
    other = work / "elsewhere"
    other.mkdir()
    outside = other / "beauty.exr"
    outside.write_bytes(b"x")
    rw = _adapter()
    r = _off_main(rw.run_fireflies, str(outside), roots=[str(root)], work_dir=str(work))
    assert (r["status"], r["code"], r["pass"]) == ("refused", "outside_roots", None), r


def test_timeout_kills_the_worker(setup, monkeypatch):
    root, product, work = setup
    marker = work / "survived.txt"
    sleeper = ("import pathlib, sys, time\ntime.sleep(3.0)\n"
               "pathlib.Path(sys.argv[1]).write_text('survived')\n")
    rw = _adapter()
    assert rw.DEFAULT_TIMEOUT_S == 60.0
    monkeypatch.setattr(rw, "_worker_argv", lambda python, request: [sys.executable, "-c", sleeper, str(marker)])
    t0 = time.monotonic()
    r = _off_main(rw.run_fireflies, str(product), roots=[str(root)], timeout=0.5, work_dir=str(work))
    assert time.monotonic() - t0 < 2.5
    assert (r["status"], r["code"], r["pass"]) == ("inconclusive", "timeout", None), r
    time.sleep(4.0)
    assert not marker.exists(), "the timed-out worker was not killed"


def test_a_result_for_another_request_is_inconclusive(setup, monkeypatch):
    root, product, work = setup
    writer = (
        "import json, sys\np = sys.argv[1]\nreq = json.load(open(p))\n"
        "c = {'name': 'firefly_scan', 'pass': True, 'detail': 'ok'}\n"
        "json.dump({'protocol': req['protocol'], 'request_id': 'someone-else', 'op': req['op'],"
        " 'status': 'ok', 'code': None, 'pass': True, 'reason': None, 'check': c,"
        " 'event': {'ch': 'perception', 'v': 1, 'tier': 1, 'claim': 'x', 'checks': [c],"
        " 'verdict': 'pass', 'proof': None, 'at': None}, 'mask_path': None},"
        " open(p[:-5] + '.result.json', 'w'))\n"
    )
    rw = _adapter()
    monkeypatch.setattr(rw, "_worker_argv", lambda python, request: [sys.executable, "-c", writer, request])
    r = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(work))
    assert (r["status"], r["code"], r["pass"]) == ("inconclusive", "bad_result", None), r


def test_main_thread_refusal(setup, monkeypatch):
    root, product, work = setup
    rw = _adapter()
    monkeypatch.setattr(rw, "_worker_argv", lambda *a: pytest.fail("launched on the main thread"))
    assert threading.current_thread() is threading.main_thread()
    with pytest.raises(rw.MainThreadRefused):
        rw.run_fireflies(str(product), roots=[str(root)], work_dir=str(work))


def test_unset_worker_reads_not_configured(setup, monkeypatch):
    root, product, work = setup
    monkeypatch.delenv(ENV, raising=False)
    rw = _adapter()
    r = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(work))
    assert (r["status"], r["code"], r["pass"]) == ("inconclusive", "not_configured", None), r
