# Release card — SYNAPSE v5.101.0

**Status: GATED on the crux review.** Steps 1 and 2 run first; nothing from
step 3 on runs until the review passes.

```
+== GATE: v5.101.0 RANGE CRUX ===============================================+
| Blocked by : the Codex crux review of v5.100.0..<reviewed tip>             |
| Tip        : the commit that carries this revision of this card            |
| Record     : harness/notes/release-5.101.0/CRUX-RECORD.json                |
| Scope      : master as it is. The receipts lane is NOT in this release.    |
| Revised    : 2026-11-14 pre-crux fix round; drafted 2026-11-11             |
| Author     : Claude Code. Every number below names its producer.           |
+============================================================================+
```

Nothing in this card has been executed. `VERSION` is still `5.100.0` and no tag
exists beyond `v5.100.0`. This revision was written on `a1ea943e`, the
decision-2 revision of this card, whose parent is local master `8fcdca29`.
Neither was pushed; `origin/master` was `2cde3bf5`. Those lines are the card's
only live claims: re-read them before acting.

**Joe's go, 14 November 2026.** It covers the commit, the push, the release,
`TAGS.md`, the logo and the README, "when you are ready using CTO best
practices". Later the same day: "When the card fix round passes its verifiers,
commit it, land and push master, run the Codex crux review on the new card
commit, and keep going toward the release." The go replaces no check below.
Each step still waits for its own gate: a passing crux record before step 4,
a passing build and qualification before the push, CI green before the tag, the
CI gate before the tag push.

**Why this revision.** Joe, 14 November 2026: "Do decision 2: update
harness/notes/release-5.101.0/RELEASE_v5.101.0.md so it describes v5.101.0
without the receipts lane." The first version of this card planned two lanes and
was gated on the receipts lane's own crux review. That version, with its trial
merge, its two-lane notes draft and its release-guard runs, is kept in git:
`git show 8fcdca29:harness/notes/release-5.101.0/RELEASE_v5.101.0.md`.

**Why the fix round.** The same day, a CTO pre-crux read of `a1ea943e` decided
**fix, then crux**: six card fixes (RG-1, CARD-1, CARD-2, CARD-3, CARD-4, TG-1)
and no code change. This revision applies them, folds in CARD-5 to CARD-9,
and takes the fixes that two independent verifiers of the revision asked for.
One verifier finding reverses half of CARD-4: README line 7's `tags:` text moves
in the release commit, not after the tag, because
`tests/test_phase0c_doc1_toolcount.py:176` pins it to `VERSION`. The error was
in the read's fix text.
The read's lens findings, refuter verdicts and decision are in
`<build-root>/v51010-graph/precrux-journal.json`; the verifiers' issues are in
`<build-root>/v51010-graph/moe-journal.json`. Both are outside the repo.

Two of the decisions the read put to Joe were then closed by the orchestrator
under Joe's delegation, on the read's recommended options: the timing branch
stays two merges (section 2), and decision 4's hardening lane lands after the
tag (section 4.3). Joe confirmed both the same day: "All other decisions as
you've taken them." The same message ruled QC-Q3: "QC-Q3: keep 2.0 s." A
later message ruled leg C's machine precondition for v5.101.0 (step 6a).

---

## 1. What v5.101.0 is

Master as it is, compared with `v5.100.0` (`7f8c5ec3`).

| Part | Ships in Setup? | Producer |
|---|---|---|
| **The brain-stack import diagnostic,** `python/synapse/host/daemon.py`, +36/−9 | **Yes**, the only shipped file the range changes | `scripts/product_surface.py --diff v5.100.0 a1ea943e` |
| **The Render QC timing harness,** `harness/vision/qc_timing/` and its closure predicate | No | `RUNTIME_TREES` in `installer/build_payload.py` has no `harness/` entry |
| **The release gates:** the crux record and its bindings in `scripts/tag_release.py`; the tagged-tree path check in `harness/jev/jev_release.py` | No | `scripts/` and `harness/` are outside the payload |
| **Developer side:** the run identity stamp in `conftest.py`, the ratchet's interpreter check, the panel `-I` child fix, the daemon real-probe test, `harness2 --out`, `TAGS.md`, the salience test pin, the timing test's sentinel strings | No | same |

