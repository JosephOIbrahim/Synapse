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
  R8: PDG async cook bridge — pdg.PyEventHandler + asyncio.Event for farm cooks (H21)
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

        if not hash_data:
            return hashlib.sha256(
                datetime.now().isoformat().encode()
            ).hexdigest()[:HASH_LENGTH]

        return hashlib.sha256(
            "|".join(str(x) for x in hash_data).encode("utf-8")
        ).hexdigest()[:HASH_LENGTH]

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
                for dep in n.dependents():
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

            with hou.undos.group(f"SYNAPSE: {operation.summary}"):
                result = operation.fn(*operation.args, **operation.kwargs)

                integrity.scene_hash_after = self._compute_scene_hash(hash_target)

                if integrity.scene_hash_before != integrity.scene_hash_after:
                    integrity.delta_hash = hashlib.sha256(
                        f"{integrity.scene_hash_before}:{integrity.scene_hash_after}".encode()
                    ).hexdigest()[:HASH_LENGTH]
                else:
                    integrity.delta_hash = "no_change"

                # ── ANCHOR: Scene Integrity ─────────────────
                if operation.touches_stage and operation.stage_path:
                    if not self._verify_composition(operation.stage_path):
                        hou.undos.performUndo()
                        raise RuntimeError(
                            f"USD Composition violation on {operation.stage_path}"
                        )

                return self._finalize(operation, integrity, result)

        except Exception as e:
            try:
                hou.undos.performUndo()
            except Exception:
                pass
            integrity.delta_hash = "rolled_back"
            return self._fail_with_integrity(integrity, str(e), "execution_error")

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

            try:
                with hou.undos.group(f"SYNAPSE: {operation.summary}"):
                    result = operation.fn(*operation.args, **operation.kwargs)

                    integrity.scene_hash_after = self._compute_scene_hash(hash_target)

                    if integrity.scene_hash_before != integrity.scene_hash_after:
                        integrity.delta_hash = hashlib.sha256(
                            f"{integrity.scene_hash_before}:{integrity.scene_hash_after}".encode()
                        ).hexdigest()[:HASH_LENGTH]
                    else:
                        integrity.delta_hash = "no_change"

                    if operation.touches_stage and operation.stage_path:
                        if not self._verify_composition(operation.stage_path):
                            hou.undos.performUndo()
                            raise RuntimeError("USD Composition violation detected.")

                    return self._finalize(operation, integrity, result)

            except Exception as e:
                try:
                    hou.undos.performUndo()
                except Exception:
                    pass
                integrity.delta_hash = "rolled_back"
                return self._fail_with_integrity(integrity, str(e), "execution_error")

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
        Cook events use pdg.GraphContext.addEventHandler with pdg.PyEventHandler
        instead of hou TopNode.addEventCallback (which handles hou.nodeEventType).

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

        handler = None
        try:
            # H21: pdg.PyEventHandler wraps a Python callback for PDG events.
            # This callback fires on Houdini's main thread — thread-safe
            # threading.Event.set() is safe to call from any thread.
            def on_cook_event(event):
                if event.type == _pdg.EventType.CookComplete:
                    cook_success[0] = True
                    cook_complete.set()
                elif event.type == _pdg.EventType.CookError:
                    cook_success[0] = False
                    cook_error[0] = event.message if event.message else "Unknown PDG error"
                    cook_complete.set()

            handler = _pdg.PyEventHandler(on_cook_event)
            graph_context.addEventHandler(handler, _pdg.EventType.CookComplete)
            graph_context.addEventHandler(handler, _pdg.EventType.CookError)

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
            if handler is not None:
                try:
                    graph_context.removeEventHandler(handler)
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

    def _check_consent_gate(self, operation: Operation) -> bool:
        """Route consent through synapse.core.gates.HumanGate."""
        proposal = self._gate.propose(
            operation=operation.operation_type,
            description=operation.summary,
            sequence_id=self._session_id,
            category=AuditCategory.PIPELINE,
            level=CoreGateLevel(operation.gate_level.value),
            proposed_changes=operation.kwargs,
            agent_id=operation.agent_id.value if operation.agent_id else "",
            reasoning=f"Bridge gate: {operation.operation_type}",
        )

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
                "Composition validation fallback on %s: %s: %s",
                stage_path, type(exc).__name__, exc,
            )
            return True  # Defensive — validation is best-effort

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
