"""Cook-verify measurement contracts — W5-MEASURES substrate (Blueprint M3).

FP2, the wave's one law: *never assert what you haven't measured.* Every contract
here has an explicit UNKNOWN condition — when the observation needed to judge an
output is absent, the verdict is UNKNOWN with the exact missing input, never a
fabricated pass. A measured output earns MEASURED (or FAIL/EXPLODING) backed by
the signals that decided it.

Five output kinds, each a pure function ``obs (dict) -> MeasureResult``:

  image     res, channels, per-channel stats, hash      UNKNOWN if not rendered
  sim       per-frame NaN / max_velocity / KE / strain  UNKNOWN if no frames
  geometry  point/prim counts, bbox, NaN, weight norm   UNKNOWN if not cooked
  channels  sample count, value range, variance         UNKNOWN if no samples
  graph     compiles, errors empty, invokes             UNKNOWN if not evaluated

The tier the exposure system shows a tool at is DERIVED from a measurement via
``exposure_rung`` — this EXTENDS ``synapse.science.exposure`` (it emits one of that
module's existing rungs); it does not fork or edit it, so the exposure contract
tests stay byte-for-byte green.

Pure Python, zero `hou`. The observations are produced by a live cook (hython;
see rulebook/goldens/README.md) — headless, that cook is UNKNOWN, and these
contracts render it UNKNOWN rather than green.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from .explosion import detect_explosion, EXPLODING as _EXPLODING, UNKNOWN as _EXPL_UNKNOWN

# Verdicts
MEASURED = "MEASURED"
UNKNOWN = "UNKNOWN"
FAIL = "FAIL"
EXPLODING = "EXPLODING"   # sim-specific FAIL flavour, carried through from explosion.py

OUTPUT_KINDS = ("image", "sim", "geometry", "channels", "graph")

# The exact UNKNOWN condition for each kind — the observation whose absence means
# "not measured". Pinned by the acceptance test so no kind can silently drop its
# honesty guard.
UNKNOWN_CONDITIONS = {
    "image": "no rendered pixels (resolution or stats absent) -> not rendered",
    "sim": "no frames measured -> sim never cooked",
    "geometry": "point/prim counts absent -> geometry not cooked",
    "channels": "no samples -> channel never evaluated",
    "graph": "compiles flag absent -> graph never evaluated",
}


@dataclass(frozen=True)
class MeasureResult:
    """A cook-verify judgement on one produced output.

    verdict is MEASURED | UNKNOWN | FAIL | EXPLODING. ``signals`` carries the
    measured evidence (empty on UNKNOWN). ``unknown_reason`` (UNKNOWN) or
    ``detail`` (FAIL/EXPLODING) anchors the verdict — no bare verdicts.
    """

    kind: str
    verdict: str
    signals: dict = field(default_factory=dict)
    unknown_reason: str | None = None
    detail: str | None = None

    @property
    def measured(self) -> bool:
        return self.verdict != UNKNOWN


def _has(obs: dict, *keys) -> bool:
    return all(obs.get(k) is not None for k in keys)


def _is_num(x) -> bool:
    """A real numeric measurement (int/float, excluding bool)."""
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _bad(x) -> bool:
    return isinstance(x, float) and (math.isnan(x) or math.isinf(x))


def _any_bad(values) -> bool:
    return any(_bad(v) for v in values)


def _flatten_stats(stats):
    """Leaf values of a stats dict/list, up to two levels (per-channel dicts)."""
    if isinstance(stats, dict):
        src = stats.values()
    elif isinstance(stats, (list, tuple)):
        src = stats
    else:
        return [stats]
    out = []
    for s in src:
        if isinstance(s, dict):
            out.extend(s.values())
        else:
            out.append(s)
    return out


# ── image ────────────────────────────────────────────────────────────────────
def measure_image(obs: dict) -> MeasureResult:
    if not _has(obs, "resolution", "stats"):
        return MeasureResult("image", UNKNOWN, unknown_reason=UNKNOWN_CONDITIONS["image"])
    res = obs["resolution"]
    stats = obs["stats"]
    channels = obs.get("channels")
    # resolution is a render SETTING, not proof of pixels — validate its shape,
    # but the actual pixel MEASUREMENT is stats (checked next).
    if not (isinstance(res, (list, tuple)) and len(res) == 2
            and _is_num(res[0]) and _is_num(res[1]) and res[0] > 0 and res[1] > 0):
        return MeasureResult("image", FAIL, signals={"resolution": res},
                             detail=f"non-positive / malformed resolution {res}")
    flat = _flatten_stats(stats)
    numeric = [v for v in flat if _is_num(v)]
    # FP2: present-but-empty stats == no pixel measured. resolution alone (a
    # setting known before any render) must not green a never-rendered image.
    if not numeric:
        return MeasureResult("image", UNKNOWN,
                             unknown_reason="image stats present but empty: no pixel statistics measured")
    if _any_bad(numeric) or len(numeric) != len(flat):
        return MeasureResult("image", FAIL, signals={"stats": stats},
                             detail="NaN/inf or non-numeric value in pixel stats")
    return MeasureResult("image", MEASURED, signals={
        "resolution": tuple(res), "channels": channels, "stats": stats,
        "hash": obs.get("hash"),
    })


# ── sim ──────────────────────────────────────────────────────────────────────
def measure_sim(obs: dict) -> MeasureResult:
    frames = obs.get("frames")
    if not frames:
        return MeasureResult("sim", UNKNOWN, unknown_reason=UNKNOWN_CONDITIONS["sim"])
    verdict = detect_explosion(
        frames,
        ke_ratio_threshold=obs.get("ke_ratio_threshold", 2.0),
        ke_window=obs.get("ke_window", 5),
        strain_bound=obs.get("strain_bound", 10.0),
    )
    if verdict.verdict == _EXPL_UNKNOWN:
        return MeasureResult("sim", UNKNOWN, unknown_reason=verdict.unknown_reason)
    if verdict.verdict == _EXPLODING:
        return MeasureResult("sim", EXPLODING,
                             signals={"signal": verdict.signal, "offending_frame": verdict.offending_frame},
                             detail=verdict.detail)
    return MeasureResult("sim", MEASURED, signals={"frames": len(frames), "verdict": "stable"})


# ── geometry ───────────────────────────────────────────────────────────────--
def measure_geometry(obs: dict) -> MeasureResult:
    if not _has(obs, "point_count", "prim_count"):
        return MeasureResult("geometry", UNKNOWN, unknown_reason=UNKNOWN_CONDITIONS["geometry"])
    bbox = obs.get("bbox")
    if bbox is not None and _any_bad(list(bbox)):
        return MeasureResult("geometry", FAIL, signals={"bbox": bbox}, detail="NaN/inf in bbox")
    if obs.get("has_nan_positions"):
        return MeasureResult("geometry", FAIL, detail="NaN in point positions")
    # weight normalization: if a weight_sum is claimed, it must be ~1.0
    wsum = obs.get("weight_sum")
    if wsum is not None and not math.isclose(wsum, 1.0, abs_tol=obs.get("weight_tol", 1e-4)):
        return MeasureResult("geometry", FAIL, signals={"weight_sum": wsum},
                             detail=f"weights not normalized (sum={wsum})")
    return MeasureResult("geometry", MEASURED, signals={
        "point_count": obs["point_count"], "prim_count": obs["prim_count"],
        "bbox": bbox, "weight_sum": wsum,
    })


# ── channels ───────────────────────────────────────────────────────────────--
def measure_channels(obs: dict) -> MeasureResult:
    samples = obs.get("samples")
    n = samples if isinstance(samples, int) else (len(samples) if samples is not None else None)
    if not n:
        return MeasureResult("channels", UNKNOWN, unknown_reason=UNKNOWN_CONDITIONS["channels"])
    rng = obs.get("range")
    variance = obs.get("variance")
    if rng is not None and (_any_bad(list(rng)) or rng[0] > rng[1]):
        return MeasureResult("channels", FAIL, signals={"range": rng}, detail=f"invalid range {rng}")
    if _bad(variance):
        return MeasureResult("channels", FAIL, detail="NaN/inf variance")
    return MeasureResult("channels", MEASURED, signals={"samples": n, "range": rng, "variance": variance})


# ── graph ────────────────────────────────────────────────────────────────────
def measure_graph(obs: dict) -> MeasureResult:
    if obs.get("compiles") is None:
        return MeasureResult("graph", UNKNOWN, unknown_reason=UNKNOWN_CONDITIONS["graph"])
    if not obs["compiles"]:
        return MeasureResult("graph", FAIL, signals={"errors": obs.get("errors") or []},
                             detail="graph does not compile")
    errors = obs.get("errors")
    invokes = obs.get("invokes")
    # measured failures first (a present, bad signal)
    if errors:
        return MeasureResult("graph", FAIL, signals={"errors": errors}, detail=f"{len(errors)} error(s) present")
    if invokes is False:
        return MeasureResult("graph", FAIL, detail="graph compiles but does not invoke")
    # FP2: the graph contract is three legs (compiles, errors empty, invokes).
    # If errors/invokes were never captured, only compilation was measured —
    # UNKNOWN (partial), never a green verdict that fabricates invokes=True.
    if errors is None or invokes is None:
        return MeasureResult("graph", UNKNOWN,
                             unknown_reason="graph partially measured: only compiles captured (errors/invokes absent)")
    return MeasureResult("graph", MEASURED, signals={"compiles": True, "errors": errors, "invokes": invokes})


CONTRACTS: dict[str, Callable[[dict], MeasureResult]] = {
    "image": measure_image,
    "sim": measure_sim,
    "geometry": measure_geometry,
    "channels": measure_channels,
    "graph": measure_graph,
}


def measure(kind: str, obs: dict) -> MeasureResult:
    """Dispatch to the contract for ``kind``. Unknown kinds render UNKNOWN, never
    a fabricated pass — an output kind we have no contract for is unmeasured."""
    fn = CONTRACTS.get(kind)
    if fn is None:
        return MeasureResult(kind, UNKNOWN, unknown_reason=f"no measurement contract for output kind '{kind}'")
    return fn(obs)


# ── tier ladder: DERIVE an exposure rung from a measurement ───────────────────
# EXTENDS synapse.science.exposure (emits one of ITS existing rungs); does not
# edit it. A tool is foregrounded only when its output was actually verified;
# UNKNOWN keeps it surfaced-unverified; a measured FAIL/EXPLODING is surfaced
# with a caveat — never silently hidden, never falsely foregrounded.
_RUNG_FOR_VERDICT = {
    MEASURED: "V1_output",     # output verified            -> foreground
    FAIL: "V1-degraded",       # cooked, output bad         -> surfaced_caveat
    EXPLODING: "V1-degraded",  # cooked, sim exploded       -> surfaced_caveat
    UNKNOWN: "V0_membership",  # exists but not cook-verified-> surfaced_unverified
}


def exposure_rung(result: MeasureResult) -> str:
    """Map a MeasureResult onto an existing ``synapse.science.exposure`` rung."""
    return _RUNG_FOR_VERDICT[result.verdict]


def exposure_tier(result: MeasureResult) -> str:
    """Project a measurement all the way to the panel tier via the existing
    exposure system. Guarded import: if exposure is unavailable the rung is still
    the honest answer, so we surface that rather than crash."""
    rung = exposure_rung(result)
    try:
        from synapse.science.exposure import highest_tier
    except Exception:
        return rung  # exposure module absent — the rung is the honest fallback
    return highest_tier([rung])
