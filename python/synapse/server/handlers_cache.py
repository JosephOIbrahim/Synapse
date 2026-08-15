"""python/synapse/server/handlers_cache.py -- Mile 4 (resource-aware-cache Phase 1), R-CACHE-1.

Wires the Phase 0 pure policy package (``synapse.cache_policy``) and passive host probe
(``host/cache_host_probe.py``) into a single read-only, feature-flagged MCP tool:
``synapse_assess_cache``. Authorized scope: ruling R-CACHE-1
(docs/reviews/cache-adjudication-ruling.md, Joe/CTO, 2026-08-09) item 4 (the d6 cure --
this handler + its TOOL_DEFS/bridge_adapter registration IS the "live caller" the
adjudication required before any cache_policy module could ship).

SCOPE (binding, this mile): read-only advisor ONLY. Nothing in this module's call graph
creates a node, writes a file, or mutates the scene -- there is no ``synapse_insert_cache``
or ``synapse_bake_cache`` here; Phase 2 is out of scope and additionally REJECTed at HEAD
(adjudication e3: no cancel API for an in-flight cook on this build).

Feature flag: ``SYNAPSE_CACHE_ADVISOR_ENABLED`` (see ``advisor_enabled()``), OFF by
default. When disabled, ``_handle_assess_cache`` returns a static "disabled" advice card
WITHOUT resolving a node, touching ``hou``, or calling the probe -- the feature is inert
by construction, not merely by convention, until explicitly turned on.

Architecture -- two layers, split deliberately so the decision pipeline is testable with
zero Houdini present (tests/test_cache_assess_tool.py):

  * ``assess_cache_core()`` -- the pipeline. Takes an already-resolved node object
    (duck-typed: a real ``hou.OpNode`` OR a test fake, matching the convention
    ``host/cache_host_probe.py``'s own ``observe_node_passively`` already established)
    plus caller-supplied classification hints, and drives passive probe ->
    WorkloadSnapshot -> resolve_strategy -> decide_cache -> advice card. Imports no
    ``hou`` of its own; every ``hou``-touching call happens on the ``node`` object the
    caller already resolved, and only the exact calls
    ``host/cache_host_probe.py::observe_node_passively`` makes (never re-implemented
    here -- binding constraint #5, no forced cook).
  * ``CacheHandlerMixin._handle_assess_cache`` -- the live MCP-facing wrapper. Resolves
    the real node from the payload (explicit path, else current selection) under
    ``run_on_main``, detects the machine profile, loads policy, and calls
    ``assess_cache_core``. This is the ONLY place in this module that imports/touches
    ``hou`` directly.

Symbol provenance (CLAUDE.md §12/§15): ``hou.node``, ``hou.selectedNodes``,
``hou.OpNode.{path,type}``, ``hou.NodeType.{name,category}``, ``hou.NodeTypeCategory.name``
are all confirmed present (dir()-membership) on the committed
python/synapse/cognitive/tools/data/h22_symbol_table.json (houdini_version 22.0.400).
``_classify_context`` never asserts the exact category-name STRING as verified fact (that
is intake-appendix c1-class V0 territory) -- it does a defensive, case-insensitive prefix
match and falls back to Context.UNKNOWN on anything it does not recognize, per binding
constraint (never guess a supported context).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from ..core.aliases import resolve_param, resolve_param_with_default
from ..core.errors import HoudiniUnavailableError, NodeNotFoundError, SynapseUserError

try:
    import hou  # type: ignore

    HOU_AVAILABLE = True
except ImportError:  # pragma: no cover -- exercised in the no-hou test environment
    hou = None  # type: ignore
    HOU_AVAILABLE = False

# host/cache_host_probe.py is not a package -- sys.path-insert the host dir, matching the
# convention host/cache_host_probe.py itself uses for python/ and
# tests/test_cache_no_forced_cook.py uses for host/.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_HOST_DIR = _REPO_ROOT / "host"
try:
    if str(_HOST_DIR) not in sys.path:
        sys.path.insert(0, str(_HOST_DIR))
    import cache_host_probe as _chp  # type: ignore

    CACHE_HOST_PROBE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _chp = None  # type: ignore
    CACHE_HOST_PROBE_AVAILABLE = False

try:
    from ..cache_policy import (
        CachePolicy,
        Context,
        FrameRange,
        MachineProfile,
        NodeDescriptor,
        WorkloadSnapshot,
        decide_cache,
        load_policy,
        resolve_strategy,
        to_jsonable,
    )

    CACHE_POLICY_AVAILABLE = True
except ImportError:  # pragma: no cover
    CACHE_POLICY_AVAILABLE = False


_DEPENDENCY_ERROR = (
    "Cache advisor dependencies unavailable: host/cache_host_probe.py or "
    "synapse.cache_policy failed to import."
)

# In-memory only (§8.2's dirty-node historical fallback) -- process-lifetime, never
# persisted. A durable version is a Memory-plane decision deferred beyond this mile
# (adjudication b12/d6: no new persistence authority here).
_LAST_OBSERVATION_STORE = _chp.LastObservationStore() if CACHE_HOST_PROBE_AVAILABLE else None


# --------------------------------------------------------------------------- feature flag

def advisor_enabled() -> bool:
    """SYNAPSE_CACHE_ADVISOR_ENABLED, OFF by default. Mirrors the repo convention
    (core/floor_gate.py's SYNAPSE_FLOOR_FSYNC_SYNC, panel/designsystem/tokens.py's
    SYNAPSE_REDUCED_MOTION): ``os.environ.get(...).strip().lower() in {truthy}``,
    unset/anything else -> disabled."""
    return os.environ.get("SYNAPSE_CACHE_ADVISOR_ENABLED", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


_DISABLED_MESSAGE = (
    "Cache advisor is disabled (Phase 1, feature-flagged off by default).\n"
    "Set SYNAPSE_CACHE_ADVISOR_ENABLED=1 to enable read-only cache assessment.\n"
    "No node was inspected and no cook was triggered."
)


# --------------------------------------------------------------------------- context classification

def _classify_context(node: Any) -> str:
    """Best-effort SOP/DOP/LOP/COP/TOP classification from
    ``node.type().category().name()``. Never raises; returns Context.UNKNOWN.value on any
    failure or unrecognized category name -- never guesses a supported context from a
    failed or ambiguous read (blueprint §9: "never guess a strategy"). Only ever called
    from assess_cache_core(), which already guards on CACHE_POLICY_AVAILABLE (so ``Context``
    is always a real import here, never an unbound name)."""
    try:
        category_name = node.type().category().name()
    except Exception:
        return Context.UNKNOWN.value
    if not isinstance(category_name, str):
        return Context.UNKNOWN.value
    lowered = category_name.lower()
    if lowered.startswith("sop"):
        return Context.SOP.value
    if lowered.startswith("dop"):
        return Context.DOP.value
    if lowered.startswith("lop"):
        return Context.LOP.value
    if lowered.startswith("cop"):
        return Context.COP.value
    if lowered.startswith("top"):
        return Context.TOP.value
    return Context.UNKNOWN.value


# --------------------------------------------------------------------------- advice card (§14.1/§14.2)

_VERDICT_LABELS = {
    "use_valid_cache": "USE EXISTING CACHE",
    "cache_now": "CACHE RECOMMENDED",
    "insert_boundary_only": "INSERT BOUNDARY ONLY",
    "measure_first": "MEASURE FIRST",
    "optimize_first": "OPTIMIZE FIRST",
    "not_worth_it": "NOT WORTH CACHING",
    "insufficient_disk": "INSUFFICIENT DISK",
    "unsupported": "UNSUPPORTED CONTEXT",
    "unknown": "UNKNOWN",
}
_MAX_REASONS_SHOWN = 3  # §14.2: "show at most three decisive reasons before 'More details'"
_VALIDITY_NOT_A_PROBLEM = ("not_present", "valid")


def _fmt_bytes(n: Optional[float]) -> str:
    if n is None:
        return "unknown"
    gb = n / (1024.0 ** 3)
    if gb >= 1.0:
        return f"{gb:.1f} GB"
    return f"{n / (1024.0 ** 2):.1f} MB"


def _fmt_seconds(n: Optional[float]) -> str:
    if n is None:
        return "unknown"
    if n >= 60.0:
        return f"{n / 60.0:.1f} min"
    return f"{n:.2f} s"


def _render_advice_card(decision, *, node_path: str) -> str:
    """CacheDecision -> plain/markdown-ish text. Renders through the EXISTING panel
    result surface (python/synapse/panel/message_formatter.py's format_response /
    format_synapse_message, which reads a response dict's ``message`` field) -- this
    function only builds that string. No new panel module (R-CACHE-1 disposition item 4).

    Follows blueprint §14.1's six questions (recommend? boundary? why? cost?
    uncertain/blocked? approval needed?) and §14.2's rules: one verdict lead line, max
    three reasons before "more details", ranges not false precision, a blocker rendered
    separately from uncertainty, stale/partial/unverifiable status never buried.
    """
    label = _VERDICT_LABELS.get(decision.verdict, decision.verdict.upper())
    confidence = (decision.confidence or "unknown").upper()
    lines = [f"{label} -- {confidence} CONFIDENCE", "", f"Node: {node_path}"]

    if decision.frame_range:
        fr = decision.frame_range
        lines.append(f"Range: {fr.get('start')}-{fr.get('end')}")
    lines.append(f"Strategy: {decision.strategy_id}")

    est = decision.estimates
    cost_lines = []
    if est.cache_bytes is not None:
        cost_lines.append(
            f"Estimated disk: {_fmt_bytes(est.cache_bytes.low)}-{_fmt_bytes(est.cache_bytes.high)}"
        )
    if est.write_seconds is not None:
        cost_lines.append(
            f"Estimated write time: {_fmt_seconds(est.write_seconds.low)}-{_fmt_seconds(est.write_seconds.high)}"
        )
    if est.break_even_future_reads is not None:
        cost_lines.append(
            f"Break-even future reads: {est.break_even_future_reads.low:.2f}-"
            f"{est.break_even_future_reads.high:.2f}"
        )
    if cost_lines:
        lines.append("")
        lines.append("Cost")
        lines.extend(f"- {c}" for c in cost_lines)

    if decision.cache_validity not in _VALIDITY_NOT_A_PROBLEM:
        lines.append("")
        lines.append(f"Cache status: {decision.cache_validity.upper()} -- not usable as-is")

    reasons = decision.reasons[:_MAX_REASONS_SHOWN]
    if reasons:
        lines.append("")
        lines.append("Why")
        lines.extend(f"- {r}" for r in reasons)
        remaining = len(decision.reasons) - _MAX_REASONS_SHOWN
        if remaining > 0:
            lines.append(f"- ({remaining} more reason(s) -- ask for details)")

    if decision.blockers:
        lines.append("")
        lines.append("Blocked")
        lines.extend(f"- {b}" for b in decision.blockers)

    if decision.missing_evidence:
        lines.append("")
        lines.append("Uncertain / missing evidence")
        lines.extend(f"- {m}" for m in decision.missing_evidence)

    lines.append("")
    lines.append(
        "Action: read-only advisor only in this mile -- no insert/bake tool exists yet; "
        "any future disk write or node mutation requires separate authorized approval."
    )
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- the pipeline

def assess_cache_core(
    node: Any,
    *,
    node_path: str,
    machine: "MachineProfile",
    node_type: Optional[str] = None,
    context: Optional[str] = None,
    frame_range: Optional[tuple] = None,
    expected_future_reads: Optional[float] = None,
    is_solver_result: Optional[bool] = None,
    is_independent_frames: Optional[bool] = None,
    data_class: Optional[str] = None,
    policy: Optional["CachePolicy"] = None,
    last_observation_store: Optional[Any] = None,
    evidence_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Passive observation -> deterministic policy -> CacheDecision -> advice card.

    Read-only: the only calls made against ``node`` are the ones
    ``cache_host_probe.observe_node_passively`` itself makes (never re-implemented here --
    binding constraint #5/§8.2: geometry() is never called when needsToCook() is True).
    No disk write, no node creation, anywhere in this function.

    ``evidence_overrides`` -- Phase-1-forward escape hatch (documented, not a blueprint
    field -- same shape as ``WorkloadSnapshot.compute_seconds_total``'s own "Phase-0
    addition" pattern in cache_policy/models.py). Phase 0 only ever populates cook-time/
    geometry-memory evidence from the passive probe; it has no manifest reader, no
    boundary-signal detector, and no calibrated size estimator yet (those are Phase 1.x/3
    concerns per the blueprint's own §11.1 estimation ladder). This lets an ALREADY-KNOWN
    piece of real evidence (never a guess) -- e.g. ``peak_working_set_bytes``,
    ``gpu_relevance``, ``boundary_signals``, ``existing_cache``,
    ``estimated_output_bytes_per_frame``, ``compute_seconds_total``,
    ``write_seconds_total``, ``read_seconds_total`` -- reach ``decide_cache`` through the
    real assess path instead of only through direct WorkloadSnapshot construction (which
    is how tests/test_cache_policy.py already exercises decision.py). NOT exposed on the
    live MCP tool's JSON schema (blueprint §13.3 names only node/path/range/expected-reads
    for this tool in Phase 1) -- a caller key that is not a real ``WorkloadSnapshot``
    field name raises ``TypeError`` rather than being silently dropped.
    """
    if not (CACHE_HOST_PROBE_AVAILABLE and CACHE_POLICY_AVAILABLE):
        raise RuntimeError(_DEPENDENCY_ERROR)

    policy = policy if policy is not None else load_policy()
    store = last_observation_store if last_observation_store is not None else _LAST_OBSERVATION_STORE
    resolved_context = context if context is not None else _classify_context(node)

    observation = _chp.observe_node_passively(
        node, store, node_path=node_path, node_type=node_type,
    )

    descriptor = NodeDescriptor(
        context=resolved_context,
        data_class=data_class if data_class is not None else "unknown",
        is_solver_result=is_solver_result,
        is_independent_frames=is_independent_frames,
    )
    strategy = resolve_strategy(descriptor)

    kwargs = _chp.to_workload_snapshot_kwargs(observation)
    kwargs["context"] = resolved_context
    kwargs["cache_strategy_id"] = strategy.strategy_id
    kwargs["strategy_support"] = strategy.support
    kwargs["strategy_support_reasons"] = list(strategy.reasons)
    if frame_range is not None:
        start, end = frame_range[0], frame_range[1]
        step = frame_range[2] if len(frame_range) > 2 else 1
        kwargs["frame_range"] = FrameRange(start=start, end=end, step=step)
    if expected_future_reads is not None:
        kwargs["expected_future_reads"] = expected_future_reads
    if evidence_overrides:
        kwargs.update(evidence_overrides)
    workload = WorkloadSnapshot(**kwargs)

    decision = decide_cache(machine, workload, strategy, policy)
    resolved_node_path = observation["node_path"]
    card = _render_advice_card(decision, node_path=resolved_node_path)

    return {
        "schema": "synapse.cache_assessment_response/v1",
        "status": "ok",
        "node_path": resolved_node_path,
        "node_type": observation["node_type"],
        "verdict": decision.verdict,
        "confidence": decision.confidence,
        "cache_validity": decision.cache_validity,
        "strategy_id": strategy.strategy_id,
        "strategy_supported": strategy.supported,
        "decision": to_jsonable(decision),
        "observation_status": observation["observation_status"],
        "warnings": list(observation.get("warnings", [])),
        "message": card,
    }


