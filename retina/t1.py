"""T1 — deterministic pixels. "Did the *right thing* change?"

The second rung of the tier ladder (blueprint §4): milliseconds, CPU, headless,
zero tokens. It runs AFTER T0's file-truth pass (routing rule §4: cheap-first,
escalate on inconclusive, never skip a tier downward) and publishes a tier-1
perception event that is a **schema-sibling of T0's** (same envelope, same check
shape, same roll-up, same honesty rule, same JSONL persistence — all from
``retina.events``).

The metric kit (blueprint §4 T1 row, verbatim enumeration):

1. **NaN/inf census** — no non-finite pixels.
2. **black / blown-frame detection** — the frame isn't (near-)all-black or -white.
3. **clip %** — fraction of clipped pixels within tolerance.
4. **firefly outlier count** — sparse ultra-bright outliers (denoiser/sampling).
5. **SSIM vs baseline** — structural similarity to the last-accepted frame.
6. **change masks** — difference → threshold → morphological cleanup.
7. **containment** — changed pixels ⊆ the target prim's ID matte within ε, and an
   SSIM floor *outside* the matte. The scoped-delta proof (§5) lives here.

Scoped-delta primitives (§5, public-safe altitude — M2 SHIPS them, M3 drives them
end-to-end on the Dark_Glass scenario): ``change_mask`` → ``id_matte`` →
``containment`` → ``ssim_outside``, plus ``project_bbox`` (the worker projects prim
bboxes to screen space itself from the manifest camera 4×4 — pure numpy, zero
``hou``; CRUCIBLE feeds synthetic manifests, so the whole organ is testable
without Houdini).

**Thresholds, never equality.** GPU renders are not bit-stable (§7). Every
tolerance is a parameter sourced from ``qc_profiles.toml`` (per renderer × denoiser
× sample tier) — none is hardcoded in the metric logic. **Commandment 7 extends to
thresholds: a threshold is a test assertion; it is NEVER loosened to green a
verdict — a red is fixed forward in the scene or the contract.** Nothing in this
module relaxes a threshold at runtime.

**Honesty (§7).** A metric that cannot run — no baseline yet, an absent ID AOV, an
unreadable plane — returns ``pass=None`` (inconclusive), NEVER a silent pass, exactly
as T0 does.

cv2/numpy imports are guarded (CLAUDE.md §12 idiom) so the pure event-assembly
below imports cleanly in stock CI; the pixel metrics raise :class:`T1Unavailable`
if called without cv2. OpenCV is restricted to base-module classical ops
(``GaussianBlur``, ``absdiff``, ``threshold``, ``morphologyEx``, ``dilate``,
``getStructuringElement``) so the blueprint's ``4.13.x`` API-stable fallback holds
for every op named here; the 5.0 DNN engine is not used (that oracle role is M4).
Zero ``hou``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .events import emit_verdict, make_check, make_event

try:
    import numpy as np  # type: ignore[import-untyped]

    _NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - numpy-less CI leg
    np = None  # type: ignore[assignment]
    _NUMPY_AVAILABLE = False

try:
    import cv2  # type: ignore[import-untyped]

    _CV2_AVAILABLE = True
except ImportError:  # pragma: no cover - stock-CI leg (cv2 lives in the venv)
    cv2 = None  # type: ignore[assignment]
    _CV2_AVAILABLE = False

TIER = 1

# re-export so callers can persist without importing events directly
__all__ = [
    "TIER",
    "T1Unavailable",
    "pixels_available",
    "nan_inf_census",
    "black_blown_frame",
    "clip_percent",
    "firefly_count",
    "ssim",
    "change_mask",
    "id_matte",
    "containment",
    "ssim_outside",
    "project_bbox",
    "assess_frame",
    "assess_scoped_delta",
    "build_t1_event",
    "emit_verdict",
]


class T1Unavailable(RuntimeError):
    """A pixel metric was called without cv2/numpy — the honest signal for the
    no-venv leg, never a fabricated verdict."""


def pixels_available() -> bool:
    return _CV2_AVAILABLE and _NUMPY_AVAILABLE


def _require() -> None:
    if not pixels_available():
        raise T1Unavailable(
            "cv2/numpy not installed — T1 pixel metrics run in the RETINA worker "
            "venv (retina/requirements.txt). Pure event assembly (build_t1_event) "
            "does not need them."
        )


def _luma(plane: "np.ndarray") -> "np.ndarray":
    """Reduce an (H,W[,C]) plane to a single-channel float32 array for the
    structural metrics. Mean across channels — deterministic, colour-agnostic on
    the already-linear beauty plane."""
    a = np.asarray(plane, dtype=np.float32)
    if a.ndim == 3:
        a = a.mean(axis=2)
    return a


# ---------------------------------------------------------------------------
# The seven-metric kit — each returns one check dict (make_check), tri-state.
# ---------------------------------------------------------------------------

def nan_inf_census(plane: "np.ndarray") -> Dict[str, Any]:
    """(1) No non-finite pixels. A NaN/inf is a hard render bug — always False on
    presence, never inconclusive."""
    _require()
    a = np.asarray(plane, dtype=np.float32)
    nan_count = int(np.isnan(a).sum())
    inf_count = int(np.isinf(a).sum())
    clean = nan_count == 0 and inf_count == 0
    return make_check(
        "nan_inf_census",
        clean,
        "no non-finite pixels" if clean else f"{nan_count} NaN, {inf_count} inf",
        nan_count=nan_count,
        inf_count=inf_count,
    )


def black_blown_frame(
    plane: "np.ndarray",
    *,
    black_threshold: float,
    blown_threshold: float,
    ratio: float,
) -> Dict[str, Any]:
    """(2) The frame isn't (near-)all-black or (near-)all-blown. ``ratio`` is the
    fraction-of-pixels tolerance from the profile."""
    _require()
    a = _luma(plane)
    total = a.size or 1
    near_black = float((a <= black_threshold).sum()) / total
    blown = float((a >= blown_threshold).sum()) / total
    ok = near_black < ratio and blown < ratio
    return make_check(
        "black_blown",
        ok,
        (
            "frame exposure within range"
            if ok
            else f"near_black={near_black:.3f} blown={blown:.3f} exceed ratio={ratio}"
        ),
        near_black_ratio=round(near_black, 6),
        blown_ratio=round(blown, 6),
        ratio=ratio,
    )


def clip_percent(
    plane: "np.ndarray", *, low: float, high: float, clip_ratio: float
) -> Dict[str, Any]:
    """(3) Fraction of clipped (at/below ``low`` or at/above ``high``) pixels within
    ``clip_ratio``."""
    _require()
    a = _luma(plane)
    total = a.size or 1
    clipped = float(((a <= low) | (a >= high)).sum()) / total
    ok = clipped <= clip_ratio
    return make_check(
        "clip_percent",
        ok,
        f"clip={clipped:.4f} {'<=' if ok else '>'} ratio={clip_ratio}",
        clip_fraction=round(clipped, 6),
        clip_ratio=clip_ratio,
    )


def firefly_count(plane: "np.ndarray", *, std_devs: float) -> Dict[str, Any]:
    """(4) **Census** of sparse ultra-bright outliers (> mean + ``std_devs``·σ). The
    *count* is the payload — evidence a higher tier or a ratified firefly policy
    weighs — so this census passes structurally and never invents a hardcoded
    pass/fail fraction (all tolerances live in ``qc_profiles.toml``; ``std_devs`` is
    the one this reads). A truly degenerate frame is caught by
    ``black_blown``/``clip``/``nan_inf``, not here."""
    _require()
    a = _luma(plane)
    std = float(a.std())
    if std == 0.0:
        return make_check(
            "firefly_count", True, "flat frame — no variance for outlier test",
            firefly_count=0, std_devs=std_devs,
        )
    threshold = float(a.mean()) + std_devs * std
    count = int((a > threshold).sum())
    return make_check(
        "firefly_count",
        True,
        f"{count} outlier px (> mean+{std_devs}σ)",
        firefly_count=count,
        firefly_fraction=round(count / (a.size or 1), 6),
        std_devs=std_devs,
    )


def ssim(
    a: "np.ndarray",
    b: "np.ndarray",
    *,
    data_range: float,
    win: int = 11,
    sigma: float = 1.5,
    return_map: bool = False,
):
    """(5) Classical Wang-et-al. SSIM via Gaussian windows (``cv2.GaussianBlur`` —
    base-module, stable across the 4.13.x fallback and 5.0). Returns the mean SSIM,
    or ``(mean, ssim_map)`` when ``return_map`` (used by ``ssim_outside``)."""
    _require()
    x = _luma(a).astype(np.float64)
    y = _luma(b).astype(np.float64)
    C1 = (0.01 * data_range) ** 2
    C2 = (0.03 * data_range) ** 2
    k = (win, win)
    mu_x = cv2.GaussianBlur(x, k, sigma)
    mu_y = cv2.GaussianBlur(y, k, sigma)
    mu_x2, mu_y2, mu_xy = mu_x * mu_x, mu_y * mu_y, mu_x * mu_y
    sigma_x2 = cv2.GaussianBlur(x * x, k, sigma) - mu_x2
    sigma_y2 = cv2.GaussianBlur(y * y, k, sigma) - mu_y2
    sigma_xy = cv2.GaussianBlur(x * y, k, sigma) - mu_xy
    ssim_map = ((2 * mu_xy + C1) * (2 * sigma_xy + C2)) / (
        (mu_x2 + mu_y2 + C1) * (sigma_x2 + sigma_y2 + C2)
    )
    mean = float(ssim_map.mean())
    return (mean, ssim_map) if return_map else mean


# ---------------------------------------------------------------------------
# Scoped-delta primitives (§5) — M2 ships, M3 drives.
# ---------------------------------------------------------------------------

def change_mask(
    before: "np.ndarray",
    after: "np.ndarray",
    *,
    diff_threshold: float,
    morph_radius: int = 1,
) -> "np.ndarray":
    """(6) before/after **change mask**: difference → threshold → morphological
    cleanup (open removes speckle, close fills pinholes). Returns a uint8 {0,1}
    mask, top-down."""
    _require()
    x = _luma(before).astype(np.float32)
    y = _luma(after).astype(np.float32)
    diff = cv2.absdiff(x, y)
    mask = (diff > diff_threshold).astype(np.uint8)
    if morph_radius > 0:
        kern = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (2 * morph_radius + 1, 2 * morph_radius + 1)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kern)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kern)
    return mask


def id_matte(
    id_plane: "np.ndarray", target_id: int, *, dilation: int = 1
) -> "np.ndarray":
    """The target prim's **ID matte** from the integer object-ID AOV: pixels whose
    (rounded) ID equals ``target_id``, with a small dilation for AA edges (§5 step
    3). Returns a uint8 {0,1} matte, top-down."""
    _require()
    ids = np.rint(np.asarray(id_plane, dtype=np.float64)).astype(np.int64)
    matte = (ids == int(target_id)).astype(np.uint8)
    if dilation > 0:
        kern = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (2 * dilation + 1, 2 * dilation + 1)
        )
        matte = cv2.dilate(matte, kern)
    return matte


def containment(
    mask: "np.ndarray", matte: "np.ndarray", *, leak_eps: int
) -> Dict[str, Any]:
    """(7) **containment**: changed pixels ⊆ target matte within a leak-pixel ε.
    ``leak_px`` = changed pixels landing OUTSIDE the matte; pass when ``leak_px <=
    leak_eps``. Numeric evidence rides the check (blueprint §3 illustration:
    ``leak_px``, ``eps``)."""
    _require()
    m = np.asarray(mask) > 0
    t = np.asarray(matte) > 0
    if m.shape != t.shape:
        return make_check(
            "delta_containment", None,
            f"shape mismatch mask{m.shape} vs matte{t.shape} — cannot compare",
        )
    leaked = np.logical_and(m, np.logical_not(t))
    leak_px = int(leaked.sum())
    return make_check(
        "delta_containment",
        leak_px <= leak_eps,
        f"leak_px={leak_px} {'<=' if leak_px <= leak_eps else '>'} eps={leak_eps}",
        leak_px=leak_px,
        eps=leak_eps,
        changed_px=int(m.sum()),
    )


def ssim_outside(
    before: "np.ndarray",
    after: "np.ndarray",
    matte: "np.ndarray",
    *,
    ssim_min: float,
    data_range: float,
    win: int = 11,
) -> Dict[str, Any]:
    """SSIM floor **outside** the target matte (§5): everything the change was NOT
    supposed to touch must stay structurally identical. Pass when ``val >=
    ssim_min``.

    The SSIM map is windowed (``win``×``win`` Gaussian), so a pixel whose window
    overlaps the changed matte is spatially coupled to the change — it is neither
    cleanly inside nor outside, and counting it would penalise the outside score
    for the window's coupling rather than for a real leak. So the matte is dilated
    by the window radius to form an **exclusion band**, and only genuinely
    unaffected pixels are scored. This is NOT a threshold relaxation (Commandment
    7): the floor is unchanged; the *region measured* is corrected to "truly
    outside the change's footprint". A real leak still degrades pixels beyond the
    band and fails the floor (and containment catches it exactly, in parallel).
    """
    _require()
    _, smap = ssim(before, after, data_range=data_range, win=win, return_map=True)
    t = (np.asarray(matte) > 0).astype(np.uint8)
    radius = max(1, win // 2)
    kern = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1)
    )
    exclusion = cv2.dilate(t, kern) > 0
    outside = smap[np.logical_not(exclusion)]
    if outside.size == 0:
        return make_check(
            "ssim_outside", None,
            "matte (+ window band) covers the whole frame — no outside region to score",
            min=ssim_min,
        )
    val = float(outside.mean())
    return make_check(
        "ssim_outside",
        val >= ssim_min,
        f"ssim_outside={val:.4f} {'>=' if val >= ssim_min else '<'} min={ssim_min}",
        val=round(val, 6),
        min=ssim_min,
    )


def project_bbox(
    world_to_ndc: Sequence[float],
    world_bbox: Sequence[float],
    width: int,
    height: int,
) -> Optional[List[int]]:
    """Project a world-space AABB to a screen-space pixel bbox using the manifest's
    ``world_to_ndc`` 4×4 (row-major, 16 floats — husk stamps it in
    ``husk:render_stats``). Pure numpy; the worker does this itself so it stays
    ``hou``-free (§3). Returns ``[x0, y0, x1, y1]`` in **top-down** pixel coords
    (y=0 at the top, matching OIIO ingest), clamped to the frame, or ``None`` if
    every corner falls behind the camera.

    ``world_bbox`` = ``[xmin, ymin, zmin, xmax, ymax, zmax]``.
    """
    _require()
    M = np.asarray(world_to_ndc, dtype=np.float64).reshape(4, 4)
    xmin, ymin, zmin, xmax, ymax, zmax = (float(v) for v in world_bbox)
    corners = np.array(
        [
            [x, y, z, 1.0]
            for x in (xmin, xmax)
            for y in (ymin, ymax)
            for z in (zmin, zmax)
        ],
        dtype=np.float64,
    )
    clip = corners @ M  # row-vector convention: v' = v · M
    w = clip[:, 3]
    valid = np.abs(w) > 1e-9
    if not valid.any():
        return None
    ndc = clip[valid, :3] / w[valid, None]
    # NDC [-1,1] → pixel; y flipped so row 0 is the TOP (top-down convention).
    px = (ndc[:, 0] * 0.5 + 0.5) * width
    py = (1.0 - (ndc[:, 1] * 0.5 + 0.5)) * height
    x0 = int(np.floor(np.clip(px.min(), 0, width - 1)))
    x1 = int(np.ceil(np.clip(px.max(), 0, width - 1)))
    y0 = int(np.floor(np.clip(py.min(), 0, height - 1)))
    y1 = int(np.ceil(np.clip(py.max(), 0, height - 1)))
    return [x0, y0, x1, y1]


# ---------------------------------------------------------------------------
# Verdict assembly — pure (no cv2), so it imports + tests in stock CI.
# ---------------------------------------------------------------------------

def build_t1_event(
    *,
    claim: str,
    checks: List[Dict[str, Any]],
    proof: Optional[str],
    now: str,
) -> Dict[str, Any]:
    """Assemble a tier-1 perception event from pre-computed checks — a
    schema-sibling of T0's (``retina.events.make_event(tier=1, ...)``). Pure: no
    cv2, no clock read, so the same inputs yield a byte-identical event."""
    return make_event(tier=TIER, claim=claim, checks=checks, proof=proof, now=now)


# ---------------------------------------------------------------------------
# Orchestrators — the pixel path M3 drives end-to-end.
# ---------------------------------------------------------------------------

def assess_frame(
    plane: "np.ndarray",
    profile: Dict[str, Any],
    *,
    claim: str,
    now: str,
    baseline: Optional["np.ndarray"] = None,
    proof: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the single-frame health metrics (1–5) and roll them into a tier-1 event.
    SSIM (5) needs a baseline (the last-accepted frame from the disk-outbox
    baseline store); absent → inconclusive, never a silent pass (§7)."""
    _require()
    checks: List[Dict[str, Any]] = [
        nan_inf_census(plane),
        black_blown_frame(
            plane,
            black_threshold=profile["black_threshold"],
            blown_threshold=profile["blown_threshold"],
            ratio=profile["black_ratio"],
        ),
        clip_percent(
            plane,
            low=profile["black_threshold"],
            high=profile["blown_threshold"],
            clip_ratio=profile["clip_ratio"],
        ),
        firefly_count(plane, std_devs=profile["firefly_std_devs"]),
    ]
    if baseline is None:
        checks.append(
            make_check("ssim", None, "no baseline yet — SSIM cannot run",
                       min=profile["ssim_min"])
        )
    else:
        val = ssim(baseline, plane, data_range=profile["ssim_data_range"])
        checks.append(
            make_check(
                "ssim", val >= profile["ssim_min"],
                f"ssim={val:.4f} {'>=' if val >= profile['ssim_min'] else '<'} "
                f"min={profile['ssim_min']}",
                val=round(val, 6), min=profile["ssim_min"],
            )
        )
    return build_t1_event(claim=claim, checks=checks, proof=proof, now=now)


