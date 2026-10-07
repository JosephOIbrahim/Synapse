"""Firefly detection: isolated pixels far brighter than their neighbourhood.

This lives in the RETINA worker tree because it needs ``cv2``, and ``cv2`` may
never be imported host-side (blueprint P5, ``tests/test_retina_boundary.py``).
It is the localised companion to :func:`retina.t1.firefly_count`, which is a
whole-frame ``mean + k*std`` census with no positions. This one reports where.
It imports nothing from ``synapse`` (the worker venv does not carry it) and
only :class:`retina.t1.T1Unavailable` from the rest of ``retina``.

Method, all on Rec.709 luminance:

1. ``residual = L - median5x5(L)`` (``cv2.medianBlur``, border replicated).
2. ``sigma`` = 1.4826 x the median absolute deviation of the residual over the
   whole frame: a noise estimate that the fireflies themselves cannot inflate.
   It is floored at ``1e-6`` so a noise-free frame does not flag float rounding.
3. A pixel is a candidate when ``residual > threshold_sigma * sigma``.
4. Candidates are grouped with ``cv2.connectedComponentsWithStats``
   (8-connected). A group of at most ``max_blob_area`` pixels is a firefly.
   Larger groups are bright features, not fireflies; they are counted in
   ``large_blobs_ignored`` so they never vanish silently.
5. A small group is only a firefly if it is isolated: no pixel touching it
   (``cv2.dilate`` with a 3x3 kernel, minus the group) is brighter than the
   local median at its peak plus the threshold. A group that touches a bright
   region (the corner of a sharp highlight, say) is counted in
   ``attached_blobs_ignored`` instead.

A 5x5 median sees through blobs up to about 3x3, so the default
``max_blob_area`` of 9 matches what step 1 can isolate.
"""

from __future__ import annotations

import os

from .t1 import T1Unavailable

REC709_WEIGHTS = (0.2126, 0.7152, 0.0722)


class FirefliesUnavailable(T1Unavailable):
    """cv2 or numpy is missing, or what imported is not the real package."""


def _real(mod, name, pip_name):
    if mod is None or not isinstance(getattr(mod, "__version__", None), str):
        raise FirefliesUnavailable(
            f"'{name}' imported but has no str __version__, so it is not the real "
            f"package (pip install {pip_name} in the RETINA venv)"
        )
    return mod


def require_numpy():
    try:
        import numpy
    except ImportError as exc:
        raise FirefliesUnavailable(
            f"firefly scan needs numpy (pip install numpy in the RETINA venv): {exc}"
        ) from exc
    return _real(numpy, "numpy", "numpy")


def require_cv2():
    try:
        import cv2
    except ImportError as exc:
        raise FirefliesUnavailable(
            "firefly scan needs cv2 (pip install opencv-python-headless in the RETINA "
            f"venv, retina/requirements.txt): {exc}"
        ) from exc
    return _real(cv2, "cv2", "opencv-python-headless")


def _check_rgb(np, img):
    arr = np.asarray(img)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError(f"expected an HxWx3 RGB array, got shape {arr.shape}")
    if arr.shape[0] == 0 or arr.shape[1] == 0:
        raise ValueError(f"empty image, shape {arr.shape}")
    return arr.astype(np.float32, copy=False)


def _luminance(np, arr):
    return (arr * np.asarray(REC709_WEIGHTS, dtype=np.float32)).sum(axis=2, dtype=np.float32)


_SIGMA_FLOOR = 1e-6
_MAD_TO_SIGMA = 1.4826


def _r(x):
    return round(float(x), 6)


