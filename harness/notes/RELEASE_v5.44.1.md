# v5.44.1 — release truth

One canonical version, gated tags. Root `VERSION` is the single source;
`scripts/sync_version.py` observes and propagates six surfaces (UNKNOWN never
passes); `scripts/tag_release.py` stands between `git tag` and the claim —
refusing on tracked dirt, drift, an existing tag, or anything unobservable.
This is the first release to pass through its own gate.

Also in the tag: `docs/RELEASE_CARD.md` (the operator ritual) and an intake
fix (h22-intake args-as-JSON-string parsed loud instead of silently dropped —
the fix that enabled the SYN-NEXT-001 adjudication run).

Fixes the three-way version split (VERSION 5.44.0 / runtime 5.43.0 / README
5.42.0) and the two CI conformance reds it caused.

Known open, disclosed: abrupt-restart persistence (the PRST pair, xfail-tracked
on master) — the W1 memory-recovery program is next and un-xfails them.

Post-tag on master: Houdini 22.0.400 re-stamp (35,908 symbols, +5/-0) and
`docs/SUPPORT_MATRIX.md` as the standing claims surface.
