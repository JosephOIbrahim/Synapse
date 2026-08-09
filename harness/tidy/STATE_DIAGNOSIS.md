# TIDY — State Reconciliation Diagnosis

> Dispatch: state-reconcile (READ-ONLY). Diagnosed 2026-08-07 against git reality.
> Scope: `harness/legs.json` and `harness/rope/STATE.json`. No state file was edited.
> Disposition per TIDY SPEC: both files were classified REVIEW; the findings below
> resolve them to COMMIT (rope) and FIX (legs).

---

## 1. `harness/legs.json` — 2 stale entries (M5, M5b); CI0 is correct

### 1.1 M5 — `blocks/m5-reconciler` — STALE: `ready` → `done`

**What is stale:** `state: "ready"` on the M5 leg. The branch is **fully merged to master**.

**Git reality (verified):**
- Merge commit `d6b22a4e` "merge M5: BLOCKS reconciler" is on master.
- The branch tip `87927076` is the merge's **second parent** (`d6b22a4e^2`), i.e. the branch was merged in whole, not cherry-picked.
- `blocks/m5-reconciler` appears in `git branch --merged master`.
- Worktree still exists at `.claude/worktrees/m5-reconciler` (checked out at `87927076`, the merged tip).

**Correct state:** `state: "done"`, with a `closed_note` recording the merge and a `worktree_released` entry, matching the pattern of every other done leg (H2, F1, V0, E1, V3).

**Exact edit needed** (in the M5 leg object, `harness/legs.json`):
```jsonc
"state": "done",
"closed_note": "state->done 2026-08-07 (tidy state-reconcile): branch blocks/m5-reconciler merged to master at d6b22a4e (tip 87927076 is the merge's second parent); BLOCKS reconciler shipped",
"worktree_released": ".claude/worktrees/m5-reconciler"
```

### 1.2 M5b — `blocks/m5b-rulings` — STALE: `ready` → `done`

**What is stale:** `state: "ready"` on the M5b leg. The branch is **fully merged to master**.

**Git reality (verified):**
- Merge commit `c4187d01` "merge M5b implementation: c3 baseline, eject, symbol table (2a2d88c4)" is on master.
- The branch tip `2a2d88c4` is the merge's **second parent** (`c4187d01^2`).
- `blocks/m5b-rulings` appears in `git branch --merged master`.
- Worktree still exists at `.claude/worktrees/m5b-rulings` (checked out at `2a2d88c4`, the merged tip).

**Correct state:** `state: "done"`, with `closed_note` + `worktree_released`, same pattern as M5.

**Exact edit needed** (in the M5b leg object, `harness/legs.json`):
```jsonc
"state": "done",
"closed_note": "state->done 2026-08-07 (tidy state-reconcile): branch blocks/m5b-rulings merged to master at c4187d01 (tip 2a2d88c4 is the merge's second parent); four M5 rulings closed (c3 / display / eject / symbol table)",
"worktree_released": ".claude/worktrees/m5b-rulings"
```

### 1.3 CI0 — `ci/ci0-honest-green` — CORRECT: stays `ready` (NOT stale)

**What is NOT stale:** `state: "ready"` on the CI0 leg is accurate.

**Git reality (verified):**
- `ci/ci0-honest-green` is **NOT** in `git branch --merged master`.
- The CI0 fix commit `14ad01e7` "fix(ci): CI0 — master's CI made honestly green" is on the ci0 branch but **NOT** on master (`git merge-base --is-ancestor 14ad01e7 master` → NO).
- Branch tip `992a48f2`; worktree alive at `.claude/worktrees/ci0-honest-green`.

**Correct state:** `state: "ready"` — unchanged. CI0 is genuinely unmerged work awaiting dispatch/merge.

### 1.4 No other staleness

All other 19 `ready` legs (RES, H3a, H3b, H4, H5, H6, H7, H8, U1, V1, C1, RSI0, S0, S2, S3, I0, I1, E0, V2) have branches **not** merged to master — all correctly `ready`. No edit.

---

## 2. `harness/rope/STATE.json` — 1 uncommitted change; NOT stale (working tree is correct)

### 2.1 L5-13 status `needs_review` → `blocked` — legitimate verdict, uncommitted

**What is stale:** Nothing in the *content* — the working tree is correct. What is stale is the **git state**: the working tree holds a deliberate status change that was never committed, so `git HEAD` disagrees with the working tree.

**The uncommitted diff (verified):**
```diff
-   "status": "needs_review",
+   "status": "blocked",
```
on task **L5-13** "Make prominence visible — QSS rules for hero/quiet".

**Why this is a legitimate verdict, not an error:**
- The runner's own recon output `harness/rope/_recon_status.txt` (generated after the edit) lists `L5-13  blocked  a=0` — the working tree and the runner agree.
- `blocked` with `attempts=0` is only reachable through the runner's `verify` command (`runner.py` `cmd_verify`: `--failed` → `t["status"] = "blocked"`), i.e. a deliberate human/verifier rejection — not the 2-strike auto-block path (which requires `attempts >= 2`).
- L5-13's standalone deliverable was superseded by the amendment chain L5-14 ("AMEND L5-13, do not redo it") / L5-15 / L5-16. A verifier rejecting L5-13 as superseded is the correct, honest disposition. The dependents (L5-14..L5-23) remain `needs_review` because they are separate, still-open tasks — a blocked base does not gate them (deps are dispatch ordering hints, not status gates).

**Correct state:** L5-13 = `"blocked"` — the working tree already holds the correct value. **Do not revert it.**

**Exact edit needed:** None to content. The reconciliation action is to **commit** the working-tree change so git agrees:
```
git add harness/rope/STATE.json
git commit -m "rope: L5-13 prominence base rejected as superseded by the L5-14/15/16 amendment chain (verify verdict)"
```
This is a COMMIT disposition (real, deliberate state), not a FIX. Per the safety model this is proposed for the human to approve — the dispatch agent does not commit.

---

## 3. Summary table

| File | Item | Working-tree state | Git reality | Verdict | Action |
|---|---|---|---|---|---|
| legs.json | M5 | `ready` | merged @ d6b22a4e | **STALE** | FIX → `done` + closed_note + worktree_released |
| legs.json | M5b | `ready` | merged @ c4187d01 | **STALE** | FIX → `done` + closed_note + worktree_released |
| legs.json | CI0 | `ready` | not merged | correct | no change |
| legs.json | other 19 `ready` | `ready` | not merged | correct | no change |
| rope/STATE.json | L5-13 | `blocked` | HEAD `needs_review` | **working tree correct, uncommitted** | COMMIT the change (proposed) |

## 4. Open human gates

1. **Approve the legs.json FIX** — set M5 and M5b to `done` (exact edits in §1.1/§1.2). This is a state-file edit, so it must be applied by the producer path / human, not by a dispatch agent.
2. **Approve the rope/STATE.json COMMIT** — commit the L5-13 `blocked` verdict (§2.1). No content change; the working tree is already correct.
