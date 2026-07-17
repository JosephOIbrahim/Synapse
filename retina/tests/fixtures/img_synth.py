"""Synthetic image-pair + ID-plane builders for T1 pixel-metric tests.

Same philosophy as ``exr_synth`` (T0's header builder): hermetic, deterministic,
reviewable source that documents exactly what it produces. Where ``exr_synth``
hand-builds EXR *header bytes* (T0 reads headers), this builds the *pixel arrays*
T1 measures — before/after beauty planes and an integer object-ID plane — so the
scoped-delta path (change mask × ID matte containment + SSIM-outside) is exercised
without Houdini or a real render (blueprint §3: CRUCIBLE feeds synthetic inputs;
the whole organ is testable without Houdini running).

numpy is imported at module top: this fixture is only ever imported *inside*
cv2-guarded tests (cv2's dependency stack always brings numpy), and ``retina/``
is never collected by pytest directly, so a numpy-less CI run never imports it.
The OIIO EXR-writer helper is separately guarded — it is only used by the
OIIO-gated ingest tests.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import numpy as np

try:  # OIIO: only the ingest tests need it, and they skip when it is absent
    import OpenImageIO as oiio  # type: ignore[import-untyped]

    _OIIO_AVAILABLE = True
except ImportError:  # pragma: no cover
    oiio = None  # type: ignore[assignment]
    _OIIO_AVAILABLE = False


def flat_plane(h: int = 64, w: int = 64, c: int = 3, value: float = 0.25) -> np.ndarray:
    """A uniform linear plane (H, W, C) float32."""
    return np.full((h, w, c), float(value), dtype=np.float32)


def gradient_plane(h: int = 64, w: int = 64, c: int = 3) -> np.ndarray:
    """A smooth horizontal gradient — structure for SSIM to latch onto (a flat
    plane has zero variance and degenerate SSIM)."""
    row = np.linspace(0.1, 0.9, w, dtype=np.float32)
    base = np.tile(row, (h, 1))
    return np.repeat(base[:, :, None], c, axis=2)


def with_patch(
    plane: np.ndarray,
    *,
    y0: int,
    y1: int,
    x0: int,
    x1: int,
    value: float,
) -> np.ndarray:
    """Return a copy of ``plane`` with a rectangular region overwritten — the
    'change' between before and after (top-down coords, y=0 at top)."""
    out = plane.copy()
    out[y0:y1, x0:x1, ...] = float(value)
    return out


def before_after_pair(
    *,
    h: int = 64,
    w: int = 64,
    c: int = 3,
    region: Tuple[int, int, int, int] = (16, 32, 16, 32),
    change_value: float = 0.95,
) -> Tuple[np.ndarray, np.ndarray]:
    """A (before, after) pair differing only inside ``region`` = (y0, y1, x0, x1).
    ``before`` is a gradient (SSIM-friendly); ``after`` overwrites the region."""
    before = gradient_plane(h, w, c)
    y0, y1, x0, x1 = region
    after = with_patch(before, y0=y0, y1=y1, x0=x0, x1=x1, value=change_value)
    return before, after


def id_plane(
    h: int = 64,
    w: int = 64,
    *,
    background_id: int = 0,
    regions: Optional[Sequence[Tuple[int, Tuple[int, int, int, int]]]] = None,
) -> np.ndarray:
    """An integer object-ID plane (H, W) float32 (husk writes primid as float32).
    ``regions`` = [(id, (y0, y1, x0, x1)), ...] stamps target IDs into rectangles;
    everything else is ``background_id``."""
    plane = np.full((h, w), float(background_id), dtype=np.float32)
    for prim_id, (y0, y1, x0, x1) in regions or []:
        plane[y0:y1, x0:x1] = float(prim_id)
    return plane


def inject_fireflies(
    plane: np.ndarray, *, count: int = 5, value: float = 50.0, seed: int = 0
) -> np.ndarray:
    """Scatter ``count`` ultra-bright single-pixel outliers — for the firefly
    census. Deterministic given ``seed``."""
    out = plane.copy()
    rng = np.random.default_rng(seed)
    h, w = out.shape[:2]
    ys = rng.integers(0, h, size=count)
    xs = rng.integers(0, w, size=count)
    out[ys, xs, ...] = float(value)
    return out


def inject_nan(plane: np.ndarray, *, y: int = 0, x: int = 0) -> np.ndarray:
    out = plane.copy()
    out[y, x, ...] = np.nan
    return out


# ---------------------------------------------------------------------------
# OIIO EXR writer — only the OIIO-gated ingest tests use this.
# ---------------------------------------------------------------------------

def oiio_available() -> bool:
    return _OIIO_AVAILABLE


def write_multipart_exr(
    path: str,
    beauty: np.ndarray,
    id_plane_arr: Optional[np.ndarray] = None,
    *,
    beauty_channels: Sequence[str] = ("R", "G", "B"),
) -> str:
    """Write a 2-part EXR (beauty part ``C`` + ID part ``primid``) via OIIO,
    mirroring the live husk layout (catalog item 6). Used only by ingest tests
    that skip without OIIO. Returns ``path``."""
    if not _OIIO_AVAILABLE:  # pragma: no cover - guarded by the caller's skipif
        raise RuntimeError("OpenImageIO not installed — write_multipart_exr needs it")
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    h, w = beauty.shape[:2]

    beauty_spec = oiio.ImageSpec(w, h, len(beauty_channels), oiio.HALF)
    beauty_spec.channelnames = list(beauty_channels)
    beauty_spec["name"] = "C"

    id_spec = None
    if id_plane_arr is not None:
        id_spec = oiio.ImageSpec(w, h, 1, oiio.FLOAT)
        id_spec.channelnames = ["id"]
        id_spec["name"] = "primid"

    out = oiio.ImageOutput.create(path)
    if out is None:
        raise RuntimeError(f"OIIO could not create {path}: {oiio.geterror()}")
    # OIIO 3.1 multi-subimage write (probed live in the worker venv): open with
    # the FULL spec list, write subimage 0, then re-open per subimage with the
    # string mode 'AppendSubimage' (the mode is a str, NOT a module attribute).
    specs = [beauty_spec] if id_spec is None else [beauty_spec, id_spec]
    if not out.open(path, specs):
        raise RuntimeError(f"OIIO open failed for {path}: {out.geterror()}")
    out.write_image(
        np.ascontiguousarray(beauty[:, :, : len(beauty_channels)], dtype=np.float32)
    )
    if id_spec is not None:
        if not out.open(path, id_spec, "AppendSubimage"):
            raise RuntimeError(f"OIIO AppendSubimage failed: {out.geterror()}")
        # write_image wants (H, W, nchannels); reshape a 2D ID plane to (H, W, 1)
        # so the single channel is laid out correctly (a bare 2D array corrupts).
        id3 = id_plane_arr[:, :, None] if id_plane_arr.ndim == 2 else id_plane_arr
        out.write_image(np.ascontiguousarray(id3, dtype=np.float32))
    out.close()
    return path
