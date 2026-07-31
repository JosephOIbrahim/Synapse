# CHAMPION — the current best disposition per line

*Exactly one champion per line. Updated only by noise-aware promotion: a result beats the champion on the predicate, replicated on a fresh run if the check is stochastic, before it is promoted.*

## L1 · uncommitted-work

**CHAMPION:** _(seed)_ All 6 latency-relay files untracked on every branch; no commit-or-drop decision recorded.
- Files: `.claude/agents/latency-forge.md`, `.claude/agents/latency-measurer.md`, `.claude/agents/latency-relay-orchestrator.md`, `.claude/workflows/latency-relay.js`, `docs/latency-relay-operator-card.md`, `docs/reviews/synapse-latency-report-2026-07-27.md`.
**SEED STATE:** open — the loss-risk item.
**VERIFICATION RECIPE:** P1.1 — `git log --all -- <each file>` returns a commit for all 6, OR a DECISIONS entry marks the set dropped.
**PROMOTION RULE:** not stochastic. Promote when the gate fires (commit landed OR drop logged).

## L2 · decisions-board

**CHAMPION:** _(seed)_ 289 open; cycle C.0 `ratified:false`, gate-REFUSING L1 gap-closure; board 5 days stale.
**SEED STATE:** open — human-attention bottleneck, not authority.
**VERIFICATION RECIPE:** P2.1 — `python harness/decisions.py --count` runs AND C.0 has `ratified:true` OR an explicit deferral entry.
**PROMOTION RULE:** not stochastic. Promote when Joe's decision is recorded (the harness never records it for him).

## L3 · open-from-release

**CHAMPION:** _(seed)_ No fix shipped. F6, CI mcp, websocket cancel, and the addendum all open; husk parked (Indie-blocked).
**SEED STATE:** open across 4 independent sub-lines.
**VERIFICATION RECIPE:** P3.1–P3.5 per sub-line. P3.3 is stochastic (timing) → replicate before promote.
**PROMOTION RULE:** per sub-line, noise-aware. P3.4 (husk) promotes only on a deferral entry, never on a "fix."

## L4 · changelog-gap

**CHAMPION:** _(seed)_ Gap unreconstructed — v5.34.0 through v5.40.0 absent from `CHANGELOG.md`.
**SEED STATE:** open.
**VERIFICATION RECIPE:** P4.1 — grep `CHANGELOG.md` for the 7 headers, OR a "not backfilling" DECISIONS entry.
**PROMOTION RULE:** not stochastic. Promote on backfill OR the deliberate non-backfill decision.