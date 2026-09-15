# v5.70.1 — cut straight to Latest, docs-only

Kept as the record of how this release was cut, and of what the qualification does
and does not cover.

## Why a release with no product change

Since `v5.70.0` every commit was documentation or harness state. Two of those are
artist-facing: the README rewrite and the setup guide's download links, which had
pointed at 5.68.0 for three releases. A GitHub-only fix would have left every
installed copy's `getting-started.html` and the release page's notes behind; a
patch release carries them. The product is identical and the notes say so in the
first line.

## Order of operations

1. `VERSION` 5.70.0 → 5.70.1, propagated by `scripts/sync_version.py --write` to all
   six surfaces. README `tags:` line, download and checksum links, "New in" block and
   release-notes links hand-edited; `docs/getting-started/installation.md` links
   bumped from 5.68.0 to 5.70.1.
2. README rewrite verified by three independent critics before the build: Law-2
   (every number, link and claim has a producer), ADHD form per the documentation
   convention, and content loss against the previous README.
3. Moneta bundle digest checked BEFORE the build: `moneta-local.zip` sha256
   `81a3d873…` — byte-identical to the reviewed, authorized 1.2.0rc1 bundle.
4. **Build, then qualify, then commit.** Stock suite, seat suite and installer unit
   checks ran serially and alone (see the trap below). The release notes and
   changelog were written from the measured numbers after the build, so `docs/` in
   the payload is one edit behind the tag; `python/` and `installer/` differ from
   v5.70.0 only by the version string in `python/synapse/__init__.py`, and the
   payload was built from the bumped tree (`git diff --stat v5.70.0 v5.70.1 -- python installer`).
5. `scripts/tag_release.py`, then the Gate C push scoped to one command, then
   `gh release create` in a separate command — never chained with the gate.

## Measured

- Stock suite: 8920 passed, 430 skipped, 625 warnings in 346.60s (0:05:46)
- Seat suite (hython 22.0.400, `SYNAPSE_HYTHON` pinned, alone): 5 failed, 201 passed, 38 warnings in 75.63s (0:01:15)
- Installer unit checks: 37 passed, 1 warning in 7.92s
- Installer qualification: 19 of 19 PASS, exit 0
- Build revision: 1d8baae24568aeb3e4d280cdfd804aae8d6d2b93; payload sha256 e603cfb3386579710fa5735c26ba69ca220fbbcc10de15929b5b4ebf2d186406; payload_id 5.70.1-325d5be06597f1f8
- CI on the tagged commit: PENDING_AT_PUBLICATION

## Traps that still hold

**The seat suite and the stock suite must not run at the same time.** Both rotate
`~/.synapse/logs/synapse.log`; the loser reports a plausible timing failure in its
own subject matter. Both numbers above were measured alone, in sequence.

**`python` on this shell is 3.14, not the repo's 3.13.** The stock suite runs on 3.14
with the vendored SDK inactive, as it did for 5.70.0; the seat suite runs on Houdini's
3.13.10. The two numbers are not comparable to each other and are not compared.

**Two Houdini 22 builds are installed (22.0.400 and 22.0.429).** The hytest shim picks
the newest unless pinned; it was pinned to 22.0.400 for this release.

## What is NOT behind this Latest

- The installer is **unsigned**.
- No clean Windows machine, no native wizard visual qualification.
- The upgrade path was exercised with a synthetic prior payload, not a historical
  released installer.
- Five panel seat tests remain red; none is new in 5.70.1.
- The suite's skip population is still not stable — see
  `harness/notes/SUITE_FLOOR_IS_NOT_STABLE.md`.
- No live-Houdini introspection was run for this release: there is no changed
  module to look for. The 5.70.0 live check remains the last one.
- The bridge-down send-queue defect named in the release notes (FR-1 in
  `harness/notes/closeout-2026-09-15/`) is disclosed, not fixed.
