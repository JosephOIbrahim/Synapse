"""
SYNAPSE Lossless Execution Bridge
The structural layer that enforces all 4 anchors.

Every agent operation passes through this bridge. Anchors are implemented HERE,
not in individual agents. Agents cannot bypass this layer.

Four structural safety anchors:
  - Undo Safety: every mutation in undo group
  - Thread Safety: all hou.* on main thread via hdefereval
  - Artist Consent: gate levels on destructive ops
  - Scene Integrity: USD composition validation

Elegant Revisions integrated:
  R1: Topological Hashing (cookCount + sessionId + geo intrinsics — H21 compatible)
  R2: Unbreakable async→sync boundary (hdefereval.executeInMainThreadWithResult)
  R4: Structural disk-write gate override (touches_disk → APPROVE)
  R7: Blast radius inference — auto-detect SOP→LOP bleed via dependency tracing
  R8: PDG async cook bridge — addEventHandler(raw_callable) + asyncio.Event for farm cooks (H21)
"""

from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
from enum import Enum
import asyncio
import hashlib
import json
import os
import threading
import time

from shared.types import AgentID, ExecutionResult
from shared.constants import (
    AGENT_CONTEXT_REQUIREMENTS,
    FIDELITY_DEGRADED,
    FIDELITY_PERFECT,
    GATE_POLL_INTERVAL,
    GATE_TIMEOUT_APPROVE,
    GATE_TIMEOUT_CRITICAL,
    HASH_LENGTH,
    OPERATION_GATES as _OPERATION_GATES_RAW,
    READ_ONLY_OPS,
    READ_ONLY_PREFIXES,
)

# ── Houdini Import Guard ────────────────────────────────────────
# Production: real hou + hdefereval inside Houdini
# Test/standalone: graceful fallback to synchronous execution

_HOU_AVAILABLE = False
try:
    import hou
    import hdefereval
    _HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore[assignment]
    hdefereval = None  # type: ignore[assignment]

# ── Gate System Import Guard ───────────────────────────────────
# Production: synapse.core.gates provides HumanGate with full proposal lifecycle
# Standalone/test: falls back to auto-approve or injected callback

_GATES_AVAILABLE = False
try:
    from synapse.core.gates import (
        HumanGate,
        GateDecision,
        GateLevel as CoreGateLevel,
    )
    from synapse.core.audit import AuditCategory
    _GATES_AVAILABLE = True
except ImportError:
    HumanGate = None  # type: ignore[assignment,misc]
    GateDecision = None  # type: ignore[assignment,misc]
    CoreGateLevel = None  # type: ignore[assignment,misc]
    AuditCategory = None  # type: ignore[assignment,misc]


# ── pxr Import Seam (Finding 4: composition validation) ────────
def _import_pxr_composition() -> tuple[Any, Any]:
    """Lazy pxr import for _verify_composition. Returns ``(Sdf, Usd)``;
    each is None when unavailable. pxr stays a call-time import (heavy,
    absent in standalone/CI). ``Sdf is not None`` preserves the original
    in-function ``_pxr_available`` semantics for the reference path.

    Module-level ON PURPOSE: tests exercise the pxr-available branches by
    monkeypatching this seam on the module — never via sys.modules (the
    fake-residency trap).
    """
    try:
        from pxr import Sdf
    except ImportError:
        return None, None
    try:
        from pxr import Usd
    except ImportError:
        Usd = None  # Sdf alone still enables the reference/payload checks
    return Sdf, Usd


# ── Anchor Evidence (Finding 1: no self-attested flags) ─────────
# The IntegrityBlock anchor flags were previously ASSIGNED True by the code
# path that intended them — never measured. These helpers derive them from
# evidence at execution time, so fidelity=1.0 means "verified", not "didn't
# throw". Both hou.undos evidence APIs (areEnabled, undoLabels) are
# live-verified members of hou.undos on H21.0.671.


def _on_main_thread() -> bool:
    """Thread Safety anchor evidence: is THIS frame executing on the process
    main thread?

    Module-level ON PURPOSE: tests that fake hdefereval and run the payload
    on an executor thread can monkeypatch ``bridge._on_main_thread`` to keep
    documenting production behavior. Production evidence stays real —
    hdefereval guarantees the main thread by construction, so the live value
    is True.
    """
    return threading.current_thread() is threading.main_thread()


def _topo_component(node_path: str | None) -> str | None:
    """Authored-change proxy for the undo-evidence rule (CTO decision
    2026-07-10): the TOPOLOGY component of the R1 hash ONLY — child count +
    child sessionIds (node create/delete evidence). Deliberately EXCLUDES
    cookCount and geometry intrinsics: those shift on NON-undoable events
    (a lazy cook the op triggered, a frame change) and are NOT evidence that
    anything was authored. Returns None when unavailable (no hou, missing
    node, API error) — callers treat None as "no evidence"."""
    if not _HOU_AVAILABLE or node_path is None:
        return None
    try:
        node = hou.node(node_path)
        if not node:
            return None
        children = node.children()
        return f"children:{len(children)}|" + "|".join(
            str(child.sessionId()) for child in children
        )
    except Exception:
        return None


def _topo_shifted(topo_before: str | None, hash_target: str | None) -> bool:
    """True only when BOTH topology snapshots exist and differ — missing
    evidence is never treated as a shift."""
    if topo_before is None:
        return False
    topo_after = _topo_component(hash_target)
    return topo_after is not None and topo_after != topo_before


def _undo_evidence_snapshot(
        hash_target: str | None = None) -> tuple[bool | None, int | None,
                                                 str | None]:
    """Undo Safety anchor evidence, part 1: snapshot BEFORE the undo group
    opens.

    Returns ``(enabled, depth_before, topo_before)``. enabled/depth are None
    when the evidence API is unavailable (fake hou modules in tests may lack
    areEnabled/undoLabels) — evidence-unavailable falls back to the
    pre-evidence behavior in
    :meth:`LosslessExecutionBridge._undo_group_evidence`. ``topo_before``
    (the authored-change proxy) is captured ONLY when undos are measured
    disabled — the sole case that consults it — so the healthy path pays no
    extra children scan.
    """
    enabled: bool | None = None
    depth_before: int | None = None
    try:
        are_enabled = getattr(hou.undos, "areEnabled", None)
        if are_enabled is not None:
            enabled = bool(are_enabled())
    except Exception:
        enabled = None
    try:
        undo_labels = getattr(hou.undos, "undoLabels", None)
        if undo_labels is not None:
            depth_before = len(undo_labels())
    except Exception:
        depth_before = None
    topo_before = _topo_component(hash_target) if enabled is False else None
    return enabled, depth_before, topo_before


# ── Scene-Hash Instrumentation (MEASURE-FIRST) ──────────────────
# The R1 stage-integrity hash runs stage.Flatten().ExportToString()+sha256 TWICE
# per stage-touching op (before + after) on the main thread. That cost scales with
# STAGE SIZE, not the mutation -- a real per-op floor on production Solaris stages
# that was UNMEASURED at scale. This module-level histogram times every
# _compute_scene_hash() call so the Flatten cost becomes visible in telemetry and a
# future tuning decision has real data. Same shape + bucket scheme as the
# main_thread_direct / dispatch_wait histograms (server/main_thread.py) so a one-line
# telemetry_dump pull surfaces it identically. Process-global (shared across bridge
# instances); thread-safe; zero-cost to read.
_SCENE_HASH_BUCKETS_MS = (1, 5, 10, 50, 100, 250, 500, 1000, 2000, 4000)
_scene_hash_lock = threading.Lock()
_scene_hash_metrics = {
    "count": 0,
    "sum_ms": 0.0,
    "max_ms": 0.0,
    "buckets": {b: 0 for b in _SCENE_HASH_BUCKETS_MS},
}


def _record_scene_hash_ms(ms: float) -> None:
    with _scene_hash_lock:
        _scene_hash_metrics["count"] += 1
        _scene_hash_metrics["sum_ms"] += ms
        if ms > _scene_hash_metrics["max_ms"]:
            _scene_hash_metrics["max_ms"] = ms
        for b in _SCENE_HASH_BUCKETS_MS:
            if ms <= b:
                _scene_hash_metrics["buckets"][b] += 1


def scene_hash_stats() -> dict:
    """Snapshot of the scene-hash (R1 stage-integrity) duration histogram in ms
    (copy -- safe to serialize). Key surface: ``scene_hash_ms`` cost, the Flatten
    floor on stage-touching ops. Mirrors main_thread_direct_stats()."""
    with _scene_hash_lock:
        return {
            "count": _scene_hash_metrics["count"],
            "sum_ms": _scene_hash_metrics["sum_ms"],
            "max_ms": _scene_hash_metrics["max_ms"],
            "buckets": dict(_scene_hash_metrics["buckets"]),
        }


def reset_scene_hash_stats() -> None:
    """Test/diagnostic helper -- zero the scene-hash histogram."""
    with _scene_hash_lock:
        _scene_hash_metrics["count"] = 0
        _scene_hash_metrics["sum_ms"] = 0.0
        _scene_hash_metrics["max_ms"] = 0.0
        for b in _SCENE_HASH_BUCKETS_MS:
            _scene_hash_metrics["buckets"][b] = 0


# ── Stage-Hash Size Gate (R1 cost control) ──────────────────────
# Below this prim count the stage hash stays the EXACT, byte-identical
# Flatten().ExportToString()+sha256 (zero behavior change for normal stages). ONLY
# above it do we switch to a cheaper-but-COMPLETE structural traversal signature
# that avoids the full USDA string serialization. Override via env at call time so
# operators (and tests) can tune it without a restart. Documented in
# docs/studio/DEPLOYMENT.md ('Stage-Hash Integrity Tuning').
# Structural stage-hash is OPT-IN, OFF by default. It is unproven at scale (can be
# SLOWER than Flatten on value-heavy stages) and carries a narrow time-sample-value
# completeness gap, so for an INTEGRITY primitive the default keeps the proven
# Flatten path on EVERY stage. Lower SYNAPSE_STAGE_HASH_PRIM_THRESHOLD (after reading
# the scene_hash_ms telemetry the hash wrapper now records) to opt in.
_DEFAULT_STAGE_HASH_PRIM_THRESHOLD = 1 << 62  # effectively unbounded => Flatten always
_STAGE_HASH_THRESHOLD_ENV = "SYNAPSE_STAGE_HASH_PRIM_THRESHOLD"


