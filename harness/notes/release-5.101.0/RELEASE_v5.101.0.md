# Release card — SYNAPSE v5.101.0

**Status: DRAFT, GATED. Do not execute any step below.**

```
+== GATE: NR-RECOVERY-RECEIPTS CRUX ==========================================+
| Blocked by : the Codex crux review of qc/recovery-receipts                  |
| Earliest   : 2026-11-14 08:44 (Joe's ruling 47737990; Codex usage limit)    |
| Also needed: the never-launched rule node, drafted and NOT launched         |
| Drafted    : 2026-11-11, session a021515b, after CI 43120470516 went green  |
| Author     : Claude Code. Every number below names its producer.            |
+=============================================================================+
```

Nothing in this card has been executed. `VERSION` is still `5.100.0` and no
tag exists beyond `v5.100.0`. `origin/master` is `e6516be6` as of 2026-11-12;
this line is the one live claim in the card, so treat it as stale the moment
master moves and re-read it before acting.

---

## 1. What v5.101.0 is

Two lanes, one of which is already on master and one of which is not.

| Lane | Node | State on master | Ships in Setup? |
|---|---|---|---|
| Render QC timing harness | `NR-QC-TIMING` | **landed** (`db8b43a6`) | **No** — all under `harness/` |
| Durable worker receipts | `NR-RECOVERY-RECEIPTS` | **not merged** (`58f23d33`) | **Partly** — `python/synapse/host/retina_receipts.py` |

The payload boundary, measured: `RUNTIME_TREES` in `installer/build_payload.py`
includes `python/synapse/`, so the new host module ships. `retina/` appears
in that file, but only as eight named modules in `RUNTIME_FILES` —
`__init__`, `events`, `exr_header`, `t0`, `t1`, `ingest`, `qc_profiles.py` and
`qc_profiles.toml` (`installer/build_payload.py:22-23`) — and
`retina/worker_entrypoint.py` is not among them, so it does not ship. **The
early draft of this card said `retina/` appeared nowhere in that file, which
was false**; the conclusion survived the correction, the sentence did not.
The timing lane adds nothing outside `harness/`, which is not a payload tree.

---

## 2. Commits since v5.100.0

### 2.1 Already on master — `git log --oneline v5.100.0..master`

**Snapshot, taken at `db8b43a6`.** The list below is the timing lane as it
stood then; it is kept as the record of that landing and is not maintained.
The range has since grown: at `e6516be6` it is **21 commits and 6 merges**
(`git rev-list --count v5.100.0..master` and `--merges`). At the time of the
snapshot it was ten commits, eight of them the branch:

```
db8b43a6  merge: qc/timing into master (trial 2, after the model-string strip)
195365a1  feat(qc-timing): rebuild the timing receipt without the workstation model strings
f91d5d28  fix(qc-timing): keep the workstation model strings out of the receipt
19a2fb74  merge: qc/timing into master (trial for the packet)
1fecb663  feat(qc-timing): the timing receipt for run-20261111-1357
f68eafd0  fix(qc-timing): keep frame names out of the timing receipt
293ac1d5  fix(qc-timing): N1 check_warmup is red on a warm-up record that carries an exception
227f4737  fix(qc-timing): referee fix pass F1-F15 (Joe F4 ruling a, F11 kept)
68e91add  feat(qc-timing): the timing harness, decide.py, stage, run_timing, make_receipt
74690f91  test(qc-timing): NR-QC-TIMING closure predicate, red until the receipt is committed
```

**Two of those commits were merges of the same branch.** `19a2fb74` and
`db8b43a6` both merge it, because the trial tree was built, the model-string
strip was then applied, and the trial tree was merged again. The tree content
is exactly what was tested and what CI passed on; the shape is two nested
merges. The range has since gained four more merges for other work, so a
"rebuild it as one merge" decision now covers six, not two, and the cost of
rebuilding has risen with them. Decide before the tag, never after.

### 2.2 Not yet on master — `git log --oneline origin/master..HEAD` in `wt-receipts`

Nineteen commits at `58f23d33` (branch `qc/recovery-receipts`).

**It branched before the timing lane landed, and that has to be proved safe.**

`git diff --diff-filter=D --name-only origin/master..HEAD` in `wt-receipts`
lists eight paths as deletions: the whole of `harness/vision/qc_timing/`
(`README.md`, `decide.py`, `make_receipt.py`, `run_timing.py`, `stage.py`,
`test_qc_timing_harness.py`, `timing_receipt.json`) and
`harness/next-release/proposals/predicates/test_nr_qc_timing.py`.

