"""Contract tests for the supervised RETINA worker (NR-WORKER-SUPERVISED).

Two files meet across a process boundary:

* ``retina/worker_entrypoint.py`` runs in the R4 CPU worker interpreter
  (CPython 3.12.10, cv2, numpy, OpenImageIO). It reads one request JSON, runs the
  only allowlisted operation (the firefly scan) on a product inside a declared
  read-only root, and writes one result JSON beside the request.
* ``python/synapse/host/retina_worker.py`` is the thin host adapter: it refuses the
  main thread, launches the interpreter named by ``SYNAPSE_RETINA_WORKER_PYTHON``
  with a timeout and a kill, and validates the result file. Every failure comes
  back as an inconclusive result that says why.

Most tests run on stock Python with ``sys.executable`` as a stand-in worker. Stock
Python has no OpenImageIO, so a scan there ends in an honest ``error`` result; the
refusals (allowlist, roots) happen before any read and are asserted by their
machine-readable ``code``. Faults the real worker never produces (a sleeper, a
garbled result) come from a stand-in command swapped in through the adapter's
``_worker_argv`` seam.

The end-to-end tests at the bottom need the real worker interpreter and are skipped
unless ``SYNAPSE_RETINA_WORKER_PYTHON`` names an existing file.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "python"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ADAPTER_REL = "python/synapse/host/retina_worker.py"
ENTRY_REL = "retina/worker_entrypoint.py"
ENV = "SYNAPSE_RETINA_WORKER_PYTHON"


def _adapter():
    import synapse.host.retina_worker as rw

    return rw


def _off_main(fn, *args, **kwargs):
    """Run ``fn`` on a helper thread (the adapter refuses the main thread)."""
    box = {}

    def target():
        try:
            box["value"] = fn(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller's thread
            box["error"] = exc

    t = threading.Thread(target=target, name="retina-worker-test")
    t.start()
    t.join(180)
    assert not t.is_alive(), "adapter call did not return within 180 s"
    if "error" in box:
        raise box["error"]
    return box["value"]


@pytest.fixture
def stand_in(monkeypatch):
    """The stock interpreter as the configured worker."""
    monkeypatch.setenv(ENV, sys.executable)
    return sys.executable


@pytest.fixture
def frame(tmp_path):
    """A product file inside a root. Its bytes are not an EXR; stock Python never
    gets far enough to notice (no OpenImageIO)."""
    root = tmp_path / "renders"
    root.mkdir()
    product = root / "beauty.0001.exr"
    product.write_bytes(b"not really an exr")
    return root, product


def _assert_inconclusive_check(result):
    check = result["check"]
    assert check["pass"] is None
    assert check["detail"].startswith("inconclusive")


# ---------------------------------------------------------------------------
# Protocol round trip with the stock interpreter as the worker
# ---------------------------------------------------------------------------


def test_round_trip_with_stand_in_worker_returns_a_validated_result(stand_in, frame, tmp_path):
    root, product = frame
    rw = _adapter()
    result = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(tmp_path))
    # The worker ran, wrote a result the adapter accepted, and was honest that it
    # could not read the frame on an interpreter without OpenImageIO.
    assert result["protocol"] == rw.PROTOCOL
    assert result["op"] == "fireflies"
    assert result["status"] == "error", result
    assert result["code"] in ("unavailable", "unreadable"), result
    assert result["pass"] is None
    assert result["reason"]
    assert result["worker"]["returncode"] == 0
    assert result["check"]["name"] == "firefly_scan"
    _assert_inconclusive_check(result)
    event = result["event"]
    assert event["ch"] == "perception" and event["tier"] == 1
    assert event["verdict"] == "inconclusive"
    assert event["checks"] == [result["check"]]
    assert result["mask_path"] is None


def test_request_id_is_fresh_per_call_and_echoed(stand_in, frame, tmp_path):
    root, product = frame
    rw = _adapter()
    a = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(tmp_path))
    b = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(tmp_path))
    assert a["request_id"] and b["request_id"] and a["request_id"] != b["request_id"]


def test_adapter_cleans_up_its_request_and_result_files(stand_in, frame, tmp_path):
    root, product = frame
    work = tmp_path / "work"
    work.mkdir()
    rw = _adapter()
    _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(work))
    assert list(work.iterdir()) == []


# ---------------------------------------------------------------------------
# Allowlist and read-only roots, enforced by the worker
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("op", ["exec_python", "read_any", "FIREFLIES", ""])
def test_worker_refuses_an_op_outside_the_allowlist(stand_in, frame, tmp_path, op):
    root, product = frame
    rw = _adapter()
    result = _off_main(rw.run_worker, op, str(product), roots=[str(root)], work_dir=str(tmp_path))
    assert result["status"] == "refused", result
    assert result["code"] == "op_not_allowed", result
    assert result["pass"] is None
    assert "allowlist" in result["reason"]
    _assert_inconclusive_check(result)


def test_allowlist_is_exactly_fireflies():
    src = (ROOT / ENTRY_REL).read_text(encoding="utf-8")
    tree = ast.parse(src)
    values = None
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == "ALLOWED_OPS" for t in targets):
                values = ast.literal_eval(node.value.args[0] if isinstance(node.value, ast.Call)
                                          else node.value)
    assert values is not None, "ALLOWED_OPS literal not found in the entrypoint"
    assert set(values) == {"fireflies"}


def test_worker_refuses_a_product_outside_every_root(stand_in, tmp_path):
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    inside.mkdir()
    outside.mkdir()
    product = outside / "beauty.exr"
    product.write_bytes(b"x")
    rw = _adapter()
    result = _off_main(rw.run_fireflies, str(product), roots=[str(inside)], work_dir=str(tmp_path))
    assert result["status"] == "refused", result
    assert result["code"] == "outside_roots", result
    assert result["pass"] is None
    _assert_inconclusive_check(result)


def test_worker_refuses_a_dotdot_escape_from_a_root(stand_in, tmp_path):
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    inside.mkdir()
    outside.mkdir()
    (outside / "beauty.exr").write_bytes(b"x")
    sneaky = str(inside) + os.sep + ".." + os.sep + "outside" + os.sep + "beauty.exr"
    rw = _adapter()
    result = _off_main(rw.run_fireflies, sneaky, roots=[str(inside)], work_dir=str(tmp_path))
    assert result["code"] == "outside_roots", result


def test_worker_refuses_a_sibling_whose_name_extends_the_root(stand_in, tmp_path):
    root = tmp_path / "shots"
    sibling = tmp_path / "shots_private"
    root.mkdir()
    sibling.mkdir()
    (sibling / "beauty.exr").write_bytes(b"x")
    rw = _adapter()
    result = _off_main(rw.run_fireflies, str(sibling / "beauty.exr"), roots=[str(root)],
                       work_dir=str(tmp_path))
    assert result["code"] == "outside_roots", result


def test_worker_refuses_a_request_with_no_roots(stand_in, frame, tmp_path):
    _root, product = frame
    rw = _adapter()
    result = _off_main(rw.run_fireflies, str(product), roots=[], work_dir=str(tmp_path))
    assert result["status"] == "refused", result
    assert result["code"] == "bad_request", result


def test_worker_refuses_an_unknown_mask_policy(stand_in, frame, tmp_path):
    root, product = frame
    rw = _adapter()
    result = _off_main(rw.run_worker, "fireflies", str(product), roots=[str(root)],
                       mask="C:/anywhere/mask.png", work_dir=str(tmp_path))
    assert result["status"] == "refused", result
    assert result["code"] == "bad_mask_policy", result


def test_mask_path_is_computed_beside_the_frame():
    sys.path.insert(0, str(ROOT))
    try:
        from retina.worker_entrypoint import mask_path_for
    finally:
        sys.path.remove(str(ROOT))
    frame = os.path.join("C:" + os.sep, "shots", "sh010", "beauty.0001.exr")
    mask = mask_path_for(frame, 0)
    assert os.path.dirname(mask) == os.path.dirname(frame)
    assert os.path.basename(mask) == "beauty.0001.fireflies.png"
    assert os.path.basename(mask_path_for(frame, 2)) == "beauty.0001.sub2.fireflies.png"


# ---------------------------------------------------------------------------
# Supervision: timeout and kill, launch failures, configuration
# ---------------------------------------------------------------------------

_SLEEPER = (
    "import pathlib, sys, time\n"
    "time.sleep(3.0)\n"
    "pathlib.Path(sys.argv[1]).write_text('survived')\n"
)


def test_timeout_kills_the_worker_and_reads_inconclusive(stand_in, frame, tmp_path, monkeypatch):
    root, product = frame
    marker = tmp_path / "survived.txt"
    rw = _adapter()
    monkeypatch.setattr(rw, "_worker_argv",
                        lambda python, request: [sys.executable, "-c", _SLEEPER, str(marker)])
    t0 = time.monotonic()
    result = _off_main(rw.run_fireflies, str(product), roots=[str(root)], timeout=0.5,
                       work_dir=str(tmp_path))
    elapsed = time.monotonic() - t0
    assert result["status"] == "inconclusive", result
    assert result["code"] == "timeout", result
    assert result["pass"] is None
    assert "timed out" in result["reason"]
    _assert_inconclusive_check(result)
    assert elapsed < 2.5, f"adapter waited {elapsed:.2f} s for a worker it should have killed"
    # The child was killed, not abandoned: it never reaches its write.
    time.sleep(4.0)
    assert not marker.exists(), "the timed-out worker kept running after the adapter returned"


def test_default_timeout_is_sixty_seconds():
    assert _adapter().DEFAULT_TIMEOUT_S == 60.0


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), True, "60"])
def test_timeout_must_be_a_positive_finite_number(stand_in, frame, tmp_path, bad):
    root, product = frame
    rw = _adapter()
    with pytest.raises(ValueError):
        _off_main(rw.run_fireflies, str(product), roots=[str(root)], timeout=bad,
                  work_dir=str(tmp_path))


def test_unset_env_var_reads_not_configured(frame, tmp_path, monkeypatch):
    root, product = frame
    monkeypatch.delenv(ENV, raising=False)
    rw = _adapter()
    monkeypatch.setattr(rw, "_worker_argv", lambda *a: pytest.fail("launched without a worker"))
    result = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(tmp_path))
    assert result["status"] == "inconclusive"
    assert result["code"] == "not_configured"
    assert ENV in result["reason"]
    assert result["pass"] is None
    _assert_inconclusive_check(result)


def test_env_var_naming_a_missing_file_reads_not_configured(frame, tmp_path, monkeypatch):
    root, product = frame
    monkeypatch.setenv(ENV, str(tmp_path / "no" / "python.exe"))
    rw = _adapter()
    result = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(tmp_path))
    assert result["code"] == "not_configured", result


def test_no_interpreter_discovery_from_path(frame, tmp_path, monkeypatch):
    """A bare name is not resolved through PATH (owner ruling D3): only an explicit
    path to an existing file configures the worker."""
    root, product = frame
    monkeypatch.setenv(ENV, "python")
    rw = _adapter()
    result = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(tmp_path))
    assert result["code"] == "not_configured", result


def test_a_worker_that_cannot_start_reads_inconclusive(stand_in, frame, tmp_path, monkeypatch):
    root, product = frame
    rw = _adapter()
    monkeypatch.setattr(rw, "_worker_argv",
                        lambda python, request: [str(tmp_path / "missing.exe"), request])
    result = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(tmp_path))
    assert result["status"] == "inconclusive"
    assert result["code"] == "launch_failed", result


def test_a_worker_flooding_stdout_is_killed(stand_in, frame, tmp_path, monkeypatch):
    root, product = frame
    rw = _adapter()
    flood = "import sys\nwhile True:\n    sys.stdout.write('x' * 65536)\n"
    monkeypatch.setattr(rw, "_worker_argv",
                        lambda python, request: [sys.executable, "-c", flood])
    result = _off_main(rw.run_fireflies, str(product), roots=[str(root)], timeout=20,
                       work_dir=str(tmp_path))
    assert result["status"] == "inconclusive"
    assert result["code"] == "output_limit", result


# ---------------------------------------------------------------------------
# Result validation: a missing, late or garbled result is inconclusive
# ---------------------------------------------------------------------------

_WRITER = r'''
import json, os, sys
request_path, mode = sys.argv[1], sys.argv[2]
req = json.load(open(request_path, encoding="utf-8"))
base = request_path[:-len(".json")] if request_path.endswith(".json") else request_path
out = base + ".result.json"
check = {"name": "firefly_scan", "pass": True, "detail": "no fireflies above 6.0 local sigma"}
event = {"ch": "perception", "v": 1, "tier": 1, "claim": "firefly scan", "checks": [check],
         "verdict": "pass", "proof": None, "at": req.get("now")}
good = {"protocol": req["protocol"], "request_id": req["request_id"], "op": req["op"],
        "status": "ok", "code": None, "pass": True, "reason": None, "check": check,
        "event": event, "mask_path": None}
if mode == "none":
    sys.exit(0)
if mode == "notjson":
    open(out, "w").write("{this is not json")
    sys.exit(0)
if mode == "list":
    json.dump([good], open(out, "w"))
    sys.exit(0)
bad = dict(good)
if mode == "wrong_id":
    bad["request_id"] = "someone-else"
elif mode == "wrong_protocol":
    bad["protocol"] = "other/9"
elif mode == "wrong_op":
    bad["op"] = "exec_python"
elif mode == "pass_str":
    bad["pass"] = "yes"
elif mode == "pass_int":
    bad["pass"] = 1
elif mode == "no_check":
    del bad["check"]
elif mode == "no_event":
    bad["event"] = None
elif mode == "check_disagrees":
    bad["check"] = dict(check, **{"pass": False})
elif mode == "event_disagrees":
    bad["event"] = dict(event, verdict="fail")
elif mode == "event_tier0":
    bad["event"] = dict(event, tier=0)
elif mode == "event_other_checks":
    bad["event"] = dict(event, checks=[])
elif mode == "refused_but_passed":
    bad["status"] = "refused"
    bad["code"] = "op_not_allowed"
elif mode == "none_without_reason":
    bad["pass"] = None
    bad["check"] = dict(check, **{"pass": None, "detail": "inconclusive: x"})
    bad["event"] = dict(event, checks=[bad["check"]], verdict="inconclusive")
elif mode == "mask_elsewhere":
    bad["mask_path"] = os.path.join(os.path.dirname(out), "elsewhere", "m.png")
elif mode == "exit3":
    json.dump(good, open(out, "w"))
    sys.exit(3)
json.dump(bad if mode != "good" else good, open(out, "w"))
'''


def _with_writer(rw, monkeypatch, mode):
    monkeypatch.setattr(rw, "_worker_argv",
                        lambda python, request: [sys.executable, "-c", _WRITER, request, mode])


def test_a_well_formed_result_is_accepted(stand_in, frame, tmp_path, monkeypatch):
    """Positive control for the validator below: the stand-in writer's good result."""
    root, product = frame
    rw = _adapter()
    _with_writer(rw, monkeypatch, "good")
    result = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(tmp_path))
    assert result["status"] == "ok", result
    assert result["pass"] is True
    assert result["reason"] is None


