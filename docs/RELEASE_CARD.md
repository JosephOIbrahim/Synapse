# RELEASE · SYNAPSE

**review → commit → build exact HEAD → qualify actual Setup → push → exact CI → tag → publish**

One isolated worktree and one conductor. Obtain authorization for the specific
release acts under AGENTS.md before performing them. A source review and a green
TestSetup are evidence with narrower scope than the final shipped executable.

## Order matters

Finalize source, synchronized versions and public docs, then commit. Build the
production installer from that clean committed HEAD so its source revision names
the actual payload. A pre-commit candidate can qualify a method or reveal a defect;
it cannot replace final qualification after the source changes. Never edit the
source after the final build and silently reuse its old receipt.

## The ritual

```text
0   select the isolated release worktree; inventory worktrees and owned processes
1   confirm next version/tag is unused and preserve older tags/assets
2   edit VERSION; python scripts/sync_version.py --write
3   hand-edit README download/checksum/what's-new/channel links
4   write docs/releases/vX.Y.Z.md; update CHANGELOG and installation links
5   verify dependency bytes, redistribution rights/notices and archive exclusions
6   run changed tests and meaningful red controls; preserve failures
7   run relevant composed tests on the qualified headless host
8   run the stock suite alone in an isolated environment
9   compare seat failures against the published baseline; do not call failed suites green
10  run installer unit controls and required mutation checks
11  obtain independent review of the exact source; fix and requalify real findings
12  review the exact diff/index; no private logs, keys, stores or personal paths
13  SYNAPSE_GATE_C=1 git add / git commit   scoped authorization for the VERSION commit
14  audit the clean committed source archive and all runtime release inputs
15  build production Setup from exact HEAD with pinned dependency/toolchain bytes
16  qualify THAT executable: integrity/list/extract; compare all embedded maintenance
    files and payload hashes; execute its own embedded engine only in a fenced
    disposable sandbox for fresh install, genuine previous-version upgrade,
    verification, reinstall/tamper refusal, preservation and uninstall; run fresh
    normal configured H22 processes against the isolated installed package
17  SYNAPSE_GATE_C=1 git push origin HEAD:refs/heads/master   scoped one command
    require exact full 40-character SHA, workflow and all six expected CI jobs
    to complete successfully; compare actual hosted source archive with the audit
18  python scripts/tag_release.py --check-only; then create the annotated tag
    run scripts/release_ci_gate.py too; independently retain the stronger full-SHA
    workflow/job check; push only the intended unused tag after all gates pass
19  publish using the explicit existing tag, redacted build report, parsed executed
    verification record and SHA256SUMS; verify remote commit/tag, latest release,
    all asset bytes/hashes and hosted archives after upload
20  installation into the live seat is a separate owner-authorized act
```

These are steps, not one shell command chain. PowerShell must check every exit
code. Never let a failed gate fall through to `gh release create`, which can mint
a tag. Never overwrite an existing tag or asset. From a worktree push `HEAD` to
the named remote branch; local `master` can still name an older release.

## Evidence boundaries

The production Setup wizard must not be run with a different `/DIR` and described
as isolated: package, registry, shortcut and user-data effects have separate
locations. Use the actual archive's extracted engine with an explicit owned
sandbox. Record that interactive wizard/registry/shortcut and clean-machine
qualification remain unverified when those operations were not executed.

A TestSetup build can add harness coverage. Matching payload hashes alone do not
prove all production maintenance files or wrapper behavior. Do not publish a
TestSetup hash as the final production hash.

Never run the stock and seat suites together against shared log directories.
Redirect temporary/log/bridge/ledger/preference paths into owned disposable roots.
Retain the real Git identity for release commits and tags; a scratch HOME can hide
it. Never force-close unknown Houdini processes or erase their scene state.

## Version and publication surfaces

`scripts/sync_version.py` observes seven values in six files: VERSION, pyproject,
`__version__`, module docstring, CLAUDE.md, README banner and Help page. README
download/checksum/channel/what's-new links and CHANGELOG/release notes are manual.
The install stamp changes only when installation actually occurs.

`scripts/product_surface.py` defines the shipped product diff, including root
entry points and vendored libraries. Use it for a product-unchanged claim; do not
substitute an incomplete pathspec. Version synchronization and passing tests do
not establish that product code is unchanged.

Public build reports must omit local payload/compiler/output paths. Public
verification records identify exact source, artifact hashes, commands, parsed
results and honest limits without private logs, credentials or store data.
Preserve failed attempts privately. Archive exclusions do not rewrite Git history;
validate the actual hosted archive as well as the local export.

The tag gate never pushes. `--check-only` is read-only. A missing/unreadable
surface is UNKNOWN and blocks release; do not weaken an assertion to proceed.
