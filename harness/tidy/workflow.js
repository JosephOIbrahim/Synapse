export const meta = {
  name: 'tidy-housecleaning',
  description: 'TIDY: unfinished-work closure + housecleaning — SWEEP → CLASSIFY → DISPATCH → VERIFY → REPORT',
  phases: [
    { title: 'RECON', detail: '11 agents inventory the unfinished state' },
    { title: 'CLASSIFY', detail: 'orchestrator synthesizes the disposition table' },
    { title: 'DISPATCH', detail: 'work packages execute safe dispositions, prepare gated ones' },
    { title: 'VERIFY', detail: 'tree delta, state consistency, test baseline' },
    { title: 'REPORT', detail: 'orchestrator writes the report + STATE.json' },
  ],
}

const ROOT = 'C:/Users/User/SYNAPSE'
const DATE = (args && args.date) || '2026-08-07'

const INVENTORY_SCHEMA = {
  type: 'object',
  properties: {
    surface: { type: 'string' },
    items: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          path: { type: 'string' },
          kind: { type: 'string', enum: ['untracked', 'modified', 'state', 'gate', 'dir', 'other'] },
          description: { type: 'string' },
          size: { type: 'string' },
          mtime: { type: 'string' },
          risk: { type: 'string', enum: ['low', 'med', 'high'] },
          notes: { type: 'string' },
        },
        required: ['path', 'kind', 'description'],
      },
    },
    summary: { type: 'string' },
  },
  required: ['surface', 'items', 'summary'],
}

const DISPOSITION_SCHEMA = {
  type: 'object',
  properties: {
    items: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          path: { type: 'string' },
          disposition: { type: 'string', enum: ['COMMIT', 'DROP', 'PARK', 'FIX', 'MOVE', 'DEFER'] },
          action: { type: 'string' },
          risk: { type: 'string', enum: ['low', 'med', 'high'] },
          gate: { type: 'string', enum: ['none', 'human'] },
          rationale: { type: 'string' },
        },
        required: ['id', 'path', 'disposition', 'action', 'risk', 'gate', 'rationale'],
      },
    },
    loopClosure: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['items', 'loopClosure', 'summary'],
}

const DISPATCH_RESULT_SCHEMA = {
  type: 'object',
  properties: {
    packageId: { type: 'string' },
    actions: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          item: { type: 'string' },
          action: { type: 'string' },
          status: { type: 'string', enum: ['done', 'prepared', 'blocked', 'skipped'] },
          detail: { type: 'string' },
        },
        required: ['item', 'action', 'status'],
      },
    },
    gates: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['packageId', 'actions', 'summary'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    check: { type: 'string' },
    passed: { type: 'boolean' },
    evidence: { type: 'string' },
    issues: { type: 'array', items: { type: 'string' } },
  },
  required: ['check', 'passed', 'evidence'],
}

