export const meta = {
  name: 'h22-leg0',
  description: 'Leg 0 paper deliverables: Mile 0.1 G7 doc fixes + Mile 0.2 baseline freeze + Mile 0.3 four Phase-0 specs, each adversarially reviewed',
  whenToUse: 'MODE A-legal, run now (pre-drop). Pass {groundTruth} = the h22-ground-truth findings if available.',
  phases: [
    { title: 'Draft', detail: 'scribe: four specs in parallel · docsurgeon: G7 · scribe: baseline freeze' },
    { title: 'Verify', detail: 'crucible attacks each artifact as it lands' },
    { title: 'Revise', detail: 'scribe closes blockers; unresolved → human' },
  ],
}

const GT = args && args.groundTruth ? `\n\nGround-truth findings from the §11 sweep (trust these over the blueprint's INFERENCE tags):\n${JSON.stringify(args.groundTruth)}` : ''

const SPECS = [
  {
    slug: 'port-wave-manifest', out: 'docs/PORT_WAVE_MANIFEST.md',
    brief: 'G1 port-wave manifest. Enumerate the actual legacy-path tool inventory from the live registry source (do not trust the count 104 — derive it). Waves by family: scene → usd → render → tops → cops → memory. 10–15 tools per wave. Per-wave DoD: basic pass + hostile (crucible) pass + phantom_clean guardrail intact + full pytest suite at floor. Adapter-retirement criteria for legacy mcp_server.py branches. Name the governing gate (merge per wave, human) and relay leg (Leg 3, first priority).',
  },
  {
    slug: 'preflight-gate', out: 'docs/PREFLIGHT_GATE.md',
    brief: 'G9 pre-flight admission gate spec (P7 made operational). Input: proposed graph IR before any hou mutation. Pass 1 structural admission against harness/notes/verified_connectivity_21.0.671.json (type exists, wire catalog-legal, arity). Typed refusal with the failing rule, no mutation. Pass 2 context conformity, COP first (resolution policy, OCIO/ACEScg), auto-injected fix nodes inside the same undo block, provenance-tagged gate-injected. Admitted IR → single undo-wrapped transaction → post-verify → commit or rollback. hou.imageResolution and any header-reading symbol are V0 — route to runbook step 9, never assert. MUST inventory the existing python/synapse/routing/ validator surface first and specify reuse, not rebuild — pointing the shipped rulebook backward is the design. COP pass explicitly blocks on the G2 COP re-audit.',
  },
  {
    slug: 'grounding-contract', out: 'docs/SCENE_GROUNDING_CONTRACT.md',
    brief: 'G5 scene-grounding contract. Four read-only manifest tools: graph_manifest, attr_manifest, parm_manifest, error_manifest. Token-budgeted with a degradation ladder (counts → names → typed samples). Thread posture per the Spike 3.1 lesson (find and cite it). Explicit non-dependency on USD schema changes — the Michael Gold RFC stays off the critical path. Specify against the existing synapse_inspect_* tool surface: what exists, what the manifests add.',
  },
  {
    slug: 'benchmark-design', out: 'docs/BENCHMARK_DESIGN.md',
    brief: 'G6 benchmark design. Latency track: identical op set, in-process dispatch vs hwebserver HTTP round-trip, cold + warm — extend _benchmark_api.py/_benchmark_latency.py, never rebuild. Token track: identical tasks, SYNAPSE grounding vs naive serialization recipe; tokens/turn, tokens/task, turns-to-green; three scene tiers. Memory track: the Shot-010 scenario as named benchmark + flagship demo ("revert lookdev to Shot 010 layout, keep current point-cloud density" — answerable only by composition over append-only history). G6b sidecar boundary sentence verbatim: telemetry (lexical, sidecar) records what happened; cognitive state (USD, substrate) records what is true. No vector store. Results publish through README with methodology.',
  },
]

