# Release preparation: v5.84.2

Publish the completed JEV / TypeSafe key-entry update in commit
`ec0ce5d0e8ce36af15c0ec3b84112eac4b06d61f`, on top of v5.84.1.
The implementation is already committed and applied to the open Houdini 22.0.400
panel. Its board, `checks/jev-key-setup-20260924`, records independent review,
87 passing native checks, four effective mutation controls and the live refresh.
No real credential was entered, sent or authenticated during those checks.

This patch release moves the six version surfaces together, updates current
release links and describes the new setup path. It preserves all earlier tags
and the older v5.75.2 Windows installer. No credentials, settings, documentation
caches or unrelated untracked files are staged. No further live GUI change is
needed for publication.

The release board is `checks/release-5.84.2-20260924`. Before commit, the release
candidate must pass the composed JEV/native and version/public-surface checks
and an independent review. The clean-tree tag gate creates the local annotated
tag. Push master, require all four CI jobs on the exact release commit, then push
the tag and publish. Finally verify GitHub master, the peeled tag and local
master match; v5.84.1's tag identity must remain unchanged.

The composed native candidate run passed 132 tests with no skips. Runtime JEV
files and tests are unchanged from the independently reviewed implementation.

This preparation record does not claim that the later CI, push or publication
steps have already completed. Their receipts belong to the release board.
