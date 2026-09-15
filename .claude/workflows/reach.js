// REACH workflow — dynamic dispatch for docs/REACH_BLUEPRINT.md.
// One phase per invocation. The orchestrator (.claude/agents/reach-orchestrator.md)
// arms each run; "armed" is per-run, never banked. All merges/pushes/tags/VERSION
// edits are Joe words per act (Article V) — this script never does them.
//
// Spawn discipline: hard cap 30 across the whole blueprint, reserve 2 untouched.
// The orchestrator passes spawnedSoFar from harness/reach/STATE.json each run;
// this workflow refuses (structured refusal, never a throw) if the phase cannot
// fit inside (SPAWN_CAP - RESERVE).

export const meta = {
  name: 'reach',
  description: 'Execute the REACH blueprint (skills library + reach gates) one phase per run, capped at 30 spawned agents total (2 held in reserve). Dispatch via the reach-orchestrator, never directly.',
  whenToUse: 'arm via the reach-orchestrator. args: { phase: "p1"|"p2"|"p3"|"p4"|"p5"|"p6"|"p7"|"p0", date: "YYYY-MM-DD", autonomy: "green"|"amber"|"red", spawnedSoFar: <int from STATE.json>, armed: true }. One phase per run. armed:true is per-run, never banked.',
  phases: [
    { title: 'P1 Truth',   detail: 'R2 public-face agreement contract + R3 reach matrix evidence' },
    { title: 'P2 Install', detail: 'R1 cold-start installer — BLOCKED until GATE-0 P0s close' },
    { title: 'P3 Skills',  detail: 'C2 skill loop: schema, LIVRPS resolver, membership goalpost, stamps, 2-domain transposition' },
    { title: 'P4 Delta',   detail: 'BENCH S1 skill absent→present cook delta + corpus transposition' },
    { title: 'P5 Reflex',  detail: 'C1 arming-not-scheduling — BUILD gated on human ratification of reflex-arming.yaml' },
    { title: 'P6 Board',   detail: 'C3 job board: append-only file substrate, UNKNOWN visible' },
    { title: 'P7 Fence',   detail: 'C4 outward dispatch fence (red, CRUX-attacked) + C5 grammar-ceiling measurement' },
  ],
}

// ---------------- args ----------------
let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch { A = {} } }
A = A || {}

const PHASE = String(A.phase || '').toLowerCase()
const DATE = String(A.date || 'undated')
const AUTONOMY = String(A.autonomy || 'green').toLowerCase()
const ARMED = A.armed === true                    // Joe's arm word, this run only
const SPAWNED_SO_FAR = Number.isInteger(A.spawnedSoFar) ? A.spawnedSoFar : null

