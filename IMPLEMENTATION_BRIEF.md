# IMPLEMENTATION BRIEF — stand up the SYNAPSE → H22 harness

**You are implementing an existing harness, not designing one.** Ten files were generated in
a prior session. Your job: place them in the SYNAPSE repo and resolve the wiring (the `ADAPT`
anchors) so the loop runs truthfully on H21 **today**. You are not redesigning it, not
expanding it, and not attempting the post-drop pipeline (Houdini 22 isn't out yet).

This brief is the **procedure**. The source of truth for *what the harness is* lives in the
files themselves — read these three first and treat them as authoritative:
`harness/README.md`, `harness/state/claude-progress.md`, `CLAUDE.md`. **If this brief ever
conflicts with those files, the files win — flag the conflict to the human.**

> **Environment assumption:** you have filesystem access to the SYNAPSE repo (Claude Code).
> If you are a chat *without* the repo, you can only review/adapt file text the human pastes —
> say so and ask for repo access, because every wiring step below requires reading real
> entrypoints. Do not guess repo internals from memory.

---

## The shape, in brief
A long-running loop: **fresh Generator (WIP=1) → `checks.py` (deterministic) → adversarial
Evaluator → PASS or repair-ticket → loop**, capped at `MAX_ROUNDS` before a task is flagged
for the human. It runs headless for cooks/renders/patches/worktree-commits. Full detail is in
the files; don't re-derive it here.

## TWO MODES — you only touch Mode A
- **Mode A (now, H21):** `harness/state/drop.json` absent → only Phase 0 tasks (`0.1`–`0.7`) run.
- **Mode B (mid-July):** a human writes `drop.json` → the `1.x`/`2.x`/`3.x` pipeline arms on H22.
  **Do not attempt Mode B. Do not stub its checks to pass. It cannot be tested until H22 ships.**

## THE THREE HUMAN GATES — do not cross these
1. **`0.1` sidecar vs abi3.** *Recommended: **sidecar*** (brain in its own pinned interpreter,
   immune to H22's Python). **Surface the recommendation; do not commit the architecture.**
   While wiring, check whether `host/daemon.py` already implies an out-of-process design and
   report that finding to the human.
2. **The drop trigger** (`1.1`/`1.2`): only a human installs H22, reads the three numbers, and
   writes `drop.json`. Never create `drop.json` yourself.
3. **Merge to main.** The harness commits in worktrees only. Never `git push` or `git merge`.

## DISCIPLINE CONTRACT — read twice
- **Never make a check return `True` to pass a task.** A check you cannot wire stays
  `ok:false` with an honest reason string. Faking a pass defeats the entire harness.
- **Do not expand the harness.** No new abstractions, no parallelism, no extra tools. v1 is
  WIP=1 / sequential **by choice**. Adding scope here is the failure mode, not a contribution.
- **Do not refactor SYNAPSE's product code.** Read its entrypoints to learn real values; edit
  product code only if an `ADAPT` genuinely requires it, and prefer reading over editing.
- **The harness is a tool, not the project.** The project is shipping the H22 demo. Wire what's
  needed to make the loop honest, then hand back.

---

## IMPLEMENTATION SEQUENCE
Each step ends with a concrete verification. Do them in order; don't skip ahead.

### Step 0 · Place the files + smoke-test (no agents spawned)
Put the ten files at these paths, then confirm `bun` is installed:

| path | role |
|---|---|
| `harness/run.ts` | orchestrator |
| `harness/tasks.json` | machine source of truth (keep synced with the checklist — that's task `0.3`) |
| `harness/prompts/generator.md` | fresh-instance builder |
| `harness/prompts/evaluator.md` | adversarial Houdini TD |
| `harness/verify/checks.py` | deterministic checks |
| `harness/state/manifest.schema.json` | verdict / repair-ticket contract |
| `harness/state/claude-progress.md` | state continuity |
| `.claude/settings.json` | tool allowlist + format hook |
| `CLAUDE.md` | distilled conventions |
| `harness/README.md` | on-ramp |

```bash
bun run harness/run.ts --dry
```
**Verify:** it prints the Mode-A queue (`0.1`–`0.7`), shows `0.1` as a human gate with the
sidecar recommendation, reports `MODE A` (drop.json absent), and **spawns nothing**.
✅ Done when `--dry` runs clean and the queue + gates look right.

### Step 1 · Discover real values (read, don't guess)
Grep the repo for `ADAPT`. Then open the real sources and **write down** the true values
(keep a scratch table — do not change code yet):

- Panel/host import name → what `import synapse` should actually be (`check_import_panel`).
- Brain health/ping call → sidecar handshake or in-proc query (`check_brain_answers`).
- `server/doctor.py` → how it's invoked + how it signals green (exit code? JSON `status`?).
- `science/apex_probes.py` → how it's invoked + where it writes the delta report.
- `agent.usd` → the prim type + attribute names for `decision`/`reasoning`/`revert`, and the
  revert API (`check_ledger`, `check_revert_clean`).
- `VERSION` + `pyproject.toml` → their exact shapes (`check_version_single_source`).
- The installed `claude` CLI → run `claude --help` and confirm the flags used in
  `run.ts` → `runAgent()` (headless/print mode, system-prompt injection, cwd scoping).

✅ Done when a written findings table exists. No code changed yet.

### Step 2 · Wire the survival spine, prove it on H21
Edit `checks.py` for **only** `import_panel`, `brain_answers`, `doctor` (these unblock the three
survival-tagged tasks `0.1`/`0.4`/`0.7`). Point `HYTHON` at your H21 build, then test the
checks **standalone** — no agent loop, no tokens:

```bash
export HYTHON="/path/to/Houdini 21.x/bin/hython"   # Windows: ...\bin\hython.exe
python harness/verify/checks.py --task 0.4 --worktree . --hython "$HYTHON"
```
**Verify:** the three checks return *truthful* `ok` values (green if SYNAPSE is healthy on H21).
✅ Done when they report real results, not placeholders.

### Step 3 · Wire the remaining Mode-A checks
`probe_runs`, `version_single_source`, `hip_opens`, `shot_login`, `clean_install`,
`nodes_appear`. Test each standalone via `checks.py --task <id>`. **Leave the Mode-B-only
checks as `ADAPT`** (`cook_node`, `ledger`, `revert_clean`, `render`, `probe_clean`,
`theme_ok`) — they can't be tested before the drop. Do not stub them green.
✅ Done when every Mode-A task's `verify` checks return truthful results standalone.

### Step 4 · Prove the full loop on the safest task
Confirm `runAgent()` flags against the installed CLI first. Then run one real round on `0.3`
(single-source-version — purely mechanical, deterministic check, safest first loop):

```bash
bun run harness/run.ts --task 0.3
```
**Verify, by watching:** a fresh Generator edits, the format hook runs, `checks.py` runs, the
Evaluator returns a **parseable JSON verdict**, the gate fires, a single atomic commit lands in
the worktree — and the harness does **not** merge to main.
✅ Done when one full round completes end-to-end with a clean verdict and a worktree commit.

### Step 5 · Update state + hand back
Append the wiring deltas to `harness/state/claude-progress.md` (what's wired, what's still
`ADAPT`, the `0.1`/`daemon.py` finding — keep it to one-line deltas, not a diary). Then report
to the human:
- Which Mode-A tasks now pass on H21.
- The remaining `ADAPT` items (Mode-B / render / ledger — expected, not failures).
- The sidecar-vs-abi3 recommendation **with the evidence you found**, for their decision.
- Confirmation that Mode B stays dormant until `drop.json` exists.

---

## DEFINITION OF DONE (for this handoff)
**Done =** files placed · `--dry` clean · survival spine (`import_panel`/`brain_answers`/`doctor`)
wired and truthful on H21 · all Mode-A checks truthful standalone · one full real loop round
green on `0.3` · state updated · remaining `ADAPT`s documented for the human.

**Out of scope / NOT done =** attempting Mode B (no H22 yet) · deciding `0.1` · merging to main ·
faking any check to pass · refactoring SYNAPSE's product code · adding harness features.

If you finish the in-scope work and want to keep going, **stop and hand back instead** — the
next decision (the architecture, the merge, the drop) belongs to the human.
