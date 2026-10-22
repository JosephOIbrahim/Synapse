// ATTEST-HARDEN — dynamic refinement loop for the 2026-10-22 version-match review.
// Board: harness/attest/SPEC.md + harness/attest/STATE.json. One wave per run.
//
// Graph engineering: every phase returns nodes (one owner, disjoint files) and typed
// edges (dep | contract | invariant | seam). The spanning order over `dep` edges is
// the only legal implementation order. Two nodes may not own the same file.
//
// Caps: 30 spawned agents per board, 2 held in reserve — same contract as harness/loop.
// A phase that would breach the cap is REFUSED, never silently shrunk.
//
// Model policy: the tier comes from the shipped JEV-ROUTE guard (see args.routing).
// The tier buys a LENS and a dispatch alias. On this host the mechanical and reasoning
// aliases resolve to the session model and the referee alias is unreachable, so a
// referee seat runs the referee lens on the reachable alias and the substitution is
// recorded rather than hidden. No seat is dispatched without a route decision.
//
// No push, no merge, no tags, no VERSION edits — Joe's words, per act.

export const meta = {
  name: 'attest-harden',
  description: 'Refinement loop that turns the 2026-10-22 version-match review into a hardened attestation substrate: map the seams, design single-writer fixes, attack them, forge the survivors on branches, verify the proofs.',
  whenToUse: 'arm via Workflow({scriptPath, args: {date, autonomy, spawnedSoFar, armed:true}}). One wave per run. armed:true is per-run, never banked.',
  phases: [
    { title: 'Map', detail: '5 parallel read-only analysts, one per seed cluster: re-derive the nodes and edges of the current attestation surface with file:line evidence.' },
    { title: 'Seam', detail: 'One analyst builds the unified graph and ranks the seams by blast radius.' },
    { title: 'Design', detail: 'One designer per top-ranked seam: single-writer file map, invariant, proof, back-compat, needs_joe.' },
    { title: 'Crucible', detail: 'One adversarial critic per design: SOUND | SOUND-WITH-NITS | BROKEN | COULD-NOT-ASSESS.' },
    { title: 'Synth', detail: 'One analyst produces the final graph: nodes, owners, typed edges, spanning order, forge-now vs park.' },
    { title: 'Forge', detail: 'One agent per forge-now node, in its own worktree, one atomic commit on its own branch. Never pushes, never merges.' },
    { title: 'Verify', detail: 'One agent per forged node re-runs that node’s acceptance proof against the branch.' },
  ],
}

// ---------------- args ----------------
let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch { A = {} } }
A = A || {}

const DATE = String(A.date || 'undated')
const AUTONOMY = String(A.autonomy || 'green').toLowerCase()
// args may arrive as real JSON values or as stringified scalars (the Workflow
// launcher stringifies on some paths). Accept both, and refuse to guess.
const ARMED = A.armed === true || A.armed === 'true'
const _sf = typeof A.spawnedSoFar === 'string' ? Number(A.spawnedSoFar) : A.spawnedSoFar
const SPAWNED_SO_FAR = Number.isInteger(_sf) && _sf >= 0 ? _sf : 0

const CAP = 30
const RESERVE = 2
const BUDGET = { map: 5, seam: 1, design: 4, crucible: 4, synth: 1, forge: 5, verify: 5 }
const DESIGN_MAX = 4
const FORGE_MAX = 5
const VERIFY_MAX = 5

// ---- JEV-ROUTE table (built by harness/jev/jev_route.py, the shipped guard) -------
// The tier buys a LENS and a dispatch alias. On this host the mechanical and reasoning
// aliases resolve to the session model; the referee alias resolves to a model the host
// cannot reach, so a referee seat is served the referee LENS on the reachable alias and
// the substitution is recorded rather than hidden.
let ROUTING = A.routing
if (typeof ROUTING === 'string') { try { ROUTING = JSON.parse(ROUTING) } catch { ROUTING = null } }
const SEATS = (ROUTING && ROUTING.seats) || null
const TIER_EFFORT = { mechanical: 'low', reasoning: 'medium', referee: 'high' }
const EFFORT_ORDER = { low: 0, medium: 1, high: 2, xhigh: 3, max: 4 }
// The lens is CODE's half of the split: Jev names the tier, code supplies the lens.
// It lives here, in the executor, not in the routing payload.
const LENS_BY_TIER = {
  mechanical: 'MECHANICAL LENS (Jev-routed): reproduce what the brief names. Cite every claim to a file and line. Count and report. Do not design a fix and do not widen scope - if the brief does not name something, report it as unknown.',
  reasoning: 'REASONING LENS (Jev-routed): the structure of the output is not given. Choose between alternatives and say why you chose. State the invariant that can be false, the proof that could fail, and the blast radius you are declaring.',
  referee: 'REFEREE LENS (Jev-routed): trust no builder\'s proof. Author your own check. A wrong result here is what ships, so verify against the code, not against the claim. A gate that cannot fail is a broken gate.',
}
function seatRoute(role) { return (SEATS && SEATS[role]) ? SEATS[role] : null }
function lensFor(role) { const r = seatRoute(role); return r ? (LENS_BY_TIER[r.tier] || '') : '' }
function effortFor(role, floor) {
  const r = seatRoute(role)
  const t = r ? (TIER_EFFORT[r.tier] || 'medium') : 'medium'
  return (EFFORT_ORDER[t] || 1) > (EFFORT_ORDER[floor] || 0) ? t : floor
}
function modelFor(role) {
  const r = seatRoute(role)
  if (!r) return null
  return r.model_reachable ? r.dispatch_alias : null
}