def _stage_hash_prim_threshold() -> int:
    """Prim-count gate above which the stage hash uses the structural signature
    instead of full Flatten()+ExportToString(). Env override; non-negative ints
    only, else the default (effectively unbounded => structural OFF / opt-in; a bad
    value never silently CHANGES the default)."""
    raw = os.environ.get(_STAGE_HASH_THRESHOLD_ENV)
    if raw:
        try:
            v = int(raw)
            if v >= 0:
                return v
        except (TypeError, ValueError):
            pass
    return _DEFAULT_STAGE_HASH_PRIM_THRESHOLD


# ── PDG Cook Timeout (R8-bounded) ───────────────────────────────
# Backstop against a PDG cook that fires NEITHER CookComplete NOR CookError
# (stuck work item, scheduler stall, a graph already cooking from another
# trigger). Without it, _execute_pdg_deferred's poll loop ran forever -- no
# IntegrityBlock finalized, the operation never returned. The general
# execute_async path has a 120s guard; the PDG path -- the longest op type --
# did not. 1800s is a backstop, not a target: real farm cooks run minutes-to-
# hours, so override per-op via the ``cook_timeout`` kwarg (seconds). cancelCook()
# is the same API EmergencyProtocol.trigger_emergency_halt uses -- H21-real.
DEFAULT_COOK_TIMEOUT_S: float = 1800.0


# ── Integrity Block ─────────────────────────────────────────────

@dataclass
class IntegrityBlock:
    """Appended to every ExecutionResult. Internal to SYNAPSE."""

    undo_group_active: bool = False
    main_thread_executed: bool = False
    consent_verified: bool = False
    composition_valid: bool = True

    agent_id: str = ""
    operation_type: str = ""
    timestamp: str = ""

    scene_hash_before: str = ""
    scene_hash_after: str = ""
    delta_hash: str = ""

    # H1 (multi-client hardening): the scene changed BETWEEN SYNAPSE ops —
    # the hash parked at the end of the previous op on this target differs
    # from this op's scene_hash_before. Attribution metadata ONLY: artists
    # legitimately edit between ops, so this is never a fidelity violation
    # (fidelity below is untouched). It stops foreign/artist edits from being
    # silently folded into SYNAPSE's integrity narrative.
    external_change_detected: bool = False

    # Path-qualified provenance (live-envelope, 2026-07). Defaults preserve
    # exact pre-existing "/mcp" semantics at every existing construction site.
    # *_applicable=False means "no such check EXISTS on this path" — the anchor
    # is N/A and recorded honestly as such, never faked True. The live
    # /synapse envelope (server/integrity_envelope.py) sets consent/
    # composition/undo not-applicable: no gate ran (D1 posture, pinned), no
    # composition validation ran, and inline undo-wrapping is only PARTIAL
    # across the live handlers (per-op verification is not scout-verifiable).
    execution_path: str = "mcp"          # "mcp" (bridge-enforced) | "live" (handler-envelope, observed)
    consent_applicable: bool = True      # False => no consent gate exists on this path — anchor N/A
    composition_applicable: bool = True  # False => no composition validation ran on this path — anchor N/A
    undo_applicable: bool = True         # False => undo wrapping not verified on this path — anchor N/A
    hash_target: str = ""                # what node path the topo hashes measured ("" = legacy/implicit)

    @property
    def anchors_hold(self) -> bool:
        # *_applicable flags gate the anchor set per execution path; defaults
        # (all True) reduce EXACTLY to the old four-way conjunction.
        # execution_path itself is pure metadata — never branched on.
        return (
            (self.undo_group_active or not self.undo_applicable)
            and self.main_thread_executed
            and (self.consent_verified or not self.consent_applicable)
            and (self.composition_valid or not self.composition_applicable)
        )

    @property
    def fidelity(self) -> float:
        """1.0 = pipeline functioning. <1.0 = pipeline bug."""
        if not self.anchors_hold:
            return 0.0
        if not self.delta_hash and self.operation_type not in READ_ONLY_OPS:
            return FIDELITY_DEGRADED
        return FIDELITY_PERFECT

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchors_hold": self.anchors_hold,
            "fidelity": self.fidelity,
            "undo": self.undo_group_active,
            "thread": self.main_thread_executed,
            "consent": self.consent_verified,
            "composition": self.composition_valid,
            "agent": self.agent_id,
            "operation": self.operation_type,
            "timestamp": self.timestamp,
            "scene_hash_before": self.scene_hash_before,
            "scene_hash_after": self.scene_hash_after,
            "delta_hash": self.delta_hash,
            "external_change_detected": self.external_change_detected,
            "execution_path": self.execution_path,
            "consent_applicable": self.consent_applicable,
            "composition_applicable": self.composition_applicable,
            "undo_applicable": self.undo_applicable,
            "hash_target": self.hash_target,
        }


# ── Gate Levels ─────────────────────────────────────────────────

class GateLevel(str, Enum):
    INFORM = "inform"
    REVIEW = "review"
    APPROVE = "approve"
    CRITICAL = "critical"


OPERATION_GATES: dict[str, GateLevel] = {
    op: GateLevel(level) for op, level in _OPERATION_GATES_RAW.items()
}


# ── Operation Descriptor ────────────────────────────────────────

@dataclass
class Operation:
    agent_id: AgentID
    operation_type: str
    summary: str
    fn: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    touches_stage: bool = False
    stage_path: str | None = None

    @property
    def gate_level(self) -> GateLevel:
        base = OPERATION_GATES.get(self.operation_type, GateLevel.REVIEW)
        # ── R4: Structural disk-write override ──
        # Disk writes elevate to at least APPROVE (never downgrades CRITICAL)
        if self.kwargs.get("touches_disk", False) and base not in (
            GateLevel.APPROVE, GateLevel.CRITICAL,
        ):
            return GateLevel.APPROVE
        return base

    @property
    def is_read_only(self) -> bool:
        return self.operation_type.startswith(READ_ONLY_PREFIXES)


# ── Lossless Execution Bridge ───────────────────────────────────