**That list is a tree comparison, not a merge outcome.** Those files are simply
absent from a branch cut before they existed, and a merge onto `db8b43a6`
would keep them: they were added on the master side and never touched on the
receipts side, so there is nothing to conflict with. The card states it this
way round because the alarming reading is the wrong one.

**Measured, not predicted.** A trial merge was run on 2026-11-11 in a throwaway
worktree `<build-root>/release-51010/wt-trial`, branch
`trial/receipts-on-master`, from `db8b43a6`:

- **`git merge --no-ff qc/recovery-receipts` → "Merge made by the 'ort'
  strategy", no conflicts.** Merge commit `0ee8b00c`. Six files changed,
  **3,028 insertions, 5 deletions**.
- **Every one of the eight paths above survives byte-identical to
  `195365a1`** — checked with `git hash-object` against
  `git rev-parse 195365a1:<path>` on all seven `qc_timing` files and the
  predicate. Eight of eight OK.
- Worktree clean after the merge.

So the branching hazard is closed: the receipts lane merges onto the timing
master without touching it. The trial branch is throwaway and unmerged; the
real merge still needs Joe's word.

---

## 3. Release notes — draft, since authored

> **This section has been carried out.** The notes are authored on the branch
> `scratch/v5.101.0-card`, at `docs/releases/v5.101.0.md`, with a CHANGELOG
> entry above v5.100.0, and they land with the release commit. They are
> deliberately not on master yet: they assert a product module that is not in
> this tree, and will not be until the receipts lane merges. What follows is
> the draft they were written from, kept as the record of what was decided
> before the authoring pass. Every figure carries its producer. The «angle
> brackets» were filled from the verification record when the notes were
> authored.

### Header

**The Render QC timing measurement lands, and it does not clear its budget.**
A four-part harness stages frames, times three passes per frame, decides under
a frozen rule, and emits a receipt that recomputes from raw records. The
verdict is **branch 4**: the pipeline's floor — everything except the dense
analysis — is **5.732 s** against a **2.0 s** budget on the deciding tier,
2.9× over, while read plus write is only **0.300 s**. Making the scan cheaper
cannot reach the budget.

**Durable worker receipts land behind a gate.** A request record and one
terminal receipt per request, written through an exclusive temp and
`os.replace`, with the reply's mask bound to the worker that wrote it. Nothing
calls them yet.

### The timing measurement

- **Verdict, branch 4, row 3, unanimous** across the three deciding stills,
  char-9 and char-2. Producer:
  `harness/vision/qc_timing/timing_receipt.json`, `decision.units`.
- **Deciding tier:** T **6.474 s**, R+W **0.300 s**, Floor **5.732 s**, dense
  share **0.120**. char-9: T 3.469, Floor 3.079. char-2: T 2.310, Floor 2.196
  over 24 frames.
- **The run:** 541 records — 417 timed, 121 untimed, 3 dry. **0 exceptions,
  0 inconclusive, 0 check disagreements.** 45 passes voided, every one naming
  a foreign process (`python.exe`, `python3.13.exe`, `hython.exe`,
  `husk.exe`). Producer: `run-20261111-1357/timed/raw.jsonl`.
- **The rule is frozen:** revision 2, `B = 2.0`, `threshold = 0.5`, pinned in
  `decide.py` and in the receipt's `rule` block.
- **Independently recomputed** by a referee that did not build it: 1,240
  per-frame numbers, 81 boundary cases, `decide.decide()` dict-identical.
- **The receipt carries no frame names and no workstation model strings.**
  0 of 124 staged names, no stem and no project-name form, no `cpu_model` or
  `scratch_drive_model` key. Producer: `make_receipt.compose()` at `f91d5d28`.
- **Closure predicate:** `harness/next-release/proposals/predicates/test_nr_qc_timing.py`,
  **36 passed** at `195365a1`.

### The receipts lane «pending crux»

- `python/synapse/host/retina_receipts.py`, **+828/−0**, new, **ships in
  Setup**. Producer: `git diff --numstat origin/master..HEAD` in `wt-receipts`.
- `retina/worker_entrypoint.py`, **+230/−5**. **Not in Setup.**
- `tests/test_retina_receipts.py` **+1,084/−0** and
  `tests/test_retina_worker_contract.py` **+429/−0**.
