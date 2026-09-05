export const meta = {
  name: 'cto-review',
  description: 'CTO review loop over SYNAPSE master: SWEEP prior backlog predicates -> FIND (7 lanes) -> VERIFY (refuter per lane) -> SYNTH -> APPLY (auto-gated only) -> PERSIST',
  whenToUse: 'One crank per run. args: {date:"YYYY-MM-DD", head:"<sha>", range:"<since-sha>..<head>", autonomy?:"green"|"amber"|"red", apply?:false, lanes?:[...]}',
  phases: [
    { title: 'Sweep', detail: 'run every open BACKLOG closure predicate; closed/open/regressed' },
    { title: 'Find', detail: 'seven read-only lanes, evidence + repro per finding' },
    { title: 'Verify', detail: 'one adversarial refuter per lane re-runs every repro' },
    { title: 'Synthesize', detail: 'CTO merge: dedupe, rank, gate, closure predicate' },
    { title: 'Apply', detail: 'gate=auto items only, forge in worktree, never merges' },
    { title: 'Persist', detail: 'runs/<date>/report.json + BACKLOG.json + LEDGER.md' },
  ],
}

// args may arrive as a JSON string in this runtime (h22-doc-scout lesson). Parse defensively.
let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch { A = {} } }
A = A || {}
const D = String(A.date || 'undated'), HEAD = String(A.head || 'HEAD'), RANGE = String(A.range || 'HEAD~50..HEAD')
const AUTONOMY = String(A.autonomy || 'amber')
const APPLY = A.apply === true && AUTONOMY !== 'red'
const ONLY = Array.isArray(A.lanes) ? A.lanes.map(s => String(s).toUpperCase()) : null

const CTX = `You are one lane of the SYNAPSE CTO review loop (harness/cto/SPEC.md) over C:\\Users\\User\\SYNAPSE, branch master, HEAD ${HEAD}, ${D}.
HARD RULES: read-only unless your assignment says otherwise; never touch .git, never merge/push/tag/edit VERSION; never run the full pytest suite (targeted <=2 files ok).
Use rg/sed -n/git; read only needed passages. Exclude worktrees: rg -g '!.claude/worktrees/**' -g '!**/__pycache__/**'.
Every finding MUST carry evidence as path:line or sha AND a paste-able one-line repro; no evidence => do not report.
Severity: critical = ships wrong/unsafe or breaks release truth; high = real defect or stagnation with clear cost; medium = drift/debt; low/info = note.
Tier every claim: 'claimed' (docs/receipts/commit messages) vs 'shipped' (code on master) vs 'live' (what Houdini loads). If the Houdini bridge is down, say so and do not fake live evidence; hython offscreen (C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe) with a 60s timeout is acceptable for import checks.
Project law: CLAUDE.md at repo root (H22.0.400, phantom-API discipline via python/synapse/cognitive/tools/data/h22_symbol_table.json + rulebook/phantoms.json, receipts, Joe's-word gates). Recent range under review: ${RANGE}.
OUTPUT: only the structured object; terse fields; max 10 findings ranked by severity; unsettled points go in open_questions.`

const FINDINGS = { type: 'object', properties: {
  lane: { type: 'string' }, summary: { type: 'string' },
  findings: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string' }, title: { type: 'string' },
    severity: { type: 'string', enum: ['critical','high','medium','low','info'] },
    tier: { type: 'string', enum: ['claimed','shipped','live'] },
    evidence: { type: 'string' }, repro: { type: 'string' }, recommendation: { type: 'string' }, confidence: { type: 'number' },
  }, required: ['id','title','severity','tier','evidence','repro','recommendation','confidence'] } },
  open_questions: { type: 'array', items: { type: 'string' } },
}, required: ['lane','summary','findings','open_questions'] }

const VERDICT = { type: 'object', properties: {
  lane: { type: 'string' },
  verdicts: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string' }, verdict: { type: 'string', enum: ['CONFIRMED','REFUTED','DOWNGRADED','UPGRADED'] },
    reason: { type: 'string' }, corrected_severity: { type: 'string', enum: ['critical','high','medium','low','info'] },
  }, required: ['id','verdict','reason','corrected_severity'] } },
  missed: { type: 'array', items: { type: 'object', properties: {
    title: { type: 'string' }, severity: { type: 'string' }, evidence: { type: 'string' }, repro: { type: 'string' },
  }, required: ['title','severity','evidence','repro'] } },
  lane_summary_accurate: { type: 'boolean' },
}, required: ['lane','verdicts','missed','lane_summary_accurate'] }

const SWEEP = { type: 'object', properties: {
  results: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string' }, status: { type: 'string', enum: ['closed','open','regressed','unknown'] }, note: { type: 'string' },
  }, required: ['id','status','note'] } },
  backlog_count: { type: 'number' },
}, required: ['results','backlog_count'] }

