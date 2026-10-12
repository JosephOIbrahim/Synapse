# v5.97.2 - Source release preparation

Source-only cut for the reviewed seven-fix Solaris candidate. No installer payload
is selected and no live installation is changed. See
[public release notes](../../docs/releases/v5.97.2.md) and
[native receipt](release-v5.97.2/native_validation/native-evidence.json).

Native source commit `b7301f3f985d1c0a9876b8ee629472392422bc26`; baseline
`54cbe14264c29792678d9fd12a11b36ac5f2fd90`. Two product files and one regression
test file constitute that candidate. This cut adds documentation, version metadata
and sanitized original validation tooling, without a behavior change to the
native-tested handler/dependency closure or speculative feature implementation.

## Release gates

- Use canonical VERSION and every value observed by `scripts/sync_version.py`,
  including the help page. README channel/current-release links are hand maintained.
- Preserve ADHD-friendly short blocks and the README's two-orange/black Mermaid
  conventions. Run its existing negative-control receipt and conformance tests.
- Run scoped non-native registration, dispatch/integrity/worker-policy/undo
  contracts. Their host doubles are not interactive production evidence.
- Commit and push only the scoped candidate branch. Require full-SHA exact-final
  CI with all six jobs; do not reuse the native source candidate's historical CI
  as proof of a later documentation/version commit.
- Check tracked-clean real release checkout and `tag_release.py --check-only`.
  No tag/merge/release act happens before the required gates pass.
- Preserve native input equivalence and all failures. Source-release installer
  build/TestSetup/19-check/asset steps are NOT_APPLICABLE_TO_SOURCE_PAYLOAD,
  not silently labelled PASS. A later installer cut needs its own full ritual.

The release CI helper matches an eight-character prefix; final evidence must also
verify the exact 40-character tag/commit/workflow/job identity independently.

No copied-scene net-benefit result, production reload, native outer-undo-group
qualification or new painted-panel seat result is claimed. Whole catalogue and
strict live-probe gates remain outside this minimum native assay and are stated in
the public limitations. Source-only publication does not erase them.
