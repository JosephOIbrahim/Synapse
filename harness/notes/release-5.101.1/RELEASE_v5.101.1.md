# Release card — SYNAPSE v5.101.1

**Status: GATED on the crux review.** Step 1 runs before the review; nothing
from step 3 on runs until the review passes.

```
+== GATE: v5.101.1 RANGE CRUX ===============================================+
| Blocked by : the Codex crux review of b8f14e9e..{{TIP}}                    |
| Tip        : {{TIP}}, the commit that carries this card                    |
| Record     : harness/notes/release-5.101.1/CRUX-RECORD.json                |
| Scope      : master f58acb4f plus one lane, fix/worker-tool-allowlist      |
| Gates      : VERSION commit, Gate C push, tag, gh release create           |
| Drafted    : 14 November 2026                                              |
| Author     : Claude Code. Every number names its producer.                 |
+============================================================================+
```

**Executed so far: the lane's own evidence (section 2), the lane commit and
its merge (step 1). Nothing else.** `VERSION` is still `5.101.0`: a fenced
`scripts/sync_version.py --check` on `f58acb4f`, whose six surface files the range
does not change, read seven values, all `5.101.0`, PASS (log
`cardwriter-51011-sync-check`). No tag exists beyond `v5.101.0`
(`git tag --list 'v5.101*'` prints only `v5.101.0`). The lane commit and the
merge are on the local branch `release/v5.101.1` and are not pushed: the
remote-tracking `origin/master` is `f58acb4f`, and no remote-tracking branch
contains `fe4864a9` (`git branch -r --contains fe4864a9` prints nothing). Those
are this card's only live claims, read when it was drafted. Re-read them before
acting.

**Joe's go, 14 November 2026, in full:** "The allowlist suite is green and
committed. Start the v5.101.1 release with only fix/worker-tool-allowlist using
CTO best practices. Stop and ask me at each gate: VERSION commit, Gate C push,
tag, gh release create." When he wrote it, the lane's first full stock run had
ended with one failure and nothing was committed; the fix, the second run and
the commit followed (section 2.1).

**Later the same evening, in full:** "Keep going: commit the release card on
release/v5.101.1 as the reviewed tip, run the Codex crux review of
b8f14e9e..<tip> from CRUX-BRIEF-v5.101.1.md, write CRUX-RECORD.json if it
passes, stage the release commit, and stop at gate 1 with the diff and
checks."

**His four gates are STOP points in section 4.2:**

- **GATE 1,** the VERSION commit (step 4);
- **GATE 2,** the Gate C push of master (step 6);
- **GATE 3,** the tag (step 7);
- **GATE 4,** `gh release create` (step 8).

Everything between them he delegated "using CTO best practices". The post-tag
`TAGS.md` push (step 9) is another Gate C push, and it is asked on its own. The
go replaces no check below: each step still waits for its own evidence.

**The lane commit waited for a green suite.** An earlier decision batch on the
lane, answered "all recommended", made the commit wait for a full stock run with
no failure. The item is recorded in the header of
`<build-root>/allowlist-mut/run-stock-allowlist-r2.sh`, which dates it
2026-11-15; the run started at 00:45:41 UTC that day, 19:45 on 14 November
locally. The run ended with exit 0 at 00:55:26 UTC (its `stamp.txt`), and the
lane commit is dated 19:55:58 −05:00, 32 seconds later
(`git show -s --format=%cI fe4864a9`).

**Three owner rulings are open when this card is committed** (section 5).
Joe rules them at GATE 1, with the release commit, and his words go into the
Limits of `docs/releases/v5.101.1.md`, which is outside the reviewed range. This
card is frozen once the review reads it, so it never carries them.

**Markers.** `<build-root>` is the release host's build folder, outside the
repository. Each double-brace marker below stands for a value that does not
exist when this card is committed. This card is in the reviewed range, so it is
never edited to fill them in; the table says where each one is recorded instead.

| Marker | Stands for | Recorded in |
|---|---|---|
| `{{TIP}}` | this card's commit, the reviewed tip, 40 hex | `CRUX-RECORD.json`, `commit_range` |
| `{{RECORD_COMMIT}}` | the commit that adds the record | git, the commit after `{{TIP}}` |
| `{{RELEASE_COMMIT}}` | the release commit, 40 hex | the tag; 6a's `TREE_OK` line; the public build record's `source_revision` |
| `{{CI_RUN}}` | the Actions run on `{{RELEASE_COMMIT}}` | the verification record's `ci` block; `TAGS.md` |
| `{{STOCK_RELEASE}}` | the stock suite's counts on `{{RELEASE_COMMIT}}` | the verification record |
| `{{INSTALLER_TESTS}}` | the installer unit tests on `{{RELEASE_COMMIT}}` | the verification record |
| `{{NOTES_CLAIMS}}` | how many claims the guard splits from the notes | the guard's output, kept beside the record |
| `{{OWNER_PATH_HITS}}` | the owner-path count measured in the v5.101.1 source zip | the verification record, `publication_hygiene` |
| `{{TAG_OBJECT}}` | the annotated tag object of `v5.101.1` | `TAGS.md` (step 9) |

---

## 1. What v5.101.1 is

**v5.101.0's master plus one lane,** compared with the `v5.101.0` tag, which
names the release commit `b8f14e9e`. The lane adds an operator ceiling on the
panel worker's tools: `SYNAPSE_WORKER_TOOL_ALLOWLIST`.