@pytest.mark.parametrize("mode,code", [
    ("none", "no_result"),
    ("notjson", "bad_result"),
    ("list", "bad_result"),
    ("wrong_id", "bad_result"),
    ("wrong_protocol", "bad_result"),
    ("wrong_op", "bad_result"),
    ("pass_str", "bad_result"),
    ("pass_int", "bad_result"),
    ("no_check", "bad_result"),
    ("no_event", "bad_result"),
    ("check_disagrees", "bad_result"),
    ("event_disagrees", "bad_result"),
    ("event_tier0", "bad_result"),
    ("event_other_checks", "bad_result"),
    ("refused_but_passed", "bad_result"),
    ("none_without_reason", "bad_result"),
    ("mask_elsewhere", "bad_result"),
    ("exit3", "worker_exit"),
])
def test_a_missing_or_garbled_result_reads_inconclusive(stand_in, frame, tmp_path, monkeypatch,
                                                       mode, code):
    root, product = frame
    rw = _adapter()
    _with_writer(rw, monkeypatch, mode)
    result = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(tmp_path))
    assert result["status"] == "inconclusive", result
    assert result["code"] == code, result
    assert result["pass"] is None
    assert result["reason"]
    assert result["event"] is None
    _assert_inconclusive_check(result)


def test_a_deeply_nested_result_reads_inconclusive_not_an_exception(stand_in, frame, tmp_path,
                                                                     monkeypatch):
    """Under the size cap but deep enough that json.load raises RecursionError."""
    root, product = frame
    rw = _adapter()
    deep = (
        "import sys\n"
        "p = sys.argv[1]\n"
        "open(p[:-len('.json')] + '.result.json', 'w').write('[' * 200000)\n"
    )
    monkeypatch.setattr(rw, "_worker_argv",
                        lambda python, request: [sys.executable, "-c", deep, request])
    result = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(tmp_path))
    assert result["status"] == "inconclusive", result
    assert result["code"] == "bad_result", result


