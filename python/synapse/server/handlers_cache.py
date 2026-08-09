"""python/synapse/server/handlers_cache.py -- Mile 4 (Phase 1) + insert slice (Phase 2, buildable half), R-CACHE-1.

Wires the Phase 0 pure policy package (``synapse.cache_policy``) and passive host probe
(``host/cache_host_probe.py``) into two feature-flagged MCP tools:
  * ``synapse_assess_cache`` -- Phase 1, read-only advisor (the d6 cure / live caller);
  * ``synapse_insert_cache`` -- Phase 2 INSERTION ONLY, an undoable graph mutation.

Authorized scope: ruling R-CACHE-1 (docs/reviews/cache-adjudication-ruling.md, Joe/CTO,
2026-08-09) item 4 for assess; the insert slice is authorized by that ruling's Phase 2
"controlled insertion" clause + explicit team-lead delegation for the LOCAL build of the
one buildable Phase 2 piece. This handler + its TOOL_DEFS/bridge_adapter registration IS
the required live caller for both tools.

SCOPE (binding, this mile):
  * assess: read-only. Nothing in ``assess_cache_core``'s call graph creates a node, writes
    a file, or mutates the scene.
  * insert: an undoable GRAPH mutation ONLY -- create the File Cache SOP, wire it between the
    source and its downstream consumers, and SET (never write) its output-path parameter, all
    inside a single ``hou.undos.group``. It NEVER writes a byte to disk, NEVER cooks or saves
    the File Cache, and creates NO manifest. Phase 2's BAKE half (the disk write) is REJECTed
    at HEAD (adjudication e3: no cancel API for an in-flight cook on this build) and is NOT
    scaffolded here -- there is no ``synapse_bake_cache``, no manifest writer/reader, and no
    ``.cook()``/``.save()`` on the File Cache anywhere in this module.

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

import contextlib
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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


# --------------------------------------------------------------------------- issued-decision store (insert slice)

#: How long an issued ``synapse_assess_cache`` decision stays insertable before
#: ``synapse_insert_cache`` rejects it as ``expired``. Monotonic-clock based
#: (``time.monotonic()``), so it is immune to wall-clock adjustments. 15 minutes:
#: long enough for an artist to read an advice card and act on it, short enough that
#: a stale decision (scene edited, node deleted, upstream changed) is not silently
#: acted on. This is a per-call FRESHNESS guard, not the §12 upstream-signature
#: validity check (that is a Phase 2 bake concern, out of scope here).
INSERT_CACHE_DECISION_TTL_SECONDS = 900.0


class IssuedDecisionStore:
    """In-memory, process-lifetime record of decisions issued by
    ``synapse_assess_cache``, keyed by ``decision_id``. Mirrors
    ``host/cache_host_probe.LastObservationStore``'s shape and its posture exactly:
    NOT a new persistence authority (adjudication b12/d6 -- no new durable store is
    authorized in this wave), never written to disk, never survives the process.
    ``synapse_insert_cache`` consumes an entry here to turn a read-only recommendation
    into an authorized graph mutation; a durable version is a Memory-plane decision for
    a later mile.

    Recording is a pure dict write -- it does NOT make ``assess`` a mutation: assess
    still touches no scene and writes no disk.
    """

    def __init__(self) -> None:
        self._by_id: Dict[str, Dict[str, Any]] = {}

    def record(self, decision_id: str, entry: Dict[str, Any]) -> None:
        self._by_id[decision_id] = entry

    def lookup(self, decision_id: str) -> Optional[Dict[str, Any]]:
        return self._by_id.get(decision_id)


#: Process-lifetime issued-decision store shared by assess (writer) and insert
#: (reader). In-memory only (same posture as ``_LAST_OBSERVATION_STORE``).
_ISSUED_DECISION_STORE = IssuedDecisionStore()


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
    issued_decision_store: Optional[Any] = None,
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

    # Record the issued decision so synapse_insert_cache can consume it later
    # (insert slice, R-CACHE-1 Phase 2). PURE in-memory write -- assess stays
    # read-only (no disk, no scene mutation). Recorded for EVERY issued decision;
    # insert re-validates (freshness TTL + strategy-drift + supported context) and
    # rejects anything not insertable. Never changes assess's returned dict shape.
    store_issued = (
        issued_decision_store if issued_decision_store is not None
        else _ISSUED_DECISION_STORE
    )
    time_dependent_observed = None
    td_ev = observation.get("time_dependent")
    if isinstance(td_ev, dict):
        time_dependent_observed = td_ev.get("value")
    store_issued.record(decision.decision_id, {
        "strategy_id": strategy.strategy_id,
        "strategy_supported": strategy.supported,
        "decision": decision,
        "evidence_digest": decision.evidence_digest,
        "descriptor": descriptor,
        "node_path": resolved_node_path,
        "node_type": observation["node_type"],
        "frame_range": frame_range,
        "proposed_path": decision.proposed_path,
        "time_dependent_observed": time_dependent_observed,
        "issued_monotonic": time.monotonic(),
    })

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


# --------------------------------------------------------------------------- insert slice: boundary plan (server-side)

# Strategy_id -> deterministic File Cache SOP parameter plan. This map is the ONE place a
# strategy becomes concrete Houdini parm names/values -- it lives SERVER-SIDE, never in
# cache_policy (stdlib-only, must name no Houdini parms; blueprint §13.2 + strategies.py
# header). Only SOP strategies are supported this slice.
#
# Every parm name below was VERIFIED PRESENT on the live ``filecache`` SOP, H22.0.400
# (hython dir()/parmTemplate probe, 2026-08-09) -- NOT guessed from the blueprint's V0 list:
#   file          (String, "Geometry File")       -- the output path parameter
#   filemethod    (Menu,   "File Path")           -- constructed | EXPLICIT (author `file` directly)
#   filetype      (Menu,   "File Type")           -- token ".bgeo.sc" | ".vdb" (the dotted ext IS the token)
#   trange        (Menu,   "Evaluate As")         -- "off" (single) | "normal" (frame range)
#   timedependent (Toggle, "Time Dependent Cache")
#   cachesim      (Toggle, "Simulation")          -- ON = sequential state; OFF = frames independent
# ``savetodisk`` from the blueprint's V0 list is a PHANTOM on this build (absent) and is never
# emitted. Any parm absent at insert time is skipped defensively with a receipt warning, never
# a crash (File Cache parm names remain build-sensitive; probe-truth over pinned constants).

_FROM_OBSERVATION = object()  # sentinel: timedependent taken from stored observed evidence, not a constant

_INSERT_STRATEGY_PLAN: Dict[str, Dict[str, Any]] = {
    # SOP particle/mesh geometry: .bgeo.sc, Time Dependent per animated output, Simulation OFF.
    "sop_filecache_geometry_v1": {"filetype": ".bgeo.sc", "cachesim": 0, "timedependent": _FROM_OBSERVATION},
    # SOP solver/result: .bgeo.sc, Time Dependent ON, Simulation ON (sequential state).
    "sop_filecache_solver_result_v1": {"filetype": ".bgeo.sc", "cachesim": 1, "timedependent": 1},
    # Independent procedural frames: .bgeo.sc, Time Dependent ON, Simulation OFF (parallelizable).
    "sop_filecache_independent_frames_v1": {"filetype": ".bgeo.sc", "cachesim": 0, "timedependent": 1},
    # SOP VDB-only output: .vdb, Time Dependent per output.
    "sop_filecache_vdb_v1": {"filetype": ".vdb", "cachesim": 0, "timedependent": _FROM_OBSERVATION},
}

FILECACHE_NODE_TYPE = "filecache"  # verified present, H22.0.400 (probe 2026-08-09)


def resolve_boundary_plan(
    strategy_id: str,
    *,
    time_dependent_observed: Optional[bool] = None,
    frame_range: Optional[tuple] = None,
) -> Optional[Dict[str, Any]]:
    """Strategy_id -> a deterministic File Cache boundary plan (node type + ordered strategy
    parms). Returns ``None`` for any strategy_id without a supported SOP plan.

    DETERMINISM / no prose channel (gate test 3): this function's ONLY inputs are the
    registry-resolved ``strategy_id`` plus STRUCTURED stored evidence (observed time-dependence,
    frame range). It has NO free-text/explanation parameter -- an LLM-authored explanation cannot
    reach it, so it cannot alter the node type or the parm set. ``timedependent`` for the
    geometry/vdb strategies is "per animated output": taken from the stored OBSERVED
    time-dependence, and left at the node default when that was unmeasured (binding constraint
    #3: unmeasured is UNKNOWN, never a fabricated value).
    """
    spec = _INSERT_STRATEGY_PLAN.get(strategy_id)
    if spec is None:
        return None
    parms: List[Dict[str, Any]] = [
        {"name": "filetype", "value": spec["filetype"], "meaning": f"File Type = {spec['filetype']}"},
        {"name": "cachesim", "value": spec["cachesim"],
         "meaning": ("Simulation ON (sequential state)" if spec["cachesim"]
                     else "Simulation OFF (frames independent)")},
    ]
    td = spec["timedependent"]
    if td is _FROM_OBSERVATION:
        if time_dependent_observed is True:
            parms.append({"name": "timedependent", "value": 1,
                          "meaning": "Time Dependent ON (observed animated output)"})
        elif time_dependent_observed is False:
            parms.append({"name": "timedependent", "value": 0,
                          "meaning": "Time Dependent OFF (observed static output)"})
        else:
            parms.append({"name": "timedependent", "value": None, "set": False,
                          "meaning": "Time Dependent left at node default (time-dependence unmeasured)"})
    else:
        parms.append({"name": "timedependent", "value": td,
                      "meaning": "Time Dependent ON per strategy"})
    if frame_range is not None and len(frame_range) >= 2:
        start, end = frame_range[0], frame_range[1]
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            if end > start:
                parms.append({"name": "trange", "value": "normal", "meaning": "Evaluate As = Frame Range"})
            elif end == start:
                parms.append({"name": "trange", "value": "off", "meaning": "Evaluate As = Single Frame"})
    return {
        "node_type": FILECACHE_NODE_TYPE,
        "strategy_id": strategy_id,
        "format": spec["filetype"],
        "parms": parms,
    }


# --------------------------------------------------------------------------- insert slice: mutation core

_INSERT_RESPONSE_SCHEMA = "synapse.cache_insert_response/v1"

_INSERT_DISABLED_MESSAGE = (
    "Cache insertion is disabled (feature-flagged off by default).\n"
    "Set SYNAPSE_CACHE_ADVISOR_ENABLED=1 to enable synapse_insert_cache.\n"
    "No node was created and the scene was not modified."
)


def _insert_reject(decision_id: str, reason: str, detail: str) -> Dict[str, Any]:
    """Clean structured rejection -- NEVER a partial mutation. ``reason`` is a stable slug
    (mismatched | expired | strategy_drift | unsupported | source_missing); ``detail`` explains."""
    return {
        "schema": _INSERT_RESPONSE_SCHEMA,
        "status": "rejected",
        "reason": reason,
        "decision_id": decision_id,
        "message": detail,
    }


def _node_path(node: Any) -> str:
    try:
        return node.path()
    except Exception:
        return "unknown"


def _node_type_name(node: Any) -> str:
    try:
        return node.type().name()
    except Exception:
        return "unknown"


def _node_name(node: Any) -> str:
    try:
        return node.name()
    except Exception:
        p = _node_path(node)
        return p.rsplit("/", 1)[-1] if "/" in p else p


def _is_real_path(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != "" and value.strip().lower() != "unknown"


def _set_parm_defensive(node, name, value, meaning, parameter_summary, warnings):
    """Set one parm IF it exists on this build; otherwise record a skipped-absent entry +
    warning (never crash). File Cache parm names are build-sensitive -- a phantom name degrades
    to a warning, never a failure."""
    parm = None
    try:
        parm = node.parm(name)
    except Exception:
        parm = None
    if parm is None:
        parameter_summary.append({"name": name, "value": value, "applied": False,
                                  "reason": "parm_absent", "meaning": meaning})
        warnings.append(f"filecache parm {name!r} absent on this build -- skipped (not set)")
        return
    try:
        parm.set(value)
    except Exception as e:  # noqa: BLE001
        parameter_summary.append({"name": name, "value": value, "applied": False,
                                  "reason": f"set_raised:{type(e).__name__}", "meaning": meaning})
        warnings.append(f"filecache parm {name!r} .set({value!r}) raised {type(e).__name__}: {e}")
        return
    parameter_summary.append({"name": name, "value": value, "applied": True, "meaning": meaning})


def _render_insert_receipt_card(strategy_id, created_path, source_path, path_value,
                                parameter_summary, rewired, warnings) -> str:
    lines = [
        "CACHE BOUNDARY INSERTED (undoable -- one Ctrl+Z reverses it)",
        "",
        f"Strategy: {strategy_id}",
        f"Source:   {source_path}",
        f"Created:  {created_path}",
        f"Output path parameter (SET, not written): {path_value}",
    ]
    if rewired:
        lines.append("")
        lines.append("Downstream rewired to the cache node:")
        lines.extend(f"- {r['node']} (input {r['input_index']})" for r in rewired)
    applied = [p for p in parameter_summary if p.get("applied")]
    skipped = [p for p in parameter_summary if not p.get("applied")]
    if applied:
        lines.append("")
        lines.append("Parameters set:")
        lines.extend(f"- {p['name']} = {p['value']}  ({p['meaning']})" for p in applied)
    if skipped:
        lines.append("")
        lines.append("Parameters not set:")
        lines.extend(f"- {p['name']}: {p.get('reason', 'skipped')} ({p['meaning']})" for p in skipped)
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {w}" for w in warnings)
    lines.append("")
    lines.append("No bytes were written to disk. Baking the cache (writing frames) is a separate, "
                 "out-of-scope action; nothing here cooked or saved the File Cache.")
    return "\n".join(lines).rstrip() + "\n"


def insert_cache_core(
    *,
    decision_id: str,
    resolve_source_node: Callable[[], Any],
    store: Optional[Any] = None,
    explanation: Optional[str] = None,
    undo_context_factory: Optional[Callable[[], Any]] = None,
    cache_node_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Consume an issued ``synapse_assess_cache`` decision and insert+wire a File Cache SOP
    between the assessed source node and its downstream consumers, inside a single undo block.

    Contract (blueprint §13.3 + insert slice):
      * Rejects unknown/mismatched, expired (TTL), strategy-drifted, or unsupported decisions
        with a CLEAN structured error and ZERO mutation -- ``resolve_source_node`` is not even
        called on a rejection, so no node is touched.
      * The boundary plan (node type + parms) is derived DETERMINISTICALLY from the STORED
        decision's registry-resolved strategy via ``resolve_boundary_plan`` -- never from
        ``explanation`` (accepted for the receipt/audit trail only; it cannot alter the plan).
      * Sets the File Cache output-path PARAMETER (``file`` + ``filemethod=explicit``); NOTHING
        is written to disk and the node is NEVER cooked or saved.
      * Runs the create+wire+set inside ``undo_context_factory()`` (``hou.undos.group`` on the
        live path) so one Ctrl+Z reverses the whole op.

    ``resolve_source_node`` is a zero-arg callable so the live caller can marshal ``hou.node``
    onto the main thread; tests pass a fake-node factory. ``undo_context_factory`` returns a
    fresh context manager only on the go-path (no empty undo group is created on a rejection).
    """
    store = store if store is not None else _ISSUED_DECISION_STORE

    entry = store.lookup(decision_id)
    if entry is None:
        return _insert_reject(
            decision_id, "mismatched",
            f"decision_id {decision_id!r} is not in the issued-decision store -- it was never "
            "issued by synapse_assess_cache in this process, or belongs to a different session. "
            "Run synapse_assess_cache first and use the decision_id it returns.")

    age = time.monotonic() - entry.get("issued_monotonic", 0.0)
    if age > INSERT_CACHE_DECISION_TTL_SECONDS:
        return _insert_reject(
            decision_id, "expired",
            f"decision {decision_id} was issued {age:.0f}s ago, past the "
            f"{INSERT_CACHE_DECISION_TTL_SECONDS:.0f}s freshness window -- the scene may have "
            "changed. Re-run synapse_assess_cache for a fresh decision.")

    descriptor = entry.get("descriptor")
    stored_strategy_id = entry.get("strategy_id")
    strategy = resolve_strategy(descriptor)
    if strategy.strategy_id != stored_strategy_id:
        return _insert_reject(
            decision_id, "strategy_drift",
            f"strategy re-resolved to {strategy.strategy_id!r} but the issued decision was for "
            f"{stored_strategy_id!r} -- the strategy registry or node classification changed "
            "since assessment. Re-run synapse_assess_cache.")

    if not strategy.supported or strategy.strategy_id not in _INSERT_STRATEGY_PLAN:
        return _insert_reject(
            decision_id, "unsupported",
            f"strategy {strategy.strategy_id!r} has no supported File Cache insertion boundary in "
            "this slice (only SOP geometry / solver-result / independent-frames / VDB strategies "
            "are insertable). Refusing to guess a boundary.")

    plan = resolve_boundary_plan(
        strategy.strategy_id,
        time_dependent_observed=entry.get("time_dependent_observed"),
        frame_range=entry.get("frame_range"),
    )
    fmt = plan["format"]

    # --- go-path: resolve the source node (first hou touch) and mutate under undo ---
    node = resolve_source_node()
    if node is None:
        return _insert_reject(
            decision_id, "source_missing",
            f"source node {entry.get('node_path')!r} no longer exists -- it was deleted or renamed "
            "since assessment. Re-run synapse_assess_cache.")

    source_name = _node_name(node)
    proposed = entry.get("proposed_path")
    path_value = proposed if _is_real_path(proposed) else \
        f"$HIP/cache/{source_name}/{source_name}.$F4{fmt}"

    parameter_summary: List[Dict[str, Any]] = []
    warnings: List[str] = []
    ctx = undo_context_factory() if undo_context_factory is not None else contextlib.nullcontext()

    with ctx:
        parent = node.parent()
        # Capture downstream consumers BEFORE inserting, so we rewire exactly the old edges.
        downstream: List = []
        try:
            for c in node.outputConnections():
                downstream.append((c.outputNode(), c.inputIndex()))
        except Exception as e:  # noqa: BLE001
            warnings.append(f"outputConnections() read failed: {type(e).__name__}: {e}")

        name = cache_node_name or f"{source_name}_cache"
        cache_node = parent.createNode(plan["node_type"], name)
        cache_node.setInput(0, node)

        rewired: List[Dict[str, Any]] = []
        for dnode, in_idx in downstream:
            try:
                dnode.setInput(in_idx, cache_node, 0)
                rewired.append({"node": _node_path(dnode), "input_index": in_idx})
            except Exception as e:  # noqa: BLE001
                warnings.append(f"rewire of {_node_path(dnode)} input {in_idx} failed: "
                                f"{type(e).__name__}: {e}")

        try:
            cache_node.moveToGoodPosition()
        except Exception:
            pass

        # Path parameter: SET (never write). filemethod=explicit makes `file` authoritative.
        _set_parm_defensive(cache_node, "filemethod", "explicit",
                            "File Path = Explicit (author `file` directly)",
                            parameter_summary, warnings)
        _set_parm_defensive(cache_node, "file", path_value,
                            "Geometry File output path (SET only -- never written to disk)",
                            parameter_summary, warnings)

        # Strategy-derived parms (deterministic; explanation cannot reach these).
        for pm in plan["parms"]:
            if pm.get("set") is False or pm["value"] is None:
                parameter_summary.append({"name": pm["name"], "value": None, "applied": False,
                                          "reason": "unmeasured_left_default", "meaning": pm["meaning"]})
                continue
            _set_parm_defensive(cache_node, pm["name"], pm["value"], pm["meaning"],
                                parameter_summary, warnings)

        created_path = _node_path(cache_node)
        created_type = _node_type_name(cache_node)

    return {
        "schema": _INSERT_RESPONSE_SCHEMA,
        "status": "ok",
        "decision_id": decision_id,
        "evidence_digest": entry.get("evidence_digest"),
        "strategy_id": strategy.strategy_id,
        "source_node_path": entry.get("node_path"),
        "created_node_path": created_path,
        "node_type": created_type,
        "proposed_path": path_value,
        "path_written": False,      # invariant: insert NEVER writes to disk
        "cooked": False,            # invariant: the File Cache is never cooked/saved here
        "undo_group": "wrapped",    # create+wire+set ran inside one undo group (this fn owns it)
        "downstream_rewired": rewired,
        "parameter_summary": parameter_summary,
        "warnings": warnings,
        "explanation_recorded": explanation,  # kept for the receipt/audit; DID NOT affect the plan
        "reasoning": (
            f"Inserted a File Cache boundary ({strategy.strategy_id}) after {entry.get('node_path')} "
            f"and rewired {len(rewired)} downstream input(s); output-path parameter set to "
            f"{path_value} (not written)."
        ),
        "message": _render_insert_receipt_card(
            strategy.strategy_id, created_path, entry.get("node_path"),
            path_value, parameter_summary, rewired, warnings),
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

        node, resolved_path, resolved_type, hip_dir = run_on_main(_resolve_node_on_main)

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

        return run_on_main(_observe_and_decide_on_main)

    def _handle_insert_cache(self, payload: Dict) -> Dict:
        """synapse_insert_cache -- an undoable GRAPH mutation. Feature-flagged off by default
        (SYNAPSE_CACHE_ADVISOR_ENABLED, shared with assess). Consumes a ``decision_id`` issued by
        synapse_assess_cache and inserts+wires a File Cache SOP between the assessed source node
        and its downstream consumers, inside a single ``hou.undos.group`` (one Ctrl+Z reverses
        it). It SETS the output-path parameter but NEVER writes a byte to disk and NEVER cooks or
        saves the File Cache -- the bake half is out of scope (adjudication e3).

        Main-thread hygiene: the whole op runs in one ``run_on_main`` closure. The undo group is
        created via a factory inside ``insert_cache_core`` only on the go-path, so a rejection
        (mismatched/expired/strategy-drift/unsupported) creates no undo group and touches no node.
        """
        if not advisor_enabled():
            return {"status": "disabled", "message": _INSERT_DISABLED_MESSAGE}

        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()
        if not (CACHE_HOST_PROBE_AVAILABLE and CACHE_POLICY_AVAILABLE):
            raise RuntimeError(_DEPENDENCY_ERROR)

        decision_id = resolve_param(payload, "decision_id")
        # ``explanation`` is accepted for the receipt/audit trail ONLY -- it can never alter the
        # structured boundary plan (that is derived solely from the stored decision's strategy).
        explanation = resolve_param_with_default(payload, "explanation", None)

        store = _ISSUED_DECISION_STORE
        entry = store.lookup(decision_id)

        from .main_thread import run_on_main

        def _insert_on_main():
            def _resolve():
                node_path = entry.get("node_path") if entry else None
                return hou.node(node_path) if node_path else None  # type: ignore[union-attr]

            return insert_cache_core(
                decision_id=decision_id,
                resolve_source_node=_resolve,
                store=store,
                explanation=explanation,
                undo_context_factory=lambda: hou.undos.group("SYNAPSE insert_cache"),  # type: ignore[union-attr]
            )

        return run_on_main(_insert_on_main)