const SYNTH = { type: 'object', properties: {
  executive: { type: 'string' }, panel_verdict: { type: 'string' }, two_day_work_verdict: { type: 'string' }, recipes_verdict: { type: 'string' },
  lane_scores: { type: 'array', items: { type: 'object', properties: { lane: { type: 'string' }, grade: { type: 'string' }, one_line: { type: 'string' } }, required: ['lane','grade','one_line'] } },
  backlog: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string' }, title: { type: 'string' }, lane: { type: 'string' },
    severity: { type: 'string', enum: ['critical','high','medium','low'] },
    action: { type: 'string' }, evidence: { type: 'string' }, repro: { type: 'string' },
    gate: { type: 'string', enum: ['auto','crux','joe'] }, closure_predicate: { type: 'string' },
  }, required: ['id','title','lane','severity','action','evidence','repro','gate','closure_predicate'] } },
  rsi_scaffold: { type: 'array', items: { type: 'object', properties: {
    ability: { type: 'string' }, purpose: { type: 'string' }, signal: { type: 'string' }, producer: { type: 'string' }, referee: { type: 'string' },
    apply_path: { type: 'string' }, closure_predicate: { type: 'string' }, proof_test: { type: 'string' }, wires_existing: { type: 'string' },
  }, required: ['ability','purpose','signal','producer','referee','apply_path','closure_predicate','proof_test','wires_existing'] } },
  human_gates: { type: 'array', items: { type: 'string' } },
  refuted_count: { type: 'number' }, confirmed_count: { type: 'number' },
}, required: ['executive','panel_verdict','two_day_work_verdict','recipes_verdict','lane_scores','backlog','rsi_scaffold','human_gates','refuted_count','confirmed_count'] }

