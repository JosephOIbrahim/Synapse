# Release preparation: v5.84.1

The user asked to verify GitHub and the release include all of today's
revisions. The audit found origin/master and v5.84.0 at
`897e30ef3cf546d1e46b6ffeab1477c755f424f4`, while installed master was one
commit ahead at `b92e4feac58298ab9fdc57082cbfc857f66e60aa`.
That commit changes only the resize painter's label to `Resize`.

v5.84.1 preserves the published v5.84.0 tag and advances the release to include
the missing commit. It continues the established source-release format;
the older v5.75.2 Windows installer remains explicitly identified as older.
No downloaded corpus, local settings, credentials or untracked user files
are staged. No additional live Houdini action is needed to cut this release.

The label change already passed independent review, four native grip behavior
checks, and Computer verification in the running 22.0.400 panel. Release
preparation rechecks version/public surfaces and the grip controls, then
requires independent review, the clean-tree tag gate and successful four-job
GitHub CI on the exact tagged commit before tag push and publication.

The focused release check passed 49 existing tests using Houdini 22.0.400's
Python 3.13 and native Qt: four grip, 11 version, 28 tool-count/public README,
and six product-surface checks. No assertions were changed for this patch.

The local board `checks/release-5.84.1-20260924` retains today's master commit
inventory, review, test output, remote refs and final publication receipt.
Every inventoried commit must be an ancestor of the final release commit;
remote master, peeled tag and final local master must match. This preparation
record does not claim those later publication steps have already completed.
