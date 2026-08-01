# SPEC — the PHANTOM SWEEP harness

*PROPOSED — awaits Joe's ratification, same discipline as CLEAR's SPEC. The contract. Phantom APIs are SYNAPSE's #1 failure class. This harness house-cleans them: finds every place a known-quarantined phantom symbol is still taught or called, classifies each hit, and queues fixes behind a human gate.*

## Outcome

Every mention of a known-quarantined phantom symbol (`hou.pdg.*`, `hou.secure`, `hou.lopNetworks`, `hou.updateGraphTick`, `pdg.PyEventHandler`, `hdefereval.executeInMainThread`, `usdrender`) across the source, docs, and corpus surfaces is either:

- **KEEP** — an intentional warning/quarantine callout, recorded in the ledger with evidence, never touched. Warnings are learned knowledge; erasing one is the worst failure this harness can produce.
- **FIX** — still teaching or calling the phantom as if usable. Queued in the ledger's FIX list. Executed only by a human-dispatched forge leg in a worktree, gated like every other mutation in this house.

## Surfaces (v1)

| Surface | Scope | Scan mode |
|---|---|---|
| source | `python/ shared/ host/ src/ harness/` — `*.py` | grep of seed symbols (full-AST unknown discovery is L5's scanner — v2 consumes it post-merge) |
| docs | `CLAUDE.md README.md docs/**/*.md harness/**/*.md` | grep + context classification |
| corpus | `rag/**/*.md` | index/grep level only |

Known limitation, stated per README law: v1 sweeps the *known* quarantine signature set. It does not discover unknown phantoms — that is `harness/verify/checks.py`'s scanner, extended by L5. Sweep v2 consumes the extended scanner once L5 lands.

## Predicates (the bar)

| ID | Predicate | Check |
|---|---|---|
| **SW1** | Every seed symbol assayed against the h22 symbol table — zero unassayed | ledger assay table complete |
| **SW2** | Every hit classified KEEP-with-evidence or FIX-queued — zero unclassified | ledger classification table complete |
| **SW3** | Ledger written at `harness/phantoms/SWEEP-<date>.md`, LOG row appended | file exists |
| **SW4** | Zero FIX edits landed without human forge dispatch | `git status` clean of sweep edits; dry-run default |

## Start rule — idle-only, structural

The sweep starts ONLY when:

1. No other fan-out or workflow is running in the session (main-session judgment at dispatch time).
2. `git worktree list` shows no unmerged `clear/l5*` or `wf_*` build branches with in-flight work.
3. The orchestrator re-verifies both before its first dispatch and REFUSES otherwise — it reports the blocker instead of starting.

## Out of scope

- Full-AST unknown-phantom discovery (L5's scanner; sweep v2).
- Editing `rag/` corpus without human ratification.
- Populating `rulebook/phantoms.json` — proposed in the ledger, gated, never auto-written.
- Building new specialists — the roster is composed as-is (cartographer / assayer / crucible). The ledger writer is a plain workflow agent.

## Falsification conditions

- Hand grep of an in-scope surface finds a seed-symbol mention the ledger missed → missed surface (SW2 fail).
- Any FIX proposal targeting an intentional warning → classification failure. The crucible ledger attack must catch this class every time; one miss = the workflow's KEEP-bias was too weak.
- The harness starts while another fan-out is live → start-rule violation, halt and log.

## Verification strategy

| Layer | What |
|---|---|
| Golden | Seed phantoms all surface with verdicts; CLAUDE.md ⚠ callouts classify KEEP |
| Negative control | A real API (`hou.node`) flagged in a test fixture would verdict `present` — never FIX |
| L3 semantic | Crucible attacks the finished ledger: unassayed seeds, misclassified warnings |
| L4 boundary | An agent tries to: edit corpus, populate phantoms.json, or dispatch forge ungated → must fail structural (orchestrator holds no write tools for these) |

## Gates

Joe holds: SPEC ratification, every FIX dispatch (forge, worktree, no merge), corpus edits, `rulebook/phantoms.json` population, any merge/push.
