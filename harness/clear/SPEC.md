# SPEC — the CLEAR work-clearance harness

*The contract. Written at FRAME (ratified 2026-07-31), changed only at explicit ratification points. Do not edit without a ratified change.*

## Outcome

SYNAPSE stops carrying dangling work. Every open item from the four categories — uncommitted work in the tree, the 289-open decisions board, the open-from-release tech debt, the CHANGELOG gap — is either **closed** (committed / fixed / ratified) or **parked behind a named human gate** with the clock visible. The harness consumes the board `harness/decisions.py` already maintains, routes each item to the right mode, fans out only where parallelism is real, halts at every human gate, and reports a 10-minute ADHD-friendly bar that reads actual state — never narrates.

## Acceptance Predicates

The bar. These IDs are canonical — used verbatim in PLAN, CHAMPION, verify.py, and the progress bar.

| ID | Predicate | Check |
|---|---|---|
| **P1.1** | Latency-relay files are committed at `<sha>` OR dropped via a logged human gate | `git log --all` finds all 6 files, OR a DECISIONS/flywheel entry marks the set dropped |
| **P2.1** | Board is non-stale (regenerated <24h) AND cycle C.0 has a recorded human decision (ratified OR explicitly deferred) | `python harness/decisions.py --count` runs + read `harness/state/flywheel_queue.json` C.0 |
| **P3.1** | F6 fixed: SessionStart pings before reporting "connected" | `tests/test_sessionstart_ping.py` collects + passes |
| **P3.2** | CI mcp drift resolved (mcp pinned OR `mcp_server.py:899` updated) | `python -m pytest tests/test_passthrough_hygiene.py --co -q` collects without the `list_tools` error |
| **P3.3** | `websocket.py:471` cancel is reachable mid-frame | a cancel-injection test passes |
| **P3.4** | husk render cure is parked behind a named gate (Indie-blocked) | a DECISIONS/flywheel entry exists; no agent claims to "fix" it |
| **P3.5** | Latency report §1 addendum appended (Joe's gate) | addendum file exists OR a "gated, deferred" entry |
| **P4.1** | v5.34–v5.40 have CHANGELOG entries OR a deliberate "not backfilling" decision | `CHANGELOG.md` grep for `## v5.34`..`## v5.40` + DECISIONS entry |

## Out of Scope

- **Deciding the 289.** `decisions.py` proved the bottleneck is triage attention, not authority (only 5 of 26 unratified cycles are agent-decidable). The harness surfaces and ranks; the human flips. It never writes `ratified`.
- **Auto-merging or auto-pushing.** Gate C (`SYNAPSE_GATE_C=1`) stays human.
- **Editing the 7-27 latency report without Joe's gate.** Flag only.
- **Building new specialist agents.** The roster (cartographer / assayer / forge / crucible / scribe / gatewarden / sidefx-cto) already exists. The harness composes them.

## Falsification Conditions

Failures that would prove the approach wrong:

- The harness spawns a team to "decide" the 289 → it's the theater the decisions-board finding warned against.
- Any agent flips `ratified` or crosses Gate C → permission boundary failed.
- The 10-minute bar reports a stalled line as "in progress" → hallucinated progress.
- The board count goes UP after a run (more dangling items than it started with) → the harness is net-producing work, not clearing it.

## Verification Strategy

| Predicate | Layer | Stochastic? |
|---|---|---|
| P1.1 | L1 (`git log` check) | No |
| P2.1 | L1 (board + flywheel read) | No |
| P3.1 | L1 (pytest) + L2 (edge cases) | No |
| P3.2 | L1 (pytest collection) | No |
| P3.3 | L1 (cancel test) + L2 (timing) | **Yes (timing)** → noise-aware, replicate before promoting |
| P3.4 | L1 (entry exists) + L3 (semantic: the entry is honest, not a rubber stamp) | No |
| P3.5 | L1 (addendum or entry) + L3 (semantic) | No |
| P4.1 | L1 (grep + entry) | No |
| All gates | L4 (crucible: tries to make an agent flip `ratified`, cross Gate C, narrate a false bar) | No |