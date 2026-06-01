# FORUM — proposals · CRUCIBLE critiques · results

> **Logical layer:** FORUM. **Authored at:** INGEST (scaffold only).
> Net-new harness file. Coordination happens THROUGH this shared state — no
> central planner. Every wiring proposal gets adversarial CRUCIBLE review here
> **before** FORGE pays the execution cost. Weak claims die here.

**Status at INGEST: EMPTY by design.** FORUM entries are written during
DELIBERATE ⇄ EXECUTE, which begin only **after** the SPEC is ratified. INGEST is
a seeding gate; it does not deliberate, propose, or critique a fix. Seeding any
proposal here now would cross the gate.

## First entries (written only after ratification)

The first DELIBERATION is fixed — not open structure-discovery:

1. **VERIFY-THE-AUDIT** — for each of R / O / S / F / E, confirm-or-falsify the
   audit's file:line claim against live code (the first FORGE action per line).
   CRUCIBLE's job: find the hidden second call site, the missing `__init__`, the
   guard that's false for a different reason than stated.
2. **RESOLVE THE ORDERING FORK** — close the one-liners onto today's store and
   migrate later, OR build the two-tier substrate (Line C) first? Record the
   decision and its evidence here. CRUCIBLE must confirm the swap-seam
   (`deposit_fn`, `SYNAPSE_MEMORY_BACKEND`) actually exists at each cited point
   before the fork is settled.

## Entry format

```
### [<phase> | line <X>] <one-line proposal>
PROPOSAL   — the change + the verifier ladder + expected effect
CRUCIBLE   — the adversarial critique (the hidden cost, the second call site…)
RESULT     — PASS / FAIL / FALSIFIED, with the verifier evidence
```
