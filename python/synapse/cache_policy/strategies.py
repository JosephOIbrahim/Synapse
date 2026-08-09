"""python/synapse/cache_policy/strategies.py -- Mile 2 (resource-aware-cache Phase 0), R-CACHE-1.

Implements the §9 cache strategy resolver as a versioned registry, per the Protocol shape
blueprint §9 sketches (``CacheStrategy``). Models the SHAPE of the resolution decision only.

V0/UNVERIFIED (adjudication c6, ADOPT: "Adopt the discipline, probe the names"): this module
NEVER asserts a Houdini parameter name or its behavior as confirmed fact -- "Time Dependent",
"Simulation" on/off, ".vdb-only" format selection are all File Cache SOP parm-level claims
this repo has zero live evidence for (adjudication e8: ``connectivity_22.json`` has zero
occurrences of ``timedependent``/``trange``/``initsim``/``cachesim``/``savetodisk``). Every
docstring/comment below that names one of those parms is marked V0 and none of them is ever
emitted as a mutation -- this module returns a ``strategy_id`` string and a context
classification, nothing that touches a live node.

cache_policy imports stdlib only -- no ``hou``, no Qt (binding constraint #2). This module
resolves a strategy from a caller-supplied ``NodeDescriptor`` classification (context +
data-class strings); it never introspects a live node itself. A Phase 1 caller (with a real
``hou`` import elsewhere) is responsible for producing that classification honestly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .models import Context, StrategySupport


@dataclass
class NodeDescriptor:
    """Caller-supplied, already-classified node context. ``UNKNOWN``/``None`` defaults
    mean "not classified" -- resolve_strategy() must never guess a favorable classification
    from an unset field."""
    context: str = Context.UNKNOWN.value
    data_class: str = "unknown"  # "geometry_mixed" | "vdb_only" | "unknown"
    is_solver_result: Optional[bool] = None
    is_independent_frames: Optional[bool] = None


@dataclass
class StrategyResolution:
    strategy_id: str
    context: str
    supported: bool
    support: str
    reasons: list = field(default_factory=list)


def resolve_strategy(descriptor: NodeDescriptor) -> StrategyResolution:
    """§9 strategy table, Phase-0 scope: only the SOP row family has an implemented
    resolver (V0 on parm names, per this module's header). DOP/LOP/COP/unknown all resolve
    ``supported=False`` because no tested resolver exists in this repository yet for those
    contexts -- this generalizes §9's explicit "Return unsupported until a tested resolver
    exists" (stated there for COP specifically) to every context this mile does not build a
    real resolver for, rather than asserting untested behavior as fact for DOP/LOP.
    """
    ctx = descriptor.context

    if ctx == Context.SOP.value:
        if descriptor.is_solver_result is True:
            return StrategyResolution(
                strategy_id="sop_filecache_solver_result_v1", context=ctx, supported=True,
                support=StrategySupport.SUPPORTED.value,
                reasons=[
                    "Boundary placed after solver/result output, not an arbitrary upstream "
                    "branch (blueprint §9).",
                    "V0/unverified: 'Time Dependent'/'Simulation' File Cache parm names and "
                    "behavior are not confirmed on this build (adjudication c6/e8).",
                ],
            )
        if descriptor.is_independent_frames is True:
            return StrategyResolution(
                strategy_id="sop_filecache_independent_frames_v1", context=ctx, supported=True,
                support=StrategySupport.SUPPORTED.value,
                reasons=[
                    "Independent frames can be scheduled in parallel (blueprint §9/§11.3).",
                    "V0/unverified: 'Simulation off' parm semantics not confirmed on this "
                    "build.",
                ],
            )
        if descriptor.data_class == "vdb_only":
            return StrategyResolution(
                strategy_id="sop_filecache_vdb_v1", context=ctx, supported=True,
                support=StrategySupport.SUPPORTED.value,
                reasons=[
                    "VDB-only output; .vdb format candidate (blueprint §9).",
                    "V0/unverified: '.vdb'-only-format selection is a parm-level claim with "
                    "zero live evidence on this build.",
                ],
            )
        return StrategyResolution(
            strategy_id="sop_filecache_geometry_v1", context=ctx, supported=True,
            support=StrategySupport.SUPPORTED.value,
            reasons=[
                "General safe default for mixed/unknown Houdini geometry: .bgeo.sc "
                "(blueprint §9).",
            ],
        )

    if ctx == Context.DOP.value:
        return StrategyResolution(
            strategy_id="dop_unsupported_v0", context=ctx, supported=False,
            support=StrategySupport.UNSUPPORTED.value,
            reasons=[
                "Classic DOP simulation requires solver-specific result-cache/checkpoint "
                "strategies (blueprint §9); none is implemented in this Phase-0 build. "
                "Refusing to collapse into one generic SOP cache.",
            ],
        )

    if ctx == Context.LOP.value:
        return StrategyResolution(
            strategy_id="lop_usd_cache_unsupported_v0", context=ctx, supported=False,
            support=StrategySupport.UNSUPPORTED.value,
            reasons=[
                "Solaris/LOP caching requires USD-aware path/layer policy and stage "
                "composition validation (blueprint §9); not implemented in this Phase-0 "
                "build.",
            ],
        )

    if ctx == Context.COP.value:
        return StrategyResolution(
            strategy_id="cop_unsupported_v0", context=ctx, supported=False,
            support=StrategySupport.UNSUPPORTED.value,
            reasons=["Copernicus/COP: unsupported until a tested resolver exists (blueprint §9, explicit)."],
        )

    return StrategyResolution(
        strategy_id="unknown_context_unsupported", context=ctx, supported=False,
        support=StrategySupport.UNSUPPORTED.value,
        reasons=["Unrecognized/unclassified node context -- never guess a strategy (blueprint §9)."],
    )
