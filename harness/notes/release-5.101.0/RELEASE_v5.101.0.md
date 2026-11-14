# Release card — SYNAPSE v5.101.0

**Status: DRAFT, GATED. Do not execute any step below.**

```
+== GATE: v5.101.0 RANGE CRUX ===============================================+
| Blocked by : the Codex crux review of v5.100.0..<this card's commit>       |
| Record     : harness/notes/release-5.101.0/CRUX-RECORD.json                |
| Scope      : master as it is. The receipts lane is NOT in this release.    |
| Revised    : 2026-11-14 on Joe's decision 2; first drafted 2026-11-11      |
| Author     : Claude Code. Every number below names its producer.           |
+============================================================================+
```

Nothing in this card has been executed. `VERSION` is still `5.100.0` and no tag
exists beyond `v5.100.0`. This revision was written on local master `8fcdca29`,
which was not yet pushed; `origin/master` was `2cde3bf5`. Those two lines are
the card's only live claims: re-read them before acting.

**Why this revision.** Joe, 14 November 2026: "Do decision 2: update
harness/notes/release-5.101.0/RELEASE_v5.101.0.md so it describes v5.101.0
without the receipts lane." The first version of this card planned two lanes and
was gated on the receipts lane's own crux review. That version, with its trial
merge, its two-lane notes draft and its release-guard runs, is kept in git:
`git show 8fcdca29:harness/notes/release-5.101.0/RELEASE_v5.101.0.md`.

---

## 1. What v5.101.0 is

Master as it is, compared with `v5.100.0` (`7f8c5ec3`).

| Part | Ships in Setup? | Producer |
|---|---|---|
| **The brain-stack import diagnostic,** `python/synapse/host/daemon.py`, +36/−9 | **Yes**, the only shipped file that changes | `scripts/product_surface.py --diff v5.100.0 8fcdca29` |
| **The Render QC timing harness,** `harness/vision/qc_timing/` and its closure predicate | No | `RUNTIME_TREES` in `installer/build_payload.py` has no `harness/` entry |
| **The release gates:** the crux record and its bindings in `scripts/tag_release.py`; the tagged-tree path check in `harness/jev/jev_release.py` | No | `scripts/` and `harness/` are outside the payload |
| **Developer side:** the run identity stamp in `conftest.py`, the ratchet's interpreter check, the panel `-I` child fix, the daemon real-probe test, `harness2 --out`, `TAGS.md`, the salience test pin, the timing test's sentinel strings | No | same |

**Not in this release:**

- **Durable worker receipts** (`qc/recovery-receipts` at `58f23d33`, node
  `NR-RECOVERY-RECEIPTS`). Unmerged, behind its own crux review and the
  never-launched node that precedes `NR-QC-PANEL-ROW`.
- **The always-on agent.** Proposals and a probe receipt only, on the branch
  `proposal/always-on-reconcile`; nothing of it is on master.

---

## 2. The range

**At `8fcdca29`: 50 commits, 17 of them merges.** Producer:
`git rev-list --count v5.100.0..8fcdca29` and the same with `--merges`. This
card's own commit adds one more.

**27 files differ from `v5.100.0`, +56,514/−361.** Producer:
`git diff --stat --no-renames v5.100.0 8fcdca29`. Most of the insertions are the
timing receipt, `harness/vision/qc_timing/timing_receipt.json`. With this card,
these are the files the crux record will freeze (section 4.3):

| Area | Files |
|---|---|
| Shipped | `python/synapse/host/daemon.py` |
| Release gates | `scripts/tag_release.py`, `harness/jev/jev_release.py` |
| Timing harness | `harness/vision/qc_timing/` (`README.md`, `decide.py`, `make_receipt.py`, `run_timing.py`, `stage.py`, `test_qc_timing_harness.py`, `timing_receipt.json`) and `harness/next-release/proposals/predicates/test_nr_qc_timing.py` |
| Harness | `harness/harness2/compositor.py`, `harness/verify/checks.py` |
| Tests | `conftest.py`, `harness/harness2/tests/test_compositor.py`, `harness/jev/tests/test_jev_release.py`, `tests/test_daemon_import_diagnostic.py`, `tests/test_identify_salience.py`, `tests/test_panel_alt_entry_unshipped.py`, `tests/test_panel_rhythm_docking.py`, `tests/test_panel_sweep_a.py`, `tests/test_panel_sweep_b_widgets.py`, `tests/test_run_identity.py`, `tests/test_suite_baseline_shape.py`, `tests/test_tag_release_crux_record.py` |
| Docs | `TAGS.md`, `harness/notes/release-5.101.0/RELEASE_v5.101.0.md` (this card) |

**The timing branch is merged twice.** `19a2fb74` and `db8b43a6` both merge it:
the receipt was rebuilt between the two merges, and the tree carries only the
rebuilt one. Whether to rebuild the history as one merge is still Joe's call,
before the tag and never after.

**CI.** The last CI run on master is Actions run `43593998527` on `2cde3bf5`:
six of six `test (os, py)` jobs `success`, 0 failed. `8fcdca29` adds one change
to `harness/vision/qc_timing/test_qc_timing_harness.py`, which CI does not
collect. A full local stock suite on the `8fcdca29` tree gave 12,728 passed,
727 skipped and 0 failed on CPython 3.14.2; that is not a release number.

---

## 3. Release notes