def fireflies(
    img,
    threshold_sigma=6.0,
    *,
    max_blob_area=9,
    max_listed=50,
    mask_path=None,
):
    """Firefly report for ``img`` (float HxWx3 linear RGB).

    Returns ``count`` (fireflies = small isolated blobs), ``pixel_count``
    (pixels in them), ``large_blobs_ignored``, ``attached_blobs_ignored``,
    ``sigma``, ``threshold``, ``worst`` (the
    single pixel with the largest residual: ``x``, ``y``, ``rgb``,
    ``luminance``, ``sigmas``; ``None`` when there are no fireflies) and
    ``fireflies``: up to ``max_listed`` entries, brightest residual first, each
    with the peak pixel ``x``/``y``, ``area`` and ``sigmas``.

    Pixels with a NaN or infinite channel are set to 0 before analysis and
    counted in ``nonfinite_pixels``. When ``mask_path`` is given an 8-bit PNG
    is written there: 255 on firefly pixels, 0 elsewhere. A missing cv2 raises
    :class:`FirefliesUnavailable` (a :class:`retina.t1.T1Unavailable`). Bad
    arguments raise :class:`ValueError`.
    """
    np = require_numpy()
    cv2 = require_cv2()
    if not threshold_sigma > 0:
        raise ValueError(f"threshold_sigma must be above 0, got {threshold_sigma}")
    if max_blob_area < 1:
        raise ValueError(f"max_blob_area must be at least 1, got {max_blob_area}")
    arr = _check_rgb(np, img)
    finite = np.isfinite(arr).all(axis=2)
    nonfinite = int(finite.size - int(finite.sum()))
    if nonfinite:
        arr = np.where(finite[:, :, None], arr, np.float32(0.0)).astype(np.float32)
    height, width = arr.shape[:2]

    lum = np.ascontiguousarray(_luminance(np, arr), dtype=np.float32)
    local = cv2.medianBlur(lum, 5)
    residual = lum - local
    mad = float(np.median(np.abs(residual - np.median(residual))))
    sigma = max(_MAD_TO_SIGMA * mad, _SIGMA_FLOOR)
    threshold = threshold_sigma * sigma
    candidates = (residual > threshold).astype(np.uint8)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        candidates, connectivity=8, ltype=cv2.CV_32S
    )
    mask = np.zeros((height, width), dtype=np.uint8)
    kernel = np.ones((3, 3), dtype=np.uint8)
    found = []
    large = 0
    attached = 0
    for label in range(1, n_labels):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area > max_blob_area:
            large += 1
            continue
        # Work in the blob's bounding box grown by one pixel, clipped to the frame.
        bx = int(stats[label, cv2.CC_STAT_LEFT])
        by = int(stats[label, cv2.CC_STAT_TOP])
        bw = int(stats[label, cv2.CC_STAT_WIDTH])
        bh = int(stats[label, cv2.CC_STAT_HEIGHT])
        x0, y0 = max(bx - 1, 0), max(by - 1, 0)
        x1, y1 = min(bx + bw + 1, width), min(by + bh + 1, height)
        blob = (labels[y0:y1, x0:x1] == label).astype(np.uint8)
        ring = cv2.dilate(blob, kernel).astype(bool) & ~blob.astype(bool)
        ys, xs = np.nonzero(blob)
        k = int(np.argmax(residual[y0:y1, x0:x1][ys, xs]))
        y, x = int(ys[k]) + y0, int(xs[k]) + x0
        if ring.any() and float(lum[y0:y1, x0:x1][ring].max()) > float(local[y, x]) + threshold:
            attached += 1
            continue
        mask[ys + y0, xs + x0] = 255
        found.append(
            {
                "x": x,
                "y": y,
                "area": area,
                "sigmas": _r(residual[y, x] / sigma),
                "_residual": float(residual[y, x]),
            }
        )
    found.sort(key=lambda f: (-f["_residual"], f["y"], f["x"]))

    worst = None
    if found:
        top = found[0]
        x, y = top["x"], top["y"]
        worst = {
            "x": x,
            "y": y,
            "rgb": [_r(v) for v in arr[y, x]],
            "luminance": _r(lum[y, x]),
            "sigmas": top["sigmas"],
        }
    listed = [{k: v for k, v in f.items() if k != "_residual"} for f in found[:max_listed]]

    result = {
        "width": int(width),
        "height": int(height),
        "nonfinite_pixels": nonfinite,
        "threshold_sigma": float(threshold_sigma),
        "sigma": _r(sigma),
        "threshold": _r(threshold),
        "max_blob_area": int(max_blob_area),
        "count": len(found),
        "pixel_count": int((mask > 0).sum()),
        "large_blobs_ignored": large,
        "attached_blobs_ignored": attached,
        "worst": worst,
        "fireflies": listed,
        "fireflies_truncated": len(found) > len(listed),
        "mask_path": None,
    }
    if mask_path is not None:
        path = os.path.abspath(os.fspath(mask_path))
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if not cv2.imwrite(path, mask):
            raise OSError(f"cv2.imwrite could not write the firefly mask to {path}")
        result["mask_path"] = path
    return result
