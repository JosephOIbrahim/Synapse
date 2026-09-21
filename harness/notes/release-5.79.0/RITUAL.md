# v5.79.0 cut: the exact order, written before the work so nothing is improvised

Standing instruction (Joe, 2026-09-21): "once the currently running agents conclude do the
following commit. git push and git release." This file is the order that instruction is
executed in, written while the graph still runs so no step is invented at the end.

Two corrections from today's two cuts are baked in: **measure the product-surface diff AFTER
the bump commit** (both v5.77.1 and v5.78.0 needed the tag re-cut because a number was typed
before the commit that changed it), and **never run the stock suite and the seat suite at the
same time** (they share a rotating log handler; the loser reports a fake failure).

## 0. Refuse conditions, checked first

Stop and report instead of releasing if any of these is true:

- **master carries commits you did not verify.** Run `git log origin/master..master` and
  `git log v5.78.0..master` BEFORE anything else. On 2026-09-21 a concurrent BP10 orchestrator
  committed its scaffold straight to master mid-wave while this release was queued; releasing
  would have shipped half of another wave to the public repo. If either list is non-empty with
  work you did not verify, STOP and report. Integrate onto the last released tag, not a moving
  master, whenever `harness/notes/h22/orchestrator-*.pid` shows another wave is live.

  **RULED 2026-09-21 (Joe): "merge is pre-approved."** The two BP10 commits on master
  (`5ab7ee9d` scaffold, `357bf1e7` its receipt) are accepted into this release base, and the
  merge step no longer stops for a human. Three things this ruling does NOT do: it does not
  excuse a red gate, it does not make BP10-SCAFFOLD's own receipt a substitute for the composed
  gate (which runs the whole stock suite over the combined tree and so covers it), and it does
  not let the notes go quiet — they must say plainly that BP10's harvest scaffold is in and its
  bench, corpus and crux legs are not. A LATER unverified commit from another wave still stops
  the cut; this ruling covers the two shas named above, not a moving master forever.
- any leg's verifier said BROKEN and its bounded repair did not clear it
- the composed gate reports a FAIL row
- `git status --porcelain` shows a tracked modification I did not deliberately stage
- the audit ratchet exits non-zero on the integration branch
- CI is not green on the exact tagged commit

A partial release is allowed: leaves whose verifier refused are simply not merged, and the
notes say which spec legs did not land and why. A red gate is not allowed.

## 1. Integrate

    python harness/notes/bp9/compose_panel_gate.py --plan     # read the plan, refuse list included
    python harness/notes/bp9/compose_panel_gate.py --merge    # worktree ../pnl-integration, branch pnl/integration

The plan refuses any leaf whose verifier did not set merge_ready. A merge conflict stops the
script with the conflicting paths named; resolve in the worktree, never by re-running blind.

## 2. Composed gate (this is the real gate, not the per-leg green)

    python harness/notes/bp9/compose_panel_gate.py --gate

Seven checks, one at a time: no test file deleted; stock suite alone; panel seat suite alone
under hython; the audit ratchet; the first-click, measure and host-floor probes. An
all-skipped pytest run counts as a FAIL, not a pass. Logs land in `harness/notes/bp9/gate-logs/`.

## 3. Master

    python harness/notes/release-5.79.0/preflight_ff.py           # report
    python harness/notes/release-5.79.0/preflight_ff.py --clear   # then clear
    git merge --ff-only pnl/integration        # fast-forward only; a non-ff means re-integrate

**Why the pre-flight.** Several files started as untracked working copies in the main tree
and were later committed on a branch: the panel spec, the composed gate, the mission file,
this directory. Git refuses the fast-forward over an untracked file it would overwrite. The
pre-flight removes one **only** when it is byte-identical to the integration's version, and
exits non-zero on any difference -- a difference means the main-tree copy carries an edit the
branch never received, and deleting it would silently drop that edit. `compose_panel_gate.py`
is exactly that case: it is edited here and hand-synced to `pnl/gate-fix`. Re-run the
pre-flight after the FINAL `--merge`, not before; each rebuild can add new collisions.

## 4. Version and documents

    edit VERSION -> 5.79.0
    python scripts/sync_version.py --write     # six surfaces
    python harness/notes/release-5.79.0/apply_docs.py --apply --not-landed "<md>"

`apply_docs.py` does the README banner and "is Latest" tag, the "New in 5.79.0" block, the
release-notes links, the CHANGELOG entry and docs/releases/v5.79.0.md, leaving
`{{PRODUCT_DIFF}}` as a placeholder. It asserts every anchor, so a drifted README fails loud
rather than writing nothing.

**The two scripts overlap on one line and the rehearsal found it.** `sync_version.py --write`
rewrites the banner's VERSION but not its `tags: ... is Latest`, so whichever runs second
meets an anchor the other consumed. `apply_docs` is now idempotent on that line and either
order works.

Also stage the evidence this work produced and the main tree still holds untracked or modified:
`docs/design/PANEL_TYPE_AND_COMMANDS_2026-09-21.md`, `harness/notes/bp9/RULINGS.md`,
`harness/state/resolved.json` (the A1/B1 rulings landed through `scripts/ingest_rulings.py`),
and the four `harness/jev/ledger/bp9.*.jsonl` routing ledgers. Do NOT stage `Claude outputs/`
(session scratch) or the unrelated untracked battleplan run directories.

## 5. Commit, then measure, then fix the number

    SYNAPSE_GATE_C=1 git add <the list above>
    SYNAPSE_GATE_C=1 git commit -F harness/notes/release-5.79.0/commit-msg.txt
    python scripts/product_surface.py --diff v5.78.0 HEAD      # NOW it is true
    -> paste the real files/insertions/deletions into the notes, the changelog and the body
    git commit -F harness/notes/release-5.79.0/diff-fix-msg.txt

## 6. Tag, push, CI, publish

    python scripts/tag_release.py --check-only
    python scripts/tag_release.py
    SYNAPSE_GATE_C=1 git push origin master v5.79.0
    python scripts/release_ci_gate.py v5.79.0 --wait-minutes 40      # green on the tagged sha, or stop
    gh release create v5.79.0 --latest --title "..." --notes-file harness/notes/release-5.79.0/release-body.md
    gh release view v5.79.0 --json body -q .body   -> compare byte-for-byte with the source file
    gh api repos/JosephOIbrahim/Synapse/releases/latest -q .tag_name  -> must read v5.79.0

No installer in this release, as in v5.77.1 and v5.78.0; the notes must say so plainly.

## 7. Afterwards

Re-render and republish the board, update the memory entries, and report: what landed, what
did not, every verifier verdict, and the composed gate's summary lines.