def test_an_unusable_work_dir_reads_inconclusive_not_an_exception(stand_in, frame, tmp_path,
                                                                  monkeypatch):
    root, product = frame
    rw = _adapter()
    monkeypatch.setattr(rw, "_worker_argv", lambda *a: pytest.fail("launched without a request"))
    result = _off_main(rw.run_fireflies, str(product), roots=[str(root)],
                       work_dir=str(tmp_path / "does" / "not" / "exist"))
    assert result["status"] == "inconclusive", result
    assert result["code"] == "request_failed", result
    assert result["pass"] is None and result["reason"]
    _assert_inconclusive_check(result)


def test_a_result_larger_than_the_cap_is_refused(stand_in, frame, tmp_path, monkeypatch):
    root, product = frame
    rw = _adapter()
    big = (
        "import sys\n"
        "p = sys.argv[1]\n"
        "open(p[:-len('.json')] + '.result.json', 'w').write(' ' * (8 * 1024 * 1024) + '{}')\n"
    )
    monkeypatch.setattr(rw, "_worker_argv",
                        lambda python, request: [sys.executable, "-c", big, request])
    result = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(tmp_path))
    assert result["code"] == "bad_result", result


# ---------------------------------------------------------------------------
# Main-thread refusal (I-2)
# ---------------------------------------------------------------------------


