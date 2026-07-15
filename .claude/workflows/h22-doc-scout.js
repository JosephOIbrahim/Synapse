export const meta = {
  name: 'h22-doc-scout',
  description: 'Scout the H22 SideFX docs (Solaris/COPs/HOM) through a SYNAPSE-dev lens; every actionable is a provenance-tagged candidate cross-checked against the committed h22 symbol table with a runtime probe attached. Writes a prioritized report + a flywheel-shaped candidates.json. Read-only external; writes only under docs/ + harness/notes/.',
  whenToUse: 'On demand — per SideFX doc update or a future Houdini major. args: { date: "YYYY-MM-DD", domains?: [...] }. NOTE: args arrives as a JSON STRING in this runtime; the parse below is defensive on purpose.',
  phases: [
    { title: 'Map', detail: 'discover target doc URLs per domain' },
    { title: 'Read', detail: 'fan-out SYNAPSE-lens readers per page' },
    { title: 'Cross-verify', detail: 'match real SYNAPSE surface + symbol-table phantom-guard' },
    { title: 'Synthesize', detail: 'prioritized report + candidates.json' },
  ],
}

// args arrives as a JSON STRING in this runtime (see synapse-harness memory) —
// parse defensively so `date`/`domains` are never silently dropped.
const A = (typeof args === 'string')
  ? (() => { try { return JSON.parse(args) || {} } catch { return {} } })()
  : (args || {})
const DATE = A.date || 'undated'

const REPO = 'C:/Users/User/SYNAPSE'
const SYMTAB = REPO + '/python/synapse/cognitive/tools/data/h22_symbol_table.json'

const LENS = `You are scouting SideFX Houdini 22 documentation for SYNAPSE — an agentic Houdini plugin exposing ~115 MCP tools (Solaris/USD set-dressing, COPs/Copernicus networks, Karma renders, PDG/TOPs), every action reversible + recorded. SYNAPSE's #1 failure mode is PHANTOM APIs (calling hou/pxr/pdg symbols that do not exist). HARD RULE: docs describe INTENT, the runtime is TRUTH — NEVER assert a doc claim as verified fact. Classify every finding into exactly one bucket: NEW_MCP_TOOL (a capability SYNAPSE could expose as a new tool), RECIPE_CHANGE (a node/param SYNAPSE's Solaris/COP recipes use that H22 changed/renamed), API_MIGRATION (a hou/pxr/pdg call H22 changed/deprecated), CAPABILITY_GAP (something the docs show is possible SYNAPSE should support), CORPUS_SEED (H22 prose worth adding to a houdini22-reference RAG skill). For each finding give: the exact doc URL + section heading, the bucket, a one-line SYNAPSE relevance, tier (default DOC-CLAIM), the list of concrete hou./pxr./pdg. symbols it cites (if any), and a CONCRETE runtime probe (the exact dir()/hasattr/hou call that would verify it). SCOPE: Solaris, COPs/Copernicus, HOM/scripting/automation only. REJECT anything rigging/KineFX/APEX (declared non-goal) — do not report it. Flag any version-bump / breaking change as needing ESCALATE.`

const DEFAULT_DOMAINS = [
  { key: 'solaris', seed: 'https://www.sidefx.com/docs/houdini22.0/solaris/index.html', focus: 'LOP nodes, USD stage composition, set-dressing (instancer/pointinstancer/layout/component builder/duplicate), variants, karma render settings, light LOPs, materialx binding' },
  { key: 'cops', seed: 'https://www.sidefx.com/docs/houdini22.0/copernicus/index.html', focus: 'Copernicus/COP nodes, OpenCL, the SOPs->COPs heightfield migration, compositing/AOVs, procedural textures, reaction-diffusion/solvers' },
  { key: 'mcp_hom', seed: 'https://www.sidefx.com/docs/houdini22.0/hom/index.html', focus: 'HOM Python API changes (hou.*), any first-party automation / web-server / agent / MCP surface, session + command + node/parm APIs SYNAPSE builds on' },
]
const DOMAINS = Array.isArray(A.domains) && A.domains.length ? A.domains : DEFAULT_DOMAINS

