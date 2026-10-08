"""Firefly detection: isolated pixels far brighter than their neighbourhood.

This lives in the RETINA worker tree because it needs ``cv2``, and ``cv2`` may
never be imported host-side (blueprint P5, ``tests/test_retina_boundary.py``).
It is the localised companion to :func:`retina.t1.firefly_count`, which is a
whole-frame ``mean + k*std`` census with no positions. This one reports where.
It imports nothing from ``synapse`` (the worker venv does not carry it) and
only :class:`retina.t1.T1Unavailable` from the rest of ``retina``.

Method, all on Rec.709 luminance:

1. ``residual = L - median5x5(L)`` (``cv2.medianBlur``, border replicated).
2. Noise per stop. 1.4826 x the median absolute deviation (MAD) of the
   residual, which the fireflies themselves cannot inflate, is taken
   separately for groups of pixels at the same level. *Black* pixels have a
   5x5 median at or below 0 (an object on black or on a transparent
   background, Karma's canonical frame) and form one group. *Lit* pixels are
   grouped by stop, ``floor(log2(5x5 median))``, because Monte Carlo noise
   grows with brightness and one absolute sigma for a frame with a dark and
   a bright region flags the bright one's noise. (One MAD over the whole
   frame is also wrong whenever black is at least half of it: the MAD is
   then 0 whatever the noise on the object, the threshold collapses and
   object noise floods the mask.) A lit stop's MAD is taken over its *live*
   pixels, those that are neither *flat* (``cv2.dilate`` == ``cv2.erode`` of
   L over 3x3: the pixel and its eight neighbours are one exact value) nor
   *smooth* (every residual in the 3x3 is at most ``_SMOOTH_REL``, 2^-10,
   about one half-float step, of the 5x5 median). A constant backdrop (a
   constant-colour dome, a grey lookdev backdrop, a flat emissive card) is
   flat; a noise-free linear gradient, whose 5x5 median is the pixel
   itself, is smooth; neither can fill the object's stop with zeros the way
   black would. The flatness window is 3x3, not 5x5, because a backdrop
   pixel near the silhouette has a residual of exactly 0 and carries no
   noise; a wider window keeps a wider ring of those zeros and drags the
   MAD down. When fewer than ``_MIN_NOISE_PIXELS`` of the stop are live, the
   whole stop is used (an all-flat frame is judged as before). These
   sigmas are floored at ``1e-6``.
   A stop with fewer than ``_MIN_NOISE_PIXELS`` pixels borrows the sigma of
   the nearest stop that has enough (the brighter one on a tie); ``noise``
   in the result lists every stop and what it borrowed. When lit pixels
   exist but no stop has enough, their noise cannot be estimated and the
   result is *inconclusive*: ``count`` is ``None`` with a ``note``, never a
   number (the retina/t1.py honesty rule). The stop sigmas are the reported
   reference and the fallback; detection uses step 3.
3. Local noise. Each lit pixel is judged against the noise around it: the
   live pixels of its own stop in the 31x31 window centred on it
   (``_LOCAL_RADIUS`` 15). Their mean ``|residual|``, clipped at
   ``_LOCAL_CLIP`` (4) sigmas so a firefly cannot inflate its own yardstick,
   times sqrt(pi / 2) is the local sigma (``cv2.boxFilter`` sums, per stop;
   two passes, the first clipped at the stop's sigma, the second at the
   first pass's). A window with fewer than ``_MIN_LOCAL_PIXELS`` (64) live
   pixels of the stop keeps the stop's sigma; ``noise.local_pixels`` counts
   the lit pixels that got a local one. Black pixels keep the black group's
   sigma. A lit pixel's sigma is never below ``_SMOOTH_REL`` x its 5x5
   median: a residual under about 0.6% of the level (6 such sigmas) is
   within half-float precision and no evidence of a firefly.
   A pixel is a candidate when ``residual > threshold_sigma * sigma`` there.
4. Candidates are grouped with ``cv2.connectedComponentsWithStats``
   (8-connected). A group of at most ``max_blob_area`` pixels is a firefly.
   Larger groups are bright features, not fireflies; they are counted in
   ``large_blobs_ignored`` so they never vanish silently.
5. A small group is only a firefly if it is isolated: no pixel q touching it
   (``cv2.dilate`` with a 3x3 kernel, minus the group) is brighter than the
   background expected at q plus the threshold at the peak p. The expected
   background is the local median at p, raised by the background's trend:
   the rise of the local median from the mirror pixel 2p - q to p and from
   p to q, the smaller of the two, less ``_TREND_NOISE`` (3) sigmas at p (a
   noisy surface's medians differ by noise alone). So a firefly on a smooth
   gradient, whose neighbours sit a gradient step above its median, is
   isolated, while a group that touches a bright region (the corner of a
   sharp highlight, which rises on one side only) is counted in
   ``attached_blobs_ignored`` instead. ``sigmas`` is the peak's residual over
   its local sigma.

A 5x5 median sees through blobs up to about 3x3, so the default
``max_blob_area`` of 9 matches what step 1 can isolate.

Known limits of the noise model (reviews of 65b02294, F2, d4c7ab11 and
8490b80b; attack grids of 5 seeds per cell, object 0.18 +- 0.01):

- An object pixel on the silhouette has background in its 5x5 window, so
  its local median sits off the object's level and a high noise draw there
  can be one false firefly; so can a backdrop pixel whose median the object
  pulls toward its own level. Rare on black (no false firefly in 30 noisy
  270x480 frames in the d4c7ab11 review), more frequent when the background
  is only a few sigma from the object (a 0.15 backdrop under the object: a
  false firefly on 1 to 6 of 30 96x128 frames at d4c7ab11, depending on
  coverage). In the reviewer's 8490b80b grid this is the single false
  firefly on 1 or 2 of 5 frames that some covers of most backdrops show,
  before and after the local model.
- A small noisy object on a flat or smooth backdrop at its own stop is
  judged locally once its window holds ``_MIN_LOCAL_PIXELS`` live pixels.
  Below that (a square of 7x7 or less, with its one-pixel ring) it falls
  back to the stop and, when the stop has fewer than ``_MIN_NOISE_PIXELS``
  live pixels, to the whole stop, whose MAD is about 0: its noise is then
  flagged (5x5 and 7x7 squares on a 0.18 or 0.15 backdrop: 10 of 10 frames
  wrong; 8x8 to 20x20: 0 or 1 of 10). At 8490b80b, with no local estimate,
  the reviewer measured this well past "under about 100 pixels": up to 144
  pixels on a 0.18 backdrop and 400 on a 0.15 one. Such an object on black
  is inconclusive instead.
- Two noise levels at one stop (a glossy and a diffuse surface of equal
  brightness) are judged apart only more than a window half-width (15 px)
  from where they meet; nearer, the window mixes them.
- A *curved* noise-free backdrop is not smooth where it bends sharply: near
  the apex of a radial gradient its residuals are small but above 2^-10 of
  the level, so they count as live. They pull the stop's reported sigma
  down (0.0024 for a 10% object on a 0.25 -> 0.10 radial ramp), and when
  the object is tiny and sits on the apex (2% of a 96x128 frame) they
  dominate its windows too: 32 false fireflies and 2 missed over 5 frames.
- A steep noise-free gradient at another stop than the object's (0.05 ->
  1.0 over 128 px, about 1% of the level per pixel): backdrop pixels on the
  silhouette, whose median the object pulls down by one gradient step, sit
  in a stop with no noise of its own and clear the half-float floor (2
  false fireflies per frame at 96x128, covers 0.3 to 0.8). Over 480 px
  (0.2% per pixel) the floor holds: 1 false firefly in 45 270x480 frames.
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
# Fewest lit pixels a noise estimate is taken from. Below it (but above 0) the
# answer is inconclusive rather than a count against a guessed sigma.
_MIN_NOISE_PIXELS = 100
# A lit pixel is *smooth* when every residual in its 3x3 neighbourhood is at
# most this fraction of its 5x5 median: about one half-float step, far below
# any render noise worth a sigma. A noise-free gradient is smooth everywhere.
_SMOOTH_REL = 2.0**-10
# Local noise: a (2 * _LOCAL_RADIUS + 1)^2 window around each lit pixel, over
# the live pixels of its own stop. Fewer than _MIN_LOCAL_PIXELS live pixels in
# the window and the pixel keeps its stop's sigma.
_LOCAL_RADIUS = 15
_MIN_LOCAL_PIXELS = 64
# |residual| is clipped at this many sigmas before the local mean, so a
# firefly cannot inflate the noise it is judged against.
_LOCAL_CLIP = 4.0
# Mean |x| of a zero-mean normal is sigma * sqrt(2 / pi).
_MEAN_ABS_TO_SIGMA = 1.2533141
# Isolation: a background trend counts only beyond this many sigmas (step 5).
_TREND_NOISE = 3.0


def _r(x):
    return round(float(x), 6)


def _mad_sigma(np, values):
    """1.4826 x MAD of ``values``; 0.0 for an empty array."""
    if values.size == 0:
        return 0.0
    return _MAD_TO_SIGMA * float(np.median(np.abs(values - np.median(values))))


def fireflies(
    img,
    threshold_sigma=6.0,
    *,
    max_blob_area=9,
    max_listed=50,
    mask_path=None,
    origin=None,
):
    """Firefly report for ``img`` (float HxWx3 linear RGB).

    Returns ``count`` (fireflies = small isolated blobs), ``pixel_count``
    (pixels in them), ``large_blobs_ignored``, ``attached_blobs_ignored``,
    ``sigma`` and ``threshold`` (a frame-wide reference: one MAD over the
    live lit pixels, neither flat nor smooth, or over all lit pixels when
    fewer than ``_MIN_NOISE_PIXELS`` are live, or over the black ones when
    nothing is lit, and the threshold it gives; detection uses the local
    sigmas, module docstring step 3), ``noise`` (pixel counts and sigmas for
    the black group and each lit stop, ``levels``; ``local_window``,
    ``local_min_pixels`` and ``local_pixels``, how many lit pixels were
    judged by a local sigma), ``inconclusive``, ``note``, ``worst`` (the
    single pixel with the largest residual: ``x``, ``y``, ``rgb``,
    ``luminance``, ``sigmas``; ``None`` when there are no fireflies) and
    ``fireflies``: up to ``max_listed`` entries, brightest residual first, each
    with the peak pixel ``x``/``y``, ``area`` and ``sigmas``.

    ``x``/``y`` are positions in ``img``. When ``img`` is a data window that
    does not start at the frame's corner, pass ``origin=(ox, oy)`` (the
    ``origin`` of ``synapse.cv.read_frame``'s window): every listing entry
    and ``worst`` then also carry ``frame_x``/``frame_y`` = ``x + ox`` /
    ``y + oy``, and the result carries ``origin``.

    When the noise cannot be estimated (lit pixels exist but are too few, see
    the module docstring) ``inconclusive`` is True, ``note`` says why, and
    ``count``, ``pixel_count``, ``sigma``, ``threshold`` and ``worst`` are
    ``None`` with an empty listing; no mask is written.

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
    if origin is not None:
        try:
            ox, oy = (int(v) for v in origin)
        except (TypeError, ValueError):
            raise ValueError(f"origin must be two integers (x, y), got {origin!r}") from None
    arr = _check_rgb(np, img)
    finite = np.isfinite(arr).all(axis=2)
    nonfinite = int(finite.size - int(finite.sum()))
    if nonfinite:
        arr = np.where(finite[:, :, None], arr, np.float32(0.0)).astype(np.float32)
    height, width = arr.shape[:2]

    lum = np.ascontiguousarray(_luminance(np, arr), dtype=np.float32)
    local = cv2.medianBlur(lum, 5)
    residual = lum - local
    lit = local > 0
    n_lit = int(lit.sum())
    n_black = int(lit.size - n_lit)
    base = {
        "width": int(width),
        "height": int(height),
        "nonfinite_pixels": nonfinite,
        "threshold_sigma": float(threshold_sigma),
        "max_blob_area": int(max_blob_area),
        "origin": None if origin is None else [ox, oy],
    }
    # Live pixels carry noise. Flat: the pixel and its 8 neighbours are one
    # exact value (3x3, not 5x5: see the module docstring, step 2). Smooth:
    # every residual in the 3x3 is within _SMOOTH_REL of the local median (a
    # noise-free gradient). Neither may feed a noise estimate, so a constant
    # or graded backdrop cannot zero the sigma of the object it surrounds.
    k3 = np.ones((3, 3), dtype=np.uint8)
    flat = cv2.dilate(lum, k3) == cv2.erode(lum, k3)
    smooth = cv2.dilate(np.abs(residual), k3) <= np.float32(_SMOOTH_REL) * local
    est = lit & ~flat & ~smooth
    levels, lit_px_sigma = _stop_sigmas(
        np, residual[lit], local[lit], residual[est], local[est]
    )
    if n_lit and lit_px_sigma is None:
        return _inconclusive(
            base,
            {
                "lit_pixels": n_lit,
                "lit_sigma": None,
                "black_pixels": n_black,
                "black_sigma": None,
                "min_pixels": _MIN_NOISE_PIXELS,
                "levels": levels,
            },
            f"{n_lit} lit pixels (5x5 median above 0) and no stop holds "
            f"{_MIN_NOISE_PIXELS} of them: their noise cannot be estimated",
        )
    ref = est if int(est.sum()) >= _MIN_NOISE_PIXELS else lit
    lit_sigma = max(_mad_sigma(np, residual[ref]), _SIGMA_FLOOR)
    black_sigma = max(_mad_sigma(np, residual[~lit]), _SIGMA_FLOOR)
    sigma_px = np.full(lum.shape, np.float32(black_sigma), dtype=np.float32)
    n_local = 0
    if n_lit:
        sigma_px[lit] = lit_px_sigma
        n_local = _local_sigmas(np, cv2, residual, local, lit, est, sigma_px)
        # Detection never trusts a sigma under one half-float step of the
        # level (_SMOOTH_REL): a residual that small is not noise, so
        # it is no evidence of a firefly either.
        sigma_px[lit] = np.maximum(sigma_px[lit], np.float32(_SMOOTH_REL) * local[lit])
    sigma = lit_sigma if n_lit else black_sigma
    thresh_px = np.float32(threshold_sigma) * sigma_px
    candidates = (residual > thresh_px).astype(np.uint8)

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
        if ring.any():
            # Background expected at each ring pixel q: the local median at
            # the peak p, plus the rise of the local median toward q when
            # it rises by as much on both sides of p (from the mirror pixel
            # 2p - q to p, and from p to q). A smooth gradient is then not
            # a brighter neighbour; a highlight's edge, which rises on one
            # side only, still is.
            qy, qx = np.nonzero(ring)
            qy, qx = qy + y0, qx + x0
            my = np.clip(2 * y - qy, 0, height - 1)
            mx = np.clip(2 * x - qx, 0, width - 1)
            base_p = local[y, x]
            rise = np.minimum(base_p - local[my, mx], local[qy, qx] - base_p)
            # Less _TREND_NOISE of the peak's sigmas: on a noisy surface the
            # medians differ by noise alone, which is no trend.
            rise = rise - _TREND_NOISE * sigma_px[y, x]
            expect = float(base_p) + np.maximum(rise, 0.0)
            if bool((lum[qy, qx] > expect + float(thresh_px[y, x])).any()):
                attached += 1
                continue
        mask[ys + y0, xs + x0] = 255
        found.append(
            {
                "x": x,
                "y": y,
                "area": area,
                "sigmas": _r(residual[y, x] / sigma_px[y, x]),
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
    if origin is not None:
        for f in found[:max_listed] + ([worst] if worst else []):
            f["frame_x"], f["frame_y"] = f["x"] + ox, f["y"] + oy
    listed = [{k: v for k, v in f.items() if k != "_residual"} for f in found[:max_listed]]

    result = dict(base)
    result.update(
        {
            "sigma": _r(sigma),
            "threshold": _r(threshold_sigma * sigma),
            "noise": {
                "lit_pixels": n_lit,
                "lit_sigma": _r(lit_sigma),
                "black_pixels": n_black,
                "black_sigma": _r(black_sigma),
                "min_pixels": _MIN_NOISE_PIXELS,
                "levels": levels,
                "local_window": 2 * _LOCAL_RADIUS + 1,
                "local_min_pixels": _MIN_LOCAL_PIXELS,
                "local_pixels": n_local,
            },
            "inconclusive": False,
            "note": None,
            "count": len(found),
            "pixel_count": int((mask > 0).sum()),
            "large_blobs_ignored": large,
            "attached_blobs_ignored": attached,
            "worst": worst,
            "fireflies": listed,
            "fireflies_truncated": len(found) > len(listed),
            "mask_path": None,
        }
    )
    if mask_path is not None:
        path = os.path.abspath(os.fspath(mask_path))
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if not cv2.imwrite(path, mask):
            raise OSError(f"cv2.imwrite could not write the firefly mask to {path}")
        result["mask_path"] = path
    return result


def _stop_sigmas(np, res, loc, eres, eloc):
    """Per-stop MAD sigmas for the lit pixels (``res`` and ``loc`` 1-D, loc > 0).

    ``eres``/``eloc`` are the same for the live lit pixels (neither flat nor
    smooth, module docstring step 2). A stop with
    ``_MIN_NOISE_PIXELS`` pixels takes its MAD from its live ones when
    it has that many of them, else from all of them.

    Returns ``(levels, per_pixel)``: ``levels`` is a list of dicts (``stop``,
    ``pixels``, ``sigma``, ``borrowed_from``: None when the stop has
    ``_MIN_NOISE_PIXELS`` itself, else the stop it took its sigma from) and
    ``per_pixel`` a float32 sigma for every input pixel, floored. When no stop
    has enough pixels ``per_pixel`` is None. Empty input gives ``([], empty)``.
    """
    if res.size == 0:
        return [], np.zeros(0, dtype=np.float32)
    stops = np.floor(np.log2(loc.astype(np.float64))).astype(np.int64)
    uniq, inverse, counts = np.unique(stops, return_inverse=True, return_counts=True)
    order = np.argsort(inverse, kind="stable")
    groups = np.split(res[order], np.cumsum(counts)[:-1])
    estops = np.floor(np.log2(eloc.astype(np.float64))).astype(np.int64)
    own = {}
    for i, (stop, n) in enumerate(zip(uniq.tolist(), counts.tolist())):
        if n >= _MIN_NOISE_PIXELS:
            g = eres[estops == stop]
            if g.size < _MIN_NOISE_PIXELS:
                g = groups[i]  # too few live pixels: the whole stop
            own[stop] = max(_mad_sigma(np, g), _SIGMA_FLOOR)
    levels = []
    sig = np.zeros(len(uniq), dtype=np.float32)
    for i, (stop, n) in enumerate(zip(uniq.tolist(), counts.tolist())):
        if stop in own:
            src = stop
        elif own:
            # Nearest estimated stop; on a tie the brighter one (larger key).
            src = min(own, key=lambda s: (abs(s - stop), -s))
        else:
            src = None
        sig[i] = own[src] if src is not None else 0.0
        levels.append(
            {
                "stop": int(stop),
                "pixels": int(n),
                "sigma": _r(own[src]) if src is not None else None,
                "borrowed_from": None if src == stop else (None if src is None else int(src)),
            }
        )
    if not own:
        return levels, None
    return levels, sig[inverse.reshape(-1)]


def _local_sigmas(np, cv2, residual, local, lit, live, sigma_px):
    """Overwrite ``sigma_px`` on lit pixels with their local noise; return how many.

    For each stop, the live pixels of that stop (``live``: lit, not flat, not
    smooth) give a clipped mean of ``|residual|`` over the window around every
    pixel of the stop; times sqrt(pi / 2) it is a sigma. Two passes: the first
    clips at ``_LOCAL_CLIP`` x the stop's sigma (already in ``sigma_px``), the
    second at ``_LOCAL_CLIP`` x the first pass's local sigma. A pixel whose
    window holds fewer than ``_MIN_LOCAL_PIXELS`` live pixels of its stop keeps
    its stop's sigma.
    """
    stop_map = np.full(local.shape, np.iinfo(np.int64).min, dtype=np.int64)
    stop_map[lit] = np.floor(np.log2(local[lit].astype(np.float64))).astype(np.int64)
    abs_res = np.abs(residual).astype(np.float64)
    r = _LOCAL_RADIUS
    k = (2 * r + 1, 2 * r + 1)
    height, width = local.shape
    total = 0
    for stop in np.unique(stop_map[live]).tolist():
        members = stop_map == stop
        ys, xs = np.nonzero(members)
        y0, y1 = max(int(ys.min()) - r, 0), min(int(ys.max()) + r + 1, height)
        x0, x1 = max(int(xs.min()) - r, 0), min(int(xs.max()) + r + 1, width)
        box = (slice(y0, y1), slice(x0, x1))
        mem = members[box]
        use = (live[box] & mem).astype(np.float64)
        count = cv2.boxFilter(use, -1, k, normalize=False, borderType=cv2.BORDER_CONSTANT)
        ok = mem & (count >= _MIN_LOCAL_PIXELS - 0.5)
        if not ok.any():
            continue
        cap = sigma_px[box].astype(np.float64)
        for _ in range(2):
            clipped = np.minimum(abs_res[box], _LOCAL_CLIP * cap) * use
            sums = cv2.boxFilter(clipped, -1, k, normalize=False, borderType=cv2.BORDER_CONSTANT)
            est = _MEAN_ABS_TO_SIGMA * sums / np.maximum(count, 1.0)
            cap = np.where(ok, est, cap)
        sub = sigma_px[box]
        sub[ok] = np.maximum(cap[ok], _SIGMA_FLOOR).astype(np.float32)
        total += int(ok.sum())
    return total


def _inconclusive(base, noise, note):
    """The honest result when the noise cannot be estimated: no count at all."""
    result = dict(base)
    result.update(
        {
            "sigma": None,
            "threshold": None,
            "noise": noise,
            "inconclusive": True,
            "note": note,
            "count": None,
            "pixel_count": None,
            "large_blobs_ignored": None,
            "attached_blobs_ignored": None,
            "worst": None,
            "fireflies": [],
            "fireflies_truncated": False,
            "mask_path": None,
        }
    )
    return result