def test_main_thread_call_is_refused_before_anything_runs(stand_in, frame, tmp_path, monkeypatch):
    root, product = frame
    rw = _adapter()
    assert threading.current_thread() is threading.main_thread()
    monkeypatch.setattr(rw, "_worker_argv", lambda *a: pytest.fail("launched on the main thread"))
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(rw.MainThreadRefused):
        rw.run_fireflies(str(product), roots=[str(root)], work_dir=str(work))
    with pytest.raises(rw.MainThreadRefused):
        rw.run_worker("fireflies", str(product), roots=[str(root)], work_dir=str(work))
    assert list(work.iterdir()) == [], "the refused call wrote a request file"
    assert issubclass(rw.MainThreadRefused, RuntimeError)


# ---------------------------------------------------------------------------
# Import boundaries (I-1): pixels and binaries stay on the worker side
# ---------------------------------------------------------------------------


def _imports(rel):
    tree = ast.parse((ROOT / rel).read_bytes(), filename=rel)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(("." * node.level) + (node.module or ""))
    return names


def test_adapter_imports_only_the_standard_library():
    stdlib = set(sys.stdlib_module_names) | set(sys.builtin_module_names)
    names = _imports(ADAPTER_REL)
    tops = {n.lstrip(".").partition(".")[0] for n in names}
    assert not any(n.startswith(".") for n in names), names
    assert tops <= stdlib, f"non-stdlib imports in the adapter: {sorted(tops - stdlib)}"
    assert not tops & {"cv2", "retina", "hou", "numpy", "OpenImageIO"}
    assert "importlib" not in tops


