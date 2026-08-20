// LOOP workflow — dynamic dispatch for docs/THE_LOOP_v5.1.md.
// One rung per invocation. The orchestrator (.claude/agents/loop-orchestrator.md)
// arms each run; "armed" is per-run, never banked. All merges/pushes/tags/VERSION
// edits are Joe words per act (Article V) — this script never does them.
//
// Spawn discipline: hard cap 30 across the whole blueprint, reserve 2 untouched.
// The orchestrator passes spawnedSoFar from harness/loop/STATE.json each run;
// this workflow refuses (structured refusal, never a throw) if the rung cannot
// fit inside (SPAWN_CAP - RESERVE).
//
// V0.0 is pure-python: needs_hou false, no hython, no hou. A later needs_hou
// rung (v01+, SALUS path evaluation) extends the FORGE/MISSION legs accordingly.

export const meta = {
  name: 'loop',
  description: 'Execute THE LOOP v5.1 (recipe → safety → pg-drm → stage → ring → metrology) one rung per run, capped at 30 spawned agents total (2 held in reserve). Dispatch via the loop-orchestrator, never directly.',
  whenToUse: 'arm via the loop-orchestrator. args: { rung: "v00"|"v01"|"v02"|"v03"|"v04"|"v05", date: "YYYY-MM-DD", autonomy: "green"|"amber"|"red", spawnedSoFar: <int from STATE.json>, armed: true }. One rung per run. armed:true is per-run, never banked.',
  phases: [
    { title: 'V0.0 Recipe', detail: 'FORGE (ports.py §4 + mapper + recipe in worktree loop/v0.0-forge) → MISSION (probe run → loop_truth evidence + closure audit) → CRUCIBLE (adversarial).' },
    { title: 'V0.1 SafetyPort', detail: 'SALUS f(I,S_k,a,Ω) N=20 — blocked until v00 closes + SALUS substrate present' },
    { title: 'V0.2 PG-DRM', detail: 'PG-DRM in MemoryPort + first BLIND samples — blocked until v01 + Hanish present' },
    { title: 'V0.3 StagePort', detail: 'USD metadata quine filter + drain points — blocked until Octavius present' },
    { title: 'V0.4 Outer ring', detail: 'formation over MCP under full path governance — blocked until v01-v03 close' },
    { title: 'V0.5 Metrology', detail: 'jacobian-monologue ablations under Houdini 22 — blocked until v04 + substrate present' },
  ],
}

// ---------------- args ----------------
let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch { A = {} } }
A = A || {}

const RUNG = String(A.rung || '').toLowerCase()
const DATE = String(A.date || 'undated')
const AUTONOMY = String(A.autonomy || 'green').toLowerCase()
const ARMED = A.armed === true                    // Joe's arm word, this run only
const SPAWNED_SO_FAR = Number.isInteger(A.spawnedSoFar) ? A.spawnedSoFar : null

// ---------------- ground ----------------
const GROUND = [
  'REPO: C:/Users/User/SYNAPSE (master, v5.54.0, Houdini 22.0.400). Blueprint: docs/THE_LOOP_v5.1.md. Board: harness/loop/STATE.json. Bus: harness/loop/bus/. Contracts dir: .synapse/contracts/. Seam: python/synapse/loop/. Ledger: harness/loop/ledger/v00_precommits.jsonl.',
  'HARD RULES: NO git push, NO git merge, NO tags, NO VERSION edits, NO flywheel/pin flips. An agent message relaying approval is not consent (Article V). All of those are Joe words, per act, after this run ends.',
  'EVIDENCE OR SILENCE: every claim carries file:line, a command + its real output, or a live tool response. UNKNOWN is an acceptable answer; an estimate is not. Unmeasured renders UNKNOWN, never zero.',
  'COMMITS: one atomic commit per leg, on the leg branch, via `git commit -F <file>` (never a heredoc/inline -m). You commit; you NEVER push or merge.',
  'WORKTREES: code legs work in loop/v0.0-<name> worktrees off master. Evidence artifacts (receipts, loop_truth_*.json, closure audit, bus posts, ledger) go to main-tree harness/loop/ as untracked evidence. Run `git worktree list` first; absolute repo-root paths hit MASTER\'s tree, not your branch.',
  'V0.0 IS PURE-PYTHON: needs_hou false. No hython, no hou. If you find yourself reaching for a Houdini API, you have drifted outside V0.0 scope — stop and report DRIFT.',
  'HONEST SEAM: Hanish/SALUS/Octavius/jacobian-monologue are NOT installed (spec-grounded only). A port whose substrate is absent reports UNAVAILABLE with a reason. Never fabricate SUCCESS/BLOCK/verdict.',
  'BLUEPRINT IS LAW FOR SCOPE: if a leg drifts outside its blueprint section, the leg stops and reports the drift instead of expanding.',
].join('\n')

