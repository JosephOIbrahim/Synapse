# Release card: SYNAPSE v5.102.0

**What this release is.** It removes paths from this project's machines from five
files that reach users, and it widens the release audit so the same paths cannot ship
again unseen. No shipped code changes. The notes are `docs/releases/v5.102.0.md`.

**What this card is.** The plan and the record of the steps before the release commit,
which carries this card. Steps after that commit (6a, the gates, TAGS.md) are recorded
in the release working set outside the repository and in the gate packets Joe reads.
Producers named below as `rel-51020/...` or `v5102/...` are files in that working set.

---

## 1. Joe's words

- **Gate 1 go, 15 November 2026:** "Script the owner-path cleanup locally, with the
  widened audit pattern and one test that scans the five files. Build it as one lane in
  a fresh worktree off master. Run the lane's tests, then the full stock suite on the
  merged tree. Fast-forward local master only on 0 failed. Then: one Codex crux review
  of v5.101.1..lane tip; the crux record; stage the release commit; run the checks; make
  the VERSION commit with SYNAPSE_GATE_C=1 only if all are green; then 6a. Use one new
  agent only: an adversarial reviewer for the new release-notes text. Stop at gate 2
  with the leg results, the check results and the new claims for my read. Stop at the
  first red."
- **The range and three rulings, the same day:** "All recommended. Start the Codex crux
  review on 712ca2c3..1194373d from CRUX-BRIEF-v5.102.0.md and stop at gate 2." The
  recommendations it accepted:
  - the crux range is `712ca2c3..1194373d`, because `scripts/tag_release.py:301-319`
    refuses a record whose range holds a file a later commit changes again, and
    `README.md` changes both in the v5.101.1 docs commits and in this release's commit;
  - leg C: the uninstall-registration check alone is a known machine precondition, as
    for v5.101.0 and v5.101.1; any other leg C failure is a red;
  - the suites that need Houdini are not measured, as for v5.101.1.
- **The gate 2 graph, the same evening:** "Fan out a small team of subagents with MOE
  roles, built as a dependency graph, to take v5.102.0 from the Codex crux result to
  gate 2 as fast as the gates allow, with gates 3 and 4 ready for my go." It allowed
  three more agents: the gate 3 and 4 kit, its independent check, and the gate 2 packet.
- **Deferred by the gate 1 packet unless Joe re-rules:** the other 17 repo-only files
  with local paths (77 locations), the decision-4 hardening lane, the panel design
  build, Step P and the OpenCV prototypes.

## 2. The commits

| Commit | What | Check |
|---|---|---|
| `712ca2c3` | base: `origin/master` after the v5.101.1 docs pushes | CI 6/6 on its push |
| `1194373d` | the lane: five files rewritten, one test added | lane tests below |
| `29b7e906` | `--no-ff` merge on `release/v5.102.0` | tree `76a3c1ec` equals the lane's |
| `a28a6d26` | the crux record, alone | Codex PASS |
| this commit | VERSION 5.102.0, its sync surfaces, README, installation guide, CHANGELOG, notes, this card | 7a, sync check, README/version tests, stock suite on the staged tree |

## 3. Results before this commit

- **The rewrite.** Every count asserted before anything was written: 2/1/1 account
  segments, 409 staging prefixes, 2 anatomy lines. Producer: `v5102/logs/cleanup-applied.md`.
- **Lane tests:** 63 passed, 0 failed, 15 skipped, on `712ca2c3` with the six files
  before they were committed. Producer: `v5102/logs/lane-tests-1.log`.
- **The new test against the old files:** 5 failed, 7 passed. Producer: `v5102/scratch-mut/`.
- **Full stock suite on the merge:** 12,765 passed, 0 failed, 727 skipped,
  11 deselected, 10 xfailed, 554 s; tree clean before and after. Producer:
  `v5102/stock-r1/stamp.txt`. Local master then moved `f58acb4f` to `29b7e906` by
  fast-forward.
- **Codex crux review of `712ca2c3..1194373d`:** PASS, 0 high, 0 medium, 1 low that the
  range did not introduce (the committed semantic index is stale at the base and at the
  tip). The configured model was refused for this account, so the one relaunch named
  the model v5.101.1's review used. Producer: the review and its evidence in
  `v5102-crux/`.
- **The audit pattern:** the widened audit finds 0 account paths in the lane commit's
  archive and in the v5.101.1 Setup payload's text files, and the 4 paths in 3 files on
  the v5.101.1 tree, where the old audit reports 0 findings. Producer:
  `v5102/scratch/audit-dry/`, `audit-mut/`, `audit-old/`.

## 4. Order from here

1. The staged-tree checks, then this commit with `SYNAPSE_GATE_C=1`.
2. Post-commit checks: 7a in committed mode, `sync_version.py --check`,
   `tag_release.py --check-only`.
3. 6a on a fresh detached tree at this commit, then the installer unit tests.
4. **STOP, gate 2:** Joe reads the results and claims 21 onward; the Gate C push waits
   for his go. Precondition: `origin/master` is `712ca2c3`.
5. **STOP, gate 3:** the tag, the 8a guard, the CI gate, compose, the record check, the
   tag push, each on Joe's go.
6. **STOP, gate 4:** `gh release create` and the read-back, on Joe's go. Then TAGS.md.