let spent = 0
const spawnLog = []
const faults = []
function budgetCheck(phase, n) {
  if (!ARMED) return 'refused: not armed for this run (armed:true is per-run, Joe word)'
  if (SPAWNED_SO_FAR + spent + n > CAP - RESERVE) {
    return `refused: spawn_cap — ${SPAWNED_SO_FAR} prior + ${spent} this wave + ${n} for ${phase} > ${CAP - RESERVE} available. Report the ledger to Joe and halt; do not retry smaller.`
  }
  return null
}
function charge(phase, n) { spent += n; spawnLog.push({ phase, n }) }

// A seat is dispatched with its routed alias. If that alias dies on a terminal API
// error the seat is re-dispatched once with no override, and BOTH attempts are
// recorded as faults. The tier claim is never silently replaced by a success.
async function seat(prompt, opts) {
  const want = opts.model || null
  const r = await agent(prompt, opts)
  if (r !== null && r !== undefined) return r
  faults.push({ phase: opts.phase || '?', label: opts.label || '?', model: want || 'inherited', outcome: 'null - no report' })
  const o2 = Object.assign({}, opts)
  delete o2.model
  spent += 1
  spawnLog.push({ phase: (opts.phase || '?') + '-fallback', n: 1 })
  const r2 = await agent(prompt, o2)
  if (r2 !== null && r2 !== undefined) {
    faults.push({ phase: opts.phase || '?', label: opts.label || '?', model: 'inherited', outcome: 'recovered on fallback' })
    return r2
  }
  faults.push({ phase: opts.phase || '?', label: opts.label || '?', model: 'inherited', outcome: 'null - no report on fallback' })
  return null
}

// ---------------- ground ----------------
const GROUND = [
  'REPO: C:/Users/User/SYNAPSE (master, VERSION 5.97.6). Houdini 22.0.400. Harness conventions: harness/CLAUDE.md. Board spec: harness/attest/SPEC.md.',
  '',
  'SEED (the 2026-10-22 review — these are CLAIMS TO ATTACK, not facts to copy. Re-derive every one from the tree):',
  '  H1 label-vs-identity: version_check (python/synapse/core/preflight.py:202) compares version STRINGS. The working tree and the Houdini-installed package are different code sets that both declare 5.97.6, so a behavioural divergence would still report green.',
  '  H2 carrier split: payload["client_version"] (read at server/handlers.py:994, health path) and top-level "synapse_version" (core/protocol.py:235-236, read at server/websocket.py:126 and server/hwebserver_adapter.py:109, gate path) are one truth carried by two fields that are never cross-checked.',
  '  H3 absent carrier: mcp/server.py:244 calls preflight_gate.admit(..., tool_name) with NO client_version, so the version check is NOT_APPLICABLE and cannot refuse a mismatched-version bridge on the in-Houdini HTTP endpoint.',
  '  H4 provenance echo: server/doctor.py:732-747 _check_bridge_endpoint reads ~/.synapse/bridge.json and echoes host/port/pid/ts back as status ok without ever verifying the peer. Measured 2026-10-22: two houdini.exe processes both LISTEN on 0.0.0.0:9999; bridge.json named one, the connection was served by the other.',
  '  H5 install drift: the installed tree is written by the installer and never re-checked. installation.json records checks.files_checked=1972 status=PASS at install time and a sha for packages/synapse.json only — no per-file manifest for the tree body, no runtime check.',
  '  H6 tier collapse: only the session model is reachable on this host. Alias haiku and alias opus both resolve to the session model; alias fable and every explicit Anthropic model id fail with "There\'s an issue with the selected model". A receipt saying model=fable is a claim, not a fact. Nothing shipped reads the EFFECTIVE model out of a transcript and fails a tier claim that did not execute.',
  '',
  'HARD RULES:',
  '  - NO git push, NO git merge, NO tags, NO VERSION edits, NO pyproject version sync. You commit on your own branch; Joe merges. Promotion to main is human.',
  '  - NEVER git stash. NEVER export GIT_* env vars. NEVER `git checkout --` or `git reset --hard` against a path you did not write.',
  '  - One atomic commit per node, on the node branch, via `git commit -F <file>` (never a heredoc, never an inline -m).',
  '  - WORKTREE DISCIPLINE: if you are running in a worktree, the absolute path C:/Users/User/SYNAPSE is a SEPARATE checkout of MASTER — absolute repo-root paths hit master\'s tree, not your branch. Operate on RELATIVE paths inside your own cwd. Run `git worktree list` and `git branch --show-current` first and say what they returned.',
  '  - NO HARDCODED USER PATHS in anything you write. No absolute machine paths in source. If a path is needed, derive it from a documented source of truth.',
  '  - READ-ONLY against the live Houdini. No mutating tool, no scene clear, no node create/delete, no parm writes, no renders. The live bridge is reachable read-only at ws://localhost:9999/synapse via the probe scripts in C:/Users/User/Claude outputs/synapse-vf-20261022/ (client_probe.py, raw_ws_health.py, preflight_control.py). Use them for evidence; never mutate through them.',
  '  - EVIDENCE OR SILENCE: every claim carries a file:line, a command plus its real output, or a live tool response. UNKNOWN is an acceptable answer; an estimate is not. Unmeasured is UNKNOWN, never zero. Never fabricate a verdict, a probe output, or a test result.',
  '  - BLUEPRINT IS LAW FOR SCOPE: if your leg drifts outside the node you were given, it STOPS and reports the drift instead of expanding.',
  '  - No hardcoded user paths. One source of version truth (VERSION is canonical). Do not invent a third version source; the fix must consolidate, not multiply.',
].join('\n')

