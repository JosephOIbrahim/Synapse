"""Detached backend truth, process ownership and immutable-package regressions."""
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from synapse.farm import package
from synapse.farm.backend import NativeTopsBackend
from synapse.farm.models import canonical_plan
from synapse.farm.native_driver import ProcessTree, _cancelled
from synapse.farm.service import FarmService


@pytest.fixture
def plan(tmp_path):
    source = tmp_path / "source.hiplc"
    source.write_bytes(b"source scene bytes")
    return canonical_plan({"request_id": "unit", "source_hip": str(source),
                           "source_node": "/stage/OUT", "frames": [1, 3],
                           "output_root": str(tmp_path / "out")})


def sealed(tmp_path, plan):
    root = tmp_path / "job"
    root.mkdir()
    (root / "graph.hiplc").write_bytes(b"frozen graph")
    (root / "texture.exr").write_bytes(b"immutable texture bytes")
    manifest = package.seal_manifest(root, {"plan_digest": plan["digest"],
        "frames": plan["frames"], "graph": "graph.hiplc",
        "outputs": [{"frame": f, "path": "outputs/{}.exr".format(f)} for f in plan["frames"]],
        "file_paths": ["graph.hiplc", "texture.exr"]})
    return root, manifest


def test_frozen_copy_rejects_source_revision_and_keeps_original(tmp_path):
    source = tmp_path / "source.hip"
    source.write_bytes(b"revision one")
    first = package.file_receipt(source)["sha256"]
    package.frozen_copy(source, tmp_path / "copy.hip", first)
    source.write_bytes(b"revision two")
    with pytest.raises(ValueError, match="changed after"):
        package.frozen_copy(source, tmp_path / "second.hip", first)
    assert (tmp_path / "copy.hip").read_bytes() == b"revision one"
    assert source.read_bytes() == b"revision two"


def test_manifest_binds_every_dependency_and_refuses_tamper(tmp_path, plan):
    root, manifest = sealed(tmp_path, plan)
    assert package.verify_manifest(root, plan, manifest["manifest_digest"])["frames"] == [1, 3]
    (root / "texture.exr").write_bytes(b"different texture data")
    with pytest.raises(ValueError, match="input changed"):
        package.verify_manifest(root, plan, manifest["manifest_digest"])


def test_manifest_refuses_changed_manifest_and_foreign_outputs(tmp_path, plan):
    root, manifest = sealed(tmp_path, plan)
    manifest["outputs"][0]["path"] = "../foreign.exr"
    package.atomic_json(root / "package.json", manifest)
    with pytest.raises(ValueError, match="differs"):
        package.verify_manifest(root, plan, manifest["manifest_digest"])
    with pytest.raises(ValueError, match="leaves"):
        package.owned_path(root, "../foreign.exr")


def test_worker_environment_excludes_model_and_custom_packages(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-sentinel")
    monkeypatch.setenv("PYTHONPATH", "artist-custom-modules")
    monkeypatch.setenv("HOUDINI_PATH", "artist-custom-tools")
    env = package.isolated_environment(tmp_path / "hfs", tmp_path / "runtime")
    assert "OPENAI_API_KEY" not in env and "PYTHONPATH" not in env
    assert env["HOUDINI_PATH"] == "&"
    assert "__HVER__" in env["HOUDINI_USER_PREF_DIR"]
    assert env["HOUDINI_PACKAGE_SKIP"] == "1"


def test_capabilities_never_claim_hqueue_and_limit_local(tmp_path):
    result = NativeTopsBackend(tmp_path).capabilities()
    assert result["profiles"][0]["available"] is False
    assert result["profiles"][1]["available"] is False
    assert result["profiles"][0]["qualification"] == "bounded_preview"
    assert result["profiles"][0]["limits"]["frame_timeout_seconds"] == 60


def test_cancel_before_pid_is_durable_and_prevents_later_launch(tmp_path, plan, monkeypatch):
    backend = NativeTopsBackend(tmp_path)
    monkeypatch.setattr(backend, "capabilities", lambda: {"profiles": [{"available": True}]})
    root = tmp_path / "job"
    root.mkdir()
    result = backend.cancel(plan, root, {"metadata": {}})
    assert result["state"] == "cancel_requested"
    assert package.read_json(root / "cancel-request.json")["plan_digest"] == plan["digest"]
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: pytest.fail("must not launch"))
    assert backend.prepare(plan, root)["state"] == "cancelled"
    assert _cancelled(root / "operation", {"job_dir": str(root), "plan": plan, "token": "new-token"})


