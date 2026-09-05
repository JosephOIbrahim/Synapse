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

from synapse.panel.designsystem import tokens as _ds

logger = logging.getLogger(__name__)

# ── sys.path bridging ────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", ".."))  # panel->synapse->python->repo root (was 4x '..' = one level too high)
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
        # R306: the R1 stage-hash size gate's blind spot, counted instead of
        # invisible. See record() for what each one means.
        self._reduced_fidelity: int = 0
        self._unobservable_deltas: int = 0

    def record(self, integrity_dict: dict) -> None:
        """Record an IntegrityBlock result from bridge execution."""
        self._blocks.append(integrity_dict)
        self._total += 1

        fidelity = integrity_dict.get("fidelity", 1.0)
        if fidelity < 1.0:
            self._violations += 1

        # ── R306: the reduced-mode blind spot is COUNTED, never hidden ──
        # Above the R1 size gate the stage hash runs the reduced signature,
        # which never reads attribute VALUES. The bridge records that honestly
        # (stage_hash_full_fidelity=False) but nothing read it. Two counts:
        #   reduced_fidelity     ops whose delta was computed by the reduced
        #                        signature at all (the denominator).
        #   unobservable_deltas  the blind-spot case itself: reduced mode AND
        #                        delta_hash "no_change". before == after here
        #                        means "this algorithm could not see a change",
        #                        NOT "nothing changed" — a value-only edit above
        #                        threshold lands here.
        # Deliberately NOT folded into violations/fidelity: an honest reduction
        # is not a pipeline bug, and R306 puts fidelity semantics out of scope.
        # Deliberately NOT counted as a mutation either — the point is that an
        # unobservable delta is VISIBLE as unobservable, not invented.
        if not integrity_dict.get("stage_hash_full_fidelity", True):
            self._reduced_fidelity += 1
            if integrity_dict.get("delta_hash") == "no_change":
                self._unobservable_deltas += 1

        # Track tool usage for evolution triggers
        self._tool_calls += 1
        operation = integrity_dict.get("operation", "")
        if operation in ("create_node", "set_parameter", "connect_nodes"):
            # Extract node path hints from the block.
            # NOTE (R306, verified at HEAD): the sentinels below guard the two
            # SCENE-HASH fields, which only ever hold a hex digest or "" —
            # shared/bridge.py assigns "no_change"/"rolled_back" to delta_hash
            # ALONE, never to these. So this filter has never discarded the
            # blind-spot case; it simply never saw it. The real gap was that
            # nothing counted that case at all — closed above, not here. Left
            # behaviorally untouched: it is inert, and the evolution-trigger
            # heuristic is not this lane's contract.
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

    @property
    def unobservable_delta_count(self) -> int:
        """Ops whose delta could not be observed at full fidelity (R306).

        NOT a violation count and NOT a mutation count — a separate, honest
        third category: the reduced stage hash ran and saw no change, which
        does not establish that no change happened.
        """
        return self._unobservable_deltas

    def should_warn(self) -> bool:
        """True if 3+ integrity violations occurred."""
        return self._violations >= 3

    def summary(self) -> dict:
        """Qt-free aggregation for the panel's fidelity readout.

        THE LOAD-BEARING GUARD is ``has_data``: ``session_fidelity`` returns a
        clean 1.0 when ``total == 0`` (nothing has run), so a widget that only
        read ``fidelity`` would paint a green 100% before a single operation --
        a lie. ``has_data`` (``total > 0``) is how the widget knows to render
        "no operations yet" instead. ``verified`` is ``total - violations``.

        This method stays ``hou``-free / Qt-free so the honesty-critical
        aggregation is testable under stock CPython.

        ``reduced_fidelity`` / ``unobservable_deltas`` are ADDITIVE (R306) and
        deliberately sit outside the verified/violations split: a reduced-mode
        op is neither a proven pass nor a pipeline bug, and collapsing it into
        either would be the same lie in the other direction.
        """
        return {
            "total": self._total,
            "verified": self._total - self._violations,
            "violations": self._violations,
            "fidelity": self.session_fidelity,
            "has_data": self._total > 0,
            "should_warn": self.should_warn(),
            "reduced_fidelity": self._reduced_fidelity,
            "unobservable_deltas": self._unobservable_deltas,
        }

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
        """Format an HTML report for the activity log.

        NOTE (Law 2, honest scope): this method has NO caller in the tree today
        — ``summary()`` is the live path (claude_worker -> integrity_updated ->
        face_work -> IntegrityReadout). The R306 line below is kept in step with
        ``summary()`` so the two renderings cannot diverge if it is ever wired,
        but it is not itself a surfacing claim.
        """
        lines = []
        lines.append("<b>Session Integrity</b>")
        lines.append("Operations: {} | Verified: {} | Violations: {}".format(
            self._total, self._total - self._violations, self._violations,
        ))
        lines.append("Fidelity: {:.1%}".format(self.session_fidelity))
        lines.append("Tool calls: {} | Node paths: {}".format(
            self._tool_calls, len(self._node_paths),
        ))

        if self._unobservable_deltas:
            lines.append(
                f'<span style="color: {_ds.WARN};">' '{} operation{} ran on a '
                'reduced stage hash with no delta observed -- a value-only '
                'edit would be invisible to it. Not a violation; not a '
                'verified no-op either.</span>'.format(
                    self._unobservable_deltas,
                    "" if self._unobservable_deltas == 1 else "s",
                )
            )

        if self.should_warn():
            lines.append(
                f'<span style="color: {_ds.FIRE};">WARNING: Multiple integrity '
                'violations detected. Check undo history.</span>'
            )

        if self.should_evolve():
            lines.append(
                f'<span style="color: {_ds.SIGNAL};">Memory evolution recommended '
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