**"The only shipped file" is true of the range, not of the release.** The
release commit (section 4.2, step 4) also rewrites the version string in four
shipped files: `VERSION`, `pyproject.toml`, `python/synapse/__init__.py` and
`docs/help/index.html`. Producer: `RUNTIME_FILES` and `RUNTIME_TREES` in
`installer/build_payload.py`.

**Not in this release:**

- **Durable worker receipts** (`qc/recovery-receipts` at `58f23d33`, node
  `NR-RECOVERY-RECEIPTS`). Unmerged, behind its own crux review and the
  never-launched node that precedes `NR-QC-PANEL-ROW`.
- **The always-on agent.** Proposals and a probe receipt only, on the branch
  `proposal/always-on-reconcile`; nothing of it is on master.

**Known limitation that ships (KI-4).** In the daemon's import diagnostic
(`python/synapse/host/daemon.py:498-501`, inside `except ImportError`),
`find_spec` raises `ValueError` when `sys.modules` already holds an `anthropic`
or `pydantic` stub with no usable `__spec__`, such as a bare module object or a
`MagicMock`. That error then replaces the diagnostic's own `RuntimeError`. The
pre-crux read's grep found no current stub in the tree that triggers it. The
notes state it as a known limitation; the fix is for v5.102.0.

---

## 2. The range

**At `a1ea943e`: 51 commits, 17 of them merges.** Producer:
`git rev-list --count v5.100.0..a1ea943e` and the same with `--merges`. The
commit that carries this revision makes it **52 commits, 17 merges**. That
commit is the reviewed tip and the last commit of the reviewed range (section
4.2, step 1).

**26 files other than this card differ from `v5.100.0`, +56,016/−361.**
Producer: `git diff --shortstat --no-renames v5.100.0 a1ea943e -- .
':!harness/notes/release-5.101.0/RELEASE_v5.101.0.md'`. This card is the 27th
file. Its own line count moves with each revision, so it is left out of the
figure. Most of the insertions are the timing receipt,
`harness/vision/qc_timing/timing_receipt.json`. These are the files the crux
record will freeze (section 4.3):

| Area | Files |
|---|---|
| Shipped | `python/synapse/host/daemon.py` |
| Release gates | `scripts/tag_release.py`, `harness/jev/jev_release.py` |
| Timing harness | `harness/vision/qc_timing/` (`README.md`, `decide.py`, `make_receipt.py`, `run_timing.py`, `stage.py`, `test_qc_timing_harness.py`, `timing_receipt.json`) and `harness/next-release/proposals/predicates/test_nr_qc_timing.py` |
| Harness | `harness/harness2/compositor.py`, `harness/verify/checks.py` |
| Tests | `conftest.py`, `harness/harness2/tests/test_compositor.py`, `harness/jev/tests/test_jev_release.py`, `tests/test_daemon_import_diagnostic.py`, `tests/test_identify_salience.py`, `tests/test_panel_alt_entry_unshipped.py`, `tests/test_panel_rhythm_docking.py`, `tests/test_panel_sweep_a.py`, `tests/test_panel_sweep_b_widgets.py`, `tests/test_run_identity.py`, `tests/test_suite_baseline_shape.py`, `tests/test_tag_release_crux_record.py` |
| Docs | `TAGS.md`, `harness/notes/release-5.101.0/RELEASE_v5.101.0.md` (this card) |

**The timing branch is merged twice, and stays that way.** `19a2fb74` and
`db8b43a6` both merge it: the receipt was rebuilt between the two merges, and
the tree carries only the rebuilt one.

- **Closed as two merges** on 14 November 2026: the orchestrator's CTO call
  under Joe's delegation, which Joe confirmed the same day.
- **The reason.** Both merges are already in public `origin/master` `2cde3bf5`
  (`git merge-base --is-ancestor` on each). One merge would mean force-pushing
  public master and running the crux review again. A history rewrite after the
  review makes the tag gate refuse the record as stale (pinned by
  `tests/test_tag_release_crux_record.py::test_commit_not_in_tagged_history_refuses`).

