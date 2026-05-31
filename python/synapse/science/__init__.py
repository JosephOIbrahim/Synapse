"""SYNAPSE science loop — falsifiability-gated API surface verification.

Pure-Python (stdlib + dataclasses + inspect). ZERO Houdini/apex/hou imports:
namespaces are injected at probe time, so every module here is standalone-
testable with a fake namespace dict.

Public surface:
    ProbeSpec, ProbeResult, probe   — the pure probe primitive (probe.py)
    Record, Registry                — dedup-indexed append-only store (registry.py)
    run_search                      — the search driver / second-seed gate (loop.py)
    APEX_SEED                       — seed claims about the H21.0.671 APEX surface
"""

from __future__ import annotations

from .probe import ProbeSpec, ProbeResult, probe
from .registry import Record, Registry
from .loop import run_search
from .apex_probes import APEX_SEED

__all__ = [
    "ProbeSpec",
    "ProbeResult",
    "probe",
    "Record",
    "Registry",
    "run_search",
    "APEX_SEED",
]