def test_cancel_spelling_crosses_real_backend_core_seam(tmp_path, monkeypatch):
    backend = NativeTopsBackend(tmp_path)
    monkeypatch.setattr(backend, "_launch", lambda *a, **kw: {"state": "preparing", "metadata": {}})
    source = tmp_path / "scene.hiplc"
    source.write_bytes(b"not rendered by this contract test")
    service = FarmService(tmp_path / "registry", backend)
    prepared = service.prepare({"request_id": "cancel-seam", "source_hip": str(source),
        "source_node": "/stage/OUT", "frames": [1], "output_root": str(tmp_path / "outputs")})
    result = service.cancel(prepared["request_id"])
    assert result["state"] == "cancel_requested"
    assert (Path(prepared["job_dir"]) / "cancel-request.json").is_file()


def test_lost_process_without_receipt_is_unknown_not_failed(tmp_path, plan, monkeypatch):
    from synapse.farm import backend as module
    operation = tmp_path / "native" / "token"
    operation.mkdir(parents=True)
    package.atomic_json(operation / "config.json", {"token": "token", "plan": plan,
        "phase": "render", "job_dir": str(tmp_path), "timeout_seconds": 60})
    record = {"state": "rendering", "metadata": {"native_operation": "native/token", "native_token": "token",
                "native_phase": "render", "supervisor": {"pid": 9876, "birth": "old"}}}
    monkeypatch.setattr(module, "process_identity", lambda pid: {"pid": pid, "birth": "new", "alive": True})
    assert NativeTopsBackend().poll(plan, tmp_path, record)["state"] == "status_unavailable"


def test_post_popen_identity_error_preserves_admitted_launch(tmp_path, plan, monkeypatch):
    from synapse.farm import backend as module
    backend = NativeTopsBackend(tmp_path)
    monkeypatch.setattr(backend, "capabilities", lambda: {"profiles": [{"available": True}]})
    class Child:
        pid = 4321
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **kw: Child())
    monkeypatch.setattr(module, "process_identity", lambda pid: (_ for _ in ()).throw(OSError("identity unavailable")))
    result = backend.prepare(plan, tmp_path / "job")
    assert result["state"] == "preparing"
    assert result["metadata"]["supervisor"]["pid"] == 4321
    assert result["backend_id"].startswith("local:4321:")


@pytest.mark.parametrize("key,value,message", [("frames", list(range(121)), "1–120"),
    ("width", 2049, "2048"), ("samples", 129, "1–128"), ("profile_id", "hqueue", "HQueue")])
def test_pre_admission_errors_are_actionable_without_launch(tmp_path, plan, monkeypatch, key, value, message):
    plan[key] = value
    plan["digest"] = package.digest({k: v for k, v in plan.items() if k != "digest"})
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: pytest.fail("must not start a process"))
    result = NativeTopsBackend().prepare(plan, tmp_path / "job")
    assert result["state"] == "failed"
    assert message in result["note"]


def recovered_operation(root, token, plan, phase="prepare"):
    operation = root / "native" / token
    operation.mkdir(parents=True)
    package.atomic_json(operation / "config.json", {"token": token, "plan": plan,
        "phase": phase, "job_dir": str(root), "timeout_seconds": 60})
    package.atomic_json(operation / "supervisor.json", {"token": token,
        "plan_digest": plan["digest"], "identity": {"pid": 123, "birth": "past", "alive": False}})
    package.atomic_json(operation / "status.json", {"token": token, "plan_digest": plan["digest"],
        "state": "prepared" if phase == "prepare" else "complete", "note": "Recovered frozen package",
        "metadata": {"package_digest": "bound"}})


