export const meta = {
  name: 'freeze-forensics',
  description: 'FREEZE FORENSICS RELAY — evidence-ranked diagnosis of why SYNAPSE freezes Houdini node interaction when a prompt is sent. Historian reconciles the 4-class freeze taxonomy, cartographers map the prompt-path seams, hypotheses are seeded + generated, per-hypothesis probes (static + live telemetry) verdict, crucible attacks survivors, verdict doc + remediation ticket written. Read-only: repairs nothing.',
  whenToUse: 'Dispatched by freeze-forensics-orchestrator after arming. args: {date: "YYYY-MM-DD"}',
  phases: [
    { title: 'Historian', detail: 'known freeze classes + closure status' },
    { title: 'Seam-Map', detail: 'three cartographers, prompt-path seams' },
    { title: 'Hypothesize', detail: 'seed + seam-derived candidates' },
    { title: 'Probe', detail: 'per-hypothesis evidence legs' },
    { title: 'Attack', detail: 'crucible refutes survivors' },
    { title: 'Verdict', detail: 'doc + remediation ticket' },
  ],
}

const A = typeof args === 'string' ? JSON.parse(args) : (args || {})
const DATE = A.date || '2026-07-31'
const ROOT = 'C:\\Users\\User\\SYNAPSE'

const HISTORY_SCHEMA = {
  type: 'object',
  properties: {
    classes: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          mechanism: { type: 'string' },
          closure_status: { type: 'string', description: 'CLOSED-at-<sha> | MITIGATED-only | OPEN' },
          applies_to_prompt_path: { type: 'boolean' },
        },
        required: ['name', 'closure_status', 'applies_to_prompt_path'],
      },
    },
    regression_window: { type: 'string', description: 'commits since the symptom could have appeared, with the most-likely-suspect commit named' },
  },
  required: ['classes', 'regression_window'],
}

phase('Historian')
const history = await agent(
  `Build the freeze taxonomy for the SYNAPSE prompt-send freeze. Evidence sources (read them, cite file:line):\n` +
  `1. CHANGELOG.md v5.33.0 / v5.40.1 / v5.41.0 entries (the closed classes: render grip, marshal self-deadlock, ` +
  `chat-time Qt fallback).\n` +
  `2. python/synapse/server/freeze_chain.py + marshal_guard.py (the D3 escalation surface: beat→5s detect→30s ` +
  `sustained→breaker force_open + emergency halt).\n` +
  `3. python/synapse/panel/claude_worker.py (~:357), tool_executor.py (~:50,:344,:422), bridge_adapter.py ` +
  `(~:229-299), synapse_panel.py (:375-394 freeze heartbeat), host/main_thread_executor.py (:62,:221).\n` +
  `4. git log 293484c..HEAD — TODAY's commits (P3.1 ping gate 340db86, P3.3 recv loop 9c9bc8e): name the ` +
  `most-likely-suspect commit for a NEW symptom.\n` +
  `For each class: mechanism, whether CLOSED-at-sha / MITIGATED / OPEN, and whether it can fire on the ` +
  `prompt-send path (chat typed → LLM turn → tool loop). applies_to_prompt_path must be honest — a render-only ` +
  `class is false.`,
  { label: 'historian', phase: 'Historian', schema: HISTORY_SCHEMA }
)