**CI.** The last CI run on master is Actions run `43593998527` on `2cde3bf5`:
six of six `test (os, py)` jobs `success`, 0 failed. `8fcdca29` adds one change
to `harness/vision/qc_timing/test_qc_timing_harness.py`, which CI does not
collect.

**Local suite.** A full local stock suite on the `a1ea943e` tree gave 12,728
passed, 727 skipped, 10 xfailed, 11 deselected and no failures on CPython
3.14.2. Producer: the summary line of
`<build-root>/v51010-graph/stock-a1ea943e/stock-suite.log`, which stamps commit
`a1ea943e`. It was measured before this card-only fix round, and it is not a
release number.

---

## 3. Release notes

**Authored and sentence-checked, not on master.** `docs/releases/v5.101.0.md` and
the CHANGELOG entry are on `scratch/v5.101.0-notes-master` at `4d6c6523`. They
describe master at `2cde3bf5`. An independent sentence check on 14 November found
14 problems; all were fixed before that commit. They land with the release
commit.

**Before the release commit they need:**

1. **The release head.** The notes say "master at `2cde3bf5`". The head is now
   the reviewed tip (section 4.2, step 1), which adds the timing test's sentinel
   strings (one developer-side line) and this card.
2. **The CI table** for the release head. The table in the notes is run
   `43593998527` on `2cde3bf5`.
3. **KI-4 as a known limitation** (section 1), and **QC-Q3 as ruled:** keep
   2.0 s.
4. **Leg C's machine precondition for v5.101.0, as ruled** (section 4.2, step
   6a).

**The release-guard pass is step 8a, after the local tag.** The shipped guard,
`jev_release.py notes`, refuses a tag that does not resolve, so it cannot judge
the notes before step 8. There is no guard pass before the tag.

**The budget sentence.** `docs/releases/v5.100.0.md:388` put QC-Q3 "after
`NR-QC-TIMING`". That is backwards: `B_SECONDS = 2.0` in
`harness/vision/qc_timing/decide.py` is an input to the measurement. The new
notes say so ("The budget is an input to the measurement, not a result of it").
Every mention of the budget must agree with `decide.py` and the receipt's
`rule.B`. QC-Q3 is ruled: Joe kept the budget at 2.0 s on 14 November 2026, so
the notes state it as ruled, not open.

---

## 4. VERSION plan and order

`VERSION` is canonical. `scripts/sync_version.py` is the one observer and the one
propagator, for the surfaces in its `SURFACES` table and no others.

### 4.1 Surfaces

`git grep -l "5\.100\.0" a1ea943e -- ':!docs/releases'` returns 11 paths: the rows
below and this card, which quotes the version as history.

