"""Hermetic tests for make_contract.py and the R4 seed guard in retina/setup_venv.py.

Every contract test works in a temporary folder with a fake build-lock receipt.
Nothing here creates a venv, runs pip, imports cv2 or OIIO, touches a GPU or uses
the network: the setup_venv tests replace every act (subprocess, venv creation,
rmtree) with a function that fails the test if it is reached.

Not collected by the default suite (pyproject testpaths); run it by path.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CUDA = "D:/toolkits/cuda/v13.3"  # a fixture value, not a claim about any machine


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mc = _load("gpu_worker_env_make_contract", HERE / "make_contract.py")
sv = _load("retina_setup_venv_under_test", REPO / "retina" / "setup_venv.py")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _receipt(**over) -> dict:
    r = {
        "python": {"version": "3.12.10", "abi_tag": "cp312", "limited_api": False},
        "install": {
            "command": "cmake --install <build>",
            "worker_venv": mc.WORKER_VENV,
            "cv2_file": mc.WORKER_VENV + "/Lib/site-packages/cv2/__init__.py",
        },
    }
    r.update(over)
    return r


def _tree(tmp: Path, receipt: dict | None = None, gpu_text: str | None = None) -> Path:
    for rel, text in (
        ("retina/requirements.txt", "pytest>=8\n"),
        ("retina/setup_venv.py", "print('recipe')\n"),
        ("retina/setup_venv.ps1", "Write-Host recipe\n"),
    ):
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
    gpu = tmp / mc.GPU_REQUIREMENTS
    gpu.parent.mkdir(parents=True, exist_ok=True)
    real = (HERE / "requirements-gpu.txt").read_bytes()
    gpu.write_bytes(real if gpu_text is None else gpu_text.encode("utf-8"))
    if receipt is not None:
        rp = tmp / mc.BUILD_LOCK
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_bytes(json.dumps(receipt, indent=2).encode("utf-8"))
    return tmp


def _build(root: Path) -> dict:
    return mc.build_contract(root, cuda_path_at_build=CUDA, check_committed=False)


# --- make_contract.py --------------------------------------------------------


def test_refuses_when_the_build_lock_receipt_is_absent(tmp_path):
    root = _tree(tmp_path)
    with pytest.raises(mc.ContractError, match="build-lock receipt"):
        _build(root)
    # The CLI refuses on the receipt first, before the CUDA argument or any git call.
    assert mc.main(["--root", str(root)]) == 2
    assert not (root / mc.CONTRACT).exists()


def test_contract_carries_every_field_the_predicate_reads(tmp_path):
    root = _tree(tmp_path, _receipt())
    out = mc.write_contract(root, _build(root))
    c = json.loads(out.read_text(encoding="utf-8"))
    # Mirrors test_nr_vg_gpu_worker_env.py field by field.
    assert c["python"] == "3.12.10"
    wheel = c["oiio_wheel"]
    assert wheel.lower().startswith("openimageio") and "cp312" in wheel and "win_amd64" in wheel
    assert str(c["numpy"]).startswith("2.")
    assert c["build_lock_receipt_sha256"] == _sha(root / mc.BUILD_LOCK)
    assert c["gpu_requirements"] == mc.GPU_REQUIREMENTS
    lines = [ln.strip().lower() for ln in (root / c["gpu_requirements"]).read_text(encoding="utf-8").splitlines()]
    assert not [ln for ln in lines if ln and not ln.startswith("#") and ln.startswith("opencv")]
    assert c["recipe_review_sha256"] == {rel: _sha(root / rel) for rel in mc.RECIPE}
    # Beyond the predicate: the DLL policy and the declared worker venv.
    pol = c["cuda_dll_policy"]
    assert pol["cuda_path_at_build"] == CUDA and pol["dll_dir_at_build"] == CUDA + "/bin/x64"
    assert "CUDA_PATH" in pol["launcher_rule"] and "add_dll_directory" in pol["loader"]
    assert c["worker_venv"] == mc.WORKER_VENV
    assert c["gpu_requirements_sha256"] == _sha(root / mc.GPU_REQUIREMENTS)
    assert b"\r" not in out.read_bytes()
    assert not (root / (mc.CONTRACT + ".tmp")).exists()


def test_a_rerun_is_byte_identical(tmp_path):
    root = _tree(tmp_path, _receipt())
    first = mc.write_contract(root, _build(root)).read_bytes()
    assert mc.write_contract(root, _build(root)).read_bytes() == first


def test_worker_venv_comparison_ignores_case_and_slashes(tmp_path):
    v = mc.WORKER_VENV.replace("/", "\\").lower() + "\\"
    inst = {"command": "x", "worker_venv": v, "cv2_file": v + "Lib\\site-packages\\cv2\\__init__.py"}
    _build(_tree(tmp_path, _receipt(install=inst)))


@pytest.mark.parametrize(
    "over, needle",
    [
        ({"python": {"version": "3.12.9"}}, "python.version"),
        ({"python": {"version": "3.14.2"}}, "python.version"),
        ({"python": "3.12.10"}, "python.version"),
        ({"install": {"worker_venv": "E:/elsewhere/venv", "cv2_file": "E:/elsewhere/venv/cv2.pyd"}}, "worker_venv"),
        ({"install": {"worker_venv": mc.WORKER_VENV, "cv2_file": "D:/other/cv2.pyd"}}, "cv2_file"),
        ({"install": {}}, "worker_venv"),
    ],
)
def test_refuses_a_receipt_that_contradicts_r4(tmp_path, over, needle):
    with pytest.raises(mc.ContractError, match=needle):
        _build(_tree(tmp_path, _receipt(**over)))


def test_refuses_a_receipt_that_is_not_json(tmp_path):
    root = _tree(tmp_path, _receipt())
    (root / mc.BUILD_LOCK).write_bytes(b"{not json")
    with pytest.raises(mc.ContractError, match="not valid"):
        _build(root)


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda t: t + "opencv-python-headless==5.0.0.93\n", "stock OpenCV"),
        (lambda t: t + "  OpenCV-Contrib-Python\n", "stock OpenCV"),
        (lambda t: t.replace(mc.OIIO_WHEEL_SHA256, "0" * 64), "lacks the R4 pin"),
        (lambda t: t.replace("numpy==2.4.4", "numpy==2.3.5"), "lacks the R4 pin"),
    ],
)
def test_refuses_gpu_requirements_that_break_the_profile(tmp_path, mutate, needle):
    real = (HERE / "requirements-gpu.txt").read_text(encoding="utf-8")
    with pytest.raises(mc.ContractError, match=needle):
        _build(_tree(tmp_path, _receipt(), gpu_text=mutate(real)))


@pytest.mark.parametrize("bad", ["", "   ", "relative/cuda/v13.3", "D:/users/build/cuda/v13.3", "D:\\Users\\build\\CUDA"])
def test_refuses_a_missing_relative_or_user_cuda_path(tmp_path, bad):
    root = _tree(tmp_path, _receipt())
    with pytest.raises(mc.ContractError, match="cuda-path-at-build"):
        mc.build_contract(root, cuda_path_at_build=bad, check_committed=False)


def test_refuses_pinned_inputs_that_are_not_committed(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")
    root = _tree(tmp_path, _receipt())
    r = subprocess.run(["git", "-C", str(root), "init", "-q"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    bad = mc.uncommitted(root, (mc.BUILD_LOCK, mc.GPU_REQUIREMENTS, *mc.RECIPE))
    assert len(bad) == 5 and all(b.endswith("(not tracked)") for b in bad), bad
    with pytest.raises(mc.ContractError, match="not committed"):
        mc.build_contract(root, cuda_path_at_build=CUDA)
    assert mc.main(["--root", str(root), "--cuda-path-at-build", CUDA]) == 2
    assert not (root / mc.CONTRACT).exists()


def test_the_shipped_gpu_requirements_pass_their_own_check():
    lines = [ln.strip().lower() for ln in (HERE / "requirements-gpu.txt").read_text(encoding="utf-8").splitlines()]
    assert not [ln for ln in lines if ln and not ln.startswith("#") and ln.startswith("opencv")]
    assert mc._check_gpu_requirements(REPO) == _sha(HERE / "requirements-gpu.txt")


# --- retina/setup_venv.py: the R4 seed guard ----------------------------------


def _forbid_acts(monkeypatch, venv_dir: Path) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("setup_venv reached an act the R4 guard must stop first")

    monkeypatch.setattr(sv.subprocess, "run", boom)
    monkeypatch.setattr(sv.subprocess, "check_call", boom)
    monkeypatch.setattr(sv.venv, "create", boom)
    monkeypatch.setattr(sv.shutil, "rmtree", boom)
    monkeypatch.setattr(sv, "_VENV", venv_dir)


@pytest.mark.parametrize("seed", ["hython", "hython.exe", "HYTHON3.13.EXE", "D:/Houdini/bin/hython3.13.exe"])
def test_a_hython_seed_is_refused_by_name(seed):
    assert "hython" in sv.hython_refusal(seed)


@pytest.mark.parametrize("seed", ["python", "python3.12", "D:/Python312/python.exe"])
def test_cpython_seed_names_pass_the_name_check(seed):
    assert sv.hython_refusal(seed) is None


@pytest.mark.parametrize(
    "name, version", [("cpython", (3, 14, 2)), ("cpython", (3, 13, 10)), ("cpython", (3, 11, 9)), ("pypy", (3, 12, 10))]
)
def test_an_interpreter_other_than_cpython_312_is_refused(name, version):
    assert "R4" in sv.version_refusal(name, version)


@pytest.mark.parametrize("version", [(3, 12, 10), (3, 12, 4)])
def test_cpython_312_is_allowed(version):
    assert sv.version_refusal("cpython", version) is None


def test_main_refuses_a_hython_seed_before_running_anything(tmp_path, monkeypatch):
    _forbid_acts(monkeypatch, tmp_path / ".venv")
    assert sv.main(["--python", str(tmp_path / "hython3.13.exe")]) == 2
    assert not (tmp_path / ".venv").exists()


def test_main_refuses_a_default_seed_that_is_not_312(tmp_path, monkeypatch):
    _forbid_acts(monkeypatch, tmp_path / ".venv")
    monkeypatch.setattr(sv, "_running_identity", lambda: ("cpython", (3, 14, 2)))
    assert sv.main([]) == 2


def test_main_refuses_a_probed_seed_that_is_not_312(tmp_path, monkeypatch):
    _forbid_acts(monkeypatch, tmp_path / ".venv")
    monkeypatch.setattr(sv, "_probe", lambda seed: ("cpython", (3, 13, 10)))
    assert sv.main(["--python", str(tmp_path / "python.exe")]) == 2


def test_main_refuses_an_existing_venv_that_is_not_312(tmp_path, monkeypatch):
    v = tmp_path / ".venv"
    v.mkdir()
    (v / "pyvenv.cfg").write_text("home = x\nversion = 3.14.2\n", encoding="utf-8")
    _forbid_acts(monkeypatch, v)
    monkeypatch.setattr(sv, "_running_identity", lambda: ("cpython", (3, 12, 10)))
    assert sv.main([]) == 2


@pytest.mark.parametrize(
    "cfg, want",
    [
        ("home = x\nversion = 3.12.10\n", (3, 12, 10)),
        ("version_info = 3.12.4.final.0\n", (3, 12, 4)),
        ("home = x\n", None),
        ("version = banana\n", None),
    ],
)
def test_pyvenv_cfg_version_is_read(tmp_path, cfg, want):
    (tmp_path / "pyvenv.cfg").write_text(cfg, encoding="utf-8")
    assert sv._venv_version(tmp_path) == want
