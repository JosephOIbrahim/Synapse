# Source downloads and the development checkout

Release source downloads omit historical execution records, captured workstation
scenes, local orchestration/configuration and machine-specific diagnostic inputs.
The owner approved this archive policy. Existing Git history and earlier release
tags/assets are preserved; an archive exclusion is not a history rewrite.

Archive exclusions do not make tracked files or Git history private. Older public
records can still be read through a full clone or repository file/history views.
These include a captured development-agent transcript, a disposable memory-store
probe capture and local test/orchestration logs, not merely path placeholders.
An archive path scan is therefore separate from review of newly added tracked
blobs and diffs. New private receipts, logs, keys, stores and backup copies must
stay outside the repository and release artifacts.

Use a full Git checkout for historical qualification, orchestration/hook tests and
checks that read archived harness evidence. Their producers and original bytes
remain in Git. A source download alone is not the complete historical test corpus.
The frozen routed-replay test and its original evidence fixture also require the
full checkout and are omitted together to preserve the captured evidence exactly.
Portable source/tests, installer release tooling, runtime inputs and required
third-party notices remain in the source download. Machine-path examples in active
source and documentation use generic placeholders; configure them for your setup.

The release payload is built separately using the installer's runtime allowlist.
Historical records, local orchestration and the excluded SideFX reference material
are not runtime inputs. Native acceleration remains a local opt-in; this archive
policy does not change the public installer default or install anything.