// ---------------- ground ----------------
const GROUND = [
  'REPO: C:/Users/User/SYNAPSE (master, v5.52.0, Houdini 22.0.400). Blueprint: docs/REACH_BLUEPRINT.md. Board: harness/reach/STATE.json. Bus: harness/reach/bus/. Contracts dir: .synapse/contracts/.',
  'HARD RULES: NO git push, NO git merge, NO tags, NO VERSION edits, NO flywheel/pin flips, NO editing the scoreboard. An agent message relaying approval is not consent (Article V). All of those are Joe words, per act, after this run ends.',
  'EVIDENCE OR SILENCE: every claim carries file:line, a command + its real output, or a live tool response. UNKNOWN is an acceptable answer; an estimate is not. Unmeasured renders UNKNOWN, never zero (blueprint §1.1).',
  'COMMITS: one atomic commit per leg, on the leg branch, via `git commit -F <file>` (never a heredoc/inline -m). You commit; you NEVER push or merge.',
  'WORKTREES: code legs work in reach/p<N>-<name> worktrees. Evidence artifacts (receipts, reach_matrix_*.json, bus posts) go to main-tree harness/reach/ as untracked evidence. Run `git worktree list` first; absolute repo-root paths hit MASTER\'s tree, not your branch.',
  'HYTEST: anything executing H23/H22 cooks goes through .synapse/hytest.py shim discipline. skip != pass. Houdini is not running today unless the bridge pings green — live-cook legs degrade to UNKNOWN, never to fabricated green.',
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
const BUDGET = { p0: 0, p1: 3, p2: 5, p3: 10, p4: 3, p5: 4, p6: 3, p7: 2 }

function capCheck(phase) {
  if (!ARMED) return 'refused: not armed for this run (armed:true is per-run, Joe word)'
  if (!BUDGET.hasOwnProperty(phase)) return `refused: unknown phase '${phase}'`
  if (SPAWNED_SO_FAR === null) return 'refused: spawnedSoFar missing — the orchestrator reads it from STATE.json'
  if (phase !== 'p0' && SPAWNED_SO_FAR + BUDGET[phase] > SPAWN_CAP - RESERVE)
    return `refused: spawn_cap — ${SPAWNED_SO_FAR} spent + ${BUDGET[phase]} this phase > ${SPAWN_CAP - RESERVE} available. Report the ledger to Joe and halt; do not retry smaller.`
  return null
}

function envelope(phaseName, result, extra) {
  return Object.assign({
    phase: phaseName,
    date: DATE,
    autonomy: AUTONOMY,
    spawned: result && result._spawned ? result._spawned : 0,
  }, result, extra || {})
}

// ============================================================
// P0 — GATE-0 P0 closeout read (orchestrator-side evidence, 0 agents)
// The orchestrator verifies gate state with reads; this lane emits the
// structured verdict for the board and never touches anything.
// ============================================================
// (p0 spawns nothing — handled by the shell below as a structured refusal
//  pointing at the human gate list.)

// ============================================================
// P1 — Truth: R2 forge + R3 author, then crucible (3 agents)
// ============================================================
async function runP1() {
  const forge = () => agent([
    GROUND,
    '',
    'ROLE: R2-FORGE. Blueprint §4 R2 + §7 reach-public-agreement.yaml.',
    'Territory: worktree reach/p1-r2 off master. Touch ONLY: harness/verify/version_agreement.py, .synapse/contracts/reach-public-agreement.yaml, tests/.',
    'FIRST, the free check: read README.md line ~1-15 and VERSION. If README-fronted version == VERSION, record it as evidence and do NOT rewrite the README — the blueprint explicitly warns the README was rewritten 2026-08-17 and may already be closed. The work left is DURABILITY, not cosmetics:',
    '  1. Extend harness/verify/version_agreement.py so public artifacts are covered: README claimed version == tagged version, else red. Check how it currently scopes and extend, do not fork it.',
    '  2. Author .synapse/contracts/reach-public-agreement.yaml with the goalpost: README version == `git describe --tags`-style tag; drift is red. Note in the contract that the changelog falls out of the existing bump/verify/tag ritual for free.',
    '  3. Tests for both additions.',
    '  4. Run the extended verifier live and paste its real output into evidence.',
    'Post your receipt JSON to harness/reach/bus/reach_p1_r2.json AND return it as your final answer.',
  ].join('\n'), { label: 'reach:p1:r2-forge', schema: RECEIPT_SCHEMA })

  const author = () => agent([
    GROUND,
    '',
    'ROLE: R3-AUTHOR. Blueprint §4 R3 + §7 reach-matrix.yaml.',
    'Produce harness/reach/reach_matrix_' + DATE + '.json: the grid (Houdini build x licence tier x OS), every cell runs / fails / UNKNOWN.',
    'Today\'s honest state: one green cell (build 22.0.400, Windows, licence tier: probe harness/state/drop.json + docs/memory for Indie-vs-Commercial evidence; if you cannot verify the tier from an artifact, the tier is UNKNOWN — say so, never infer). Every other cell is UNKNOWN. An unnamed cell fails the contract — name every cell explicitly.',
    'Also author .synapse/contracts/reach-matrix.yaml: goalpost = every (build x tier x OS) cell is runs/fails/UNKNOWN and no cell is unnamed. Note that Apprentice/Indie tiers are where beta testers live and the Gate A L3-5 Apprentice session is already an outstanding human task — same work, two purposes.',
    'This leg writes evidence only (main-tree harness/reach/ + .synapse/contracts/), no code, no worktree needed for files that are pure artifacts; if you touch .synapse/contracts/ use worktree reach/p1-r3 and put the worktree path in git_branch.',
    'Post your receipt JSON to harness/reach/bus/reach_p1_r3.json AND return it.',
  ].join('\n'), { label: 'reach:p1:r3-author', schema: RECEIPT_SCHEMA })

  const built = await parallel([forge, author])
  const live = built.filter(Boolean)

  const crucible = await agent([
    GROUND,
    '',
    'ROLE: CRUCIBLE (adversarial). You did not build these artifacts; you are motivated to break them, fair in method.',
    'Consume from the bus: harness/reach/bus/reach_p1_r2.json and harness/reach/bus/reach_p1_r3.json (either may be absent — report COULD-NOT-ASSESS for that leg, never guess).',
    'Attacks to attempt, minimum:',
    '  1. R2: does the extended version_agreement.py actually GO red when README and tag disagree? Construct the disagreement (temp files/branches, never committed misleading state) and show the real output.',
    '  2. R2: does the contract goalpost catch a README that was correct yesterday and stale today (the apex_probes.py June defect class)?',
    '  3. R3: is any cell in reach_matrix silently green without an artifact? Is any cell unnamed? Is the licence tier claimed without evidence?',
    '  4. Both: any claim in the receipts that lacks file:line or a command+output citation?',
    'Return: for each attack, target + verdict (SOUND | SOUND-WITH-NITS | BROKEN | COULD-NOT-ASSESS) + counter-evidence + honest fix if BROKEN.',
    'Post your attacks JSON to harness/reach/bus/reach_p1_crucible.json AND return it.',
  ].join('\n'), { label: 'reach:p1:crucible', schema: CRUCIBLE_SCHEMA })

  return envelope('p1', {
    _spawned: 1 + live.length,
    receipts: live,
    crucible,
    gates_open: ['none — P1 is evidence; any merges of reach/p1-* worktrees are Joe words'],
  })
}

// ============================================================
// P2 — Install (BLOCKED today; lane defined for when GATE-0 closes)
// ============================================================
async function runP2() {
  return envelope('p2', {
    _spawned: 0,
    refused: 'P2 is BLOCKED by GATE-0: TRUTH-P0-1, TRUTH-P0-2, ENG-INJ-GATE-OFF are open in harness/reach/STATE.json (BASTION MX-3). Blueprint §8: close the P0s, then open the door. Verify STATE gate0_open_p0s are resolved before re-arming this phase.',
    gates_open: [
      'GATE-0: Joe closes/confirms the three P0s (two fixes + one consent-posture DECIDE)',
      'Then re-dispatch with phase p2 — lane roster: installer-forge, verifier, step-counter, crucible, clean-room PREP (the genuine stranger-machine run is Joe\'s, never an agent\'s)',
    ],
  })
}

// ============================================================
// P3 — Skills: C2 loop (10 agents)
// ============================================================
async function runP3() {
  // Stage 1: cartographer (read-only) — the map everything else hangs on.
  // Everything downstream BLOCKs cleanly if this returns no map.
  const carto = await agent([
    GROUND,
    '',
    'ROLE: CARTOGRAPHER (read-only). Blueprint §3.2 (seven-arrow loop), §3.4 (six prose methods).',
    'Produce harness/reach/bus/reach_p3_map.json:',
    '  1. Locate the six prose methods (solaris-usd-composition, vex-pattern-library, pdg-tops-patterns, materialx-cross-renderer, houdini-performance-profiling, hdk-build-recipes) — real paths, real sizes. If fewer than six exist, that is a finding; do not invent the missing ones.',
    '  2. For each of the seven arrows (author, install, compose, resolve, apply, verify, stamp): which substrate pieces already exist in python/synapse/ (memory/agent_state.py USD substrate, APEXFORGE WA1 catalog-membership goalpost path, harness/verify/, .synapse/harness.py worker entry) — file:line citations.',
    '  3. Explicitly name what is ABSENT (expected: the in-Houdini resolution layer and the skill package format).',
    '  4. Recommend the territory for python/synapse/skills/ (module layout only, no code).',
    'You write ONLY to harness/reach/bus/. Return the map path + a 6-line summary.',
  ].join('\n'), { label: 'reach:p3:cartographer', schema: RECEIPT_SCHEMA })

  if (!carto || carto.verdict === 'FAIL') {
    return envelope('p3', {
      _spawned: 1,
      receipts: [carto],
      refused: 'cartographer did not deliver the map — downstream legs blocked. Do not re-arm without a fix.',
    })
  }

  // Stage 2 (parallel, disjoint territories): contracts scribe vs core forge.
  // scribe -> worktree reach/p3-schema (contracts only, no code)
  const scribe = () => agent([
    GROUND,
    '',
    'ROLE: SCHEMA-SCRIBE. Blueprint §3.1: a skill = opinion + evidence + build stamp.',
    'Consume harness/reach/bus/reach_p3_map.json via the bus.',
    'Author .synapse/contracts/skill-loop.yaml (author→install→compose→resolve→apply→verify→stamp round-trips; precedence deterministic repeat-2) AND .synapse/contracts/skill-stamp.yaml (every installed skill carries build + date + evidence ref; unstamped loads in hypothesis mode and announces it).',
    'Territory: worktree reach/p3-schema. Contracts ONLY — no code.',
    'Every goalpost must be mechanically checkable. Post receipt to harness/reach/bus/reach_p3_schema.json and return it.',
  ].join('\n'), { label: 'reach:p3:schema-scribe', schema: RECEIPT_SCHEMA })

  // core chain on worktree reach/p3-core: forge skeleton -> livrps resolver (sequential, same branch)
  const coreForge = () => agent([
    GROUND,
    '',
    'ROLE: CORE-FORGE. Build the skills skeleton per the cartographer\'s recommendation: python/synapse/skills/ on worktree reach/p3-core.',
    'Consume harness/reach/bus/reach_p3_map.json via the bus.',
    'Deliver: the package layout + skill file format (opinion / evidence-ref / build-stamp as first-class fields) + install path that REJECTS a skill with no stamp into hypothesis mode with an announcement (never silent, never fake).',
    'Tests for the format round-trip. Commit via git commit -F. Post receipt to harness/reach/bus/reach_p3_core.json and return it.',
  ].join('\n'), { label: 'reach:p3:core-forge', schema: RECEIPT_SCHEMA })

  const coreBuilt = await parallel([scribe, coreForge])

  // Stage 3 (sequential on reach/p3-core — same files, no parallel writes):
  const livrps = coreBuilt[1] && await agent([
    GROUND,
    '',
    'ROLE: LIVRPS-RESOLVER. Blueprint §3.2(b): skill precedence is LIVRPS composition, NOT priority integers. THE MOAT.',
    'Consume harness/reach/bus/reach_p3_core.json. Extend the skills skeleton on worktree reach/p3-core (check out that branch — do NOT branch fresh).',
    'Implement precedence: studio method sublayers, project method references, shot override = stronger local opinion; composition resolves deterministically.',
    'HARD RULE: no priority integer, no recency rule, no scoring function ANYWHERE. If two skills conflict, the stage resolves it.',
    'Test (blueprint S2): two conflicting skills, one prompt, one predicted winner, binary assert, repeat-2 IDENTICAL. Paste the real test output into evidence.',
    'Post receipt to harness/reach/bus/reach_p3_livrps.json and return it.',
  ].join('\n'), { label: 'reach:p3:livrps', schema: RECEIPT_SCHEMA })

  const membership = livrps && await agent([
    GROUND,
    '',
    'ROLE: MEMBERSHIP-WIRING. Blueprint §3.2(c): a skill cannot name a node type that does not exist.',
    'Locate the APEXFORGE WA1 catalog-membership goalpost (harness/apexforge/ — it exists; find it, cite it. If it does NOT exist, that is a finding: verdict DRIFT, evidence, stop).',
    'Author .synapse/contracts/skill-catalog-membership.yaml: inherits the WA1 goalpost shape — no skill emits a type absent from the catalog; a MISSING catalog artifact fails LOUDLY (never silently passes).',
    'Wire the check into the skills install path on worktree reach/p3-core (install-time failure, not run-time). Test with a skill naming a deliberately phantom type — must fail to install with the phantom named in the error. Real output in evidence.',
    'Post receipt to harness/reach/bus/reach_p3_membership.json and return it.',
  ].join('\n'), { label: 'reach:p3:membership', schema: RECEIPT_SCHEMA })

  const stamper = membership && await agent([
    GROUND,
    '',
    'ROLE: STAMP-ENFORCER. Blueprint §3.1/§7 skill-stamp.yaml.',
    'On worktree reach/p3-core: enforce at the loader that every installed skill resolves its stamp against the live build (build equality check + age warning). Stamp = build 22.0.400 + date + evidence-artifact ref. An unstamped skill loads hypothesis-mode and ANNOUNCES it; a fake stamp MUST fail the check — write a test where a forged stamp is rejected, real output in evidence.',
    'Post receipt to harness/reach/bus/reach_p3_stamp.json and return it.',
  ].join('\n'), { label: 'reach:p3:stamp', schema: RECEIPT_SCHEMA })

  // Stage 4: two transposers in parallel (read skeleton, write distinct skill files)
  const transposer = (method, idx) => () => agent([
    GROUND,
    '',
    `ROLE: TRANSPOSER-${idx}. Blueprint §3.4: prose method '${method}' → stamped skill on worktree reach/p3-core.`,
    'The prose survives (opinion). Trigger model + catalog membership are per the skeleton. Stamp carries build=22.0.400, this date, evidence ref. No fake stamps.',
    'If the skeleton or an earlier stage is broken (check the bus receipts first), return BLOCKED with what you checked — do not write skills onto a broken skeleton.',
    `Post receipt to harness/reach/bus/reach_p3_transpose_${idx}.json and return it.`,
  ].join('\n'), { label: `reach:p3:transpose-${idx}`, schema: RECEIPT_SCHEMA })

  const transposed = stamper ? await parallel([
    transposer('solaris-usd-composition', 'a'),
    transposer('pdg-tops-patterns', 'b'),
  ]) : []

  // Stage 5: full-loop verifier + crucible (parallel — verifier repeats the arrows; crucible attacks)
  const loopVerify = () => agent([
    GROUND,
    '',
    'ROLE: LOOP-VERIFY. Run the seven arrows END TO END on worktree reach/p3-core: author a minimal throwaway skill → install → compose → resolve → apply → verify → stamp. Produce a receipt per arrow with real command output. Any arrow that cannot execute = FAIL with evidence (that is the loop being absent, per blueprint §3.2).',
    'Also run blueprint S2 live: two conflicting transposed skills, one prompt, predicted winner, repeat-2 identical — real outputs pasted.',
    'Post receipt to harness/reach/bus/reach_p3_loopverify.json and return it.',
  ].join('\n'), { label: 'reach:p3:loop-verify', schema: RECEIPT_SCHEMA })

  const crucible = () => agent([
    GROUND,
    '',
    'ROLE: CRUCIBLE (adversarial). Consume every reach_p3_*.json on the bus. You built nothing; you are motivated to break it.',
    'Attacks, minimum:',
    '  1. Priority-integer hunt: grep the skills package for any priority/recency/scoring mechanism. One hit = BROKEN, cite it.',
    '  2. Stamp forgery: can you install a skill with a fabricated stamp? If yes, BROKEN + the path.',
    '  3. Phantom smuggle: author a skill naming a node type you invent — does install refuse it WITH the phantom named?',
    '  4. Determinism: run the S2 repeat THREE times, not two — any variance = BROKEN.',
    '  5. Receipt audit: any claim without file:line or command+output = SOUND-WITH-NITS at best.',
    'verdict enum: SOUND | SOUND-WITH-NITS | BROKEN | COULD-NOT-ASSESS. Post attacks to harness/reach/bus/reach_p3_crucible.json and return it.',
  ].join('\n'), { label: 'reach:p3:crucible', schema: CRUCIBLE_SCHEMA })

  const verified = transposed.length ? await parallel([loopVerify, crucible]) : []

  const spawned = 1 + coreBuilt.filter(Boolean).length
    + (livrps ? 1 : 0) + (membership ? 1 : 0) + (stamper ? 1 : 0)
    + transposed.filter(Boolean).length + verified.filter(Boolean).length

  return envelope('p3', {
    _spawned: spawned,
    budget: BUDGET.p3,
    receipts: {
      cartographer: carto,
      schema: coreBuilt[0] || null,
      core: coreBuilt[1] || null,
      livrps: livrps || null,
      membership: membership || null,
      stamp: stamper || null,
      transpose_a: transposed[0] || null,
      transpose_b: transposed[1] || null,
    },
    loop_verify: verified[0] || null,
    crucible: verified[1] || null,
    chain_broken_at: !coreBuilt[1] ? 'core-forge' : !livrps ? 'livrps' : !membership ? 'membership' : !stamper ? 'stamp' : !transposed.length ? 'transpose' : null,
    gates_open: ['merge reach/p3-schema + reach/p3-core — Joe word each'],
  })
}

// ============================================================
// P4 — Delta (blocked until P3 + live cook)
// ============================================================
async function runP4() {
  return envelope('p4', {
    _spawned: 0,
    refused: 'P4 requires (a) P3 skill loop landed on master and (b) the Houdini bridge reachable for the live S1 cook (ping first). Check both before re-arming. When armed: prompter (skill-absent / skill-present runs, same prompt), differ (graph-structure delta), crucible. BENCH S1 output is the first number worth tracking (blueprint §9).',
  })
}

// ============================================================
// P5 — Reflex (contract draft may run; BUILD gated)
// ============================================================
async function runP5() {
  if (A.contractDraftOnly === true) {
    const scribe = await agent([
      GROUND,
      '',
      'ROLE: REFLEX-CONTRACT-SCRIBE. Blueprint §5 C1 + §7 reflex-arming.yaml / reflex-failclosed.yaml.',
      'Author .synapse/contracts/reflex-arming.yaml (red tier): arming is a per-act human word; enumerated batches only; chain cannot widen itself; constitutional acts (push/tag/publish/drop) NEVER armable — chain ends AT the governed act, artifact produced, human word still required.',
      'Author .synapse/contracts/reflex-failclosed.yaml (green): injected failure halts chain, real error preserved verbatim, downstream never runs; duplicate event runs the bound act exactly once (blueprint S4/S5).',
      'Territory: worktree reach/p5-contracts. Contracts ONLY. The BUILD requires human ratification of reflex-arming.yaml — a chain that arms itself is the prohibited pattern (blueprint §5 C1, §10).',
      'Post receipt to harness/reach/bus/reach_p5_contracts.json and return it.',
    ].join('\n'), { label: 'reach:p5:contract-scribe', schema: RECEIPT_SCHEMA })
    return envelope('p5', { _spawned: 1, receipts: [scribe], gates_open: ['RATIFY reflex-arming.yaml — Joe word, per act, never relayed'] })
  }
  return envelope('p5', {
    _spawned: 0,
    refused: 'P5 build requires .synapse/contracts/reflex-arming.yaml RATIFIED by Joe (human word). For the unblocked leg, re-dispatch with {phase:"p5", contractDraftOnly:true}.',
  })
}

// ============================================================
// P6 — Board
// ============================================================
async function runP6() {
  return envelope('p6', {
    _spawned: 0,
    refused: 'P6 arms after P3 lands (the skill corpus informs the board\'s error-surface design). When armed, the lane is: board-forge (append-only FILE substrate — a future surface is a READER, never a service; blueprint §5 C3), persistence-verifier (survives host restart), crucible (hunts estimated values — ANY estimate on the surface is BROKEN; unmeasured cells must render UNKNOWN verbatim).',
  })
}

// ============================================================
// P7 — Fence
// ============================================================
async function runP7() {
  return envelope('p7', {
    _spawned: 0,
    refused: 'P7 is double-gated: C4 (outward dispatch) is RED tier — the fence exists to be attacked by CRUX before any green, and that attack + the human gate come first. C5 (portability) requires a local model present; unmeasured grammar ceiling = UNKNOWN, claimed as UNKNOWN (blueprint §5 C5, §7 portability-grammar.yaml).',
  })
}

// ============================================================
// main
// ============================================================
const gateRefusal = capCheck(PHASE)
if (gateRefusal) {
  return {
    refused: gateRefusal,
    phase: PHASE || '(unset)',
    spawned: 0,
    spawned_total_known: SPAWNED_SO_FAR,
    spawn_cap: SPAWN_CAP,
    reserve: RESERVE,
    note: 'Structured refusal, not an error. The orchestrator passes armed:true per run and spawnedSoFar from harness/reach/STATE.json.',
  }
}

switch (PHASE) {
  case 'p0': return envelope('p0', {
    _spawned: 0,
    note: 'GATE-0 is orientation work for the orchestrator (spot-check the three P0 anchors live, cross-check harness/bastion/FINDINGS_INDEX.md). No agents spawn. State lives in harness/reach/STATE.json gate0_open_p0s.',
    gates_open: ['Joe: close TRUTH-P0-1 + TRUTH-P0-2 (fixes), DECIDE the ENG-INJ-GATE-OFF consent posture. Then P2 unblocks.'],
  })
  case 'p1': return runP1()
  case 'p2': return runP2()
  case 'p3': return runP3()
  case 'p4': return runP4()
  case 'p5': return runP5()
  case 'p6': return runP6()
  case 'p7': return runP7()
  default:
    return {
      refused: `unknown or unset phase '${PHASE}' — expected p0..p7`,
      phases_available: Object.keys(BUDGET),
      spawned: 0,
    }
}
