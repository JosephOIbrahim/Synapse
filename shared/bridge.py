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

    @property
    def anchors_hold(self) -> bool:
        return all([
            self.undo_group_active,
            self.main_thread_executed,
            self.consent_verified,
            self.composition_valid,
        ])

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
        # H1 (multi-client hardening): last computed scene hash per hash_target,
        # parked at op end (after scene_hash_after / after rollback). Compared
        # against the NEXT op's scene_hash_before to attribute between-op
        # foreign/artist edits. Zero extra hashing — compares values already
        # computed by the integrity flow.
        self._parked_hash: dict[str, str] = {}
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
        log = list(self._operation_log)
        return log[-n:]

    def operation_stats(self) -> dict[str, Any]:
        """Aggregate execution statistics. Cheap O(N over current log)."""
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
        n = len(self._operation_log)
        self._operation_log.clear()
        return n

    # ── R1: Cryptographic Topological Hashing ────────────────

    def _compute_scene_hash(self, target_node_path: str | None = "/obj") -> str:
        """
        R1: Topological scene hashing via Houdini change-detection APIs.

        Timed wrapper around _compute_scene_hash_impl: every call records its
        wall-clock duration into the module ``scene_hash_ms`` histogram
        (scene_hash_stats()) so the stage-Flatten cost is visible in telemetry.
        The hash VALUE is identical to the un-timed implementation.
        """
        _t0 = time.perf_counter()
        try:
            return self._compute_scene_hash_impl(target_node_path)
        finally:
            _record_scene_hash_ms((time.perf_counter() - _t0) * 1000.0)

    def _compute_scene_hash_impl(self, target_node_path: str | None = "/obj") -> str:
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
        try:
            if hasattr(node, "stage"):
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
          attribute VALUE change ...... per-attr value repr + value-type + #samples
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
                # time-sample add/remove (count). visibility lands here too.
                for attr in prim.GetAuthoredAttributes():
                    try:
                        parts.append(
                            f"{attr.GetName()}:{attr.GetTypeName()}"
                            f":{attr.GetNumTimeSamples()}={attr.Get()!r}"
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

    # ── Synchronous Execute (test / direct main-thread) ──────

    def execute(self, operation: Operation) -> ExecutionResult:
        """Synchronous path. For async MCP server, use execute_async()."""
        self._operations_total += 1
        agent_key = operation.agent_id.value if operation.agent_id else ""
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
        integrity.main_thread_executed = True
        integrity.undo_group_active = True

        try:
            integrity.scene_hash_before = self._compute_scene_hash(hash_target)
            self._note_external_change(integrity, hash_target)  # H1

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

                return self._finalize(operation, integrity, result)

        except Exception as e:
            note = self._guarded_rollback(integrity, hash_target)  # H2
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
        self._operations_total += 1
        agent_key = operation.agent_id.value if operation.agent_id else ""
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
            integrity.main_thread_executed = True
            integrity.undo_group_active = True
            integrity.scene_hash_before = self._compute_scene_hash(hash_target)
            self._note_external_change(integrity, hash_target)  # H1

            try:
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

                    return self._finalize(operation, integrity, result)

            except Exception as e:
                note = self._guarded_rollback(integrity, hash_target)  # H2
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

        On failure: wipes caches via dirtyAllTasks(remove_files=True).
        """
        integrity.main_thread_executed = True
        integrity.undo_group_active = True

        if not _HOU_AVAILABLE:
            # Test fallback: simulate successful cook
            integrity.delta_hash = "pdg_test_cook"
            return self._finalize(operation, integrity, {"pdg": "test_cook_ok"})

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
        try:
            # H21.0.671: pdg.PyEventHandler(fn) is a PHANTOM constructor
            # ("TypeError: No constructor defined"). The live idiom is
            # graph_context.addEventHandler(raw_callable, EventType) — it
            # REGISTERS the callable AND RETURNS the wrapper object, which
            # we keep so we can removeEventHandler() it later. One call per
            # event type → one wrapper per type. The callback fires on
            # Houdini's main thread; threading.Event.set() is thread-safe.
            def on_cook_event(event):
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
                try:
                    top_node.executeGraph()
                except Exception as e:
                    cook_error[0] = str(e)
                    cook_complete.set()

            hdefereval.executeInMainThread(_exec_graph_safe)

            # Poll the threading.Event from the async loop so FastMCP stays
            # responsive. 250ms poll interval matches gate polling cadence.
            loop = asyncio.get_running_loop()
            while not cook_complete.is_set():
                await asyncio.sleep(0.25)

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
            # Disk-based rollback: wipe generated caches
            try:
                hdefereval.executeInMainThread(
                    lambda: top_node.dirtyAllTasks(remove_files=True)
                )
            except Exception:
                pass
            integrity.delta_hash = "pdg_rolled_back"
            return self._fail_with_integrity(
                integrity,
                f"PDG cook failed on farm. Caches wiped. {cook_error[0]}",
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
            self._anchor_violations += 1
            return self._fail_with_integrity(
                integrity, f"Integrity check failed: fidelity={fidelity}",
                "integrity_violation",
            )

        self._operations_verified += 1
        agent_key = operation.agent_id.value if operation.agent_id else ""
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

            try:
                from pxr import Sdf
                _pxr_available = True
            except ImportError:
                _pxr_available = False

            for prim in stage.Traverse():
                if not prim.IsValid():
                    self._log_composition_failure(
                        stage_path, prim.GetPath(), "prim is invalid")
                    return False
                if not prim.IsActive():
                    continue

                if prim.HasAuthoredReferences() and _pxr_available:
                    refs_api = prim.GetReferences()
                    prim_path = str(prim.GetPath())
                    for ref_item in refs_api.GetAddedOrExplicitItems():
                        # Cycle detection: prim referencing itself
                        ref_prim_path = str(ref_item.primPath) if ref_item.primPath else ""
                        if ref_prim_path == prim_path:
                            self._log_composition_failure(
                                stage_path, prim.GetPath(),
                                f"self-referencing cycle: {prim_path}")
                            return False
                        # Validate referenced layers resolve
                        if ref_item.assetPath:
                            resolved = Sdf.Layer.Find(str(ref_item.assetPath))
                            if resolved is None:
                                resolved = Sdf.Layer.FindOrOpen(str(ref_item.assetPath))
                            if resolved is None:
                                self._log_composition_failure(
                                    stage_path, prim.GetPath(),
                                    f"unresolvable reference: {ref_item.assetPath}")
                                return False
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

    def _log_composition_failure(self, stage_path: str, prim_path, reason: str) -> None:
        import logging
        logger = logging.getLogger("synapse.bridge")
        logger.warning(
            "Composition validation failed on %s at %s: %s",
            stage_path, prim_path, reason,
        )

    def _fail_with_integrity(self, integrity: IntegrityBlock,
                             error: str, error_type: str) -> ExecutionResult:
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
        return [b.to_dict() for b in self._operation_log]


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