# --------------------------------------------------------------------------- live wrapper

def _detect_machine_profile(cache_root: Optional[str]) -> "MachineProfile":
    """The ONLY place this module calls host/cache_host_probe.py's hardware detection.
    Read-only OS/subprocess probing (disk_usage, cpu_count, a bounded 5s nvidia-smi call)
    -- takes ``cache_root`` as a plain argument rather than reading ``hou.getenv`` itself
    so this can run OFF the main thread (see the main-thread hygiene note on
    ``_handle_assess_cache`` below). Only ever called from the live wrapper -- tests pass
    a pre-built MachineProfile fixture directly to assess_cache_core."""
    import synapse

    profile_dict = _chp.detect_machine_profile(
        synapse_version=getattr(synapse, "__version__", None), cache_root=cache_root,
    )
    return _chp.maybe_construct_machine_profile(profile_dict)


class CacheHandlerMixin:
    """Mile 4 (resource-aware-cache Phase 1) -- ``synapse_assess_cache``. Read-only,
    feature-flagged OFF by default. See this module's header for the full architecture.

    Main-thread hygiene: this repo has a documented freeze class from long-running work
    inside a single ``run_on_main`` closure (blocking Houdini's GUI thread). The hardware
    probe (bounded 5s nvidia-smi subprocess + disk_usage) does NOT need ``hou`` beyond a
    single cheap ``hou.getenv("HIP")`` read, so ``_handle_assess_cache`` uses TWO short
    ``run_on_main`` calls -- resolve node + read HIP first, then (after the potentially-
    slow off-main-thread probe) observe + decide -- instead of one call spanning both.
    """

    def _handle_assess_cache(self, payload: Dict) -> Dict:
        if not advisor_enabled():
            return {"status": "ok", "verdict": "disabled", "message": _DISABLED_MESSAGE}

        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()
        if not (CACHE_HOST_PROBE_AVAILABLE and CACHE_POLICY_AVAILABLE):
            raise RuntimeError(_DEPENDENCY_ERROR)

        node_path = resolve_param(payload, "node", required=False)
        frame_start = resolve_param_with_default(payload, "frame_start", None)
        frame_end = resolve_param_with_default(payload, "frame_end", None)
        expected_future_reads = resolve_param_with_default(payload, "expected_future_reads", None)
        is_solver_result = resolve_param_with_default(payload, "is_solver_result", None)
        is_independent_frames = resolve_param_with_default(payload, "is_independent_frames", None)
        data_class = resolve_param_with_default(payload, "data_class", None)
        # NO policy_overrides here (B1 fix, reviewer showstopper on 87e758bc): blueprint
        # §13.3 declares this tool's input as ONLY node/path/range/expected-reads. §7.4's
        # policy overrides are project-scoped (§15), never per-MCP-call, and §10.4's
        # safety-invariant precedence + "receipt should say 'user override'" rule are not
        # honored by a bare threshold swap with no trace in the response. An LLM caller
        # could otherwise flip insufficient_disk -> cache_now (or the reverse) by supplying
        # e.g. cache_size_safety_multiplier=0.001 with zero record that thresholds moved --
        # exactly the machine-specs+prompt->LLM-opinion->bake shape §5 refuses. Always the
        # unmodified default policy on the live path.

        from .main_thread import run_on_main

        def _resolve_node_on_main():
            if node_path:
                node = hou.node(node_path)  # type: ignore[union-attr]
                if node is None:
                    raise NodeNotFoundError(node_path)
            else:
                selected = hou.selectedNodes()  # type: ignore[union-attr]
                if not selected:
                    raise SynapseUserError(
                        "No node path supplied and no node is currently selected -- "
                        "synapse_assess_cache needs one or the other."
                    )
                node = selected[0]
            hip_dir = hou.getenv("HIP")  # type: ignore[union-attr]
            return node, node.path(), node.type().name(), hip_dir

        node, resolved_path, resolved_type, hip_dir = run_on_main(_resolve_node_on_main, label="cache:_handle_assess_cache")

        # OFF the main thread: bounded 5s nvidia-smi subprocess + disk_usage. Never a
        # hou.* call from here down to the machine-profile return.
        machine = _detect_machine_profile(cache_root=hip_dir)
        policy = load_policy()
        frame_range = (
            (frame_start, frame_end)
            if frame_start is not None and frame_end is not None
            else None
        )

        def _observe_and_decide_on_main():
            # Short: only the exact hou.* calls observe_node_passively makes, plus pure
            # policy math -- see assess_cache_core's docstring.
            return assess_cache_core(
                node,
                node_path=resolved_path,
                node_type=resolved_type,
                machine=machine,
                frame_range=frame_range,
                expected_future_reads=expected_future_reads,
                is_solver_result=is_solver_result,
                is_independent_frames=is_independent_frames,
                data_class=data_class,
                policy=policy,
            )

        return run_on_main(_observe_and_decide_on_main, label="cache:_handle_assess_cache")