const FINDINGS = {
  type: 'object',
  properties: {
    blockers: { type: 'array', items: { type: 'string' }, description: 'must-fix before the artifact is executable — unverified claims stated as fact, open design decisions hidden as prose, rebuilt-shipped-code' },
    weaknesses: { type: 'array', items: { type: 'string' }, description: 'bounded, document-and-keep' },
  },
  required: ['blockers', 'weaknesses'],
}

// The three legs are independent — one pipeline, no barrier between them.
const specResults = pipeline(
  SPECS,
  s => agent(
    `Draft ${s.out}. Brief: ${s.brief}${GT}\n\nHouse rules apply: verify every path/count/symbol yourself; ` +
    `tag what you cannot verify; OPEN DECISIONS block at top for anything only the human can rule on; ` +
    `DoD first. This is MODE A paper — you are writing the spec, not building the thing.`,
    { agentType: 'h22-scribe', label: `draft:${s.slug}`, phase: 'Draft' }
  ),
  (draft, s) => agent(
    `Attack ${s.out}. You did not write it. Hunt: (1) claims stated as fact that the spec author did not ` +
    `verify (demand the citation), (2) design decisions silently made that belong to the human, ` +
    `(3) anything that rebuilds shipped code (check python/synapse/routing/, _benchmark_*.py, existing tools), ` +
    `(4) phantom API symbols asserted without a V0/V1 tag, (5) rigging-scope leakage. ` +
    `Blockers must be specific enough to fix.`,
    { agentType: 'crucible', label: `verify:${s.slug}`, phase: 'Verify', schema: FINDINGS }
  ),
  (findings, s) => {
    if (!findings || !findings.blockers.length) return { spec: s.out, status: 'CLEAN', findings }
    return agent(
      `Revise ${s.out} to close these blockers, and only these:\n${findings.blockers.map((b, i) => `${i + 1}. ${b}`).join('\n')}\n` +
      `If a blocker is actually a human decision, move it into the OPEN DECISIONS block instead of resolving it.`,
      { agentType: 'h22-scribe', label: `revise:${s.slug}`, phase: 'Revise' }
    ).then(() => ({ spec: s.out, status: 'REVISED', findings }))
  }
)

const g7 = agent(
  `Execute the standing G7 worklist on README.md and docs/ (your agent charter lists it: auth setx fix, ` +
  `outside-in framing, loopback sentence, C3 Moneta rider, badge/version reconciliation).${GT} ` +
  `Surgical diffs only. Report per-item: fixed / already-correct / could-not-verify.`,
  { agentType: 'h22-docsurgeon', label: 'g7:doc-surface', phase: 'Draft' }
).then(r => agent(
  `Attack the G7 changes just made to README.md/docs/ (git diff shows them). Did any edit weaken a true claim, ` +
  `add mechanism detail that should stay at claim level (IP hygiene), or miss a live instance of the worklist? ` +
  `Report of the surgeon: ${typeof r === 'string' ? r.slice(0, 2000) : JSON.stringify(r)}`,
  { agentType: 'crucible', label: 'verify:g7', phase: 'Verify', schema: FINDINGS }
))

const baselines = agent(
  `Mile 0.2 baseline freeze → write harness/state/leg0_baselines.json. Freeze, with evidence commands shown: ` +
  `(1) sha256 of harness/notes/verified_connectivity_21.0.671.json (catalog hash), ` +
  `(2) the quarantine snapshot — exact symbol list + the file:line it came from, ` +
  `(3) the test-pass floor from harness/verify/suite_baseline.json (copy, cite — do not re-run the suite), ` +
  `(4) sha256 of python/synapse/cognitive/tools/data/h21_symbol_table.json. ` +
  `This file is the fixed LEFT SIDE of every drop-week diff (runbook step 1 stops without it).`,
  { agentType: 'h22-scribe', label: 'freeze:baselines', phase: 'Draft' }
)

const [specs, g7Result, baselineResult] = await parallel([() => specResults, () => g7, () => baselines])

log('Leg 0 paper pass complete — merge-to-main remains the human gate on every artifact')
return { specs, g7: g7Result, baselines: baselineResult }
