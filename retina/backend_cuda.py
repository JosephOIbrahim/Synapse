"""RETINA T1: a worker-only OpenCV CUDA backend for the R2 change-mask chain.

ADR-0002 (Accepted 2026-11-08), Site 2. Owner ruling R2 (2026-11-07) names the
first GPU chain: the body of :func:`retina.t1.change_mask`, and nothing else::

    absdiff -> strict threshold -> morphological open -> morphological close

**Placement.** This module runs only inside the out-of-process RETINA worker
(CPython 3.12.10 with a CUDA build of cv2, owner ruling R4). It must never be
reachable from the modules that load inside Houdini (``retina/__init__.py``,
``retina/t0.py``, ``retina/events.py``, ``retina/exr_header.py``), and it must never
be listed in ``RUNTIME_FILES`` in ``installer/build_payload.py``. It imports no
``hou``.

**Off by default.** Nothing in the product imports this module. T1 has no production
caller and no worker launches it yet (ADR-0002, Context section 2), so until a worker
exists its only consumer is an offline parity harness. :func:`retina.t1.change_mask`
is untouched and stays the CPU reference.

**Honest failure.** When the chain cannot run on CUDA, :func:`change_mask_cuda`
raises :class:`CudaUnavailable` (a :class:`retina.t1.T1Unavailable`) carrying a
reason, and :func:`change_mask_check` turns that into an inconclusive check
(``pass=None``) whose detail is the reason. It is never a pass. Nothing here computes
the mask on the CPU, so there is no fallback to fall into. Three things make the
chain unavailable: :func:`cuda_status` is False; the cv2 build lacks a ``cv2.cuda``
function the chain calls; or a ``cv2.cuda`` call raises ``cv2.error`` part-way, in
which case the reason names the step.

**Parity with** ``retina.t1.change_mask`` **by construction.** Same inputs, same uint8
{0,1} mask, same shape:

1. Luma is computed on the host by ``retina.t1._luma`` (the code the CPU path runs),
   then float32, then made C-contiguous for upload.
2. ``cv2.cuda.absdiff`` on the two float32 planes.
3. Strict threshold. The CPU path computes ``diff > diff_threshold`` in NumPy. Under
   NumPy >= 2 (NEP 50) a Python float threshold is compared at float32, so the device
   receives ``float(numpy.float32(diff_threshold))``. That value is exact in float32
   and ``cv2.cuda.threshold(..., THRESH_BINARY)`` is a strict ``src > thresh``, so the
   device agrees with NumPy whether it compares in float32 or in float64. The value
   is derived by asking NumPy itself (:func:`_float32_threshold`), so a strongly
   typed wider NumPy scalar, which NumPy compares in float64, is matched as well.
   Then ``convertTo(CV_8U)``.
4. Morphology. Open is erode then dilate; close is dilate then erode; the structuring
   element is the CPU path's ``MORPH_ELLIPSE`` of size ``2r+1``. The CPU
   ``morphologyEx`` calls pass no border, so OpenCV uses a constant border holding
   each step's neutral value (the maximum for erode, the minimum for dilate). The
   CUDA filters apply an edge rule of their own, and that rule is not relied on:
   each step is padded on the device by ``r`` pixels with ``cv2.cuda.copyMakeBorder``
   holding that step's neutral value (1 for erode on the {0,1} mask, 0 for dilate),
   filtered, and cropped back, so every kept pixel sees only real pixels and neutral
   padding. ``morph_radius <= 0`` skips morphology, as the CPU path does.

Importing this module needs neither cv2 nor numpy: cv2 is imported only inside
functions, numpy is guarded, and ``retina.t1`` (imported for ``T1Unavailable`` and
``_luma``) guards its own imports.
"""

from __future__ import annotations

import operator
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import t1 as _t1
from .events import make_check

try:
    import numpy as np  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - numpy-less CI leg
    np = None  # type: ignore[assignment]

__all__ = [
    "OPERATIONS",
    "CudaUnavailable",
    "cuda_status",
    "change_mask_cuda",
    "change_mask_check",
    "last_dispatch",
    "witness",
]

#: The R2 chain in execution order. Equals the closure predicate's ``R2_OPS``.
OPERATIONS: Tuple[str, ...] = ("absdiff", "threshold", "morphology_open", "morphology_close")

#: ``cv2.cuda`` functions the chain calls. A build without one cannot run the chain.
_REQUIRED_CUDA_FUNCTIONS: Tuple[str, ...] = ("absdiff", "threshold", "copyMakeBorder", "createMorphologyFilter")

