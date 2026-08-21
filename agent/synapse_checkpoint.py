"""
synapse_checkpoint.py -- Checkpoint and resume for the Synapse Agent.

Saves agent state (plan progress, conversation history, scene snapshot)
to JSONL files so interrupted tasks can be resumed. Each goal gets its
own checkpoint file, identified by a deterministic hash of the goal text.

Part of Sprint C: Agent SDK v2.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from synapse_planner import Plan, goal_hash

logger = logging.getLogger("synapse.checkpoint")

# Checkpoint directory alongside this file
CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"

# Maximum conversation messages to persist (keep context manageable)
MAX_MESSAGES = 20


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

@dataclass
class Checkpoint:
    """Snapshot of agent state for resume."""

    plan: Plan
    messages: list[dict] = field(default_factory=list)
    completed_goals: list[str] = field(default_factory=list)
    scene_snapshot: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.monotonic)
    goal_hash: str = ""

    def __post_init__(self):
        if not self.goal_hash:
            self.goal_hash = self.plan.goal_hash

    def to_dict(self) -> dict:
        """Serialize with sorted keys (He2025)."""
        # Truncate messages to last MAX_MESSAGES
        msgs = self.messages[-MAX_MESSAGES:] if len(self.messages) > MAX_MESSAGES else self.messages
        return {
            "completed_goals": sorted(self.completed_goals),
            "goal_hash": self.goal_hash,
            "messages": msgs,
            "plan": self.plan.to_dict(),
            "scene_snapshot": self.scene_snapshot,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Checkpoint":
        """Deserialize from dict."""
        return cls(
            plan=Plan.from_dict(d["plan"]),
            messages=d.get("messages", []),
            completed_goals=d.get("completed_goals", []),
            scene_snapshot=d.get("scene_snapshot", {}),
            timestamp=d.get("timestamp", 0.0),
            goal_hash=d.get("goal_hash", ""),
        )


# ---------------------------------------------------------------------------
# File Operations
# ---------------------------------------------------------------------------

def save_checkpoint(checkpoint: Checkpoint) -> Path:
    """Append checkpoint as one JSON line to goal-specific file.

    Returns the path to the checkpoint file.
    """
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{checkpoint.goal_hash}.jsonl"
    path = CHECKPOINT_DIR / filename
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(checkpoint.to_dict(), sort_keys=True) + "\n")
    logger.info("Checkpoint saved: %s", path)
    return path


def load_latest_checkpoint(gh: str) -> "Checkpoint | None":
    """Read last line from goal-specific JSONL file.

    Args:
        gh: Goal hash (from goal_hash() function).

    Returns:
        Latest Checkpoint or None if no checkpoint exists.
    """
    path = CHECKPOINT_DIR / f"{gh}.jsonl"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        return None
    try:
        return Checkpoint.from_dict(json.loads(lines[-1]))
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Couldn't parse checkpoint %s: %s", path, e)
        return None


def resume_from_checkpoint(gh: str) -> "tuple[Plan, list[dict]] | None":
    """Load checkpoint and return (plan, messages) for resumption.

    Args:
        gh: Goal hash.

    Returns:
        Tuple of (Plan, messages) or None if no checkpoint found.
    """
    cp = load_latest_checkpoint(gh)
    if cp is None:
        return None
    return cp.plan, cp.messages


def list_checkpoints() -> list[dict]:
    """List all checkpoint files with metadata.

    Returns list of dicts with: goal_hash, path, size_bytes, modified.
    """
    if not CHECKPOINT_DIR.exists():
        return []
    results = []
    for f in sorted(CHECKPOINT_DIR.glob("*.jsonl")):
        stat = f.stat()
        results.append({
            "goal_hash": f.stem,
            "path": str(f),
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
        })
    return results


def prune_old_checkpoints(max_age_days: int = 7) -> int:
    """Delete checkpoint files older than max_age_days.

    Returns count of deleted files.
    """
    cutoff = time.time() - (max_age_days * 86400)
    count = 0
    if CHECKPOINT_DIR.exists():
        for f in sorted(CHECKPOINT_DIR.glob("*.jsonl")):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                count += 1
                logger.info("Pruned old checkpoint: %s", f)
    return count