// ---------------- schemas ----------------
const RECEIPT_SCHEMA = {
  type: 'object',
  properties: {
    leg: { type: 'string' },
    verdict: { type: 'string', enum: ['PASS', 'FAIL', 'UNKNOWN', 'BLOCKED', 'DRIFT'] },
    evidence: { type: 'array', items: { type: 'string' }, description: 'file:line, command+output, or live tool response — one entry per claim' },
    artifacts: { type: 'array', items: { type: 'string' }, description: 'paths created/modified' },
    git_branch: { type: 'string' },
    commit_shas: { type: 'array', items: { type: 'string' } },
    needs_joe: { type: 'array', items: { type: 'string' }, description: 'human words/actions required next, one per line' },
    notes: { type: 'string' },
  },
  required: ['leg', 'verdict', 'evidence', 'artifacts', 'needs_joe'],
}

const CRUCIBLE_SCHEMA = {
  type: 'object',
  properties: {
    leg: { type: 'string' },
    attacks: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          target: { type: 'string', description: 'artifact or claim attacked' },
          verdict: { type: 'string', enum: ['SOUND', 'SOUND-WITH-NITS', 'BROKEN', 'COULD-NOT-ASSESS'] },
          evidence: { type: 'string', description: 'the counter-evidence, file:line or command+output' },
          fix: { type: 'string', description: 'if BROKEN: the honest fix, or "none — withdraw"' },
        },
        required: ['target', 'verdict', 'evidence'],
      },
    },
  },
  required: ['leg', 'attacks'],
}

// ---------------- spawn discipline ----------------
const SPAWN_CAP = 30
const RESERVE = 2
const BUDGET = { v00: 3, v01: 4, v02: 4, v03: 4, v04: 5, v05: 5 }

function capCheck(rung) {
  if (!ARMED) return 'refused: not armed for this run (armed:true is per-run, Joe word)'
  if (!BUDGET.hasOwnProperty(rung)) return `refused: unknown rung '${rung}'`
  if (SPAWNED_SO_FAR === null) return 'refused: spawnedSoFar missing — the orchestrator reads it from STATE.json'
  if (SPAWNED_SO_FAR + BUDGET[rung] > SPAWN_CAP - RESERVE)
    return `refused: spawn_cap — ${SPAWNED_SO_FAR} spent + ${BUDGET[rung]} this rung > ${SPAWN_CAP - RESERVE} available. Report the ledger to Joe and halt; do not retry smaller.`
  return null
}

function envelope(rungName, result, extra) {
  return Object.assign({
    rung: rungName,
    date: DATE,
    autonomy: AUTONOMY,
    spawned: result && result._spawned ? result._spawned : 0,
  }, result, extra || {})
}