const REPORT_SCHEMA = {
  type: 'object',
  properties: {
    executed: { type: 'array', items: { type: 'string' } },
    gated: { type: 'array', items: { type: 'string' } },
    deferred: { type: 'array', items: { type: 'string' } },
    verification: { type: 'array', items: { type: 'string' } },
    humanDecisions: { type: 'array', items: { type: 'string' } },
    skillsApplied: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['executed', 'gated', 'deferred', 'verification', 'humanDecisions', 'summary'],
}

const SAFETY = `SAFETY MODEL (binding):
- You may MOVE files (git mv or mv) — reversible.
- You may CREATE files (reports, harness files) — reversible.
- You may STAGE git changes (git add) and DRAFT commit messages — reversible.
- You may NOT run git commit, git push, git merge, or git reset --hard.
- You may NOT delete any file that looks like real work. For DROP items, write a proposal file instead.
- You may NOT modify another harness's state files (harness/legs.json, harness/rope/STATE.json, harness/flywheel_queue.json, harness/drop.json, harness/posture.json). Diagnose and propose only.
- You may NOT modify any file under src/, python/, panel/, shared/, tests/ unless the item explicitly says so.
- If an action would be destructive or irreversible, mark it 'blocked' and explain.
- Verify each item still exists before acting (the inventory may be stale).
- Consult and follow any relevant skill from the available skills list (e.g. phantom-sweep, rsi-closure, h22-doc-scout) — read its instructions and apply its protocol where the item matches its domain.`

const RECON_AGENTS = [
  {
    label: 'recon:git-status',
    prompt: `TIDY RECON — git status surface. Working dir: ${ROOT}.
Run 'git status --porcelain=v1' and 'git status'. For every modified and untracked entry, report: path, kind (untracked/modified), size, mtime, and a one-line description of what it appears to be. Read the file named '$null' (it is UTF-16 — read with the Read tool; it contains a captured PowerShell error about a vendored-SDK ABI mismatch). List the contents of 'models/' and 'shot_layers/' (top level, with sizes). Note any .bak files. Also run 'git diff --stat' for the modified files and report what changed. Return the full inventory.`,
  },
  {
    label: 'recon:recent-commits',
    prompt: `TIDY RECON — recent commits surface. Working dir: ${ROOT}.
Run 'git log --oneline -25' and 'git log -3 --stat'. Identify: what landed recently (last ~10 commits), whether the working-tree changes relate to recent commits, and any dangling/orphaned work. Run 'git stash list' and 'git worktree list' and report the worktrees (note: M5/M5b are merged to master but their worktrees may still exist). Check 'git branch -a' for branches that look merged-but-uncleaned. Return the inventory.`,
  },
  {
    label: 'recon:harness-state',
    prompt: `TIDY RECON — harness state surface. Working dir: ${ROOT}.
Read these state files and report their current state: harness/legs.json (note: M5 and M5b are MERGED to master per git log, but legs.json shows them as 'ready' — this is stale state), harness/rope/STATE.json (note the uncommitted 2-line diff), harness/NEXT_SESSION.md (the session handoff — summarize its open items: the 5 CI0 rulings, R-M5b-1, M6, Gate C), harness/flywheel_queue.json (if exists), harness/drop.json (if exists), harness/posture.json (if exists). For each: what it is, current state, consistency issues, open items. Do NOT modify anything. Return the inventory.`,
  },
  {
    label: 'recon:notes-probes',
    prompt: `TIDY RECON — notes/probe scripts surface. Working dir: ${ROOT}.
List harness/notes/ and identify the untracked probe/scratch files: _diff_runs.py, _extract_reasons.py, _probe_double_run.py, _probe_oiio.py, _probe_oiio_read.py, _probe_to_thread.py, _route_dispatch.py, _why.py, watch_moneta.ps1, MONETA_WATCH.txt. For each untracked file: read it (or its first ~30 lines), describe what it does, whether it looks like finished work or scratch, and whether anything references it (grep for its basename). Note the repo convention: some _-prefixed probes ARE committed (e.g. _activerender.py) — so '_' prefix alone does not mean scratch. Return the inventory.`,
  },
  {
    label: 'recon:release-notes',
    prompt: `TIDY RECON — release notes surface. Working dir: ${ROOT}.
Read harness/notes/RELEASE_v5.43.0.md and harness/notes/RELEASE_v5.43.0_DRAFT.md. The final has F-1..F-7 + c3 canonicalizer + suite 5765/9/147; the draft has F-1..F-5 + c2 baseline and says 'do not publish until M5+M5b merged'. Per harness/NEXT_SESSION.md, v5.43.0 IS released (tagged, published). Determine: is the draft superseded? Should it be archived/deleted? Is the final the real release note? Is either referenced anywhere? Return the inventory.`,
  },
  {
    label: 'recon:docs-untracked',
    prompt: `TIDY RECON — untracked docs surface. Working dir: ${ROOT}.
Read docs/project.md and docs/pkg_info.json. project.md is a 'Project Memory: scripts' export (Moneta/evolution memory, schema 0.1.0) — determine if it belongs in docs/ or is a stray memory export. pkg_info.json is a machine-generated diagnostic (pkg_dir, host_items, introspect_script) — determine if it is a stray artifact. Grep for references to either filename. Return the inventory.`,
  },
  {
    label: 'recon:data-dirs',
    prompt: `TIDY RECON — data directories surface. Working dir: ${ROOT}.
models/ contains minilm-l6-v2.onnx (90MB — the Moneta embedder). shot_layers/ contains 5 tiny USD files (animation/fx/layout/lighting/render.usd, 492 bytes each). Determine: are these data/asset dirs that should be gitignored? Is there a .gitignore entry? Do the shot_layers USD files look like a real fixture (read one)? Check if anything references shot_layers/ (grep). Return the inventory.`,
  },
  {
    label: 'recon:autoresearch',
    prompt: `TIDY RECON — autoresearch runs surface. Working dir: ${ROOT}.
List harness/autoresearch/runs/ (6 run dirs + LATEST.txt). For each run dir: list contents, read the summary/verdict if present, determine if it is a completed campaign run (evidence to keep) or abandoned. Check which are tracked vs untracked (git status). Read harness/autoresearch/LATEST.txt. Return the inventory.`,
  },
  {
    label: 'recon:open-gates',
    prompt: `TIDY RECON — open human gates surface. Working dir: ${ROOT}.
Survey the open human gates across all harnesses. Read: harness/NEXT_SESSION.md (the 5 CI0 rulings R-CI0-1..5 + R-M5b-1 + M6 + CI0 merge Gate C), harness/clear/ state (L1 commit-or-drop gate for 6 latency-relay files), harness/phantoms/ state (merge + digest rebuild + quarantine-list gates), harness/rsi/ REGISTRY.json (C ratification, R/A3), harness/rope/STATE.json (blocked_human tasks L3-2, L3-5; blocked_seat L2-4; blocked L5-13; needs_review L5-14), harness/flywheel_queue.json (ratification flips). For each gate: the exact ask, who must decide, and what closes it. Return the inventory.`,
  },
  {
    label: 'recon:ci-health',
    prompt: `TIDY RECON — CI/test health surface. Working dir: ${ROOT}.
Check the test suite health WITHOUT running the full suite. Run 'python -m pytest tests/ -q --co' (collection only) with a 120s timeout and report the collected count + any collection errors. Check .github/workflows/ for the CI config and what it runs. Note the known state: release note says 5765 passed / 9 failed / 147 skipped; memory notes mcp list_tools CI red since 2026-07-29. Report the baseline. Return the inventory.`,
  },
  {
    label: 'recon:stray-files',
    prompt: `TIDY RECON — stray files surface. Working dir: ${ROOT}.
Read harness/prompts/ci0.md (the CI0 leg brief — untracked but referenced by harness/legs.json), harness/rope/OPERATOR_CARD.md.bak (a .bak file), and any other untracked files not covered by other recon agents. For each: what it is, whether it is referenced, and its disposition lean (commit/park/drop). Return the inventory.`,
  },
]

const CLASSIFY_PROMPT = (compact) => `TIDY ORCHESTRATOR — classify. You are the orchestrator of the TIDY housecleaning harness. You have received 11 recon inventories of the SYNAPSE repo's unfinished state (working dir ${ROOT}). Your job: produce the disposition table.

Recon inventories (compact):
${JSON.stringify(compact, null, 1)}

For EVERY item across all inventories, assign exactly one disposition:
- COMMIT: real work that should ship (e.g. the final release note, the ci0.md leg brief, finished probe scripts the repo convention keeps)
- DROP: garbage/artifact (e.g. the $null file, .bak files, superseded drafts, machine-generated strays) — propose, never delete
- PARK: draft/scratch worth keeping but not in the main tree (move to harness/notes/scratch/)
- MOVE: right content, wrong place (e.g. docs/ strays)
- FIX: broken/stale state needing repair (e.g. legs.json showing merged legs as 'ready') — diagnose + propose, never mutate state files
- DEFER: needs a decision the human has not made (e.g. the CI0 rulings, M6) — surface, don't act

Rules:
- Be conservative. When unsure between DROP and PARK, choose PARK. When unsure between COMMIT and PARK, choose COMMIT if it is referenced by anything, else PARK.
- Every item gets a gate: 'none' (harness may execute) or 'human' (human must approve).
- Also produce loopClosure: the list of open human decisions that close the loop (from NEXT_SESSION.md and the harness gates).
- Risk: low/med/high per item.

Return the disposition table.`

const fmtItems = (items) => items.map((i) => `- ${i.id}: ${i.path} — ${i.action}${i.rationale ? ` (${i.rationale})` : ''}`).join('\n')

const dispatchPrompt = (packageName, items, extra) => `TIDY DISPATCH — ${packageName}. Working dir: ${ROOT}.
You are executing the ${packageName} work package. Items:
${fmtItems(items)}
${extra || ''}
${SAFETY}
Return what you did.`

const PRE_RUN = `Pre-run working-tree snapshot (session start 2026-08-07):
Modified: harness/legs.json, harness/rope/STATE.json
Untracked: $null, docs/pkg_info.json, docs/project.md, harness/NEXT_SESSION.md, harness/autoresearch/runs/fixture_verify_20260805_183316/, harness/autoresearch/runs/scout_20260805_181349/, harness/autoresearch/runs/solaris_basic_20260805_181026/, harness/notes/MONETA_WATCH.txt, harness/notes/RELEASE_v5.43.0.md, harness/notes/RELEASE_v5.43.0_DRAFT.md, harness/notes/_diff_runs.py, harness/notes/_extract_reasons.py, harness/notes/_probe_double_run.py, harness/notes/_probe_oiio.py, harness/notes/_probe_oiio_read.py, harness/notes/_probe_to_thread.py, harness/notes/_route_dispatch.py, harness/notes/_why.py, harness/notes/watch_moneta.ps1, harness/prompts/ci0.md, harness/rope/OPERATOR_CARD.md.bak, models/, shot_layers/`

const VERIFY_AGENTS = [
  {
    label: 'verify:tree-delta',
    prompt: `TIDY VERIFY — tree delta. Working dir: ${ROOT}.
Run 'git status --porcelain=v1' and compare against the pre-run state:
${PRE_RUN}
Expected changes from the TIDY run: new files under harness/tidy/, files moved to harness/notes/scratch/, staged commits (git diff --cached --stat), the report file. Flag anything unexpected: deletions of real work, modifications to src/python/panel/shared/tests, modifications to harness state files beyond the pre-existing uncommitted changes. Report passed=true only if the delta is exactly the expected set.`,
  },
  {
    label: 'verify:state-consistency',
    prompt: `TIDY VERIFY — state consistency. Working dir: ${ROOT}.
Verify: (1) harness/tidy/ files exist (SPEC.md, STATE.json, runner.py, workflow.js, REPORT_*.md), (2) no other harness's state files were modified by this run (run 'git diff --stat harness/legs.json harness/rope/STATE.json harness/flywheel_queue.json harness/drop.json harness/posture.json' — should show only the pre-existing uncommitted changes, not new ones), (3) the scratch dir exists if items were parked. Report passed=true only if all hold.`,
  },
  {
    label: 'verify:test-baseline',
    prompt: `TIDY VERIFY — test baseline. Working dir: ${ROOT}.
Run 'python -m pytest tests/ -q --co' (collection only, 120s timeout). Report the collected count and any collection errors. Compare against the known baseline (5765 passed / 9 failed / 147 skipped per the v5.43.0 release note). This run should not have changed the suite. Report passed=true if collection succeeds and the count is in the expected range.`,
  },
]

const REPORT_PROMPT = `TIDY ORCHESTRATOR — final report. Working dir: ${ROOT}.
You are the orchestrator closing the TIDY run on ${DATE}. You have: the recon summaries, the disposition table, the dispatch results, and the verify results.

Produce the final report:
- executed: what the harness actually did (moves, staging, files created)
- gated: what is prepared but needs human approval (commits staged, drops proposed, fixes proposed)
- deferred: what is surfaced but not acted (open gates, rulings)
- verification: the verify results
- humanDecisions: the numbered decision list for the human (the gates + rulings)
- skillsApplied: which skills/protocols were consulted
- summary: one paragraph

Write the report to harness/tidy/REPORT_${DATE}.md AND update harness/tidy/STATE.json with the run record (items, dispositions, gates). Read STATE.json first, then update it. Return the structured report.`

phase('RECON')
log(`RECON: ${RECON_AGENTS.length} agents fanning out`)
const recon = await parallel(
  RECON_AGENTS.map((r) => () => agent(r.prompt, { label: r.label, phase: 'RECON', schema: INVENTORY_SCHEMA, effort: 'medium' }))
)

phase('CLASSIFY')
log('CLASSIFY: orchestrator synthesizing the disposition table')
const compact = recon
  .filter(Boolean)
  .map((r) => ({
    surface: r.surface,
    items: (r.items || []).map((i) => ({ path: i.path, kind: i.kind, desc: i.description, risk: i.risk })),
    summary: r.summary,
  }))
const disposition = await agent(CLASSIFY_PROMPT(compact), {
  label: 'orchestrator:classify',
  phase: 'CLASSIFY',
  schema: DISPOSITION_SCHEMA,
  effort: 'high',
})

phase('DISPATCH')
const groups = {}
for (const item of (disposition && disposition.items) || []) {
  if (!groups[item.disposition]) groups[item.disposition] = []
  groups[item.disposition].push(item)
}
const jobs = []
const addJob = (label, prompt) => jobs.push({ label, prompt })
if (groups.COMMIT && groups.COMMIT.length) {
  addJob('dispatch:prepare-commits', dispatchPrompt('prepare commits', groups.COMMIT, 'For each item: verify it exists, STAGE it (git add), and DRAFT a commit message per repo convention (feat(area): <id> <what> / fix(area): <id> <what>). Group logically related items into one commit. Write the draft messages to harness/tidy/COMMITS.md. DO NOT run git commit.'))
}
if (groups.DROP && groups.DROP.length) {
  addJob('dispatch:propose-drops', dispatchPrompt('propose drops', groups.DROP, 'For each item: verify it exists, read it to confirm it is what the classifier said, and write a drop proposal to harness/tidy/DROPS.md (path, what it is, why safe to delete, risk). DO NOT delete anything.'))
}
if (groups.PARK && groups.PARK.length) {
  addJob('dispatch:park-scratch', dispatchPrompt('park scratch', groups.PARK, 'For each item: verify it exists, then MOVE it to harness/notes/scratch/ (create the dir if needed). Use git mv if tracked, else mv. Note any references in the report.'))
}
if (groups.MOVE && groups.MOVE.length) {
  addJob('dispatch:move-items', dispatchPrompt('move items', groups.MOVE, 'For each item: verify it exists, determine the correct destination per the item action, and MOVE it. Use git mv if tracked, else mv.'))
}
if (groups.FIX && groups.FIX.length) {
  addJob('dispatch:diagnose-fixes', dispatchPrompt('diagnose fixes', groups.FIX, 'For each item: diagnose the issue (read the file, compare against reality) and write a fix proposal to harness/tidy/FIXES.md (what is wrong, the exact change needed, the risk). DO NOT apply the fix. DO NOT modify harness state files.'))
}
addJob('dispatch:state-reconcile', `TIDY DISPATCH — state reconciliation diagnosis. Working dir: ${ROOT}.
Diagnose (READ-ONLY) the consistency of harness/legs.json and harness/rope/STATE.json against git reality. legs.json shows M5/M5b/CI0 as 'ready' but M5/M5b are merged to master (git log c4187d01, d6b22a4e). rope/STATE.json has an uncommitted 2-line diff. For each: what is stale, what the correct state is, and the exact edit needed. Write the diagnosis to harness/tidy/STATE_DIAGNOSIS.md. DO NOT edit the state files.
${SAFETY}
Return what you did.`)
addJob('dispatch:data-dirs', `TIDY DISPATCH — data directories. Working dir: ${ROOT}.
models/ (90MB ONNX embedder) and shot_layers/ (5 tiny USD files) are untracked. Determine the right disposition: if they are data/asset dirs, propose .gitignore entries (write the proposal to harness/tidy/GITIGNORE_PROPOSAL.md — DO NOT edit .gitignore). If shot_layers/ is a real fixture, propose committing it.
${SAFETY}
Return what you did.`)
addJob('dispatch:open-gates', `TIDY DISPATCH — open gates enumeration. Working dir: ${ROOT}.
Consolidate the open human gates into harness/tidy/GATES.md: for each gate, the exact ask, who decides, what closes it. Include: the 5 CI0 rulings (R-CI0-1..5), R-M5b-1, M6, CI0 merge (Gate C), CLEAR L1, PHANTOM SWEEP gates, RSI gates, ROPE blocked_human tasks, MONETA ratification. This is the human decision list.
${SAFETY}
Return what you did.`)

log(`DISPATCH: ${jobs.length} work packages`)
const dispatchResults = await parallel(
  jobs.map((j) => () => agent(j.prompt, { label: j.label, phase: 'DISPATCH', schema: DISPATCH_RESULT_SCHEMA, effort: 'medium' }))
)

phase('VERIFY')
log(`VERIFY: ${VERIFY_AGENTS.length} checks`)
const verifyResults = await parallel(
  VERIFY_AGENTS.map((v) => () => agent(v.prompt, { label: v.label, phase: 'VERIFY', schema: VERIFY_SCHEMA, effort: 'low' }))
)

phase('REPORT')
log('REPORT: orchestrator writing the final report')
const report = await agent(REPORT_PROMPT, {
  label: 'orchestrator:report',
  phase: 'REPORT',
  schema: REPORT_SCHEMA,
  effort: 'high',
})
return report
