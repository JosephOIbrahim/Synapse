# spec-CLOSER — the organ between "found" and "merged"

**Status:** Phase 1 built 2026-07-29. Phase 2 specified, not built.
**Authority:** bounded autonomy (human decision, this session).
**Producer for every number below:** named inline. Nothing here is recalled.

---

## 1 · The job

SYNAPSE **reviews** well and **improves** well. Both halves exist and are good.
What is missing is the thing *between sprints*: nothing decides what runs next,
and nothing carries a finding forward once its receipt is written.

The CLOSER owns exactly that gap. It is not a new harness. `run.ts`,
`orchestrate.ps1`, `checks.py`, the Generator/Evaluator adversary, the 13-agent
roster, the R/S/D fingerprint-gate pattern and the three human gates all stay.

**What must never happen:** the CLOSER merges to main, flips `drop.json`, makes
an architecture ruling, or writes `ratified`. Those are Constitution Article I
gates and bounded autonomy does not reach them.

---

## 2 · Evidence this gap is real

| Signal | Number | Producer |
|---|---|---|
| legs at `ready`, dispatched by nobody | 22 of 32 | `harness/legs.json` |
| flywheel cycles at `ratified:false` | 26 of 52 | `harness/state/flywheel_queue.json` |
| …of those, gating nothing mechanically | 24 of 26 | audit `ratification-bottleneck`, 2026-07-29 |
| …classifying as agent-provable under Art. I | 5 of 26 | same |
| receipt files for 32 legs | 41 | `ls harness/notes/receipts/` |
| receipts NOT plain green | 17 of 41 | `status` field census, this spec §6 |
| receipts whose `findings[]`/`for_ruling[]` any code reads | **0** | audit `loop-closure`, CONFIRMED |
| scheduled/continuous re-review anywhere | **none** | `.github/workflows/ci.yml` is `on: push, pull_request` |

**The one sentence:** a finding reaches a receipt and stops there, because no
consumer exists downstream of the receipt and no clock exists upstream of the
next sprint.

### The correction that matters

An earlier read of this gap held that the 26-deep ratification queue was
*over-gated* — that Article I already licenses agents to decide most of it. The
triage refutes that: **20 of 26 are genuine human judgement calls.** The
bottleneck is not authority, it is **triage attention on items that gate
nothing**. Batching and aging fix it. Reclassification does not.

Recorded because the wrong diagnosis would have pushed work past a real gate.

---

## 3 · Phase 1 — built, green, mutation-proved

### 3.1 The concurrency fence

`harness/state/locks/` had a reader (`harness/status.py:62`) and, in Python and
TypeScript, no writer. `harness/orchestrate.ps1:102` *does* write one — a fact
missed on first pass because the search excluded `*.ps1`. So the fence existed
in PowerShell and was absent from every other dispatch path, including
`run.ts`, which takes no lock at all.

`harness/lock.py` is the language-neutral client of **the same protocol**, not a
third implementation:

- writes `orchestrate.ps1`'s exact fields (`leg`, `pid`, `started`, `machine`)
  plus additive ones (`worktree`, `branch`, `base_sha`, `heartbeat_at`, `agent`)
- reads either dialect — `started_epoch()` parses the ISO string *and* the float,
  because a reader fluent in only its own dialect scores the other's lock as age
  zero and silently disables staleness
- refuses pid 0 and pid 4. `Get-Process -Id 0` is Idle and `-Id 4` is System;
  both always resolve, so either would read as a live holder **forever** and the
  leg could never be reclaimed. This was a live bug in the first draft.
- `acquire` is `O_CREAT|O_EXCL` — the throw is the mutex, not a check-then-write
- reap requires a dead pid **and** a quiet clock. Never one alone.

### 3.2 The board's verdict rule

`state_of()` read receipt **presence** as success:

```python
if receipt_for(leg): return "done"      # before
```

17 of 41 receipts are not plain green — `amber` ×6, `green_with_findings` ×4,
no `status` field ×4, `held_not_started` ×2, `green-with-collision`, `red`,
`green_measurement_red_finding`. All 17 printed as done. `H2.json` says
`held_not_started` in as many words and the board called it complete.

That is this project's central finding for the third time: `heats_status.py` was
retired for rendering real receipts into a layout that no longer described
anything, and its replacement went on reading presence as success.

Now: `verdict_of()` reads the field. A leg is `done` only on green; anything
else surfaces as `attention` carrying the receipt's own word. A non-green
receipt also no longer satisfies a downstream dependency — a halted leg must not
unblock work that was waiting on it.

Board moved 32 done → 26 done + 6 attention.

### 3.3 Still open in Phase 1

- **`orchestrate.ps1:151` has the identical presence-is-done bug**, in the LIVE
  dispatcher, where it drives dispatch rather than a display. Not fixed here:
  changing it could flip amber legs out of `done` and cause re-dispatch of
  finished work. Needs a look at every `Get-LegState` consumer first.