// Lane prompts. Adding a lane = one entry. Keep each lane's questions concrete and path-anchored.
const LANES = [
  { key: 'SCOUT', agentType: 'cartographer', prompt: `LANE SCOUT - map the release as published. (1) Do the synced surfaces agree (README.md, CLAUDE.md header, harness/notes/RELEASE_v*.md, VERSION, pyproject, packages/synapse.json): version strings, MCP tool count (count real registrations in mcp_server.py), Houdini build? (2) Branch/worktree debt: git branch --no-merged master; git worktree list; which carry product code vs scratch; which worktrees are dead (branch merged). (3) Uncommitted files on master (git status --porcelain | head -80): product vs run artefacts vs junk. (4) Public-repo exposure: secrets, .env, personal paths. (5) Is CLAUDE.md section 1 (two paths to Houdini, undo/main-thread wrapping) still accurate against python/synapse/server at HEAD?` },
  { key: 'DESIGN', agentType: 'panel-design-warden', prompt: `LANE DESIGN - the Houdini Python panel (python/synapse/panel, tests/panel). Test two readings of 'the panel design is stagnant and not updating properly'. Reading A (stagnation): locate the vendored design-system tokens; git log -1 dates of tokens vs widgets; run the census CLI (rg -l 'census' python/synapse/panel scripts harness/panel_pd) on master and report raw hex / inline styles / token bypasses; list unmerged pd/* branches (git branch --no-merged master | grep pd/) with git diff --stat master...<b> | tail -1 and find WHY they did not merge (rg -l 'PD-CRUX|panel-integrate' harness docs -g '!**/worktrees/**'). Reading B (stale load): how does Houdini find the panel (packages/synapse.json, houdini/, .pypanel, PYTHONPATH, junctions); any installed copy that could shadow master (ls ~/Documents/houdini22.0 and HOUDINI_USER_PREF_DIR); reload mechanism coverage of the tokens module; __pycache__ risk. Give a definitive answer with evidence. Run the G3 strict audit if a script exists (60s timeout).` },
  { key: 'REVIEW', agentType: 'crucible', prompt: `LANE REVIEW - adversarial code review of ${RANGE}. git log --format='%h %s' ${RANGE} | head -100; git diff --stat ${RANGE} -- python/ scripts/ | tail -40. Hunt: (a) tests that cannot fail / expectations copied from the brief / mutation controls that never run; (b) phantom hou.*/pxr.*/pdg.* symbols new in range vs h22_symbol_table.json + rulebook/phantoms.json; (c) seams: is new code WIRED to a user-reachable surface (mcp_server.py registration, handler mixins actually mixed in, panel widgets actually instantiated) or dormant scaffolding with green tests; (d) undo/main-thread discipline on every new mutating hou call (CLAUDE.md section 1); (e) any 'fails closed' / policy default claims - verify the default path; (f) acceptance runners and NOT_RUN ledgers - what actually ran on what build vs what the release note claims. Report receipts-vs-reality gaps. Run at most 2 targeted test files.` },
  { key: 'HEALTH', agentType: 'cartographer', prompt: `LANE HEALTH - operational health at HEAD. (1) Test truth: release-note pass/fail/skip claim vs the standing failure(s) and skip reasons grouped (rg -n 'pytest.mark.skip|pytest.skip|skipif' tests -g '!**/worktrees/**'); are skips hiding Houdini-only coverage that never runs? (2) CI: .github/workflows/*.yml; is the mcp list_tools breakage (mcp_server.py ~L899) fixed; pinned mcp version; gh run list --limit 5 --branch master (10s timeout). (3) Health tools: synapse_health/doctor/live_metrics handlers - what they measure vs known failure classes (render freeze, marshal deadlock, bridge-down Qt fallback, Moneta unavailable). (4) Fresh-machine prerequisites (Python 3.13, H22.0.400 vs .429 hython pin, MONETA_SRC/PXR_PLUGINPATH_NAME) per DEPLOYMENT docs. (5) Hygiene: worktree count, __pycache__ under worktrees, .gitignore gaps evidenced by untracked files. Rank by what bites a new operator first.` },
  { key: 'INTENT', agentType: 'sidefx-cto', prompt: `LANE INTENT - does shipped match intended, and is the intent sound for a production H22 tool? Sources: CLAUDE.md, harness/battleplan/SPEC.md, the newest docs/*_v*/ blueprint, harness/*/briefs, harness/notes/RELEASE_v*.md (newest), the capsule commits in ${RANGE} ('definitions of closed as predicates'). (1) For each definition-of-closed predicate, does master satisfy it (evidence)? (2) Is the release-note title's claim borne out by code, not receipts? (3) Product vs harness: count commits in ${RANGE} touching python/synapse vs harness/+docs/; quantify. (4) SideFX-architect lens on the newest abstractions: aligned with how H22 Solaris/Karma/LOPs want to be driven, or a parallel universe? Top 3 second-order risks (deprecation, Indie/husk licensing, precision). (5) Open rulings (harness/notes/CTO_RULINGS_*.md): which still gate product; which could be decided by policy without Joe.` },
  { key: 'RECIPES', agentType: 'cartographer', prompt: `LANE RECIPES - are the recipes updated and which recipe system is live? Inventory every recipe home (rg -l 'recipe' python/synapse -g '!**/tests/**' | sed 's#/[^/]*$##' | sort -u): schema, count, last git touch, consumers (synapse_list_recipes, synapse_instantiate_graph/propose_graph, TieredRouter, panel recipe_card, handlers_recipe mixin). Do the homes talk or is one a fork behind a 'frozen seam'? Which recipes reference phantom or H21-era node types/parms (cross-check against rulebook/surfaces/<build>/ and h22_symbol_table.json)? Recipe ledger (SYNAPSE_RECIPE_LEDGER_DIR): any non-test writer? rag/ corpus recipe teachings consistent with code? Final: table recipe -> home -> last updated -> user-reachable via which tool -> H22-clean.` },
  { key: 'RSI', agentType: 'cartographer', prompt: `LANE RSI - audit self-improvement abilities. First principles: signal that cannot be faked, candidate producer, referee, apply path that lands in product, closure predicate the next run reads. Audit harness/rsi/REGISTRY.json (dict; loops under 'loops'), SPEC.md, LEDGER.md, CHAMPION.md, DEADENDS.md; harness/cto/BACKLOG.json + LEDGER.md (this loop's own record); ConductorAdvisor + RecommendationHistory consumers; harness/autoresearch, autorevise, loop, reach, ratchet, flywheel_queue.json. For each loop: status, which of the five components exist (path:line), has the apply path EVER executed outside tests (non-test call sites). Then specify 3-5 abilities that close one loop end-to-end with minimal human-in-loop, wiring existing dormant halves first: signal, producer, referee, apply path + gate, closure predicate, smallest proof test.` },
].filter(l => !ONLY || ONLY.includes(l.key))

phase('Sweep')
const sweep = await agent(`${CTX}\n\nASSIGNMENT: SWEEP. Read harness/cto/BACKLOG.json. For every item with status 'open', run its closure_predicate from repo root with a 60s timeout (bash -c). Exit 0 => 'closed'; non-zero => 'open'; command missing/unrunnable => 'unknown'; an item previously 'closed' whose predicate now fails => 'regressed'. Never mutate anything. Return results for every item and the total count. If the backlog is empty, return an empty results list.`,
  { label: 'sweep:backlog', phase: 'Sweep', schema: SWEEP, effort: 'low', agentType: 'cartographer' })
const closed = (sweep?.results || []).filter(r => r.status === 'closed').length
log(`Sweep: ${sweep?.backlog_count ?? 0} open items, ${closed} closed by predicate`)

