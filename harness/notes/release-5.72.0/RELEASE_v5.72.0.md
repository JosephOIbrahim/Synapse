# v5.72.0 - how it was cut

Seven branches merged through a CI-gated train, then the standard ritual.

1. Every PR gated on the **CI matrix only** - the four `test (os, py)` jobs. CodeRabbit is
   advisory and was ignored by construction: on its first pass it reported "pass" because it was
   rate limited, which would have read as a green gate on a PR nothing had reviewed.
2. `master` carries **no branch protection** and `allow_auto_merge` is false, so the gate is
   whoever is merging. That is worth changing.
3. One PR was refused and stayed refused: it edits a constructor pinned by `_PANEL_BASE`, whose
   comment says that source is byte-identical to its landing unless a ruling says otherwise. A
   crit is not a ruling, and re-anchoring the pin to pass one's own branch is precisely the
   isolated-green failure the pin exists to prevent.

## Measured

- Stock suite: 9558 passed, 430 skipped, 625 warnings in 392.28s (0:06:32)
- Seat suite (hython 22.0.400, `SYNAPSE_HYTHON` pinned, alone): 6 failed, 200 passed, 47 warnings in 72.39s (0:01:12)
- Installer unit checks: 37 passed, 1 warning in 6.62s
- Installer qualification: 19/19 PASS, exit 0

The seat suite and the stock suite share `~/.synapse/logs/synapse.log` and must not run at the
same time; they ran alone, in that order.

## What this cut does differently

`step_commit` passes `SYNAPSE_GATE_C=1`. The pre-commit fence shipped in this very release
refuses a staged `VERSION`, and the adversarial pass on that branch found `harness/finalize.ps1`
committing `VERSION` ungated and then tagging regardless - which puts the tag on an un-bumped
HEAD and prints READY. The release script would have hit the same wall on its own bump.