#: Lower-case basename prefixes of the native modules :func:`witness` reports.
#: ``None`` widens the filter to every module loaded in the process.
_NATIVE_MODULE_PREFIXES: Optional[Tuple[str, ...]] = ("cv2", "opencv_", "cudart", "npp", "cublas", "cufft")

#: The CUDA lines of ``cv2.getBuildInformation()`` that :func:`witness` keeps.
_BUILD_LINE_PREFIXES: Tuple[str, ...] = ("NVIDIA CUDA", "NVIDIA GPU arch", "NVIDIA PTX archs")

# Rebound at the top of every change_mask_cuda call. Each entry is written by the code
# path that issued that operation, after its cv2.cuda call returned.
_dispatched: Dict[str, str] = {}


class CudaUnavailable(_t1.T1Unavailable):
    """The R2 chain cannot run on CUDA here; ``reason`` says why.

    It is a :class:`retina.t1.T1Unavailable`, so a caller that already handles T1's
    honest "could not run" signal handles this one too."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = str(reason)


def _import_cv2() -> Tuple[Any, Optional[str]]:
    """``(cv2, None)``, or ``(None, reason)`` when cv2 cannot be imported. Never raises."""
    try:
        import cv2  # type: ignore[import-untyped]
    except Exception as exc:  # ImportError, or an OSError from a native DLL load
        return None, f"cv2 is not importable ({type(exc).__name__}: {exc})"
    return cv2, None


def _who(cv2: Any) -> str:
    return f"cv2 {getattr(cv2, '__version__', '?')} at {getattr(cv2, '__file__', '?')}"


def cuda_status() -> Tuple[bool, str]:
    """``(True, detail)`` only when cv2 imports, ``cv2.cuda`` exists and
    ``cv2.cuda.getCudaEnabledDeviceCount() > 0``; otherwise ``(False, reason)``.

    Never raises. A ``cv2.cuda`` namespace alone is not availability: CPU-only cv2
    builds carry the namespace and report 0 devices, and -1 means the driver is
    missing or incompatible."""
    cv2, reason = _import_cv2()
    if cv2 is None:
        return False, str(reason)
    who = _who(cv2)
    cuda = getattr(cv2, "cuda", None)
    if cuda is None:
        return False, f"{who} has no cv2.cuda namespace (built without CUDA)"
    try:
        count = cuda.getCudaEnabledDeviceCount()
    except Exception as exc:
        return False, f"{who}: cv2.cuda.getCudaEnabledDeviceCount() raised {type(exc).__name__}: {exc}"
    if isinstance(count, bool) or not isinstance(count, int):
        return False, f"{who}: cv2.cuda.getCudaEnabledDeviceCount() returned {count!r}, not a device count"
    if count <= 0:
        return False, (
            f"{who}: cv2.cuda.getCudaEnabledDeviceCount() returned {count}, so no CUDA device is "
            "usable (0: built without CUDA or no device; -1: driver missing or incompatible)"
        )
    return True, f"{who}: {count} CUDA device(s)"


def _float32_threshold(diff_threshold: float) -> float:
    """The float32 threshold ``t`` for which the device's strict ``v > t`` equals
    NumPy's own ``plane > diff_threshold`` for every float32 ``v``.

    Start from the nearest float32 ``c``. The two comparisons can disagree only at
    ``v == c``, and only when NumPy compares in a wider type and ``c`` rounded up
    past the threshold; then the next float32 below ``c`` is used. For a Python float
    under NumPy >= 2 (NEP 50) NumPy compares at float32, and this returns exactly
    ``float(numpy.float32(diff_threshold))``."""
    with np.errstate(over="ignore", invalid="ignore"):
        c = np.float32(diff_threshold)
        if bool((np.array([c], dtype=np.float32) > diff_threshold)[0]):
            c = np.nextafter(c, np.float32(-np.inf))
    return float(c)


def _neutral_step(cv2: Any, morph: Any, mask: Any, radius: int, neutral: float, height: int, width: int) -> Any:
    """One erode or dilate on the device: pad ``radius`` pixels holding the step's
    neutral value, filter, and crop back to ``height`` x ``width``. Every kept pixel
    then sees only real pixels and neutral padding, never the filter's own edge rule."""
    padded = cv2.cuda.copyMakeBorder(
        mask, radius, radius, radius, radius, cv2.BORDER_CONSTANT, value=(neutral, neutral, neutral, neutral)
    )
    filtered = morph.apply(padded)
    return filtered.rowRange(radius, radius + height).colRange(radius, radius + width)


