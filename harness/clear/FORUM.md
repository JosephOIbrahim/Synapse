# CLEAR — FORUM

*Append-only deliberation: proposals, critiques, results, analyses. Where critique-before-commit happens and where lines are proposed, merged, split, retired.*

## 2026-07-31 — FRAME ratification

- **SPEC ratified by Joe.** All four categories confirmed ("1-4 is the four categories you created").
- **Per-line modes ratified:** L1 SOLO, L2 SOLO, L3 ORCHESTRATED, L4 SOLO. L3 is the only line that earns a team (breadth × independence ≥ 4 + long horizon + expensive rework + external launcher).
- **MVP ratified:** scaffold + L1 first, then L3 fan-out (P2), then L2 digest + L4 history (P3), then stagnation + LEDGER (P4).
- **Open question (deferred to P2):** Monitor-vs-Cron for the 10-min bar. Recommended: session-bound Monitor for the build, Cron for the standing watch.

## 2026-07-31 — P1 build mode

- The Workflow launcher (external) was temporarily unavailable. Per the AutoScientist HONESTY CONSTRAINT and the ratified SPEC's falsification conditions, the build downshifted to SOLO rather than narrating parallel agents it was not actually running. The P2 L3 fan-out is where ORCHESTRATED earns its keep; the scaffold itself is serial writes either way.

## 2026-07-31 — L5 opened (CTO insight: phantom defense is introspection, not docs)

- **Proposal (Analyst):** the codebase's #1 failure class is phantom APIs. The defense already exists as a per-sprint guardrail (`harness/verify/checks.py::check_phantom_clean` + `scout._load_symbol_table` dir()-authority + freshness/staleness + GUI allowlist). Grounding found it is NOT missing — it is *narrow*.
- **Critique-before-commit (Critic, on the record):** two candidate fixes were tested against source and REJECTED as duplicates before any cost was paid:
  - "build a phantom lint" → REJECTED. `check_phantom_clean` already runs every sprint. (too-easy heuristic fired; grounding caught it.)
  - "add a freshness gate" → REJECTED. `scout._load_symbol_table` (scout.py:520) already stamps+stales; `check_phantom_clean` already WARNs on gate-down.
- **Two surviving gaps, source-confirmed:**
  - **G2 (coverage):** the introspection authority (`host/introspect_runtime.py`) walks hou AND pdg (depth 2) AND pxr (depth 1) — its self-check asserts `pdg.EventType`/`pxr.Usd` are in the table. But the LINT (`_hou_phantoms_in_source`, checks.py:403) collects only `import hou` aliases and flags only `hou.<attr>`. It never queries the table about `pdg.*`/`pxr.*`. So bare `pdg.PyEventHandler`/`pdg.EventType` (the §1.7 phantom) slips through today, even though the authority knows `pdg.EventType` is real. The authority has the data; the scanner doesn't ask.
  - **G1 (scope):** `check_phantom_clean` lives in `harness/verify/checks.py` (per-sprint via run.ts). CLEAR's bar (`harness/clear/verify.py`) runs no phantom check. The #1 failure class is outside work-clearance.
- **Fix (Builder), ORCHESTRATED:** (1) extend the scanner to `pdg.`/`pxr.` depth-1 against the same table — keep `_hou_phantoms_in_source` intact, add a unified `_phantoms_in_source`; (2) propose **P5.1** as a CLEAR predicate with *clearance* semantics — gate-down = FAIL (not WARN), because "couldn't verify no phantoms" is not "no phantoms." **P5.1 is PROPOSED, not ratified** — surfaced for Joe. The ratified SPEC.md and verify.py are NOT edited; a `PROPOSED-P5.1.md` is written for the ratification gate.
- **Team:** cartographer (map the hou/pdg/pxr production surface) + assayer (prove the table covers pdg/pxr) + sidefx-cto (is depth-1 dir()-completeness sound for pdg/pxr as for hou) → forge (worktree: extend + test) → crucible (attack: does it catch the blind spot? do hou tests stay green? depth-2 false-phantoms? stale-table FAIL?). Parallel workflows: L3 fan-out (P3.1/P3.3) continues independently.