const MAP_SCHEMA = {
  type: 'object', required: ['domain', 'urls'],
  properties: { domain: { type: 'string' }, urls: { type: 'array', items: { type: 'string' } } },
}
const FINDING = {
  type: 'object', required: ['title', 'bucket', 'relevance', 'probe'],
  properties: {
    title: { type: 'string' }, bucket: { type: 'string' }, section: { type: 'string' },
    relevance: { type: 'string' }, tier: { type: 'string' },
    symbols: { type: 'array', items: { type: 'string' } }, probe: { type: 'string' },
    escalate: { type: 'boolean' },
  },
}
const READ_SCHEMA = {
  type: 'object', required: ['url', 'domain', 'findings'],
  properties: { url: { type: 'string' }, domain: { type: 'string' }, findings: { type: 'array', items: FINDING } },
}
const VERIFY_SCHEMA = {
  type: 'object', required: ['domain', 'verified'],
  properties: {
    domain: { type: 'string' },
    verified: {
      type: 'array',
      items: {
        type: 'object', required: ['title', 'bucket', 'tier', 'probe'],
        properties: {
          title: { type: 'string' }, bucket: { type: 'string' }, tier: { type: 'string' },
          doc_url: { type: 'string' }, relevance: { type: 'string' }, probe: { type: 'string' },
          symbols: { type: 'array', items: { type: 'string' } }, gap: { type: 'string' },
          escalate: { type: 'boolean' },
        },
      },
    },
  },
}

// Phase Map — discover the SYNAPSE-relevant sub-pages per domain (barrier).
phase('Map')
const maps = await parallel(DOMAINS.map(d => () =>
  agent(`${LENS}\n\nDOMAIN: ${d.key}. Focus: ${d.focus}. Start at ${d.seed} — WebFetch it (if it redirects, follow the returned URL once), read its table of contents, and return the 7 MOST SYNAPSE-relevant sub-page URLs to scout in depth (absolute URLs). Prefer pages about nodes/APIs SYNAPSE would actually call. Return {domain, urls}.`,
    { label: `map:${d.key}`, phase: 'Map', agentType: 'general-purpose', schema: MAP_SCHEMA })
))
const readTargets = maps.filter(Boolean).flatMap(m =>
  [...new Set(m.urls)].slice(0, 7).map(u => ({ domain: m.domain, url: u })))
log(`Mapped ${readTargets.length} pages across ${maps.filter(Boolean).length} domains`)

// Phase Read — fan out one reader per page.
phase('Read')
const findingBatches = await parallel(readTargets.map(t => () =>
  agent(`${LENS}\n\nDOMAIN: ${t.domain}. WebFetch ${t.url} (follow one redirect if returned) and extract SYNAPSE-dev findings per the rules above. Only report genuinely SYNAPSE-actionable items — quality over quantity. Return {url, domain, findings}.`,
    { label: `read:${t.domain}:${t.url.split('/').pop().replace('.html', '').slice(0, 24)}`, phase: 'Read', agentType: 'general-purpose', schema: READ_SCHEMA })
))
const byDomain = {}
for (const b of findingBatches.filter(Boolean)) {
  (byDomain[b.domain] ||= []).push(...(b.findings || []).map(f => ({ ...f, doc_url: b.url })))
}