def assess_scoped_delta(
    before: Optional["np.ndarray"],
    after: "np.ndarray",
    id_plane: Optional["np.ndarray"],
    target_id: Optional[int],
    profile: Dict[str, Any],
    *,
    claim: str,
    now: str,
    proof: Optional[str] = None,
) -> Dict[str, Any]:
    """The scoped-delta proof (§5) assembled into a tier-1 event: change mask ×
    ID matte containment + an SSIM floor outside the matte. This is the primitive
    M3 drives on the Dark_Glass scenario; here it is fully self-contained and
    Houdini-free.

    Honesty (§7): a missing baseline (``before``), a missing ID AOV (``id_plane`` /
    ``target_id``), or a shape mismatch yields ``inconclusive`` checks — never a
    silent pass.
    """
    _require()
    checks: List[Dict[str, Any]] = [nan_inf_census(after)]

    if before is None:
        checks.append(
            make_check("delta_containment", None, "no baseline (before) — change "
                       "mask cannot be computed", eps=profile["leak_eps"])
        )
        checks.append(
            make_check("ssim_outside", None, "no baseline (before) — SSIM cannot run",
                       min=profile["ssim_min"])
        )
        return build_t1_event(claim=claim, checks=checks, proof=proof, now=now)

    if id_plane is None or target_id is None:
        checks.append(
            make_check("delta_containment", None, "no ID AOV / target id — "
                       "containment cannot run (declare karmarendersettings.primid)",
                       eps=profile["leak_eps"])
        )
        # SSIM-outside also needs a matte; without one, report inconclusive.
        checks.append(
            make_check("ssim_outside", None, "no ID matte — outside-region SSIM "
                       "cannot be isolated", min=profile["ssim_min"])
        )
        return build_t1_event(claim=claim, checks=checks, proof=proof, now=now)

    mask = change_mask(
        before, after,
        diff_threshold=profile["diff_threshold"],
        morph_radius=profile["morph_radius"],
    )
    matte = id_matte(id_plane, target_id, dilation=profile["matte_dilation"])
    checks.append(containment(mask, matte, leak_eps=profile["leak_eps"]))
    checks.append(
        ssim_outside(
            before, after, matte,
            ssim_min=profile["ssim_min"],
            data_range=profile["ssim_data_range"],
        )
    )
    return build_t1_event(claim=claim, checks=checks, proof=proof, now=now)
