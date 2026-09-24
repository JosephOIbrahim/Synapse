# Release preparation: v5.84.0

Authorized by the user on 2026-09-24: commit, push and publish a bumped release.
The product candidate is `d5a2e9e7ef483211125a7bcb33dbc4624fe1765a`, nine commits
after v5.83.0. Preparation changes version strings and documentation only.

## Distribution

Continue the source-release format used for v5.80.0 through v5.83.0. The previous
published release has no installer assets. This release does not build or
qualify a Windows installer, and does not claim the release card's installer
qualification results. README and installation guidance identify v5.75.2 as the
older packaged installer and direct current-version users to source installation.
The existing v5.75.2 Setup and checksum assets were observed on GitHub.

Downloaded SideFX documentation, the local corpus database, ignored connection
configuration and credentials are excluded from the release. No live Houdini
reload, scene edit or local installer execution is part of cutting this release.

## Local evidence

The isolated release worktree ran 13 existing test files with Houdini 22.0.400's
Python 3.13 and native Qt, offscreen: **287 passed, 1 skipped**. The skip is the
SideFX reader's Windows symlink-privilege check. That initial release-preparation
run changed no tests or assertions.
The run includes panel editorial/design/submenu/model-picker/palette/World Labs
checks, SideFX reader/builder/downloader/Markdown checks, version conformance,
tool-count/public README checks and product-surface checks.

Commands and detailed receipts are in the local release board
`checks/release-5.84.0-20260924` in the SYNAPSE_Refactor workspace, including
`run_native_checks.py`, `native-checks.txt`, `native-checks.xml` and `bus/`.
The six canonical surfaces agree after `python scripts/sync_version.py --write`.
The public release notes retain the upstream 404s, incomplete web-fetch status,
document-only runtime authority, and measured short-dock layout regression.

## CI correction before publication

The first candidate, `6c51d2c2`, failed CI run `36052675251` with four failures:
the deployment environment table omitted `SYNAPSE_SIDEFX_CORPUS_ROOT`; the
CAMERA constructor guard still pinned the earlier resize grip; the QSS guard
still pinned older focus colors; and one negative control used a retired
focus-rule anchor. The release remained unpublished.

The correction documents the environment override and records exact,
count-checked guard amendments for the user-requested changes already in
`90e72706` and `d5a2e9e7`. Literal baselines, constructor equality, selector
coverage and existing negative controls remain intact. Additional negative
controls reject incorrect grip scale/accessibility/drag state and restoration
of the retired focus colors. No runtime source changes are part of this
correction. Independent review and native guard-check artifacts are retained
in the release board. All 115 tests across the environment, CAMERA and QSS
guard modules passed under Houdini 22.0.400's Python 3.13, including native Qt
subprocess checks. Publication still requires a fresh successful CI run on
the corrected commit, using a newly checked local tag before its first push.

## Publication sequence

1. Independently review the release diff and exact file hashes.
2. Commit the synchronized version and notes with the user's authorized Gate C
   environment variable scoped to that command; fast-forward the installed master.
3. Run `python scripts/tag_release.py --check-only`, then the full tag gate.
   Require clean tracked files, version agreement and passing pre/post conformance.
4. Push master, using Gate C for that one authorized command.
5. Run `python scripts/release_ci_gate.py v5.84.0` against the tagged commit.
   The full stock test, JEV and production-memory checks run in GitHub's Ubuntu/
   macOS × Python 3.11/3.14 matrix. Refuse publication if the exact commit is not green.
6. Push the tag, then create the GitHub release with `--verify-tag`, `--latest`
   and a notes file identifying the source distribution and actual CI result.
7. Verify remote master, the peeled tag commit, the published release and Latest.

This committed preparation record does not assert that a later network action
has already happened. The final local receipt and published release carry the
observed commit, CI run and release URL after those steps complete.
