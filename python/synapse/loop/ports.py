"""ports.py — blueprint §4 contract surface for THE LOOP v5.1.

VERBATIM signatures (blueprint §4):
    PortResult   NamedTuple(status, payload, error_message)  status ∈ SUCCESS|UNAVAILABLE|BLOCKED
    SafetyPort   evaluate_path(agent_id, path_history_hash, recent_actions, proposed_action, scene_state_digest)
    MemoryPort   query_and_filter(relation_keys, task_context_tokens)
    LedgerPort   author_precommit(claim_predicate, probability, world_ref)
    StagePort    compose_sanitized_stage(stage_identifier)

Honest-seam rule: a port whose live substrate is absent reports UNAVAILABLE
with a reason (phantom-API law). Only Moneta is live today. Hanish/SALUS/
Octavius/jacobian-monologue are spec-grounded only — their ports satisfy the
contract surface; their live gates are later rungs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, NamedTuple, Optional

# ---------------------------------------------------------------------------
# PortResult + STATUS
# ---------------------------------------------------------------------------

STATUS = frozenset({"SUCCESS", "UNAVAILABLE", "BLOCKED"})


class PortResult(NamedTuple):
    """Uniform result envelope for every port method (blueprint §4)."""

    status: str  # "SUCCESS" | "UNAVAILABLE" | "BLOCKED"
    payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    @classmethod
    def ok(cls, payload: Optional[Dict[str, Any]] = None) -> "PortResult":
        return cls(status="SUCCESS", payload=payload)

    @classmethod
    def unavailable(cls, reason: str) -> "PortResult":
        return cls(status="UNAVAILABLE", error_message=reason)

    @classmethod
    def blocked(cls, reason: str) -> "PortResult":
        return cls(status="BLOCKED", error_message=reason)


def _require_status(result: PortResult) -> PortResult:
    if result.status not in STATUS:
        raise ValueError(
            f"status {result.status!r} not in {sorted(STATUS)} — ports may only "
            "return SUCCESS|UNAVAILABLE|BLOCKED (blueprint §4)"
        )
    return result


# ---------------------------------------------------------------------------
# Repo-relative ledger location (no hardcoded user paths)
# ---------------------------------------------------------------------------

# python/synapse/loop/ports.py -> parents[3] = repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_LEDGER_FILE = "v00_precommits.jsonl"


def ledger_dir() -> Path:
    """The ledger directory: env SYNAPSE_LOOP_LEDGER_DIR override, else the
    repo-relative harness/loop/ledger/. One oracle for the file location."""
    env_dir = os.environ.get("SYNAPSE_LOOP_LEDGER_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    return _REPO_ROOT / "harness" / "loop" / "ledger"


# ---------------------------------------------------------------------------
# Ports (blueprint §4)
# ---------------------------------------------------------------------------


class SafetyPort:
    """f(I, S_k, a_{k+1}, Ω) — path safety. V0.1 rung: SALUS live gate.

    SALUS is spec-grounded, not installed -> every evaluation reports
    UNAVAILABLE naming the absent substrate. Never a fabricated ALLOW.
    """

    def evaluate_path(self, agent_id, path_history_hash, recent_actions,
                      proposed_action, scene_state_digest) -> PortResult:
        return _require_status(PortResult.unavailable(
            "SALUS substrate not installed (substrate_presence.salus=absent); "
            "SafetyPort.evaluate_path is contract-surface-only until V0.1"
        ))


class MemoryPort:
    """Recall with task-context filtering. V0.2 rung: PG-DRM active inside.

    Moneta is live as the memory substrate but the headless task-context
    filter (PG-DRM) is not wired -> query_and_filter reports UNAVAILABLE.
    """

    def query_and_filter(self, relation_keys, task_context_tokens) -> PortResult:
        return _require_status(PortResult.unavailable(
            "PG-DRM task-context filter not wired (V0.2 rung); Moneta is live "
            "but query_and_filter is contract-surface-only until then"
        ))


class LedgerPort:
    """Append-only precommit ledger. The V0.0 invariant: precommit authored
    BEFORE any mutating act, every turn. settle() stays honest-UNAVAILABLE
    until Hanish lands, so every turn verdict is EXPOSED."""

    def __init__(self, ledger_dir_override: Optional[Path] = None) -> None:
        # run_recipe threads its ledger_dir here; the classmethod ledger_path()
        # stays the zero-arg oracle the probes ask.
        self._dir = Path(ledger_dir_override).resolve() if ledger_dir_override else ledger_dir()

    @classmethod
    def ledger_path(cls) -> Path:
        """One oracle: env override or repo-relative default, with the file name."""
        return ledger_dir() / _DEFAULT_LEDGER_FILE

    @property
    def ledger(self) -> Path:
        return self._dir / _DEFAULT_LEDGER_FILE

    def author_precommit(self, claim_predicate, probability, world_ref) -> PortResult:
        """Append one durable precommit line BEFORE the mutating act.

        probability is a number in [0,1] the AUTHOR asserts for the predicate
        at author time — V0.0 honest value is 0.0 (no observed outcome yet,
        the predicate is a pre-registration, not a posterior). A bool is not a
        probability (True is an int subclass) — rejected.
        """
        if isinstance(probability, bool) or \
                not isinstance(probability, (int, float)) or \
                not (0.0 <= probability <= 1.0):
            return _require_status(PortResult.blocked(
                f"probability must be a number in [0,1], got {probability!r}"))
        if not isinstance(claim_predicate, str) or not claim_predicate.strip():
            return _require_status(PortResult.blocked("claim_predicate must be a non-empty string"))
        if not isinstance(world_ref, str) or not world_ref.strip():
            return _require_status(PortResult.blocked("world_ref must be a non-empty string"))

        line = {
            "event": "precommit",
            "claim_predicate": claim_predicate,
            "probability": float(probability),
            "world_ref": world_ref,
            "author": "v0.0-recipe",
            "seq": self._next_seq(),
        }
        # Append + flush + fsync: durable BEFORE the mutation step runs. Never
        # rename over an existing ledger (append-only discipline). A write
        # failure is an honest UNAVAILABLE — never a crash, never a fabricated
        # SUCCESS (blueprint §3 step-6 fallback: log error, turn stays exposed).
        try:
            self.ledger.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return _require_status(PortResult.unavailable(
                f"ledger dir create failed: {e}"))
        try:
            with open(self.ledger, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError as e:
            return _require_status(PortResult.unavailable(
                f"ledger write failed: {e}"))
        return _require_status(PortResult.ok({"seq": line["seq"]}))

    def settle(self, turn_id) -> PortResult:
        """Settlement. Hanish (settlement substrate) is absent -> honest
        UNAVAILABLE; the turn stays EXPOSED. Never a fabricated HIT/MISS."""
        return _require_status(PortResult.unavailable(
            "Hanish substrate not installed (substrate_presence.hanish=absent); "
            "settlement honest-UNAVAILABLE until V0.2"
        ))

    def _next_seq(self) -> int:
        if not self.ledger.exists():
            return 1
        n = 0
        for ln in self.ledger.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                try:
                    rec = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if rec.get("event") == "precommit":
                    n = max(n, int(rec.get("seq", 0)))
        return n + 1


class StagePort:
    """Sanitized USD stage composition. V0.3 rung: quine filter + drain points.

    Octavius is absent -> compose_sanitized_stage reports UNAVAILABLE naming
    the absent substrate and writes NOTHING to disk (V0.0 gate: closes
    without the Octavius stage present).
    """

    def compose_sanitized_stage(self, stage_identifier) -> PortResult:
        # Deliberately zero side effects: no files, no ledger, no state.
        return _require_status(PortResult.unavailable(
            f"Octavius substrate not installed (substrate_presence.octavius=absent); "
            f"StagePort.compose_sanitized_stage('{stage_identifier}') is "
            "contract-surface-only until V0.3"
        ))