class LosslessExecutionBridge:
    """
    ALL agent operations pass through this bridge.
    Anchors are HERE, not in agents. No bypass path exists.
    """

    #: Default cap on the in-memory operation log. Bounds long-running session
    #: memory growth — older entries are dropped FIFO when the cap is exceeded.
    DEFAULT_LOG_MAX_SIZE: int = 1000

    def __init__(
        self,
        consent_callback: Callable[[Operation], bool] | None = None,
        log_max_size: int | None = None,
    ):
        # B1: bounded deque so long sessions don't leak unbounded memory.
        max_size = log_max_size if log_max_size is not None else self.DEFAULT_LOG_MAX_SIZE
        self._log_max_size: int = max_size
        self._operation_log: deque[IntegrityBlock] = deque(maxlen=max_size)
        self._anchor_violations: int = 0
        self._operations_total: int = 0
        self._operations_verified: int = 0
        # Pass 7: per-agent counters so the ConductorAdvisor can flag a
        # specific agent rather than the bridge as a whole. Lifetime totals
        # — survive operation log eviction.
        self._per_agent_total: dict[str, int] = {}
        self._per_agent_verified: dict[str, int] = {}
        # Live-envelope thread safety: record_external_block() is called from
        # the handlers' _log_executor threads concurrent with execute() on the
        # main thread. One lock guards the log deque + counter dicts at every
        # mutation/iteration site — behavior identical single-threaded.
        self._log_lock = threading.Lock()
        # H1 (multi-client hardening): last computed scene hash per hash_target,
        # parked at op end (after scene_hash_after / after rollback). Compared
        # against the NEXT op's scene_hash_before to attribute between-op
        # foreign/artist edits. Zero extra hashing — compares values already
        # computed by the integrity flow.
        self._parked_hash: dict[str, str] = {}
        # Undo-evidence warn-once (CTO constraint 4): inconclusive undo-stack
        # evidence emits at most ONE logging.warning per bridge instance —
        # never per op (a flat stack is routine at the undo memory cap).
        self._undo_evidence_warned: bool = False
        self._consent_callback = consent_callback
        self._gate = (
            HumanGate.get_instance()
            if _GATES_AVAILABLE and HumanGate
            else None
        )
        self._session_id = datetime.now().strftime("bridge_%Y%m%d_%H%M%S")

    # ── B2: Public read access to the operation log ──────────────
    # The operation log was previously a write-only sink. These accessors let
    # OBSERVER (and any future self-observability layer) read execution history
    # without reaching into private state. See pass-1 review for the missing
    # observability loop this enables.

    def recent_operations(self, n: int = 100) -> list[IntegrityBlock]:
        """Return the last *n* IntegrityBlocks (newest last). Caller-owned copy."""
        if n <= 0:
            return []
        with self._log_lock:
            log = list(self._operation_log)
        return log[-n:]

    def operation_stats(self) -> dict[str, Any]:
        """Aggregate execution statistics. Cheap O(N over current log)."""
        with self._log_lock:
            log = list(self._operation_log)
            per_op: dict[str, int] = {}
            for ib in log:
                per_op[ib.operation_type] = per_op.get(ib.operation_type, 0) + 1
            success_rate = (
                self._operations_verified / self._operations_total
                if self._operations_total > 0 else 0.0
            )
            # Pass 7: per-agent lifetime totals + success rates so the
            # ConductorAdvisor can flag a specific agent rather than the bridge
            # as a whole. These survive operation log eviction.
            per_agent_success_rate: dict[str, float] = {}
            for agent_key, total in self._per_agent_total.items():
                verified = self._per_agent_verified.get(agent_key, 0)
                per_agent_success_rate[agent_key] = (
                    verified / total if total > 0 else 0.0
                )
            return {
                "operations_total": self._operations_total,
                "operations_verified": self._operations_verified,
                "anchor_violations": self._anchor_violations,
                "success_rate": success_rate,
                "log_size": len(log),
                "log_capacity": self._log_max_size,
                "per_agent": dict(self._per_agent_total),
                "per_agent_verified": dict(self._per_agent_verified),
                "per_agent_success_rate": per_agent_success_rate,
                "per_operation_type": per_op,
                "session_id": self._session_id,
            }

    def clear_operation_log(self) -> int:
        """Clear the operation log. Returns the number of entries dropped."""
        with self._log_lock:
            n = len(self._operation_log)
            self._operation_log.clear()
        return n

    def record_external_block(self, integrity: IntegrityBlock) -> None:
        """Append an externally-produced IntegrityBlock (the live /synapse
        handler envelope) into this bridge's log + lifetime counters.
        Thread-safe — callers are the handlers' _log_executor threads,
        concurrent with execute() on the main thread. Mirrors _finalize's
        counting: fidelity == 1.0 -> verified, else anchor_violations."""
        with self._log_lock:
            self._operations_total += 1
            key = integrity.agent_id or ""
            self._per_agent_total[key] = self._per_agent_total.get(key, 0) + 1
            if integrity.fidelity >= FIDELITY_PERFECT:
                self._operations_verified += 1
                self._per_agent_verified[key] = (
                    self._per_agent_verified.get(key, 0) + 1
                )
            else:
                self._anchor_violations += 1
            self._operation_log.append(integrity)

    # ── R1: Cryptographic Topological Hashing ────────────────

    def _compute_scene_hash(self, target_node_path: str | None = "/obj",
                            include_stage: bool = True) -> str:
        """
        R1: Topological scene hashing via Houdini change-detection APIs.

        Timed wrapper around _compute_scene_hash_impl: every call records its
        wall-clock duration into the module ``scene_hash_ms`` histogram
        (scene_hash_stats()) so the stage-Flatten cost is visible in telemetry.
        The hash VALUE is identical to the un-timed implementation.

        ``include_stage=False`` is the live-envelope path: skip the S2 composed-
        stage hash entirely so the live /synapse path can NEVER hit
        stage.Flatten() (the Finding 3 floor), even on a LOP hash target.
        Forwarded ONLY when non-default so existing single-arg monkeypatched
        impl stubs (tests/test_scene_hash_gate.py) stay byte-identical.
        """
        _t0 = time.perf_counter()
        try:
            if include_stage:
                return self._compute_scene_hash_impl(target_node_path)
            return self._compute_scene_hash_impl(target_node_path,
                                                 include_stage=False)
        finally:
            _record_scene_hash_ms((time.perf_counter() - _t0) * 1000.0)

    def _compute_scene_hash_impl(self, target_node_path: str | None = "/obj",
                                 include_stage: bool = True) -> str:
        """
        R1: Topological scene hashing via Houdini change-detection APIs.

        H21 replaced several H20 APIs:
          H20 hou.updateGraphTick()    -> H21 node.cookCount() + child count
          H20 node.modificationCount() -> H21 node.cookCount()
          H20 geometry().dataId()      -> H21 geo intrinsics composite

        Falls back to timestamp-based hashing in standalone/test mode.
        """
        if not _HOU_AVAILABLE or target_node_path is None:
            return hashlib.sha256(
                datetime.now().isoformat().encode()
            ).hexdigest()[:HASH_LENGTH]

        node = hou.node(target_node_path)
        if not node:
            return "invalid_context"

        hash_data = []

        # Global topology: child count + session IDs capture create/delete/wire
        try:
            children = node.children()
            hash_data.append(f"children:{len(children)}")
            for child in children:
                hash_data.append(f"sid:{child.sessionId()}:{child.cookCount()}")
        except Exception:
            pass

        # Local: cookCount tracks parameter changes and recooks
        try:
            hash_data.append(f"cook:{node.cookCount()}")
        except Exception:
            pass

        # Geometry: intrinsics composite when geo exists
        try:
            geo = node.geometry()
            if geo:
                hash_data.append(f"pts:{geo.intrinsicValue('pointcount')}")
                hash_data.append(f"prims:{geo.intrinsicValue('primitivecount')}")
                hash_data.append(f"bounds:{geo.intrinsicValue('bounds')}")
        except Exception:
            pass

        # S2 (Solaris/LOP): hash the COMPOSED stage content, not just cookCount.
        # node.geometry() is None for LOPs, so the geometry block above is skipped;
        # without this the hash collapses to "did the node recook" and cannot detect
        # that the composed stage CHANGED — blind on the headline Solaris path.
        # Flatten-export verified stable + attribute-value-sensitive on H21.0.631.
        # Size-gated: below the prim threshold this is byte-identical to the old
        # Flatten()+sha256; above it, a cheaper COMPLETE structural signature.
        # include_stage=False (live envelope) skips this block structurally.
        try:
            if include_stage and hasattr(node, "stage"):
                stage = node.stage()
                if stage is not None:
                    hash_data.append("stage:" + self._hash_stage_signature(stage))
        except Exception:
            pass  # graceful — never let one missing API kill the hash

        if not hash_data:
            return hashlib.sha256(
                datetime.now().isoformat().encode()
            ).hexdigest()[:HASH_LENGTH]

        return hashlib.sha256(
            "|".join(str(x) for x in hash_data).encode("utf-8")
        ).hexdigest()[:HASH_LENGTH]

    # ── R1 stage hash: size-gated complete signature ──────────

    def _hash_stage_signature(self, stage) -> str:
        """Hash a composed USD stage. Returns the 16-hex digest appended after the
        ``stage:`` prefix in the scene hash.

        SIZE GATE (cost control, INTEGRITY-PRESERVING):
          - At/below the prim threshold: the EXACT original
            ``sha256(stage.Flatten().ExportToString())[:HASH_LENGTH]`` — byte-identical,
            zero behavior change for normal stages.
          - Above the threshold: a cheaper-but-COMPLETE structural signature that
            avoids the full USDA string serialization (see
            _structural_stage_signature).

        Conservative by construction: the size-probe and the structural path each
        fall back to the proven Flatten path on ANY error, so the gate can only ever
        make the hash *cheaper*, never *blinder* than before.
        """
        try:
            large = self._stage_exceeds(stage, _stage_hash_prim_threshold())
        except Exception:
            large = False  # probe failed → behave exactly like before (Flatten)

        if large:
            try:
                return self._structural_stage_signature(stage)
            except Exception:
                # Structural path failed → fall back to the proven Flatten algorithm
                # rather than dropping the stage hash (under-capture is a defect).
                pass

        flat = stage.Flatten().ExportToString()
        return hashlib.sha256(flat.encode("utf-8")).hexdigest()[:HASH_LENGTH]

    @staticmethod
    def _stage_exceeds(stage, threshold: int) -> bool:
        """True if the stage has MORE than ``threshold`` prims. Short-circuits at
        threshold+1 so the probe is bounded even on huge stages. Uses TraverseAll()
        (inactive/abstract prims included) so the gate decision is conservative."""
        n = 0
        for _ in stage.TraverseAll():
            n += 1
            if n > threshold:
                return True
        return False

    @staticmethod
    def _structural_stage_signature(stage) -> str:
        """Complete-but-cheaper structural signature for LARGE stages — avoids the
        full Flatten().ExportToString() USDA serialization while still changing on
        EVERY mutation class:

          prim add/remove/rename ...... path set + per-prim path
          type change ................. typeName
          specifier change (def/over/class) ... specifier
          activation .................. IsActive() (TraverseAll keeps inactive prims)
          attribute add/remove ........ sorted authored property names
          attribute VALUE change ...... per-attr value repr + value-type + per-time-sample
                                         values (animated attrs: every authored frame)
          visibility .................. authored as the ``visibility`` attribute → above
          metadata / composition arc .. authored metadata dict + explicit arc flags +
                                         variant set names & selections

        Over-captures by design: when in doubt a signal is INCLUDED. Under-capture
        would let an integrity check silently PASS on a real mutation, which is the
        one failure this gate must never introduce. Incremental hashing keeps memory
        flat regardless of stage size. Per-prim failures degrade to a path-bound
        marker — one bad prim never erases the rest of the signature.
        """
        h = hashlib.sha256()
        # TraverseAll() visits inactive/abstract prims too, so deactivating a prim
        # flips a captured IsActive() flag instead of vanishing without a trace.
        for prim in stage.TraverseAll():
            try:
                parts = [
                    prim.GetPath().pathString,        # add/remove/rename
                    str(prim.GetTypeName()),          # type change
                    str(prim.GetSpecifier()),         # def / over / class
                    "1" if prim.IsActive() else "0",  # activation
                ]
                # Authored property NAMES — attribute/relationship add/remove.
                try:
                    parts.append(",".join(sorted(prim.GetAuthoredPropertyNames())))
                except Exception:
                    parts.append("?props")
                # Per-attribute VALUE digest — value change, value-type change,
                # time-sample add/remove. visibility lands here too.
                #
                # TIME-SAMPLE COMPLETENESS (gap closure): the old form captured only
                # the DEFAULT-time value (`attr.Get()`) plus the sample COUNT. An edit
                # at a NON-default time (the common case on animated Solaris stages —
                # a keyframe value change at frame != 0) left the signature unchanged
                # while the count stayed the same → a real mutation the gate silently
                # passed. That gap is the reason structural was unsafe as a DEFAULT.
                #
                # Now: for an animated attr (GetNumTimeSamples() > 0) digest EVERY
                # authored time-sample value via GetTimeSamples() + Get(t) — so a
                # non-default-time value edit flips the signature. For a STATIC attr
                # the form is byte-identical to before (`:0={Get()!r}`) — the closure
                # costs nothing on the static stages where structural is the perf win.
                # GetTimeSamples()/Get(t) are dir()-confirmed in the H21.0.671 symbol
                # table; Get() / GetNumTimeSamples() are already used in production.
                for attr in prim.GetAuthoredAttributes():
                    try:
                        n_samples = attr.GetNumTimeSamples()
                        if n_samples and n_samples > 0:
                            sample_vals = [
                                f"{t}={attr.Get(t)!r}" for t in attr.GetTimeSamples()
                            ]
                            parts.append(
                                f"{attr.GetName()}:{attr.GetTypeName()}"
                                f":{n_samples}=" + "|".join(sample_vals)
                            )
                        else:
                            parts.append(
                                f"{attr.GetName()}:{attr.GetTypeName()}"
                                f":0={attr.Get()!r}"
                            )
                    except Exception:
                        parts.append(f"{attr.GetName()}=<err>")
                # Per-relationship TARGET digest — a relationship RETARGET (material
                # rebind, light-linking/collection membership) leaves the property
                # NAME and metadata unchanged, so without the targets the signature
                # is blind to it (Flatten is not). Targets are paths (cheap, bounded),
                # not arrays, so this over-capture adds no array-serialization cost.
                for rel in prim.GetAuthoredRelationships():
                    try:
                        parts.append(
                            f"REL:{rel.GetName()}="
                            + ",".join(t.pathString for t in rel.GetTargets())
                        )
                    except Exception:
                        parts.append(f"REL:{rel.GetName()}=<err>")
                # Authored metadata — covers most composition arcs + misc metadata.
                try:
                    meta = prim.GetAllAuthoredMetadata()
                    for k in sorted(meta):
                        parts.append(f"@{k}={meta[k]!r}")
                except Exception:
                    pass
                # Explicit composition-arc presence + variant selections
                # (belt-and-suspenders over the metadata dict).
                try:
                    parts.append(
                        "arc:"
                        + ("r" if prim.HasAuthoredReferences() else "")
                        + ("p" if prim.HasAuthoredPayloads() else "")
                        + ("i" if prim.HasAuthoredInherits() else "")
                        + ("s" if prim.HasAuthoredSpecializes() else "")
                    )
                    vsets = prim.GetVariantSets()
                    for vs in sorted(vsets.GetNames()):
                        parts.append(f"vset:{vs}={vsets.GetVariantSelection(vs)}")
                except Exception:
                    pass
                line = "|".join(parts)
            except Exception:
                # Never let one prim kill the signature; still bind something unique.
                try:
                    line = "ERRPRIM:" + prim.GetPath().pathString
                except Exception:
                    line = "ERRPRIM:?"
            h.update(line.encode("utf-8"))
            h.update(b"\n")
        return h.hexdigest()[:HASH_LENGTH]

    # ── R7: Blast Radius Inference ─────────────────────────────

    def _infer_stage_touch(self, operation: Operation) -> bool:
        """
        R7: Never trust the LLM's boundary flags. Compute the blast radius.

        Traces the dependency graph forward from the operation's target node
        to detect if a SOP mutation bleeds into Solaris via any downstream
        LOP node. If it does, auto-sets touches_stage=True and stage_path
        to the first affected LOP -- ensuring the Scene Integrity anchor
        fires even when the agent didn't flag it.
        """
        if operation.touches_stage:
            return True

        node_path = (operation.kwargs.get("node_path")
                     or operation.kwargs.get("parent_path"))
        if not node_path or not _HOU_AVAILABLE:
            return False

        node = hou.node(node_path)
        if not node:
            return False

        # Trace graph forward recursively (max depth 3): does this SOP feed into any LOP?
        try:
            visited = set()

            def _trace(n, depth=0):
                if depth > 3 or n.path() in visited:
                    return False
                visited.add(n.path())
                # S3: SOP→LOP data flow is BOTH param refs (dependents() — e.g. a
                # sopimport's soppath) AND wires (outputs() — a SOP chain feeding
                # the SOP the LOP imports). dependents() alone misses
                # box→(wire)→blast→(soppath)→sopimport. Verified live on H21.0.631:
                # box.dependents()==[] but box.outputs()==[blast],
                # blast.dependents()==[sopimport].
                for dep in list(n.dependents()) + list(n.outputs()):
                    if isinstance(dep, hou.LopNode):
                        operation.touches_stage = True
                        operation.stage_path = dep.path()
                        return True
                    if _trace(dep, depth + 1):
                        return True
                return False

            return _trace(node)
        except Exception:
            pass

        return False

    # ── H1/H2: Multi-Client Hardening ──────────────────────────
    # Foreign clients (fxhoudinimcp) marshal via hdefereval too, so foreign
    # work cannot interleave INSIDE a SYNAPSE op — the real exposures are
    # between-op attribution (H1) and the empty-group rollback edge where
    # performUndo() pops a foreign/artist block when fn raised before
    # mutating (H2). See docs/MCP_COEXISTENCE.md.

    @staticmethod
    def _is_sentinel_hash(scene_hash: str) -> bool:
        """True when a scene hash is not a real topology digest: empty (never
        computed), the no-node marker, or the no-hou timestamp fallback —
        a timestamp hash ALWAYS differs and would false-alarm any comparison."""
        return (not scene_hash) or scene_hash == "invalid_context" or not _HOU_AVAILABLE

    def _note_external_change(self, integrity: IntegrityBlock,
                              hash_target: str) -> None:
        """H1: between-op attribution. If the hash parked at the end of the
        last op on this target differs from THIS op's scene_hash_before, the
        scene changed between SYNAPSE ops (artist or another MCP client).
        Informational only — auto-reverting the foreign edit would revert the
        artist (indistinguishable), so attribution is the correct posture."""
        parked = self._parked_hash.get(hash_target)
        if (
            parked is not None
            and not self._is_sentinel_hash(parked)
            and not self._is_sentinel_hash(integrity.scene_hash_before)
            and parked != integrity.scene_hash_before
        ):
            integrity.external_change_detected = True

    def _park_hash(self, hash_target: str, scene_hash: str) -> None:
        """H1: park the last computed hash for this target at op end."""
        self._parked_hash[hash_target] = scene_hash

    def _guarded_rollback(self, integrity: IntegrityBlock,
                          hash_target: str) -> str | None:
        """H2: hash-guarded rollback shared by the sync (_execute_houdini) and
        async (_sync_payload) exception paths — previously near-duplicate
        unconditional performUndo() sites.

        Uses ONLY hashes already in production use (undo-stack label
        inspection is rejected: `hou.undos` member APIs are not in the
        introspected symbol table, so not scout-verifiable):

          1. Scene hash unchanged since scene_hash_before → fn raised before
             mutating. performUndo() would pop the artist's or a foreign
             client's most recent block (the CTO-review empty-group edge) —
             SKIP the undo, delta_hash = "no_mutation_no_rollback".
          2. Changed → performUndo() once, then re-hash. Still differs from
             scene_hash_before → delta_hash = "rollback_incomplete" and an
             attribution note is returned — honest surfacing instead of a
             false "rolled_back" claim.
          3. Sentinel hashes (see _is_sentinel_hash) disable the guard
             conservatively: unconditional single performUndo(), exactly the
             pre-H2 behavior, and never a false "rollback_incomplete" alarm.

        Returns an attribution note to append to the error message, or None.
        """
        before = integrity.scene_hash_before
        try:
            h_now = self._compute_scene_hash(hash_target)
        except Exception:
            h_now = "invalid_context"

        if self._is_sentinel_hash(before) or self._is_sentinel_hash(h_now):
            try:
                hou.undos.performUndo()
            except Exception:
                pass
            integrity.delta_hash = "rolled_back"
            self._park_hash(hash_target, h_now)
            return None

        if h_now == before:
            integrity.delta_hash = "no_mutation_no_rollback"
            self._park_hash(hash_target, h_now)
            return None

        try:
            hou.undos.performUndo()
        except Exception:
            pass
        try:
            h_post = self._compute_scene_hash(hash_target)
        except Exception:
            h_post = "invalid_context"
        self._park_hash(hash_target, h_post)
        if not self._is_sentinel_hash(h_post) and h_post != before:
            integrity.delta_hash = "rollback_incomplete"
            return (
                f"rollback incomplete on {hash_target}: the scene hash still "
                "differs from the pre-op state — concurrent scene changes "
                "(another MCP client or the artist) may have interfered; "
                f"manual review of {hash_target} recommended"
            )
        integrity.delta_hash = "rolled_back"
        return None

    def _undo_group_evidence(self, enabled: bool | None,
                             depth_before: int | None,
                             topo_before: str | None, delta_hash: str,
                             hash_target: str | None) -> bool:
        """Undo Safety anchor evidence, part 2: decide ``undo_group_active``
        AFTER the undo group has CLOSED (the caller exits the with-block
        first).

        PINNED SEMANTICS (CTO decision 2026-07-10 — zero false violations):

          - A scene-hash delta is NEVER, by itself, mutation evidence: the R1
            hash digests cookCount + geo intrinsics, which shift on
            NON-undoable events (a lazy cook the op triggered, a frame
            change). The only authored-change proxy is the topology component
            (:func:`_topo_component` — child sessionIds).
          - ``hou.undos.areEnabled()`` False AND the topology component
            shifted → False: an authored structural change provably had no
            undo protection. This is the ONLY violation verdict this
            evidence can return.
          - ``areEnabled()`` False with NO authored-change evidence → True:
            nothing needed undo protection — the anchor ("every MUTATION
            wrapped") is vacuously satisfied. Reads and cook-only deltas
            under a ``hou.undos.disabler()`` scope or a zeroed undo memory
            cap must not fail.
          - Undo-stack depth (undoLabels) is corroborating ONLY: the stack
            legitimately stays flat for captured mutations (eviction at
            ``hou.undos.memoryUsageLimit``), so flat depth + a changed hash
            is INCONCLUSIVE — keep True and emit at most ONE warning per
            bridge instance (``self._undo_evidence_warned``), then stop
            scanning the stack.
          - Evidence unavailable (fake hou without areEnabled/undoLabels,
            standalone) → True: the with-statement having been entered and
            exited without raising IS the wrap evidence (the pre-evidence
            behavior, pinned) — inconclusive, so it shares the one warning.
        """
        if enabled is False:
            if _topo_shifted(topo_before, hash_target):
                import logging
                logging.getLogger("synapse.bridge").warning(
                    "Undo anchor evidence: undos are DISABLED and the node "
                    "topology of %s changed — the authored mutation had no "
                    "undo protection.", hash_target,
                )
                return False
            return True
        # enabled True (or unknown): NEVER a hard violation — undo-stack
        # eviction and cook-visible deltas would false-flag. Flat/missing
        # depth on a changed scene is worth exactly one warning per bridge.
        if self._undo_evidence_warned or delta_hash in ("", "no_change"):
            return True
        depth_after: int | None = None
        try:
            undo_labels = getattr(hou.undos, "undoLabels", None)
            if undo_labels is not None:
                depth_after = len(undo_labels())
        except Exception:
            depth_after = None
        import logging
        if depth_before is None or depth_after is None:
            self._undo_evidence_warned = True
            logging.getLogger("synapse.bridge").warning(
                "Undo anchor evidence INCONCLUSIVE: the scene changed "
                "(delta=%s) but the undo-stack evidence APIs are "
                "unavailable — keeping the anchor (entered-and-exited wrap "
                "is the only evidence). Warning once per bridge instance.",
                delta_hash,
            )
        elif depth_after <= depth_before:
            self._undo_evidence_warned = True
            logging.getLogger("synapse.bridge").warning(
                "Undo anchor evidence INCONCLUSIVE: the scene changed "
                "(delta=%s) but the undo stack did not grow (%s -> %s). "
                "Expected for non-undoable deltas (a cook the op triggered, "
                "a frame change) and for eviction at the undo memory limit "
                "— keeping the anchor. Warning once per bridge instance.",
                delta_hash, depth_before, depth_after,
            )
        return True

    # ── Synchronous Execute (test / direct main-thread) ──────

    def execute(self, operation: Operation) -> ExecutionResult:
        """Synchronous path. For async MCP server, use execute_async()."""
        agent_key = operation.agent_id.value if operation.agent_id else ""
        with self._log_lock:
            self._operations_total += 1
            self._per_agent_total[agent_key] = self._per_agent_total.get(agent_key, 0) + 1

        integrity = IntegrityBlock(
            agent_id=operation.agent_id.value,
            operation_type=operation.operation_type,
            timestamp=datetime.now().isoformat(),
        )

        consent_ok = self._check_consent(operation)
        integrity.consent_verified = consent_ok
        if not consent_ok:
            return self._fail_with_integrity(
                integrity,
                f"Operation requires {operation.gate_level.value} consent",
                "consent_required",
            )

        # ── R7: Infer blast radius before execution ─────────
        self._infer_stage_touch(operation)

        hash_target = operation.stage_path or "/obj"

        if _HOU_AVAILABLE:
            return self._execute_houdini(operation, integrity, hash_target)
        else:
            return self._execute_direct(operation, integrity, hash_target)

    def _execute_direct(self, operation: Operation, integrity: IntegrityBlock,
                        hash_target: str) -> ExecutionResult:
        """Test path: direct execution without Houdini."""
        integrity.main_thread_executed = True
        integrity.undo_group_active = True

        try:
            integrity.scene_hash_before = self._compute_scene_hash(hash_target)
            result = operation.fn(*operation.args, **operation.kwargs)
            integrity.scene_hash_after = self._compute_scene_hash(hash_target)

            if integrity.scene_hash_before != integrity.scene_hash_after:
                integrity.delta_hash = hashlib.sha256(
                    f"{integrity.scene_hash_before}:{integrity.scene_hash_after}".encode()
                ).hexdigest()[:HASH_LENGTH]
            else:
                integrity.delta_hash = "no_change"

        except Exception as e:
            integrity.delta_hash = "rolled_back"
            return self._fail_with_integrity(integrity, str(e), "execution_error")

        return self._finalize(operation, integrity, result)

    def _execute_houdini(self, operation: Operation, integrity: IntegrityBlock,
                         hash_target: str) -> ExecutionResult:
        """Production path: undo-wrapped execution on Houdini main thread."""
        # Anchor flags from EVIDENCE, not self-attestation (Finding 1).
        integrity.main_thread_executed = _on_main_thread()
        # Provisional: the exception path keeps the entered-wrap presumption;
        # the success path refines this from undo-stack evidence after the
        # group closes below.
        integrity.undo_group_active = True

        undo_enabled: bool | None = None
        undo_topo_before: str | None = None
        try:
            integrity.scene_hash_before = self._compute_scene_hash(hash_target)
            self._note_external_change(integrity, hash_target)  # H1

            undo_enabled, undo_depth_before, undo_topo_before = (
                _undo_evidence_snapshot(hash_target)
            )
            with hou.undos.group(f"SYNAPSE: {operation.summary}"):
                result = operation.fn(*operation.args, **operation.kwargs)

                integrity.scene_hash_after = self._compute_scene_hash(hash_target)
                self._park_hash(hash_target, integrity.scene_hash_after)  # H1

                if integrity.scene_hash_before != integrity.scene_hash_after:
                    integrity.delta_hash = hashlib.sha256(
                        f"{integrity.scene_hash_before}:{integrity.scene_hash_after}".encode()
                    ).hexdigest()[:HASH_LENGTH]
                else:
                    integrity.delta_hash = "no_change"

                # ── ANCHOR: Scene Integrity ─────────────────
                if operation.touches_stage and operation.stage_path:
                    if not self._verify_composition(operation.stage_path):
                        # S1 fix (verified live H21.0.671): do NOT performUndo()
                        # inside the still-open undo group — H21 raises "Cannot
                        # undo within an undo group", which masks this error and
                        # leaves the real reason invisible to the caller. Let the
                        # raise close the group; the outer `except` performs the
                        # single rollback.
                        raise RuntimeError(
                            f"USD Composition violation on {operation.stage_path}"
                        )

            # Group CLOSED — capture undo-stack evidence (Finding 1).
            integrity.undo_group_active = self._undo_group_evidence(
                undo_enabled, undo_depth_before, undo_topo_before,
                integrity.delta_hash, hash_target,
            )
            return self._finalize(operation, integrity, result)

        except Exception as e:
            note = self._guarded_rollback(integrity, hash_target)  # H2
            # F-E: evidence in hand overrides the entered-wrap presumption —
            # undos were measured DISABLED before the group opened AND an
            # authored structural change is still on the scene (the no-op
            # rollback could not restore it): the trail must not claim the
            # mutation was undo-protected. Same pinned semantics as
            # _undo_group_evidence; presumption stands when evidence is
            # absent.
            if undo_enabled is False and _topo_shifted(undo_topo_before,
                                                       hash_target):
                integrity.undo_group_active = False
            msg = f"{e} [{note}]" if note else str(e)
            return self._fail_with_integrity(integrity, msg, "execution_error")

    # ── R2: Async Execute (FastMCP server path) ──────────────

    async def execute_async(self, operation: Operation) -> ExecutionResult:
        """
        R2: The unbreakable async-to-sync execution boundary.

        Called from FastMCP async event loop. Dispatches the synchronous
        Houdini payload to main thread via hdefereval without blocking
        the MCP server. All anchors enforced inside the closure.
        """
        agent_key = operation.agent_id.value if operation.agent_id else ""
        with self._log_lock:
            self._operations_total += 1
            self._per_agent_total[agent_key] = self._per_agent_total.get(agent_key, 0) + 1

        integrity = IntegrityBlock(
            agent_id=operation.agent_id.value,
            operation_type=operation.operation_type,
            timestamp=datetime.now().isoformat(),
        )

        consent_ok = await self._check_consent_async(operation)
        integrity.consent_verified = consent_ok
        if not consent_ok:
            return self._fail_with_integrity(
                integrity,
                f"Operation requires {operation.gate_level.value} consent",
                "consent_required",
            )

        # ── R7: Infer blast radius before execution ─────────
        self._infer_stage_touch(operation)

        hash_target = operation.stage_path or "/obj"

        if not _HOU_AVAILABLE:
            return self._execute_direct(operation, integrity, hash_target)

        # ── R8: PDG operations use deferred cook path ────────
        if operation.operation_type == "cook_pdg_chain":
            return await self._execute_pdg_deferred(operation, integrity)

        # ── The Synchronous Payload Closure ──────────────────
        def _sync_payload() -> ExecutionResult:
            # Anchor flags from EVIDENCE, not self-attestation (Finding 1;
            # parity with _execute_houdini).
            integrity.main_thread_executed = _on_main_thread()
            # Provisional: the exception path keeps the entered-wrap
            # presumption; the success path refines this from undo-stack
            # evidence after the group closes below.
            integrity.undo_group_active = True
            integrity.scene_hash_before = self._compute_scene_hash(hash_target)
            self._note_external_change(integrity, hash_target)  # H1

            undo_enabled: bool | None = None
            undo_topo_before: str | None = None
            try:
                undo_enabled, undo_depth_before, undo_topo_before = (
                    _undo_evidence_snapshot(hash_target)
                )
                with hou.undos.group(f"SYNAPSE: {operation.summary}"):
                    result = operation.fn(*operation.args, **operation.kwargs)

                    integrity.scene_hash_after = self._compute_scene_hash(hash_target)
                    self._park_hash(hash_target, integrity.scene_hash_after)  # H1

                    if integrity.scene_hash_before != integrity.scene_hash_after:
                        integrity.delta_hash = hashlib.sha256(
                            f"{integrity.scene_hash_before}:{integrity.scene_hash_after}".encode()
                        ).hexdigest()[:HASH_LENGTH]
                    else:
                        integrity.delta_hash = "no_change"

                    if operation.touches_stage and operation.stage_path:
                        if not self._verify_composition(operation.stage_path):
                            # S1 fix (parity with _execute_houdini, verified live
                            # H21.0.671): no inner performUndo — it raises "Cannot
                            # undo within an undo group" and masks this error. The
                            # outer `except` performs the single rollback.
                            raise RuntimeError("USD Composition violation detected.")

                # Group CLOSED — capture undo-stack evidence (Finding 1).
                integrity.undo_group_active = self._undo_group_evidence(
                    undo_enabled, undo_depth_before, undo_topo_before,
                    integrity.delta_hash, hash_target,
                )
                return self._finalize(operation, integrity, result)

            except Exception as e:
                note = self._guarded_rollback(integrity, hash_target)  # H2
                # F-E parity with _execute_houdini: measured-disabled undos +
                # an authored structural change still on the scene → the
                # recorded block must not claim undo protection.
                if undo_enabled is False and _topo_shifted(undo_topo_before,
                                                           hash_target):
                    integrity.undo_group_active = False
                msg = f"{e} [{note}]" if note else str(e)
                return self._fail_with_integrity(integrity, msg, "execution_error")

        # ── Dispatch to main thread without blocking FastMCP ──
        # Timeout prevents indefinite hang if Houdini main thread stalls.
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: hdefereval.executeInMainThreadWithResult(_sync_payload)
                ),
                timeout=120.0,
            )
        except asyncio.TimeoutError:
            integrity.delta_hash = "timeout"
            return self._fail_with_integrity(
                integrity,
                "Houdini main thread did not respond within 120s — "
                "the scene may be unresponsive or a heavy cook is blocking",
                "execution_timeout",
            )

    # ── R8: PDG Async Cook Bridge ──────────────────────────

    async def _execute_pdg_deferred(self, operation: Operation,
                                     integrity: IntegrityBlock) -> ExecutionResult:
        """
        R8: Safely bridges PDG asynchronous cooks with FastMCP async loops.

        H21 moved PDG events from hou.pdgEventType to the standalone pdg module.
        Cook events register a RAW callable via pdg.GraphContext.addEventHandler
        (which returns the wrapper to pass to removeEventHandler) — NOT the
        phantom pdg.PyEventHandler(fn) constructor — instead of hou
        TopNode.addEventCallback (which handles hou.nodeEventType).

        On failure: dirties the generated tasks so they recook. Cache files on
        disk are PRESERVED by default — a blanket remove_files delete is
        non-granular and unsafe on shared farm storage. On-disk removal is
        opt-in per operation via the ``remove_generated_files`` kwarg
        (single-user local scratch), never the default.
        """
        if not _HOU_AVAILABLE:
            # Test/standalone fallback: simulate successful cook — keeps the
            # _execute_direct posture (both anchors asserted, no hou).
            integrity.main_thread_executed = True
            integrity.undo_group_active = True
            integrity.delta_hash = "pdg_test_cook"
            return self._finalize(operation, integrity, {"pdg": "test_cook_ok"})

        # F1 parity — no self-attested anchors on the PDG path:
        #   undo: PDG cooks are NOT undo-wrapped (failure recovery is
        #   dirtyAllTasks, not hou.undos) — recorded honestly as
        #   not-applicable, never faked True (same N/A semantics as the live
        #   envelope, server/integrity_envelope.py).
        #   main thread: measured (_on_main_thread) inside the hdefereval-
        #   marshalled frame that triggers the graph cook — the scene-
        #   mutating call on this path — not asserted by this coroutine
        #   (which runs on the FastMCP loop/executor thread).
        integrity.undo_applicable = False
        integrity.undo_group_active = False

        node_path = operation.kwargs.get("node_path")
        if not node_path:
            return self._fail_with_integrity(
                integrity, "cook_pdg_chain requires node_path kwarg", "missing_context"
            )

        integrity.scene_hash_before = self._compute_scene_hash(node_path)

        top_node = hou.node(node_path)
        if not top_node:
            return self._fail_with_integrity(
                integrity, f"TOP node not found: {node_path}", "invalid_node"
            )

        # R8 threading fix: asyncio.Event is NOT thread-safe. PDG callbacks
        # fire on Houdini's main thread while await runs in the FastMCP async
        # loop. Use threading.Event and poll it from the async loop.
        import threading as _threading
        cook_complete = _threading.Event()
        cook_success = [False]
        cook_error = [""]

        # H21: PDG events live in the standalone pdg module
        try:
            import pdg as _pdg
        except ImportError:
            _pdg = None

        if _pdg is None:
            return self._fail_with_integrity(
                integrity, "pdg module not available", "missing_dependency"
            )

        # Get the PDG graph context from the TOP node
        graph_context = top_node.getPDGGraphContext()
        if not graph_context:
            return self._fail_with_integrity(
                integrity, f"No PDG graph context on {node_path}", "invalid_node"
            )

        handlers = []
        timed_out = False
        try:
            # H21.0.671: pdg.PyEventHandler(fn) is a PHANTOM constructor
            # ("TypeError: No constructor defined"). The live idiom is
            # graph_context.addEventHandler(raw_callable, EventType) — it
            # REGISTERS the callable AND RETURNS the wrapper object, which
            # we keep so we can removeEventHandler() it later. One call per
            # event type → one wrapper per type. The callback fires on
            # Houdini's main thread; threading.Event.set() is thread-safe.
            def on_cook_event(event):
                if timed_out:
                    return  # late event after timeout/cancel -- don't overwrite
                if event.type == _pdg.EventType.CookComplete:
                    cook_success[0] = True
                    cook_complete.set()
                elif event.type == _pdg.EventType.CookError:
                    cook_success[0] = False
                    cook_error[0] = event.message if event.message else "Unknown PDG error"
                    cook_complete.set()

            handlers.append(
                graph_context.addEventHandler(on_cook_event, _pdg.EventType.CookComplete)
            )
            handlers.append(
                graph_context.addEventHandler(on_cook_event, _pdg.EventType.CookError)
            )

            # Trigger cook on main thread — wrap in try/except so exceptions
            # don't silently vanish in the fire-and-forget dispatch.
            def _exec_graph_safe():
                # Thread anchor evidence (F1 parity): measured in the frame
                # hdefereval marshals — True in production by construction.
                # Stays False (honest) if the main thread never ran this.
                integrity.main_thread_executed = _on_main_thread()
                try:
                    top_node.executeGraph()
                except Exception as e:
                    cook_error[0] = str(e)
                    cook_complete.set()

            hdefereval.executeInMainThread(_exec_graph_safe)

            # Poll the threading.Event from the async loop so FastMCP stays
            # responsive. 250ms poll interval matches gate polling cadence.
            # BOUNDED (R8): a stuck cook that fires neither CookComplete nor
            # CookError used to poll here FOREVER -- no IntegrityBlock finalized,
            # the operation never returned. The general execute_async path has a
            # 120s guard; the PDG path -- the longest op type -- did not. Bound
            # it by cook_timeout (default DEFAULT_COOK_TIMEOUT_S; override via the
            # kwarg, seconds). On expiry, cancel the cook on the main thread and
            # fall through to the dirty+fail path with a distinct delta_hash.
            # cancelCook() is the same API EmergencyProtocol uses -- H21-real.
            cook_timeout = float(
                operation.kwargs.get("cook_timeout", DEFAULT_COOK_TIMEOUT_S)
            )
            deadline = time.monotonic() + cook_timeout
            while not cook_complete.is_set():
                if time.monotonic() >= deadline:
                    timed_out = True
                    break
                await asyncio.sleep(0.25)

            if timed_out:
                try:
                    hdefereval.executeInMainThread(
                        lambda: graph_context.cancelCook()
                    )
                except Exception:
                    pass
                cook_error[0] = (
                    f"PDG cook timed out after {cook_timeout:.0f}s on "
                    f"{node_path} -- cancelled. The cook fired neither "
                    "CookComplete nor CookError (stuck work item, scheduler "
                    "stall, or a graph already cooking from another trigger)."
                )

        except Exception as e:
            return self._fail_with_integrity(
                integrity, f"PDG callback error: {e}", "pdg_error"
            )
        finally:
            for _handler in handlers:
                try:
                    graph_context.removeEventHandler(_handler)
                except Exception:
                    pass

        if not cook_success[0]:
            # Rollback: dirty the generated tasks so they recook. By DEFAULT the
            # cache files on disk are PRESERVED — a blanket remove_files=True wipe
            # is non-granular and unsafe on shared farm storage (deletes work other
            # nodes/artists may still depend on). On-disk removal is opt-in per
            # operation (single-user local scratch), never the default.
            remove_files = bool(operation.kwargs.get("remove_generated_files", False))
            try:
                hdefereval.executeInMainThread(
                    lambda: top_node.dirtyAllTasks(remove_files=remove_files)
                )
            except Exception:
                pass
            integrity.delta_hash = "pdg_timeout" if timed_out else "pdg_rolled_back"
            disposition = "removed from disk" if remove_files else "preserved on disk"
            return self._fail_with_integrity(
                integrity,
                f"PDG cook failed on farm. Generated caches {disposition}. {cook_error[0]}",
                "pdg_error",
            )

        integrity.scene_hash_after = self._compute_scene_hash(node_path)
        integrity.delta_hash = hashlib.sha256(
            f"{integrity.scene_hash_before}:{integrity.scene_hash_after}".encode()
        ).hexdigest()[:HASH_LENGTH]

        return self._finalize(operation, integrity, {
            "pdg": "cook_complete",
            "node": node_path,
        })

    # ── Shared Finalization ──────────────────────────────────

    def _finalize(self, operation: Operation, integrity: IntegrityBlock,
                  result: Any) -> ExecutionResult:
        fidelity = integrity.fidelity
        if fidelity < FIDELITY_PERFECT:
            with self._log_lock:
                self._anchor_violations += 1
            return self._fail_with_integrity(
                integrity, f"Integrity check failed: fidelity={fidelity}",
                "integrity_violation",
            )

        agent_key = operation.agent_id.value if operation.agent_id else ""
        with self._log_lock:
            self._operations_verified += 1
            self._per_agent_verified[agent_key] = (
                self._per_agent_verified.get(agent_key, 0) + 1
            )
            self._operation_log.append(integrity)

        if isinstance(result, ExecutionResult):
            return result.with_integrity(integrity)
        return ExecutionResult(
            success=True, result=result,
            agent_id=operation.agent_id, integrity=integrity,
        )

    def _check_consent(self, operation: Operation) -> bool:
        gate = operation.gate_level
        if gate == GateLevel.INFORM:
            return True

        # Path 1: Full gate system available (production inside Synapse)
        if self._gate is not None:
            return self._check_consent_gate(operation)

        # Path 2: Injected callback (MCP server or custom integration)
        if self._consent_callback is not None:
            return self._consent_callback(operation)

        # Path 3: Standalone/test -- auto-approve (preserves existing behavior)
        return True

    def _propose_gate(self, operation: Operation):
        """Create the HumanGate proposal for an operation (shared by the sync and
        async consent paths)."""
        return self._gate.propose(
            operation=operation.operation_type,
            description=operation.summary,
            sequence_id=self._session_id,
            category=AuditCategory.PIPELINE,
            level=CoreGateLevel(operation.gate_level.value),
            proposed_changes=operation.kwargs,
            agent_id=operation.agent_id.value if operation.agent_id else "",
            reasoning=f"Bridge gate: {operation.operation_type}",
        )

    def _check_consent_gate(self, operation: Operation) -> bool:
        """Route consent through HumanGate (SYNC path, used by execute())."""
        proposal = self._propose_gate(operation)

        # REVIEW: proposal logged to batch, allow execution to continue
        if operation.gate_level == GateLevel.REVIEW:
            return proposal.decision != GateDecision.REJECTED

        # APPROVE: must wait for explicit artist decision
        if operation.gate_level == GateLevel.APPROVE:
            return self._wait_for_decision(proposal, timeout=GATE_TIMEOUT_APPROVE)

        # CRITICAL: same as APPROVE but longer timeout
        if operation.gate_level == GateLevel.CRITICAL:
            return self._wait_for_decision(proposal, timeout=GATE_TIMEOUT_CRITICAL)

        return True

    # ── INT-1: async consent path — the FastMCP event loop must not block ──
    async def _check_consent_async(self, operation: Operation) -> bool:
        """Async consent check for execute_async. Same policy as _check_consent,
        but APPROVE/CRITICAL waits use `await asyncio.sleep` so a pending decision
        never stalls the FastMCP event loop (INT-1; the sync path's blocking
        time.sleep was the S4 defect). INFORM / callback / standalone are already
        non-blocking and reuse the same outcomes."""
        gate = operation.gate_level
        if gate == GateLevel.INFORM:
            return True
        if self._gate is not None:
            return await self._check_consent_gate_async(operation)
        if self._consent_callback is not None:
            return self._consent_callback(operation)
        return True

    async def _check_consent_gate_async(self, operation: Operation) -> bool:
        """Async mirror of _check_consent_gate — non-blocking APPROVE/CRITICAL wait."""
        proposal = self._propose_gate(operation)

        if operation.gate_level == GateLevel.REVIEW:
            return proposal.decision != GateDecision.REJECTED
        if operation.gate_level == GateLevel.APPROVE:
            return await self._wait_for_decision_async(
                proposal, timeout=GATE_TIMEOUT_APPROVE)
        if operation.gate_level == GateLevel.CRITICAL:
            return await self._wait_for_decision_async(
                proposal, timeout=GATE_TIMEOUT_CRITICAL)
        return True

    def _wait_for_decision(self, proposal, timeout: float = GATE_TIMEOUT_APPROVE) -> bool:
        """Poll for artist decision on APPROVE/CRITICAL-level proposals."""
        import time as _time
        deadline = _time.monotonic() + timeout
        while _time.monotonic() < deadline:
            if proposal.decision != GateDecision.PENDING:
                return proposal.decision in (
                    GateDecision.APPROVED,
                    GateDecision.MODIFIED,
                )
            _time.sleep(GATE_POLL_INTERVAL)
        # Timeout -- treat as rejection (safe default)
        return False

    async def _wait_for_decision_async(self, proposal, timeout: float = GATE_TIMEOUT_APPROVE) -> bool:
        """INT-1: async mirror of _wait_for_decision. Polls with `await asyncio.sleep`
        so a pending APPROVE/CRITICAL decision does not stall the FastMCP event loop
        (the sync version's blocking time.sleep was the S4 defect). Mirrors the PDG
        path's await-based poll cadence."""
        import time as _time
        deadline = _time.monotonic() + timeout
        while _time.monotonic() < deadline:
            if proposal.decision != GateDecision.PENDING:
                return proposal.decision in (
                    GateDecision.APPROVED,
                    GateDecision.MODIFIED,
                )
            await asyncio.sleep(GATE_POLL_INTERVAL)
        # Timeout -- treat as rejection (safe default)
        return False

    def _verify_composition(self, stage_path: str) -> bool:
        if not _HOU_AVAILABLE:
            return True
        try:
            node = hou.node(stage_path)
            if not node or not hasattr(node, 'stage'):
                return True
            stage = node.stage()
            if not stage:
                return True

            Sdf, Usd = _import_pxr_composition()
            _pxr_available = Sdf is not None

            # F-H cost control: the inherit/specialize sweep adds two
            # composed-metadata queries per prim plus (on the PCQ fallback
            # path) a PrimCompositionQuery per inheriting prim — main-thread
            # time inside the open undo group, scaling with stage size. Gate
            # it behind the SAME operator-tunable prim threshold as the
            # stage hash: at the default (unbounded) no probe runs and the
            # sweep is always on; lowering
            # SYNAPSE_STAGE_HASH_PRIM_THRESHOLD for hash cost also sheds
            # this sweep on stages above it (advisory skip, debug note).
            class_arcs_enabled = Usd is not None
            if class_arcs_enabled:
                threshold = _stage_hash_prim_threshold()
                if threshold < _DEFAULT_STAGE_HASH_PRIM_THRESHOLD:
                    try:
                        if self._stage_exceeds(stage, threshold):
                            class_arcs_enabled = False
                            import logging
                            logging.getLogger("synapse.bridge").debug(
                                "stage exceeds %d prims -- skipping the "
                                "inherit/specialize sweep on %s (size gate)",
                                threshold, stage_path)
                    except Exception:
                        pass  # probe failure never disables validation

            for prim in stage.Traverse():
                if not prim.IsValid():
                    self._log_composition_failure(
                        stage_path, prim.GetPath(), "prim is invalid")
                    return False
                if not prim.IsActive():
                    continue

                if prim.HasAuthoredReferences() and _pxr_available:
                    # GetAddedOrExplicitItems is live-verified on
                    # Usd.References (H21.0.671) — called unguarded so a
                    # broken References API keeps failing CLOSED through the
                    # outer except (pre-Finding-4 reference outcome preserved).
                    if not self._check_arc_items(
                            stage_path, prim, prim.GetReferences(), Sdf,
                            kind="reference"):
                        return False

                if prim.HasAuthoredPayloads() and _pxr_available:
                    payloads_api = prim.GetPayloads()
                    # GetAddedOrExplicitItems is verified only on References;
                    # on Usd.Payloads it is hasattr-guarded — an absent
                    # optional API skips the sub-check (debug), it is NOT an
                    # exception path and never a hard fail (INT-3 untouched).
                    if hasattr(payloads_api, "GetAddedOrExplicitItems"):
                        if not self._check_arc_items(
                                stage_path, prim, payloads_api, Sdf,
                                kind="payload"):
                            return False
                    else:
                        import logging
                        logging.getLogger("synapse.bridge").debug(
                            "Usd.Payloads.GetAddedOrExplicitItems absent -- "
                            "skipping payload item checks at %s",
                            prim.GetPath())

                if class_arcs_enabled:
                    has_inherits = prim.HasAuthoredInherits()
                    has_specializes = prim.HasAuthoredSpecializes()
                else:
                    has_inherits = has_specializes = False

                if has_inherits or has_specializes:
                    # PrimCompositionQuery statics accept only genuine
                    # Usd.Prim objects (Boost.Python rejects anything else
                    # with an ArgumentError). A non-Usd.Prim traverser
                    # (fake/mock stages in tests) is API-inapplicability,
                    # NOT an exception path — debug-skip, never fail-closed.
                    usd_prim_cls = getattr(Usd, "Prim", None)
                    if usd_prim_cls is not None and not isinstance(
                            prim, usd_prim_cls):
                        import logging
                        logging.getLogger("synapse.bridge").debug(
                            "prim at %s is not a Usd.Prim -- skipping "
                            "inherit/specialize checks", prim.GetPath())
                        has_inherits = has_specializes = False

                if has_inherits:
                    # F-H fast path: read the inherits LIST OP (items are
                    # target paths) — a self-target is detectable WITHOUT
                    # constructing a Usd.PrimCompositionQuery per inheriting
                    # prim (prim-index walk + per-arc allocation). Attr-
                    # guarded; absent APIs fall back to the PCQ static.
                    handled, ok = self._check_class_listop_self_target(
                        stage_path, prim, "GetInherits", kind="inherit")
                    if handled:
                        if not ok:
                            return False
                    else:
                        # GetDirectInherits is a live-verified static
                        # (H21.0.671). Self-cycle is the ONLY hard failure —
                        # inheriting a nonexistent class prim is LEGAL USD
                        # (composes to nothing).
                        query = Usd.PrimCompositionQuery.GetDirectInherits(prim)
                        if not self._check_class_arc_cycles(
                                stage_path, prim, query, kind="inherit"):
                            return False

                if has_specializes:
                    # F-H fast path (same as inherits above).
                    handled, ok = self._check_class_listop_self_target(
                        stage_path, prim, "GetSpecializes", kind="specialize")
                    if handled:
                        if not ok:
                            return False
                    else:
                        # No live-verified PrimCompositionQuery static exists
                        # for specializes (H21.0.671) — fully hasattr-guarded;
                        # an absent optional API skips with a debug note,
                        # never a hard fail.
                        pcq = getattr(Usd, "PrimCompositionQuery", None)
                        get_specializes = getattr(
                            pcq, "GetDirectSpecializes", None
                        ) if pcq is not None else None
                        if get_specializes is not None:
                            if not self._check_class_arc_cycles(
                                    stage_path, prim, get_specializes(prim),
                                    kind="specialize"):
                                return False
                        else:
                            import logging
                            logging.getLogger("synapse.bridge").debug(
                                "PrimCompositionQuery.GetDirectSpecializes "
                                "absent -- skipping specializes check at %s",
                                prim.GetPath())

                # Variants: deliberately OUT OF SCOPE of hard validation — a
                # selection naming a missing variant composes to nothing by
                # design (legal USD flexibility).
            return True
        except Exception as exc:
            import logging
            logging.getLogger("synapse.bridge").warning(
                "Composition validation FAILED-CLOSED on %s: %s: %s",
                stage_path, type(exc).__name__, exc,
            )
            # INT-3 (v4 §4a fail-closed): a validation that could not COMPLETE must
            # report failure, not success. Returning True here would mark the stage
            # composition_valid (fidelity=1.0) having validated nothing. An
            # un-verifiable composition is treated as invalid → rollback.
            return False

    def _check_arc_items(self, stage_path: str, prim, items_api, Sdf,
                         kind: str) -> bool:
        """Shared hard checks for listed composition arcs (references,
        payloads). Extracted from the original reference loop (Finding 4).

        (1) Self-cycle — an INTERNAL arc (empty assetPath) whose primPath is
        the prim itself. An external arc targeting the same prim path in a
        DIFFERENT layer (``payload = @cache.usda@</World/A>`` authored on
        /World/A — the standard export-then-payload-back round-trip) is
        LEGAL composition, not a cycle (F-C).

        (2) Unresolvable assetPath — hard fail for references (pre-Finding-4
        outcome preserved); ADVISORY for payloads (F-G): authored payload
        paths are commonly anchored-relative ('./payload.usdc') and resolve
        against the INTRODUCING layer, which this raw-path registry lookup
        cannot reproduce (it resolves against CWD) — a miss is not evidence
        of a broken stage. No FindOrOpen for payloads either: payloads are
        commonly unloaded, and opening from disk per stage-touching op on
        the main thread inside the open undo group (handle dropped at loop
        end) is a latency tax the check must not impose."""
        prim_path = str(prim.GetPath())
        cycle_word = "referencing" if kind == "reference" else kind
        for item in items_api.GetAddedOrExplicitItems():
            # Cycle detection: an INTERNAL arc (no assetPath) targeting the
            # prim itself. With an assetPath the target lives in another
            # layer — same-path targeting there is legal (F-C).
            item_prim_path = str(item.primPath) if item.primPath else ""
            if item_prim_path == prim_path and not item.assetPath:
                self._log_composition_failure(
                    stage_path, prim.GetPath(),
                    f"self-{cycle_word} cycle: {prim_path}")
                return False
            # Validate targeted layers resolve
            if item.assetPath:
                if kind == "payload":
                    # Advisory only (see docstring) — never a hard fail.
                    if Sdf.Layer.Find(str(item.assetPath)) is None:
                        import logging
                        logging.getLogger("synapse.bridge").debug(
                            "payload asset not in the layer registry by raw "
                            "path (advisory — relative paths anchor to the "
                            "introducing layer): %s at %s",
                            item.assetPath, prim.GetPath())
                    continue
                resolved = Sdf.Layer.Find(str(item.assetPath))
                if resolved is None:
                    resolved = Sdf.Layer.FindOrOpen(str(item.assetPath))
                if resolved is None:
                    self._log_composition_failure(
                        stage_path, prim.GetPath(),
                        f"unresolvable {kind}: {item.assetPath}")
                    return False
        return True

    def _check_class_listop_self_target(self, stage_path: str, prim,
                                        accessor: str,
                                        kind: str) -> tuple[bool, bool]:
        """F-H fast path for the class-arc self-cycle check: read the
        inherit/specialize LIST OP directly — items are target paths, so a
        self-target is readable WITHOUT constructing a
        Usd.PrimCompositionQuery (the per-inheriting-prim cost on
        class-based pipelines). ``GetInherits``/``GetSpecializes`` are
        live-verified members of Usd.Prim on H21.0.671;
        ``GetAddedOrExplicitItems`` on their return objects is NOT (verified
        on Usd.References only) — both lookups are attr-guarded, and an
        absent API returns ``handled=False`` so the caller falls back to the
        PCQ path. Returns ``(handled, ok)``."""
        api_getter = getattr(prim, accessor, None)
        if api_getter is None:
            return False, True
        try:
            items_fn = getattr(api_getter(), "GetAddedOrExplicitItems", None)
        except Exception:
            return False, True
        if items_fn is None:
            return False, True
        prim_path = str(prim.GetPath())
        for target in items_fn():
            if str(target) == prim_path:
                self._log_composition_failure(
                    stage_path, prim.GetPath(),
                    f"self-{kind} cycle: {prim_path}")
                return True, False
        return True, True

    def _check_class_arc_cycles(self, stage_path: str, prim, query,
                                kind: str) -> bool:
        """Hard-fail ONLY on a self-cycle (an arc targeting the prim
        itself). An inherit/specialize to a nonexistent class prim is
        LEGAL USD — it composes to nothing by design and is never failed
        here (Finding 4, conservative broadening)."""
        prim_path = str(prim.GetPath())
        for arc in query.GetCompositionArcs():
            if str(arc.GetTargetPrimPath()) == prim_path:
                self._log_composition_failure(
                    stage_path, prim.GetPath(),
                    f"self-{kind} cycle: {prim_path}")
                return False
        return True

    def _log_composition_failure(self, stage_path: str, prim_path, reason: str) -> None:
        import logging
        logger = logging.getLogger("synapse.bridge")
        logger.warning(
            "Composition validation failed on %s at %s: %s",
            stage_path, prim_path, reason,
        )

    def _fail_with_integrity(self, integrity: IntegrityBlock,
                             error: str, error_type: str) -> ExecutionResult:
        with self._log_lock:
            self._operation_log.append(integrity)
        result = ExecutionResult.fail(
            error=error, error_type=error_type,
            agent_id=AgentID(integrity.agent_id) if integrity.agent_id else None,
        )
        return result.with_integrity(integrity)

    # ── Session Reporting ────────────────────────────────────

    @property
    def session_fidelity(self) -> float:
        if self._operations_total == 0:
            return 1.0
        ratio = self._operations_verified / self._operations_total
        penalty = 0.0 if self._anchor_violations == 0 else 1.0
        return ratio * (1.0 - penalty)

    def session_report(self) -> dict:
        return {
            "operations_total": self._operations_total,
            "operations_verified": self._operations_verified,
            "anchor_violations": self._anchor_violations,
            "session_fidelity": self.session_fidelity,
            "operation_log_length": len(self._operation_log),
            "houdini_available": _HOU_AVAILABLE,
        }

    def reconstruct_operation_history(self) -> list[dict]:
        with self._log_lock:
            log = list(self._operation_log)
        return [b.to_dict() for b in log]


