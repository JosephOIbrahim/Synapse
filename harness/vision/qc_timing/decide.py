"""NR-QC-TIMING decision code, frozen rule r2 (3.3, 3.4, 3.5). Stdlib only, pure.

Frame dicts carry ``id``, ``reaches`` (the scan returned without an exception and
``inconclusive`` is False), and the per-frame values ``T``, ``RW``, ``Floor`` and
``share`` formed from that frame's own medians (see :func:`frame_values`).
"""
from __future__ import annotations

import statistics
from typing import Any, Dict, Iterable, List, Mapping

B_SECONDS = 2.0
THRESHOLD = 0.5
TIER = ("char-8", "sib-v016", "sib-v017")
FALLBACK = ("char-9", "char-2")
QUANTITIES = ("T", "RW", "Floor", "share")
MEDIAN_FIELDS = ("R", "S", "S_dense", "S_rest", "W")


def median(values: Iterable[float]) -> float:
    """Median; two values give their mean (3.5, derived)."""
    return float(statistics.median(list(values)))


def frame_values(m: Mapping[str, float]) -> Dict[str, float]:
    """T, R+W, Floor and S_dense/T from one frame's medians of R, S, S_dense, S_rest, W.

    Each of the five is its own median over the frame's passes; these four are
    formed from those medians (3.3). Floor is never T - S_dense.
    """
    T = m["R"] + m["S"] + m["W"]
    return {
        "T": T,
        "RW": m["R"] + m["W"],
        "Floor": m["R"] + m["W"] + m["S_rest"],
        "share": (m["S_dense"] / T) if T > 0 else 0.0,
    }


def branch(T: float, RW: float, Floor: float, share: float,
           B: float = B_SECONDS, thr: float = THRESHOLD) -> int:
    """The five branches of 3.4. T = B is 1, Floor = B is 4, share = thr is 3."""
    if T <= B:
        return 1
    if RW > B:
        return 2
    if Floor >= B:
        return 4
    return 3 if share >= thr else 5


def unit_value(frames: List[Mapping[str, Any]], B: float = B_SECONDS,
               thr: float = THRESHOLD) -> Dict[str, Any]:
    """Median of each quantity across the frames, separately (3.3); min and max
    as the spread. The share is the median of the per-frame shares."""
    if not frames:
        raise ValueError("a voting unit needs at least one frame that reached a result")
    out: Dict[str, Any] = {"n_frames": len(frames)}
    for q in QUANTITIES:
        vals = [float(f[q]) for f in frames]
        out[q] = median(vals)
        out[q + "_min"] = min(vals)
        out[q + "_max"] = max(vals)
    out["branch"] = branch(out["T"], out["RW"], out["Floor"], out["share"], B, thr)
    return out


def who_decides(frames: List[Mapping[str, Any]]) -> int:
    """The row of the 3.5 table: how many deciding stills reach a result (0 to 3)."""
    return sum(1 for f in frames if f["id"] in TIER and f["reaches"])


def decide(frames: List[Mapping[str, Any]], B: float = B_SECONDS,
           thr: float = THRESHOLD) -> Dict[str, Any]:
    """Row, voting units with their values and branches, and the verdict.

    3 or 2 conclusive stills: the tier, char-9 (if its frame reaches a result)
    and char-2 (median of its conclusive frames) vote; the verdict is branch k
    when every voting unit lands in k, else ``split``. 1 or 0: char-9 and char-2
    decide and the lone still does not vote; both must reach a result: the same
    branch is the verdict, different branches ``split``, either missing
    ``no verdict``.
    """
    ok = [f for f in frames if f["reaches"]]
    row = who_decides(frames)
    units: Dict[str, Dict[str, Any]] = {}
    if row >= 2:
        units["tier"] = unit_value([f for f in ok if f["id"] in TIER], B, thr)
    for uid in FALLBACK:
        sub = [f for f in ok if f["id"] == uid]
        if sub:
            units[uid] = unit_value(sub, B, thr)
    if row >= 2:
        found = {u["branch"] for u in units.values()}
        verdict = f"branch {next(iter(found))}" if len(found) == 1 else "split"
    elif all(uid in units for uid in FALLBACK):
        a, b = units["char-9"]["branch"], units["char-2"]["branch"]
        verdict = f"branch {a}" if a == b else "split"
    else:
        verdict = "no verdict"
    return {"row": row, "units": units, "voting": sorted(units), "verdict": verdict}