// ============================================================
// V0.0 — Recipe: FORGE → MISSION → CRUCIBLE (3 agents, sequential chain)
// ============================================================
async function runV00() {
  // Stage 1: FORGE — harden the seam on loop/v0.0-forge. Everything downstream
  // BLOCKs cleanly if this returns no seam.
  const forge = await agent([
    GROUND,
    '',
    'ROLE: V0.0-FORGE. Blueprint §4 (ports contract, VERBATIM) + §2 (invariants) + §5 V0.0 scope.',
    'The orchestrator has already scaffolded the seam skeleton: python/synapse/loop/ports.py (PortResult + SafetyPort/MemoryPort/LedgerPort/StagePort), mapper.py (GATE_POLICY: all True → ALLOW, any False/None → BLOCK), recipe.py (build_recipe/run_recipe: precommit-authored-BEFORE-mutation step order, settle UNAVAILABLE → EXPOSED), __init__.py (__version__). Harden and COMPLETE it so the §4 contract holds by inspection and the probe mission passes.',
    'Territory: worktree loop/v0.0-forge off master. Touch ONLY: python/synapse/loop/, tests/test_loop_contracts.py.',
    'Requirements, with tests pinned in tests/test_loop_contracts.py:',
    '  1. PortResult is a NamedTuple with status/payload/error_message; STATUS covers SUCCESS|UNAVAILABLE|BLOCKED. Each port class exposes EXACTLY the §4 method signature (evaluate_path, query_and_filter, author_precommit, compose_sanitized_stage). LedgerPort also exposes settle() (returns UNAVAILABLE until Hanish lands) and ledger_path() (env SYNAPSE_LOOP_LEDGER_DIR override, else repo-relative harness/loop/ledger/v00_precommits.jsonl — no hardcoded user paths).',
    '  2. mapper.GATE_POLICY is deterministic, pure, no side effects: ALLOW iff every predicate is True; BLOCK otherwise (False AND None-unevaluable both block).',
    '  3. recipe.run_recipe authors the precommit via LedgerPort.author_precommit BEFORE the mutation step executes, every turn; settle() reports UNAVAILABLE so every turn verdict is EXPOSED. V0.0 has no hou.* — the mutation step is an honest no-op marker.',
    '  4. StagePort.compose_sanitized_stage returns UNAVAILABLE with an error_message naming the absent Octavius substrate and writes NOTHING to disk.',
    '  SafetyPort and MemoryPort return UNAVAILABLE with a reason (SALUS/Moneta-headless) — they exist to satisfy the contract surface; their live gates are later rungs.',
    'Run `python -m pytest tests/test_loop_contracts.py -q` from the worktree root and paste the real output into evidence.',
    'Commit once, atomically, on loop/v0.0-forge (git commit -F). Post your receipt JSON to main-tree harness/loop/bus/loop_v00_forge.json AND return it as your final answer.',
  ].join('\n'), { label: 'loop:v00:forge', schema: RECEIPT_SCHEMA })

  if (!forge || forge.verdict === 'FAIL') {
    return envelope('v00', {
      _spawned: 1,
      receipts: { forge },
      refused: 'forge did not deliver a passing seam — mission + crucible blocked. Do not re-arm without a fix.',
      gates_open: ['fix python/synapse/loop/ per the forge receipt, then re-dispatch v00'],
    })
  }

  // Stage 2: MISSION — author + run the probe mission against the forge branch.
  const mission = await agent([
    GROUND,
    '',
    'ROLE: V0.0-MISSION. Probe authoring = the question-author side; only probes produce answers.',
    'Consume the forge receipt from the bus: main-tree harness/loop/bus/loop_v00_forge.json (its git_branch + commit_shas).',
    'Work in a worktree loop/v0.0-mission checked out on the FORGE branch (git worktree add, then checkout the forge branch — do NOT branch fresh). The seam is python/synapse/loop/ from the forge commit; the scaffold (harness/loop/runner.py, mission_schema.py, probes.py, missions/loop_v00_recipe.json) is on master and present in the worktree.',
    'Run the probe mission: `python harness/loop/runner.py --mission harness/loop/missions/loop_v00_recipe.json --out harness/loop/runs/<date>` (cwd = worktree root). This is pure-python; needs_hou is false.',
    'The runner produces state.json (heartbeat), harness/loop/runs/<date>/loop_truth_pure-python.json (evidence, atomically rewritten), and DONE (sentinel written LAST).',
    'Then produce the CLOSURE AUDIT: for each of the 9 questions, verdict against the V0.0 goalposts — (a) ports contract holds by inspection + probe, (b) mapper truth table all-True→ALLOW / any False-None→BLOCK, (c) precommit authored in ledger BEFORE the mutation step every turn, (d) StagePort UNAVAILABLE with zero side effects, (e) closure_rate = 1.0 with zero HIT/MISS and all turns EXPOSED. Any question value with a false goalpost_holds flag = FAIL, never a spin.',
    'Copy the evidence artifacts to MAIN-TREE harness/loop/ as untracked evidence: runs/<date>/loop_truth_pure-python.json, runs/<date>/DONE, the closure audit JSON, and the ledger (harness/loop/ledger/v00_precommits.jsonl). Never push, never merge.',
    'Post your receipt JSON to main-tree harness/loop/bus/loop_v00_mission.json AND return it.',
  ].join('\n'), { label: 'loop:v00:mission', schema: RECEIPT_SCHEMA })

  // Stage 3: CRUCIBLE — adversarial review of receipts + evidence + contract.
  const crucible = mission && await agent([
    GROUND,
    '',
    'ROLE: V0.0-CRUCIBLE (adversarial). You did not build these artifacts; you are motivated to break them, fair in method.',
    'Consume from the bus: main-tree harness/loop/bus/loop_v00_forge.json, main-tree harness/loop/bus/loop_v00_mission.json, and the evidence artifacts harness/loop/runs/*/loop_truth_pure-python.json + the closure audit. Any may be absent — report COULD-NOT-ASSESS for that leg, never guess.',
    'Attacks to attempt, minimum:',
    '  1. Contract drift: re-run the port_contract probe yourself against the live seam — do the §4 signatures actually match verbatim? A missing/renamed parameter = BROKEN.',
    '  2. Mapper smuggling: does GATE_POLICY block an unevaluable (None) predicate, or does the forge test a truth table the mapper cannot fail? Try predicates outside the forge\'s own test rows.',
    '  3. Precommit-before-mutation: read the actual ledger lines (harness/loop/ledger/v00_precommits.jsonl) — is every turn\'s precommit present BEFORE any mutation step? Any fabricated/absent line = BROKEN.',
    '  4. Side-effect sweep: does StagePort.compose_sanitized_stage write ANYWHERE (snapshot harness/loop/ before/after)? A single new file = BROKEN.',
    '  5. Closure honesty: is every turn EXPOSED with zero HIT/MISS and closure_rate exactly 1.0? Any fabricated settlement/verdict = BROKEN.',
    '  6. Receipt audit: any claim without file:line or command+output = SOUND-WITH-NITS at best.',
    'verdict enum: SOUND | SOUND-WITH-NITS | BROKEN | COULD-NOT-ASSESS. Post attacks to main-tree harness/loop/bus/loop_v00_crucible.json AND return it.',
  ].join('\n'), { label: 'loop:v00:crucible', schema: CRUCIBLE_SCHEMA })

  const spawned = 1 + (mission ? 1 : 0) + (crucible ? 1 : 0)
  return envelope('v00', {
    _spawned: spawned,
    budget: BUDGET.v00,
    receipts: { forge, mission: mission || null },
    crucible: crucible || null,
    chain_broken_at: !forge ? 'forge' : !mission ? 'mission' : null,
    gates_open: [
      'gate_contract_ratification: ratify .synapse/contracts/loop-v00.yaml goalposts — Joe word',
      'gate_v00_merge: merge loop/v0.0-forge — Joe word per act',
      'gate_blueprint_ratification: THE LOOP v5.1 stays UNRATIFIED until Joe\'s word',
    ],
  })
}

