# TIDY — Fix Proposals (diagnose-fixes dispatch)

> Proposals only. **Nothing here is applied by the harness.** Each entry is a
> diagnosis with the exact change needed and the risk. The human applies each
> fix (or approves the state-file edit / destructive prune). See
> `harness/tidy/SPEC.md` (FIX disposition).
>
> Generated: 2026-08-07 · Dispatch agent: diagnose-fixes
>
> Scope: TIDY-18..TIDY-23. All items verified present against the live tree
> before writing (the inventory was not stale).

---

## TIDY-18 — `harness/legs.json`: M5 / M5b legs stale `ready`

**Path:** `C:/Users/User/SYNAPSE/harness/legs.json`

**What is wrong:** The `M5` (blocks reconciler) and `M5b` (blocks reconciler —
close M5 rulings) legs both report `"state": "ready"`, but **both are merged to
master**:

| Leg | state | merged by | branch HEAD | ancestor of master? |
|---|---|---|---|---|
| M5 | `ready` | `d6b22a4e` | `blocks/m5-reconciler` @ `87927076` | YES |
| M5b | `ready` | `c4187d01` | `blocks/m5b-rulings` @ `2a2d88c4` | YES |

Verified live: `git merge-base --is-ancestor 87927076 master` → YES, and
`git merge-base --is-ancestor 2a2d88c4 master` → YES. Both branches are fully
contained in master (no commits ahead). The `ready` state is stale — the work
shipped.

**The CI0 leg is correct and must NOT be touched:** the committed `legs.json`
has **no** CI0 row; the uncommitted working-tree diff correctly **adds** the CI0
leg (`state: ready`, base master, branch `ci/ci0-honest-green`). CI0 is **not**
merged (`992a48f2` is ahead of master, not an ancestor). The CI0 row ships with
the CI0 merge. Leave it as-is.

**Exact change needed (human applies to `harness/legs.json`):** flip M5 and M5b
to `"state": "done"` and add the `closed_note` + `worktree_released` fields,
matching the established done-leg convention (see V3 at lines 473-474, F1 at
lines 210-211):

- **M5:** `"state": "done"`, `"closed_note": "state->done 2026-08-07 (TIDY-18): blocks/m5-reconciler ancestor-merged into master (d6b22a4e)"`, `"worktree_released": ".claude/worktrees/m5-reconciler"`.
- **M5b:** `"state": "done"`, `"closed_note": "state->done 2026-08-07 (TIDY-18): blocks/m5b-rulings ancestor-merged into master (c4187d01)"`, `"worktree_released": ".claude/worktrees/m5b-rulings"`.

**Risk:** Low. This is a state-file correction to match reality; the orchestrator
reads `state` to decide whether a leg still needs dispatch, so leaving `ready`
on a merged leg risks a redundant re-dispatch. The edit is **human-approved** —
this dispatch does not mutate `harness/legs.json` (safety model).

**Disposition:** FIX (proposed). Action: human edits `harness/legs.json` per above.

---

## TIDY-19 — `models/` → `.gitignore`

**Path:** `C:/Users/User/SYNAPSE/models/` (untracked, `?? models/`)

**What is wrong:** `models/minilm-l6-v2.onnx` (90,405,214 bytes ≈ 90MB) is a
downloaded ONNX embedder sitting untracked at the repo root. It is a **download
cache / model asset, not source** — committing it would bloat the repo by 90MB
and is not reproducible from the tree. `docs/DEBUT_READINESS.md` is explicit that
no model ships with the repo and the embedder is expected at
`~/.synapse/models/` (outside the tree). `SemanticEmbedder` degrades gracefully
to `HashEmbedder` when the file is missing, so ignoring it breaks nothing.

**Exact change needed (human applies to `.gitignore`):** append
`models/` (with a comment). The full proposed block, evidence, and rationale are
already written in `harness/tidy/GITIGNORE_PROPOSAL.md` §1 — this dispatch does
not duplicate it.

**Risk:** None to the tree. The 90MB file stays on disk, untracked. No code
depends on the in-tree copy.