phase('Seam-Map')
const SEAM_SCHEMA = {
  type: 'object',
  properties: {
    seam: { type: 'string' },
    prompt_path_trace: { type: 'array', items: { type: 'string' }, description: 'the exact call chain on prompt-send, file:line per hop' },
    main_thread_work: { type: 'array', items: { type: 'string' }, description: 'any hop that can run ON Houdini main thread or block it, with duration bound or "unbounded"' },
    live_telemetry: { type: 'array', items: { type: 'string' }, description: 'log/metric surfaces that would show this seam firing' },
  },
  required: ['seam', 'prompt_path_trace', 'main_thread_work', 'live_telemetry'],
}
const SEAMS = [
  { id: 'panel-prompt', brief: `Panel prompt path: python/synapse/panel/chat_panel.py (_send_message :869, _gather_context_if_stale :850-883+973, ctx wiring), claude_worker.py, ws_bridge.py (gather_context_off_main). Trace from the Send click to the provider call. The critical question: on a STALE-context send, does context gather run inline on the Qt/main thread despite the v5.40.1 off-main fix (check whether the fix covered this call site or only the 10s poll + tool fallback)?` },
  { id: 'server-marshal', brief: `Server dispatch + marshal + escalation: server/main_thread.py Fast paths, freeze_chain.py escalation actions, marshal_guard.py, server/handlers* on tool dispatch. Question: does anything on a plain prompt turn (not a tool call) land on the marshal? And if the freeze_chain ESCALATION fires, what exactly wedges afterward (breaker open semantics)?` },
  { id: 'transport-provider', brief: `Transport + provider: panel/providers/ (Gemini/Anthropic adapters), websocket read loop (server/websocket.py :93+ P3.3 cancel-aware recv — TODAY'S change), streaming path back to the panel (per-token Qt slots? whole-document re-render per chunk?). Question: any synchronous/blocking call on the prompt path (REST on a Qt slot, streaming re-render), and could the P3.3 recv loop mis-consume or starve the pump?` },
]
const seams = await parallel(SEAMS.map(s => () =>
  agent(
    `Map the "${s.id}" seam of the SYNAPSE prompt-send path. ${s.brief}\n` +
    `Produce: the exact call chain on prompt-send (file:line per hop), every hop that runs on or blocks Houdini's ` +
    `main thread (with the duration bound if the code names one, else "unbounded"), and the live telemetry that ` +
    `would prove the seam firing (~/.synapse/logs entries, stall detector, dispatch-wait histogram — check ` +
    `synapse_live_metrics via ToolSearch if reachable). TRACE, DON'T HYPOTHESIZE.`,
    { agentType: 'cartographer', label: `seam:${s.id}`, phase: 'Seam-Map', schema: SEAM_SCHEMA }
  )
))
const seamOk = seams.filter(Boolean)
if (!seamOk.length) throw new Error('freeze-forensics: all seam mappers died')

phase('Hypothesize')
// Deterministically seed from recon; the seam evidence decides, not this list.
const SEED_HYPS = [
  { id: 'H1-provider-sync-on-main', claim: 'The provider REST/streaming call runs synchronously on a Qt/main thread on prompt send → GUI dead for the whole LLM turn.' },
  { id: 'H2-context-gather-inline', claim: 'On a stale-context prompt send, context gather still runs inline on the main thread (v5.40.1 fixed the poll + tool fallback, not this call site).' },
  { id: 'H3-tool-marshal-grip', claim: 'A heavy tool call blocks the marshal/defereval queue long enough to grip the GUI (advisory-layer failure: freeze is attributable but unbounded).' },
  { id: 'H4-freeze-chain-misfire', claim: 'The freeze_chain escalation fires on a legitimate long main-thread stretch → breaker force-open + emergency halt → everything wedges (panel + server dead), read as "nodes frozen".' },
  { id: 'H5-streaming-jank', claim: 'Per-token streaming triggers a Qt slot that re-renders the document each chunk → main-thread churn during the turn.' },
  { id: 'H6-todays-regression', claim: 'The P3.3 cancel-aware recv loop (9c9bc8e, today) mis-consumes or blocks transport; or P3.1 ping gate (340db86) mis-routes the bridge state machine → new symptom since v5.41.0.' },
  { id: 'H7-handler-heavy-tool', claim: 'A context/observation handler (traverses all nodes) blocks executeInMainThreadWithResult unbounded → queued marshals starve the GUI.' },
]
const HYPO_SCHEMA = {
  type: 'object',
  properties: {
    candidates: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          claim: { type: 'string' },
          mechanism: { type: 'string', description: 'file:line mechanism from the seam evidence, or "no-seam-support" if the maps refute it' },
          falsifiable_probe: { type: 'string' },
        },
        required: ['id', 'claim', 'mechanism', 'falsifiable_probe'],
      },
    },
    dropped_seeds: { type: 'array', items: { type: 'string' }, description: 'seed hypotheses the seam maps refute on sight, one line why' },
  },
  required: ['candidates', 'dropped_seeds'],
}
const hypos = await agent(
  `Generate the candidate root-cause set for the prompt-send freeze FROM THE EVIDENCE, anchored on these seeds ` +
  `(keep, strengthen, or drop each with a reason):\n${JSON.stringify(SEED_HYPS, null, 1)}\n\n` +
  `SEAM EVIDENCE:\n${JSON.stringify(seamOk, null, 1)}\n\n` +
  `TAXONOMY:\n${JSON.stringify(history, null, 1)}\n\n` +
  `Rules: every candidate carries a mechanism at file:line from the seam maps (no-seam-support = drop it), ` +
  `and a falsifiable probe (a code read or a telemetry query that could REFUTE it). A closed-class re-explanation ` +
  `without checking the closure goes to dropped_seeds. Add candidates the evidence suggests beyond the seeds. ` +
  `Cap at 12 candidates.`,
  { label: 'hypothesize', phase: 'Hypothesize', schema: HYPO_SCHEMA }
)