const READONLY = 'You are READ-ONLY. You read, grep, and run read-only probes. You change no file in the repo and you make no commit.'

// ---------------- cluster registry ----------------
// AF2: a MAP seat's cluster identity must be structural, not self-asserted.
// This list is the single source of truth for the cluster enum in MAP_SCHEMA.
// The CLUSTERS registry further down carries the briefs; the assertion after it
// fails the wave loudly if the two ever name different clusters, rather than
// letting a seat be briefed on a cluster the schema does not know.
const CLUSTER_IDS = ['C1-carriers', 'C2-identity', 'C3-provenance', 'C4-install', 'C5-harness']

// ---------------- schemas ----------------
const MAP_SCHEMA = {
  type: 'object',
  properties: {
    cluster: { type: 'string', enum: CLUSTER_IDS },
    seed_confirmed: { type: 'string', enum: ['CONFIRMED', 'REFUTED', 'PARTIAL', 'UNKNOWN'] },
    seed_evidence: { type: 'array', items: { type: 'string' } },
    carriers: {
      type: 'array',
      description: 'every place a version / identity value enters, is stored, is compared or is reported',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          written_at: { type: 'string' },
          read_at: { type: 'array', items: { type: 'string' } },
          authority: { type: 'string', enum: ['authentic', 'self-asserted', 'echoed', 'absent'] },
          evidence: { type: 'string' },
        },
        required: ['name', 'written_at', 'read_at', 'authority', 'evidence'],
      },
    },
    identity_primitives: {
      type: 'array',
      description: 'identity values that already exist in the codebase and could carry content identity rather than a label',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          defined_at: { type: 'string' },
          value_shape: { type: 'string' },
          content_derived: { type: 'boolean' },
          reachable_from_both_sides: { type: 'string', enum: ['yes', 'no', 'partly', 'unknown'] },
          evidence: { type: 'string' },
        },
        required: ['name', 'defined_at', 'value_shape', 'content_derived', 'reachable_from_both_sides', 'evidence'],
      },
    },
    nodes: {
      type: 'array',
      description: 'candidate work items, each with a single owner and a disjoint file set',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          title: { type: 'string' },
          files_owned: { type: 'array', items: { type: 'string' } },
          problem: { type: 'string' },
          evidence: { type: 'string' },
        },
        required: ['id', 'title', 'files_owned', 'problem', 'evidence'],
      },
    },
    edges: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          from: { type: 'string' },
          to: { type: 'string' },
          type: { type: 'string', enum: ['dep', 'contract', 'invariant', 'seam'] },
          why: { type: 'string' },
        },
        required: ['from', 'to', 'type', 'why'],
      },
    },
    unknowns: { type: 'array', items: { type: 'string' } },
  },
  required: ['cluster', 'seed_confirmed', 'seed_evidence', 'carriers', 'identity_primitives', 'nodes', 'edges', 'unknowns'],
}

// AF2: the shared schema names the five known ids; each seat is handed the SAME
// schema with its own id pinned to a single allowed value. The tool-call layer
// rejects any other value and the seat retries, so a seat cannot report a cluster
// it was not given. The enum makes the label well-formed; the pin makes it
// CHECKABLE. A seat that answers "C2-identity" when it was given "C1-carriers"
// now fails validation instead of passing a claim the board cannot verify.
const mapSchemaFor = (clusterId) => ({
  ...MAP_SCHEMA,
  properties: {
    ...MAP_SCHEMA.properties,
    cluster: { type: 'string', enum: [clusterId] },
  },
})

const SEAM_SCHEMA = {
  type: 'object',
  properties: {
    graph_summary: { type: 'string' },
    seams: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          title: { type: 'string' },
          why_seam: { type: 'string' },
          carriers_in_conflict: { type: 'array', items: { type: 'string' } },
          files: { type: 'array', items: { type: 'string' } },
          blast_radius: { type: 'number' },
          blast_radius_reason: { type: 'string' },
          fixable_without_joe: { type: 'boolean' },
        },
        required: ['id', 'title', 'why_seam', 'carriers_in_conflict', 'files', 'blast_radius', 'blast_radius_reason', 'fixable_without_joe'],
      },
    },
    global_invariants: { type: 'array', items: { type: 'string' } },
    unknowns: { type: 'array', items: { type: 'string' } },
  },
  required: ['graph_summary', 'seams', 'global_invariants', 'unknowns'],
}

const DESIGN_SCHEMA = {
  type: 'object',
  properties: {
    node_id: { type: 'string' },
    title: { type: 'string' },
    problem: { type: 'string' },
    proposal: { type: 'string' },
    files_owned: { type: 'array', items: { type: 'string' } },
    edges: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          to: { type: 'string' },
          type: { type: 'string', enum: ['dep', 'contract', 'invariant', 'seam'] },
          why: { type: 'string' },
        },
        required: ['to', 'type', 'why'],
      },
    },
    invariant: { type: 'string' },
    proof: { type: 'string' },
    back_compat: { type: 'string' },
    blast_radius: { type: 'string' },
    risk: { type: 'string' },
    needs_joe: { type: 'array', items: { type: 'string' } },
  },
  required: ['node_id', 'title', 'problem', 'proposal', 'files_owned', 'edges', 'invariant', 'proof', 'back_compat', 'blast_radius', 'risk', 'needs_joe'],
}

