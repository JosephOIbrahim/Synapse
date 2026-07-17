"""Load + resolve RETINA T1 tolerance profiles (blueprint §7 governance).

``qc_profiles.toml`` carries the tolerances T1 asserts against, per renderer ×
denoiser policy × sample tier. This loader reads them with the stdlib ``tomllib``
(Python 3.11+ — zero third-party dependency) and merges a specific profile over
``[default]``.

Governance rules this module upholds:

* **Thresholds, never equality** — the profile only ever *supplies* tolerances;
  no code here compares for exact equality.
* **Commandment 7** — a threshold is a test assertion; it is never loosened to
  green a verdict. This loader has no runtime-relax path: it reads static config
  and merges inheritance, nothing more.
* **Honesty** — an unknown (renderer, policy, tier) inherits ``[default]``
  cleanly rather than fabricating a looser tolerance.

Zero ``hou``, zero ``cv2`` — pure stdlib, so it loads in stock CI.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_TOML = Path(__file__).with_name("qc_profiles.toml")

# The knobs a resolved profile must carry — every metric parameter T1 reads.
REQUIRED_KEYS = (
    "diff_threshold",
    "morph_radius",
    "leak_eps",
    "matte_dilation",
    "ssim_min",
    "ssim_data_range",
    "black_threshold",
    "blown_threshold",
    "black_ratio",
    "clip_ratio",
    "firefly_std_devs",
)


class ProfileError(ValueError):
    """The profile TOML is missing ``[default]`` or a required knob."""


def load_profiles(path: str | Path = DEFAULT_TOML) -> Dict[str, Any]:
    """Parse the profile TOML into a dict. Raises :class:`ProfileError` if the
    ``[default]`` table is absent or incomplete — a missing tolerance must fail
    loud, never default to a silent zero."""
    p = Path(path)
    with p.open("rb") as fh:
        data = tomllib.load(fh)
    default = data.get("default")
    if not isinstance(default, dict):
        raise ProfileError(f"{p}: no [default] profile table")
    missing = [k for k in REQUIRED_KEYS if k not in default]
    if missing:
        raise ProfileError(f"{p}: [default] missing required knobs: {missing}")
    return data


def resolve_profile(
    profiles: Dict[str, Any],
    *,
    renderer: Optional[str] = None,
    denoiser_policy: Optional[str] = None,
    sample_tier: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge the most specific ``[renderer.denoiser_policy.sample_tier]`` table over
    ``[default]``. Any level that is absent (or ``None``) simply contributes
    nothing — an unknown combination resolves to ``[default]`` unchanged.

    Returns a flat dict carrying every :data:`REQUIRED_KEYS` knob. The merge only
    ever *narrows or restates* tolerances from ratified config — it never invents
    or loosens one at runtime (Commandment 7)."""
    resolved: Dict[str, Any] = dict(profiles["default"])
    node: Any = profiles
    for level in (renderer, denoiser_policy, sample_tier):
        if level is None:
            return resolved
        node = node.get(level) if isinstance(node, dict) else None
        if not isinstance(node, dict):
            return resolved
    # node is now the leaf table; overlay only its scalar overrides.
    for key, val in node.items():
        if not isinstance(val, dict):
            resolved[key] = val
    return resolved


def default_profile(path: str | Path = DEFAULT_TOML) -> Dict[str, Any]:
    """Convenience: the ``[default]`` profile, loaded + validated."""
    return dict(load_profiles(path)["default"])
