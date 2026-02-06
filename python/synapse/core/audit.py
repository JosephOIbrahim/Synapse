"""
Synapse Audit Logging

Every AI agent action is logged for:
1. Reproducibility (replay any sequence of operations)
2. Debugging (trace what went wrong)
3. Compliance (prove what was done and when)
4. Learning (train better agents from success patterns)

Logs are append-only, tamper-evident (hash chain), and human-readable.
"""

import json
import time
import hashlib
import threading
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Callable, Tuple
from enum import Enum

from .determinism import deterministic_uuid, deterministic_dict_items


class AuditLevel(Enum):
    """Severity/importance levels for audit entries"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    # Special levels for agent workflow
    AGENT_ACTION = "agent_action"
    HUMAN_DECISION = "human_decision"
    GATE_APPROVAL = "gate_approval"
    GATE_REJECTION = "gate_rejection"


class AuditCategory(Enum):
    """Categories for filtering audit logs"""
    LIGHTING = "lighting"
    MATERIAL = "material"
    ENVIRONMENT = "environment"
    AOV = "aov"
    RENDER = "render"
    PIPELINE = "pipeline"
    GATE = "gate"
    SYSTEM = "system"
    SYNAPSE = "synapse"
    ENGRAM = "engram"


@dataclass
class AuditEntry:
    """Single audit log entry with hash chain integrity"""

    # Core fields
    timestamp_utc: str
    level: AuditLevel
    category: AuditCategory
    operation: str
    message: str

    # Context
    tool: str = ""
    agent_id: str = ""
    user_id: str = ""
    session_id: str = ""
    sequence_id: str = ""  # Shot/sequence being worked on

    # Operation details
    operation_id: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    # State tracking
    before_state_hash: str = ""
    after_state_hash: str = ""

    # Hash chain (tamper evidence)
    previous_hash: str = ""
    entry_hash: str = ""

    def __post_init__(self):
        if not self.entry_hash:
            self.entry_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of entry content"""
        content = {
            "timestamp_utc": self.timestamp_utc,
            "level": self.level.value,
            "category": self.category.value,
            "operation": self.operation,
            "message": self.message,
            "tool": self.tool,
            "agent_id": self.agent_id,
            "operation_id": self.operation_id,
            "previous_hash": self.previous_hash,
        }
        content_str = json.dumps(dict(deterministic_dict_items(content)), sort_keys=True)
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "timestamp_utc": self.timestamp_utc,
            "level": self.level.value,
            "category": self.category.value,
            "operation": self.operation,
            "message": self.message,
            "tool": self.tool,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "sequence_id": self.sequence_id,
            "operation_id": self.operation_id,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "duration_ms": self.duration_ms,
            "before_state_hash": self.before_state_hash,
            "after_state_hash": self.after_state_hash,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEntry':
        """Create from dictionary"""
        return cls(
            timestamp_utc=data["timestamp_utc"],
            level=AuditLevel(data["level"]),
            category=AuditCategory(data["category"]),
            operation=data["operation"],
            message=data["message"],
            tool=data.get("tool", ""),
            agent_id=data.get("agent_id", ""),
            user_id=data.get("user_id", ""),
            session_id=data.get("session_id", ""),
            sequence_id=data.get("sequence_id", ""),
            operation_id=data.get("operation_id", ""),
            input_data=data.get("input_data", {}),
            output_data=data.get("output_data", {}),
            duration_ms=data.get("duration_ms", 0.0),
            before_state_hash=data.get("before_state_hash", ""),
            after_state_hash=data.get("after_state_hash", ""),
            previous_hash=data.get("previous_hash", ""),
            entry_hash=data.get("entry_hash", ""),
        )

    def to_human_readable(self) -> str:
        """Format for human reading"""
        return (
            f"[{self.timestamp_utc}] [{self.level.value.upper():8}] "
            f"[{self.category.value}] {self.operation}: {self.message}"
        )