const CRUCIBLE_SCHEMA = {
  type: 'object',
  properties: {
    node_id: { type: 'string' },
    verdict: { type: 'string', enum: ['SOUND', 'SOUND-WITH-NITS', 'BROKEN', 'COULD-NOT-ASSESS'] },
    attacks: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          target: { type: 'string' },
          verdict: { type: 'string', enum: ['SOUND', 'SOUND-WITH-NITS', 'BROKEN', 'COULD-NOT-ASSESS'] },
          evidence: { type: 'string' },
          fix: { type: 'string' },
        },
        required: ['target', 'verdict', 'evidence', 'fix'],
      },
    },
    summary: { type: 'string' },
  },
  required: ['node_id', 'verdict', 'attacks', 'summary'],
}

const SYNTH_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['GRAPH-CLOSED', 'GRAPH-PARTIAL', 'GRAPH-EMPTY'] },
    graph_summary: { type: 'string' },
    nodes: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          title: { type: 'string' },
          owner_files: { type: 'array', items: { type: 'string' } },
          edges: { type: 'array', items: { type: 'string' } },
          depends_on: { type: 'array', items: { type: 'string' } },
          crucible_verdict: { type: 'string' },
          acceptance_proof: { type: 'string' },
          forge_now: { type: 'boolean' },
          needs_joe: { type: 'array', items: { type: 'string' } },
        },
        required: ['id', 'title', 'owner_files', 'edges', 'depends_on', 'crucible_verdict', 'acceptance_proof', 'forge_now', 'needs_joe'],
      },
    },
    spanning_order: { type: 'array', items: { type: 'string' } },
    parked: { type: 'array', items: { type: 'string' } },
    file_ownership: { type: 'array', items: { type: 'string' } },
    unproven: { type: 'array', items: { type: 'string' } },
    needs_joe: { type: 'array', items: { type: 'string' } },
  },
  required: ['verdict', 'graph_summary', 'nodes', 'spanning_order', 'parked', 'file_ownership', 'unproven', 'needs_joe'],
}

const FORGE_SCHEMA = {
  type: 'object',
  properties: {
    node_id: { type: 'string' },
    status: { type: 'string', enum: ['IMPLEMENTED', 'BLOCKED', 'DRIFT', 'NO-OP'] },
    branch: { type: 'string' },
    commit_sha: { type: 'string' },
    files_changed: { type: 'array', items: { type: 'string' } },
    proof_output: { type: 'string' },
    notes: { type: 'string' },
  },
  required: ['node_id', 'status', 'branch', 'commit_sha', 'files_changed', 'proof_output', 'notes'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    node_id: { type: 'string' },
    verdict: { type: 'string', enum: ['PASS', 'FAIL', 'UNKNOWN'] },
    evidence: { type: 'array', items: { type: 'string' } },
    commit_sha: { type: 'string' },
    notes: { type: 'string' },
  },
  required: ['node_id', 'verdict', 'evidence', 'commit_sha', 'notes'],
}

// ---------------- phase helpers ----------------
function brief(reports) {
  return reports.filter(Boolean).map(r => JSON.stringify(r)).join('\n\n')
}
function seamBlock(seam) {
  return [
    'SEAM ' + seam.id + ' — ' + seam.title,
    'why it is a seam: ' + seam.why_seam,
    'carriers in conflict: ' + JSON.stringify(seam.carriers_in_conflict),
    'files in play: ' + JSON.stringify(seam.files),
    'blast radius: ' + seam.blast_radius + ' — ' + seam.blast_radius_reason,
    'fixable without a Joe decision: ' + seam.fixable_without_joe,
  ].join('\n')
}
const FORGE_RULES = [
  'You are in a FRESH WORKTREE. Confirm it first: run `git worktree list` and `git branch --show-current` and put the real output in notes.',
  'Do NOT touch any absolute path outside your own cwd. C:/Users/User/SYNAPSE is a separate checkout of master — writing there edits master, not your branch.',
  'Your file set is FIXED and given to you. If the change requires a file outside it, do NOT expand: report status BLOCKED naming the file you needed.',
  'Two nodes may not own the same file. If another node in this wave owns a file you need, report BLOCKED naming it.',
  'Commit: ONE atomic commit on your own branch, via `git commit -F <file>` (write the message to a file first; never a heredoc, never inline -m). Message form: `fix(attest): <node_id> <what>`.',
  'NEVER push, NEVER merge, NEVER tag, NEVER stash, NEVER edit VERSION.',
  'You must ALSO make the proof real: the acceptance proof must be runnable, and running it must be part of your work. If it needs a test file, that test file is inside your file set — say so.',
].join('\n')