// Phase Cross-verify — real-surface match + symbol-table phantom-guard, per domain.
phase('Cross-verify')
const handlerHint = { solaris: 'server/handlers_solaris_*.py + server/solaris_graph_templates.py', cops: 'server/handlers_cops.py', mcp_hom: 'server/handlers*.py + mcp/_tool_registry.py' }
const verifiedBatches = await parallel(Object.entries(byDomain).map(([domain, findings]) => () =>
  agent(`You adversarially verify H22 doc-scout findings for SYNAPSE (domain: ${domain}). For EACH finding:
(a) CROSS-REFERENCE the real SYNAPSE surface — Grep ${REPO}/python/synapse/mcp/_tool_registry.py and ${REPO}/python/synapse/${handlerHint[domain] || 'server/handlers*.py'} and (for prose) ${REPO}/rag/skills/houdini21-reference/ — set gap = "GAP" (not covered), "COVERED" (already a tool/handler), or "PARTIAL".
(b) PHANTOM-GUARD — for every hou./pxr./pdg. symbol the finding lists, Grep ${SYMTAB} (the committed H22 symbol table, 35903 symbols, stamp 22.0.368) for the EXACT dotted symbol. Set tier = VERIFIED (symbol present), PHANTOM (a concrete symbol is cited but ABSENT — do NOT implement), or DOC-ONLY (prose, no concrete symbol). A finding with no symbols stays DOC-CLAIM. CRITICAL inverse-trap: hou.lop.* / hou.ui.* / hou.qt.* / hou.hipFile.* submodules introspect to 0 children in the headless table — a symbol under them reading ABSENT is a COVERAGE GAP, not a phantom; tag those DOC-ONLY with a "blind-spot" note, never PHANTOM.
(c) keep the runtime probe; drop anything rigging/KineFX/APEX; preserve escalate flags.
Return {domain, verified} with each item carrying title, bucket, tier, doc_url, relevance, probe, symbols, gap, escalate. Findings:\n${JSON.stringify(findings).slice(0, 12000)}`,
    { label: `verify:${domain}`, phase: 'Cross-verify', agentType: 'general-purpose', schema: VERIFY_SCHEMA })
))
const all = verifiedBatches.filter(Boolean).flatMap(v => v.verified || [])
log(`Cross-verified ${all.length} findings`)

// Phase Synthesize — the report + machine-readable candidates.
phase('Synthesize')
const summary = await agent(`You are the SYNAPSE H22 doc-intel synthesizer. From the ${all.length} cross-verified findings below, WRITE TWO FILES with the Write tool:

1. ${REPO}/docs/reviews/h22-doc-intel-${DATE}.md — a prioritized report for SYNAPSE development. Structure:
   - Title + provenance line (fetch-date ${DATE}, symbol-table stamp 22.0.368, doc source sidefx.com/docs/houdini22.0).
   - Executive summary + a TOP 10 HIGHEST-LEVERAGE table (rank, domain, bucket, item, tier, gap).
   - Per domain (Solaris, COPs/Copernicus, MCP/HOM), grouped by bucket (NEW_MCP_TOOL, RECIPE_CHANGE, API_MIGRATION, CAPABILITY_GAP, CORPUS_SEED). Each item: doc URL, tier, one-line relevance, the runtime probe, gap-vs-covered.
   - A dedicated ## PHANTOM WATCH section: Tier A confirmed-absent dotted symbols (do NOT emit), Tier B node-type-name strings (never table-verifiable — probe before createNode), Tier C coverage blind-spots (ABSENT but REAL — do NOT auto-reject; allowlist like hou.ui/hou.qt).
   - A ## ESCALATE section (breaking changes / version-bump smells).
   - A closing ## How to use this (candidates are DOC-CLAIM until their probe runs under H22 hython; feed to flywheel ratified:false; this report never mutates code).

2. ${REPO}/harness/notes/h22_doc_candidates.json — {"generated":"${DATE}","against_build":"22.0.368","source":"sidefx docs houdini22.0","candidates":[{id, domain, bucket, tier, doc_url, relevance, probe, gap, escalate}]} — every actionable finding, ready to seed flywheel ratified:false entries.

Both must be valid + written via Write. Return a concise text summary: counts per bucket, per tier (esp. how many PHANTOM), and the top 5 items. Findings:\n${JSON.stringify(all).slice(0, 60000)}`,
  { label: 'synthesize:report', phase: 'Synthesize', agentType: 'general-purpose' })

return { pagesRead: readTargets.length, findings: all.length, phantomGuarded: all.filter(f => f.tier === 'PHANTOM').length, summary }