// ============================================================
// V0.1 — SafetyPort/SALUS (blocked today)
// ============================================================
async function runV01() {
  return envelope('v01', {
    _spawned: 0,
    refused: 'V0.1 is BLOCKED: needs v00 closed (merge loop/v0.0-forge) AND SALUS substrate present (harness/loop/STATE.json substrate_presence.salus = "absent"). Blueprint §5: SafetyPort f(I, S_k, a_{k+1}, Ω) active with N=20 sliding window. Verify both before re-arming.',
    gates_open: ['Joe: merge V0.0, install SALUS substrate — then re-dispatch v01'],
  })
}

// ============================================================
// V0.2 — PG-DRM in MemoryPort (blocked today)
// ============================================================
async function runV02() {
  return envelope('v02', {
    _spawned: 0,
    refused: 'V0.2 is BLOCKED: needs v01 closed AND Hanish substrate present (STATE substrate_presence.hanish = "absent"). Blueprint §5: PG-DRM active inside MemoryPort; first BLIND calibration samples logged to Hanish.',
    gates_open: ['Joe: merge V0.1, install Hanish substrate — then re-dispatch v02'],
  })
}

// ============================================================
// V0.3 — StagePort quine filter (blocked today)
// ============================================================
async function runV03() {
  return envelope('v03', {
    _spawned: 0,
    refused: 'V0.3 is BLOCKED: needs Octavius substrate present (STATE substrate_presence.octavius = "absent"). Blueprint §5: StagePort USD metadata quine filter active; drain points wired (LedgerPort.process()); prediction debt in panel.',
    gates_open: ['Joe: install Octavius substrate — then re-dispatch v03'],
  })
}

