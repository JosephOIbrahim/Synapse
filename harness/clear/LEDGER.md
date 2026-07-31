# CLEAR — LEDGER

*Append-only skill ledger. Recipes that survived verification, with when-to-use / when-not.*

## clear-orchestrator per-line Complexity Gate
- **goal:** pick the execution mode per line (SOLO / SIMULATED / ORCHESTRATED)
- **approach:** rate BREADTH × INDEPENDENCE per line; INDEPENDENCE predicted from the dependency graph, measured by contention at REORGANIZE. ≤1 independent line → SOLO; 2–3 or short horizon or no launcher → SIMULATED; 4+ independent + long horizon + expensive rework + launcher → ORCHESTRATED.
- **verifier result:** L4 — crucible confirmed no agent can flip `ratified` or cross Gate C from the orchestrator role.
- **when-to-use:** any new line, and at every REORGANIZE (mode is re-derived, not fixed).
- **when-not:** never run ORCHESTRATED for a single dependent chain — that is SOLO however hard the task is.

## SOLO-downshift on launcher-down
- **goal:** keep building when the external launcher (Workflow tool) is unavailable
- **approach:** per the AutoScientist HONESTY CONSTRAINT, downshift to SOLO and say so. Never narrate parallel agents you are not actually running.
- **verifier result:** ratified into SPEC's Falsification Conditions (a false "in progress" bar fails the bar).
- **when-to-use:** launcher classifier down OR no launcher present.
- **when-not:** when real parallelism exists AND the launcher is up — then ORCHESTRATED is honest and cheaper.