- **Tests, measured 2026-11-11** with `python -B -m pytest
  tests/test_retina_receipts.py tests/test_retina_worker_contract.py -q
  -p no:cacheprovider` on stock CPython 3.14.2: **175 passed, 8 skipped** on
  the lane at `58f23d33`, and **175 passed, 8 skipped** on the trial merge
  `0ee8b00c` — the shape that ships. Both closure predicates on the merged
  tree (`test_nr_qc_timing.py` and `test_nr_recovery_receipts.py`):
  **49 passed**.
- **The 8 skips are one reason, quoted from `-rs`:**
  `SYNAPSE_RETINA_WORKER_PYTHON does not name a worker interpreter`. The
  end-to-end worker tests did not run. They are not counted as passes, and the
  release note must say so rather than report "175 passed" alone.

### Full suite, trial merge against the release master

Both trees were run in full on the same machine, in the same interpreter, back
to back, with the dependency state recorded at launch:

| | `db8b43a6` (release master) | `0ee8b00c` (master + receipts) |
|---|---|---|
| Interpreter | CPython 3.14.2 | CPython 3.14.2 |
| numpy / cv2 / pytest / pxr | present | present |
| `mcp` | **absent** | **absent** |
| Other sessions' load | 28 python.exe | 32 python.exe |
| **failed** | **60** | **60** |
| **errors** | **92** | **92** |
| passed | 12,550 | 12,649 |
| skipped | 660 | 664 |
| xfailed | 10 | 10 |
| collected | 13,352 | 13,455 |
| wall clock | 14m27s | 11m29s |

- **The FAILED sets are identical: 60 each, none in either direction.**
- **The ERROR sets are identical: 92 each, none in either direction.**
- The +103 collected reconciles exactly: `tests/test_retina_worker_contract.py`
  goes from **80 to 101** collected tests, and the new
  `tests/test_retina_receipts.py` contributes **82**. 21 + 82 = 103, and the
  99 extra passes plus 4 extra skips account for all of them.

**The 60 failures and 92 errors are environment, not code, and they are shared
by both trees.** Two collection errors are `No module named 'mcp'`. Ninety are
`test_panel_rhythm_docking.py`: that test spawns
`python -I .../test_panel_rhythm_docking.py`, the `-I` flag excludes the user
site-packages where pytest lives, the child dies with
`ModuleNotFoundError: No module named 'pytest'`, and the parent asserts
`returncode == 0`. Thirty nested `ImportError: cannot import name 'trace' from
'opentelemetry'` sit inside those. Remaining failures cluster in
`panel_sweep_a` (22), `model_transports` (10), `host_layer` (10),
`model_lanes` (8) and `panel_sweep_b_widgets` (6).

**These local numbers are not the release's suite numbers.** They are the
evidence that the receipts merge regresses nothing. The release's suite numbers
are CI's, on `db8b43a6` — which was the head when this was measured, and is
not the head now — where every dependency is present:

| CI job | passed | skipped | deselected | xfailed | failed |
|---|---|---|---|---|---|
| `windows-latest`, 3.11 | 12,620 | 616 | 50 | 10 | **0** |
| `windows-latest`, 3.14 | 12,618 | 618 | 50 | 10 | **0** |
| `macos-latest`, 3.11 | 12,612 | 624 | 50 | 10 | **0** |
| `macos-latest`, 3.14 | 12,612 | 624 | 50 | 10 | **0** |
| `ubuntu-latest`, 3.11 | 12,611 | 625 | 50 | 10 | **0** |
| `ubuntu-latest`, 3.14 | 12,611 | 625 | 50 | 10 | **0** |

Source: each job's own pytest summary line in Actions run **43120470516**, all
six jobs `success`. 228 subtests passed on every job.

### Limits that must appear in the note

Every one of these is currently true and each was verified today:

1. **Nothing calls the receipts module.** It ships dormant.
2. **The budget question is open.** The 2.0 s constant is in the frozen rule;
   whether 2.0 s is the right number is owner decision **QC-Q3**, still open.
3. **The timing data is from one machine and one run.** 124 frames, one host,
   45 voided passes from foreign processes.
4. **The receipts crux has not run** (`NR-RECOVERY-RECEIPTS`), and the
   never-launched rule node is not drafted.
5. **The master range carries six merges**, two of them for the same branch
   (see §2.1). It carried two when that section was written.
6. **`anthropic` 2.x remains unsupported** — the pin stays `anthropic>=1.0.0,<2`.
7. **Setup remains unsigned.**

---

## 4. VERSION plan

`VERSION` is canonical. `scripts/sync_version.py` is the one observer and the
one propagator; every other surface derives from it or is checked against it.

