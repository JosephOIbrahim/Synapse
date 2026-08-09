"""python/synapse/cache_policy/policy_loader.py -- Mile 2 (resource-aware-cache Phase 0), R-CACHE-1.

Loads a §7.4 ``CachePolicy`` from defaults + an optional project-override JSON/dict, with
validation per §17.2's boundary test: "policy JSON rejects invalid fractions, negative
sizes, and unknown enum values." Pure stdlib (``json`` only). No ``hou``, no Qt.
"""
from __future__ import annotations

import json
from dataclasses import fields as dc_fields
from pathlib import Path
from typing import Optional, Union

from .models import CachePolicy, NETWORK_CACHE_POLICY_VALUES, RETENTION_POLICY_VALUES

_FRACTION_FIELDS = (
    "ram_safety_fraction", "vram_safety_fraction", "minimum_free_disk_after_fraction",
    "single_sample_extrapolation_margin",
)
_NONNEGATIVE_SIZE_FIELDS = (
    "minimum_free_disk_after_bytes",
)
_POSITIVE_FIELDS = (
    "cache_size_safety_multiplier",
)
_NONNEGATIVE_FIELDS = (
    "minimum_seconds_saved", "minimum_expected_future_reads",
)
_ENUM_FIELDS = {
    "network_cache_policy": NETWORK_CACHE_POLICY_VALUES,
    "retention_policy": RETENTION_POLICY_VALUES,
}
_BOOL_FIELDS = ("allow_low_confidence_bake_recommendation", "allow_unmanifested_cache_load")

_ALL_KNOWN_FIELDS = frozenset({f.name for f in dc_fields(CachePolicy)})


class PolicyValidationError(ValueError):
    """Raised for any policy field that fails validation. Never silently clamped/coerced --
    an invalid policy is a hard error, not a warning, because it governs disk-write safety
    thresholds downstream."""


def _validate(data: dict) -> None:
    errors = []

    unknown_keys = set(data.keys()) - _ALL_KNOWN_FIELDS
    if unknown_keys:
        errors.append(f"unknown policy field(s): {sorted(unknown_keys)}")

    for name in _FRACTION_FIELDS:
        if name in data:
            v = data[name]
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not (0.0 <= v <= 1.0):
                errors.append(f"{name} must be a fraction in [0.0, 1.0], got {v!r}")

    for name in _NONNEGATIVE_SIZE_FIELDS:
        if name in data:
            v = data[name]
            if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
                errors.append(f"{name} must be a non-negative size, got {v!r}")

    for name in _POSITIVE_FIELDS:
        if name in data:
            v = data[name]
            if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
                errors.append(f"{name} must be strictly positive, got {v!r}")

    for name in _NONNEGATIVE_FIELDS:
        if name in data:
            v = data[name]
            if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
                errors.append(f"{name} must be non-negative, got {v!r}")

    for name in _BOOL_FIELDS:
        if name in data:
            v = data[name]
            if not isinstance(v, bool):
                errors.append(f"{name} must be a boolean, got {v!r}")

    for name, allowed in _ENUM_FIELDS.items():
        if name in data:
            v = data[name]
            if v not in allowed:
                errors.append(f"{name} must be one of {sorted(allowed)}, got {v!r}")

    if errors:
        raise PolicyValidationError("; ".join(errors))


def merge_policy_overrides(defaults: dict, overrides: Optional[dict]) -> dict:
    """Shallow merge: overrides replace matching keys in defaults, unknown keys pass
    through so ``_validate`` can reject them explicitly rather than the merge silently
    dropping a typo'd field name."""
    merged = dict(defaults)
    if overrides:
        merged.update(overrides)
    return merged


def default_policy_dict() -> dict:
    policy = CachePolicy()
    return {f.name: getattr(policy, f.name) for f in dc_fields(CachePolicy)}


def load_policy(overrides: Optional[dict] = None) -> CachePolicy:
    """Builds a validated ``CachePolicy`` from the built-in defaults plus an optional
    override dict (already-parsed JSON or a plain dict). Raises ``PolicyValidationError``
    on any invalid fraction, negative size, or unknown enum value -- never silently
    clamps."""
    merged = merge_policy_overrides(default_policy_dict(), overrides)
    _validate(merged)
    return CachePolicy(**merged)


def load_policy_from_json(path: Union[str, Path]) -> CachePolicy:
    """Reads a project override CachePolicy JSON file and validates it against the
    defaults. Raises ``PolicyValidationError`` on invalid content, ``OSError``/
    ``json.JSONDecodeError`` on unreadable/malformed files -- never falls back to a silent
    default on a read failure (that would hide a real project-policy typo)."""
    text = Path(path).read_text(encoding="utf-8")
    overrides = json.loads(text)
    if not isinstance(overrides, dict):
        raise PolicyValidationError(f"policy file {path} must contain a JSON object, got {type(overrides).__name__}")
    return load_policy(overrides)