def test_entrypoint_never_imports_synapse_or_hou():
    names = _imports(ENTRY_REL)
    tops = {n.lstrip(".").partition(".")[0] for n in names}
    assert "synapse" not in tops and "hou" not in tops, names


def test_entrypoint_loads_frame_and_scan_modules_lazily():
    """Refusals must not depend on cv2/OIIO being importable: the frame reader and
    the scan are imported inside the operation, not at module import."""
    tree = ast.parse((ROOT / ENTRY_REL).read_bytes())
    top = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            top |= {f"{node.module}.{a.name}" for a in node.names} | {node.module or ""}
        elif isinstance(node, ast.Import):
            top |= {a.name for a in node.names}
    assert not any("frame_reader" in n or "firefly_scan" in n for n in top), top


# ---------------------------------------------------------------------------
# End to end on the real R4 worker interpreter
# ---------------------------------------------------------------------------

_WORKER_PY = os.environ.get(ENV, "")
_HAVE_WORKER = bool(_WORKER_PY) and os.path.isfile(_WORKER_PY)
real_worker = pytest.mark.skipif(not _HAVE_WORKER, reason=f"{ENV} does not name a worker interpreter")

# Run BY the worker interpreter: stock Python has no OpenImageIO to write an EXR.
# A 64x48 RGBA half part whose data window sits at (10, 7) inside a 96x80 display
# window; seeded 0.18 +- 0.01 grey noise (the tests/test_retina_fireflies.py recipe)
# and, in "firefly" mode, one hot pixel at array (20, 15) = frame (30, 22).
_EXR_WRITER = r'''
import sys
import numpy as np
import OpenImageIO as oiio
path, mode = sys.argv[1], sys.argv[2]
w, h = 64, 48
rng = np.random.default_rng(20261007)
grey = (0.18 + rng.normal(0.0, 0.01, size=(h, w, 1))).astype(np.float32)
rgba = np.concatenate([np.repeat(grey, 3, axis=2), np.ones((h, w, 1), np.float32)], axis=2)
if mode == "firefly":
    rgba[15, 20, :3] = 4.0
spec = oiio.ImageSpec(w, h, 4, "half")
spec.channelnames = ("R", "G", "B", "A")
spec.alpha_channel = 3
spec.x, spec.y = 10, 7
spec.full_x, spec.full_y, spec.full_width, spec.full_height = 0, 0, 96, 80
out = oiio.ImageOutput.create(path)
if out is None or not out.open(path, spec):
    raise SystemExit("cannot open for writing: " + oiio.geterror())
if not out.write_image(np.ascontiguousarray(rgba)):
    raise SystemExit("write failed: " + out.geterror())
out.close()
'''


