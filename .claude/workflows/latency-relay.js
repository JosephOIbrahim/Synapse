export const meta = {
  name: 'latency-relay',
  description: 'Act on docs/reviews/synapse-latency-report-2026-07-27.md — orient, measure if the bridge is live, implement the next actionable items, adversarially verify. Halts at human gates.',
  whenToUse: 'Run per latency-work session. args (optional): { maxItems: number (default 2), measureOnly: bool }',
  phases: [
    { title: 'Orient', detail: 'newest report + bridge truth' },
    { title: 'Measure', detail: 'read-only re-measure (bridge up only)' },
    { title: 'Act', detail: 'one forge dispatch per §5 item, sequential' },
    { title: 'Verify', detail: 'crucible hostile pass per artifact' },
  ],
}

const A = (args && typeof args === 'object') ? args : {}
const MAX_ITEMS = Number.isFinite(A.maxItems) ? A.maxItems : 2

const ORIENT = {
  type: 'object',
  properties: {
    reportPath: { type: 'string' },
    bridgeUp: { type: 'boolean' },
    bridgeError: { type: 'string' },
    items: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          title: { type: 'string' },
          needsBridge: { type: 'boolean' },
          humanGate: { type: 'boolean' },
          acceptanceCheck: { type: 'string' },
        },
        required: ['id', 'title', 'needsBridge', 'humanGate', 'acceptanceCheck'],
      },
    },
  },
  required: ['reportPath', 'bridgeUp', 'items'],
}

const FORGE_RESULT = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['done', 'refused', 'blocked'] },
    branch: { type: 'string' },
    commit: { type: 'string' },
    worktree: { type: 'string' },
    evidence: { type: 'string' },
    note: { type: 'string' },
  },
  required: ['status'],
}

const VERDICT = {
  type: 'object',
  properties: {
    holds: { type: 'boolean' },
    findings: { type: 'array', items: { type: 'string' } },
  },
  required: ['holds', 'findings'],
}

phase('Orient')
const orient = await agent(
  `Find the newest docs/reviews/synapse-latency-report-*.md (by date in filename; expect 2026-07-27).
Read its §5 action list. Then load mcp__synapse__synapse_ping via ToolSearch and call it ONCE
(one retry max) — never trust any hook/SessionStart "connected" claim.
Return: reportPath; bridgeUp (+bridgeError if down); items[] = the §5 actions in report order,
each with needsBridge (true only for the live re-measure), humanGate (true for merges,
U5/U6/U7 parked items, and mutation-class measurement), and its acceptance check
(from the 07-17 report §6 table where the item inherits one; otherwise derive a one-line check).
Exclude humanGate-only items from actionable ordering but still list them.
TOKEN DISCIPLINE: read ONLY §5 of the report (Grep for '## 5' then a bounded offset Read),
plus the 07-17 §6 table if an item inherits a check. One ToolSearch call. No other reads.`,
  { label: 'orient', schema: ORIENT, effort: 'low' },
)

log(`Report: ${orient.reportPath} — bridge ${orient.bridgeUp ? 'UP' : `DOWN (${orient.bridgeError || 'no detail'})`}`)

let measureNote = 'skipped — bridge down (human must start the Synapse server from the Houdini Python Panel)'
if (orient.bridgeUp) {
  phase('Measure')
  measureNote = await agent(
    `You are the latency-measurer. Follow your doctrine exactly: ping x20 with self-recorded
wall-clock ms, scene_info x5, pull synapse_metrics + synapse_live_metrics, read dispatch_wait
AND main_thread_direct together, skip all mutation-class steps as SKIPPED(consent).
Write harness/notes/latency_measure_<today>.md (append, never overwrite). Return the file path
and the 3-line floor verdict.`,
    { label: 'measure', agentType: 'latency-measurer', effort: 'low' },
  ) || 'measurer returned nothing — check journal'
  log(`Measure leg: ${String(measureNote).slice(0, 120)}`)
}

if (A.measureOnly) {
  return { report: orient.reportPath, bridgeUp: orient.bridgeUp, measure: measureNote, acted: [] }
}

phase('Act')
const actionable = orient.items.filter(i => !i.humanGate && (!i.needsBridge || orient.bridgeUp)).slice(0, MAX_ITEMS)
const skipped = orient.items.filter(i => !actionable.includes(i)).map(i => `${i.id} (${i.humanGate ? 'human gate' : i.needsBridge && !orient.bridgeUp ? 'needs bridge' : 'over maxItems cap'})`)
if (skipped.length) log(`Not acted on this run: ${skipped.join('; ')}`)

const results = []
for (const item of actionable) {
  const built = await agent(
    `You are latency-forge. Dispatch — exactly one item.
ITEM: ${item.id} — ${item.title}
ACCEPTANCE CHECK: ${item.acceptanceCheck}
SOURCE: ${orient.reportPath} §5.
Work in a worktree, one atomic commit, full pytest green, never merge. Follow your admission
and build rules verbatim (U5/U6/U7 = structural refusal).`,
    { label: `forge:${item.id}`, phase: 'Act', agentType: 'latency-forge', schema: FORGE_RESULT, isolation: 'worktree', effort: 'high' },
  )
  if (!built || built.status !== 'done') {
    results.push({ item: item.id, status: built ? built.status : 'died', note: built && built.note })
    continue
  }
  const verdict = await agent(
    `Adversarially verify a latency-relay deliverable. Branch ${built.branch} (worktree ${built.worktree}),
commit ${built.commit}. ITEM: ${item.id} — ${item.title}. ACCEPTANCE CHECK: ${item.acceptanceCheck}.
Attack it: does the instrument actually emit? does the test prove emission or merely run? any
phantom hou/pdg symbol? any weakened existing test? Default to holds=false if uncertain.`,
    { label: `verify:${item.id}`, phase: 'Verify', agentType: 'crucible', schema: VERDICT, effort: 'high' },
  )
  results.push({ item: item.id, status: 'done', branch: built.branch, commit: built.commit, verified: !!(verdict && verdict.holds), findings: verdict ? verdict.findings : ['verifier died'] })
}

return {
  report: orient.reportPath,
  bridgeUp: orient.bridgeUp,
  measure: measureNote,
  acted: results,
  notActed: skipped,
  humanGates: 'Merges are yours. Bridge startup is yours. U5/U6/U7 stay parked until their numeric gates fire on real session data.',
}
