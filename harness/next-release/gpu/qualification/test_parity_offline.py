"""Offline tests for the NR-GPU-QUALIFICATION parity tooling (fixtures.py, parity.py).

Hermetic: no cv2 call, no GPU, no network, nothing written outside pytest's tmp_path. The fakes
below stand in for retina.t1 and retina.backend_cuda: the tooling is under test, not the chain,
and the default interpreter's cv2 is never an oracle. The draft predicate is run against
temporary copies in a throwaway git repository, never against this repository's paths.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import itertools
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PREDICATE = HERE.parent / "test_qualification_contract.py"
AMENDMENT = REPO / "harness" / "next-release" / "proposals" / "vision-grow.amendment.PROPOSED.json"
_SEQ = itertools.count()


def _load(path: Path, *, register: bool = True):
    name = f"nr_gpu_qualification_{path.stem}_{next(_SEQ)}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    if register:
        sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


parity = _load(HERE / "parity.py")
fx = parity.load_fixtures()


def _draft_constants() -> dict:
    """Module-level constants of the committed draft predicate, read with ast, never executed."""
    wanted = {"MARKER", "RECEIPT", "PROFILE", "BUILD_LOCK", "R2_OPS",
              "G0_PROPOSED_FIXTURES", "INFERENCE_FIXTURES"}
    out = {}
    for node in ast.parse(PREDICATE.read_text(encoding="utf-8")).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id in wanted):
            out[node.targets[0].id] = ast.literal_eval(node.value)
    assert set(out) == wanted, f"draft predicate constants missing: {sorted(wanted - set(out))}"
    return out


DRAFT = _draft_constants()

FAKE_ENV = {
    "interpreter": {"implementation": "CPython", "version": "3.12.10"},
    "numpy_version": "2.4.4",
    "cv2_version": "5.1.0",
    "cv2_file": "X:/fake-prefix/site-packages/cv2/__init__.py",
    "cv2_distribution": None,
}


class FakeT1:
    """Stands in for retina.t1: threshold only, no morphology, no cv2."""

    @staticmethod
    def change_mask(before, after, *, diff_threshold, morph_radius=1):
        with np.errstate(invalid="ignore"):
            d = np.abs(np.asarray(after, np.float32) - np.asarray(before, np.float32))
        return (d > diff_threshold).astype(np.uint8)


class FakeBackend:
    """Stands in for retina.backend_cuda; flip=(row, col) corrupts that pixel in every GPU mask."""

    OPERATIONS = DRAFT["R2_OPS"]

    def __init__(self, flip=None, available=True):
        self.flip, self.available, self._last = flip, available, {}

    def cuda_status(self):
        return (True, "fake device") if self.available else (False, "no CUDA device (fake)")

    def change_mask_cuda(self, before, after, *, diff_threshold, morph_radius=1):
        if not self.available:
            raise RuntimeError("CudaUnavailable: no CUDA device (fake)")
        m = FakeT1.change_mask(before, after, diff_threshold=diff_threshold, morph_radius=morph_radius)
        if self.flip is not None:
            m[self.flip] ^= 1
        self._last = {op: "cuda" for op in self.OPERATIONS}
        return m

    def last_dispatch(self):
        return dict(self._last)

    def witness(self):
        return {"cv2_file": "X:/fake-prefix/site-packages/cv2/cv2.pyd", "cv2_version": "5.1.0",
                "cuda_device_count": 1, "device": {"compute_capability": [8, 9], "total_memory": 1},
                "cuda_build_info": ["NVIDIA CUDA: YES (fake)"],
                "loaded_modules": ["X:/fake-prefix/x64/vc17/bin/opencv_core510.dll"]}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def test_fixture_ids_and_ops_are_the_draft_predicates():
    assert set(fx.G0_PROPOSED) == DRAFT["G0_PROPOSED_FIXTURES"]
    assert set(fx.INFERENCE) == DRAFT["INFERENCE_FIXTURES"]
    assert len(fx.FIXTURE_IDS) == len(set(fx.FIXTURE_IDS)) == 8
    assert parity.R2_OPS == DRAFT["R2_OPS"]


@pytest.mark.parametrize("fid", fx.FIXTURE_IDS)
def test_fixture_is_deterministic_and_fresh(fid):
    b1, a1, t, r = fx.build(fid)
    first = fx.construction_digest(b1, a1, t, r)
    b1[...] = 0.0  # a later build must not share these buffers
    a1[...] = 0.0
    b2, a2, t2, r2 = fx.build(fid)
    assert (t2, r2) == (t, r) == (0.02, 1)
    assert fx.construction_digest(b2, a2, t2, r2) == first


def test_fixtures_are_identical_in_a_fresh_process():
    code = ("import json, sys, importlib.util as u\n"
            "s = u.spec_from_file_location('f', sys.argv[1]); m = u.module_from_spec(s)\n"
            "sys.modules['f'] = m; s.loader.exec_module(m)\n"
            "print(json.dumps({f: m.construction_digest(*m.build(f)) for f in m.FIXTURE_IDS}))\n")
    env = dict(os.environ, PYTHONHASHSEED="12345", PYTHONDONTWRITEBYTECODE="1")
    out = subprocess.run([sys.executable, "-c", code, str(HERE / "fixtures.py")],
                         capture_output=True, text=True, timeout=120, env=env)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == {f: fx.construction_digest(*fx.build(f)) for f in fx.FIXTURE_IDS}


@pytest.mark.parametrize("threshold", [0.02, 0.03])
@pytest.mark.parametrize("fid", fx.FIXTURE_IDS)
def test_fixture_relation_holds_exactly(fid, threshold):
    before, after, t, r = fx.build(fid, diff_threshold=threshold)
    assert t == threshold and r == 1
    assert before.ndim == after.ndim == 2 and before.dtype == after.dtype == np.float32
    assert fx.check_relations(fid, before, after, t, r) == []


def test_boundary_values_are_one_float32_ulp_apart():
    t32 = np.float32(0.02)
    lo, hi = fx.ulp_below(0.02), fx.ulp_above(0.02)
    assert lo.dtype == hi.dtype == np.float32 and lo < t32 < hi
    assert np.nextafter(lo, np.float32(1)) == t32 and np.nextafter(hi, np.float32(0)) == t32
    assert float(t32) != 0.02  # the chain compares at float32(0.02), not at the decimal
    d = fx.plane_diff(*fx.build("diff_at_threshold")[:2])
    assert int((d == t32).sum()) == 3 * 36


T32 = np.float32(0.02)


def _swap(old, new):
    return lambda b, a: (b, np.where(a == old, new, a).astype(np.float32))


def _reset_top_left(b, a):
    a = a.copy()
    a[0, 0] = b[0, 0]
    return b, a


MUTATIONS = {
    "edges_and_corners": _reset_top_left,
    "diff_at_threshold": _swap(T32, np.nextafter(T32, np.float32(1))),
    "diff_one_ulp_below": _swap(np.nextafter(T32, np.float32(0)), T32),
    "diff_one_ulp_above": _swap(np.nextafter(T32, np.float32(1)), T32),
    "non_contiguous_odd_stride": lambda b, a: (np.ascontiguousarray(b), np.ascontiguousarray(a)),
    "size_not_multiple_of_16_or_32": lambda b, a: (np.pad(b, ((0, 15), (0, 9))), np.pad(a, ((0, 15), (0, 9)))),
    "empty_change_set": lambda b, a: (b, a + np.float32(0.5) * (np.arange(a.size).reshape(a.shape) == 0)),
    "nan_in_luma_plane": lambda b, a: (np.nan_to_num(b, nan=0.25), np.nan_to_num(a, nan=0.25)),
}


@pytest.mark.parametrize("fid", fx.FIXTURE_IDS)
def test_relation_check_rejects_a_broken_fixture(fid):
    before, after, t, r = fx.build(fid)
    b2, a2 = MUTATIONS[fid](before, after)
    assert fx.check_relations(fid, b2, a2, t, r), f"{fid}: the relation check accepted a mutated fixture"


def test_a_contiguous_copy_is_not_the_strided_fixture():
    b, a, t, r = fx.build("non_contiguous_odd_stride")
    assert not (b.flags.c_contiguous or a.flags.c_contiguous)
    assert fx.construction_digest(b, a, t, r) != fx.construction_digest(
        np.ascontiguousarray(b), np.ascontiguousarray(a), t, r)


def test_construction_digest_separates_planes_that_differ_only_in_strides():
    """A contiguous copy also flips the contiguity flags and drops the base, so the test above
    cannot show that strides are hashed. Two views of one row-constant base share shape, dtype,
    flags, base and every byte, and differ only in their strides."""
    (vh, vw), (_, sc) = fx.VIEW, fx.VIEW_STEP
    base = np.repeat(np.arange(vh, dtype=np.float32)[:, None], vw * sc, axis=1)
    dense, odd = base[:, :vw], base[:, ::sc]
    assert dense.shape == odd.shape == (vh, vw) and dense.strides != odd.strides
    for v in (dense, odd):
        assert v.base is base and v.dtype == np.float32
        assert not (v.flags.c_contiguous or v.flags.f_contiguous)
    assert np.array_equal(dense, odd)
    assert fx.construction_digest(dense, dense, 0.02, 1) != fx.construction_digest(odd, odd, 0.02, 1)


def test_fixture_planes_pass_through_t1_luma_unchanged():
    """The parity input boundary: t1._luma returns every fixture plane unchanged. Runs in a child
    process with cv2 blocked, so this test never imports cv2."""
    code = (
        "import json, sys, importlib.util as u\n"
        "sys.modules['cv2'] = None\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import numpy as np\n"
        "from retina import t1\n"
        "s = u.spec_from_file_location('f', sys.argv[2]); m = u.module_from_spec(s)\n"
        "sys.modules['f'] = m; s.loader.exec_module(m)\n"
        "res = {}\n"
        "for f in m.FIXTURE_IDS:\n"
        "    b, a, t, r = m.build(f)\n"
        "    res[f] = all(t1._luma(p).dtype == np.float32 and t1._luma(p).shape == p.shape\n"
        "                 and np.array_equal(t1._luma(p), p, equal_nan=True) for p in (b, a))\n"
        "print(json.dumps({'cv2_available': bool(t1._CV2_AVAILABLE), 'unchanged': res}))\n"
    )
    out = subprocess.run([sys.executable, "-c", code, str(REPO), str(HERE / "fixtures.py")],
                         capture_output=True, text=True, timeout=120,
                         env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert got["cv2_available"] is False
    assert got["unchanged"] == {f: True for f in fx.FIXTURE_IDS}


# ---------------------------------------------------------------------------
# Digest and difference
# ---------------------------------------------------------------------------

def test_mask_digest_is_sha256_of_c_order_uint8_bytes():
    m = np.zeros((3, 4), np.uint8)
    m[1, 2] = 1
    d = parity.mask_digest(m)
    assert d == {"sha256": hashlib.sha256(m.tobytes()).hexdigest(), "shape": [3, 4], "dtype": "uint8"}
    assert parity.mask_digest(np.asfortranarray(m)) == d
    big = np.zeros((6, 8), np.uint8)
    big[::2, ::2] = m
    assert parity.mask_digest(big[::2, ::2]) == d
    same_bytes = parity.mask_digest(m.reshape(4, 3))
    assert same_bytes["sha256"] == d["sha256"] and same_bytes["shape"] == [4, 3]
    for bad in (m.astype(bool), m.astype(np.float32), m.tolist()):
        with pytest.raises(TypeError):
            parity.mask_digest(bad)
    assert np.array_equal(parity.decode_mask(parity.encode_mask(m), [3, 4]), m)


def test_first_difference_gives_coordinates_and_tolerates_nothing():
    a = np.zeros((5, 7), np.uint8)
    b = a.copy()
    b[3, 4] = 1
    b[4, 6] = 1
    assert parity.first_difference(a, a.copy()) is None
    assert parity.first_difference(a, b) == {"row": 3, "col": 4, "gpu": 0, "cpu": 1, "differing_px": 2}
    assert parity.first_difference(a, np.zeros((7, 5), np.uint8)) == {
        "shape_mismatch": {"gpu": [5, 7], "cpu": [7, 5]}}


# ---------------------------------------------------------------------------
# Measure, profile, assemble, and the draft predicate on temporary copies
# ---------------------------------------------------------------------------

def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=60)


@pytest.fixture
def fake_repo(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")
    root = tmp_path / "repo"
    (root / "harness" / "next-release" / "gpu").mkdir(parents=True)
    (root / "harness" / "next-release" / "graph.json").write_text("{}\n", encoding="utf-8")
    lock = root / DRAFT["BUILD_LOCK"]
    lock.parent.mkdir(parents=True)
    lock.write_text('{"fake": "build lock for an offline test"}\n', encoding="utf-8")
    assert _git(root, "init", "-q").returncode == 0
    return root


def _run_predicate(root: Path, monkeypatch) -> dict:
    """Every test_* of the committed draft predicate with its repository root at root:
    {name: None when it passes, else its assertion message}."""
    monkeypatch.chdir(root)
    mod = _load(PREDICATE, register=False)
    assert Path(mod.ROOT) == root.resolve(), "the draft predicate did not resolve the temporary repository"
    results = {}
    for name in sorted(n for n in vars(mod) if n.startswith("test_")):
        try:
            getattr(mod, name)()
        except AssertionError as exc:
            results[name] = str(exc)
        else:
            results[name] = None
    return results


def _measure(tmp_path: Path, backend):
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    cpu_doc, cpu_rc = parity.run_cpu(t1=FakeT1, env=FAKE_ENV)
    gpu_doc, gpu_rc = parity.run_gpu(backend=backend, t1=FakeT1, env=FAKE_ENV)
    assert cpu_rc == 0
    parity.write_json(work / "cpu.json", cpu_doc)
    parity.write_json(work / "gpu.json", gpu_doc)
    return work / "cpu.json", work / "gpu.json", cpu_doc, gpu_doc, gpu_rc


def _profile_and_assemble(root: Path, cpu_p: Path, gpu_p: Path, cpu_doc: dict):
    profile, receipt = root / DRAFT["PROFILE"], root / DRAFT["RECEIPT"]
    rc_p = parity.main(["profile", "--cpu", str(cpu_p), "--by", "Joe", "--date", "2000-01-01",
                        "--identity", parity.reference_identity(cpu_doc), "--out", str(profile)])
    rc_a = parity.main(["assemble", "--gpu", str(gpu_p), "--cpu", str(cpu_p), "--profile", str(profile),
                        "--build-lock", str(root / DRAFT["BUILD_LOCK"]), "--out", str(receipt)])
    return rc_p, rc_a, profile, receipt


def _index(root: Path) -> None:
    assert _git(root, "add", "--", DRAFT["RECEIPT"], DRAFT["PROFILE"], DRAFT["BUILD_LOCK"]).returncode == 0


def test_profile_and_assemble_satisfy_the_draft_predicate(fake_repo, tmp_path, monkeypatch):
    cpu_p, gpu_p, cpu_doc, gpu_doc, gpu_rc = _measure(tmp_path, FakeBackend())
    assert gpu_rc == 0 and all(rec["identical"] for rec in gpu_doc["fixtures"].values())
    rc_p, rc_a, profile, receipt = _profile_and_assemble(fake_repo, cpu_p, gpu_p, cpu_doc)
    assert (rc_p, rc_a) == (0, 0)
    r = json.loads(receipt.read_text(encoding="utf-8"))
    assert set(r) == {"profile_sha256", "build_lock_sha256", "backend_witness", "fixtures", "cpu_reference"}
    assert set(r["backend_witness"]) == {"dispatch", "loaded_modules", "cv2_file"}
    assert set(r["cpu_reference"]) == {"identity"}
    assert set(r["fixtures"]) == set(fx.FIXTURE_IDS)
    assert all(set(v) == {"gpu_mask_sha256", "cpu_mask_sha256"} for v in r["fixtures"].values())
    assert all(r["fixtures"][fid]["cpu_mask_sha256"] == cpu_doc["fixtures"][fid]["mask_sha256"]
               for fid in fx.FIXTURE_IDS)
    p = json.loads(profile.read_text(encoding="utf-8"))
    assert p["cpu_reference_ruling"] == {"by": "Joe", "date": "2000-01-01",
                                         "identity": parity.reference_identity(cpu_doc)}
    red = _run_predicate(fake_repo, monkeypatch)
    assert len(red) == 5 and all(m and DRAFT["MARKER"] in m for m in red.values()), red
    _index(fake_repo)
    green = _run_predicate(fake_repo, monkeypatch)
    assert green == {name: None for name in red}, green


def test_a_gpu_mismatch_is_recorded_with_coordinates_and_rejected(fake_repo, tmp_path, monkeypatch):
    cpu_p, gpu_p, cpu_doc, gpu_doc, gpu_rc = _measure(tmp_path, FakeBackend(flip=(2, 3)))
    assert gpu_rc == 1
    for rec in gpu_doc["fixtures"].values():
        fd = rec["first_difference"]
        assert rec["identical"] is False and (fd["row"], fd["col"], fd["differing_px"]) == (2, 3, 1)
    rc_p, rc_a, profile, receipt = _profile_and_assemble(fake_repo, cpu_p, gpu_p, cpu_doc)
    assert (rc_p, rc_a) == (0, 1)
    got = json.loads(receipt.read_text(encoding="utf-8"))["fixtures"]
    for fid in fx.FIXTURE_IDS:  # the digests differ here, so each side must come from its own file
        assert got[fid]["cpu_mask_sha256"] == cpu_doc["fixtures"][fid]["mask_sha256"]
        assert got[fid]["gpu_mask_sha256"] == gpu_doc["fixtures"][fid]["gpu_mask_sha256"]
        assert got[fid]["gpu_mask_sha256"] != got[fid]["cpu_mask_sha256"]
    fd = got["empty_change_set"]["first_difference"]
    assert (fd["row"], fd["col"], fd["differing_px"]) == (2, 3, 1)
    _index(fake_repo)
    res = _run_predicate(fake_repo, monkeypatch)
    assert "GPU mask differs" in (res.pop("test_fixture_masks_match_the_frozen_profile") or "")
    assert all(v is None for v in res.values()), res


def test_unavailable_cuda_is_inconclusive_and_cannot_be_assembled(fake_repo, tmp_path):
    cpu_p, gpu_p, cpu_doc, gpu_doc, gpu_rc = _measure(tmp_path, FakeBackend(available=False))
    assert gpu_rc == 3 and gpu_doc["cuda_status"]["available"] is False
    assert not any("gpu_mask_sha256" in rec for rec in gpu_doc["fixtures"].values())
    assert all("CudaUnavailable" in rec["gpu_error"] for rec in gpu_doc["fixtures"].values())
    rc_p, rc_a, _, receipt = _profile_and_assemble(fake_repo, cpu_p, gpu_p, cpu_doc)
    assert (rc_p, rc_a) == (0, 2) and not receipt.exists()


def test_cuda_status_unavailable_is_refused_even_with_masks(fake_repo, tmp_path, capsys):
    """cuda_status says no CUDA, yet every fixture carries a GPU mask and no error: the gpu-mode
    file is refused on cuda_status alone, not on the not-computed branch."""
    reason = "no CUDA device (fake status beside fake masks)"

    class StatusSaysNoCuda(FakeBackend):
        def cuda_status(self):
            return False, reason

    cpu_p, gpu_p, cpu_doc, gpu_doc, gpu_rc = _measure(tmp_path, StatusSaysNoCuda())
    assert gpu_rc == 3 and gpu_doc["cuda_status"] == {"available": False, "reason": reason}
    assert all("gpu_mask_sha256" in rec and not any(k.endswith("error") for k in rec)
               for rec in gpu_doc["fixtures"].values())
    capsys.readouterr()
    rc_p, rc_a, _, receipt = _profile_and_assemble(fake_repo, cpu_p, gpu_p, cpu_doc)
    assert (rc_p, rc_a) == (0, 2) and not receipt.exists()
    refused = [ln for ln in capsys.readouterr().err.splitlines() if ln.startswith("REFUSED:")]
    assert refused == [f"REFUSED: gpu-mode file: CUDA unavailable: {reason}"]


def test_a_dispatch_off_cuda_is_written_but_not_qualified(fake_repo, tmp_path, capsys):
    """morphology_close never reports cuda while every mask matches: the receipt is written,
    names that op as not cuda, and assemble exits 1."""
    class CloseNotOnCuda(FakeBackend):
        def last_dispatch(self):
            d = super().last_dispatch()
            d.pop("morphology_close", None)
            return d

    cpu_p, gpu_p, cpu_doc, gpu_doc, gpu_rc = _measure(tmp_path, CloseNotOnCuda())
    assert gpu_rc == 0 and all(rec["identical"] for rec in gpu_doc["fixtures"].values())
    capsys.readouterr()
    rc_p, rc_a, _, receipt = _profile_and_assemble(fake_repo, cpu_p, gpu_p, cpu_doc)
    assert (rc_p, rc_a) == (0, 1) and receipt.exists()
    dispatch = json.loads(receipt.read_text(encoding="utf-8"))["backend_witness"]["dispatch"]
    assert dispatch.pop("morphology_close").startswith("not cuda in:")
    assert dispatch == {op: "cuda" for op in DRAFT["R2_OPS"] if op != "morphology_close"}
    unqualified = [ln for ln in capsys.readouterr().err.splitlines() if ln.startswith("NOT QUALIFIED:")]
    assert len(unqualified) == 1
    assert unqualified[0].startswith("NOT QUALIFIED: dispatch morphology_close: not cuda in:")


def test_profile_takes_the_ruling_from_arguments_and_only_a_measured_identity(tmp_path):
    cpu_doc, _ = parity.run_cpu(t1=FakeT1, env=FAKE_ENV)
    cpu_p = tmp_path / "cpu.json"
    parity.write_json(cpu_p, cpu_doc)
    out = tmp_path / "profile.json"
    base = ["profile", "--cpu", str(cpu_p), "--by", "Joe", "--date", "2000-01-01", "--out", str(out)]
    assert parity.main(base + ["--identity", "the custom build"]) == 2 and not out.exists()
    off_doc, _ = parity.run_cpu(t1=FakeT1, env=dict(FAKE_ENV, cv2_version="4.12.0"))
    off_p = tmp_path / "cpu412.json"
    parity.write_json(off_p, off_doc)
    off = ["profile", "--cpu", str(off_p), "--by", "Joe", "--date", "2000-01-01", "--out", str(out),
           "--identity", parity.reference_identity(off_doc)]
    assert parity.main(off) == 2 and not out.exists()
    full = base + ["--identity", parity.reference_identity(cpu_doc)]
    for flag in ("--by", "--date", "--identity"):
        i = full.index(flag)
        with pytest.raises(SystemExit):
            parity.main(full[:i] + full[i + 2:])
    assert parity.main(full) == 0
    assert parity.main(full) == 2  # frozen: no silent overwrite


def test_receipt_refuses_a_user_profile_path(fake_repo, tmp_path):
    class LeakyBackend(FakeBackend):
        def witness(self):
            w = super().witness()
            w["loaded_modules"] = ["/".join(["C:", "Users", "someone", "opencv_core510.dll"])]
            return w

    cpu_p, gpu_p, cpu_doc, _, _ = _measure(tmp_path, LeakyBackend())
    rc_p, rc_a, _, receipt = _profile_and_assemble(fake_repo, cpu_p, gpu_p, cpu_doc)
    assert (rc_p, rc_a) == (0, 2) and not receipt.exists()


# ---------------------------------------------------------------------------
# Static guards
# ---------------------------------------------------------------------------

def test_tooling_reaches_cv2_only_through_retina_and_lazily():
    for name in ("parity.py", "fixtures.py"):
        tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            elif (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "import_module"
                  and node.args and isinstance(node.args[0], ast.Constant)):
                mods = [str(node.args[0].value)]
            assert not any(m == "cv2" or m.startswith("cv2.") for m in mods), f"{name} imports cv2"
        top = [a.name for n in tree.body if isinstance(n, ast.Import) for a in n.names]
        top += [n.module or "" for n in tree.body if isinstance(n, ast.ImportFrom)]
        assert not any(m.split(".")[0] == "retina" for m in top), f"{name} imports retina at module level"


def test_predicate_file_is_the_amendment_draft_byte_for_byte():
    if not AMENDMENT.is_file():
        pytest.skip("the PROPOSED amendment is no longer in the tree")
    amend = json.loads(AMENDMENT.read_text(encoding="utf-8"))
    drafts = [c["proposed_file"] for c in amend.get("_proposed_changes_to_existing", [])
              if c.get("node") == "NR-GPU-QUALIFICATION" and c.get("field") == "predicate"]
    assert len(drafts) == 1 and drafts[0]["path"] == "harness/next-release/gpu/test_qualification_contract.py"
    assert PREDICATE.read_bytes() == ("\n".join(drafts[0]["source_lines"]) + "\n").encode("utf-8")