// ============================================================
// MAP — 5 read-only analysts, one per seed cluster
// ============================================================
phase('Map')
const CLUSTERS = [
  {
    id: 'C1-carriers',
    brief: 'CLUSTER C1 — the version carrier graph. Find EVERY place a version or identity value enters, is written, is stored, is compared, or is reported across the live tree: the stdio relay (mcp_server.py), the wire protocol (python/synapse/core/protocol.py), the WebSocket server (python/synapse/server/websocket.py), the HTTP adapter (python/synapse/server/hwebserver_adapter.py), the in-Houdini HTTP MCP endpoint (python/synapse/mcp/server.py), the health handler (python/synapse/server/handlers.py), the preflight gate (python/synapse/server/preflight_gate.py) and the core check (python/synapse/core/preflight.py). For each carrier state: where it is WRITTEN, where it is READ, and whether its authority is authentic (derived from a live in-process read), self-asserted (supplied by the caller), echoed (copied out of a stamp file without verification), or absent. Then list the divergences between carriers.',
  },
  {
    id: 'C2-identity',
    brief: 'CLUSTER C2 — identity vs label. Inventory every identity primitive that ALREADY exists in the codebase and could carry CONTENT identity rather than a version label: build ids, source revisions, content hashes, manifest shas, install stamps, tree digests, the VERSION file, pyproject metadata, agent.usd provenance, and anything in python/synapse/memory/agent_state.py or the installer. For each: where it is defined (file:line), what shape its value takes, whether it is content-derived (changes when the bytes change) or merely a declared label, and whether BOTH sides of a live bridge call (the stdio relay in the working tree, and the Houdini process running the installed package) can compute or read it. The question this cluster answers: can the two sides compare something stronger than a version string, and at what cost?',
  },
  {
    id: 'C3-provenance',
    brief: 'CLUSTER C3 — peer and session provenance. Map how SYNAPSE records and reports which process it is talking to and which code set it is running. Start at ~/.synapse/ (bridge.json, auth.key, install_stamp.json, any other store), the server startup path that WRITES bridge.json, the doctor command (python/synapse/server/doctor.py) and every check it performs, the session/hop model, and anything that consumes bridge.json. For each recorded fact: who wrote it, when, and whether any consumer VERIFIES it against the live peer (a real connection, a real pid ownership check, a real handshake) or merely echoes it. Measured on 2026-10-22: two houdini.exe processes both LISTEN on 0.0.0.0:9999; bridge.json named pid 52896; the connection was served by pid 32832. Explain the mechanism that allowed a false peer to be recorded, and what a verification would have to check to catch it.',
  },
  {
    id: 'C4-install',
    brief: 'CLUSTER C4 — installed-tree integrity. Map the install and its verification surface: the installer scripts, installation.json (its schema, what `checks.files_checked` and `checks.status` actually assert, what `registrations` holds, what `stamp` holds), the SYNAPSE_ROOT / PYTHONPATH layout the installer writes into the Houdini packages dir, and any runtime or on-demand check that the installed tree still matches what was installed. The measured fact to explain: an installed file (houdini/python_panels/synapse_panel.pypanel) had an mtime ~21 hours AFTER the install completed, and no shipped check noticed. Then answer: what is the cheapest sound way to detect post-install drift of the installed tree, and where would that check have to live to be honest (installer-time only, server start, or on demand)?',
  },
  {
    id: 'C5-harness',
    brief: 'CLUSTER C5 — the harness tier-collapse gap. Map how the repo records which model an agent or workflow seat ACTUALLY ran on. Look at harness/jev/ (jev_client.py, jev_route.py, questions.json), harness/rails_exec.json and any other rails files, the workflow scripts under .claude/workflows/, and any code that reads a workflow agent meta.json, a transcript, or a ledger. The measured fact to explain: on this host alias haiku and alias opus both resolve to the session model while alias fable and explicit Anthropic ids fail outright, so a receipt that says model=fable can be a request rather than a fact. Then answer: where could a shipped guard read the EFFECTIVE model (a transcript message.model / modelId) and fail or annotate a tier claim that did not execute — and does anything there already do this?',
  },
]

// The registry and the schema enum must name the same five clusters. Fail the wave
// loudly here rather than dispatching a seat whose brief names a cluster the
// schema would refuse.
const _registryIds = CLUSTERS.map(c => c.id)
const _registryMismatch = CLUSTER_IDS
  .filter(i => !_registryIds.includes(i))
  .concat(_registryIds.filter(i => !CLUSTER_IDS.includes(i)))
if (_registryMismatch.length) {
  throw new Error('CLUSTER_IDS and the CLUSTERS registry disagree: ' + _registryMismatch.join(', '))
}

const mapBudget = budgetCheck('map', BUDGET.map)
if (mapBudget) return { refused: mapBudget, spawned: 0, spent_so_far: SPAWNED_SO_FAR }
charge('map', BUDGET.map)

const mapReports = await parallel(CLUSTERS.map(c => () => seat([
  GROUND,
  '',
  READONLY,
  '',
  lensFor('map'),
  '',
  'ROLE: MAP analyst — ' + c.id + '.',
  '',
  'YOUR ASSIGNED CLUSTER ID IS: ' + c.id,
  'The "cluster" field of your report MUST be exactly that string, character for character. Do not restate a cluster name from a brief, from a document you read, or from your own impression of the subject - the assigned id is the only accepted value and the schema refuses anything else.',
  'Name every node id you emit as "' + c.id + '-N<k>" - for example "' + c.id + '-N1", "' + c.id + '-N2". The prefix is the assigned id above, never a cluster number you read somewhere else.',
  c.brief,
  '',
  'METHOD:',
  '  1. Grep and Read the live tree. Cite file:line for every structural claim.',
  '  2. For anything you claim about runtime behaviour, RUN the read-only probe and paste the real output. A probe you did not run is UNKNOWN, not a finding.',
  '  3. Do NOT trust the SEED text. It may be wrong, stale, or overstated. Verify it, then set seed_confirmed to CONFIRMED / REFUTED / PARTIAL / UNKNOWN with the evidence that decided it.',
  '  4. Cap yourself at about 30 file reads. If you are still reading at 30, report what you have and mark the rest UNKNOWN.',
  '',
  'Return: the carriers, the identity primitives, the candidate nodes (each with its owned file set), the typed edges between them, and your explicit unknowns. Nodes are work items — a node names a problem and the files that would fix it, with a single owner. Set "cluster" to "' + c.id + '" and prefix every node id with "' + c.id + '-".',
].join('\n'), { label: 'attest:map:' + c.id, phase: 'Map', schema: mapSchemaFor(c.id), effort: effortFor('map', 'low'), model: modelFor('map') })))

const mapOk = mapReports.filter(Boolean)
log('Map complete: ' + mapOk.length + '/' + CLUSTERS.length + ' analysts returned')

