export const meta = {
  name: 'h22-relay',
  description: 'Cross-leg meta-relay for the H22 gap blueprint. Orients on gate state, drives the current-MODE spine (A: ground-truth then reverify-or-leg0 then optional intake; B: drop-week runbook steps 1-9), and STOPS at every human gate (merge / drop.json / ratify). The one cohesion piece the recon flagged as missing â€” it only sequences existing workflows and halts where a human must act.',
  whenToUse: 'The one command that drives the blueprint in its current mode. args (all optional): { intakeArtifact, intakeSlug, forceLeg0 }. Pass an intake artifact to fold a section-10 adjudication into the same run.',
  phases: [
    { title: 'Orient', detail: 'gatewarden reads drop.json / posture / flywheel / Leg-0 artifacts â€” read-only' },
    { title: 'Drive', detail: 'MODE A: re-verify the reconciled Leg-0 + adjudicate pending intake Â· MODE B: runbook' },
    { title: 'Report', detail: 'one consolidated status + open decisions + the single next human act' },
  ],
}

// args can arrive as an object OR a JSON string depending on the caller â€” normalize both.
const A = typeof args === 'string' ? JSON.parse(args) : (args || {})

// â”€â”€ Orient â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// P4 is structural: gatewarden is read-only and cannot flip a gate. The relay
// branches on what it observes; it never writes drop.json, ratified, or a merge.
const ORIENT = {
  type: 'object',
  additionalProperties: false,
  properties: {
    mode: { type: 'string', description: 'A (drop.json absent) or B (drop.json exists + parses)' },
    posture: { type: 'string', description: 'contents/verdict of harness/state/posture.json, or "absent"' },
    dropPresent: { type: 'boolean' },
    blueprintCommitted: { type: 'boolean', description: 'docs/SYNAPSE_H22_GAP_BLUEPRINT.md exists' },
    leg0ArtifactsPresent: {
      type: 'boolean',
      description: 'ALL of: docs/PORT_WAVE_MANIFEST.md, docs/PREFLIGHT_GATE.md, docs/SCENE_GROUNDING_CONTRACT.md, docs/BENCHMARK_DESIGN.md, harness/state/leg0_baselines.json',
    },
    openGates: { type: 'array', items: { type: 'string' }, description: 'gate â†’ open|closed, one per registry row' },
    humanActToAdvance: { type: 'string', description: 'the single next human act that opens the next gate' },
  },
  required: ['mode', 'dropPresent', 'blueprintCommitted', 'leg0ArtifactsPresent', 'humanActToAdvance'],
}

const orient = await agent(
  `ORIENTATION READ for the H22 relay (read-only â€” flip nothing). Report the current blueprint gate state:\n` +
  `1. Does harness/state/drop.json exist AND parse? (present â†’ MODE B; absent â†’ MODE A). Report posture.json too.\n` +
  `2. Does docs/SYNAPSE_H22_GAP_BLUEPRINT.md exist (F3 / Mile 0)?\n` +
  `3. Do ALL four Leg-0 specs exist â€” docs/PORT_WAVE_MANIFEST.md, docs/PREFLIGHT_GATE.md, ` +
  `docs/SCENE_GROUNDING_CONTRACT.md, docs/BENCHMARK_DESIGN.md â€” AND harness/state/leg0_baselines.json?\n` +
  `4. Per the gate registry (drop.json, flywheel ratification, merge-to-main, posture, gate-0.1, D-H22-1/D2, ` +
  `G9 design review, Michael Gold RFC): which are open vs closed, and what single human act advances the blueprint?\n` +
  `You are the read-only gate oracle; do not emit an ALLOW/REFUSE work verdict here â€” emit the orientation.`,
  { agentType: 'h22-gatewarden', label: 'orient', phase: 'Orient', schema: ORIENT }
)

if (!orient) {
  return { status: 'ORIENT_FAILED', humanNext: 'Gatewarden could not read gate state â€” check harness/state/ files parse, then re-run h22-relay.' }
}
log(`MODE ${orient.mode} Â· blueprint ${orient.blueprintCommitted ? 'committed' : 'NOT committed'} Â· Leg-0 ${orient.leg0ArtifactsPresent ? 'present' : 'absent'}`)

