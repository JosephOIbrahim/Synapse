"""Fenced Jev adapter (invariant 5 of the Jev README): a product-side, shadow-first
judgment call that never blocks, never raises, never logs a key, and never reaches
back into the build-time Jev tooling. See :mod:`synapse.jev.adapter`.
"""
from __future__ import annotations

from synapse.jev.adapter import judge, resolve_key

__all__ = ["judge", "resolve_key"]
