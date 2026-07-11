export const meta = {
  name: 'h22-port-wave',
  description: 'G1: one port wave — gatewarden admission → forge implements in a worktree → assayer probes changed symbols → crucible hostile pass → merge-ready report (merge itself is human)',
  whenToUse: 'MODE B only (drop.json exists) and docs/PORT_WAVE_MANIFEST.md is merged. args: { wave: "scene"|"usd"|"render"|"tops"|"cops"|"memory" }.',
  phases: [{ title: 'Gate' }, { title: 'Build' }, { title: 'Assay' }, { title: 'Attack' }],
}

if (!args || !args.wave) throw new Error('h22-port-wave requires args: { wave: "<family>" }')

phase('Gate')
const verdict = await agent(
  `Work item: G1 port wave "${args.wave}" per docs/PORT_WAVE_MANIFEST.md — MODE B implementation, ` +
  `mutating python/synapse/ source in a worktree. Emit your standard verdict block.`,
  { agentType: 'h22-gatewarden', label: `gate:${args.wave}` }
)
if (typeof verdict !== 'string' || !verdict.includes('GATE VERDICT: ALLOW') || verdict.includes('ALLOW-PAPER-ONLY')) {
  log(`Wave ${args.wave} refused at the gate — nothing was built`)
  return { wave: args.wave, status: 'REFUSED', verdict }
}

phase('Build')
const build = await agent(
  `${verdict}\n\nImplement port wave "${args.wave}" exactly per docs/PORT_WAVE_MANIFEST.md: the listed tools ` +
  `for this family, legacy WS path → Dispatcher, following the documented port pattern (find it via the ` +
  `manifest's references — do not invent a new pattern). Wave DoD from the manifest applies: full pytest ` +
  `suite at floor, phantom_clean intact, one atomic commit in the worktree. Scout-probe any symbol you ` +
  `are not certain of before emitting it.`,
  { agentType: 'h22-forge', label: `forge:${args.wave}`, isolation: 'worktree' }
)

phase('Assay')
const assay = await agent(
  `V1 hard gate on the "${args.wave}" wave. From the forge report below, extract every hou.*/pdg.*/pxr.* ` +
  `symbol the wave's diff introduces or newly relies on, and probe each against the live runtime per your ` +
  `charter (bridge first, hython fallback with build-mismatch flag). PASS/QUARANTINE per symbol, verbatim ` +
  `probes and outputs.\n\nForge report:\n` + (typeof build === 'string' ? build.slice(0, 4000) : JSON.stringify(build)),
  { agentType: 'assayer', label: `assay:${args.wave}` }
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
  `Hostile pass on port wave "${args.wave}" (worktree diff from the forge run). You did not build it. ` +
  `Hunt: silent behavior drift between the legacy WS handler and the Dispatcher port (same args → same ` +
  `effect?), consent/undo/provenance envelope loss across the port, error paths that the legacy branch ` +
  `handled and the port drops, test theater (tests that pin the mock, not the contract). ` +
  `Assayer verdicts:\n${typeof assay === 'string' ? assay.slice(0, 3000) : JSON.stringify(assay)}`,
  { agentType: 'crucible', label: `attack:${args.wave}`, schema: ATTACK }
)

const ready = attack && attack.mergeReady && !(attack.showstoppers || []).length
log(ready ? `Wave ${args.wave}: merge-ready — the merge is yours` : `Wave ${args.wave}: NOT merge-ready`)
return { wave: args.wave, status: ready ? 'MERGE_READY' : 'NEEDS_REPAIR', build, assay, attack, humanNext: ready ? 'Review worktree, merge (human gate).' : 'Read attack.showstoppers; re-dispatch wave after repair.' }