- `run.ts` takes no lock. Wire it to `harness/lock.py check` at dispatch.
- Both dispatchers decide "a worktree exists here" with a filesystem existence
  test rather than `git worktree list`. An orphaned directory makes the
  dispatcher launch an agent into the **main repo on the live branch**.
- 7 of 41 receipts carry no commit field at all.

---

## 3.4 · P0 — worktree isolation (found 2026-07-29; **NOT closed**)

Ruled ahead of everything else because it is the only open finding that can
**destroy work** rather than merely delay it.

`.claude/worktrees/` holds 26 directories. Twelve are registered git worktrees.
Fourteen are orphans — plain directories still inside the main repo. Being
inside it, git run from one walks up:

```
git -C .claude/worktrees/h2-requalify rev-parse --show-toplevel
    -> C:/Users/User/SYNAPSE
git -C .claude/worktrees/h2-requalify rev-parse --abbrev-ref HEAD
    -> feat/repair-heats-01
```

`orchestrate.ps1:238` created a worktree only when the directory was **absent**,
so an orphan skipped creation and the dispatcher launched an acceptEdits agent
whose commits landed on the live branch of the main tree. Article V inverted:
the isolation mechanism routing back into the thing it isolates from, while the
board still reported the leg as isolated.

**Armed at discovery:** 14 legs; 9 at `state: ready` — RES H3a H5 H7 H8 V1 C1
RSI0 S0. Producer: `python harness/worktree_guard.py audit`.

**The fix, three placements:**

| Where | What |
|---|---|
| `harness/worktree_guard.py` | the policy — registry check **and** resolution check; `orphan` is the dangerous class |
| `harness/lock.py` acquire | refuses with exit 5 — **direct callers only; no dispatcher calls this module** |
| `orchestrate.ps1:241` | refuses on the directory-exists branch — **1 of 5 worktree-decision sites** |
| `harness/status.py` | board line `isolation N LEG(S) ARMED` |
| `harness/statusline.py` | always-on bar, `!N armed` |

### What the adversarial pass refuted about this fix

Recorded because a partial fix described as a complete one is worse than no fix.

1. **The dispatcher manufactures SOME orphans — 6 of 14, not all.**
   `orchestrate.ps1:239` discards `git worktree add`'s exit code, and — the
   stronger anchor, missed on first pass — `$ErrorActionPreference =
   'SilentlyContinue'` at `:19` drops the failed add's stderr ErrorRecords
   through the pipe, so **a failed add leaves no log line at all**. `:334` then
   unconditionally `New-Item`s `$wt/.claude` *after* the launch, producing an
   unregistered directory at exactly the path the next dispatch will `Test-Path`
   as "exists".

   Reproduced end-to-end (add exit 255, no directory, no output, `:334` creates
   it unregistered) and observed live on **2026-07-27 14:41:25–30** manufacturing
   six orphans — H9 V1 C0 RSI0 S0 S1. Evidence: six DISPATCH blocks with no
   `HEAD is now at` line, directory `CreationTime` matching the dispatch second,
   and `.claude/{.orch_launched, settings.local.json}` as the only contents.

   The other 8 orphans came from a **different, non-orchestrator process**:
   seven were once-real worktrees emptied 2026-07-26 19:33:52–19:34:00 (they
   contain no `.claude` at all, so `:334` never ran on them), and
   `c1-token-bench` had its `.git` stripped 2026-07-27 14:40:49. **That process
   is unidentified and is a separate open question.**

2. **REFUTED — the failed-add case does NOT land the agent in the main repo root.**
   An earlier draft of this spec, and the commit message of `55371c9`, claimed
   it did. The sub-mechanics are real (a failed `Set-Location` is
   non-terminating, the `claude` line is reached, `Start-Process` honours the
   provider location rather than the process cwd) — but nothing between `:315`
   and `:334` can abort, so `:334` always creates `$wt` **67 ms** after launch
   while the child's first statement runs at **+1294 ms**. The child loses the
   race by ~1.2 s and its `Set-Location` succeeds. The agent lands in the
   freshly-manufactured orphan, not the repo root.

   Kept in the record rather than deleted: the corrected mechanism is still a
   P0, and the refuted one shows how a chain of individually-true steps
   assembles into a false scenario.
3. **`lock.py` is on no dispatch path.** Its guard protects direct callers only.
4. **`os.getppid()` is the wrong pid default under real dispatch** — it is a
   per-command `bash.exe` that dies within a second.
5. **Locks leak permanently in both implementations.** `orchestrate.ps1` binds
   to a `-NoExit` console that outlives the agent, so its lock never goes stale.

### The P1 must not be fixed before the P0