// Re-attack the merged Leg-0 artifacts for DRIFT against current HEAD (do not redraft merged work).
const LEG0_DRIFT_TARGETS = [
  { file: 'docs/PORT_WAVE_MANIFEST.md', label: 'g1-manifest',
    priorBlockers: ['every cited tool count / registry path still resolves at current HEAD', 'no wave references a phantom or since-moved symbol'] },
  { file: 'docs/PREFLIGHT_GATE.md', label: 'g9-preflight',
    priorBlockers: ['the reused validator surface under python/synapse/routing/ still exists as cited', 'harness/notes/verified_connectivity_21.0.671.json still has the cited entry count', 'no hou.* symbol asserted past a V0 tag'] },
  { file: 'docs/SCENE_GROUNDING_CONTRACT.md', label: 'g5-grounding',
    priorBlockers: ['the synapse_inspect_* surface it specifies-against still exists', 'no USD-schema dependency crept onto the critical path'] },
  { file: 'docs/BENCHMARK_DESIGN.md', label: 'g6-benchmark',
    priorBlockers: ['_benchmark_api.py / _benchmark_latency.py still present at root to extend', 'the Shot-010 scenario + the G6b sidecar-boundary sentence are intact', 'no vector store is proposed for cognitive state'] },
  { file: 'README.md', label: 'g7-surface',
    priorBlockers: [
      'the test-count badge matches the ratchet floor in harness/verify/suite_baseline.json (currently 4875 gate / 4048 shipping), not a stale release-era number (e.g. 4186)',
      'a loopback-only ingress/security sentence is present on the MCP/WS surface',
      'C3 (RULED: one Moneta) â€” Moneta IS the memory substrate; the Nuke host is a separate, differently-named product. Flag only misuse of "Moneta" as a host label, or any description of cognitive STATE as vector-similarity-recalled. Do NOT deny Moneta is the memory backend.',
    ] },
]

// â”€â”€ Drive â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
phase('Drive')
const call = async (name, a) => { try { return await workflow(name, a) } catch (e) { return { error: String(e && e.message || e), name } } }

let driven
if (orient.mode === 'B') {
  // MODE B: the Â§9 drop-week runbook runs steps 1â€“9 and STOPS before step 10 (ratify).
  // Port waves are NOT auto-run â€” each is a separate human-gated, per-wave, per-merge act.
  log('MODE B â€” running drop-week Â§9 steps 1â€“9; port waves stay human-dispatched per ratified wave.')
  driven = { mode: 'B', dropWeek: await call('h22-drop-week') }
} else {
  // MODE A: verify the reconciled state. Read-only except a new intake appendix; merged specs are never redrafted.
  const groundTruth = await call('h22-ground-truth')
  let leg0
  if (!orient.leg0ArtifactsPresent || A.forceLeg0) {
    log('Leg-0 artifacts absent (or forceLeg0) â€” authoring the four specs + baselines.')
    leg0 = { kind: 'leg0', result: await call('h22-leg0', { groundTruth: groundTruth && groundTruth.findings }) }
  } else {
    log('Leg-0 artifacts present â€” re-attacking for HEAD drift (no redraft).')
    leg0 = { kind: 'reverify', result: await call('h22-reverify', { targets: LEG0_DRIFT_TARGETS }) }
  }
  let intake = null
  if (A.intakeArtifact && A.intakeSlug) {
    log(`Folding a Â§10 intake on ${A.intakeArtifact} â†’ docs/intake/adjudication-${A.intakeSlug}.md`)
    intake = await call('h22-intake', { artifact: A.intakeArtifact, slug: A.intakeSlug })
  }
  driven = { mode: 'A', groundTruth, leg0, intake }
}

// â”€â”€ Report â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
phase('Report')

// Standing open decisions the relay always re-surfaces until a human rules on them.
const openDecisions = [
  // C3 RESOLVED 2026-07-12 (one-Moneta ruling) â€” kept as a breadcrumb, not an open action.
  'C3 â€” RESOLVED (one Moneta): Moneta IS SYNAPSE\'s memory substrate; the Nuke inside-out host is a ' +
  'separate, differently-named product (README portfolio line corrected). Corrected rider: cognitive STATE is' +
  'deterministic USD/LIVRPS, never vector similarity. Full ruling: docs/reviews/h22-c3-moneta-decision.md.',
]

// Pull any drift/needs-fix the drive phase surfaced.
const driftNeedsFix =
  driven.mode === 'A' && driven.leg0 && driven.leg0.kind === 'reverify' && driven.leg0.result && driven.leg0.result.needsFix
    ? driven.leg0.result.needsFix
    : []

const humanNext =
  driven.mode === 'B'
    ? 'Review every drop-week artifact; blueprint Â§9 step 10 (ratify) is yours â€” flip nothing until each reads clean. Then dispatch h22-port-wave per ratified wave.'
    : `Review the re-verify + any intake appendix. Then the standing gate is merge-to-main;` +
      `Leg 1 (write harness/state/drop.json) is the human act that opens MODE B. ${orient.humanActToAdvance || ''}`.trim()

log(driftNeedsFix.length ? `Leg-0 drift flagged: ${driftNeedsFix.length} item(s) â€” see driven.leg0.result.needsFix` : 'No Leg-0 drift flagged.')

return {
  status: driven.mode === 'B' ? 'DROP_WEEK_RAN' : 'MODE_A_VERIFIED',
  mode: driven.mode,
  orient,
  driven,
  openDecisions,
  driftNeedsFix,
  humanNext,
}
