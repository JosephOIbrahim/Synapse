# v5.72.1 - how it was cut

A documentation patch, cut because the two releases before it published placeholder text to a public
page and the fix belongs in the tree, not only in the GitHub UI.

## The gate this release adds

`step_compose` now asserts that no `{...}` placeholder survives in either composed document. The
composer was fixed in the same change, but fixing a producer and checking a producer are different
acts, and today supplied the argument for doing both: the composer already had a guard, and that
guard inspected the wrong file and passed.

## Measured

- Stock suite: {STOCK}
- Seat suite (hython 22.0.400, `SYNAPSE_HYTHON` pinned, alone): {SEAT}
- Installer unit checks: {INST}
- Installer qualification: {QUAL}

## Product delta

One file, two lines: the version string in `python/synapse/__init__.py`, written by the bump step.
`installer/` is untouched.

**A draft of the public notes said "byte-identical" and told the reader to run
`git diff --stat v5.72.0 v5.72.1 -- python installer` to confirm it.** That command refutes it -
the bump step guarantees `__init__.py` differs on every release. It was caught before publication
only because someone actually ran the command the document recommends, which is the whole argument
for recommending one. A claim that invites its own disproof is worse than a vague claim, because
the reader does the work of finding you out.

Same shape as the placeholder failure this release repairs: in both cases the verification existed
and was not performed.
