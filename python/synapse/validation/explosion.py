"""Explosion signature detector — W5-MEASURES cook-verify substrate (Blueprint M3).

FP2: never assert what you haven't measured. A sim that was not measured returns
UNKNOWN — never a fabricated STABLE. A sim that WAS measured returns a verdict
backed by the offending frame and the exact signal that tripped it. No vibes.

Three explosion signatures, checked in order of severity:
  1. NaN / inf in any measured signal        -> signal="nan"
  2. max_strain over a hard bound            -> signal="strain"
  3. monotonic kinetic-energy growth whose    -> signal="ke_growth"
     ratio exceeds a threshold across N
     consecutive frames

Pure Python, zero `hou`. The live cook that PRODUCES the per-frame signals is a
Houdini/hython job (see rulebook/goldens/README.md); this module only judges the
signals once measured, so it is fully testable headless against golden fixtures.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Verdicts
STABLE = "STABLE"
EXPLODING = "EXPLODING"
UNKNOWN = "UNKNOWN"

# The signals a frame may carry. A frame is a dict; any of these keys may be
# absent (that signal simply was not measured for that frame).
_SIGNAL_KEYS = ("kinetic_energy", "max_strain", "max_velocity")

# Defaults — deliberately conservative; callers override per domain.
DEFAULT_KE_RATIO_THRESHOLD = 2.0   # KE more than doubling across the window
DEFAULT_KE_WINDOW = 5              # "5 consecutive frames" per the blueprint
DEFAULT_STRAIN_BOUND = 10.0        # max_strain hard ceiling


@dataclass(frozen=True)
class ExplosionVerdict:
    """The judgement on a sim's per-frame signals.

    verdict is STABLE | EXPLODING | UNKNOWN. On EXPLODING, ``signal`` names which
    rule tripped and ``offending_frame`` is the frame index it tripped on, so the
    finding is anchored, never a vibe. On UNKNOWN, ``unknown_reason`` states the
    exact missing measurement.
    """

    verdict: str
    signal: str | None = None          # nan | strain | ke_growth
    offending_frame: int | None = None
    detail: str | None = None
    unknown_reason: str | None = None

    @property
    def exploding(self) -> bool:
        return self.verdict == EXPLODING

    @property
    def measured(self) -> bool:
        return self.verdict != UNKNOWN


def _is_number(x) -> bool:
    """True for a real numeric signal value (int/float, excluding bool)."""
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _is_bad_float(x) -> bool:
    """True for NaN or inf. Non-floats (ints, None) are never 'bad' here."""
    return isinstance(x, float) and (math.isnan(x) or math.isinf(x))


def detect_explosion(
    frames,
    *,
    ke_ratio_threshold: float = DEFAULT_KE_RATIO_THRESHOLD,
    ke_window: int = DEFAULT_KE_WINDOW,
    strain_bound: float = DEFAULT_STRAIN_BOUND,
) -> ExplosionVerdict:
    """Judge a sequence of measured per-frame signals.

    ``frames`` is a list of dicts, one per cooked frame, each optionally carrying
    ``frame`` (its index/number) and any of ``_SIGNAL_KEYS``. FP2 is enforced at
    every gap: an unmeasured OR un-evaluable sim is UNKNOWN, never STABLE. In
    particular a signal present but non-numeric, and a KE-growth rule that cannot
    run (too few frames, or a NaN-free window never assembled), both yield UNKNOWN
    rather than a fabricated pass.
    """
    if not frames:
        return ExplosionVerdict(UNKNOWN, unknown_reason="no frames measured")

    def frame_no(i: int):
        f = frames[i]
        return f.get("frame", i) if isinstance(f, dict) else i

    # Explosion RULES run first: a definite explosion on numeric data must win
    # over an unrelated malformed field elsewhere (never mask a real blow-up).

    # ── Rule 1: any NaN/inf in a measured signal (highest severity). A NaN
    # anywhere means the solve diverged; _is_bad_float is type-safe on any value.
    for i, fr in enumerate(frames):
        for key in _SIGNAL_KEYS:
            if key in fr and _is_bad_float(fr[key]):
                return ExplosionVerdict(
                    EXPLODING, signal="nan", offending_frame=frame_no(i),
                    detail=f"{key} is NaN/inf at frame {frame_no(i)}",
                )

    # ── Rule 2: max_strain over the hard bound (numeric values only). ────────
    for i, fr in enumerate(frames):
        s = fr.get("max_strain")
        if _is_number(s) and s > strain_bound:
            return ExplosionVerdict(
                EXPLODING, signal="strain", offending_frame=frame_no(i),
                detail=f"max_strain {s} > bound {strain_bound}",
            )

    # ── Rule 3: monotonic KE growth over a window of N consecutive frames. A
    # non-numeric KE is treated as a GAP (like a missing frame), so a malformed
    # value can neither crash the comparison nor be read as growth. ──────────
    kes = [fr.get("kinetic_energy") if _is_number(fr.get("kinetic_energy")) else None
           for fr in frames]
    evaluated_a_window = False
    if ke_window >= 2:
        for start in range(0, len(frames) - ke_window + 1):
            window = kes[start:start + ke_window]
            if any(k is None for k in window):
                continue  # a KE gap: this window is not evaluable
            evaluated_a_window = True
            if not all(window[j + 1] > window[j] for j in range(len(window) - 1)):
                continue  # not strictly increasing -> no growth signature here
            # Strictly increasing. Ratio uses the first NON-ZERO frame as the
            # baseline, so a runaway from rest (KE starts at 0) is still caught —
            # division by zero would otherwise have silently dropped it.
            baseline = next((v for v in window if v > 0), None)
            if baseline is None:
                continue  # all non-positive (cannot be strictly increasing to >0)
            if window[-1] / baseline > ke_ratio_threshold:
                ratio = round(window[-1] / baseline, 2)
                end_i = start + ke_window - 1
                return ExplosionVerdict(
                    EXPLODING, signal="ke_growth", offending_frame=frame_no(end_i),
                    detail=(f"kinetic_energy grew {window[0]}->{window[-1]} "
                            f"(x{ratio} over baseline {baseline}) across {ke_window} consecutive frames"),
                )

    # ── No explosion detected. Decide STABLE vs UNKNOWN honestly (FP2). ──────
    # (a) A JUDGED signal (one a rule scores) present but non-numeric could not be
    # judged -> UNKNOWN. max_velocity is informational (no rule scores it), so its
    # corruption alone does not force UNKNOWN — and any real NaN/strain/KE
    # explosion already won above, so a malformed field never masks a blow-up.
    for i, fr in enumerate(frames):
        for key in ("kinetic_energy", "max_strain"):
            v = fr.get(key)
            if v is not None and not _is_number(v):
                return ExplosionVerdict(
                    UNKNOWN,
                    unknown_reason=f"malformed signal '{key}' at frame {frame_no(i)}: {v!r} is not numeric",
                )
    # (b) KE never numerically measured -> growth cannot be judged.
    if not any(_is_number(fr.get("kinetic_energy")) for fr in frames):
        return ExplosionVerdict(UNKNOWN, unknown_reason="no kinetic_energy measured in any frame")
    # (c) KE present but no gap-free window of ke_window frames ever assembled
    # (too few frames, or every window straddled a gap). The growth rule could not
    # run, so its silence is not evidence of stability. UNKNOWN, not STABLE.
    if not evaluated_a_window:
        return ExplosionVerdict(
            UNKNOWN,
            unknown_reason=(f"KE-growth not evaluable: no {ke_window} consecutive frames "
                            "with kinetic_energy measured"),
        )

    return ExplosionVerdict(STABLE)
