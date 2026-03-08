"""
Routing Log -- Persist MOE routing decisions to agent.usd.

Logs routing decisions for session replay and cross-session fast-path
learning. Uses native pxr.Usd with string-template fallback.

Phase 5 of the MOE wiring plan.
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

# ── OpenUSD Import Guard ────────────────────────────────────────
_PXR_AVAILABLE = False
try:
    from pxr import Usd, Sdf, Tf
    _PXR_AVAILABLE = True
except ImportError:
    Usd = None  # type: ignore[assignment]
    Sdf = None  # type: ignore[assignment]
    Tf = None  # type: ignore[assignment]

_TYPES_AVAILABLE = False
try:
    from shared.types import AgentID
    from shared.router import MOERouter
    _TYPES_AVAILABLE = True
except ImportError:
    AgentID = None  # type: ignore[assignment,misc]
    MOERouter = None  # type: ignore[assignment,misc]


class RoutingLog:
    """Log routing decisions and persist to agent.usd."""

    def __init__(self, agent_usd_path: str | None = None):
        self._decisions: list[dict] = []
        self._fingerprint_counts: dict[str, int] = {}
        self._agent_usd_path = agent_usd_path
        self._counter = 0

    def log_decision(self, decision) -> None:
        """Record a routing decision.

        Args:
            decision: RoutingDecision from MOERouter.route().
        """
        if decision is None:
            return

        self._counter += 1
        entry = {
            "id": "decision_{:04d}".format(self._counter),
            "timestamp": datetime.now().isoformat(),
            "fingerprint": decision.features.fingerprint()
                if hasattr(decision, "features") else "",
            "primary": decision.primary.value
                if hasattr(decision.primary, "value") else str(decision.primary),
            "advisory": (decision.advisory.value
                if decision.advisory and hasattr(decision.advisory, "value")
                else "none"),
            "method": getattr(decision, "method", "unknown"),
        }
        self._decisions.append(entry)

        # Track fingerprint frequency for session fast-path learning
        fp = entry["fingerprint"]
        if fp:
            self._fingerprint_counts[fp] = self._fingerprint_counts.get(fp, 0) + 1

    def get_frequent_fingerprints(self, threshold: int = 3) -> list[dict]:
        """Return fingerprints seen >= threshold times (candidates for fast paths)."""
        result = []
        for fp, count in self._fingerprint_counts.items():
            if count >= threshold:
                # Find the most recent decision with this fingerprint
                for d in reversed(self._decisions):
                    if d["fingerprint"] == fp:
                        result.append({
                            "fingerprint": fp,
                            "count": count,
                            "primary": d["primary"],
                            "advisory": d["advisory"],
                        })
                        break
        return result

    def apply_learned_fast_paths(self, router) -> int:
        """Apply session-learned fast paths to a router instance.

        Returns number of fast paths applied.
        """
        if not _TYPES_AVAILABLE or router is None:
            return 0

        applied = 0
        for entry in self.get_frequent_fingerprints():
            try:
                primary = AgentID(entry["primary"])
                advisory = AgentID(entry["advisory"]) if entry["advisory"] != "none" else None
                router.learn_fast_path(entry["fingerprint"], primary, advisory)
                applied += 1
            except (ValueError, KeyError):
                pass
        return applied

    def write_to_usd(self, path: str | None = None) -> bool:
        """Write routing log to agent.usd.

        Args:
            path: USD file path. Uses self._agent_usd_path if not provided.

        Returns:
            True if written successfully.
        """
        target = path or self._agent_usd_path
        if not target or not self._decisions:
            return False

        if _PXR_AVAILABLE:
            return self._write_native_usd(target)
        return self._write_template_usd(target)

    def _write_native_usd(self, path: str) -> bool:
        """Write routing log using native pxr.Usd."""
        try:
            # Open or create the stage
            if os.path.exists(path):
                stage = Usd.Stage.Open(path)
            else:
                stage = Usd.Stage.CreateNew(path)

            root = stage.GetPrimAtPath("/SYNAPSE")
            if not root:
                root = stage.DefinePrim("/SYNAPSE", "Xform")
                stage.SetDefaultPrim(root)

            agent = stage.DefinePrim("/SYNAPSE/agent", "Xform")
            log_prim = stage.DefinePrim("/SYNAPSE/agent/routing_log", "Xform")

            for entry in self._decisions:
                safe_id = Tf.MakeValidIdentifier(entry["id"])
                prim_path = "/SYNAPSE/agent/routing_log/{}".format(safe_id)
                prim = stage.DefinePrim(prim_path, "Xform")

                prim.CreateAttribute(
                    "synapse:fingerprint", Sdf.ValueTypeNames.String
                ).Set(entry["fingerprint"])
                prim.CreateAttribute(
                    "synapse:primary_agent", Sdf.ValueTypeNames.String
                ).Set(entry["primary"])
                prim.CreateAttribute(
                    "synapse:advisory_agent", Sdf.ValueTypeNames.String
                ).Set(entry["advisory"])
                prim.CreateAttribute(
                    "synapse:method", Sdf.ValueTypeNames.String
                ).Set(entry["method"])
                prim.CreateAttribute(
                    "synapse:timestamp", Sdf.ValueTypeNames.String
                ).Set(entry["timestamp"])

            stage.GetRootLayer().Save()
            logger.debug("Routing log written to %s (%d decisions)", path, len(self._decisions))
            return True

        except Exception:
            logger.debug("Failed to write routing log to USD", exc_info=True)
            return False

    def _write_template_usd(self, path: str) -> bool:
        """Fallback: write routing log as USDA text template."""
        try:
            lines = ['#usda 1.0\n(\n    defaultPrim = "SYNAPSE"\n)\n']
            lines.append('def Xform "SYNAPSE"\n{\n')
            lines.append('    def Xform "agent"\n    {\n')
            lines.append('        def Xform "routing_log"\n        {\n')

            for entry in self._decisions:
                safe_id = entry["id"].replace("-", "_")
                lines.append('            def Xform "{}"\n            {{\n'.format(safe_id))
                lines.append('                custom string synapse:fingerprint = "{}"\n'.format(
                    entry["fingerprint"].replace('"', '\\"'),
                ))
                lines.append('                custom string synapse:primary_agent = "{}"\n'.format(
                    entry["primary"],
                ))
                lines.append('                custom string synapse:advisory_agent = "{}"\n'.format(
                    entry["advisory"],
                ))
                lines.append('                custom string synapse:method = "{}"\n'.format(
                    entry["method"],
                ))
                lines.append('                custom string synapse:timestamp = "{}"\n'.format(
                    entry["timestamp"],
                ))
                lines.append('            }\n')

            lines.append('        }\n    }\n}\n')

            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            logger.debug("Routing log written (template) to %s", path)
            return True

        except Exception:
            logger.debug("Failed to write routing log template", exc_info=True)
            return False

    def to_dict(self) -> dict:
        """Return routing log as a dict for serialization."""
        return {
            "decisions": self._decisions,
            "fingerprint_counts": self._fingerprint_counts,
            "frequent_fingerprints": self.get_frequent_fingerprints(),
        }


# ── Module-level singleton ───────────────────────────────────────
_log: RoutingLog | None = None


def get_routing_log() -> RoutingLog:
    """Get or create the session routing log."""
    global _log
    if _log is None:
        _log = RoutingLog()
    return _log


def reset_routing_log() -> None:
    """Reset the routing log (e.g., on new session)."""
    global _log
    _log = None
