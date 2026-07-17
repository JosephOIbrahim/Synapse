"""Ingest — turn husk EXR products into the linear float32 planes T1 measures.

Blueprint §3: **OpenImageIO for ingest — color-managed via the protected
``OCIO`` env: linear float32 planes for metrics; display-transformed 8-bit
proxies for T3 and panel thumbnails.** ``cv2.imread`` is explicitly NOT the EXR
path (CVE-gated, color-blind) — the worker reads through OIIO, never OpenCV.

What this module does, and what it deliberately does not:

* **Pixels via OIIO.** ``read_subimage`` mirrors the repo's already-live-verified
  OIIO idiom (``ImageInput.open`` / ``.spec()`` / ``.read_image(..., oiio.FLOAT)``
  — see ``python/synapse/autonomy/evaluator.py``), extended with
  ``seek_subimage`` for husk's multi-part frames. The OIIO leg runs only where
  OIIO is installed (the worker venv); its live verification is owed on that
  build (guarded ingest tests skip without OIIO).
* **Header truth via ``exr_header``.** *Which* subimage is the ID part, and the
  per-channel pixel type, are HEADER questions — they stay on the committed,
  dependency-free ``exr_header`` reader (catalog item 6: per-AOV pixel format is
  data-driven — beauty ``C`` is 16-bit half, the ``primid`` AOV is float32; T1
  ingest reads types from the header, never assumes half). OIIO reads PIXELS; the
  header reader answers structure.
* **Colour is protected, not clobbered.** ``$OCIO`` is read, never set — the same
  protected-env pattern the host already uses (``handler_helpers._convert_preview``
  injects ``$OCIO`` into a subprocess env; ``harness/verify/checks.py`` gates on it
  being set). Metric planes are LINEAR scene-referred pixels straight from the EXR
  (beauty is ``lin_rec709``); **ID / data AOVs (``Raw`` colorspace) are never
  colour-transformed** — only display/beauty planes ever go through a display
  transform, and the display-transformed 8-bit proxy is a T3/panel concern (M5).
  M2 provides the linear-plane ingest seam and an honest ``$OCIO`` report.
* **One orientation.** OIIO returns rows top-down (scanline 0 == top); T1 works
  entirely top-down, so the manifest's camera-projection math must place ``y=0``
  at the top too (``t1.project_bbox`` does). The COP-readback bottom-up caveat
  (catalog item 4) belongs to the M4 COP oracle, not this file.

Zero ``hou``. OIIO/numpy imports are guarded (CLAUDE.md §12 idiom) so this module
imports cleanly in stock CI; the read functions raise :class:`IngestUnavailable`
if called without OIIO rather than crashing at import.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .exr_header import ExrHeaderError, read_exr_header

try:  # numpy: present wherever cv2/OIIO are (both depend on it)
    import numpy as np  # type: ignore[import-untyped]

    _NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised in the numpy-less CI leg
    np = None  # type: ignore[assignment]
    _NUMPY_AVAILABLE = False

try:  # OpenImageIO: worker-venv only (Houdini ships it; PyPI wheel per platform)
    import OpenImageIO as oiio  # type: ignore[import-untyped]

    _OIIO_AVAILABLE = True
except ImportError:  # pragma: no cover - the stock-CI leg
    oiio = None  # type: ignore[assignment]
    _OIIO_AVAILABLE = False

# Catalog item 6: the ID part is named ``primid`` (channel ``primid.id``); the
# beauty part is ``C``. The ID AOV rides ``Raw`` colorspace — never transformed.
ID_PART_NAMES = ("primid", "id", "cryptomatte")


class IngestError(RuntimeError):
    """Ingest failed on a real product (unreadable, wrong shape, OIIO error)."""


class IngestUnavailable(IngestError):
    """A read was requested but OIIO (or numpy) is not installed — the honest
    signal for the stock-CI / no-venv leg, never a silent empty array."""


def oiio_available() -> bool:
    return _OIIO_AVAILABLE and _NUMPY_AVAILABLE


def ocio_config() -> Optional[str]:
    """The active OCIO config path, read from the PROTECTED ``$OCIO`` env — this
    module never sets or clobbers it (blueprint §3; the host's protected-env
    pattern)."""
    return os.environ.get("OCIO")


def color_env() -> Dict[str, Any]:
    """Honest report of the colour environment (never mutates it). ``color_managed``
    is True only when an OCIO config is actually present — a missing ``$OCIO`` is
    reported plainly, never faked (mirrors ``handler_helpers`` honesty)."""
    ocio = ocio_config()
    return {
        "ocio_set": ocio is not None,
        "ocio_config": ocio,
        # Metric planes are LINEAR and un-transformed, so metrics are colour-safe
        # regardless of $OCIO; the flag reports display-proxy managability (M5).
        "color_managed": ocio is not None,
        "note": (
            "linear metric planes read un-transformed; display-referred 8-bit "
            "proxy (OCIO-managed) is the T3/panel path (M5)"
        ),
    }


def _require() -> None:
    if not _OIIO_AVAILABLE:
        raise IngestUnavailable(
            "OpenImageIO not installed — ingest runs in the RETINA worker venv "
            "(retina/requirements.txt). cv2.imread is not a substitute (blueprint §3)."
        )
    if not _NUMPY_AVAILABLE:
        raise IngestUnavailable("numpy not installed — required for ingest planes.")


def subimage_count(path: str) -> int:
    """Number of subimages (parts) in the EXR, read from the header (no pixels)."""
    return len(read_exr_header(path).parts)


def read_subimage(path: str, subimage: int = 0) -> "np.ndarray":
    """Read one subimage's pixels as an ``(H, W, C)`` float32 array, top-down.

    Requests ``oiio.FLOAT`` so half and float32 AOVs both arrive as float32 (the
    per-AOV pixel type is data-driven — catalog item 6 — so we normalise the
    numeric dtype here while ``exr_header`` remains the authority on the *declared*
    type). Never colour-transforms: these are the raw linear/Raw pixels.
    """
    _require()
    inp = oiio.ImageInput.open(path)
    if inp is None:  # OIIO couldn't open it — surface OIIO's own error, honestly
        raise IngestError(f"OIIO could not open {path!r}: {oiio.geterror()}")
    try:
        if subimage != 0:
            # seek_subimage(subimage, miplevel) — the multi-part read seam,
            # verified live in the worker venv (OIIO 3.1.15.0).
            if not inp.seek_subimage(subimage, 0):
                raise IngestError(
                    f"{path!r}: no subimage {subimage} ({oiio.geterror()})"
                )
        spec = inp.spec()
        # OIIO 3.x Python RETURNS the pixels as an ndarray (probed live). NOTE: a
        # Houdini-seeded venv on OIIO 2.x uses the buffer-fill form instead
        # (``inp.read_image(subimage, 0, oiio.FLOAT, buf)`` — the evaluator.py
        # idiom); switch to that if you seed from hython's older OIIO.
        pixels = inp.read_image(oiio.FLOAT)
        if pixels is None:
            raise IngestError(f"OIIO read failed for {path!r}: {oiio.geterror()}")
        arr = np.asarray(pixels, dtype=np.float32)
        if arr.ndim == 2:  # single-channel comes back (H, W)
            arr = arr[:, :, None]
        return arr.reshape(spec.height, spec.width, spec.nchannels)
    finally:
        inp.close()


def read_beauty(path: str, *, subimage: int = 0) -> "np.ndarray":
    """The beauty plane (part ``C``), linear scene-referred float32 — the plane
    T1's exposure/clip/firefly/SSIM metrics run on. Left un-transformed: it is
    already linear (``lin_rec709``), and metrics compare like-for-like."""
    return read_subimage(path, subimage)


def find_id_subimage(path: str) -> Optional[int]:
    """Header-driven: index of the subimage carrying the integer object-ID AOV
    (part named ``primid``/``id``/…), or ``None`` if the frame has no ID part —
    the honest signal that containment cannot run on this product (blueprint §7)."""
    header = read_exr_header(path)
    for idx, part in enumerate(header.parts):
        name = (part.name or "").lower()
        if any(tag in name for tag in ID_PART_NAMES):
            return idx
        for ch in part.channels:
            if any(tag in ch.name.lower() for tag in ID_PART_NAMES):
                return idx
    return None


def read_id_plane(path: str, *, subimage: Optional[int] = None) -> "np.ndarray":
    """The integer object-ID matte source as an ``(H, W)`` float32 array (``Raw``
    colorspace — NEVER colour-transformed). Locates the ID part from the header
    when ``subimage`` is not given. Raises :class:`IngestError` if the frame has no
    ID AOV — the honest "cannot run" rather than a fabricated empty matte."""
    _require()
    if subimage is None:
        subimage = find_id_subimage(path)
        if subimage is None:
            raise IngestError(
                f"{path!r}: no integer object-ID AOV present (parts: "
                f"{[p.name for p in read_exr_header(path).parts]}) — containment "
                "cannot run; declare an ID AOV (karmarendersettings.primid=1)."
            )
    plane = read_subimage(path, subimage)
    # ID AOV is single-channel (primid.id); collapse a stray channel axis.
    if plane.ndim == 3:
        plane = plane[..., 0]
    return plane


def read_planes(path: str) -> Dict[str, Any]:
    """Read every subimage into a dict keyed by part name (header-derived), plus
    the colour-env report. Convenience for the worker; each plane is float32
    top-down, un-transformed. Header structure comes from ``exr_header``; pixels
    from OIIO."""
    _require()
    header = read_exr_header(path)
    planes: Dict[str, Any] = {}
    part_types: List[Dict[str, Any]] = []
    for idx, part in enumerate(header.parts):
        key = part.name or (f"subimage_{idx}" if header.multipart else "C")
        planes[key] = read_subimage(path, idx)
        part_types.append(
            {
                "name": part.name,
                "channels": [
                    {"name": c.name, "pixel_type": c.pixel_type} for c in part.channels
                ],
            }
        )
    return {"planes": planes, "parts": part_types, "color_env": color_env()}


__all__ = [
    "IngestError",
    "IngestUnavailable",
    "oiio_available",
    "ocio_config",
    "color_env",
    "subimage_count",
    "read_subimage",
    "read_beauty",
    "find_id_subimage",
    "read_id_plane",
    "read_planes",
    "ExrHeaderError",
]