# ── Process-Wide Bridge Singleton ────────────────────────────────
# One LosslessExecutionBridge per process — the shared §16 operation trail.
# Rationale: agent_health._find_bridge_instance() gc-scans for *any* instance,
# so a second in-process instance would make the §16 read nondeterministic.
# Both writers share this one object: the panel/in-process-MCP adapter
# (panel/bridge_adapter.get_bridge) and the live /synapse envelope
# (server/integrity_envelope.record_live_block).
#
# PANEL POSTURE BY CONSTRUCTION (ordering landmine): the default __init__
# wires HumanGate.get_instance() as the gate. If the live envelope created
# the instance first with that default, panel CRITICAL ops (execute_python)
# would later route through HumanGate's blocking poll on the GUI thread —
# the documented "make a box" freeze (bridge_adapter._panel_consent). So the
# singleton is ALWAYS constructed gate-less with an auto-approve callback,
# regardless of which caller creates it first; the panel adapter re-points
# the callback to _panel_consent on first panel use.

_process_bridge: LosslessExecutionBridge | None = None
_process_bridge_lock = threading.Lock()


def get_process_bridge() -> LosslessExecutionBridge:
    """Get or lazily create the process-wide LosslessExecutionBridge."""
    global _process_bridge
    with _process_bridge_lock:
        if _process_bridge is None:
            bridge = LosslessExecutionBridge(consent_callback=lambda op: True)
            bridge._gate = None  # never the blocking HumanGate poll (see above)
            _process_bridge = bridge
        return _process_bridge


