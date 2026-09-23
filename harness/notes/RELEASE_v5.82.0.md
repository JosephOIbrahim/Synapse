# v5.82.0 source-release record

The user authorized commit, push and release on 2026-09-23. The release carries
`782f9dc30b12c723aa8ae983cf278826cdcf3a9c` (Soft Editorial panel) plus the synchronized
version surfaces and release documentation. The preceding release is v5.81.0.

## Qualification

- 141 focused checks passed with Houdini 22.0.400's standalone Python and
  PySide6 / Qt 6.8.3; no live Houdini scene or provider call was needed.
- Independent review verified 48 decorated/native transcript painting cases;
  all retained text and selection ink. Deliberate overpainting failed all cases.
- 79 source/constructor checks passed. Counts overlap other suites.
- The broad Windows run and its failure follow-up were not all green. The
  exact counts and unqualified surfaces are recorded in the public release
  notes; the passing focused checks are not represented as a full-suite pass.
- The build-time JEV design review was not run. No installed panel was reloaded.

Evidence is retained in the task workspace under
`checks/soft-editorial-20260923/`, with release receipts in `release-v5.82.0/`
and the conductor's append-only `bus/release.jsonl`.

## Release procedure

This follows the source-only precedent of v5.81.0. No installer was built or
qualified, no setup asset is attached, and the README continues to identify
v5.75.2 as the existing Windows Setup. Its download is not this release.

The release version is synchronized with `scripts/sync_version.py`. Version,
README channel and product-surface checks run before the release commit.
`git diff --check` and independent release-note review also gate that commit.
Normal repository hooks remain enabled; the user's per-act authorization is
expressed by a command-scoped `SYNAPSE_GATE_C=1` for protected commit/push acts.

Integration is fast-forward only. Publication is conditional on successful
GitHub CI for the exact release commit and the normal pre/post checks in
`scripts/tag_release.py`. The annotated tag is pushed without force; publication
uses `gh release create --verify-tag` with the reviewed public notes. Remote
branch/tag identity, release body and Latest status are checked after publishing.
Final commit, tag, CI and publication receipts are written to the task evidence
board after those acts occur, rather than predicting their success here.