phase('Probe')
const PROBE_SCHEMA = {
  type: 'object',
  properties: {
    id: { type: 'string' },
    verdict: { type: 'string', description: 'CONFIRMED | REFUTED | OPEN — OPEN requires naming the exact evidence that would close it' },
    evidence: { type: 'array', items: { type: 'string' }, description: 'file:line code reads or live telemetry lines, verbatim' },
  },
  required: ['id', 'verdict', 'evidence'],
}
const candidates = (hypos && hypos.candidates) || SEED_HYPS
const probes = await parallel(candidates.slice(0, 12).map(h => () =>
  agent(
    `Probe ONE freeze hypothesis to verdict. HYPOTHESIS:\n${JSON.stringify(h, null, 1)}\n\n` +
    `Method: read the code at every mechanism file:line (root: ${ROOT}); where the prediction is behavioral, query ` +
    `live telemetry (stall detector / dispatch-wait histogram / freeze-chain escalation entries in ~/.synapse/logs, ` +
    `plus synapse_live_metrics via ToolSearch). Verdict REFUTED the moment code or telemetry contradicts the ` +
    `mechanism — quote the contradicting line. Verdict CONFIRMED only when the mechanism is real AND on the ` +
    `prompt-send path AND can plausibly grip the whole node surface. OPEN is honest when the evidence cannot arbitrate ` +
    `— name the exact probe that closes it (e.g. a live repro watch).`,
    { agentType: 'assayer', label: `probe:${h.id}`, phase: 'Probe', schema: PROBE_SCHEMA }
  )
))
const probeOk = probes.filter(Boolean)
const confirmed = probeOk.filter(p => p.verdict === 'CONFIRMED')
const open = probeOk.filter(p => p.verdict === 'OPEN')
log(`probe: ${confirmed.length} CONFIRMED, ${open.length} OPEN, ${probeOk.length - confirmed.length - open.length} REFUTED`)