### 4.1 Surfaces, verified on master today

`git grep -l "5\.100\.0" master -- ':!docs/releases'` returns **11 paths**:
the rows below, `CHANGELOG.md`, `TAGS.md`, and this card itself, which quotes
the version as history and is not a surface. Two of the ten real surfaces were
missing from the first version of this table — `CHANGELOG.md` and `TAGS.md` —
and are added below.

| Surface | Kind | Changes on release? |
|---|---|---|
| `VERSION` | canonical | **Yes** — `5.100.0` → `5.101.0` |
| `python/synapse/__init__.py` | `__version__` (line 123) | **Yes** — via `--write` |
| `README.md` | banner | **Yes** — via `--write` |
| `pyproject.toml` | package version | **Yes** — via `--write` |
| `docs/help/index.html` | help page | **Yes** — via `--write` |
| `docs/getting-started/installation.md` | install doc | **Yes** — via `--write` |
| `CHANGELOG.md` | changelog head | **Yes** — hand-authored entry, not `--write` |
| `TAGS.md` | current-release line and tag table | **Yes** — hand-authored, nothing tests it |
| `CLAUDE.md` | project target line | **Yes**, but project instructions — check by hand, do not bulk-write |
| `harness/next-release/proposals/render-qc.amendment.PROPOSED.json` | amendment record | **Check** — likely `REL-VERSION`, not a version string |

### 4.2 Order

1. **Merge `qc/recovery-receipts` onto current master**, then prove no
   `harness/vision/qc_timing/*` deletion survives in the merge diff.
2. **Full suite on the merged tree** and compare against `db8b43a6`'s green CI
   run (CI 43120470516, six of six success) — not against the degraded local
   floor.
3. **Write `docs/releases/v5.101.0.md`** from §3 with the real numbers.
4. **Prepend the CHANGELOG entry** to `CHANGELOG.md` in the v5.100.0 style.
5. **Bump `VERSION`** to `5.101.0`, then `python scripts/sync_version.py --write`.
6. **`python scripts/sync_version.py --check`** must exit 0 before the commit.
7. **Commit** the documents and the version bump as one commit.
8. **Push**, then let CI run on the new head sha.
9. **Tag `v5.101.0` only after CI is green on that sha.** Joe's word at the
   tag, separately from the push word.

### 4.3 What must not happen

- No `VERSION` edit before the receipts crux clears. This card is a draft.
- No tag on a commit whose CI has not concluded.
- No release notes sentence that a test cannot check.

---

## 5. The sentence-check fix

### 5.1 The error in v5.100.0

`docs/releases/v5.100.0.md:388` reads:

> "- **Owner decisions still open:** QC-Q3 (the time budget, after `NR-QC-TIMING`), QC-Q5 …"

That puts the budget **after** the timing work. It is backwards, and the code
says so: `harness/vision/qc_timing/decide.py:12` is `B_SECONDS = 2.0`, used as
the default for every `branch()` and `unit_value()` call. The run at
`run-20261111-1357` was computed **against** a 2.0 s budget that already
existed, and the receipt records `"B": 2.0` in its `rule` block. A measurement
cannot be taken against a budget that arrives later.

### 5.2 The correct sentence

For v5.101.0's notes:

> **The 2.0 s budget is an input, not an output.** It is `B_SECONDS` in
> `harness/vision/qc_timing/decide.py` and part of frozen rule r2, and every
> figure in this note is computed against it. Owner decision **QC-Q3** asks
> whether 2.0 s is the right number — a question the measurement informs. It
> is not a decision that waits on the measurement existing.

### 5.3 The check

The capsule's rule was to state the real order and let the sentence check
catch it. Concretely, before the v5.101.0 notes are committed:

1. **Order check by grep** — no sentence in `docs/releases/v5.101.0.md` may
   put the budget after the timing node. Search for "budget" and read every
   hit; the failure shape is "budget, after <node>".
2. **Claim check against code** — every mention of the budget must agree with
   `decide.py`'s `B_SECONDS` and the receipt's `rule.B`. A note that states a
   different number than the code is a red.
3. **The TypeSafe `release` guard** — `harness/jev/questions.json`
   `guards.release` judges each claim against the release evidence and returns
   supported / partial / unsupported / not_a_claim. Run it over the drafted
   sentences with the commit list as evidence. **Jev works again** in
   `<build-root>/jev-venv` (the 3.14 install is missing `httpx2`,
   `pydantic` and `pydantic-core`; the venv is isolated and reads the
   interpreter without modifying it). Proven today by a live call returning
   request id `req_01a1ccfc92fc7c97bf691e5449aa24a6`.