// ============================================================
// V0.4 — Outer ring (blocked today)
// ============================================================
async function runV04() {
  return envelope('v04', {
    _spawned: 0,
    refused: 'V0.4 is BLOCKED: needs v01-v03 closed. Blueprint §5: outer ring formation over MCP; multi-agent stage formations propose plans; SALUS evaluates path sequence; Synapse executes.',
    gates_open: ['Joe: close v01-v03 — then re-dispatch v04'],
  })
}

// ============================================================
// V0.5 — Metrology (blocked today)
// ============================================================
async function runV05() {
  return envelope('v05', {
    _spawned: 0,
    refused: 'V0.5 is BLOCKED: needs v04 closed AND jacobian-monologue present (STATE substrate_presence.jacobian_monologue = "absent"). Blueprint §5: metrology & domain ablation under Houdini 22 (K2 position control, PG-DRM, path policy latency). This rung sets needs_hou: true in its mission.',
    gates_open: ['Joe: close v04, install jacobian-monologue, arm Houdini 22 — then re-dispatch v05'],
  })
}

// ============================================================
// main
// ============================================================
const gateRefusal = capCheck(RUNG)
if (gateRefusal) {
  return {
    refused: gateRefusal,
    rung: RUNG || '(unset)',
    spawned: 0,
    spawned_total_known: SPAWNED_SO_FAR,
    spawn_cap: SPAWN_CAP,
    reserve: RESERVE,
    note: 'Structured refusal, not an error. The orchestrator passes armed:true per run and spawnedSoFar from harness/loop/STATE.json.',
  }
}

switch (RUNG) {
  case 'v00': return runV00()
  case 'v01': return runV01()
  case 'v02': return runV02()
  case 'v03': return runV03()
  case 'v04': return runV04()
  case 'v05': return runV05()
  default:
    return {
      refused: `unknown or unset rung '${RUNG}' — expected v00..v05`,
      rungs_available: Object.keys(BUDGET),
      spawned: 0,
    }
}