phase('Attack')
const ATTACK_SCHEMA = {
  type: 'object',
  properties: {
    id: { type: 'string' },
    stands: { type: 'boolean' },
    refutation: { type: 'string', description: 'if refuted: the killing evidence, file:line. If stands: what you tried and why it failed' },
  },
  required: ['id', 'stands', 'refutation'],
}
let attacks = []
if (confirmed.length) {
  attacks = (await parallel(confirmed.map(p => () =>
    agent(
      `REFUTE this CONFIRMED freeze root-cause ranking. You did not build it; you are motivated to kill it.\n` +
      `CLAIM + EVIDENCE:\n${JSON.stringify(p, null, 1)}\n\n` +
      `Attack all three legs: (1) mechanism real? re-read the code at its file:lines — same build, today, not the ` +
      `memory of it; (2) really on the prompt-send path? trace it yourself from the Send click; (3) really can grip ` +
      `the WHOLE node surface (not just the panel)? Distinguish: Qt-grab (panel dead too) vs marshal-queue starvation ` +
      `(panel live, hou interaction dead) — the symptom shape discriminates. stands=false if ANY leg falls; quote ` +
      `the killing line.`,
      { agentType: 'crucible', label: `attack:${p.id}`, phase: 'Attack', schema: ATTACK_SCHEMA }
    )
  ))).filter(Boolean)
}
const standing = attacks.filter(a => a.stands).map(a => a.id)
const refutedByAttack = attacks.filter(a => !a.stands)
log(`attack: ${standing.length} hypotheses stand${refutedByAttack.length ? `, ${refutedByAttack.length} killed by attack` : ''}`)

phase('Verdict')
const verdict = await agent(
  `Write the freeze-forensics verdict to ${ROOT}\\harness\\notes\\FREEZE_FORENSICS_${DATE.replace(/-/g, '')}.md. Sections:\n` +
  `1. SYMPTOM SHAPE discriminator — the two shapes (Qt-grab vs marshal-starvation vs escalation-wedge) and which ` +
  `live observation distinguishes them (with the exact one-line watch protocol for each).\n` +
  `2. RANKED ROOT CAUSES — standing hypotheses first, with mechanism file:line and attack-survival note; then OPEN ` +
  `with the closing probe named per item; REFUTED listed once each with the killing line.\n` +
  `3. TAXONOMY RECONCILIATION — map each standing cause to the 4 known classes or declare class 5, with the ` +
  `closure-check evidence.\n` +
  `4. TODAY'S REGRESSION CHECK — explicit verdict on whether P3.1/P3.3 (v5.41.0) plausibly introduced this, with the ` +
  `bisect evidence.\n` +
  `5. REMEDIATION TICKET — per standing cause: the fix direction, the file that owns it, the test that pins it, ` +
  `ranked by leverage. NO code is changed — this is a ticket.\n` +
  `6. LIVE REPRO PROTOCOL — exact steps: Joe sends one prompt while these telemetry surfaces are watched ` +
  `(name the MCP tools + log tail command), what each surface shows per shape. This protocol closes any OPEN item.\n\n` +
  `EVIDENCE PACK:\nHISTORY: ${JSON.stringify(history, null, 1).slice(0, 3000)}\n` +
  `PROBES: ${JSON.stringify(probeOk, null, 1).slice(0, 6000)}\n` +
  `ATTACKS: ${JSON.stringify(attacks, null, 1).slice(0, 3000)}\n\n` +
  `Reply with ONLY a one-paragraph summary naming the top root cause (or the OPEN state) and the ticket's #1 item.`,
  { label: 'verdict:write', phase: 'Verdict' }
)

return {
  verdict_doc: `harness/notes/FREEZE_FORENSICS_${DATE.replace(/-/g, '')}.md`,
  standing, confirmed: confirmed.map(c => c.id), open: open.map(o => o.id),
  refuted: probeOk.filter(p => p.verdict === 'REFUTED').map(p => p.id),
  attack_kills: refutedByAttack.map(a => ({ id: a.id, why: (a.refutation || '').slice(0, 200) })),
  regression_suspects: (history && history.regression_window) || 'unknown',
  summary: verdict || 'verdict writer died — doc may be missing',
  human_next: 'If standing causes exist: pick a remediation ticket item → dispatch a fix leg. If only OPENs: run the LIVE REPRO protocol (Joe sends a prompt, telemetry watched) → re-run probe legs with the telemetry attached.',
}