def _write_exr(path, mode):
    proc = subprocess.run([_WORKER_PY, "-E", "-s", "-c", _EXR_WRITER, str(path), mode],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert path.is_file()


@real_worker
def test_real_worker_finds_a_planted_firefly_at_its_frame_position(tmp_path):
    root = tmp_path / "renders"
    root.mkdir()
    product = root / "beauty.0001.exr"
    _write_exr(product, "firefly")
    rw = _adapter()
    result = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(tmp_path))
    assert result["status"] == "ok", result
    assert result["pass"] is False, result
    check = result["check"]
    assert check["count"] == 1, check
    assert check["frame_position"] == [30, 22], check
    assert check["array_position"] == [20, 15], check
    assert check["origin"] == [10, 7]
    assert check["reader"] == "retina.frame_reader"
    mask = Path(result["mask_path"])
    assert mask.is_file()
    assert mask.parent == product.parent
    assert mask.name == "beauty.0001.fireflies.png"
    assert result["event"]["verdict"] == "fail"
    assert result["event"]["proof"] == str(mask)


@real_worker
def test_real_worker_passes_a_clean_frame(tmp_path):
    root = tmp_path / "renders"
    root.mkdir()
    product = root / "clean.0001.exr"
    _write_exr(product, "clean")
    rw = _adapter()
    result = _off_main(rw.run_fireflies, str(product), roots=[str(root)], work_dir=str(tmp_path))
    assert result["status"] == "ok", result
    assert result["pass"] is True, result
    assert result["check"]["count"] == 0
    assert result["event"]["verdict"] == "pass"
    assert Path(result["mask_path"]).parent == product.parent


@real_worker
def test_real_worker_refuses_outside_roots_before_reading(tmp_path):
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    inside.mkdir()
    outside.mkdir()
    product = outside / "beauty.exr"
    _write_exr(product, "firefly")
    rw = _adapter()
    result = _off_main(rw.run_fireflies, str(product), roots=[str(inside)], work_dir=str(tmp_path))
    assert result["code"] == "outside_roots", result
    assert not (outside / "beauty.fireflies.png").exists()
