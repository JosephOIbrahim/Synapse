# v5.97.4 - Source release preparation

Source-only cut of one ruled candidate, L-PANIC-WS, built as two arms. No installer
payload is selected and no live installation is changed. See
[public release notes](../../docs/releases/v5.97.4.md).

## Inputs

- **Base:** `545c13eedf6f94f9b89c94ced5025fecbfb74158`, origin master at scoping
  time (PR #115, docs only).
- **Fix commits:** `274792c5` (the dispatch arm in `SynapseHandler.handle()`) and
  `f5c92110` (the three session-tracker arms). They replay the verified commits
  `897c888c` and `20fa5ad2`; `git patch-id --stable` is identical for each pair.
- **Tree at `f5c92110`:** `480f347fff5a8f7e79c9f23d41c8fc5cc9bba5f5`.
- **Test pins:** `a7eac233` (tests only; `python/` unchanged). It replays the
  verified `5a4464b7`: same parent `f5c92110`, identical `git patch-id --stable`.
  Tree at `a7eac233`: `1cbb3922b66cefbac42036773e939b1cf7ea939a`.
- **Ruling:** takeover record `results/REL5974_SCOPE.json`. The authoritative card
  is `"S-REFUTE [opus-fallback]".final_release_card_steps`; the notes claims come
  from its `final_items[*].notes_claim`.
- **Build and verification:** takeover record `results/REL5974_BUILD_PARTIAL.json`.
  Both verifiers returned `SOUND-WITH-NITS`. `a7eac233` pins the coverage-gap
  nits (independent mutation runs: `release/targeted_vpins_*.txt`); what remains
  is stated as limits in the public notes.

"Takeover record" means `Claude outputs/synapse-takeover-2026-10-17/`, which is
local and git-ignored.

## Release gates

- **PRE-0.** CI on the base must have concluded success on all six
  `test (os, py)` jobs before the base is final. Re-check
  `git ls-remote origin refs/heads/master` and `gh release list --limit 1`
  before card 16. Docs-only movement of master means re-base and redo the proofs;
  any `python/` or `tests/` movement means re-rule.
- **Cards 1 and 2.** `VERSION` is `5.97.4`; `scripts/sync_version.py --write`,
  then `--check` (`verdict=PASS`).
- **Cards 3 and 4.** README, release notes, CHANGELOG entry, the current-release
  lines of `docs/status.md`, this note, and one sentence in
  `docs/architecture/overview.md`. README's `tags:` line equals `VERSION`. The
  Moneta pin is unchanged. The stale `## Unreleased — backfill` CHANGELOG
  heading stays, and the notes say so.
- **Card 4b.** An independent agent, neither the drafter nor the CTO, checks
  every notes sentence, the reply's error string and both log texts against the
  code, and cuts what it cannot map. It maps or cuts the `MONETA_NATIVE=0 ...
  keeps it out` clause. Cutting it from the reply is a change to `handlers.py`:
  its own commit, and the proofs re-run.
- **Cards 5 to 9.** NOT_APPLICABLE_TO_SOURCE_PAYLOAD: no Setup, TestSetup,
  fixtures or 19-check harness, and no assets. Not labelled PASS.
- **Card 10.** The hermetic full suite at the release tree through
  `release/run_targeted_safe.sh` (`release/run_targeted.sh` plus a live-test
  lockout and a refusal while Houdini runs), compared with the PRE-2 baseline at
  the base, and a CPython 3.13 run with `python -VV` recorded
  (`release/run_targeted_safe_py313.sh`). Never alongside another suite or a
  seat run.
- **Card 11.** Held: the hython seat suite needs Joe's own go.
- **Card 12.** Not run: `installer/` is unchanged.
- **Card 13.** `SYNAPSE_GATE_C=1 git add`, then `git commit -F <file>`. If the
  session holds no words of Joe's own asking for this commit, stage it and fold
  the commit into his push go after he reads `git diff --cached`.
- **Cards 14 and 15.** `scripts/tag_release.py --check-only`, then the local
  annotated tag under the real home.
- **Cards 16, 16b and 18 are Joe's acts.** The fast-forward push to master, the
  tag push after a green `scripts/release_ci_gate.py v5.97.4` (16a), and
  `gh release create`.

## Fill markers

The draft left numbers it could not produce yet as markers. Resolve every one
before the release commit:

    grep -n "fills:" docs/releases/v5.97.4.md CHANGELOG.md

- `CARD 10 fills`: the broad set, the two new files together, the 3.13 run, the
  release-file readers and the ratchet at the release commit. Filled from
  `release/targeted_full_cut_a7eac233.txt`,
  `release/targeted_py313_cut_a7eac233.txt`,
  `release/targeted_readers_cut_final.txt` and
  `release/except_ratchet_cut_final.txt`.
- `CARD 13 fills`: the diff stat at the tag, filled from the staged index
  (`git diff --cached --shortstat v5.97.3`), and Joe's go. The preparing session
  held no words of Joe's own asking for this commit, so the notes say the commit
  is folded into his push go.

## What this cut does not claim

- No hython, Houdini session or real Rust module ran for either arm. The 3.13
  run used Houdini's bundled CPython 3.13.10 as a plain interpreter, not hython.
- "9 of 16 fail first" adds two per-commit runs on the base. The two files ran
  together at `5a4464b7` (the verifier's runs) and at the release tree, where
  all 25 of their cases pass; they have not run together on the base.
- The notes do not say which version the artist seat runs. The seat moves only
  when Joe lands it with Houdini closed.
- The owner's goal relayed to the release workflow is context, not consent.
