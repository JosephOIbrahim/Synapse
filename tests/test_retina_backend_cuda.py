"""NR-VG-RETINA-CUDA-BACKEND: tests for the worker-only CUDA backend
(``retina/backend_cuda.py``; ADR-0002 Site 2; owner ruling R2).

Three groups.

1. ``test_unavailable_*``: hermetic, and they always run. Each forces CUDA to be
   unavailable through a ``sys.modules`` shim that pytest restores after the test, so
   they pass in stock CI (no cv2, possibly no numpy), on a dev interpreter whose cv2
   has a ``cv2.cuda`` namespace but no device, and inside the GPU worker venv. They
   prove that an unavailable GPU operation yields an inconclusive check with a
   reason: never a pass, never a CPU fallback. ``backend_receipt.json`` lists them;
   ``harness/vision/retina_cuda_backend/make_receipt.py`` derives the list from the
   ``test_unavailable_`` prefix.
2. Host-side construction: the float32 threshold derivation (numpy only), the
   Windows loaded-module enumeration, and an *emulated device*: real CPU cv2 behind a
   stand-in ``cv2.cuda`` whose morphology filters use a deliberately wrong edge rule.
   The emulated run proves that the padding, crop, threshold and step order
   reproduce ``retina.t1.change_mask``. It is not GPU evidence.
3. ``test_gpu_*``: skip unless ``cuda_status()`` is True. On a real device
   ``change_mask_cuda`` must equal ``retina.t1.change_mask`` byte for byte.

Nothing here launches Houdini or uses the network. Only group 3, and only where a
CUDA device is usable, runs anything on a GPU.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest

import retina
from retina import backend_cuda as bc
from retina import events, t1

_REPO_ROOT = Path(__file__).resolve().parent.parent
_HAS_NUMPY = importlib.util.find_spec("numpy") is not None
_HAS_CV2 = importlib.util.find_spec("cv2") is not None
_R2 = ("absdiff", "threshold", "morphology_open", "morphology_close")
_PLANE = [[0.0, 0.5], [0.5, 0.0]]  # nested lists: the unavailable path never needs numpy

needs_numpy = pytest.mark.skipif(not _HAS_NUMPY, reason="numpy not installed")
needs_cpu_reference = pytest.mark.skipif(
    not (_HAS_CV2 and _HAS_NUMPY),
    reason="needs cv2 + numpy for the CPU reference (RETINA worker venv or a dev interpreter)",
)


# --- test doubles --------------------------------------------------------------

def _cv2_double(**attrs):
    mod = types.ModuleType("cv2")
    mod.__version__ = "0.0-test-double"
    mod.__file__ = "<test double>"
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


def _count_raises():
    raise RuntimeError("simulated driver failure")


def _cuda_ns(count):
    return types.SimpleNamespace(getCudaEnabledDeviceCount=count)


# name -> (what sys.modules["cv2"] becomes, a phrase the reason must carry)
_UNAVAILABLE = {
    "cv2_absent": (lambda: None, "cv2 is not importable"),
    "no_cuda_namespace": (lambda: _cv2_double(), "no cv2.cuda namespace"),
    "zero_devices": (lambda: _cv2_double(cuda=_cuda_ns(lambda: 0)), "returned 0"),
    "driver_missing": (lambda: _cv2_double(cuda=_cuda_ns(lambda: -1)), "returned -1"),
    "device_count_raises": (lambda: _cv2_double(cuda=_cuda_ns(_count_raises)), "raised RuntimeError"),
}


@pytest.fixture(params=sorted(_UNAVAILABLE))
def unavailable(request, monkeypatch):
    """Make CUDA unavailable one way; return the phrase the reason must carry."""
    make, phrase = _UNAVAILABLE[request.param]
    monkeypatch.setitem(sys.modules, "cv2", make())
    return phrase


# --- 1. unavailable -> inconclusive with a reason (hermetic) -----------------------

def test_unavailable_cuda_status_is_false_with_a_reason(unavailable):
    ok, reason = bc.cuda_status()
    assert ok is False
    assert isinstance(reason, str) and unavailable in reason


def test_unavailable_change_mask_cuda_raises_and_never_falls_back(unavailable, monkeypatch):
    monkeypatch.setattr(bc, "_dispatched", {"absdiff": "cuda"})  # a stale record from an earlier call
    with pytest.raises(bc.CudaUnavailable) as caught:
        bc.change_mask_cuda(_PLANE, _PLANE, diff_threshold=0.02, morph_radius=1)
    assert unavailable in caught.value.reason
    assert isinstance(caught.value, t1.T1Unavailable)
    assert bc.last_dispatch() == {}  # nothing is claimed for a call that ran nothing


def test_unavailable_change_mask_check_is_inconclusive_with_the_reason(unavailable):
    mask, check = bc.change_mask_check(_PLANE, _PLANE, diff_threshold=0.02, morph_radius=1)
    assert mask is None
    assert check["name"] == "change_mask_cuda"
    assert check["pass"] is None  # inconclusive, never a pass
    assert check["detail"] == bc.cuda_status()[1] and unavailable in check["detail"]
    assert events.roll_up([check]) == "inconclusive"
    assert bc.last_dispatch() == {}
    _, named = bc.change_mask_check(_PLANE, _PLANE, diff_threshold=0.03, name="change_mask_cuda_r2")
    assert named["name"] == "change_mask_cuda_r2" and named["pass"] is None


def test_unavailable_missing_cuda_function_is_inconclusive_with_the_reason(monkeypatch):
    cuda = types.SimpleNamespace(  # a device is reported, but the build has no copyMakeBorder
        getCudaEnabledDeviceCount=lambda: 1,
        GpuMat=object,
        absdiff=None,
        threshold=None,
        createMorphologyFilter=None,
    )
    monkeypatch.setitem(sys.modules, "cv2", _cv2_double(cuda=cuda))
    assert bc.cuda_status()[0] is True
    with pytest.raises(bc.CudaUnavailable) as caught:
        bc.change_mask_cuda(_PLANE, _PLANE, diff_threshold=0.02)
    assert "copyMakeBorder" in caught.value.reason
    mask, check = bc.change_mask_check(_PLANE, _PLANE, diff_threshold=0.02)
    assert mask is None and check["pass"] is None and "copyMakeBorder" in check["detail"]
    assert bc.last_dispatch() == {}


@needs_numpy
@pytest.mark.parametrize("failing", ["absdiff", "threshold"])
def test_unavailable_device_error_mid_chain_is_inconclusive(failing, monkeypatch):
    import numpy as np

    class Error(Exception):
        pass

    class GpuMat:
        def upload(self, arr):
            self.array = arr

    def absdiff(a, b):
        if failing == "absdiff":
            raise Error("simulated device failure")
        return GpuMat()

    def threshold(src, thresh, maxval, kind):
        raise Error("simulated device failure")

    cuda = types.SimpleNamespace(
        getCudaEnabledDeviceCount=lambda: 1,
        GpuMat=GpuMat,
        absdiff=absdiff,
        threshold=threshold,
        copyMakeBorder=None,
        createMorphologyFilter=None,
    )
    monkeypatch.setitem(sys.modules, "cv2", _cv2_double(cuda=cuda, error=Error, THRESH_BINARY=0))
    plane = np.zeros((4, 5), np.float32)
    with pytest.raises(bc.CudaUnavailable) as caught:
        bc.change_mask_cuda(plane, plane, diff_threshold=0.02)
    assert f"cv2.cuda {failing} failed" in caught.value.reason
    assert "simulated device failure" in caught.value.reason
    # Only steps whose cv2.cuda call returned are claimed.
    assert bc.last_dispatch() == ({} if failing == "absdiff" else {"absdiff": "cuda"})
    mask, check = bc.change_mask_check(plane, plane, diff_threshold=0.02)
    assert mask is None and check["pass"] is None


@needs_numpy
def test_non_cv2_error_mid_chain_propagates_unchanged(monkeypatch):
    """The edge of "unavailable". Only ``cv2.error`` part-way through the chain means
    the device could not run it. Any other exception there is a bug, and it must
    propagate unchanged: never a ``CudaUnavailable``, never an inconclusive check.

    The stand-in build has a ``cv2.error`` of its own, and ``TypeError`` is not one.
    The test has no ``test_unavailable_`` prefix on purpose: it does not prove
    "unavailable -> inconclusive", so ``make_receipt.py`` must not list it."""
    import numpy as np

    class Error(Exception):
        pass

    class GpuMat:
        def upload(self, arr):
            self.array = arr

    sentinel = "simulated non-cv2 failure inside the chain"
    calls = []

    def absdiff(a, b):
        calls.append("absdiff")
        raise TypeError(sentinel)

    cuda = types.SimpleNamespace(
        getCudaEnabledDeviceCount=lambda: 1,
        GpuMat=GpuMat,
        absdiff=absdiff,
        threshold=None,
        copyMakeBorder=None,
        createMorphologyFilter=None,
    )
    monkeypatch.setitem(sys.modules, "cv2", _cv2_double(cuda=cuda, error=Error))
    plane = np.zeros((4, 5), np.float32)
    with pytest.raises(TypeError, match=sentinel):
        bc.change_mask_cuda(plane, plane, diff_threshold=0.02)
    assert calls == ["absdiff"]  # raised inside the chain at absdiff, not before it
    assert bc.last_dispatch() == {}
    with pytest.raises(TypeError, match=sentinel):  # not turned into (None, inconclusive)
        bc.change_mask_check(plane, plane, diff_threshold=0.02)
    assert calls == ["absdiff", "absdiff"]


def test_unavailable_import_without_cv2_or_numpy_works(monkeypatch):
    # Shim both native packages away, re-import only the backend, restore everything after.
    monkeypatch.setitem(sys.modules, "cv2", None)
    monkeypatch.setitem(sys.modules, "numpy", None)
    monkeypatch.delitem(sys.modules, "retina.backend_cuda")
    monkeypatch.delattr(retina, "backend_cuda")
    fresh = importlib.import_module("retina.backend_cuda")
    assert fresh is not bc
    assert fresh.np is None
    assert fresh.OPERATIONS == _R2
    ok, reason = fresh.cuda_status()
    assert ok is False and "cv2 is not importable" in reason
    with pytest.raises(fresh.CudaUnavailable):
        fresh.change_mask_cuda(_PLANE, _PLANE, diff_threshold=0.02)
    mask, check = fresh.change_mask_check(_PLANE, _PLANE, diff_threshold=0.02)
    assert mask is None and check["pass"] is None and check["detail"] == reason
    assert fresh.last_dispatch() == {}
    w = fresh.witness()
    assert (w["cv2_file"], w["cv2_version"], w["cuda_device_count"], w["device"]) == (None, None, None, None)
    assert w["cuda_build_info"] == [] and isinstance(w["loaded_modules"], list)


# --- contract shape --------------------------------------------------------------

def _predicate_r2_ops():
    hits = sorted((_REPO_ROOT / "harness" / "next-release").rglob("test_nr_vg_retina_cuda_backend.py"))
    assert hits, "the NR-VG-RETINA-CUDA-BACKEND closure predicate is not under harness/next-release/"
    tree = ast.parse(hits[0].read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "R2_OPS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("R2_OPS is not assigned in the predicate")


def test_operations_equal_the_predicate_r2_ops():
    assert bc.OPERATIONS == _R2
    assert set(bc.OPERATIONS) == set(_predicate_r2_ops())
    assert len(set(bc.OPERATIONS)) == len(bc.OPERATIONS)


def test_cuda_unavailable_is_a_t1_unavailable_with_a_reason():
    exc = bc.CudaUnavailable("no CUDA device")
    assert isinstance(exc, t1.T1Unavailable) and isinstance(exc, RuntimeError)
    assert exc.reason == "no CUDA device" and str(exc) == "no CUDA device"


def test_cuda_status_never_raises_and_always_gives_a_reason():
    ok, reason = bc.cuda_status()  # the real interpreter: False on a CPU-only cv2, True in the worker
    assert isinstance(ok, bool) and isinstance(reason, str) and reason


def _module_level_imports_of(tree, top):
    hits = []

    def visit(node, in_function):
        for child in ast.iter_child_nodes(node):
            inside = in_function or isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
            if not inside:
                if isinstance(child, ast.Import) and any(a.name.split(".")[0] == top for a in child.names):
                    hits.append(child.lineno)
                elif isinstance(child, ast.ImportFrom) and (child.module or "").split(".")[0] == top:
                    hits.append(child.lineno)
            visit(child, inside)

    visit(tree, False)
    return hits


def test_cv2_is_imported_only_inside_functions():
    tree = ast.parse((_REPO_ROOT / "retina" / "backend_cuda.py").read_text(encoding="utf-8"))
    assert _module_level_imports_of(tree, "cv2") == []
    assert _module_level_imports_of(tree, "hou") == []


@needs_numpy
def test_float32_threshold_matches_numpy_strict_greater_than():
    import numpy as np

    for t in (0.02, 0.03, 0.1, 1.0 / 3.0, 0.5, 1e-7, 0.0):
        for typed in (t, np.float32(t), np.float64(t)):
            device = np.float32(bc._float32_threshold(typed))
            assert float(device) == bc._float32_threshold(typed)  # exact in float32
            c = np.float32(t)
            v = np.array(
                [np.nextafter(c, np.float32(-np.inf)), c, np.nextafter(c, np.float32(np.inf)), 0.0, 1.0],
                dtype=np.float32,
            )
            assert np.array_equal(v > device, v > typed), (t, type(typed).__name__)
        # A Python float (the profile type) gets exactly the pre-rounded float32 value.
        assert bc._float32_threshold(t) == float(np.float32(t))
    # The one place the two differ: a float64 scalar whose float32 rounding goes up.
    up = np.float32(0.1)
    assert float(up) > 0.1
    assert bc._float32_threshold(np.float64(0.1)) == float(np.nextafter(up, np.float32(-np.inf)))


# --- witness -----------------------------------------------------------------------

def test_witness_reports_the_contract_fields_and_only_the_named_native_families():
    w = bc.witness()
    assert set(w) == {"cv2_file", "cv2_version", "cuda_device_count", "device", "cuda_build_info", "loaded_modules"}
    assert isinstance(w["cuda_build_info"], list) and isinstance(w["loaded_modules"], list)
    for path in w["loaded_modules"]:
        assert os.path.basename(path).lower().startswith(bc._NATIVE_MODULE_PREFIXES)


@pytest.mark.skipif(sys.platform != "win32", reason="the loaded-module witness enumerates Windows process modules")
def test_witness_enumerates_loaded_modules_when_the_filter_is_widened(monkeypatch):
    monkeypatch.setattr(bc, "_NATIVE_MODULE_PREFIXES", None)
    modules = bc.witness()["loaded_modules"]
    assert modules, "K32EnumProcessModules returned nothing: were the ctypes argtypes dropped?"
    assert all(os.path.isabs(p) for p in modules)
    names = {os.path.basename(p).lower() for p in modules}
    assert {"ntdll.dll", "kernel32.dll"} <= names
    assert any(n.startswith("python") for n in names)


@pytest.mark.skipif(sys.platform == "win32", reason="off Windows the witness lists no modules")
def test_witness_lists_no_modules_off_windows():
    assert bc.witness()["loaded_modules"] == []


# --- parity fixtures (shared by the emulated-device and the GPU tests) ----------------

def _edge_pair(np, height=257, width=263):
    """Changes touching every edge and corner, 2-pixel bands on three edges, a 1-pixel
    band on the fourth, an isolated speck (open removes it) and a pinhole (close fills
    it). Sizes are not multiples of 16 or 32."""
    rng = np.random.default_rng(20261108)
    before = (rng.random((height, width), dtype=np.float32) * np.float32(0.25)).astype(np.float32)
    after = before.copy()
    h, w = height, width
    for rows, cols in (
        (slice(0, 3), slice(0, 4)),
        (slice(0, 2), slice(w - 5, w)),
        (slice(h - 4, h), slice(0, 2)),
        (slice(h - 3, h), slice(w - 3, w)),
        (slice(0, 2), slice(w // 3, w // 3 + 40)),
        (slice(h // 2, h // 2 + 6), slice(0, 1)),
        (slice(h // 4, h // 4 + 10), slice(w - 2, w)),
        (slice(h - 2, h), slice(w // 8, w // 8 + 60)),
        (slice(h // 3, h // 3 + 30), slice(w // 3, w // 3 + 40)),
        (slice(10, 11), slice(w // 5, w // 5 + 1)),
    ):
        after[rows, cols] += np.float32(0.5)
    after[h // 3 + 15, w // 3 + 20] = before[h // 3 + 15, w // 3 + 20]
    return before, after


def _threshold_pair(np, t, typed, radius=0):
    """|diff| one float32 ulp below, exactly at and one ulp above the threshold, in both
    directions (absdiff is symmetric) and in the four corners."""
    c = np.float32(t)
    lo = np.nextafter(c, np.float32(-np.inf))
    hi = np.nextafter(c, np.float32(np.inf))
    before = np.zeros((33, 35), np.float32)
    after = np.zeros_like(before)
    for col, value in ((1, lo), (3, c), (5, hi)):
        after[1, col] = value
        before[3, col] = value
    after[0, 0], after[0, 34], after[32, 0], after[32, 34] = hi, c, lo, hi
    return before, after, typed, radius


def _rgb_strided_pair(np):
    """Three-channel views with odd strides: the luma path on non-contiguous input."""
    rng = np.random.default_rng(7)
    base = rng.random((130, 200, 4), dtype=np.float32)
    changed = base.copy()
    changed[0:20, 0:30, :] += np.float32(0.6)
    changed[60:90, 150:200, :] += np.float32(0.6)
    return base[::2, ::3, :3], changed[::2, ::3, :3], 0.02, 1


def _unchanged_pair(np):
    before, _ = _edge_pair(np, 40, 50)
    return before, before.copy(), 0.02, 1


_CASES = {
    "edges_t002_r1": lambda np: (*_edge_pair(np), 0.02, 1),
    "edges_t003_r2": lambda np: (*_edge_pair(np), 0.03, 2),
    "edges_t002_r0": lambda np: (*_edge_pair(np), 0.02, 0),
    "threshold_ulps_002": lambda np: _threshold_pair(np, 0.02, 0.02),
    "threshold_ulps_003": lambda np: _threshold_pair(np, 0.03, 0.03),
    "threshold_ulps_float64_scalar": lambda np: _threshold_pair(np, 0.1, np.float64(0.1)),
    "threshold_ulps_r1": lambda np: _threshold_pair(np, 0.02, 0.02, radius=1),
    "rgb_strided_r1": _rgb_strided_pair,
    "fortran_order_r1": lambda np: (*(np.asfortranarray(a) for a in _edge_pair(np, 61, 47)), 0.02, 1),
    "unchanged_r1": _unchanged_pair,
}


def _expected_dispatch(radius):
    record = {"absdiff": "cuda", "threshold": "cuda"}
    if radius > 0:
        record.update(morphology_open="cuda", morphology_close="cuda")
    return record


# --- 2. emulated device: the construction, not the kernels -----------------------------

def _emulated_cv2(cv2, np):
    """A stand-in cv2 whose ``cv2.cuda`` runs real CPU cv2 operations, except that its
    morphology filters use the WRONG edge rule on purpose: outside pixels count as 0
    for erode and 1 for dilate, the opposite of neutral. Only the backend's own neutral
    padding can then reproduce the CPU reference at the frame edges."""

    class GpuMat:
        def __init__(self, array=None):
            self._a = array

        def upload(self, arr):
            assert arr.flags["C_CONTIGUOUS"], "the backend uploads C-contiguous planes"
            self._a = arr.copy()

        def download(self):
            return np.array(self._a, copy=True)

        def convertTo(self, rtype):
            assert rtype == cv2.CV_8U
            return GpuMat(self._a.astype(np.uint8))

        def rowRange(self, start, end):
            return GpuMat(self._a[start:end])

        def colRange(self, start, end):
            return GpuMat(self._a[:, start:end])

    class WrongEdgeFilter:
        def __init__(self, op, kernel):
            self.op, self.kernel = op, kernel

        def apply(self, src):
            if self.op == cv2.MORPH_ERODE:
                out = cv2.erode(src._a, self.kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0)
            else:
                out = cv2.dilate(src._a, self.kernel, borderType=cv2.BORDER_CONSTANT, borderValue=1)
            return GpuMat(out)

    def threshold(src, thresh, maxval, kind):
        retval, out = cv2.threshold(src._a, thresh, maxval, kind)
        return retval, GpuMat(out)

    def copy_make_border(src, top, bottom, left, right, kind, value=None):
        return GpuMat(cv2.copyMakeBorder(src._a, top, bottom, left, right, kind, value=value))

    def create_morphology_filter(op, src_type, kernel):
        assert src_type == cv2.CV_8UC1 and op in (cv2.MORPH_ERODE, cv2.MORPH_DILATE)
        return WrongEdgeFilter(op, kernel)

    cuda = types.SimpleNamespace(
        getCudaEnabledDeviceCount=lambda: 1,
        GpuMat=GpuMat,
        absdiff=lambda a, b: GpuMat(cv2.absdiff(a._a, b._a)),
        threshold=threshold,
        copyMakeBorder=copy_make_border,
        createMorphologyFilter=create_morphology_filter,
    )
    names = ("THRESH_BINARY", "CV_8U", "CV_8UC1", "MORPH_ELLIPSE", "MORPH_ERODE", "MORPH_DILATE", "BORDER_CONSTANT")
    fake = _cv2_double(
        cuda=cuda,
        error=cv2.error,
        getStructuringElement=cv2.getStructuringElement,
        **{name: getattr(cv2, name) for name in names},
    )
    fake.__version__ = "emulated-device"
    return fake, WrongEdgeFilter, GpuMat


@needs_cpu_reference
@pytest.mark.parametrize("case", sorted(_CASES))
def test_emulated_device_chain_matches_cpu_reference_under_a_wrong_edge_rule(case, monkeypatch):
    import cv2
    import numpy as np

    before, after, threshold, radius = _CASES[case](np)
    expected = t1.change_mask(before, after, diff_threshold=threshold, morph_radius=radius)
    fake, _, _ = _emulated_cv2(cv2, np)
    monkeypatch.setitem(sys.modules, "cv2", fake)
    got = bc.change_mask_cuda(before, after, diff_threshold=threshold, morph_radius=radius)
    assert got.dtype == np.uint8 and got.shape == expected.shape
    assert np.array_equal(got, expected), f"{case}: {int((got != expected).sum())} pixels differ"
    assert bc.last_dispatch() == _expected_dispatch(radius)
    mask, check = bc.change_mask_check(before, after, diff_threshold=threshold, morph_radius=radius)
    assert np.array_equal(mask, expected)
    assert check["pass"] is True and check["detail"] == "computed on cuda"
    assert check["changed_px"] == int(np.count_nonzero(expected))


@needs_cpu_reference
def test_emulated_wrong_edge_rule_is_visible_without_the_padding():
    """Control for the test above: the same wrong-edge filters run with no padding
    must change the edge fixture, so that parity is not vacuous."""
    import cv2
    import numpy as np

    before, after, threshold, radius = _CASES["edges_t002_r1"](np)
    expected = t1.change_mask(before, after, diff_threshold=threshold, morph_radius=radius)
    _, wrong_edge_filter, gpu_mat = _emulated_cv2(cv2, np)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
    erode = wrong_edge_filter(cv2.MORPH_ERODE, kernel)
    dilate = wrong_edge_filter(cv2.MORPH_DILATE, kernel)
    diff = cv2.absdiff(t1._luma(before), t1._luma(after))
    mask = gpu_mat((diff > threshold).astype(np.uint8))
    for step in (erode, dilate, dilate, erode):
        mask = step.apply(mask)
    assert not np.array_equal(mask.download(), expected)


# --- 3. the real device (skip unless CUDA is usable) ----------------------------------

def _require_cuda():
    ok, reason = bc.cuda_status()
    if not ok:
        pytest.skip(f"no usable CUDA device: {reason}")


@pytest.mark.parametrize("case", sorted(_CASES))
def test_gpu_parity_change_mask_cuda_equals_t1_change_mask(case):
    _require_cuda()
    import numpy as np

    before, after, threshold, radius = _CASES[case](np)
    expected = t1.change_mask(before, after, diff_threshold=threshold, morph_radius=radius)
    got = bc.change_mask_cuda(before, after, diff_threshold=threshold, morph_radius=radius)
    assert got.dtype == np.uint8 and got.shape == expected.shape
    assert np.array_equal(got, expected), f"{case}: {int((got != expected).sum())} pixels differ"
    assert bc.last_dispatch() == _expected_dispatch(radius)
    mask, check = bc.change_mask_check(before, after, diff_threshold=threshold, morph_radius=radius)
    assert np.array_equal(mask, expected)
    assert check["pass"] is True and check["detail"] == "computed on cuda"
    assert check["changed_px"] == int(np.count_nonzero(expected))


def test_gpu_witness_reports_the_device_and_the_cuda_build():
    _require_cuda()
    w = bc.witness()
    assert w["cuda_device_count"] >= 1
    assert w["device"]["compute_capability"] and w["device"]["total_memory"]
    assert any(line.startswith("NVIDIA CUDA") for line in w["cuda_build_info"])
    if sys.platform == "win32":
        names = [os.path.basename(p).lower() for p in w["loaded_modules"]]
        assert any(n.startswith("cv2") for n in names)