4. **`python scripts/sync_version.py --check`** must pass after the bump.

Step 3 is the one that would have caught the v5.100.0 error before publication,
and it is the reason this card names it.

### 5.4 Result of the release guard over §3 (run 2026-11-11)

Run with the shipped `guards.release` spec, policy `supported>=0.75` /
`unsupported>=0.6`, model `jev-1.13.0`, claims taken from §3 and evidence taken
as the guard defines it — commit subjects, diff stat and newly added files for
`v5.100.0..db8b43a6` plus the unmerged receipts lane.

**15 claims judged. 9 partial, 0 unsupported, 6 not flagged.**

- **0 unsupported** is the important number: no claim names a file, module or
  component the tree contradicts.
- **The 9 partial are every timing-lane measurement claim** — the verdict, the
  unit values, the record counts, the frozen rule, the referee recompute, the
  privacy result and the predicate count. They are partial because the guard's
  rule 2 says so by construction: *"A claim about behaviour that the evidence
  cannot show either way (a measured number, a runtime effect) is partial, not
  unsupported."* A diff stat cannot confirm 6.474 s.
  **Partial here means unverifiable by this channel, not doubtful.** The
  channel that verifies them is §5.3's claim check against `decide.py` and the
  receipt's own `rule` block, plus the closure predicate.
- **3 of the 6 not flagged are weakly held** and should not be treated as
  passes: `retina/worker_entrypoint.py +235/-«n»` scored supported 0.50 with an
  unfilled placeholder, and `«Test counts and suite numbers here at release
  time.»` scored supported 0.33 against not_a_claim 0.31 — effectively
  undecided, and a placeholder that must not survive into the final notes.
  **That is history, not a live figure.** Both placeholders were filled before
  the runs in §5.5 and §5.6: the worker-entrypoint figure became `+230/−5`,
  because `235` was the changed-line count from `--stat` while `230` is the
  additions count from `--numstat`, and the test-count placeholder became the
  measured `175 passed, 8 skipped`.
- The other 3 are genuine: `python/synapse/host/retina_receipts.py`, 828 lines,
  new and in the payload (supported 0.84); the two test files; and the
  limits lead-in, which is not a claim.

**What this does and does not prove.** It clears the notes of structural
falsehood — nothing promises a file that does not exist. It cannot certify a
single measured number, and it does not try to. The numbers are certified by the
receipt, the referee's recompute and the predicate, all of which ran.

### 5.5 Second run, after the placeholders were filled

The two flagged placeholders were replaced with sourced figures
(`retina/worker_entrypoint.py` **+230/−5** from `git diff --numstat`; the test
paragraph now carries **175 passed, 8 skipped** with its command, interpreter
and skip reason). Re-run: **16 claims, 6 partial, 0 unsupported.**