// ============================================================
// SEAM — unify the graph, rank the seams
// ============================================================
phase('Seam')
const seamBudget = budgetCheck('seam', BUDGET.seam)
if (seamBudget) return { refused: seamBudget, spawned: spent, map_reports: mapOk }
charge('seam', BUDGET.seam)

const seam = await seat([
  GROUND,
  '',
  READONLY,
  '',
  lensFor('seam'),
  '',
  'ROLE: SEAM analyst. Five MAP analysts just mapped the attestation surface. You are the only node that sees all five. Build the UNIFIED graph and find the SEAMS.',
  '',
  'A SEAM is a place where ONE truth is carried by TWO OR MORE divergent carriers, or where a truth has NO carrier at all. A seam is a candidate for consolidation: the fix is to make the carriers agree or to delete one, not to add a third.',
  '',
  'MAP REPORTS (raw JSON, one per cluster):',
  brief(mapOk),
  '',
  'METHOD:',
  '  1. Reconcile the five reports. Where they disagree, the tree wins — go read the file and settle it. Say which side you settled on.',
  '  2. Name the seams. For each: the carriers in conflict, the files that would be touched, and a blast radius (a number plus a one-line reason). A seam that touches a hot path (every MCP call) ranks above one that touches a diagnostic path.',
  '  3. Mark fixable_without_joe: a seam whose fix is a pure engineering consolidation is true; a seam whose fix needs a PRODUCT DECISION (what the correct behaviour should be, what an operator should see) is false.',
  '  4. Cap yourself at about 25 file reads.',
  '',
  'Return the ranked seams plus the global invariants that any correct fix must preserve.',
].join('\n'), { label: 'attest:seam', phase: 'Seam', schema: SEAM_SCHEMA, effort: effortFor('seam', 'medium'), model: modelFor('seam') })

if (!seam) {
  return {
    verdict: 'GRAPH-EMPTY',
    reason: 'the SEAM analyst returned nothing — the graph could not be built',
    spawned: spent,
    map_reports: mapOk,
    faults: [{ phase: 'seam', outcome: 'null - no report' }],
  }
}

const ranked = (seam.seams || []).slice().sort((a, b) => (b.blast_radius || 0) - (a.blast_radius || 0))
const designTargets = ranked.filter(s => s.fixable_without_joe).slice(0, DESIGN_MAX)
log('Seam ranked ' + ranked.length + ' seams; designing ' + designTargets.length)

// ============================================================
// DESIGN + CRUCIBLE — one designer and one critic per seam
// ============================================================
phase('Design')
const designBudget = budgetCheck('design', BUDGET.design)
if (designBudget) return { refused: designBudget, spawned: spent, seam, map_reports: mapOk }
charge('design', BUDGET.design)

const designs = await parallel(designTargets.map(s => () => seat([
  GROUND,
  '',
  lensFor('design'),
  '',
  'ROLE: DESIGNER for one node.',
  '',
  seamBlock(s),
  '',
  'GLOBAL INVARIANTS any correct fix must preserve (from the SEAM analyst):',
  JSON.stringify(seam.global_invariants || []),
  '',
  'MAP REPORTS (raw JSON):',
  brief(mapOk),
  '',
  'METHOD:',
  '  1. Design the change. It must CONSOLIDATE — one canonical carrier, one authority, one comparison — not add a parallel path.',
  '  2. Declare files_owned: the exact files this node writes. Every other node must have a DISJOINT set. A node that needs a file another node owns is a design error — find a different split and say why.',
  '  3. State the invariant as a sentence that can be false (a check that can never fail proves nothing).',
  '  4. State the acceptance proof as a command that can be run, with its expected output. If the proof needs a new test file, name it — it belongs in files_owned.',
  '  5. back_compat: what happens to an old client, an old relay, a caller that sends nothing. Name the failure mode you are accepting.',
  '  6. needs_joe: any item that needs a product decision or a human word. Empty array if the design is pure engineering. Do NOT hide a decision behind a design.',
  '  7. Do NOT write code. Do NOT edit files. You are producing a design, not a patch.',
  '',
  'Read the files you need. Do not guess a signature — if you are not certain a symbol exists, read it and cite it.',
].join('\n'), { label: 'attest:design:' + s.id, phase: 'Design', schema: DESIGN_SCHEMA, effort: effortFor('design', 'medium'), model: modelFor('design') })))

const designOk = designs.filter(Boolean)
log('Design complete: ' + designOk.length + '/' + designTargets.length)

phase('Crucible')
const cruBudget = budgetCheck('crucible', BUDGET.crucible)
if (cruBudget) return { refused: cruBudget, spawned: spent, seam, designs: designOk }
charge('crucible', BUDGET.crucible)

