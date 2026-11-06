"""Exposure statistics for a linear RGB frame.

Luminance is Rec.709 / sRGB-primaries relative luminance on linear values:
``Y = 0.2126 R + 0.7152 G + 0.0722 B``. Statistics are numpy. The optional
histogram PNG is drawn with numpy and written through OpenImageIO; no cv2
(this is a host surface, blueprint P5).

The suggested offset is ``log2(target_luminance / median_luminance)`` stops:
the exposure change that would put the frame's median luminance on the
target (default 0.18, scene-linear middle grey). The median, not the mean,
so a few hot pixels do not drag the suggestion.
"""

from __future__ import annotations

import math
import os

from synapse.cv.deps import CVInputError, require_numpy, require_oiio
from synapse.cv.reader import check_rgb

REC709_WEIGHTS = (0.2126, 0.7152, 0.0722)

# Histogram layout: luminance in stops relative to the target.
_HIST_LO_STOPS = -10.0
_HIST_HI_STOPS = 6.0
_HIST_BINS = 160
_HIST_W = 640
_HIST_H = 200


def luminance(img):
    """Rec.709 relative luminance of an HxWx3 linear RGB array, float32 HxW."""
    np = require_numpy()
    arr = check_rgb(img)
    w = np.asarray(REC709_WEIGHTS, dtype=np.float32)
    return (arr * w).sum(axis=2, dtype=np.float32)


def _r(x):
    return None if x is None else round(float(x), 6)


def exposure(
    img,
    *,
    black_threshold=0.001,
    clip_threshold=1.0,
    target_luminance=0.18,
    histogram_path=None,
):
    """Exposure report for ``img`` (float HxWx3 linear RGB).

    - ``black_pct``: percent of pixels whose luminance is at or below
      ``black_threshold``.
    - ``clipped_pct``: percent of pixels with any channel at or above
      ``clip_threshold`` (1.0: display-referred white).
    - ``suggested_offset_stops``: see the module docstring. ``None`` when the
      median luminance is not above zero; ``offset_note`` says why.
    - Pixels with a NaN or infinite channel are left out of every statistic
      and counted in ``nonfinite_pixels``.

    When ``histogram_path`` is given, a PNG of the log2 luminance histogram
    (stops relative to the target, with the target and clip level marked) is
    written there through OpenImageIO; a missing OpenImageIO raises
    :class:`CVDependencyError` and a failed write raises :class:`OSError`.
    """
    np = require_numpy()
    if not target_luminance > 0:
        raise CVInputError(f"target_luminance must be above 0, got {target_luminance}")
    if histogram_path is not None:
        oiio = require_oiio()
    arr = check_rgb(img)
    height, width = arr.shape[:2]
    finite = np.isfinite(arr).all(axis=2)
    nonfinite = int(finite.size - int(finite.sum()))
    if nonfinite == finite.size:
        raise CVInputError("every pixel has a NaN or infinite channel")
    lum = luminance(arr)[finite].astype(np.float64)
    maxc = arr.max(axis=2)[finite]
    n = lum.size

    mean_l = float(lum.mean())
    median_l = float(np.median(lum))
    black_pct = 100.0 * float((lum <= black_threshold).sum()) / n
    clipped_pct = 100.0 * float((maxc >= clip_threshold).sum()) / n

    if median_l > 0:
        offset = math.log2(target_luminance / median_l)
        note = None
    else:
        offset = None
        note = "median luminance is not above 0; no exposure offset reaches the target"

    result = {
        "width": int(width),
        "height": int(height),
        "pixels_measured": int(n),
        "nonfinite_pixels": nonfinite,
        "luminance_weights": "rec709",
        "mean_luminance": _r(mean_l),
        "median_luminance": _r(median_l),
        "black_threshold": float(black_threshold),
        "black_pct": _r(black_pct),
        "clip_threshold": float(clip_threshold),
        "clipped_pct": _r(clipped_pct),
        "target_luminance": float(target_luminance),
        "offset_basis": "median",
        "suggested_offset_stops": _r(offset),
        "offset_note": note,
        "histogram_path": None,
    }
    if histogram_path is not None:
        result["histogram_path"] = _write_histogram(
            oiio, np, lum, target_luminance, clip_threshold, histogram_path
        )
    return result


def _write_histogram(oiio, np, lum, target, clip, path):
    path = os.path.abspath(os.fspath(path))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tiny = target * 2.0 ** (_HIST_LO_STOPS - 1)
    stops = np.log2(np.maximum(lum, tiny) / target)
    stops = np.clip(stops, _HIST_LO_STOPS, _HIST_HI_STOPS)
    counts, _ = np.histogram(stops, bins=_HIST_BINS, range=(_HIST_LO_STOPS, _HIST_HI_STOPS))
    # RGB, row 0 at the top.
    canvas = np.full((_HIST_H, _HIST_W, 3), 24, dtype=np.uint8)
    peak = max(int(counts.max()), 1)
    bin_w = _HIST_W / _HIST_BINS
    for i, c in enumerate(counts):
        if not c:
            continue
        h = max(1, int(round((_HIST_H - 10) * c / peak)))
        x0 = int(round(i * bin_w))
        x1 = max(x0 + 1, int(round((i + 1) * bin_w)) - 1)
        canvas[_HIST_H - h :, x0:x1] = 200

    def _x(s):
        frac = (s - _HIST_LO_STOPS) / (_HIST_HI_STOPS - _HIST_LO_STOPS)
        return int(round(min(max(frac, 0.0), 1.0) * (_HIST_W - 1)))

    canvas[:, _x(0.0)] = (80, 200, 80)  # target: green
    if clip > 0:
        canvas[:, _x(math.log2(clip / target))] = (220, 60, 60)  # clip level: red

    out = oiio.ImageOutput.create(path)
    if out is None:
        raise OSError(f"OpenImageIO has no writer for {path}: {oiio.geterror()}")
    try:
        spec = oiio.ImageSpec(_HIST_W, _HIST_H, 3, "uint8")
        if not out.open(path, spec) or not out.write_image(canvas):
            raise OSError(f"OpenImageIO could not write the histogram to {path}: {out.geterror()}")
    finally:
        out.close()
    return path