**`presence-is-done` is currently the only thing suppressing the P0.** Six legs
change state under a status-aware rule, and H2 — whose worktree is an orphan —
becomes dispatchable. Fixing P1 first would have *armed* the P0. Verdict from
the blast-radius investigation: **UNSAFE-NEEDS-MORE**.

### Recovery — the orphans hold real work

**The three receipts `orchestrate.ps1:148` declares lost are NOT lost.** All
three reconstruct from the orphan directories. Across the 14 orphans, **51 files
(~481 KB) exist at no path in the main tree**; the largest block is
`v1-capture-probe` — 17 probe scripts under `harness/notes/v1/`.

Recovery precedes any cleanup. This is why the guard reports and never reclaims.

**It never deletes.** Law 4, and `orchestrate.ps1:142` records a housekeeping
pass that already destroyed the only copies of three receipts. An orphan may be
the last copy of something. `test_guard_never_deletes` pins this with a canary
file.

**Deliberately red on arrival.** `audit` exits 5 against this tree today. It
goes green when every leg's worktree is registered or absent — the actual
remediation, not a suppression.

Pinned by `tests/test_worktree_guard.py` (7 tests). Blinding `classify` to
return `registered` fails 3 of them.

---

## 4 · Phase 2 — the agent spine (specified, not built)

`.claude/workflows/synapse-close.js`, one cycle per invocation.

```
REVIEW    parallel, read-only        re-derive health from producers, never from
                                     the last report. New findings enter the ledger.
   ↓
TRIAGE    single, judgement          each open finding → PROVABLE | GATE | STALE,
                                     ranked by leverage. Ages everything.
   ↓
REPAIR    pipeline, one lock each    top-K PROVABLE only. worktree-isolated,
                                     forge → assayer → crucible → receipt.
   ↓
RATCHET   per landed fix             plant a durable regression gate in the
                                     checks.py fingerprint style so the finding
                                     cannot silently reopen.
   ↓
BATCH     single                     ONE ranked decision surface. Every GATE item
                                     with its evidence and the exact one-line flip.
```

**Why a workflow and not more TypeScript:** deterministic state must not live in
an LLM, and agent teams must not live in a script. The ledger and the lock are
Python; the fan-out and judgement are a workflow. Neither owns the other's job.

**Ordering constraint:** REPAIR must take a lock through `harness/lock.py` before
touching a worktree, or it reproduces the H2 collision at N× the rate.

**Gate on the whole spine:** `ratified` is never written. The BATCH surface
proposes; the human flips. Confirmed by audit that the read path is already
exemplary — and that exactly one workflow deliberately writes the file, which
is the hole to close before REPAIR is armed.

---

## 5 · Acceptance criteria

Each states the condition under which it FAILS. Built ones are pinned in
`tests/test_harness_lock.py` and were each proved to go red under a mutation.

| # | Check | Fails when | Status |
|---|---|---|---|
| 1 | second acquire on a held leg | it exits 0 | **green**, mutation-proved |
| 2 | lock records a resolvable base commit | `base_sha` absent or `git cat-file` fails | **green** |
| 3 | live lock survives reap | reap deletes it | **green**, mutation-proved |
| 4 | stale lock is reclaimed | it survives reap | **green**, mutation-proved |
| 5 | ps1-format lock refuses a python acquire | the seam lets a second agent in | **green** |
| 6 | ISO `started` ages correctly | parsed as epoch 0 | **green** |
| 7 | reserved pids refused | pid 0 or 4 is written | **green**, mutation-proved |
| 8 | board reads status not presence | a non-green receipt counts as done | **green**, mutation-proved |
| 9 | board shows a locked leg as running | a live leg reads `ready` | **green** |
| 10 | no finding ages past N days without disposition | an item sits untriaged | **Phase 2** |
| 11 | ratchet gate goes RED against the unfixed tree | the planted gate is green pre-fix | **Phase 2** |
| 12 | CLOSER never writes `ratified` | any write reaches the field | **Phase 2** |

Full suite after Phase 1: **5285 passed, 137 skipped, 0 failed** (`pytest tests/`).

Test 10 is the one that makes the loop *closed* rather than merely *observable*.
Everything above it is plumbing.

---

## 6 · Receipt status census — producer for §2

```
python - <<'PY'
import json,glob,collections
c=collections.Counter()
for f in glob.glob('harness/notes/receipts/*.json'):
    try: c[str(json.load(open(f,encoding='utf-8')).get('status'))]+=1
    except Exception: pass
print(dict(c))
PY
```

Emitted 2026-07-29 on `feat/repair-heats-01` @ `c0bdba8`:

```
green 22 · amber 6 · green_with_findings 4 · None 4 · held_not_started 2
green-with-collision 1 · red 1 · green_measurement_red_finding 1
```