def change_mask_cuda(
    before: Any,
    after: Any,
    *,
    diff_threshold: float,
    morph_radius: int = 1,
) -> "np.ndarray":
    """:func:`retina.t1.change_mask` with the four :data:`OPERATIONS` on the CUDA
    device: same inputs, same semantics, a uint8 {0,1} mask of the same shape.

    Raises :class:`CudaUnavailable` with a reason when :func:`cuda_status` is False,
    when the cv2 build lacks a ``cv2.cuda`` function the chain calls, or when a
    ``cv2.cuda`` call raises ``cv2.error`` part-way. Never falls back to the CPU.
    Raises ``ValueError`` when the two luma planes are not one (H, W) shape."""
    global _dispatched
    dispatched: Dict[str, str] = {}
    _dispatched = dispatched

    ok, reason = cuda_status()
    if not ok:
        raise CudaUnavailable(reason)

    import cv2  # type: ignore[import-untyped]

    cuda = cv2.cuda
    gpu_mat = getattr(cuda, "GpuMat", None) or getattr(cv2, "cuda_GpuMat", None)
    missing = [name for name in _REQUIRED_CUDA_FUNCTIONS if not hasattr(cuda, name)]
    if gpu_mat is None:
        missing.append("GpuMat")
    if missing:
        raise CudaUnavailable(f"{_who(cv2)} lacks cv2.cuda function(s) the R2 chain calls: {', '.join(missing)}")

    x = np.ascontiguousarray(_t1._luma(before).astype(np.float32))
    y = np.ascontiguousarray(_t1._luma(after).astype(np.float32))
    if x.ndim != 2 or x.shape != y.shape:
        raise ValueError(f"change_mask_cuda needs two luma planes of one (H, W) shape, got {x.shape} and {y.shape}")
    height, width = x.shape
    thresh = _float32_threshold(diff_threshold)
    radius = operator.index(morph_radius)
    cv2_error = getattr(cv2, "error", ())

    step = "upload"
    try:
        gx = gpu_mat()
        gx.upload(x)
        gy = gpu_mat()
        gy.upload(y)

        step = "absdiff"
        diff = cuda.absdiff(gx, gy)
        dispatched["absdiff"] = "cuda"

        step = "threshold"
        _, binary = cuda.threshold(diff, thresh, 1.0, cv2.THRESH_BINARY)
        mask = binary.convertTo(cv2.CV_8U)
        dispatched["threshold"] = "cuda"

        if radius > 0:
            step = "morphology_open"
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
            erode = cuda.createMorphologyFilter(cv2.MORPH_ERODE, cv2.CV_8UC1, kernel)
            dilate = cuda.createMorphologyFilter(cv2.MORPH_DILATE, cv2.CV_8UC1, kernel)
            mask = _neutral_step(cv2, erode, mask, radius, 1.0, height, width)
            mask = _neutral_step(cv2, dilate, mask, radius, 0.0, height, width)
            dispatched["morphology_open"] = "cuda"

            step = "morphology_close"
            mask = _neutral_step(cv2, dilate, mask, radius, 0.0, height, width)
            mask = _neutral_step(cv2, erode, mask, radius, 1.0, height, width)
            dispatched["morphology_close"] = "cuda"

        step = "download"
        out = mask.download()
    except cv2_error as exc:
        raise CudaUnavailable(f"cv2.cuda {step} failed ({_who(cv2)}): {exc}") from exc
    return out


def change_mask_check(
    before: Any,
    after: Any,
    *,
    diff_threshold: float,
    morph_radius: int = 1,
    name: str = "change_mask_cuda",
) -> Tuple[Optional["np.ndarray"], Dict[str, Any]]:
    """``(mask, check)``. Computed: the mask and a passing check, detail
    ``"computed on cuda"``, with ``changed_px``. Unavailable: ``(None, check)``
    with ``pass=None`` and the reason as detail: inconclusive, never a pass."""
    try:
        mask = change_mask_cuda(before, after, diff_threshold=diff_threshold, morph_radius=morph_radius)
    except CudaUnavailable as exc:
        return None, make_check(name, None, exc.reason)
    return mask, make_check(name, True, "computed on cuda", changed_px=int(np.count_nonzero(mask)))


def last_dispatch() -> Dict[str, str]:
    """``{operation: "cuda"}`` for each operation the most recent
    :func:`change_mask_cuda` call actually ran through ``cv2.cuda``.

    Each entry is written by the code path that issued the operation, after its call
    returned. An unavailable call leaves ``{}``, ``morph_radius=0`` leaves no
    morphology entries, and a call that failed part-way lists only the steps that
    finished. Returns a copy."""
    return dict(_dispatched)


