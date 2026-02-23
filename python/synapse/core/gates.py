"""
Synapse Human Gate System

Human-in-the-loop approval checkpoints for AI agent workflows.
Designed for per-sequence batch approval (faster, more trust).

Gate Levels:
- INFORM: Log only, no approval needed
- REVIEW: Collect for batch review, continue work
- APPROVE: Pause and require explicit approval before continuing
- CRITICAL: Stop everything, require approval with confirmation
"""

import json
import logging
import time
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Tuple
from enum import Enum

from .determinism import deterministic_uuid
from .audit import audit_log, AuditLevel, AuditCategory

logger = logging.getLogger(__name__)

try:
    from .crypto import CryptoEngine, ENCRYPTION_AVAILABLE
except ImportError:
    ENCRYPTION_AVAILABLE = False


class GateLevel(Enum):
    """Approval requirement levels"""
    INFORM = "inform"        # Just log it
    REVIEW = "review"        # Batch review later
    APPROVE = "approve"      # Need approval to continue
    CRITICAL = "critical"    # Full stop, confirm twice


class GateDecision(Enum):
    """Human decisions at gates"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"    # Approved with changes
    DEFERRED = "deferred"    # Review later


@dataclass
class GateProposal:
    """A proposed action awaiting human review"""

    # Identity
    proposal_id: str
    gate_id: str
    sequence_id: str

    # What's being proposed
    operation: str
    description: str
    category: AuditCategory
    level: GateLevel

    # Details
    proposed_changes: Dict[str, Any] = field(default_factory=dict)
    preview_data: Dict[str, Any] = field(default_factory=dict)
    rollback_data: Dict[str, Any] = field(default_factory=dict)

    # Agent context
    agent_id: str = ""
    reasoning: str = ""
    confidence: float = 0.0  # 0-1, agent's confidence in proposal

    # Timing
    created_at: str = ""
    expires_at: str = ""  # Optional deadline

    # Decision tracking
    decision: GateDecision = GateDecision.PENDING
    decided_by: str = ""
    decided_at: str = ""
    decision_notes: str = ""
    modified_changes: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if not self.proposal_id:
            content = f"{self.gate_id}:{self.operation}:{self.created_at}"
            self.proposal_id = deterministic_uuid(content, "proposal")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage/transmission"""
        return {
            "proposal_id": self.proposal_id,
            "gate_id": self.gate_id,
            "sequence_id": self.sequence_id,
            "operation": self.operation,
            "description": self.description,
            "category": self.category.value,
            "level": self.level.value,
            "proposed_changes": self.proposed_changes,
            "preview_data": self.preview_data,
            "rollback_data": self.rollback_data,
            "agent_id": self.agent_id,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "decision": self.decision.value,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "decision_notes": self.decision_notes,
            "modified_changes": self.modified_changes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GateProposal':
        """Deserialize from storage"""
        return cls(
            proposal_id=data["proposal_id"],
            gate_id=data["gate_id"],
            sequence_id=data["sequence_id"],
            operation=data["operation"],
            description=data["description"],
            category=AuditCategory(data["category"]),
            level=GateLevel(data["level"]),
            proposed_changes=data.get("proposed_changes", {}),
            preview_data=data.get("preview_data", {}),
            rollback_data=data.get("rollback_data", {}),
            agent_id=data.get("agent_id", ""),
            reasoning=data.get("reasoning", ""),
            confidence=data.get("confidence", 0.0),
            created_at=data.get("created_at", ""),
            expires_at=data.get("expires_at", ""),
            decision=GateDecision(data.get("decision", "pending")),
            decided_by=data.get("decided_by", ""),
            decided_at=data.get("decided_at", ""),
            decision_notes=data.get("decision_notes", ""),
            modified_changes=data.get("modified_changes", {}),
        )

    def to_human_summary(self) -> str:
        """Format for human review"""
        confidence_bar = "█" * int(self.confidence * 10) + "░" * (10 - int(self.confidence * 10))
        return (
            f"{'='*60}\n"
            f"[{self.level.value.upper()}] {self.operation}\n"
            f"{'='*60}\n"
            f"Sequence: {self.sequence_id}\n"
            f"Category: {self.category.value}\n"
            f"Agent Confidence: [{confidence_bar}] {self.confidence:.0%}\n"
            f"\n{self.description}\n"
            f"\nReasoning: {self.reasoning}\n"
            f"\nProposed Changes:\n{json.dumps(self.proposed_changes, indent=2, sort_keys=True)}\n"
        )


@dataclass
class GateBatch:
    """Collection of proposals for batch review"""

    batch_id: str
    sequence_id: str
    proposals: List[GateProposal] = field(default_factory=list)
    created_at: str = ""
    status: str = "collecting"  # collecting, ready, reviewing, completed

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if not self.batch_id:
            self.batch_id = deterministic_uuid(
                f"{self.sequence_id}:{self.created_at}", "batch"
            )

    def add_proposal(self, proposal: GateProposal) -> None:
        """Add proposal to batch"""
        self.proposals.append(proposal)

    def pending_count(self) -> int:
        """Count pending proposals"""
        return sum(1 for p in self.proposals if p.decision == GateDecision.PENDING)

    def summary(self) -> Dict[str, int]:
        """Get decision summary"""
        counts = {d.value: 0 for d in GateDecision}
        for p in self.proposals:
            counts[p.decision.value] += 1
        return counts


class HumanGate:
    """
    Human gate checkpoint manager.

    Supports per-sequence batch approval workflow:
    1. Agent proposes changes -> collected in batch
    2. When sequence complete -> batch presented for review
    3. Human approves/rejects/modifies batch
    4. Approved changes applied, rejected ones rolled back

    Usage:
        gate = HumanGate.get_instance()

        # Propose a change (doesn't apply yet)
        proposal = gate.propose(
            operation="create_light_group",
            description="Create 'key_lights' group with 3 lights",
            sequence_id="shot_010",
            category=AuditCategory.LIGHTING,
            level=GateLevel.REVIEW,
            proposed_changes={"group_name": "key_lights", "lights": [...]},
            reasoning="Following three-point lighting setup",
            confidence=0.85
        )

        # When ready for review
        batch = gate.get_batch("shot_010")
        # Present to human...

        # Record decision
        gate.decide(proposal.proposal_id, GateDecision.APPROVED, user_id="artist")
    """

    _instance: Optional['HumanGate'] = None
    _lock = threading.Lock()

    def __init__(self, storage_dir: Optional[Path] = None):
        self._storage_dir = storage_dir or Path.home() / ".synapse" / "gates"
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        # In-memory state
        self._proposals: Dict[str, GateProposal] = {}
        self._batches: Dict[str, GateBatch] = {}  # sequence_id -> batch
        self._write_lock = threading.Lock()

        # Callbacks for UI integration
        self._on_proposal: List[Callable[[GateProposal], None]] = []
        self._on_decision: List[Callable[[GateProposal, GateDecision], None]] = []
        self._on_batch_ready: List[Callable[[GateBatch], None]] = []

    @classmethod
    def get_instance(cls, storage_dir: Optional[Path] = None) -> 'HumanGate':
        """Get singleton instance"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(storage_dir)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)"""
        with cls._lock:
            cls._instance = None

    # Event registration
    def on_proposal(self, callback: Callable[[GateProposal], None]) -> None:
        """Register callback for new proposals"""
        self._on_proposal.append(callback)

    def on_decision(self, callback: Callable[[GateProposal, GateDecision], None]) -> None:
        """Register callback for decisions"""
        self._on_decision.append(callback)

    def on_batch_ready(self, callback: Callable[[GateBatch], None]) -> None:
        """Register callback for batch ready to review"""
        self._on_batch_ready.append(callback)

    def propose(
        self,
        operation: str,
        description: str,
        sequence_id: str,
        category: AuditCategory,
        level: GateLevel = GateLevel.REVIEW,
        proposed_changes: Optional[Dict[str, Any]] = None,
        preview_data: Optional[Dict[str, Any]] = None,
        rollback_data: Optional[Dict[str, Any]] = None,
        agent_id: str = "",
        reasoning: str = "",
        confidence: float = 0.5,
    ) -> GateProposal:
        """
        Propose a change for human review.

        For INFORM level: logs and returns immediately
        For REVIEW level: adds to batch for later review
        For APPROVE/CRITICAL: would block (but we return proposal for async handling)

        Returns:
            GateProposal with decision=PENDING (or APPROVED for INFORM)
        """
        with self._write_lock:
            # Generate gate ID for this checkpoint
            gate_id = deterministic_uuid(
                f"{sequence_id}:{operation}:{category.value}", "gate"
            )

            proposal = GateProposal(
                proposal_id="",  # Will be generated in __post_init__
                gate_id=gate_id,
                sequence_id=sequence_id,
                operation=operation,
                description=description,
                category=category,
                level=level,
                proposed_changes=proposed_changes or {},
                preview_data=preview_data or {},
                rollback_data=rollback_data or {},
                agent_id=agent_id,
                reasoning=reasoning,
                confidence=confidence,
            )

            # Store proposal
            self._proposals[proposal.proposal_id] = proposal

            # Handle by level
            if level == GateLevel.INFORM:
                # Auto-approve, just log
                proposal.decision = GateDecision.APPROVED
                proposal.decided_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                proposal.decided_by = "system:inform"

                audit_log().log(
                    operation=operation,
                    message=f"[INFORM] {description}",
                    level=AuditLevel.INFO,
                    category=category,
                    agent_id=agent_id,
                    input_data=proposed_changes or {},
                )
            else:
                # Add to batch for this sequence
                batch = self._get_or_create_batch(sequence_id)
                batch.add_proposal(proposal)

                audit_log().log(
                    operation="gate_proposal",
                    message=f"[{level.value.upper()}] Proposed: {operation}",
                    level=AuditLevel.AGENT_ACTION,
                    category=category,
                    agent_id=agent_id,
                    sequence_id=sequence_id,
                    input_data={
                        "proposal_id": proposal.proposal_id,
                        "gate_id": gate_id,
                        "confidence": confidence,
                    },
                )

            # Persist
            self._persist_proposal(proposal)

            # Notify callbacks
            for callback in self._on_proposal:
                try:
                    callback(proposal)
                except Exception:
                    logger.error(
                        "Gate callback %s failed",
                        getattr(callback, "__name__", repr(callback)),
                        exc_info=True,
                    )

            return proposal

    def _get_or_create_batch(self, sequence_id: str) -> GateBatch:
        """Get existing batch or create new one"""
        if sequence_id not in self._batches:
            self._batches[sequence_id] = GateBatch(
                batch_id="",
                sequence_id=sequence_id,
            )
        return self._batches[sequence_id]

    def get_batch(self, sequence_id: str) -> Optional[GateBatch]:
        """Get batch for sequence"""
        return self._batches.get(sequence_id)

    def mark_batch_ready(self, sequence_id: str) -> Optional[GateBatch]:
        """Mark batch as ready for review"""
        batch = self._batches.get(sequence_id)
        if batch:
            batch.status = "ready"

            audit_log().log(
                operation="batch_ready",
                message=f"Batch ready for review: {batch.pending_count()} proposals",
                level=AuditLevel.INFO,
                category=AuditCategory.GATE,
                sequence_id=sequence_id,
                input_data={"batch_id": batch.batch_id, "count": len(batch.proposals)},
            )

            for callback in self._on_batch_ready:
                try:
                    callback(batch)
                except Exception:
                    logger.error(
                        "Gate callback %s failed",
                        getattr(callback, "__name__", repr(callback)),
                        exc_info=True,
                    )

        return batch

    def decide(
        self,
        proposal_id: str,
        decision: GateDecision,
        user_id: str,
        notes: str = "",
        modified_changes: Optional[Dict[str, Any]] = None,
    ) -> Optional[GateProposal]:
        """
        Record human decision on a proposal.

        Args:
            proposal_id: ID of proposal to decide
            decision: The decision (APPROVED, REJECTED, MODIFIED, DEFERRED)
            user_id: Who made the decision
            notes: Optional notes explaining decision
            modified_changes: If MODIFIED, the adjusted changes

        Returns:
            Updated proposal or None if not found
        """
        with self._write_lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                return None

            proposal.decision = decision
            proposal.decided_by = user_id
            proposal.decided_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            proposal.decision_notes = notes

            if decision == GateDecision.MODIFIED and modified_changes:
                proposal.modified_changes = modified_changes

            # Audit log
            audit_level = AuditLevel.GATE_APPROVAL if decision in (
                GateDecision.APPROVED, GateDecision.MODIFIED
            ) else AuditLevel.GATE_REJECTION

            audit_log().log_human_decision(
                operation="gate_decision",
                message=f"[{decision.value.upper()}] {proposal.operation}: {notes or 'No notes'}",
                user_id=user_id,
                category=proposal.category,
                sequence_id=proposal.sequence_id,
                input_data={
                    "proposal_id": proposal_id,
                    "decision": decision.value,
                    "original_changes": proposal.proposed_changes,
                    "modified_changes": modified_changes,
                },
            )

            # Persist
            self._persist_proposal(proposal)

            # Notify callbacks
            for callback in self._on_decision:
                try:
                    callback(proposal, decision)
                except Exception:
                    logger.error(
                        "Gate callback %s failed",
                        getattr(callback, "__name__", repr(callback)),
                        exc_info=True,
                    )

            return proposal

    def decide_batch(
        self,
        sequence_id: str,
        decisions: Dict[str, Tuple[GateDecision, str]],  # proposal_id -> (decision, notes)
        user_id: str,
    ) -> GateBatch:
        """
        Decide on entire batch at once.

        Args:
            sequence_id: Sequence batch to decide
            decisions: Map of proposal_id to (decision, notes)
            user_id: Who made decisions

        Returns:
            Updated batch
        """
        batch = self._batches.get(sequence_id)
        if not batch:
            raise ValueError(f"No batch for sequence: {sequence_id}")

        batch.status = "reviewing"

        for proposal in batch.proposals:
            if proposal.proposal_id in decisions:
                decision, notes = decisions[proposal.proposal_id]
                self.decide(proposal.proposal_id, decision, user_id, notes)

        batch.status = "completed"
        return batch

    def approve_all(self, sequence_id: str, user_id: str, notes: str = "") -> GateBatch:
        """Approve all pending proposals in batch"""
        batch = self._batches.get(sequence_id)
        if not batch:
            raise ValueError(f"No batch for sequence: {sequence_id}")

        decisions = {
            p.proposal_id: (GateDecision.APPROVED, notes)
            for p in batch.proposals
            if p.decision == GateDecision.PENDING
        }

        return self.decide_batch(sequence_id, decisions, user_id)

    def reject_all(self, sequence_id: str, user_id: str, notes: str = "") -> GateBatch:
        """Reject all pending proposals in batch"""
        batch = self._batches.get(sequence_id)
        if not batch:
            raise ValueError(f"No batch for sequence: {sequence_id}")

        decisions = {
            p.proposal_id: (GateDecision.REJECTED, notes)
            for p in batch.proposals
            if p.decision == GateDecision.PENDING
        }

        return self.decide_batch(sequence_id, decisions, user_id)

    def get_proposal(self, proposal_id: str) -> Optional[GateProposal]:
        """Get proposal by ID"""
        return self._proposals.get(proposal_id)

    def get_pending(self, sequence_id: Optional[str] = None) -> List[GateProposal]:
        """Get all pending proposals, optionally filtered by sequence"""
        results = []
        for proposal in self._proposals.values():
            if proposal.decision != GateDecision.PENDING:
                continue
            if sequence_id and proposal.sequence_id != sequence_id:
                continue
            results.append(proposal)
        return results

    def _persist_proposal(self, proposal: GateProposal) -> None:
        """Write proposal to disk"""
        date_str = proposal.created_at[:10]
        file_path = self._storage_dir / f"proposals_{date_str}.jsonl"

        line = json.dumps(proposal.to_dict(), sort_keys=True)
        crypto = CryptoEngine.get_instance() if ENCRYPTION_AVAILABLE else None
        if crypto:
            line = crypto.encrypt_line(line)

        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

    def clear_batch(self, sequence_id: str) -> None:
        """Clear batch after processing (keeps proposals in storage)"""
        if sequence_id in self._batches:
            del self._batches[sequence_id]


# Convenience functions
def human_gate() -> HumanGate:
    """Get global human gate instance"""
    return HumanGate.get_instance()


def propose_change(
    operation: str,
    description: str,
    sequence_id: str,
    category: AuditCategory,
    **kwargs
) -> GateProposal:
    """Convenience function to propose a change"""
    return human_gate().propose(
        operation=operation,
        description=description,
        sequence_id=sequence_id,
        category=category,
        **kwargs
    )
