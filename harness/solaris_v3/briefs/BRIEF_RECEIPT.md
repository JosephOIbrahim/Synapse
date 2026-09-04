# BRIEF — RECEIPT stream (C5 receipt · card · freshness · cache)

You are the RECEIPT worker in a six-agent swarm implementing `docs/SOLARIS_RECIPES_H22_BLUEPRINT_V3.md`. Read, in order: `docs/solaris_v3/SWARM_CONTRACT.md`, `python/synapse/recipes/contracts.py`, then blueprint pages 09, 08, 13 (S8). Your worktree is the current working directory; branch `bp5/solaris-receipt`. Work only inside your exclusive write set.

## Principle
The card observes; it does not certify itself. The registry defines the offer, the receipt records the run, freshness decides whether that receipt still describes this scene. Cache the plan, never the outcome.

## Deliverables

1. **`python/synapse/recipes/receipt.py`** — `RunReceipt` construction helpers, `to_dict`/`from_dict` (round-trip exact, enums as values), append-only JSONL store under the repo ledger convention (find where `synapse.loop.ports.LedgerPort` and `RecommendationHistory` write; follow the `.tmp + replace` atomic pattern). `reason` required when `verdict != VERIFIED` (validator). Receipts are immutable: a store never edits a line.
2. **`python/synapse/recipes/freshness.py`** — `EvidenceTracker`: invalidation events `scene_load`, `undo`, `redo`, `owned_edit`, `dependency_change`; `freshness(receipt, instance) -> EvidenceFreshness` = CURRENT only when the receipt's `fingerprint_after` equals the current instance fingerprint **and** no invalidating event has fired since `completed_at`; incomplete change tracking → UNKNOWN (never CURRENT by default). Cheap periodic recheck hook allowed; **never** hash the full stage per UI frame (document the rule in the docstring and enforce a min-interval).
3. **`python/synapse/recipes/card.py`** — the minimal card model from p09: recipe/action + scope; graph/USD/render evidence (per `CheckResult`); `Availability` / `OperationState` / `TerminalVerdict` / `EvidenceFreshness`; approval + recovery; **one reason and one next action**. Blocked cards stay visible with reasons ("unavailable is not nonexistent"). `SpecCache` keyed by spec digest that caches compiled specs only — a test must prove no verdict is ever stored. `RequestDedup` keyed by `request_id` + job state.
4. **`python/synapse/panel/recipe_card.py`** — pure rendering of a card to (a) plain text and (b) the panel's existing HTML/rich-text convention. Look at how the panel renders status today (`python/synapse/panel/` — search for the status/health widgets and the vendored design tokens under `panel/designsystem` or similar) and reuse tokens; no Qt import at module top-level so tests run headless. Do not edit `synapse_panel.py`; write the hookup into `docs/solaris_v3/HOOKUP_RECEIPT.md`.
5. **Tests** — `tests/test_recipe_receipt*.py`: round-trip; immutability; reason-required validator; atomic write. `tests/test_recipe_card*.py`: T12 (undo → STALE; reload → STALE/UNKNOWN; dependency edit → STALE; scope change → reapproval required, i.e. card shows `AWAITING_APPROVAL` again), no-verdict-in-cache negative control, blocked-card visibility, request dedup (lost response + retry = one effect), UNKNOWN when tracking incomplete.

## Notes
- The planner's response cache (`routing/router.py`, S8) is out of your write set; if current-scene safeguards are needed there, write them as a HOOKUP note with the exact patch.
- Status lines to `harness/solaris_v3/STATUS_RECEIPT.md`; final report `docs/solaris_v3/REPORT_RECEIPT.md`.
