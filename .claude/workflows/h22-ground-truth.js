export const meta = {
  name: 'h22-ground-truth',
  description: 'Blueprint §11 verification sweep — resolve every INFERENCE-tier claim against the local repo, read-only',
  whenToUse: 'Run first, any time, MODE A-legal. Re-run whenever the blueprint or a spec cites an INFERENCE-tier fact.',
  phases: [{ title: 'Sweep', detail: 'parallel read-only probes' }, { title: 'Synthesize', detail: 'one findings table' }],
}

// Every item is one cheap local look. Read-only: this workflow writes nothing; the
// orchestrator persists the returned findings into the next paper artifact.
const ITEMS = [
  { key: 'authoring-domains', q: 'Read python/synapse/server/authoring_domains.json in full. Report the allowlist contents verbatim and whether HDA/SOP-lane scaffolding (G8b) would be admitted or refused by it.' },
  { key: 'quarantine', q: 'Find the quarantined-API list: exact membership and storage location. Start from harness/tasks.json, harness/verify/checks.py, and python/synapse/cognitive/tools/data/h21_symbol_table.json. Expected members include hou.secure, hou.pdg.*, hou.lopNetworks(), hou.updateGraphTick(). Report file:line for where membership actually lives.' },
  { key: 'preflight-equivalent', q: 'Confirm or refute: no admission gate exists between "proposed graph IR" and "nodes created". Inspect harness/verify/checks.py check_* vocabulary and python/synapse/routing/ (planner.py, wiring, validator). Distinguish generation-side validation (exists) from pre-mutation admission (G9 claims it does not exist). Cite file:line.' },
  { key: 'execute-python-wart', q: 'Status of the multi-line execute_python wart: does the live wire protocol still break on multi-line dict literals/class bodies? Check docs/FORGE_SPEC_execute_python_fix.md and the handler source it names. Report FIXED / OPEN / PARTIAL with evidence.' },
  { key: 'readme-claims', q: 'Audit README.md (repo root) for the G7 worklist: (a) any setx ANTHROPIC_API_KEY instruction, (b) outside-in framing language, (c) badge/version/test-count claims vs VERSION file and harness/verify/suite_baseline.json, (d) presence/absence of a loopback-only security sentence, (e) any use of "Moneta" as a Nuke/DCC-host label (Moneta is the memory substrate; the Nuke host is a separate product). Report each with line numbers.' },
  { key: 'd2-provider-docs', q: 'Locate the multi-provider harness + D2 decision docs. Candidates: docs/SYNAPSE_MULTI_PROVIDER_HARNESS_v1.md, docs/SYNAPSE_MULTI_PROVIDER_LEG1_ARCHITECT.md. Report exact paths and whether D2 (local Nano vs cloud Ultra) is decided or unratified in them.' },
  { key: 'sidecar-notes', q: 'Find any existing FTS5/BM25 execution-trace sidecar design notes (G6b). Grep for FTS5, BM25, telemetry sidecar across docs/ and python/synapse/. Report paths or confirm none exist.' },
  { key: 'benchmark-scripts', q: 'Read the headers of _benchmark_api.py and _benchmark_latency.py at repo root: what do they measure today, what would the G6 latency track (in-process vs hwebserver HTTP round-trip, cold + warm) still need?' },
]

const FINDING = {
  type: 'object',
  properties: {
    key: { type: 'string' },
    verdict: { type: 'string', description: 'CONFIRMED / REFUTED / PARTIAL / NOT-FOUND' },
    evidence: { type: 'string', description: 'file:line citations + the observed values, compressed' },
    blueprint_impact: { type: 'string', description: 'which gap/spec this changes, or "none"' },
  },
  required: ['key', 'verdict', 'evidence', 'blueprint_impact'],
}

const findings = await parallel(ITEMS.map(item => () =>
  agent(
    `${item.q}\n\nRules: read-only — you write nothing. Cite file:line for every claim. ` +
    `If the premise is wrong, say REFUTED and show what is actually there. Set key="${item.key}".`,
    { agentType: 'cartographer', label: `probe:${item.key}`, phase: 'Sweep', schema: FINDING }
  )
))

phase('Synthesize')
const table = findings.filter(Boolean)
log(`${table.length}/${ITEMS.length} probes returned`)
return {
  findings: table,
  missing: ITEMS.filter(i => !table.some(f => f.key === i.key)).map(i => i.key),
}