phase('Find')
log(`Fanning ${LANES.length} lanes over ${HEAD} (${D})`)
const results = await pipeline(LANES,
  l => agent(`${CTX}\n\nASSIGNMENT:\n${l.prompt}`, { label: `find:${l.key}`, phase: 'Find', schema: FINDINGS, agentType: l.agentType }),
  (found, l) => {
    if (!found) return null
    log(`${l.key}: ${found.findings.length} findings -> verify`)
    return agent(`${CTX}\n\nASSIGNMENT: adversarial REFUTER for lane ${l.key}. You did not write these findings and you are motivated to kill them. For EACH: re-run its repro (60s timeout), check the evidence path:line exists and says what is claimed, decide CONFIRMED/REFUTED/DOWNGRADED/UPGRADED with a one-line reason. Default REFUTED if the repro does not reproduce or the evidence tier is 'claimed' while the finding asserts 'shipped'. Then hunt 'missed': the finding the lane should have made; probe 2-3 adjacent surfaces its prompt names. Judge whether the lane summary is accurate.\n\nLANE PROMPT:\n${l.prompt}\n\nFINDINGS TO ATTACK:\n${JSON.stringify(found, null, 1)}`,
      { label: `verify:${l.key}`, phase: 'Verify', schema: VERDICT, agentType: 'crucible', effort: 'high' })
      .then(v => ({ lane: l.key, found, verified: v }))
  })
const lanes = results.filter(Boolean)
if (lanes.length < LANES.length) log(`WARNING: ${LANES.length - lanes.length} lane(s) returned nothing - coverage is partial`)

phase('Synthesize')
const synth = await agent(`${CTX}\n\nASSIGNMENT: CTO synthesizer. Lanes below were each attacked by an independent refuter. A finding survives only if CONFIRMED/UPGRADED/DOWNGRADED (use corrected_severity); REFUTED is dead - count it, never list it. Refuter 'missed' items enter at stated severity only with evidence + repro. Dedupe across lanes. Rank critical->low then by leverage. Gate honestly: 'auto' only for reversible, test-covered, non-policy changes; 'crux' for code fixes; 'joe' for merges, policy, consent/undo/RBAC, panel visual design decisions. Every closure_predicate is a POSIX one-liner runnable from repo root, exit 0 = closed. Carry forward still-open items from the SWEEP with their original ids. Build rsi_scaffold from the RSI lane, trimmed to 3-5 abilities wiring EXISTING dormant halves first. Blunt, specific, no praise.\n\nSWEEP:\n${JSON.stringify(sweep)}\n\nLANES:\n${JSON.stringify(lanes, null, 1)}`,
  { label: 'cto:synthesize', phase: 'Synthesize', schema: SYNTH, effort: 'high' })

phase('Apply')
let applied = []
const autoItems = (synth?.backlog || []).filter(b => b.gate === 'auto')
if (APPLY && autoItems.length) {
  log(`Apply: ${autoItems.length} auto-gated items (autonomy=${AUTONOMY})`)
  applied = await parallel(autoItems.map(b => () =>
    agent(`${CTX}\n\nASSIGNMENT: FORGE one auto-gated backlog item in THIS worktree (you are already isolated; do not cd to the main tree). Item: ${JSON.stringify(b)}. Make the smallest change that satisfies its closure_predicate, run the predicate, run the most targeted test file that covers the change, and commit once with subject 'cto(auto): ${b.id} ${b.title}'. Never merge, push, or touch VERSION. Return: branch name, commit sha, predicate exit code, test summary line.`,
      { label: `apply:${b.id}`, phase: 'Apply', isolation: 'worktree', agentType: 'general-purpose' })))
} else {
  log(`Apply skipped (apply=${APPLY}, autonomy=${AUTONOMY}, auto items=${autoItems.length})`)
}

phase('Persist')
const persisted = await agent(`${CTX}\n\nASSIGNMENT: PERSIST (the one write-enabled step). Write harness/cto/runs/${D}/report.json containing {date, head, range, sweep, synth, applied, lanes} exactly as given below (pretty JSON). Update harness/cto/BACKLOG.json: mark items whose sweep status is 'closed' as status 'closed' with closed_run '${D}'; add every synth.backlog item not already present with status 'open', opened_run '${D}'; keep ids stable. Update harness/cto/STATE.json: runs += 1, last_run_date '${D}'. Append one row to harness/cto/LEDGER.md: | ${D} | <run> | ${lanes.length} | ${synth?.confirmed_count ?? 0} | ${synth?.refuted_count ?? 0} | ${closed} | <opened count> |. Do not touch any other file. Return the list of files written and the open backlog count.\n\nDATA:\n${JSON.stringify({ date: D, head: HEAD, range: RANGE, sweep, synth, applied, lanes })}`,
  { label: 'persist', phase: 'Persist', effort: 'low', agentType: 'general-purpose' })

return { date: D, head: HEAD, sweep, synth, applied, persisted, lanes_completed: lanes.length }
