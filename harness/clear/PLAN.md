# PLAN — the live line-of-attack structure

*Re-written whenever deliberation reopens. Mode is a readout of the live line structure, not a fixed setting.*

## L1 · uncommitted-work · MODE: SOLO

**GOAL:** Get the 6 latency-relay files off the untracked list — committed or deliberately dropped — and dispose of stale scratch.

**CONTRACT:** P1.1.

**VERIFIER:** L1 — `git log --all` finds all 6 files, OR a DECISIONS/flywheel entry marks the set dropped. Not stochastic.

**MODE REASONING:** One dependent chain (present gate → commit-or-drop → dispose). Breadth = 1 → SOLO. A hard dependency chain is one deep agent, not a team, however hard.

**RANKED PROPOSAL QUEUE (cheapest first):**
1. Present the commit-or-drop human gate to Joe with the 6 latency-relay files listed (`latency-forge.md`, `latency-measurer.md`, `latency-relay-orchestrator.md`, `latency-relay.js`, `latency-relay-operator-card.md`, `synapse-latency-report-2026-07-27.md`).
2. If **commit**: stage + commit via `git commit -F <file>` on a branch. Gate C (push/merge) is human — halt there.
3. If **drop**: log a DECISIONS entry marking the set dropped; do not delete without a gate.
4. Dispose of stale scratch: the 2026-07-25 remediation ticket is STALE (its branches are gone/merged) → close it; `docs/synapse_health_report.md` (stale, says v5.33.0), `docs/mat_dump.json`, `.claude/h2-halt/` → triage (commit as scratch-archive or remove + broaden ignore).

## L2 · decisions-board · MODE: SOLO

**GOAL:** Turn 289 open items into ONE ranked digest Joe can clear in a sitting; surface the C.0 blocker.

**CONTRACT:** P2.1.

**VERIFIER:** L1 — board regenerated <24h AND C.0 has a recorded human decision. Not stochastic.

**MODE REASONING:** The bottleneck is human ATTENTION, not authority (`decisions.py` proved: only 5/26 agent-decidable). Breadth = 1 effective line (a team would contend on the same human gate and the same digest). → SOLO. Spawning a team to "decide" is theater (pre-registered in DEADENDS).

**RANKED PROPOSAL QUEUE:**
1. Regenerate the board: `python harness/decisions.py --write`.
2. Produce the ranked digest (top blockers first): C.0 ratification flip, L0 hygiene (8 dead tracked dirs, 15 untracked `docs/*.txt`, rebuild `done.json`, Issue #3), the L1/L3 items.
3. Surface the exact C.0 flip to Joe (the literal `ratified: true` edit on cycle C.0) — but **never flip it yourself**.
4. Record Joe's decision (ratified OR explicit deferral) so P2.1 clears.

## L3 · open-from-release · MODE: ORCHESTRATED

**GOAL:** Close the four independent tech-debt items the v5.40.1 release left open.

**CONTRACT:** P3.1, P3.2, P3.3, P3.4, P3.5.

**VERIFIER:** L1 (pytest / entry exists) + L2 (edge, timing on P3.3) + L3 (semantic). P3.3 is stochastic (timing) → noise-aware replicate.

**MODE REASONING:** 4 independent fix lines (F6, CI mcp, websocket cancel, addendum) + long horizon (each is measure→fix→verify) + expensive rework (these touch live paths) + external launcher available (the Workflow tool). Breadth × independence ≥ 4 → ORCHESTRATED. The only line that earns a team.

**RANKED PROPOSAL QUEUE (4 independent lines, each gatewarden ALLOW → forge → assayer → crucible):**
1. **F6 (P3.1):** SessionStart pings before reporting "connected". New `tests/test_sessionstart_ping.py` + the ping fix. Cheapest, highest-leverage (would have prevented the whole v5.40.1 incident class).
2. **CI mcp (P3.2):** pin `mcp` version OR update `mcp_server.py:899` to the new decorator API. Re-green CI on the runners.
3. **websocket.py:471 (P3.3):** cancel-injection test + reachable cancel path. STOCHASTIC (timing) → replicate before promote.
4. **latency §1 addendum (P3.5):** JOE'S GATE — flag, do not edit `docs/reviews/synapse-latency-report-2026-07-27.md` without Joe.
5. **husk (P3.4):** PARKED, not queued for a fix. Indie-blocked (DEADENDS). Register the deferral entry so P3.4 clears.

## L4 · changelog-gap · MODE: SOLO

**GOAL:** v5.34–v5.40 (7 releases) have CHANGELOG entries OR a deliberate "not backfilling" decision.

**CONTRACT:** P4.1.

**VERIFIER:** L1 — `CHANGELOG.md` grep for `## v5.34`..`## v5.40` + DECISIONS entry. Not stochastic.

**MODE REASONING:** One serial history-reconstruction chain. Breadth = 1 → SOLO.

**RANKED PROPOSAL QUEUE:**
1. Reconstruct v5.34–v5.40 entries from `git log --oneline` between the v5.33.0 and v5.40.1 commits.
2. OR present a "not backfilling" gate to Joe (log a DECISIONS entry).