def _cuda_build_lines(cv2: Any) -> List[str]:
    try:
        text = str(cv2.getBuildInformation())
    except Exception:
        return []
    return [line.strip() for line in text.splitlines() if line.strip().startswith(_BUILD_LINE_PREFIXES)]


def _device(cv2: Any, cuda: Any) -> Dict[str, Any]:
    """Compute capability and total memory of the current CUDA device."""
    out: Dict[str, Any] = {"index": None, "compute_capability": None, "total_memory": None}
    info_cls = getattr(cuda, "DeviceInfo", None) or getattr(cv2, "cuda_DeviceInfo", None)
    try:
        index = int(cuda.getDevice())
        info = info_cls(index)
    except Exception:
        return out
    out["index"] = index
    try:
        out["compute_capability"] = f"{int(info.majorVersion())}.{int(info.minorVersion())}"
    except Exception:
        pass
    try:
        out["total_memory"] = int(info.totalMemory())
    except Exception:
        pass
    return out


def _loaded_native_modules(prefixes: Optional[Sequence[str]] = None) -> List[str]:
    """Absolute paths of the native modules loaded in this process whose lower-case
    basename starts with one of ``prefixes`` (``None``: every module). Windows only;
    ``[]`` elsewhere or when the enumeration fails. Never raises.

    The ctypes argtypes and restypes are load-bearing: without them the 64-bit
    handles are truncated and the enumeration silently returns nothing."""
    if sys.platform != "win32":
        return []
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        current_process = kernel32.GetCurrentProcess
        current_process.argtypes = []
        current_process.restype = wintypes.HANDLE
        enum_modules = kernel32.K32EnumProcessModules
        enum_modules.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.HMODULE),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        enum_modules.restype = wintypes.BOOL
        module_file = kernel32.K32GetModuleFileNameExW
        module_file.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
        module_file.restype = wintypes.DWORD

        process = current_process()
        capacity = 512
        while True:
            handles = (wintypes.HMODULE * capacity)()
            needed = wintypes.DWORD(0)
            if not enum_modules(process, handles, ctypes.sizeof(handles), ctypes.byref(needed)):
                return []
            count = needed.value // ctypes.sizeof(wintypes.HMODULE)
            if count <= capacity:
                break
            capacity = count + 64

        buffer = ctypes.create_unicode_buffer(32768)
        paths: List[str] = []
        for handle in handles[:count]:
            if not handle:
                continue
            if module_file(process, handle, buffer, len(buffer)):
                paths.append(buffer.value)
    except Exception:
        return []

    if prefixes is None:
        return paths
    wanted = tuple(p.lower() for p in prefixes)
    return [p for p in paths if p.replace("/", "\\").rsplit("\\", 1)[-1].lower().startswith(wanted)]


def witness() -> Dict[str, Any]:
    """What this process would compute with: ``cv2_file``, ``cv2_version``,
    ``cuda_device_count``, ``device`` (index, compute capability, total memory),
    ``cuda_build_info`` (the NVIDIA CUDA, NVIDIA GPU arch and NVIDIA PTX archs lines
    of ``cv2.getBuildInformation()``) and ``loaded_modules`` (absolute paths of the
    loaded cv2, opencv_*, cudart*, npp*, cublas* and cufft* modules; ``[]`` off
    Windows).

    Never raises. A field that cannot be read is None; the two list fields are then
    empty. ``device`` is queried only when the device count is above 0."""
    report: Dict[str, Any] = {
        "cv2_file": None,
        "cv2_version": None,
        "cuda_device_count": None,
        "device": None,
        "cuda_build_info": [],
        "loaded_modules": [],
    }
    cv2, _ = _import_cv2()
    if cv2 is not None:
        report["cv2_file"] = getattr(cv2, "__file__", None)
        report["cv2_version"] = getattr(cv2, "__version__", None)
        report["cuda_build_info"] = _cuda_build_lines(cv2)
        cuda = getattr(cv2, "cuda", None)
        if cuda is not None:
            try:
                count = cuda.getCudaEnabledDeviceCount()
            except Exception:
                count = None
            if isinstance(count, int) and not isinstance(count, bool):
                report["cuda_device_count"] = count
                if count > 0:
                    report["device"] = _device(cv2, cuda)
    report["loaded_modules"] = _loaded_native_modules(_NATIVE_MODULE_PREFIXES)
    return report