**Disposition:** GITIGNORE (proposed). Action: human appends `models/` to
`.gitignore` per `GITIGNORE_PROPOSAL.md`.

---

## TIDY-20 — `shot_layers/` → `.gitignore`

**Path:** `C:/Users/User/SYNAPSE/shot_layers/` (untracked, `?? shot_layers/`)

**What is wrong:** `shot_layers/` holds 5 tiny USDC files (`animation.usd`,
`fx.usd`, `layout.usd`, `lighting.usd`, `render.usd`, 492 bytes each). This is
**not a real fixture** — it is the recurring **RES-F11 / R57** test litter: the
solaris live tests write USD department layers into the repo root via the
no-`hou`/fake-hou fallback of `solaris_compose_tools.py:133-136`
(`os.makedirs(hou.expandString('$HIP/' + shot + '_layers'))`). When `$HIP` is
empty (no-`hou` test path), `expandString` resolves relative to CWD, so the
layers land in the repo root. Every hython suite run dirties the working tree.

**Exact change needed (human applies to `.gitignore`):** append
`shot_layers/` (with a comment). The full proposed block, evidence trail
(CTO_RULINGS_01.md:1469 R57, S2_PREMORTEM.md:1039, RES.json:308-331,
S2.json:161-162), and rationale are already written in
`harness/tidy/GITIGNORE_PROPOSAL.md` §2 — this dispatch does not duplicate it.

**Risk:** None to the tree. The 5 files stay on disk, untracked. Note the
**root-cause** (missing absolute-path guard at `solaris_compose_tools.py:133-136`)
is a `src/` change and is out of scope for this dispatch — gitignoring stops the
tree-dirtying but does not fix the write site.

**Disposition:** GITIGNORE (proposed). Action: human appends `shot_layers/` to
`.gitignore` per `GITIGNORE_PROPOSAL.md`.

---

## TIDY-21 — `mcp_server.py` list_tools CI red — **already fixed on master**

**Path:** `C:/Users/User/SYNAPSE/mcp_server.py` (line 1067 `@server.list_tools()`)

**What is wrong (historical):** Pre-existing master CI red since 2026-07-29: the
`mcp` library dropped `Server.list_tools()` / `Server.call_tool()` decorators,
causing a collection error at `mcp_server.py:1067` + 2 tests. Local Windows was
green because the local `mcp` still had the API.

**Diagnosis — the fix is ALREADY committed on master:** commit `9c8fe878`
"fix(deps): pin mcp==1.26.0 to re-green CI (CLEAR L3 / P3.2)" pins
`mcp==1.26.0` in `pyproject.toml` (line 58). Verified: `git show HEAD:pyproject.toml`
contains `"mcp==1.26.0"`. The pin keeps the old decorator API working, so the
collection error is resolved. The CI0 leg's own verify (`harness/clear/verify.py`
`p3_2`) checks "mcp_server.py off the dropped list_tools API **OR** mcp pinned" —
the pin satisfies it (PASS).

**Exact change needed:** **None for the pin** — it is done. The residual CI red
(3 real failures: missing `synapse.memory.evolution` rot + one environmental) is
owned by the **CI0 leg** (`ci/ci0-honest-green`, in progress, ahead of master at
`992a48f2`). Per the brief, TIDY-21 **folds into the CI0 leg**. If the human
wants to fully migrate off the dropped decorator API (rather than pin), that is a
separate `mcp_server.py` change (rewrite `@server.list_tools()` at :1067 to the
new API) and is out of scope for this dispatch.

**Risk:** None. The pin is already in place and correct. Do not unpin.

**Disposition:** FIX (already applied on master) / DEFER to CI0 leg. Action:
none required from this dispatch; CI0 owns the residual CI green.

---

## TIDY-22 — prune merged worktree + branch `blocks/m5-reconciler`

**Path:** worktree `C:/Users/User/SYNAPSE/.claude/worktrees/m5-reconciler` ·
local branch `blocks/m5-reconciler` · remote `origin/blocks/m5-reconciler`