const critiques = await parallel(designOk.map(d => () => seat([
  GROUND,
  '',
  lensFor('crucible'),
  '',
  'ROLE: CRUCIBLE. You did not design this and you are motivated to break it. Fair in method, hostile in intent.',
  '',
  'DESIGN UNDER ATTACK:',
  JSON.stringify(d),
  '',
  'SEAM CONTEXT:',
  JSON.stringify(seam.seams || []),
  '',
  'ATTACKS TO ATTEMPT (at least these five):',
  '  1. DOES THE FIX CONSOLIDATE? If it adds a third carrier, a third version source, or a second place that compares versions, it is BROKEN — the whole point is one truth, one carrier.',
  '  2. IS THE PROOF A PROOF? Try the acceptance proof. If it cannot fail, or if you cannot run it, or if it asserts something the code does not actually do, that is BROKEN.',
  '  3. FILE OWNERSHIP: does files_owned overlap another node\'s set? Does the design need a file it does not own? Check against every other design you can see in the list you were given — and if you cannot see the others, say so rather than assuming.',
  '  4. BACK-COMPAT: what breaks for a caller that sends no version, for an old relay, for the in-Houdini HTTP endpoint, for the raw WebSocket path? Name the regression.',
  '  5. HONESTY: does the design claim a guarantee the code cannot deliver? Does it restate the SEED as fact? Does it introduce a hardcoded path, a magic constant, or a second source of version truth?',
  '  6. REALITY: does the design depend on something that does not exist on this host (a substrate, a model, a file)? Grep before you rely on it.',
  '',
  'You may READ and you may RUN read-only probes and read-only tests. You may NOT edit files and you may NOT commit. For each attack give the counter-evidence as file:line or a command plus its real output. If BROKEN, give the honest fix. If you cannot assess, say COULD-NOT-ASSESS — that is an acceptable answer, a guess is not.',
].join('\n'), { label: 'attest:crucible:' + d.node_id, phase: 'Crucible', schema: CRUCIBLE_SCHEMA, effort: effortFor('crucible', 'high'), model: modelFor('crucible') })))

const critiqueOk = critiques.filter(Boolean)
log('Crucible complete: ' + critiqueOk.length + '/' + designOk.length + ' attacked')

// ============================================================
// SYNTH — the final graph
// ============================================================
phase('Synth')
const synthBudget = budgetCheck('synth', BUDGET.synth)
if (synthBudget) return { refused: synthBudget, spawned: spent, seam, designs: designOk, critiques: critiqueOk }
charge('synth', BUDGET.synth)

const synth = await seat([
  GROUND,
  '',
  lensFor('synth'),
  '',
  'ROLE: SYNTH. You are the only node that sees every seat. Produce the FINAL GRAPH.',
  '',
  'SEAM REPORT:', JSON.stringify(seam),
  '',
  'DESIGNS:', brief(designOk),
  '',
  'CRUCIBLE VERDICTS:', brief(critiqueOk),
  '',
  'RULES:',
  '  - A node whose crucible verdict is BROKEN does NOT become a forge-now node. Park it and say what would have to change.',
  '  - A node whose design carries a non-empty needs_joe does NOT become a forge-now node. It is presented to Joe verbatim and parked.',
  '  - spanning_order is the topological order over the `dep` edges. A node may not be listed before a node it depends on.',
  '  - file_ownership: one line per file, naming its single owning node. If two nodes claim one file, fix the split — do not publish the collision.',
  '  - acceptance_proof per node: the command that proves it and the expected output.',
  '  - unproven: what this graph does NOT establish. Be specific. A graph that claims more than it measured is worse than a smaller one.',
  '',
  'Pick at most ' + FORGE_MAX + ' nodes for forge_now, in dependency order — a node whose dep is parked cannot be forged yet.',
].join('\n'), { label: 'attest:synth', phase: 'Synth', schema: SYNTH_SCHEMA, effort: effortFor('synth', 'high'), model: modelFor('synth') })

if (!synth) {
  return {
    verdict: 'GRAPH-EMPTY',
    reason: 'the SYNTH analyst returned nothing',
    spawned: spent,
    seam, designs: designOk, critiques: critiqueOk,
    faults: [{ phase: 'synth', outcome: 'null - no report' }],
  }
}

// ============================================================
// FORGE — one agent per forge-now node, own worktree, own branch
// ============================================================
phase('Forge')
const forgeNow = (synth.nodes || []).filter(n => n.forge_now).slice(0, FORGE_MAX)
const forgeBudget = budgetCheck('forge', forgeNow.length)
if (forgeBudget) {
  log('Forge refused: ' + forgeBudget)
  return {
    verdict: synth.verdict, synth, seam, designs: designOk, critiques: critiqueOk,
    spawned: spent, forge_refused: forgeBudget,
    file_ownership: synth.file_ownership, spanning_order: synth.spanning_order,
    parked: synth.parked, unproven: synth.unproven, needs_joe: synth.needs_joe,
  }
}
if (forgeNow.length) charge('forge', forgeNow.length)

const forgeResults = forgeNow.length ? await parallel(forgeNow.map(n => () => seat([
  GROUND,
  '',
  lensFor('forge'),
  '',
  'ROLE: FORGE. You implement ONE node. You are the single writer of the files in your set.',
  '',
  'NODE TO IMPLEMENT:',
  JSON.stringify(n),
  '',
  'THE FILE OWNERSHIP MAP FOR THIS WAVE (one owner per file):',
  JSON.stringify(synth.file_ownership || []),
  '',
  'CRUCIBLE VERDICT ON YOUR NODE:',
  JSON.stringify((critiqueOk.find(c => c.node_id === n.id)) || 'no critique found — treat as unverified'),
  '',
  'THE CRUCIBLE\'S FIXES YOU MUST HONOUR: ' + JSON.stringify(((critiqueOk.find(c => c.node_id === n.id) || {}).attacks || []).filter(a => a.fix).map(a => a.fix)),
  '',
  FORGE_RULES,
  '',
  'METHOD:',
  '  1. Read your node\'s files and the files it depends on. Verify every signature you touch actually exists — grep it, cite it.',
  '  2. Implement the node. Minimal, surgical, consistent with the surrounding code style. No drive-by refactors, no renames outside your set.',
  '  3. Add or update the test that the acceptance proof names, if the proof needs one. It is inside your file set.',
  '  4. RUN the acceptance proof. Paste the real output into proof_output. If it fails, you have not finished: fix it, or report status BLOCKED with the real failure output. Never report a proof you did not run.',
  '  5. Run the existing test suite for the area you touched (python -m pytest <paths> -q) and paste the real tail. A red suite you caused is a BLOCKED.',
  '  6. One atomic commit. Report the real branch name and the real commit sha.',
  '',
  'NEVER push. NEVER merge. NEVER tag. NEVER stash. NEVER edit VERSION.',
].join('\n'), { label: 'attest:forge:' + n.id, phase: 'Forge', schema: FORGE_SCHEMA, effort: effortFor('forge', 'medium'), model: modelFor('forge'), isolation: 'worktree' }))) : []

