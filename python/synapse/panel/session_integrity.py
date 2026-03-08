"""
Session Integrity Tracker -- Monitor bridge integrity across a conversation.

Tracks IntegrityBlocks from bridge execution, warns on violations,
and checks memory evolution triggers on session completion.

Phase 4 of the MOE wiring plan.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

logger = logging.getLogger(__name__)

# ── sys.path bridging ────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_BRIDGE_AVAILABLE = False
try:
    from shared.bridge import IntegrityBlock
    _BRIDGE_AVAILABLE = True
except ImportError:
    IntegrityBlock = None  # type: ignore[assignment,misc]

_EVOLUTION_AVAILABLE = False
try:
    from shared.evolution import check_evolution_triggers
    _EVOLUTION_AVAILABLE = True
except ImportError:
    check_evolution_triggers = None  # type: ignore[assignment]


class SessionIntegrityTracker:
    """Track integrity across a conversation session."""

    def __init__(self):
        self._blocks: list[dict] = []
        self._violations: int = 0
        self._total: int = 0
        self._tool_calls: int = 0
        self._node_paths: set[str] = set()

    def record(self, integrity_dict: dict) -> None:
        """Record an IntegrityBlock result from bridge execution."""
        self._blocks.append(integrity_dict)
        self._total += 1

        fidelity = integrity_dict.get("fidelity", 1.0)
        if fidelity < 1.0:
            self._violations += 1

        # Track tool usage for evolution triggers
        self._tool_calls += 1
        operation = integrity_dict.get("operation", "")
        if operation in ("create_node", "set_parameter", "connect_nodes"):
            # Extract node path hints from the block
            for key in ("scene_hash_before", "scene_hash_after"):
                val = integrity_dict.get(key, "")
                if val and val not in ("", "no_change", "rolled_back"):
                    self._node_paths.add(val)

    def record_tool_call(self, tool_name: str, args: dict | None = None) -> None:
        """Record a tool call (even if bridge wasn't used)."""
        self._tool_calls += 1
        if args and isinstance(args, dict):
            for key in ("node", "parent", "path", "source", "target"):
                val = args.get(key, "")
                if val and isinstance(val, str) and val.startswith("/"):
                    self._node_paths.add(val)

    @property
    def session_fidelity(self) -> float:
        """Overall session fidelity (1.0 = perfect)."""
        if self._total == 0:
            return 1.0
        return 1.0 - (self._violations / self._total)

    @property
    def violation_count(self) -> int:
        return self._violations

    def should_warn(self) -> bool:
        """True if 3+ integrity violations occurred."""
        return self._violations >= 3

    def should_evolve(self, login_data: dict | None = None) -> bool:
        """Check if memory evolution should be recommended.

        Uses simple heuristics matching shared/evolution.py triggers:
        - 5+ structured tool calls
        - 10+ node path references
        - 10+ total tool calls
        """
        if self._tool_calls >= 10 and len(self._node_paths) >= 5:
            return True
        if len(self._node_paths) >= 10:
            return True

        # Check login data for existing evolution signals
        if login_data and login_data.get("evolution_recommended"):
            return True

        return False

    def format_report(self) -> str:
        """Format an HTML report for the activity log."""
        lines = []
        lines.append("<b>Session Integrity</b>")
        lines.append("Operations: {} | Verified: {} | Violations: {}".format(
            self._total, self._total - self._violations, self._violations,
        ))
        lines.append("Fidelity: {:.1%}".format(self.session_fidelity))
        lines.append("Tool calls: {} | Node paths: {}".format(
            self._tool_calls, len(self._node_paths),
        ))

        if self.should_warn():
            lines.append(
                '<span style="color: #FF6B35;">WARNING: Multiple integrity '
                'violations detected. Check undo history.</span>'
            )

        if self.should_evolve():
            lines.append(
                '<span style="color: #4ECDC4;">Memory evolution recommended '
                '-- structured data accumulated.</span>'
            )

        return "<br>".join(lines)

    def get_bridge_report(self) -> dict | None:
        """Get the full bridge session report."""
        try:
            from synapse.panel.bridge_adapter import get_session_report
            return get_session_report()
        except ImportError:
            return None


# ── Module-level singleton ───────────────────────────────────────
_tracker: SessionIntegrityTracker | None = None


def get_tracker() -> SessionIntegrityTracker:
    """Get or create the session integrity tracker."""
    global _tracker
    if _tracker is None:
        _tracker = SessionIntegrityTracker()
    return _tracker


def reset_tracker() -> None:
    """Reset the tracker (e.g., on new session)."""
    global _tracker
    _tracker = None