**What is wrong:** The worktree/branch was merged to master (`d6b22a4e`) but
never cleaned up. Verified: `git worktree list` shows the worktree at
`87927076 [blocks/m5-reconciler]`; `git merge-base --is-ancestor 87927076 master`
→ YES; `git log master..HEAD` in the worktree → **empty** (nothing ahead of
master); `git merge-base --is-ancestor origin/blocks/m5-reconciler master` → YES
(remote also merged). The worktree is clean (no committed work to lose).

**Untracked files that pruning removes (not real work, but noted):**
- `.claude/.orch_launched` (orchestrator launch timestamp marker)
- `harness/blocks/runs/m5_invariants_20260806_190754/` (`FAILED` + `invariants_m5.json` — a test run artifact)

These are run outputs, not authored work; the invariants evidence is regenerable
from the committed fixture/tests. Flagged so the human knows what a prune deletes.

**Exact change needed (human executes — destructive):**
```
git worktree remove .claude/worktrees/m5-reconciler
git branch -D blocks/m5-reconciler
git push origin --delete blocks/m5-reconciler
```

**Risk:** Destructive and irreversible (branch force-delete has no reflog
recovery). Safe **only** because the branch is a confirmed ancestor of master
(merged). The remote delete is a remote mutation — the safety model does not
authorize it from this dispatch. **Human approval required.**

**Disposition:** PRUNE (proposed). Action: human runs the three commands above.

---

## TIDY-23 — prune merged worktree + branch `blocks/m5b-rulings`

**Path:** worktree `C:/Users/User/SYNAPSE/.claude/worktrees/m5b-rulings` ·
local branch `blocks/m5b-rulings` · remote `origin/blocks/m5b-rulings`

**What is wrong:** The worktree/branch was merged to master (`c4187d01`) but
never cleaned up. Verified: `git worktree list` shows the worktree at
`2a2d88c4 [blocks/m5b-rulings]`; `git merge-base --is-ancestor 2a2d88c4 master`
→ YES; `git log master..HEAD` in the worktree → **empty**; `git merge-base
--is-ancestor origin/blocks/m5b-rulings master` → YES (remote also merged). The
worktree is clean.

**Untracked files that pruning removes (not real work, but noted):**
- `.claude/.orch_launched` (orchestrator launch timestamp marker)
- `harness/blocks/runs/m5_invariants_20260806_214024/` (`DONE` + `invariants_m5.json` — a test run artifact)

Same class as TIDY-22: run outputs, regenerable, not authored work.

**Exact change needed (human executes — destructive):**
```
git worktree remove .claude/worktrees/m5b-rulings
git branch -D blocks/m5b-rulings
git push origin --delete blocks/m5b-rulings
```

**Risk:** Destructive and irreversible. Safe **only** because the branch is a
confirmed ancestor of master (merged). Remote delete is a remote mutation — not
authorized from this dispatch. **Human approval required.**

**Disposition:** PRUNE (proposed). Action: human runs the three commands above.

---

## Gate summary

| Item | Disposition | Gate |
|---|---|---|
| TIDY-18 `legs.json` M5/M5b stale `ready` | FIX | Human edits `harness/legs.json` (state file — not mutated here) |
| TIDY-19 `models/` | GITIGNORE | Human appends `models/` to `.gitignore` (see GITIGNORE_PROPOSAL.md) |
| TIDY-20 `shot_layers/` | GITIGNORE | Human appends `shot_layers/` to `.gitignore` (see GITIGNORE_PROPOSAL.md) |
| TIDY-21 `mcp_server.py` list_tools | FIX (already applied) / DEFER to CI0 | None — pin `mcp==1.26.0` already on master (9c8fe878); CI0 owns residual CI green |
| TIDY-22 prune `blocks/m5-reconciler` | PRUNE | Human runs `git worktree remove` + `git branch -D` + `git push origin --delete` |
| TIDY-23 prune `blocks/m5b-rulings` | PRUNE | Human runs `git worktree remove` + `git branch -D` + `git push origin --delete` |
