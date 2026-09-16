# v5.73.0 - how it was cut

Six branches, through a CI-gated train, then the standard ritual.

## What this cut has that the last one did not

Three fences, all repaired after being caught in use rather than in review:

1. `pre-push` now gates what a push ADDS rather than what its range sweeps in. The two-dot range
   broke on any force-push after a rebase, sweeping in the upstream release commits and refusing
   branches that touch no protected path.
2. The composer reads VERSION from the repo, targets the dated notes subdirectory, and checks the
   exact keys it was meant to substitute in the text it just built.
3. Slots are an uppercase name between `@@` delimiters. The gate matches that delimiter. Both
   were forced by measurement: stripping code spans before scanning misses a real slot, and not
   stripping fires on prose.

## Measured

- Stock suite: 9585 passed, 434 skipped, 625 warnings in 396.48s (0:06:36)
- Seat suite (hython 22.0.400, `SYNAPSE_HYTHON` pinned, alone): 6 failed, 202 passed, 46 warnings in 72.54s (0:01:12)
- Installer unit checks: 37 passed, 1 warning in 6.26s
- Installer qualification: 19 of 19 PASS, exit 0

The seat suite and the stock suite share a log file and must not run at the same time; they ran
alone, in that order.

## The count that matters

Four defects were found today in safety code written today. Guards are the least-exercised code in
the tree and they carry the same defect rate as what they guard. Every one was found by executing
it against the input it was written for - never by reading it.