def reset_process_bridge() -> None:
    """Test helper — drop the process-wide singleton."""
    global _process_bridge
    with _process_bridge_lock:
        _process_bridge = None


# ── Agent Handoff ────────────────────────────────────────────────

@dataclass
class AgentHandoff:
    from_agent: AgentID
    to_agent: AgentID
    task_id: str
    source_output: ExecutionResult
    source_fidelity: float
    context: dict = field(default_factory=dict)
    guidance: str = ""
    provenance: list[tuple[str, str]] = field(default_factory=list)

    def verify(self) -> bool:
        if self.source_fidelity < FIDELITY_PERFECT:
            return False
        if not self.source_output.success:
            return False
        required = AGENT_CONTEXT_REQUIREMENTS.get(self.to_agent, set())
        return required.issubset(self.context.keys())

    def extend_provenance(self, agent_id: AgentID, summary: str) -> None:
        self.provenance.append((agent_id.value, summary))


# ── Emergency Halt ────────────────────────────────────────────────

class EmergencyProtocol:
    """Pipeline emergency halt. Immediate stop, no gradual wind-down."""

    @staticmethod
    def trigger_emergency_halt(bridge: LosslessExecutionBridge, reason: str) -> dict:
        report = bridge.session_report()
        report["emergency_reason"] = reason
        report["emergency_timestamp"] = datetime.now().isoformat()
        report["action"] = "ALL_OPERATIONS_HALTED"
        if _HOU_AVAILABLE:
            try:
                for node in hou.node("/obj").allSubChildren():
                    if hasattr(node, 'getPDGGraphContext'):
                        ctx = node.getPDGGraphContext()
                        if ctx:
                            ctx.cancelCook()
            except Exception:
                pass
        return report