| Part | Ships in Setup? | Producer |
|---|---|---|
| **The worker tool ceiling,** `python/synapse/panel/worker_policy.py` (+20) and `python/synapse/panel/tool_bridge.py` (+9/−6) | **Yes**, the only shipped files the range changes | `scripts/product_surface.py --diff b8f14e9e dd816e57`: 2 files, +29/−6 (fenced log `cardwriter-51011-product-surface`) |
| **Operator docs,** `docs/studio/DEPLOYMENT.md` (+1, the variable's row) and `docs/studio/EGRESS.md` (+4) | No | `RUNTIME_TREES` in `installer/build_payload.py:18-19` carries `docs/help/`, not `docs/studio/` |
| **Tests,** `tests/conftest.py` (+25, a session-scoped fixture) and `tests/test_worker_tool_allowlist.py` (new, 183 lines, 25 tests) | No | `permitted()` drops every path with a `tests` part (`installer/build_payload.py:52`) |
| **`TAGS.md`** (`f58acb4f`, v5.101.0's post-tag commit, +10/−9) | No | in neither `RUNTIME_FILES` nor `RUNTIME_TREES` |
| **This card** | No | `harness/` is outside the payload |

Per-file counts: `git diff --numstat --no-renames b8f14e9e dd816e57`. The 25
tests: the allowlist file's own run, `25 passed`
(`<build-root>/notes-51010/logs/allowlist-r8-newfile.log`).

**What the ceiling does,** read from the code at `fe4864a9`:

- **Unset, empty, or only commas and spaces: no ceiling.** `_parse_allowlist`
  returns `None` (`worker_policy.py:64-66`).
- **Set: a comma-separated list of exact advertised tool names,** trimmed and
  de-duplicated in order, and read again on every check
  (`active_tool_allowlist`, `worker_policy.py:69-72`).
- **An unlisted tool is denied before any mode logic,** with "outside the
  configured worker tool allowlist" (`worker_policy.py:185-187`, inside
  `is_tool_allowed_for_worker` at `:161`), in all five modes (`_VALID_MODES`,
  `:52-54`).
- **A listed tool gets the mode's own decision.** The list removes tools and
  never grants one.
- **The worker's advertised roster is cached per mode and list**
  (`tool_bridge.py:111`), so it follows the variable. The full roster,
  `get_anthropic_tools`, is never filtered.

**Where it acts.** Both panel paths that run the LLM worker consult it.
`ClaudeWorker` builds its roster from `get_anthropic_tools_for_worker`
(`python/synapse/panel/claude_worker.py:158`) and, when `enforce_worker_policy`
is on, checks every tool call with `is_tool_allowed_for_worker` (`:722`). The
interactive panel creates its worker with `tools=None` and
`enforce_worker_policy=True` (`python/synapse/panel/synapse_panel.py:4132-4134`)
and routes on the worker's roster (`:2422`). So a set value limits the tools of
the artist's panel assistant, not only an autonomous run.

**The release commit changes shipped files too.** It rewrites the version string
in four of them: `VERSION`, `pyproject.toml`, `python/synapse/__init__.py` and
`docs/help/index.html` (producer: `RUNTIME_FILES` and `RUNTIME_TREES`,
`installer/build_payload.py:18-24`). "The only shipped files the range changes"
is true of the range, not of the release.

**Not in this release.** Joe's go names one lane, so these stay out until after
the tag:

- the durable worker receipts lane, `qc/recovery-receipts`;
- v5.101.0's decision-4 hardening lane for the tag gate and the release guard;
- the fixes that v5.101.0's notes planned "for the next release"
  (`docs/releases/v5.101.0.md:208` and `:220`; `README.md:100`): KI-4, F4 and F5
  in the daemon's import diagnostic, and the four developer-side defects from
  v5.101.0's crux review;
- removing the four owner paths from the source zip, and widening the audit
  pattern that missed them (below).

How v5.101.1's notes word this is the third ruling in section 5.

**Known limitations that still ship:**

- **KI-4, F4 and F5.** `python/synapse/host/daemon.py` is unchanged
  (`git diff --stat b8f14e9e dd816e57 -- python/synapse/host/daemon.py` is
  empty). The three known failures of its import diagnostic, stated in
  `docs/releases/v5.101.0.md` (Limits), still apply.
- **The four developer-side defects** from v5.101.0's crux review: the timing
  harness's resume, the timing closure predicate, the tag script's late HEAD
  check and the identity line. They are stated in the same Limits section, and
  their files are outside this range.
- **Four owner paths in the source zip.** v5.101.0's source zip carries four
  drive-rooted paths into the release host's user-profile folder, in three
  files: `docs/SYNAPSE_MULTI_PROVIDER_LEG1_PROBE_DATA.json` (2),
  `tools/_hy_parity_gui.json` (1) and `tools/_hy_verbs_sweep_22.0.400.json` (1).
  Producer: `publication_hygiene.known_owner_personal_prefix_hit_files` in
  v5.101.0's published `installer-verification.json`. The range changes none of
  the three (`git diff --name-only b8f14e9e dd816e57`), so v5.101.1's zip
  carries them too. Joe ruled for v5.101.0 to ship them with the count measured
  and disclosed (`<build-root>/rel-51010/owner-rulings-2026-11-14.txt`, entry 4).
  v5.101.1's composer measures its own count: `{{OWNER_PATH_HITS}}`.
- **Setup is unsigned.** **anthropic 2.x is unsupported:** the pin stays
  `anthropic>=1.0.0,<2` (`pyproject.toml:57`).

---

## 2. The range

**`b8f14e9e018c5d39a45004b3979875bea3989375..{{TIP}}`.** The base is the v5.101.0
release commit (`git rev-parse v5.101.0^{commit}`).

| Commit | What it is | Producer |
|---|---|---|
| `f58acb4f` | v5.101.0's post-tag `TAGS.md` commit | `git show --stat f58acb4f`: 1 file, +10/−9 |
| `fe4864a9` | the lane commit, on `fix/worker-tool-allowlist`, parent `f58acb4f` | `git show --stat fe4864a9`: 6 files, +242/−6 |
| `dd816e57` | the `--no-ff` merge, parents `f58acb4f` and `fe4864a9`, on `release/v5.101.1` | `git log -1 --format=%P dd816e57` |
| `{{TIP}}` | this card | — |

Full SHAs: `fe4864a9246b5849ad492ffc9564a4aa1abce025` and
`dd816e576d6b1f42de58bad7d9f5d4f8edf99323`.

**At `dd816e57`: 3 commits, 1 of them a merge; 7 files, +252/−15.** Producer:
`git rev-list --count b8f14e9e..dd816e57`, the same with `--merges`, and
`git diff --shortstat --no-renames b8f14e9e dd816e57`. This card's commit makes
it 4 commits, 1 merge and 8 files. The crux record freezes these 8 files
(section 4.3):

| Area | Files |
|---|---|
| Shipped | `python/synapse/panel/worker_policy.py`, `python/synapse/panel/tool_bridge.py` |
| Docs | `docs/studio/DEPLOYMENT.md`, `docs/studio/EGRESS.md`, `TAGS.md` |
| Tests | `tests/conftest.py`, `tests/test_worker_tool_allowlist.py` |
| Card | `harness/notes/release-5.101.1/RELEASE_v5.101.1.md` (this file) |

**`TAGS.md` is a reviewed file.** `f58acb4f` changed it, so the tag gate refuses
an edit to it before the tag (`crux_record_problem`,
`scripts/tag_release.py:301-319`). Step 9 moves it after the tag, as v5.101.0's
card did.

**The merge adds nothing.** `git rev-parse dd816e57^{tree} fe4864a9^{tree}`
prints `31f13f4466c4ae4d90e46ac965265774d40ee2c5` twice: master had not moved.

### 2.1 The lane's evidence

All of it ran before the lane commit. The targeted and stock runs ran on the lane
worktree (`f58acb4f` plus the six files, uncommitted); the mutation battery and
the control ran on copies of it under `<build-root>/allowlist-mut/`. The four
pytest logs below come from the fenced runners (scratch home, temp and log
folders, `SYNAPSE_JEV=off`, a dead inspector port, `-m "not live"`), and each
one's session header names CPython 3.14.2 and pytest 8.4.2.

| Run | Result | Producer |
|---|---|---|
| **Mutation battery:** a control, then 8 deliberate mutations of the two shipped modules (ceiling removed, cache keyed by mode only, list grants, case-folding, prefix match, skipped in proposal mode, no de-duplication, blank list denies all) | control 25 passed; every mutation turned at least one test red (10, 2, 6, 1, 1, 1, 1 and 14) | `<build-root>/allowlist-mut/results.txt` |
| **Targeted, after the fixture fix:** 10 files, among them the allowlist, worker-policy, bootstrap-invariant and env-conformance tests | 448 passed, 0 failed | `<build-root>/notes-51010/logs/allowlist-r9-r310fix.log` |
| **Control with the first fixture,** on a copy: that one bootstrap-invariant test alone | 1 failed, `test_r310_shapes_leave_no_runtime_divergence` | `<build-root>/notes-51010/logs/allowlist-r10-r310control.log` |
| **Full stock suite, first fixture** | 1 failed, 12,755 passed, 724 skipped, 11 deselected, 10 xfailed | `<build-root>/allowlist-mut/stock/stock-suite.log` |
| **Full stock suite, final tree** | **0 failed,** 12,756 passed, 724 skipped, 11 deselected, 10 xfailed, 569.06 s; exit 0 | `<build-root>/allowlist-mut/stock-r2/stock-suite.log` and its `stamp.txt` |

**The first stock failure, and its fix.** The lane's first `tests/conftest.py`
fixture was function-scoped and requested `monkeypatch`. That made pytest undo it
after the module-level rebind fixtures in
`tests/test_start_hwebserver_durable_ref.py` and
`tests/test_g1a_followup_job_root_discovery.py`, and
`test_r310_shapes_leave_no_runtime_divergence` then found two divergent modules.
The committed fixture is session-scoped and does not use `monkeypatch`
(`tests/conftest.py:532`). The control reproduced the failure with the old
fixture; the targeted run and the final stock run pass with the new one.

**The final run covers the committed tree.** It stamped the sha256 of the six
files before it started and again after it ended, unchanged (`stamp.txt`:
`SIX_FILES_UNCHANGED yes`). The six blobs in `fe4864a9` hash to the same six
values (`git show fe4864a9:<path> | sha256sum` against `sha_before.txt`, checked
when this card was drafted). By the tree equality above, the run also covers
`dd816e57`.

**Why it ran 28 more tests than v5.101.0's.** v5.101.0's stock run on
`b8f14e9e`, in a fresh worktree, gave 12,728 passed and 727 skipped
(`<build-root>/rel-51010/stock/stock-suite.log`). The difference is the 25 new
tests, plus 3 tests that skip there for missing local fixtures and ran in the
lane worktree: two in `tests/test_moneta_substrate_truth.py` (`:231`, `:246`)
and one in `tests/test_spatial_lane.py` (`:271`). Producer: the `SKIPPED` lines of
the two logs, compared.

**The mutation battery ran before a rename in the test file.** One constant and
one test were renamed, with one comment and one assertion message; the test
logic is unchanged. The two modules it mutated are byte-identical to the
committed ones: their sha256 values equal `sha_before.txt`'s.

**No CI run exists for the lane commit, the merge or this card.** They are pushed
together with the record and the release commit at step 6, and GitHub runs CI
for the pushed head only. That run, `{{CI_RUN}}`, is the CI evidence for the
whole range.

---

## 3. Release notes

**Not written yet.** `docs/releases/v5.101.1.md` and the `CHANGELOG.md` entry
land in the release commit (step 4). The release guard reads the notes from
`docs/releases/v5.101.1.md` (`notes()` in `harness/jev/jev_release.py`).

**They must carry:**

1. **The code they describe:** the reviewed tip, `{{TIP}}`. Every comparison is
   against the `v5.101.0` tag unless it names another commit.
2. **What changes for a seat:** the variable; its default (unset, nothing
   changes); exact names only; it only removes tools; it applies in every mode;
   and it reaches the interactive panel as well as an autonomous run (section 1,
   "Where it acts"). Where to set it: Houdini's environment, as the
   `docs/studio/DEPLOYMENT.md` row says.
3. **The lane's tests,** each number naming the tree it ran on (section 2.1).
4. **The limitations that still ship** (section 1) and **the three rulings as
   Joe made them** (section 5).

**They cannot carry the release commit's own results.** The notes are part of
that commit, so its CI run, its stock counts and its build results do not exist
when the notes are written. Those go into the verification record, a release
asset, and into `TAGS.md` at step 9. v5.101.0's notes cited CI on its reviewed
tip, which was pushed before its review; this release pushes once.

**`README.md:100` must not carry over as a claim about v5.101.1.** It says the
import diagnostic's fixes "are planned for the next release". The README refresh
rewrites it by the third ruling.

**The guard's split.** The guard judges the first 20 claims: `_claims`
(`harness/jev/jev_release.py:29-36`) returns `out[:20]` and cuts each claim at
600 characters. If the notes split into more than 20, `{{NOTES_CLAIMS}}`, claims
21 and later get Joe's recorded read before the Gate C push (step 6), as Joe read v5.101.0's claims 21 to 54
(`<build-root>/rel-51010/8a-claims-21-plus-human-read.txt`).

---

## 4. VERSION plan and order

`VERSION` is canonical. `scripts/sync_version.py` is the one observer and the one
propagator, for the 7 values in 6 files in its `SURFACES` table and no others
(`scripts/sync_version.py:41-55`).

### 4.1 Surfaces

`git grep -l "5\.101\.0" f58acb4f -- ':!docs/releases'` returns 13 paths:

| Surface | Changes in the release commit? | Ships in Setup? | In the crux range? |
|---|---|---|---|
| `VERSION` | **Yes,** `5.101.0` → `5.101.1`, the operator-directed cut | Yes | No |
| `pyproject.toml` | **Yes,** via `--write` | Yes | No |
| `python/synapse/__init__.py` | **Yes,** via `--write`: `__version__` and the docstring, two `SURFACES` rows | Yes | No |
| `docs/help/index.html` | **Yes,** via `--write` | Yes | No |
| `CLAUDE.md` | **Yes,** the target line via `--write` (`claude_md`) | No | No |
| `README.md` | **Yes:** line 10's banner via `--write`; the rest by hand (below) | No | No |
| `docs/getting-started/installation.md` | **Yes, by hand:** not a `sync_version` surface; 8 lines name `5.101.0` (`git grep -c`) | No | No |
| `CHANGELOG.md` | **Yes,** a new entry; v5.101.0's stays | No | No |
| `TAGS.md` | **Only after the tag** (step 9) | No | **Yes:** an edit before the tag refuses it |
| `harness/notes/release-5.101.0/` (card and record), `scripts/tag_release.py:23`, `tests/test_tag_release_crux_record.py:22` | **No:** history, a docstring example and a test-fixture constant | No | No |

`docs/releases/v5.101.1.md` is new in the release commit. It is not shipped in
Setup and is not in the crux range.

**README line 10 moves whole, in the release commit.** At `f58acb4f` the banner
and the tags text share line 10 (`git grep -n "5\.101\.0" f58acb4f --
README.md`); v5.101.0's card called it line 7, before the logo block above it.
`--write` moves the banner, `v5.101.0 · Houdini` (one match: `count=1` in
`write_surface`). `tags: v5.101.0 is Latest` moves to `tags: v5.101.1 is Latest`
by hand, in the same commit: `tests/test_phase0c_doc1_toolcount.py:176` pins it
to `VERSION`.

**README's 16 other lines that name `5.101.0`** (`:16 :22 :24 :26 :28 :30 :34
:36 :40 :54 :90 :104 :293 :339 :341 :353`, same producer) are reviewed by hand in
the README refresh:

- **Pinned to `VERSION`** by `harness/notes/readme_check.py`, which
  `tests/test_readme_receipt.py` runs: `[What's new]` (`:16`),
  `[Latest release notes]` (`:293`) and `[release's evidence]` (`:341`).
- **Pointing at the current release, so they move:** `:22 :24 :26 :28 :30 :34
  :36 :40 :54 :90 :104 :353`, with the anchor `#what-changed-in-51010` on `:24`.
  `:353` cites `git diff --stat v5.100.0 f50d9515 -- installer/ packages/`. For
  v5.101.1 the same diff from `v5.101.0` to `dd816e57` is empty (checked when
  drafted); the README names `{{TIP}}`.
- **`:339`** states v5.100.0's seat-suite figures as dated history, then says they
  were not re-measured for 5.101.0. Its last sentence follows the seat-suite
  ruling.

Two lines that name no version matter too. **`:100`** follows the third ruling
(section 3). **`:319`'s `**139 tools, two paths.**` stays:**
`test_readme_tool_count_matches_registry` needs it, and the lane adds no tool.

**README and installation.md move together.**
`tests/test_installation_setup_wording.py::test_readme_and_installation_agree_on_the_setup`
fails when README's Setup sentence (`:36`) and installation.md's (`:13`)
disagree.

**Operator check after the release commit:**
`git grep -n 5.101.0 HEAD -- README.md docs/getting-started/installation.md`
lists only lines that state dated v5.101.0 history.

### 4.2 Order

The labels **6a** (build and qualify), **7a** (the diff check) and **8a** (the
release guard) are kept from v5.101.0's card, so its working-set file names
carry over (`6a-verify.json`, `7a-first-run.txt`, `8a-guard.log`). They are
names here, not step numbers.

1. **The lane, the merge and this card.** Nothing is pushed in this step.
   - **Lane commit: done.** `fe4864a9`, on `fix/worker-tool-allowlist`, parent
     `f58acb4f` (section 2).
   - **Merge: done.** `dd816e57`, `--no-ff`, on the local branch
     `release/v5.101.1`, checked out in the release worktree
     `<build-root>/rel-51011/wt-release` (`git worktree list`). Its tree equals
     the lane's.
   - **The tag is free:** `git tag --list v5.101.1` prints nothing (checked when
     drafted). `git ls-remote --tags origin v5.101.1` must print nothing too; it
     needs the network and is run before this card's commit.
   - **This card** is committed alone, by explicit path, on
     `release/v5.101.1`. That commit is `{{TIP}}`, the
     reviewed tip and the last commit of the reviewed range.

2. **The Codex crux review of
   `b8f14e9e018c5d39a45004b3979875bea3989375..{{TIP}}`,** from the v5.101.1 brief
   (in `<build-root>/rel-51011/`), in a clone made for the review, detached at
   `{{TIP}}`, with no remote. On FAIL: fix, a new tip and a new review. No step
   below runs on a FAIL.

3. **Write `harness/notes/release-5.101.1/CRUX-RECORD.json` from the review, and
   commit it alone** on top of `{{TIP}}`. Write it with Python: UTF-8, no
   byte-order mark. The gate reads the file as plain UTF-8 and refuses a BOM as
   "not JSON" (`scripts/tag_release.py:194-200`). The fields, exactly as
   `crux_record_problem` requires:

   ```json
   {"version": "5.101.1",
    "review": "REL-5.101.1-RANGE",
    "reviewer": "Codex",
    "reviewed_date": "<YYYY-MM-DD, the day the review ran>",
    "verdict": "PASS",
    "passed": true,
    "commit_range": "b8f14e9e018c5d39a45004b3979875bea3989375..{{TIP}}"}
   ```

   - **`passed` is the JSON boolean `true`.** The other six fields are non-empty
     strings (`CRUX_STRING_FIELDS`, `scripts/tag_release.py:65-66`).
   - **`commit_range` carries both ends in full, 40 hex.** The gate accepts 7 to
     40 (`CRUX_SHA`, `:67`); the full form closes the hex-named-ref case, TG-3.
   - **`reviewed_date` is not before `{{TIP}}`'s commit date,** the first ten
     characters of `git show -s --format=%cI {{TIP}}`, in the committer's time
     zone (`:253-257`). It is not after the later of the local and the UTC date
     on the day the gate runs (`_today`, `:165-171`).
   - **Operator check:** `git rev-parse {{TIP}}` equals the commit Codex
     reviewed, and `git show --stat {{RECORD_COMMIT}}` lists only the record.

4. **The release commit.** In the release worktree, on top of
   `{{RECORD_COMMIT}}`:
   - **`VERSION`** gets `5.101.1` and a newline, UTF-8 without a byte-order mark
     (the R107 history in `scripts/sync_version.py`'s docstring). This is the
     operator's one `VERSION` edit in an operator-directed cut
     (`harness/CLAUDE.md`; `docs/RELEASE_CARD.md`, ritual step 2), made on Joe's
     GATE 1 go. `--write` never writes `VERSION` itself.
   - **`<python> scripts/sync_version.py --write`** moves the six other values.
   - **By hand:** README line 10's tags text and the README refresh (4.1),
     `docs/getting-started/installation.md`, the `CHANGELOG.md` entry and
     `docs/releases/v5.101.1.md` (section 3).
   - **Checks on the staged tree, before GATE 1.** `docs/RELEASE_CARD.md` runs
     the tests (ritual steps 6 to 12) before the VERSION commit (step 13), so they
     run on the working tree with every release-commit file in place:
     - **7a, on the working tree:** the paths that differ from `{{TIP}}`,
       untracked files included, are exactly the 10 listed under 7a's first run
       below.
     - **`<python> scripts/sync_version.py --check`** exits 0.
     - **The fenced README and version run:**
       `WT_OVERRIDE=<release worktree> bash <build-root>/notes-51010/run-targeted.sh <label> tests/test_installation_setup_wording.py tests/test_phase0c_doc1_version_conformance.py tests/test_phase0c_doc1_toolcount.py tests/test_readme_receipt.py tests/test_reach_public_agreement.py`
       gives 0 failed. These files pin README content and the version surfaces.
     - **The stock suite on the staged tree,** alone and fenced, in the release
       worktree, with a copy of the lane's stock runner that refuses unless HEAD
       is `{{RECORD_COMMIT}}` and the working tree differs by exactly the release
       commit's files, and that stamps their sha256 before and after: 0 failed.
       Its output folder is under `<build-root>/rel-51011`; v5.101.0's and the
       lane's stock folders are read-only evidence.
       Its difference from v5.101.0's run on `b8f14e9e` is explained file by file.
       Result: `{{STOCK_RELEASE}}`.
     - **The installer unit tests,** with a copy of `run-installer-tests.sh`:
       `python -B -m unittest discover -s installer/tests -t installer/tests -v`
       ends `OK`. v5.101.0 ran 84
       (`<build-root>/rel-51010/installer-tests-unittest.log`), and the range
       changes no file under `installer/`. Result: `{{INSTALLER_TESTS}}`.
     - **One heavy run at a time.** The stock suite, 6a and any seat run never
       overlap: the stock runner refuses while a Houdini-class process runs, and
       other sessions share this machine.
   - **Stage by explicit path, never `git add -A`:** the nine files of 7a's list
     below, other than the record.

   > **STOP: GATE 1 of 4, the VERSION commit.** Ask Joe, with the staged diff,
   > the checks above and the three open rulings (section 5). His words for the
   > rulings go into the notes' Limits before the commit, and a staged file that
   > changes after the checks gets the checks that read it again. Commit only on
   > his go, with `SYNAPSE_GATE_C=1` (`docs/RELEASE_CARD.md`, ritual step 13).
   > That commit is `{{RELEASE_COMMIT}}`.

   Then, on the committed release commit, before anything is pushed:

   - **The committed files are the tested files:** the sha256 of each staged
     file in `{{RELEASE_COMMIT}}` equals the stock run's stamp, or the file's
     change after the run is accounted for.
   - **7a, first run.** `git diff --name-only --no-renames {{TIP}} HEAD` prints
     exactly these 10 paths:

     ```
     CHANGELOG.md
     CLAUDE.md
     README.md
     VERSION
     docs/getting-started/installation.md
     docs/help/index.html
     docs/releases/v5.101.1.md
     harness/notes/release-5.101.1/CRUX-RECORD.json
     pyproject.toml
     python/synapse/__init__.py
     ```

     Any other path stops the release. The gate refuses only an edit to a
     reviewed file; a new or other file after the tip passes it. This check is
     what bounds the release commit. Keep the output beside the record.
   - **`<python> scripts/sync_version.py --check`** exits 0.
   - **`<python> scripts/tag_release.py --check-only`** reports the gate open:
     every check line `OK`, the `pytest_pre` line `PASS`, then a last line
     `gate ... OPEN`, as v5.101.0's did
     (`<build-root>/rel-51010/tag-release-check-only.log`). It runs its
     conformance test with `sys.executable -m pytest`, outside the fence: the
     one sanctioned exception, as in v5.101.0. `<python>` is the CPython 3.14.2
     interpreter the fenced runners use, with pytest installed.

   **A red in steps 4 or 5.** In the release commit's own files: a corrected
   release commit, asked again at GATE 1. In a reviewed file: a fix, a new tip
   and a new crux review, from step 1. Nothing is public yet.

5. **6a: build and qualify, before the push.**
   - **In a fresh detached worktree at `{{RELEASE_COMMIT}}`.** v5.101.0's
     `run-build-and-qual.ps1` refuses any `git status --porcelain` line,
     untracked files included, and its log opens `TREE_OK <sha> clean`.
   - **What runs.** Copies of v5.101.0's scripts in `<build-root>/rel-51010`,
     adapted for v5.101.1 in `<build-root>/rel-51011` and statically checked
     before this card's commit; none has run yet. `run-build-and-qual.ps1`
     builds Setup and runs legs A-executable, B-upgrade and C-production. One
     change in control flow from v5.101.0's copy: it takes the real-seat
     after-snapshot and compares it before it judges the qualification's exit,
     so `build-and-qual.log` shows `REAL_SEAT_UNCHANGED` before the chain throws
     on leg C's failure. v5.101.0's chain threw first and skipped that compare.
     `run-legs-D2-D.ps1` runs legs D2 and D.
     `audit_source_archive.py` checks the committed source archive; its
     real-account-path rule has no allowlist.
   - **Leg B upgrades from the published v5.101.0 build:**
     `<build-root>/rel-51010/build`, payload `5.101.0-f530ab4f1233e3e8`
     (`payload_id` in v5.101.0's published public build record), source
     `b8f14e9e`. Its `SYNAPSE-5.101.0-Setup.exe` hashes to
     `ffd316abd837745ca962e60b2ead7b26a1af8b6b4c464875864c490dd093029c`, the
     digest v5.101.0's read-back confirmed for the published asset
     (`<build-root>/rel-51010/readback-r3.log`). The copy's previous-version,
     previous-payload and previous-source parameters take those values.
   - **Leg C on this machine.** `production_uninstall_registration_absent_before`
     failed for v5.101.0 on 14 November: "the per-user registration was already
     present before this run" (`<build-root>/rel-51010/leg-reports.txt`).
     v5.101.0's `run-build-and-qual.ps1` exited 1 on that check before its
     real-seat compare, which is why v5.100.0 and v5.101.0 ran
     `run-legs-D2-D.ps1` on its own. The v5.101.1 copy compares the real seat
     first and still exits 1 on that check, so legs D2 and D still run on their
     own. REL-LEGC-PRECONDITION
     (`harness/next-release/proposals/render-qc.amendment.PROPOSED.json`)
     accepted that one failure for v5.100.0, and Joe ruled the same for
     v5.101.0. **For v5.101.1, Joe rules it at GATE 1** (section 5, first row),
     and the notes' Limits carry his words.
     The leg C result goes in the verification record. A failure in any other
     leg is a red.
   - **The seat suites** follow the second row of section 5. If they run, they
     run on `{{RELEASE_COMMIT}}`, after the stock suite and 6a, never at the same
     time as either, with their own log folders.
   - **6a builds the commit that step 6 pushes and step 7 tags.** Any new commit
     after 6a, such as a fix for red CI or a send-back, runs 6a again on that
     commit before its push. Before the tag push, `git rev-parse
     v5.101.1^{commit}` equals the SHA on 6a's `TREE_OK` line. v5.101.0's
     composer does not check this itself.

6. **The Gate C push.**

   - **Joe's read of claims 21 and later, before the push.** The notes become
     public with this push. The guard judges only the first 20 claims (section
     3). The operator writes claims 21 to `{{NOTES_CLAIMS}}` of the committed
     notes, split the way `_claims` in `harness/jev/jev_release.py` splits them,
     to a file beside the record; Joe reads them, and his read is recorded
     beside the record. A claim he finds false is a corrected release commit,
     back at GATE 1.

   > **STOP: GATE 2 of 4, the Gate C push.** Ask Joe, with 7a's first output,
   > the step 4 results, 6a's verdict and his recorded read of claims 21 and
   > later. Push only on his go.

   - **From the release worktree:**
     `SYNAPSE_GATE_C=1 git push origin HEAD:refs/heads/master`, fast-forward
     only. It pushes the lane commit, the merge, this card, the record and the
     release commit together. If `origin/master` is no longer `f58acb4f`, the
     push is rejected: stop and ask. Never rebase the reviewed commits; a rewrite
     makes the record stale.
   - **What the push prints.** The pre-push hook names `VERSION` as a protected
     path, and GitHub reports the four required checks as bypassed, as it did for
     v5.101.0 (`<build-root>/rel-51010/push-b8f14e9e.log`). The run that follows
     is the check.
   - **CI on the exact SHA.** `ci.yml` runs on a push to `master` and on pull
     requests (`.github/workflows/ci.yml:3-6`). The run that counts is the push
     run for the full 40-character `{{RELEASE_COMMIT}}`: all six
     `test (os, py)` jobs, three systems by two Pythons (`:13-15`), conclude
     `success`. Branch protection requires four of them
     (`<build-root>/rel-51010/branch-protection.json`); all six count here.
     **A human check:** `tag_release.py` never reads CI.
   - **Then the hosted archive:** GitHub's source archive for
     `{{RELEASE_COMMIT}}` matches the audited local one, with a copy of
     `archive_matches_head.py` (`docs/RELEASE_CARD.md`, ritual step 17). The
     copy in `<build-root>/rel-51011` is a byte copy of v5.101.0's, which
     matches member names exactly and does not strip the single top-level
     folder GitHub puts in a hosted archive; it is changed to strip it, and
     rehearsed on v5.101.0's hosted archive, before this step. A pass prints
     `VERDICT: the archive IS the archive of ...`.
   - **After the push, nothing is rebuilt underneath it.** From here
     `{{RELEASE_COMMIT}}` is public. A send-back from 8a, or a fix for red CI,
     is a new commit on top of the pushed head, never a rebuild on
     `{{RECORD_COMMIT}}`; `{{RELEASE_COMMIT}}` then names the new commit, the
     next push expects `origin/master` at the head pushed before, 6a runs again
     on the new commit, and Gates 1 to 3 are asked again. A fix that touches
     any of the 8 reviewed files stops before any push and goes to Joe: it needs
     a new crux review and a rewritten record, and the tag gate refuses the old
     one (`scripts/tag_release.py:301-319`).

7. **The tag.**

   > **STOP: GATE 3 of 4, the tag.** Ask Joe once CI is green on all six jobs.
   > His go covers creating the tag and, if 8a, Joe's read of every claim it
   > flags and the CI gate below pass, pushing it. A send-back from 8a is a new
   > commit on top of the pushed head (step 6, "After the push"), and Gates 1
   > to 3 are asked again.

   - **7a, second run,** immediately before the tag and after any merge to
     master: the same command prints the same 10 paths. Keep it beside the
     record.
   - **`<python> scripts/tag_release.py`** creates the annotated tag `v5.101.1`
     on the commit it checked, locally. It never pushes. Success is exit 0 with
     the lines `tag          v5.101.1 created      OK`, `pytest_post  PASS` and
     `next act     git push origin v5.101.1   (operator, per-act)`, as v5.101.0's
     run printed them (`<build-root>/rel-51010/tag-release.log`). Anything else,
     `gate         POST-TAG FAIL -- inspect before pushing v5.101.1` included,
     stops step 7: `git tag -d v5.101.1`, then ask Joe.
   - **8a, the release guard,** after the local tag and before the tag push.
     Run in this order, and keep all four outputs beside the record:
     1. `git rev-parse v5.101.1^{commit}` and `git rev-parse HEAD` print the same
        40-hex SHA, `{{RELEASE_COMMIT}}`. If they differ, stop.
     2. `git rev-parse v5.101.0^{commit}` prints
        `b8f14e9e018c5d39a45004b3979875bea3989375`. A `--prev` that does not
        resolve sends the model an empty diff.
     3. `git status --porcelain --untracked-files=no` is empty. The guard reads
        the notes from disk, so a clean tracked tree is what makes them the
        tagged text.
     4. `<python> harness/jev/jev_release.py notes --tag v5.101.1 --prev
        v5.101.0`. Its last line begins `-- N claims, M need a human read`, and it
        exits 1 when M > 0. **Prerequisites:** a `TYPESAFE_API_KEY` in the
        environment or the user registry environment (`api_key`,
        `harness/jev/jev_client.py:32`), and `SYNAPSE_JEV` not `off`, `0` or
        `false` (`:29`).
   - **Reading the result.** M counts the `UNSUPPORTED` and `REFEREE` claims;
     `PARTIAL` is not counted. A ledger row of `fallback` or `disabled` is no
     verdict, because every claim then reads `REFEREE`: fix the cause and run
     again. A claim found false is a send-back. A flagged claim that Joe's read
     finds true is recorded in writing beside the record, and the release goes
     on. The tag push waits for that read.
   - **The ledger stays out of every commit.** The run appends to
     `harness/jev/ledger/v5.101.1.release.notes.jsonl`, which git does not
     ignore. Keep it beside the record.
   - **A send-back costs** `git tag -d v5.101.1` (local, never pushed), then a
     new commit on top of the pushed head and steps 4 to 7 for it (step 6,
     "After the push").
   - **The CI gate:** `<python> scripts/release_ci_gate.py v5.101.1` exits 0. It
     resolves the local tag and reads CI for that commit.
   - **Push the tag:** `git push origin v5.101.1`, only after the CI gate exits
     0 and 6a's `TREE_OK` SHA equals the SHA from 8a's first item.

8. **The GitHub release.**
   - **Compose the public assets** with `<build-root>/rel-51011/compose_assets.py`
     and `compose_real.sh`, the working-set adapter's copies of v5.101.0's
     `compose_assets_r2.py` and `compose_real_r3.sh`. The copy changes the version
     constants (`5.101.1`, previous `5.101.0`); the leg C ruling and the
     seat-suite sentence, read from the tagged notes' Limits and the tagged
     README (this card is frozen before Joe rules, so it cannot carry them, and
     the copy's sentences for the leg C, seat-suite and owner-path rulings are
     set to Joe's words before it runs); the expected owner-path map, by the
     third ruling; and `--previous`,
     `--previous-verification` and `--native-bundle`, which come from v5.101.0's
     read-back copies (`<build-root>/rel-51010/readback-r3/assets/`). Its
     `--final` pass takes `--source-revision {{RELEASE_COMMIT}}` and
     `--ci-run-id {{CI_RUN}}`, so it runs after the tag exists and CI has
     concluded. Rehearse it first, including a failing qualification, as
     v5.101.0 did.
   - **The six assets, as v5.101.0 published them** (`readback-r3.log`, "asset
     names equal"): `SYNAPSE-5.101.1-Setup.exe`, `SYNAPSE-5.101.1-source.zip`,
     `SHA256SUMS.txt`, `SYNAPSE-5.101.1-Setup.public-build.json`,
     `installer-verification.json` and `moneta-native-0.1.0-win64-clean.zip`.
     The last is the native input, unchanged unless Moneta's pin moves; v5.101.0
     published it with sha256 `f0c67e0642305ce9…` (same read-back). Setup is
     unsigned; its hashes live in `SHA256SUMS.txt`, not in the notes.

   > **STOP: GATE 4 of 4, `gh release create`.** Ask Joe, with the composed
   > assets' hashes and the verification record's verdict. Publish only on his
   > go, after the tag push and the CI gate, as one command on its own:
   > `gh release create v5.101.1 --verify-tag --latest --title "SYNAPSE v5.101.1" --notes-file <release-page notes> <the six assets>`

   - **Read back every asset,** with a copy of v5.101.0's `readback_r2.sh`: the
     release metadata, Latest, all six downloaded and compared byte for byte,
     `SHA256SUMS.txt` verifying the downloads, and every v5.101.1 link in the
     tagged README and installation guide. In the copy, section 4 fetches the
     two HTML pages without a range header. v5.101.0's version printed one false
     FAIL there (`readback-r3.log`), cleared by `readback_links_recheck.sh`.

9. **After the publish: `TAGS.md`.** One commit that updates `TAGS.md`, staged by
   explicit path, not tagged. Check it against the live release first: the
   published hashes, `{{TAG_OBJECT}}` and `{{RELEASE_COMMIT}}` taken from git,
   and the `ci` block's run, `{{CI_RUN}}`. Fix any line copied from v5.101.0.
   v5.101.0's own step 9 commit is `f58acb4f`.

   > **STOP: a Gate C push, asked on its own.**
   > `SYNAPSE_GATE_C=1 git push origin HEAD:refs/heads/master`, only on Joe's go.

### 4.3 What must not happen

- **No edit to any of the 8 reviewed files after the crux review.** That includes
  `TAGS.md` and this card. The tag gate refuses when a reviewed file differs at
  the tagged commit (`scripts/tag_release.py:301-319`), and the review runs
  again.
- **Nothing but this lane before the tag.** No other lane, fix or cleanup lands
  on `release/v5.101.1`: Joe's go names one lane.
- **No `VERSION` edit before the record is committed.**
- **No rewrite of `fe4864a9`, `dd816e57`, `{{TIP}}` or `{{RECORD_COMMIT}}`.** The
  record binds the tip by ancestry (`scripts/tag_release.py:277-286`), so a
  rebase or an amend makes it stale.
- **No push without Joe's go.** Master moves only by
  `SYNAPSE_GATE_C=1 git push origin HEAD:refs/heads/master`, and the tag only by
  `git push origin v5.101.1`. Never a bare `git push`, a branch push or a force
  push.
- **No tag on a commit whose CI has not concluded `success` on all six jobs.** A
  human check: the tag gate never reads CI.
- **No `gh release create` before the tag push and the CI gate.** A failed gate
  never falls through to it: without `--verify-tag` it can create a tag
  (`docs/RELEASE_CARD.md`). Never overwrite an existing tag or asset.
- **No `git add -A`.** Every commit is staged by explicit path, and the 8a ledger
  stays out.
- **No `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` or `GIT_COMMON_DIR` set, and
  no `git stash`.**
- **No release-notes sentence that a check cannot trace to its producer.**
- **No local path or account name in anything committed or published.** The
  source-archive audit fails on a real account path, and the composer refuses an
  owner-path count other than the ruled one.
- **No write in the primary SYNAPSE working copy, which Houdini loads.** No stop
  or kill of a process this release did not start.
- **Installing v5.101.1 into the live seat is a separate act,** authorized by Joe
  on its own (`docs/RELEASE_CARD.md`, ritual step 20).

---

## 5. Open gates

| Gate | State | Who closes it |
|---|---|---|
| Leg C's machine precondition for v5.101.1 | **open:** asked at GATE 1; Joe's words go into the Limits of `docs/releases/v5.101.1.md` | Joe, at GATE 1 |
| The seat suites for v5.101.1 | **open:** asked at GATE 1; Joe's words go into the Limits | Joe, at GATE 1 |
| How the notes and `README.md:100` word the items v5.101.0 planned "for the next release": the owner-path cleanup and the wider audit pattern; KI-4, F4 and F5; the four developer-side defects | **open:** asked at GATE 1 | Joe, at GATE 1 |
| Lane commit and `--no-ff` merge | **done:** `fe4864a9`, `dd816e57`; local, not pushed | closed |
| This card's commit, `{{TIP}}` | **not done** when drafted | the operator, by explicit path |
| Codex crux review of `b8f14e9e..{{TIP}}` | **not run** | Codex, then the record |
| `CRUX-RECORD.json` | **not written** | the operator, from the review |
| The release commit (GATE 1) | **not done** | Joe's go |
| Joe's read of the notes' claims 21 and later | **not done;** before the Gate C push | Joe |
| Checks on the staged release tree (before GATE 1) and on the release commit, and 6a | **not run.** The v5.101.1 script copies exist in `<build-root>/rel-51011`, adapted and statically checked; a refuter's findings on them are fixed before they run | the operator |
| The Gate C push, and CI on six jobs (GATE 2) | **not done** | Joe's go; CI read by a human |
| Tag, 8a, CI gate and tag push (GATE 3) | **not done** | Joe's go |
| GitHub release and read-back (GATE 4) | **not done.** The composer copy exists and is rehearsed before its real run | Joe's go |
| `TAGS.md` and its Gate C push | **not done** | Joe, asked on its own |

---

## 6. Where this lives

- **This card:** this file. **The record:** `harness/notes/release-5.101.1/CRUX-RECORD.json`,
  from step 3.
- **The notes:** `docs/releases/v5.101.1.md` and the `CHANGELOG.md` entry, in the
  release commit.
- **The lane:** `fix/worker-tool-allowlist`, at `fe4864a9`. **The release
  branch:** `release/v5.101.1`, local, at `dd816e57` when this card was drafted,
  in the release worktree `<build-root>/rel-51011/wt-release`.
- **The lane's evidence, outside the repo:** `<build-root>/allowlist-mut/` (the
  mutation battery, both stock runs and their stamps) and the
  `allowlist-r*.log` files in `<build-root>/notes-51010/logs/`.
- **The v5.101.1 working set, outside the repo:** `<build-root>/rel-51011/`: the
  crux brief, the script copies, the checks' outputs and the composed assets.
- **v5.101.0's working set,** the pattern and the previous build:
  `<build-root>/rel-51010/`. Joe's v5.101.0 rulings are in
  `owner-rulings-2026-11-14.txt` there.
- **The patterns in the repo:** v5.101.0's card,
  `harness/notes/release-5.101.0/RELEASE_v5.101.0.md`, and the ritual,
  `docs/RELEASE_CARD.md`.
- **Never write in the primary SYNAPSE working copy, which Houdini loads.** Every
  step runs in a worktree.
