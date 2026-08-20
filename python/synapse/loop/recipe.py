"""recipe.py — THE LOOP recipe turn, pure-python for V0.0.

The V0.0 invariant (blueprint §2 + §5): every turn authors its precommit in
the real durable ledger BEFORE the mutating act executes, then observes.
Settlement (LedgerPort.settle) stays honest-UNAVAILABLE until Hanish lands,
so every turn verdict is EXPOSED — closure_rate = 1.0 with zero HIT/MISS.

V0.0 has no hou.*: the mutation step is an honest no-op marker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .ports import LedgerPort


@dataclass
class Step:
    kind: str                 # "precommit" | "mutation" | "observe" | "settle"
    detail: str = ""


@dataclass
class Turn:
    id: str
    steps: List[Step] = field(default_factory=list)
    verdict: str = "UNRESOLVABLE"   # HIT | MISS | EXPOSED | UNRESOLVABLE


@dataclass
class Recipe:
    id: str
    turns: int


def build_recipe(recipe_id: str, turns: int = 1) -> Recipe:
    if not isinstance(turns, int) or turns < 1:
        raise ValueError(f"turns must be an int >= 1, got {turns!r}")
    return Recipe(id=recipe_id, turns=turns)


def run_recipe(recipe: Recipe, ledger_dir: Optional[Path] = None) -> List[Turn]:
    """Run `recipe.turns` turns. Each turn, in order:
        1. precommit  — LedgerPort.author_precommit (REAL ledger write)
        2. mutation   — honest no-op marker (V0.0 has no hou.*)
        3. observe    — no observed outcome (nothing mutated)
        4. settle     — LedgerPort.settle -> UNAVAILABLE (Hanish absent)
    Every turn verdict is EXPOSED. Returns the turns in order.
    """
    ledger = LedgerPort(ledger_dir_override=ledger_dir)
    out: List[Turn] = []
    for n in range(1, recipe.turns + 1):
        turn_id = f"{recipe.id}-t{n}"
        turn = Turn(id=turn_id)

        # 1. precommit FIRST — durable, before any act.
        precommit = ledger.author_precommit(
            claim_predicate=f"{turn_id}: no observed outcome is claimed at author time",
            probability=0.0,  # honest: pre-registration, not a posterior
            world_ref=f"v0.0/{recipe.id}",
        )
        turn.steps.append(Step("precommit", f"status={precommit.status} seq={precommit.payload.get('seq') if precommit.payload else None}"))

        # 2. mutating act — V0.0 honest no-op marker; no hou.* reachable.
        turn.steps.append(Step("mutation", "V0.0 has no hou.* — honest no-op marker"))

        # 3. observe — nothing observable happened.
        turn.steps.append(Step("observe", "no observed outcome"))

        # 4. settle — honest-UNAVAILABLE until Hanish; turn stays EXPOSED.
        settlement = ledger.settle(turn_id)
        turn.steps.append(Step("settle", f"status={settlement.status} {settlement.error_message or ''}"))

        turn.verdict = "EXPOSED" if settlement.status == "UNAVAILABLE" else "UNRESOLVABLE"
        out.append(turn)

    return out
