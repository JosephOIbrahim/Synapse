# docs/v6/INTAKE.md — the blueprint paper→disk contract

The v6 build plan (`docs/v6/PLAN.md`) lives on paper as blueprints BP00–BP08. Nothing in the
harness arms until a human drops those files here. This doc is the whole contract: what to
drop, what shape it must be, and what the harness does the moment it lands. Read it once,
run the checklist at the bottom, and the queue takes over.

## (a) The arming rule

One file, exact name, arms the track:

```
docs/v6/BP00_manifest.md
```

`run.ts` checks `existsSync` on that path in the main checkout — but **the drop must also be
COMMITTED before the first harness run**. Every V-task runs in a git worktree branched from
`HEAD` (`git worktree add … HEAD`), and every check reads the *worktree*, not your working
tree. An uncommitted drop arms the track in the main checkout while the Generator and
`blueprints_present` see no `docs/v6/` at all — the armed track can't see its own trigger
file, and V.1 burns its repair rounds failing "BP00 missing". Commit first; it's a checklist
line below, not optional hygiene.

While the file is absent the `blocked_on:"blueprints"` tasks (V.1–V.7) are filtered out of
the queue entirely — `--task V.1` cannot override the hold (same behavior as `--task 1.4`
before `drop.json` exists); you'll get an empty queue plus this intake surface.

## (b) The `## Module Manifest` table (in BP00_manifest.md)

BP00 must contain a `## Module Manifest` section with a markdown table. First column:
repo-relative `.py` path. Second column: layer — any row whose layer contains **"pure"** gets
zero-`hou` enforcement (the `v6_skeleton_conformance` check ASTs it; `import hou` anywhere in
a pure module is a deterministic FAIL). Third column: free notes.

```markdown
## Module Manifest

| path | layer | notes |
|---|---|---|
| python/synapse/v6/knowledge_base.py | pure | BP10 — recipe store + failure DB, JSONL |
| python/synapse/v6/gsplat_compare.py | pure | BP02 interpretation layer, test-first |
| python/synapse/v6/perception_bridge.py | houdini | BP01 — may import hou, worktree-cook only |
```

V.1 stubs every listed path exactly where the table says. An empty or header-only table
verifies nothing and fails the check — list real modules or don't drop yet.

## (c) Canonical file names

| file | author | rule |
|---|---|---|
| `docs/v6/BP00_manifest.md` | human | exact name — this IS the arming marker |
| `docs/v6/BP01_*.md` … `BP08_*.md` | human | free-named, `BP0N_*.md` pattern (documented, not enforced for arming) |
| `docs/v6/BP09_iteration_controller.md` | harness (task V.2) | exact name — checks pin it |
| `docs/v6/BP10_knowledge_base.md` | harness (task V.3) | exact name — checks pin it |

One API note for V.3: the KnowledgeBase public API (`KnowledgeBase(root=…)`,
`add_recipe(dict)`, `add_failure(dict)`, `query(…)` — lossless round-trip) is pre-frozen by
the `v6_kb_roundtrip` check. The BP10 spec *documents* that API; it does not redesign it.

## (d) The one allowed intake edit

If BP00's manifest roots the code somewhere other than `python/synapse/v6/`, re-point the
`tasks.json` V.3/V.4 refs at intake time — that single edit is sanctioned, everything else in
the frozen task set is not. Make it in the same commit as the drop.

## (e) Drop checklist (copy-paste)

```bash
mkdir -p docs/v6 && cp /path/to/blueprints/BP0*.md docs/v6/    # BP00_manifest.md required; BP01-BP08 recommended
git add docs/v6 && git commit -m "docs(v6): blueprint drop"    # MANDATORY - worktrees branch from HEAD, uncommitted drops are invisible to every check
bun run harness/run.ts --dry                                   # confirm the status line says armed + V-tasks queued
bun run harness/run.ts                                         # grind: V.1 -> V.4 now (Mode A); V.5-V.7 wait for drop.json
git worktree list                                              # passing V-work waits in .claude/worktrees/feature-V.N for YOUR merge
```

**On any blueprint RE-drop or BP00 edit:** remove the stale V-worktrees first — they were
branched from the *old* HEAD and will keep seeing the old manifest (and on a later PASS the
ledger would bank the *new* BP00's hash against work that conformed to the *old* one):

```bash
git worktree remove .claude/worktrees/feature-V.1 --force && git branch -D harness/V.1   # repeat per stale V.N
```

Then commit the edited blueprints and re-run.

## (f) What happens next

- **Mode A, immediately:** V.1 (scaffold the BP00 skeleton) → V.2 (write BP09 spec) →
  V.3 (spec + build BP10 knowledge base) → V.4 (pure-Python layers, test-first), in id order,
  `bun run harness/run.ts` grinds them. Each gets its own worktree; passing work waits for
  your merge — the harness never merges.
- **Mode B (after a human writes `drop.json`):** V.5 (Miles 1–2, BP01+BP02) → V.6 (Miles 3–4,
  BP08 evaluator) → V.7 (Miles 5–7, first autonomous pyro cycle). The task-1.4 probe report
  re-ranks these before work starts.
- **The cadence is run → merge passed V-worktrees → re-run.** V.6 builds on V.5's modules and
  V.7 on V.3's, but every worktree branches from HEAD — earlier V-deliverables only exist
  there after *you* merge them. Expect V.5/V.6/V.7 to span separate invocations with your
  merges in between; a single back-to-back run will honestly BLOCK the later ones.
- **Completion-ledger behavior:** every V-task's refs are anchored on `docs/v6/BP00_manifest.md`
  (a real, committed file post-drop), so a PASS banks in `done.json` and is skipped on re-run —
  and **any BP00 edit re-arms the whole track**, which is exactly what a manifest change should
  do. Two nuances: V.3/V.7 also ref deliverables that only become real files in the main repo
  after *you* merge their worktrees — expect one post-merge re-verify run when the banked hash
  starts folding real bytes. And directory refs (`python/synapse/v6/`, `tests/v6/`) fold path
  only, not contents: post-merge code changes under them do NOT re-arm a banked task — edit
  BP00 (or `--force`) when you want a true re-verify.