| Surface | Changes on release? | In the crux range? |
|---|---|---|
| `VERSION` | **Yes**, `5.100.0` → `5.101.0` | No |
| `python/synapse/__init__.py` | **Yes**, via `--write` | No |
| `README.md` | **Yes.** Line 7 moves whole: the banner's version via `--write` (one match, `count=1` in `write_surface`) and `tags: v5.101.0 is Latest` by hand (below). The other 18 lines that name `5.100.0` are reviewed by hand in the README refresh. Lines that point at the current release (`:13`, `:17-32`, `:43` and its section, `:274`, and the `[release's evidence]` link on `:314`) move to `5.101.0`. `harness/notes/readme_check.py`, run by `tests/test_readme_receipt.py`, pins the `[What's new]` (`:13`), `[Latest release notes]` (`:274`) and `[release's evidence]` (`:314`) links to `VERSION`. Lines that state measured v5.100.0 evidence (`:310`, `:312`, `:326`) stay as dated history or are re-measured with a v5.101.0 producer. Line numbers are `a1ea943e`'s. | No |
| `pyproject.toml` | **Yes**, via `--write` | No |
| `docs/help/index.html` | **Yes**, via `--write` | No |
| `docs/getting-started/installation.md` | **Yes, by hand.** Not a `sync_version` surface; `--write` leaves its 8 lines of `5.100.0`. | No |
| `CHANGELOG.md` | **Yes**, the hand-authored entry | No |
| `CLAUDE.md` | **Yes**, the target line via `--write` (`claude_md` in `SURFACES`) | No |
| `TAGS.md` | **Yes**, but **only after the tag** | **Yes**: an edit before the tag refuses it |
| `harness/next-release/proposals/render-qc.amendment.PROPOSED.json` | **No**: its `v5.100.0` mentions are historical rulings | No |

**README and installation.md move together.**
`tests/test_installation_setup_wording.py::test_readme_and_installation_agree_on_the_setup`
fails when README's Setup link moves to `5.101.0` and installation.md does not.
In the pre-crux read's fenced run `card-refute-inst-b`, that case gave 1 failed.
Step 6 runs it.

**README line 7 moves whole, in the release commit.** The banner's version
(`v5.100.0 · Houdini`) moves by `--write`. The `tags: v5.100.0 is Latest` text
on the same line moves to `tags: v5.101.0 is Latest` by hand, in the same
commit.
`tests/test_phase0c_doc1_toolcount.py::test_readme_latest_tag_matches_version_file`
pins the first tags claim to `VERSION` ("README current release tag differs from
VERSION"), so a release commit that keeps `v5.100.0 is Latest` fails step 6's
fenced run and CI. v5.100.0 did the same: its tagged commit `7f8c5ec3` already
reads `tags: v5.100.0 is Latest`. `README.md` is outside the range, so the edit
does not trip the gate. Operator check after the release commit:
`git grep -n 5.100.0 HEAD -- README.md` lists only lines that state dated
v5.100.0 history.

### 4.2 Order

1. **Land this card on master and push master,** behind Gate C, so CI runs on the
   reviewed tip. Land it by fast-forward: a merge commit would become the tip
   instead. **The commit that carries this revision is the reviewed tip and the
   last commit of the reviewed range.** No commit that touches a section 2 file
   lands after it before the tag.
2. **The Codex crux review of `v5.100.0..<reviewed tip>`,** from the brief.
3. **Write `harness/notes/release-5.101.0/CRUX-RECORD.json` from the review, and
   commit it alone:** `version` `"5.101.0"`, `review` (the review's name),
   `reviewer` `"Codex"`, `reviewed_date` the day it ran, `verdict`, `passed`
   `true` (a JSON boolean, not a string), and `commit_range` as two full 40-hex
   SHAs:
   `7f8c5ec3cf6a794691d1df47b0b167f9147e7ac5..<reviewed tip, all 40 hex>`.
   - **`reviewed_date` is on or after the reviewed tip's commit date,** the
     first ten characters of `git show -s --format=%cI <reviewed tip>`, and not
     after the day the gate runs. `crux_record_problem` in
     `scripts/tag_release.py` refuses either.
   - **Write it with Python or pwsh 7,** never Windows PowerShell 5.1. 5.1 writes
     a byte-order mark, and the gate reads the record as plain UTF-8, so it
     refuses the file as "not JSON".
   - **Operator check:** both ends of `commit_range` match `^[0-9a-f]{40}$`, and
     `git rev-parse` of the tip equals the commit Codex reviewed.
4. **One release commit** touching only files outside section 2's list:
   `docs/releases/v5.101.0.md`, the `CHANGELOG.md` entry, `VERSION` and the
   `--write` surfaces (`pyproject.toml`, `python/synapse/__init__.py`, the
   `README.md` banner, `docs/help/index.html`, the `CLAUDE.md` target line), and
   by hand: README line 7's tags text, the README refresh, the logo files that
   refresh points at (under `assets/`, which Setup does not ship), and
   `docs/getting-started/installation.md`. Stage by explicit path, never
   `git add -A`. Then run 7a's diff check, before anything is pushed.
5. **`<python> scripts/sync_version.py --check`** exits 0.
6. **`<python> scripts/tag_release.py --check-only`** reports the gate open.
   `<python>` is the interpreter the fenced runner uses (`C:/Python314/python.exe`
   on the release host), and it needs pytest: the gate runs its own conformance
   test with `sys.executable -m pytest` (`run_conformance`). That run's test
   file reads files and `git tag --list` only. The two conftest files it loads
   do more: the root `conftest.py` runs `git rev-parse HEAD`, `git status
   --porcelain` and `find_spec` probes for its identity stamp, and
   `tests/conftest.py` makes a temporary log folder, removed at exit, and
   imports product modules. It is the one sanctioned exception to the
   fenced-runner rule. Then, on the release commit and before the step 7 push,
   a fenced run:
   `WT_OVERRIDE=<release worktree> bash <build-root>/notes-51010/run-targeted.sh <label> tests/test_installation_setup_wording.py tests/test_phase0c_doc1_version_conformance.py tests/test_phase0c_doc1_toolcount.py tests/test_readme_receipt.py tests/test_reach_public_agreement.py`
   gives 0 failed. Those files pin README content and the version surfaces.
   `test_readme_tool_count_matches_registry` needs the literal
   `**N tools, two paths.**` sentence with N equal to `len(TOOL_DEFS)`, so the
   README refresh keeps it. `tag_release.py` runs only the conformance file,
   and it never reads CI.
   - **6a. Build and qualify, before the push,** as v5.100.0 did: its build and
     legs ran on the release commit, then the Gate C push
     (`<build-root>/rel-51000/R6-RESULT.md`). A red here stops the release
     before the release commit is public.
     - **In a fresh detached worktree at the release commit.** v5.100.0's
       `run-build-and-qual.ps1` refuses any `git status --porcelain` line,
       untracked files included, and its log opens `TREE_OK` on the commit.
     - **6a builds the commit that step 7 pushes and step 8 tags.** Any new
       commit after 6a (a fix for red CI, a merge or rebase after a rejected
       push, or a send-back) runs 6a again on that commit before the push.
       Before 8b, `git rev-parse v5.101.0^{commit}` equals the SHA on 6a's
       `TREE_OK` line. v5.100.0's composer does not check this: it compares
       only payload files with the tagged tree, and it writes
       `--source-revision` into the public build record as given.
     - **What runs.** v5.100.0's scripts in `<build-root>/rel-51000` are the
       pattern; v5.101.0 needs its own copies, made before 6a (8c lists what
       does not exist yet). `run-build-and-qual.ps1`
       builds Setup and runs legs A-executable, B-upgrade and C-production;
       then `run-legs-D2-D.ps1` runs legs D2 and D (`legs-D2-D.log`); and
       `audit_source_archive.py` checks the committed source archive.
     - **Leg C on this machine.** `production_uninstall_registration_absent_before`
       fails here, because this machine already carries SYNAPSE's uninstall
       registration, and `run-build-and-qual.ps1` exits 1 on it before its
       real-seat compare. That is why v5.100.0 ran `run-legs-D2-D.ps1` on its
       own. REL-LEGC-PRECONDITION
       (`harness/next-release/proposals/render-qc.amendment.PROPOSED.json`)
       accepted that one failure for the v5.100.0 Setup qualification only.
       Joe ruled the same for v5.101.0 on 14 November 2026: that one check
       only, and any other leg C failure is a red. The notes' Limits state it,
       as v5.100.0's did (`docs/releases/v5.100.0.md`, Limits), and the result
       goes in the verification record (8c). A failure in any other leg is a
       red too.
7. **Push, behind Gate C:** `git push origin HEAD:refs/heads/master`,
   fast-forward only. `ci.yml` runs on a push to `master` and on pull requests,
   nothing else, so the run that counts is a `push` run on `master` for that
   exact 40-character sha. A feature-branch push gives no run, and
   `release_ci_gate.py` would wait 20 minutes and exit 1. Then CI green on that
   sha. **A human check:** `tag_release.py` never reads CI, so nothing in the
   gate stops a tag on a red or unfinished run.
   - **7a. The diff check, run twice:** first on the release commit after step
     4, before any push; then again immediately before step 8, and after any
     merge to master. `git diff --name-only --no-renames <reviewed tip> HEAD`
     lists only step 4's files plus `CRUX-RECORD.json`. Any other path stops
     the push or the tag. The gate refuses only an edit to a reviewed file; a
     new or other file landing after the tip passes it, and it does not bind
     the `sync_version.py` or the conformance test it runs. Paste both outputs
     beside the record.
8. **Tag with `<python> scripts/tag_release.py`.** It creates an annotated tag
   locally and never pushes.
   - **8a. The release guard, after the local tag and before the tag push.**
     Run in this order, and keep the output of all four beside the record:
     1. `git rev-parse v5.101.0^{commit}` and `git rev-parse HEAD` print the
        same 40-hex SHA, the release commit whose CI step 7 checked. If they
        differ, stop: the guard would judge the notes on disk, not the tagged
        notes.
     2. `git rev-parse v5.100.0^{commit}` prints
        `7f8c5ec3cf6a794691d1df47b0b167f9147e7ac5`. A `--prev` that does not
        resolve sends the model an empty diff.
     3. `git status --porcelain --untracked-files=no` is empty. The guard reads
        the notes from disk, so a clean tracked tree is what makes them the
        tagged text.
     4. `<python> harness/jev/jev_release.py notes --tag v5.101.0 --prev v5.100.0`.
        Its last line begins `-- N claims, M need a human read; ledger ...`,
        and it exits 1 when M > 0. **Prerequisites:** a `TYPESAFE_API_KEY`
        (from the environment, or the user registry environment that
        `jev_client.api_key` also reads), and `SYNAPSE_JEV` not set to `off`.
   - **Reading the result.** M counts the `UNSUPPORTED` and `REFEREE` claims;
     `PARTIAL` is not counted.
     - **The guard did not run** if the ledger row says `fallback` or
       `disabled`: the model was never asked, and every claim reads `REFEREE`.
       Fix the prerequisite and run it again. That is not a send-back.
     - **A send-back** is a claim found false: an `UNSUPPORTED` claim whose
       `[missing: ...]` paths the tagged tree lacks, or a flagged claim that a
       human read confirms is wrong.
     - **A flagged claim that a human read finds true** is recorded in writing
       beside the record, and the release goes on.
   - **The ledger stays out of every commit.** The run appends to
     `harness/jev/ledger/v5.101.0.release.notes.jsonl`, which git does not
     ignore. Keep it beside the record. A send-back release commit and the
     step 9 commit are staged by explicit path, never with `git add -A`.
     Whether to commit the ledger later is a separate call.
   - **The guard judges only the first 20 claims** (`_claims` in
     `jev_release.py` returns `out[:20]`). The notes draft at `4d6c6523` has 49
     claims by the same split. Claims 21 and later get a recorded human read.
   - **The cost if the guard sends the notes back:** `git tag -d v5.101.0`
     (local, never pushed), then steps 4 to 8a again: a new release commit
     staged by explicit path, 7a's first run, steps 5, 6 and 6a, the Gate C push
     and a new CI run (step 7), the tag and the guard.
   - **CI gate on the tagged commit, before the tag push:**
     `<python> scripts/release_ci_gate.py v5.101.0` exits 0. It resolves the
     local tag and reads CI for that commit, so it runs after step 8 and before
     8b. That is where its docstring places it: between the tag and the tag
     push. (The docstring pushes master after the tag; this card pushes it at
     step 7, before.)
   - **Do not use `<build-root>/release-51010/run_release_guard.py` or
     `notes_guard.py`.** Both load their Jev code from
     `<build-root>/rel-51000/wt-release`, which is at `7f8c5ec3`.
     `run_release_guard.py` imports `jev_release` from there, which has no
     `classify_claim`, so `run_release_guard.py:99` raises `AttributeError`
     after the model has already been asked. `notes_guard.py` carries its own
     second copy of the verdict rule. Both hardcode the evidence range
     `v5.100.0..db8b43a6`. A `--ref` option for judging before the tag belongs to the
     decision-4 lane.
   - **What pins the behaviour 8a relies on:**
     `harness/jev/tests/test_jev_release.py::test_notes_judges_named_paths_against_the_tag_it_was_given`
     and `::test_notes_refuses_a_tag_that_does_not_resolve`.
   - **8b. Push the tag:** `git push origin v5.101.0`, on Joe's go, only after
     the CI gate above exits 0. Step 6a's build and qualification passed on the
     tagged commit (its `TREE_OK` SHA equals 8a.1's) before step 7.
   - **8c. The GitHub release, after the tag push.** Publish the assets step 6a
     built, the way v5.100.0 did: its Signing and Downloads sections in
     `docs/releases/v5.100.0.md`, the "Verify 5.100.0" list in `TAGS.md`, and
     its working set at `<build-root>/rel-51000`.
     - **Compose the public records** with a copy of the previous composer,
       made the way `make_composer.py` made v5.100.0's. Its `--final` pass
       needs `--source-revision` and `--ci-run-id`, so it runs after the tag
       exists and CI has concluded.
     - **The assets, six, as v5.100.0 published them** (producer:
       `gh release view v5.100.0 --json assets`): `SYNAPSE-5.101.0-Setup.exe`,
       `SYNAPSE-5.101.0-source.zip`, `SHA256SUMS.txt`,
       `SYNAPSE-5.101.0-Setup.public-build.json`, `installer-verification.json`
       and `moneta-native-0.1.0-win64-clean.zip`. The last is the native input,
       unchanged unless Moneta's pin moves, and the composer's
       `--native-bundle` requires it. Setup is **unsigned**; its hashes live in
       `SHA256SUMS.txt`, not in the notes.
     - **None of this exists for v5.101.0 yet:** no working set, no build
       scripts, no composer.
     - **Then publish.** The CI gate passed before 8b and the tag is pushed;
       only then `gh release create v5.101.0` with the assets. Run each
       mutating command on its own.
9. **After the tag push:** one commit that updates `TAGS.md`, staged by explicit
   path. It is not tagged. README line 7 already moved in step 4.

### 4.3 What must not happen

- **No edit to any file in section 2 after the crux review.** The tag gate refuses
  when a reviewed file differs at the tagged commit, and the review has to run
  again. That includes this card.
- **Decision 4's hardening lane lands after the tag.** It changes reviewed files
  (`scripts/tag_release.py`, `conftest.py`, `harness/jev/jev_release.py`). This
  is the orchestrator's CTO call under Joe's delegation, 14 November 2026,
  confirmed by Joe the same day.
- **No `VERSION` edit before the crux record exists.**
- **No tag on a commit whose CI has not concluded `success`.** A human check: the
  tag gate never reads CI.
- **No release-notes sentence that a check cannot trace to its producer.**

---

## 5. Open gates

| Gate | State | Who closes it |
|---|---|---|
| Land this card and push master | **not done**; Joe's go given | the operator, behind Gate C |
| Codex crux review of `v5.100.0..<reviewed tip>` | **not run**; the brief needs the reviewed tip | Codex, then the record |
| Decision 4's hardening lane, which touches reviewed files | **closed: after the tag.** The orchestrator's CTO call under Joe's delegation; Joe confirmed it on 14 November 2026 | closed |
| Notes updated for the release head, with its CI table, KI-4, QC-Q3 and leg C's ruled precondition | **not done** | a builder |
| Leg C's machine precondition for v5.101.0 | **closed: the same as v5.100.0, that one check only.** Any other leg C failure is a red. Joe ruled it on 14 November 2026 | closed |
| Release guard (step 8a), and a human read of claims 21 and later | **not run** | the operator, after the local tag |
| QC-Q3, whether 2.0 s is the right budget | **closed: keep 2.0 s.** Joe ruled it on 14 November 2026 | closed |
| One merge or two for the timing branch | **closed: two merges.** The orchestrator's CTO call under Joe's delegation; Joe confirmed it on 14 November 2026 | closed |
| Tag `v5.101.0` | **not done**; Joe's go given | the operator, after the crux record passes and CI is green |
| Push of the release commit and of the tag | **not done**; Joe's go given | the operator, behind Gate C |
| GitHub release (step 8c) | **not done**; Joe's go given | the operator, after the CI gate passes and the tag is pushed |

---

## 6. Where this lives

- **Card:** this file.
- **Notes:** `scratch/v5.101.0-notes-master` at `4d6c6523`.
- **The pre-crux read:** `<build-root>/v51010-graph/precrux-journal.json`, outside
  the repo. **The verifiers of this revision:**
  `<build-root>/v51010-graph/moe-journal.json`, also outside.
- **The two-lane version of this card:** `8fcdca29`, and the earlier notes draft on
  `scratch/v5.101.0-card` at `f31aa5d6`. Both are history.
- **The receipts lane:** `qc/recovery-receipts` at `58f23d33`. Not in this
  release.
- **v5.100.0's build and qualification working set:** `<build-root>/rel-51000`.
- **Never write in the Houdini live checkout,** the primary SYNAPSE working copy.
  Every step above runs in a worktree under `<build-root>`.
