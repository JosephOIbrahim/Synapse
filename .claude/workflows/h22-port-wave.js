export const meta = {
  name: 'h22-port-wave',
  description: 'G1: one port wave — gatewarden admission → forge implements in a worktree → assayer probes changed symbols → crucible hostile pass → merge-ready report (merge itself is human)',
  whenToUse: 'MODE B only (drop.json exists) and docs/PORT_WAVE_MANIFEST.md is merged. args: { wave: "scene-1"|"scene-2"|"usd-1"|"usd-2"|"render"|"tops-1"|"tops-2"|"cops-1"|"cops-2"|"memory-1"|"memory-2" } (OD-1(b) sub-waves, ruled 2026-07-16; family names remain valid per OD-1(a) fallback).',
  phases: [{ title: 'Gate' }, { title: 'Build' }, { title: 'Assay' }, { title: 'Attack' }],
}

// args can arrive as a JSON STRING in this runtime — normalize (same defensive parse as h22-relay/doc-scout).
const A = typeof args === 'string' ? (() => { try { return JSON.parse(args) || {} } catch { return {} } })() : (args || {})
if (!A.wave) throw new Error('h22-port-wave requires args: { wave: "<family>" }')

phase('Gate')
const verdict = await agent(
  `Work item: G1 port wave "${A.wave}" per docs/PORT_WAVE_MANIFEST.md — MODE B implementation, ` +
  `mutating python/synapse/ source in a worktree. Emit your standard verdict block.`,
  { agentType: 'h22-gatewarden', label: `gate:${A.wave}` }
)
if (typeof verdict !== 'string' || !verdict.includes('GATE VERDICT: ALLOW') || verdict.includes('ALLOW-PAPER-ONLY')) {
  log(`Wave ${A.wave} refused at the gate — nothing was built`)
  return { wave: A.wave, status: 'REFUSED', verdict }
}

phase('Build')
const build = await agent(
  `${verdict}\n\nImplement port wave "${A.wave}" exactly per docs/PORT_WAVE_MANIFEST.md: the listed tools ` +
  `for this family, legacy WS path → Dispatcher, following the documented port pattern (find it via the ` +
  `manifest's references — do not invent a new pattern). Wave DoD from the manifest applies: full pytest ` +
  `suite at floor, phantom_clean intact, one atomic commit in the worktree. Scout-probe any symbol you ` +
  `are not certain of before emitting it.`,
  { agentType: 'h22-forge', label: `forge:${A.wave}`, isolation: 'worktree' }
)

phase('Assay')
const assay = await agent(
  `V1 hard gate on the "${A.wave}" wave. From the forge report below, extract every hou.*/pdg.*/pxr.* ` +
  `symbol the wave's diff introduces or newly relies on, and probe each against the live runtime per your ` +
  `charter (bridge first, hython fallback with build-mismatch flag). PASS/QUARANTINE per symbol, verbatim ` +
  `probes and outputs.\n\nForge report:\n` + (typeof build === 'string' ? build.slice(0, 4000) : JSON.stringify(build)),
  { agentType: 'assayer', label: `assay:${A.wave}` }
)

phase('Attack')
const ATTACK = {
  type: 'object',
  properties: {
    showstoppers: { type: 'array', items: { type: 'string' } },
    boundedWeaknesses: { type: 'array', items: { type: 'string' } },
    mergeReady: { type: 'boolean' },
  },
  required: ['showstoppers', 'boundedWeaknesses', 'mergeReady'],
}
const attack = await agent(
  `Hostile pass on port wave "${A.wave}" (worktree diff from the forge run). You did not build it. ` +
  `Hunt: silent behavior drift between the legacy WS handler and the Dispatcher port (same args → same ` +
  `effect?), consent/undo/provenance envelope loss across the port, error paths that the legacy branch ` +
  `handled and the port drops, test theater (tests that pin the mock, not the contract). ` +
  `Assayer verdicts:\n${typeof assay === 'string' ? assay.slice(0, 3000) : JSON.stringify(assay)}`,
  { agentType: 'crucible', label: `attack:${A.wave}`, schema: ATTACK }
)

const ready = attack && attack.mergeReady && !(attack.showstoppers || []).length
log(ready ? `Wave ${A.wave}: merge-ready — the merge is yours` : `Wave ${A.wave}: NOT merge-ready`)
return { wave: A.wave, status: ready ? 'MERGE_READY' : 'NEEDS_REPAIR', build, assay, attack, humanNext: ready ? 'Review worktree, merge (human gate).' : 'Read attack.showstoppers; re-dispatch wave after repair.' }