const forgeOk = forgeResults.filter(Boolean)
log('Forge complete: ' + forgeOk.length + '/' + forgeNow.length + ' implemented')

// ============================================================
// VERIFY — re-run each node's proof against its branch
// ============================================================
phase('Verify')
const implemented = forgeOk.filter(f => f.status === 'IMPLEMENTED')
const verifyTargets = implemented.slice(0, VERIFY_MAX)
const verifyBudget = budgetCheck('verify', verifyTargets.length)
if (verifyBudget) {
  log('Verify refused: ' + verifyBudget)
  return {
    verdict: synth.verdict, synth, seam, designs: designOk, critiques: critiqueOk,
    forge: forgeOk, spawned: spent, verify_refused: verifyBudget,
    file_ownership: synth.file_ownership, spanning_order: synth.spanning_order,
    parked: synth.parked, unproven: synth.unproven, needs_joe: synth.needs_joe,
  }
}
if (verifyTargets.length) charge('verify', verifyTargets.length)

const verifyResults = verifyTargets.length ? await parallel(verifyTargets.map(f => () => seat([
  GROUND,
  '',
  lensFor('verify'),
  '',
  'ROLE: VERIFY. You did not forge this. You check it.',
  '',
  'FORGED NODE:',
  JSON.stringify(f),
  '',
  'THE NODE\'S ACCEPTANCE PROOF:',
  (synth.nodes || []).find(n => n.id === f.node_id) ? ((synth.nodes || []).find(n => n.id === f.node_id)).acceptance_proof : 'not stated',
  '',
  'METHOD:',
  '  1. Locate the branch and its commit. Use `git worktree list`, `git branch --all`, and `git show --stat <sha>`. Do NOT check out anything in master.',
  '  2. Re-run the acceptance proof YOURSELF, from scratch, in the branch\'s own worktree. Paste the real command and the real output.',
  '  3. Read the diff (`git show <sha>`). Look for: a test that asserts the old (wrong) behaviour, a change to a file outside the node\'s owned set, a hardcoded machine path, a swallowed exception, a second source of version truth, a widened blast radius nobody declared.',
  '  4. If the proof cannot be run, say UNKNOWN. Do not pass on the forger\'s word.',
  '',
  'You may READ, you may RUN read-only commands and tests. You may NOT edit files, may NOT commit, and may NOT checkout, reset, clean or stash anything.',
].join('\n'), { label: 'attest:verify:' + f.node_id, phase: 'Verify', schema: VERIFY_SCHEMA, effort: effortFor('verify', 'medium'), model: modelFor('verify') }))) : []

const verifyOk = verifyResults.filter(Boolean)
log('Verify complete: ' + verifyOk.length + '/' + verifyTargets.length)

// ============================================================
// return
// ============================================================
return {
  date: DATE,
  autonomy: AUTONOMY,
  verdict: synth.verdict,
  graph_summary: synth.graph_summary,
  nodes: synth.nodes,
  spanning_order: synth.spanning_order,
  file_ownership: synth.file_ownership,
  parked: synth.parked,
  unproven: synth.unproven,
  needs_joe: synth.needs_joe,
  seam: seam,
  designs: designOk,
  critiques: critiqueOk,
  map_reports: mapOk,
  forge: forgeOk,
  verify: verifyOk,
  spawn: {
    prior: SPAWNED_SO_FAR,
    this_wave: spent,
    cap: CAP,
    reserve: RESERVE,
    by_phase: spawnLog,
  },
  faults: faults,
  routing: SEATS ? {
    source: 'JEV-ROUTE via harness/jev/jev_route.py (shipped guard), model ' + (ROUTING.jev_model_requested || 'unknown'),
    ledger: ROUTING.ledger_dir || null,
    note: 'The tier buys a LENS and a dispatch alias. On this host the mechanical and reasoning aliases resolve to the session model; the referee alias resolves to a model the host cannot reach, so referee seats run the referee lens on the reachable alias and the substitution is recorded in routing.*.model_served_by.',
    seats: Object.keys(SEATS).map(k => ({
      role: k, tier: SEATS[k].tier, reason: SEATS[k].reason,
      jev_confidence: SEATS[k].jev ? SEATS[k].jev.confidence : null,
      jev_novelty: SEATS[k].jev ? SEATS[k].jev.novelty : null,
      jev_blast_radius: SEATS[k].jev ? SEATS[k].jev.blast_radius : null,
      rails_model: SEATS[k].rails_model, dispatch_alias: SEATS[k].dispatch_alias,
      model_reachable: SEATS[k].model_reachable, model_served_by: SEATS[k].model_served_by,
      effort: SEATS[k].effort,
    })),
  } : 'NO ROUTING TABLE — this wave was dispatched without a Jev route decision',
  gates: [
    'gate_blueprint_ratification: harness/attest/SPEC.md is DRAFT until Joe\'s word',
    'gate_merges: every forge branch needs Joe\'s word to merge — no agent merges',
    'gate_product_decisions: any node with a non-empty needs_joe is parked and presented verbatim',
  ],
}