def test_new_backend_recovers_exact_admitted_operation_without_metadata(tmp_path, plan, monkeypatch):
    root = tmp_path / "recovered"
    recovered_operation(root, "first", plan)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: pytest.fail("read must not launch"))
    result = NativeTopsBackend().poll(plan, root, {"state": "preparing", "metadata": {}})
    assert result["state"] == "prepared"
    assert result["metadata"]["recovered_from_native_receipt"] is True
    assert result["metadata"]["native_token"] == "first"


def test_ambiguous_admitted_operations_stay_unknown(tmp_path, plan, monkeypatch):
    root = tmp_path / "recovered"
    recovered_operation(root, "first", plan)
    recovered_operation(root, "second", plan)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: pytest.fail("ambiguous recovery must not launch"))
    result = NativeTopsBackend().poll(plan, root, {"state": "preparing", "metadata": {}})
    assert result["state"] == "status_unavailable"
    assert "ambiguous" in result["note"]


def test_lost_submit_ack_recovers_render_instead_of_stale_prepare_metadata(tmp_path, plan, monkeypatch):
    root = tmp_path / "recovered"
    recovered_operation(root, "preparation", plan)
    recovered_operation(root, "rendering", plan, "render")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: pytest.fail("recovery must not relaunch"))
    stale = {"state": "submitting", "submission_attempted": True,
             "metadata": {"native_operation": "native/preparation", "native_token": "preparation",
                          "native_phase": "prepare", "package_digest": "bound"}}
    result = NativeTopsBackend().poll(plan, root, stale)
    assert result["state"] == "complete"
    assert result["metadata"]["native_token"] == "rendering"
    assert result["metadata"]["native_phase"] == "render"
    result = NativeTopsBackend().cancel(plan, root, dict(stale, state="cancel_requested"))
    assert result["state"] == "cancelled"
    assert result["metadata"]["native_token"] == "rendering"
    assert (root / "native/rendering/cancel.json").is_file()
    assert not (root / "native/preparation/cancel.json").exists()


def test_second_possible_launch_without_owner_makes_recovery_ambiguous(tmp_path, plan):
    root = tmp_path / "recovered"
    recovered_operation(root, "first", plan)
    recovered_operation(root, "second", plan)
    (root / "native/second/supervisor.json").unlink()
    result = NativeTopsBackend().poll(plan, root, {"state": "preparing", "metadata": {}})
    assert result["state"] == "status_unavailable"
    assert "ambiguous" in result["note"]


@pytest.mark.parametrize("terminal", ["prepared", "complete", "failed"])
def test_cancel_converges_after_terminal_receipt_without_accepting_outputs(tmp_path, plan, terminal):
    root = tmp_path / "recovered"
    phase = "prepare" if terminal == "prepared" else "render"
    recovered_operation(root, "terminal", plan, phase)
    package.atomic_json(root / "native/terminal/status.json", {"token": "terminal",
        "plan_digest": plan["digest"], "state": terminal, "outputs": [{"frame": 1}],
        "verified_frames": [1], "verification": {"verified": True}})
    result = NativeTopsBackend().cancel(plan, root,
        {"state": "cancel_requested", "submission_attempted": phase == "render", "metadata": {}})
    assert result["state"] == "cancelled"
    assert result["verified_frames"] == [] and result["outputs"] == []
    assert "verification" not in result


