# program.md: how the substrate workers behave

Joe edits this file. Workers read it every iteration. The loop enforces the
parts it can (frozen paths, forbidden additions, gates); this file carries the
rest.

## What you are doing

You improve one memory substrate (Moneta, SALUS, Hanish, Octavius or the
SALUS-Moneta shim) toward one mission objective, one small change at a time.
A change is kept only when every test in the substrate passes, SYNAPSE's own
tests against it still pass, and the mission's number gets strictly better.

## Rules

1. **Fix the cause, never the signal.** Do not add `# noqa`, `# type: ignore`,
   skips or xfails. Do not delete code that a finding points at unless the code
   is genuinely dead.
2. **Tests and specs are frozen.** You cannot edit `tests/`, the blueprint or
   architecture docs. If a test looks wrong, say so in your WHY line and change
   nothing.
3. **Locked decisions stay locked.** Moneta's four-operation API, its decay
   math and its write ordering are not yours to change. SALUS reads and never
   writes. Hanish's `capture()` never raises into its host.
4. **Small diffs.** One idea per change. A small kept change beats a large
   discarded one.
5. **Absence is a fact.** If something the code needs is not installed, the
   right behaviour is an honest UNAVAILABLE, never a fabricated success.
