export const meta = {
  name: 'flow-sprint',
  description: 'FLOW sprint sweep: scout artist-flow surfaces, adversarially attack each finding, synthesize a ranked backlog for the room',
  phases: [
    { title: 'Scout', detail: 'one scout per artist-flow surface' },
    { title: 'Attack', detail: 'crucible tries to refute each finding' },
    { title: 'Synthesize', detail: 'ranked backlog -> harness/flow/BACKLOG.json' },
  ],
}

const FINDINGS = {
  type: 'object',
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      maxItems: 3,
      items: {
        type: 'object',
        required: ['pain', 'evidence', 'fix_file', 'fix_shape', 'artist_value', 'cost'],
        properties: {
          pain: { type: 'string', description: 'artist-facing pain, one sentence, with a unit if knowable (ms/turn, s freeze, clicks)' },
          evidence: { type: 'array', items: { type: 'string' }, description: 'file:line citations only' },
          fix_file: { type: 'string' },
          fix_shape: { type: 'string', description: 'what the fix is, in one paragraph; no code dumps' },
          artist_value: { type: 'integer', minimum: 1, maximum: 5 },
          cost: { type: 'integer', minimum: 1, maximum: 5 },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
      },
    },
  },
}

const VERDICT = {
  type: 'object',
  required: ['verdict', 'note'],
  properties: {
    verdict: { type: 'string', enum: ['CONFIRMED', 'WEAKENED', 'REFUTED'] },
    note: { type: 'string', description: 'one sentence with file:line' },
  },
}

const REPO = 'C:/Users/User/SYNAPSE'
const CONTEXT = `Repo: SYNAPSE at ${REPO} (master v5.55.0, Houdini 22 panel + MCP server). Read-only. Mission: production hardening for ARTIST UTILIZATION & FLOW — ms between intent and pixel, stalls that break trance, panel truth-telling. Cite everything file:line. Leads you may verify: latency report docs/reviews/synapse-latency-report-2026-07-27.md (cached-prompt fix #1), memory-open items: marshal-deadlock class (websocket.py fix landed, core class open), panel Mile 4 IntegrityBlock readout absent, render-freeze bounded-render F1 flag, rope L5 panel-review evidence unboarded at docs/harness/notes/.`

const DIMS = [
  { key: 'latency', prompt: `${CONTEXT} Surface: CHAT-TURN LATENCY. Trace one panel chat message's real path (panel -> transport websocket -> server/handlers -> provider -> back). Find the top 2-3 fixable ms sinks. Verify whether the 4-line cache_control prompt-caching fix from the latency ledger is landed or still open, and where it belongs.` },
  { key: 'freeze', prompt: `${CONTEXT} Surface: FREEZE CLASSES. Enumerate live code paths that can block Houdini's main thread from a chat turn (render marshal, hdefereval blocking calls, Qt-fallback handler-inlining, websocket serial loops). Confirm which are FIXED vs still reachable. Findings = still-reachable classes or unverified fixes.` },
  { key: 'surface', prompt: `${CONTEXT} Surface: PANEL FLOW. Where does the panel make the artist spend clicks or attention to learn machine truth? Check panel/ for the IntegrityBlock readout (Mile 4 — present or absent?), error surfacing quality, and the rope L5-14..23 design items' implementation state. Findings = concrete missing/frictional readouts.` },
  { key: 'trust', prompt: `${CONTEXT} Surface: TRUST & TELEMETRY TRUTH. Can the artist tell working-from-broken right now? Check what the panel surfaces about bridge fidelity, gates, render status; note pytest pollution of the production log (~/.synapse/logs) as a truth-surface hazard. Findings = trust gaps with a fix_file.` },
]

phase('Scout')
const results = await pipeline(
  DIMS,
  d => agent(d.prompt, { label: `scout:${d.key}`, phase: 'Scout', schema: FINDINGS, effort: 'high' }),
  (found, d) => {
    if (!found || !found.findings || !found.findings.length) return []
    return parallel(
      found.findings.slice(0, 2).map((f, i) => () =>
        agent(
          `${CONTEXT} Adversarially attack this claimed artist-flow finding from the ${d.key} surface. Try to REFUTE: is the pain real in the code, is fix_file the right file, is artist_value inflated? Default to skepticism. CLAIM: ${JSON.stringify(f)}`,
          { label: `attack:${d.key}-${i}`, phase: 'Attack', schema: VERDICT, effort: 'high' }
        ).then(v => ({ dimension: d.key, ...f, attack: v }))
      )
    )
  }
)

phase('Synthesize')
const flat = results.filter(Boolean).flat().filter(Boolean)
const confirmed = flat.filter(f => f.attack && f.attack.verdict !== 'REFUTED')
log(`${flat.length} findings attacked, ${confirmed.length} survived`)
const synthesis = await agent(
  `${CONTEXT} You are the FLOW synthesis leg. Below are survival-filtered findings (attack verdict attached). Rank by artist_value/cost, merge duplicates, keep at most 8. Write the result as JSON to ${REPO}/harness/flow/BACKLOG.json with shape {"generated_from":"flow-sprint","items":[{"id":"FLOW-B<n>","rank":n,"dimension","pain","evidence","fix_file","fix_shape","artist_value","cost","attack_verdict","attack_note"}]}. Then return the same JSON inline. FINDINGS: ${JSON.stringify(confirmed)}`,
  { label: 'synthesize', phase: 'Synthesize', effort: 'high' }
)

return { attacked: flat.length, survived: confirmed.length, backlog: synthesis }