**Authored and sentence-checked, not on master.** `docs/releases/v5.101.0.md` and
the CHANGELOG entry are on `scratch/v5.101.0-notes-master` at `4d6c6523`. They
describe master at `2cde3bf5`. An independent sentence check on 14 November found
14 problems; all were fixed before that commit. They land with the release
commit.

**Before the release commit they need:**

1. **The release head.** The notes say "master at `2cde3bf5`". The head is now
   `8fcdca29` plus this card, which add the timing test's sentinel strings (one
   developer-side line) and this card.
2. **The CI table** for the release head. The table in the notes is run
   `43593998527` on `2cde3bf5`.
3. **A release-guard pass.** `jev_release.py notes --tag v5.101.0` now refuses a
   tag that does not resolve, so before the tag exists the guard runs the way the
   first version of this card ran it: the shipped spec and policy, claims read
   from the notes file, evidence for `v5.100.0..<release head>`.

**The budget sentence.** `docs/releases/v5.100.0.md:388` put QC-Q3 "after
`NR-QC-TIMING`". That is backwards: `B_SECONDS = 2.0` in
`harness/vision/qc_timing/decide.py` is an input to the measurement. The new
notes say so ("The budget is an input to the measurement, not a result of it").
Every mention of the budget must agree with `decide.py` and the receipt's
`rule.B`.

---

## 4. VERSION plan and order

`VERSION` is canonical. `scripts/sync_version.py` is the one observer and the one
propagator.

### 4.1 Surfaces

`git grep -l "5\.100\.0" 8fcdca29 -- ':!docs/releases'` returns 11 paths: the rows
below and this card, which quotes the version as history.

| Surface | Changes on release? | In the crux range? |
|---|---|---|
| `VERSION` | **Yes**, `5.100.0` → `5.101.0` | No |
| `python/synapse/__init__.py` | **Yes**, via `--write` | No |
| `README.md` | **Yes**, via `--write` | No |
| `pyproject.toml` | **Yes**, via `--write` | No |
| `docs/help/index.html` | **Yes**, via `--write` | No |
| `docs/getting-started/installation.md` | **Yes**, via `--write` | No |
| `CHANGELOG.md` | **Yes**, the hand-authored entry | No |
| `CLAUDE.md` | **Yes**, the target line, by hand | No |
| `TAGS.md` | **Yes**, but **only after the tag** | **Yes**: an edit before the tag refuses it |
| `harness/next-release/proposals/render-qc.amendment.PROPOSED.json` | Check: likely `REL-VERSION`, not a version string | No |

### 4.2 Order

1. **Land this card on master and push master,** behind Gate C, so CI runs on the
   reviewed tip. Joe's word.
2. **The Codex crux review of `v5.100.0..<this card's commit>`,** from the brief.
3. **Write and commit `harness/notes/release-5.101.0/CRUX-RECORD.json`** from the
   review: `version` `5.101.0`, the review's name, `reviewer` `Codex`,
   `reviewed_date` the day it ran, `verdict`, `passed`, and `commit_range`
   `7f8c5ec3..<this card's commit>`.
4. **One release commit** touching only files outside section 2's list: the notes,
   the CHANGELOG entry, `VERSION` and the `--write` surfaces, the `CLAUDE.md`
   target line, and the record if step 3 did not commit it.
5. **`python scripts/sync_version.py --check`** exits 0.
6. **`python scripts/tag_release.py --check-only`** reports the gate open.
7. **Push, behind Gate C,** then CI green on that exact 40-character sha.
8. **Tag with `python scripts/tag_release.py`,** then push the tag. Each is Joe's
   word, separately.
9. **After the tag:** update `TAGS.md` in its own commit. It is not tagged.

### 4.3 What must not happen

- **No edit to any file in section 2 after the crux review.** The tag gate refuses
  when a reviewed file differs at the tagged commit, and the review has to run
  again. That includes this card. It also includes the files decision 4's
  hardening lane would change (`scripts/tag_release.py`, `conftest.py`,
  `harness/jev/jev_release.py`), so that lane lands before the review or after
  the tag.
- **No `VERSION` edit before the crux record exists.**
- **No tag on a commit whose CI has not concluded.**
- **No release-notes sentence that a check cannot trace to its producer.**

---

## 5. Open gates

| Gate | State | Who closes it |
|---|---|---|
| Land this card and push master | **not done** | Joe, Gate C |
| Codex crux review of `v5.100.0..<this card's commit>` | **not run**; the brief is drafted | Codex, then the record |
| Decision 4's hardening lane, which touches reviewed files | **not started** | Joe: before the review, or after the tag |
| Notes updated for the release head, with its CI table and a guard pass | **not done** | a builder |
| QC-Q3, whether 2.0 s is the right budget | **open** | Joe |
| One merge or two for the timing branch | **open** | Joe, before the tag |
| Tag `v5.101.0` | **not given** | Joe, after CI is green |
| Push of the release commit and of the tag | **not given** | Joe |

---

## 6. Where this lives

- **Card:** this file.
- **Notes:** `scratch/v5.101.0-notes-master` at `4d6c6523`.
- **The two-lane version of this card:** `8fcdca29`, and the earlier notes draft on
  `scratch/v5.101.0-card` at `f31aa5d6`. Both are history.
- **The receipts lane:** `qc/recovery-receipts` at `58f23d33`. Not in this
  release.
- **Never write in the Houdini live checkout,** the primary SYNAPSE working copy.
  Every step above runs in a worktree under `<build-root>`.