class AuditLog:
    """
    Thread-safe audit log with hash chain integrity.

    Usage:
        log = AuditLog.get_instance()
        log.log_action("create_light", "Created key light", category=AuditCategory.LIGHTING)
    """

    _instance: Optional['AuditLog'] = None
    _lock = threading.Lock()

    def __init__(self, log_dir: Optional[Path] = None):
        self._entries: List[AuditEntry] = []
        self._log_dir = log_dir or Path.home() / ".synapse" / "audit"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._current_session = deterministic_uuid(str(time.time()), "session")
        self._last_hash = "genesis"
        self._write_lock = threading.Lock()

        # Callbacks for real-time monitoring
        self._callbacks: List[Callable[[AuditEntry], None]] = []

    @classmethod
    def get_instance(cls, log_dir: Optional[Path] = None) -> 'AuditLog':
        """Get singleton instance"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(log_dir)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)"""
        with cls._lock:
            cls._instance = None

    def add_callback(self, callback: Callable[[AuditEntry], None]) -> None:
        """Add callback for real-time log monitoring"""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[AuditEntry], None]) -> None:
        """Remove callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def log(
        self,
        operation: str,
        message: str,
        level: AuditLevel = AuditLevel.INFO,
        category: AuditCategory = AuditCategory.SYSTEM,
        tool: str = "",
        agent_id: str = "",
        operation_id: str = "",
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        sequence_id: str = "",
    ) -> AuditEntry:
        """
        Log an audit entry.

        Args:
            operation: Name of operation (e.g., "create_light_group")
            message: Human-readable description
            level: Severity level
            category: Category for filtering
            tool: Tool name (e.g., "synapse", "engram")
            agent_id: ID of AI agent (if applicable)
            operation_id: Unique operation ID for correlation
            input_data: Input parameters
            output_data: Output/result data
            sequence_id: Shot/sequence identifier

        Returns:
            Created AuditEntry
        """
        with self._write_lock:
            entry = AuditEntry(
                timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                level=level,
                category=category,
                operation=operation,
                message=message,
                tool=tool,
                agent_id=agent_id,
                session_id=self._current_session,
                sequence_id=sequence_id,
                operation_id=operation_id or deterministic_uuid(f"{operation}:{message}"),
                input_data=input_data or {},
                output_data=output_data or {},
                previous_hash=self._last_hash,
            )

            self._entries.append(entry)
            self._last_hash = entry.entry_hash

            # Write to disk
            self._persist_entry(entry)

            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(entry)
                except Exception:
                    pass  # Don't let callback errors break logging

            return entry

    def log_agent_action(
        self,
        operation: str,
        message: str,
        agent_id: str,
        category: AuditCategory,
        **kwargs
    ) -> AuditEntry:
        """Convenience method for agent actions"""
        return self.log(
            operation=operation,
            message=message,
            level=AuditLevel.AGENT_ACTION,
            category=category,
            agent_id=agent_id,
            **kwargs
        )

    def log_human_decision(
        self,
        operation: str,
        message: str,
        user_id: str,
        category: AuditCategory,
        **kwargs
    ) -> AuditEntry:
        """Convenience method for human decisions"""
        entry = self.log(
            operation=operation,
            message=message,
            level=AuditLevel.HUMAN_DECISION,
            category=category,
            **kwargs
        )
        entry.user_id = user_id
        return entry

    def _persist_entry(self, entry: AuditEntry) -> None:
        """Write entry to disk"""
        # Daily log files
        date_str = entry.timestamp_utc[:10]
        log_file = self._log_dir / f"audit_{date_str}.jsonl"

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry.to_dict()) + '\n')

    def get_entries(
        self,
        level: Optional[AuditLevel] = None,
        category: Optional[AuditCategory] = None,
        operation: Optional[str] = None,
        agent_id: Optional[str] = None,
        sequence_id: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """Query audit entries with filters"""
        results = []

        for entry in reversed(self._entries):
            if level and entry.level != level:
                continue
            if category and entry.category != category:
                continue
            if operation and entry.operation != operation:
                continue
            if agent_id and entry.agent_id != agent_id:
                continue
            if sequence_id and entry.sequence_id != sequence_id:
                continue
            if since and entry.timestamp_utc < since:
                continue

            results.append(entry)
            if len(results) >= limit:
                break

        return results

    def verify_chain(self) -> Tuple[bool, Optional[int]]:
        """
        Verify hash chain integrity.

        Returns:
            (is_valid, first_invalid_index)
        """
        expected_hash = "genesis"

        for i, entry in enumerate(self._entries):
            if entry.previous_hash != expected_hash:
                return False, i
            expected_hash = entry.entry_hash

        return True, None

    def export_session(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Export all entries for a session"""
        target_session = session_id or self._current_session
        return [
            entry.to_dict()
            for entry in self._entries
            if entry.session_id == target_session
        ]

    def replay_info(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get info needed to replay an operation"""
        for entry in self._entries:
            if entry.operation_id == operation_id:
                return {
                    "operation": entry.operation,
                    "input_data": entry.input_data,
                    "before_state_hash": entry.before_state_hash,
                    "expected_output": entry.output_data,
                    "expected_after_hash": entry.after_state_hash,
                }
        return None


# Convenience function for global log access
def audit_log() -> AuditLog:
    """Get global audit log instance"""
    return AuditLog.get_instance()