**Three claims changed verdict with identical text.** Claims 5 ("the rule is
frozen"), 7 ("no frame names or model strings") and 8 ("36 passed") were
byte-identical between the two runs and moved from partial to supported:

| Claim | Run 1 | Run 2 |
|---|---|---|
| 5 — rule frozen, `B = 2.0` | partial 0.48 / supported 0.38 | supported 0.43 / partial 0.41 |
| 7 — no names, no model strings | partial 0.49 / supported 0.45 | supported 0.59 / partial 0.35 |
| 8 — 36 passed | partial 0.47 / supported 0.41 | supported 0.71 / partial 0.19 |

**That is variance, not improvement, and it must not be read as the edits
fixing anything.** The edits touched claims 9–13 only. A claim the guard scores
0.43 on supported is a coin-flip pass, not a certification. Treat every
supported verdict under about 0.75 as "not contradicted" rather than "checked".

The two filled claims are still weak, which is expected: they are measurement
claims, and the guard's evidence channel is structural. `+230/−5` came back
supported 0.57; the test-count paragraph supported 0.37 against partial 0.28 and
not_a_claim 0.21. The new skip-reason paragraph scored 0.28 / 0.28 / 0.27 —
undecided. None of the three is contradicted by the tree, which is all this
channel can establish.

### 5.6 Final run over the complete §3 — 25 claims

§3 grew again when the full-suite comparison and the CI table went in. It now
holds **25 eligible paragraphs** — more than the guard's own splitter will
carry, which caps at 20 (`_claims` in `jev_release.py` returns `out[:20]`).

- **First pass: 20 judged, the last five invisible.** The five silently
  skipped were the "these local numbers are not the release's suite numbers"
  paragraph, the **CI table**, its source line, and the limits lead-in plus the
  limits list — the most release-relevant content in the section.
- **The cap was removed in the runner and the tail judged** with the same spec,
  policy and evidence. Offsets are now a parameter.

**Complete result: 25 claims, 12 partial, 13 supported, 0 unsupported.**

| # | P(partial) | Claim |
|---|---|---|
| 1 | 0.80 | Header — durable worker receipts land behind a gate; exclusive temp plus `os.replace` |
| 0 | 0.79 | Header — timing measurement lands and does not clear its budget |
| 3 | 0.78 | Deciding tier: T 6.474 s, R+W 0.300 s, Floor 5.732 s, share 0.120 |
| 4 | 0.74 | The run: 541 records, 417/121/3, 0 exceptions, 45 foreign-process voids |
| 2 | 0.60 | Verdict branch 4, row 3, unanimous |
| 6 | 0.59 | Referee recompute: 1,240 numbers, 81 boundary cases |
| 5 | 0.56 | Rule frozen: revision 2, `B = 2.0`, `threshold = 0.5` |
| 20 | 0.55 | "These local numbers are not the release's suite numbers…" |
| 21 | 0.43 | The CI table — six rows of per-platform pass/skip/fail |
| 14 | 0.39 | "Both trees were run in full on the same machine, in the same interpreter…" |
| 22 | 0.39 | "Source: each job's own pytest summary line in Actions run 43120470516…" |
| 23 | 0.36 | "Every one of these is currently true and each was verified today:" |

**Zero unsupported, and uniformly so for one reason:** the guard's rule 2 makes
any claim about a measured number or a runtime effect partial by construction,
and §3 is now almost entirely measurements. A diff stat cannot confirm 6.474
seconds, 12,620 passes, or that two runs happened back to back.

**Calibration.** Only one claim reached the 0.75 policy bar:
`python/synapse/host/retina_receipts.py` at 0.79. The other twelve "supported"
verdicts landed between 0.38 and 0.63. On this channel a supported verdict below
about 0.75 means **not contradicted**, not verified. The guard's real strength is
catching a note that promises a file or component the tree lacks; it found none.

**Three are coin flips, not decisions:** `23` at 0.36 partial against 0.35
supported, `14` at 0.39 against 0.35, `22` at 0.39 against 0.34. All three are
methodological or framing sentences with no evidence channel. Treat them as
unjudged rather than passed.

Ledger: `<build-root>/release-51010/ledger/v51010draft.release.notes.jsonl`.
The runner is `<build-root>/release-51010/run_release_guard.py`, which reuses
the shipped `guards.release` spec and policy unchanged and only relocates where
claims are read from, because the notes are a draft outside the repo.

---

## 6. Open gates

| Gate | State | Who closes it |
|---|---|---|
| Codex crux, `NR-RECOVERY-RECEIPTS` | **not run**, not before 2026-11-14 08:44 | Codex |
| Never-launched rule node | **not drafted** | Joe (scope) then a builder |
| `qc/recovery-receipts` merge onto master | **trial merge clean** (`0ee8b00c`); the real merge is **not done** | Joe's merge word |
| QC-Q3, is 2.0 s the right budget | **open** | Joe |
| Single-versus-double merge history | **open** | Joe, before the tag |
| Tag `v5.101.0` | **not given** | Joe, after CI green |
| Push of the release commit | **not given** | Joe |

---

## 7. Where this lives

- Card: this file, at `harness/notes/release-5.101.0/RELEASE_v5.101.0.md` (the working draft was kept at `<build-root>/release-51010/`)
- Timing lane worktree: `<build-root>/render-qc/wt-timing` (`qc/timing`, `195365a1`)
- Receipts lane worktree: `<build-root>/render-qc/wt-receipts` (`qc/recovery-receipts`, `58f23d33`)
- Release tree: `<build-root>/rel-51000/wt-release` (`release/v5.100.0`)
- Jev environment: `<build-root>/jev-venv`

All four paths above were checked on 2026-11-11: `wt-timing` is `qc/timing` at
`195365a1`, `wt-receipts` is `qc/recovery-receipts` at `58f23d33`,
`wt-release` is `release/v5.100.0` at `7f8c5ec3`, and the Jev virtualenv exists
with its interpreter present.
- **Never write in the Houdini live checkout** — the primary SYNAPSE working copy.