@pytest.mark.parametrize("leader_exits", [False, True])
def test_owned_process_tree_termination_does_not_target_other_processes(tmp_path, leader_exits):
    gate, child_pid = tmp_path / "gate", tmp_path / "child.pid"
    script = ("import pathlib,subprocess,sys,time; "
              "gate=pathlib.Path(sys.argv[1]); "
              "\nwhile not gate.exists(): time.sleep(.01)\n"
              "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
              "pathlib.Path(sys.argv[2]).write_text(str(child.pid)); time.sleep(" + ("0" if leader_exits else "30") + ")")
    bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    child = subprocess.Popen([sys.executable, "-c", script, str(gate), str(child_pid)],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), start_new_session=os.name != "nt")
    tree = None
    try:
        tree = ProcessTree(child)
        gate.write_text("owned")
        end = time.monotonic() + 5
        while not child_pid.exists() and time.monotonic() < end:
            time.sleep(.02)
        assert child_pid.is_file()
        leaf = int(child_pid.read_text())
        if leader_exits:
            child.wait(timeout=5)
        tree.stop()
        assert tree.quiescent
        if os.name == "nt":
            assert tree._active_processes() == 0
        tree.close()
        tree = None
        assert child.poll() is not None
        observed = package.process_identity(leaf)
        assert observed is not None and observed["alive"] is False
        assert bystander.poll() is None
    finally:
        if tree is not None:
            tree.stop()
            tree.close()
        elif child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        if bystander.poll() is None:
            bystander.terminate()
        bystander.wait(timeout=5)


def test_quiescence_timeout_is_unknown_and_never_cancelled(tmp_path, plan, monkeypatch):
    from synapse.farm import native_driver as driver
    operation = tmp_path / "native" / "timeout"
    operation.mkdir(parents=True)
    config = {"token": "timeout", "plan": plan, "phase": "render", "job_dir": str(tmp_path),
              "hfs": str(tmp_path / "fake-hfs"), "timeout_seconds": 1}
    package.atomic_json(operation / "config.json", config)
    class Child:
        pid = 4321
        def poll(self):
            return None
    class UnconfirmedTree:
        quiescent = False
        def __init__(self, process):
            pass
        def stop(self):
            raise TimeoutError("A child has not confirmed exit")
        close = stop
        def remember_processes(self):
            pass
    calls = iter([False, True])
    monkeypatch.setattr(driver, "_cancelled", lambda *args: next(calls))
    monkeypatch.setattr(driver, "ProcessTree", UnconfirmedTree)
    monkeypatch.setattr(driver.subprocess, "Popen", lambda *args, **kwargs: Child())
    assert driver.supervise(operation / "config.json") == 1
    status = package.read_json(operation / "status.json")
    assert status["state"] == "status_unavailable"
    assert status["metadata"]["owned_processes_stopped"] is False
    assert status["outputs"] == []
    result = NativeTopsBackend().poll(plan, tmp_path,
        {"state": "cancel_requested", "submission_attempted": True, "metadata": {}})
    assert result["state"] == "status_unavailable"


def test_process_group_wait_has_a_bounded_failure(tmp_path, monkeypatch):
    from types import SimpleNamespace
    tree = ProcessTree.__new__(ProcessTree)
    tree.handle, tree.quiescent = 42, False
    tree.process = SimpleNamespace(wait=lambda timeout: 0)
    tree.process_handles = {}
    tree.kernel = SimpleNamespace(TerminateJobObject=lambda *args: True)
    monkeypatch.setattr(tree, "remember_processes", lambda: None)
    monkeypatch.setattr(tree, "_active_processes", lambda: 1)
    with pytest.raises(TimeoutError, match="every process stopped"):
        tree.stop(timeout=0)
    assert tree.quiescent is False


def test_terminal_poll_reaps_only_owned_completed_children(tmp_path, plan):
    from types import SimpleNamespace
    root = tmp_path / "recovered"
    recovered_operation(root, "first", plan)
    backend = NativeTopsBackend()
    backend._children = {10: SimpleNamespace(poll=lambda: 0),
                         11: SimpleNamespace(poll=lambda: None)}
    result = backend.poll(plan, root, {"state": "preparing", "metadata": {}})
    assert result["state"] == "prepared"
    assert list(backend._children) == [11]
