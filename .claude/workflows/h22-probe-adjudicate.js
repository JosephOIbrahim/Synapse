export const meta = {
  name: 'h22-probe-adjudicate',
  description: 'Doc-scout Phase 3: turn the raw hython probe results (harness/notes/h22_probe_results.json) into final VERIFIED/REFUTED verdicts (per-domain judgment), then write the promoted work queue into the dated report and stamp probe_verdict onto every candidate. Read-only external; writes only docs/ + harness/notes/.',
  whenToUse: 'After scripts/h22_probe_candidates.py has produced h22_probe_results.json for a doc-scout run. args: { date: "YYYY-MM-DD" } — MUST match the date passed to h22-doc-scout so this appends to the same docs/reviews/h22-doc-intel-<date>.md. args arrives as a JSON string in this runtime (parsed defensively below).',
  phases: [
    { title: 'Adjudicate', detail: 'per-domain: raw probe facts -> final verdict' },
    { title: 'Assemble', detail: 'promoted work queue in the report + verdicts on candidates' },
  ],
}

const A = (typeof args === 'string') ? (() => { try { return JSON.parse(args) || {} } catch { return {} } })() : (args || {})
const DATE = A.date || 'undated'
const REPO = 'C:/Users/User/SYNAPSE'
const RESULTS = REPO + '/harness/notes/h22_probe_results.json'
const CAND = REPO + '/harness/notes/h22_doc_candidates.json'
const REPORT = REPO + '/docs/reviews/h22-doc-intel-' + DATE + '.md'
const SYMTAB = REPO + '/python/synapse/cognitive/tools/data/h22_symbol_table.json'

const VERDICT_SCHEMA = {
  type: 'object', required: ['domain', 'verdicts'],
  properties: {
    domain: { type: 'string' },
    verdicts: {
      type: 'array',
      items: {
        type: 'object', required: ['id', 'verdict', 'evidence'],
        properties: {
          id: { type: 'string' },
          verdict: { type: 'string', description: 'VERIFIED | REFUTED | NEEDS_LIVE_NODE | NOT_RUNNABLE | INCONCLUSIVE' },
          evidence: { type: 'string', description: 'the deciding fact from probe_run (value/stdout/error) or symbol-table check' },
          note: { type: 'string' },
        },
      },
    },
  },
}

const DOMAINS = [
  { key: 'SOL', name: 'Solaris' },
  { key: 'COP', name: 'COPs/Copernicus' },
  { key: 'HOM', name: 'MCP/HOM' },
]

phase('Adjudicate')
const batches = await parallel(DOMAINS.map(d => () =>
  agent(`You adjudicate H22 doc-scout probe results for the ${d.name} domain. Read ${RESULTS} and take ONLY the candidates whose id starts with "${d.key}-". For EACH, using its probe_run facts (hint, mode, value, stdout, error) assign a FINAL verdict:
- VERIFIED — the runtime confirms the symbol/type/method exists & the claim holds (e.g. eval value True, a non-empty list of node-type names, stdout showing True/True, asserts passed).
- REFUTED — the runtime DENIES it (eval value False, empty list [], AssertionError, or a clean "absent" — the doc claim is wrong for H22; do NOT build).
- NEEDS_LIVE_NODE — the probe needs a real node or a cook (placeholder path like /stage/<a_lop>, an undefined node var n/node, or "needs createNode + parm read"); can only be settled interactively.
- NOT_RUNNABLE — the probe is prose (English instruction) or JS/Qt (window.Python) — no hython verdict possible.
- INCONCLUSIVE — genuinely ambiguous after reading the facts.
RULES: read the stdout to decide RAN probes. A SyntaxError on an English sentence = NOT_RUNNABLE (prose), not REFUTED. For any symbol you are unsure about, Grep ${SYMTAB} (the committed H22 table, 35903 symbols) for the exact dotted symbol — present = evidence toward VERIFIED, absent-and-not-a-hou.lop/ui/qt/hipFile-blindspot = toward REFUTED. Honor the Tier C blind-spot: hou.lop.* / hou.ui.* / hou.qt.* / hou.hipFile.* read absent in the table but are REAL → NEEDS_LIVE_NODE, never REFUTED. Return {domain:"${d.name}", verdicts:[{id, verdict, evidence, note}]}.`,
    { label: `adjudicate:${d.key}`, phase: 'Adjudicate', agentType: 'general-purpose', schema: VERDICT_SCHEMA })
))
const verdicts = batches.filter(Boolean).flatMap(b => b.verdicts || [])
log(`Adjudicated ${verdicts.length} candidates`)

phase('Assemble')
const summary = await agent(`You finalize doc-scout Phase 3 for SYNAPSE. You have ${verdicts.length} final probe verdicts (below). Do BOTH:

1. APPEND a new section to ${REPORT} (use Read then Edit to add it at the very end — do not disturb existing content). The section:
## Probe Verdicts (Phase 3 — ${DATE})
> Ran every candidate's probe under H22 hython (scripts/h22_probe_candidates.py) and adjudicated the raw facts. Candidates stay ratified:false — this adds runtime evidence for the human's ratification.
- One summary line: counts per verdict (VERIFIED / REFUTED / NEEDS_LIVE_NODE / NOT_RUNNABLE / INCONCLUSIVE).
- ### Promoted work queue (VERIFIED — ratified-ready) — a table (id, domain, bucket, item, gap, evidence) of ONLY the VERIFIED candidates, escalations first. This is the runtime-backed dev queue.
- ### Refuted (doc claim denied by the runtime — do NOT build) — table of REFUTED with the deciding evidence.
- ### Needs a live node / manual — table of NEEDS_LIVE_NODE + NOT_RUNNABLE + INCONCLUSIVE with why + the probe to run by hand.

2. REWRITE ${CAND} (Read it, then Write it back) adding "probe_verdict" and "probe_evidence" to EACH candidate object (match by id), preserving every existing field and the top-level keys. Keep ratified:false semantics (do not add ratified:true).

Then return a concise text summary: the verdict counts, the promoted VERIFIED work queue (ids + one-liners), and any REFUTED items (doc claims the runtime killed). Verdicts:\n${JSON.stringify(verdicts)}`,
  { label: 'assemble:report+candidates', phase: 'Assemble', agentType: 'general-purpose' })

const tally = verdicts.reduce((m, v) => (m[v.verdict] = (m[v.verdict] || 0) + 1, m), {})
return { adjudicated: verdicts.length, tally, summary }
