# RELEASE · SYNAPSE

**reviewed lanes → merge check → text review → release commit → evidence on that commit → tip review → crux record → tag gate → push → exact CI → tag → publish**

One isolated release worktree (each lane keeps its own) and one conductor. Obtain
authorization for the specific release acts under AGENTS.md before performing
them. A source review and a green TestSetup are evidence with narrower scope than
the final shipped executable.

## Order matters

Finalize source, synchronized versions and public docs, then commit. The release
evidence runs on that commit: the stock and seat suites, the installer tests and
the production installer, built from that clean committed HEAD so its source
revision names the actual payload. The release text is written before that
evidence exists, so it cites only evidence that already exists, naming the tree
each run used, and describes the runs on the release commit as process, never as
results.

After the evidence, review the committed text on the same day as the release
commit, in the committer's offset (`git show -s --format=%cI`), then commit the
crux record. When the tip review needs no fix, the tagged commit differs from the
evidence commit by that one added file. A fix lands as its own text-only commit,
reviewed the same way, and any evidence whose inputs the fix changes runs again.

A pre-commit candidate can qualify a method or reveal a defect; it cannot replace
final qualification after the source changes. Never edit the source after the
final build and silently reuse its old receipt.

## The ritual

```text
0   inventory worktrees and owned processes
1   confirm next version/tag is unused and preserve older tags/assets
2   in each lane's own worktree, run changed tests and meaningful red controls;
    preserve failures
3   run relevant composed tests on the qualified headless host
4   obtain independent review of each lane's exact source; fix and requalify real
    findings
5   create the release branch in a fresh worktree at origin/master; dry-run, then
    git merge --no-ff each reviewed lane
6   run the stock suite alone on the merged tree: a merge check, not release evidence
7   edit VERSION; python scripts/sync_version.py --write
8   hand-edit README download/checksum/what's-new/channel links
9   write docs/releases/vX.Y.Z.md and harness/notes/release-X.Y.Z/RELEASE_vX.Y.Z.md;
    update CHANGELOG and installation links; cite only evidence that exists, with
    its tree, and describe steps 14 to 20 as process
10  verify dependency bytes, redistribution rights/notices and archive exclusions
11  run sync_version.py --check and the tests that read the edited files; review
    the release text on an archive copy, round by round, until a round finds no FIX
12  review the exact diff/index; no private logs, keys, stores or personal paths
13  SYNAPSE_GATE_C=1 git add / git commit   scoped authorization for the VERSION
    commit: the release commit, which carries the version and the release text
14  quiesce: no agent and no other heavy run until step 17 ends; then, on THAT
    commit and one at a time, run the stock suite alone in an isolated environment,
    the seat suite under hython (compare its failures against the published
    baseline; do not call failed suites green), any hython suite the release's
    lanes add, and the installer unit controls and required mutation checks
15  audit the clean committed source archive and all runtime release inputs
16  build production Setup from exact HEAD with pinned dependency/toolchain bytes
17  qualify THAT executable: integrity/list/extract; compare all embedded maintenance
    files and payload hashes; execute its own embedded engine only in a fenced
    disposable sandbox for fresh install, genuine previous-version upgrade,
    verification, reinstall/tamper refusal, preservation and uninstall; run fresh
    normal configured H22 processes against the isolated installed package
18  review the committed release text on the day it was committed, in the
    committer's offset (git show -s --format=%cI); a fix is a text-only commit,
    reviewed the same way
19  commit harness/notes/release-X.Y.Z/CRUX-RECORD.json: reviewed_date is the day
    the review ran; commit_range runs from the previous release's commit to the
    last commit the reviews covered
20  python scripts/tag_release.py --check-only
21  SYNAPSE_GATE_C=1 git push origin HEAD:refs/heads/master   scoped one command
    require exact full 40-character SHA, workflow and all six expected CI jobs
    to complete successfully; compare actual hosted source archive with the audit
22  python scripts/tag_release.py creates the annotated tag on the commit it checked;
    run scripts/release_ci_gate.py too; independently retain the stronger full-SHA
    workflow/job check; push only the intended unused tag after all gates pass
23  publish using the explicit existing tag, redacted build report, parsed executed
    verification record and SHA256SUMS; verify remote commit/tag, latest release,
    all asset bytes/hashes and hosted archives after upload; then commit the
    TAGS.md update (current release, its row and any missing earlier rows, the
    tag object), checked against the live release, and ask its Gate C push on
    its own
24  installation into the live seat is a separate owner-authorized act
```

These are steps, not one shell command chain. PowerShell must check every exit
code. Never let a failed gate fall through to `gh release create`, which can mint
a tag. Never overwrite an existing tag or asset. From a worktree push `HEAD` to
the named remote branch; local `master` can still name an older release.

## What the tag gate checks

`scripts/tag_release.py` captures `HEAD` first, then prints one line per check.
Any check it cannot observe refuses.

- **version:** `VERSION` is readable and not empty. If it is not, the gate
  refuses at once and prints no other check.
- **worktree:** no tracked file has an uncommitted change. Untracked files do not
  block.
- **sync_check:** `scripts/sync_version.py --check` passes.
- **crux_record:** `harness/notes/release-<VERSION>/CRUX-RECORD.json` is a JSON
  object with the non-empty string fields `version`, `review`, `reviewer`,
  `reviewed_date`, `verdict` and `commit_range`, and a `passed` field.
  - `version` equals `VERSION`, and `passed` is `true`. The gate reads `passed`,
    not `verdict`.
  - `reviewed_date` is a `YYYY-MM-DD` date, not earlier than the reviewed tip's
    commit date (the date in `git show -s --format=%cI <tip>`, in the committer's
    own offset) and not later than today (the later of the local and the UTC
    date).
  - `commit_range` is `<base>..<tip>`, two commit SHAs of 7 to 40 hex digits that
    resolve here; base is an ancestor of tip and not the same commit.
  - The tip is in the history of `HEAD`, and the record is committed in `HEAD`'s
    tree, not only present in the working folder.
  - The range changes at least one file besides the record, and none of the files
    it changes has changed between the tip and `HEAD`. Later commits may add or
    edit other files, and the record itself may change.
- **tag_free:** the tag `v<VERSION>` does not exist in this clone
  (`git tag --list`; fetch tags first).
- **pytest_pre:** `tests/test_phase0c_doc1_version_conformance.py` passes. It runs
  only when every check above passed.

`--check-only` stops there: it prints `gate OPEN` and creates no tag. Without it,
the gate refuses if `HEAD` moved while it ran, creates the annotated tag on the
commit it checked, runs the conformance test again and prints the tag's push
command. It never pushes, and it does not read CI or the evidence runs;
`scripts/release_ci_gate.py` reads the tagged commit's CI.

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
`__version__`, module docstring, CLAUDE.md, README banner and Help page. These
are manual: README download/checksum/channel/what's-new links, CHANGELOG, the
release notes and record, the installation page's links, the current-release
lines of `docs/status.md`, `installer/README.md`, `docs/architecture/overview.md`,
`INSTRUCTIONS.md`, `docs/index.md` and `docs/studio/UPGRADE.md`, and `TAGS.md`
(after publish, step 23).
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
