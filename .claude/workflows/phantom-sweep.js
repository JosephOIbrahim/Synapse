export const meta = {
  name: 'phantom-sweep',
  description: 'PHANTOM SWEEP execution engine — inventories known-quarantined phantom symbols across source/docs/corpus, assays each against the h22 symbol-table authority, classifies every hit KEEP (intentional warning) vs FIX (still teaching), writes the SWEEP ledger, then attacks it. Read-only: applies no fixes ever; the FIX queue is a human-gated orchestrator action.',
  whenToUse: 'Dispatched by phantom-sweep-orchestrator after its arming check passes. args: {date: "YYYY-MM-DD", surfaces?, maxHits?}',
  phases: [
    { title: 'Inventory', detail: 'one cartographer per surface' },
    { title: 'Assay', detail: 'assayer over the discovered symbol set' },
    { title: 'Classify', detail: 'crucible per path-group — KEEP/FIX with evidence' },
    { title: 'Ledger', detail: 'write SWEEP ledger, then crucible attacks it' },
  ],
}

// args can arrive as an object OR a JSON string depending on the caller — normalize both.
const A = typeof args === 'string' ? JSON.parse(args) : (args || {})
if (!A.date || !/^\d{4}-\d{2}-\d{2}$/.test(A.date)) {
  throw new Error('phantom-sweep requires args.date "YYYY-MM-DD" (Date APIs are unavailable in workflow scripts by design)')
}
const SURFACES = A.surfaces || ['source', 'docs', 'corpus']
const MAX_HIT_GROUPS = A.maxHits || 30

// The known-quarantine signature set (SYNAPSE's documented phantoms; SPEC.md is canonical).
const SEED = [
  'hou.pdg', 'hou.secure', 'hou.lopNetworks', 'hou.updateGraphTick',
  'pdg.PyEventHandler', 'hdefereval.executeInMainThread', 'usdrender',
]

const SURFACE_SCOPE = {
  source: 'Source — *.py under python/, shared/, host/, src/, harness/',
  docs: 'Docs — CLAUDE.md, README.md, docs/**/*.md, harness/**/*.md',
  corpus: 'Corpus — rag/**/*.md (grep/index level only; do not deep-read every file)',
}

const INVENTORY_SCHEMA = {
  type: 'object',
  properties: {
    hits: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          symbol: { type: 'string' },
          path: { type: 'string' },
          line: { type: 'integer' },
          surface: { type: 'string' },
          snippet: { type: 'string', description: 'the matching line, verbatim, trimmed' },
        },
        required: ['symbol', 'path', 'surface', 'snippet'],
      },
    },
    discovered_symbols: {
      type: 'array',
      items: { type: 'string' },
      description: 'phantom-SUSPECT hou.*/pdg.*/pxr.* names found while mapping that are NOT in the seed set — symbols other warnings flag as never-use',
    },
  },
  required: ['hits', 'discovered_symbols'],
}

const ASSAY_SCHEMA = {
  type: 'object',
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          symbol: { type: 'string' },
          verdict: { type: 'string', description: 'present | absent | present-headless-blind | unknown — unknown is honest, never a guess' },
          evidence: { type: 'string', description: 'how the table matched (which key/prefix), or why unknown' },
        },
        required: ['symbol', 'verdict'],
      },
    },
    match_protocol: { type: 'string', description: 'one line: how the symbol table was read and matched' },
  },
  required: ['verdicts', 'match_protocol'],
}

const CLASSIFY_SCHEMA = {
  type: 'object',
  properties: {
    path: { type: 'string' },
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          symbol: { type: 'string' },
          line: { type: 'integer' },
          action: { type: 'string', description: 'KEEP | FIX' },
          why: { type: 'string', description: 'evidence from the surrounding context, quoted' },
        },
        required: ['symbol', 'action', 'why'],
      },
    },
  },
  required: ['path', 'verdicts'],
}

const ATTACK_SCHEMA = {
  type: 'object',
  properties: {
    unassayed_seeds: { type: 'array', items: { type: 'string' } },
    misclassified_warnings: { type: 'array', items: { type: 'string' }, description: 'FIX verdicts that are actually intentional warnings — the worst failure class' },
    missing_hits: { type: 'array', items: { type: 'string' }, description: 'seed-symbol mentions a hand grep finds that the ledger lacks' },
    verdict: { type: 'string', description: 'PASS | FAIL' },
  },
  required: ['verdict'],
}

// ---------- Phase: Inventory (one cartographer per surface, blind to each other) ----------
phase('Inventory')
const inventories = await parallel(SURFACES.map(s => () =>
  agent(
    `Map every mention of SYNAPSE's known-quarantined phantom symbols on the "${s}" surface.\n` +
    `SEED SYMBOLS: ${SEED.join(', ')}\n` +
    `SCOPE: ${SURFACE_SCOPE[s]}\n` +
    `Use Grep (output_mode content, -n) for each seed symbol — one search, pattern-OR. Record every hit: symbol, ` +
    `path, line, the verbatim matching line as snippet. Do NOT judge keep-vs-fix — you map, others judge.\n` +
    `ALSO: while mapping, note any phantom-SUSPECT hou.*/pdg.*/pxr.* symbol flagged by OTHER warnings as never-use ` +
    `that is NOT in the seed set — return those as discovered_symbols (they feed the assay).\n` +
    `Cap: 60 hits for your surface; if over, keep the EARLIEST 60 by path order and say so in a hit whose snippet ` +
    `reads "CAPPED at 60". Set surface="${s}" on every hit.`,
    { agentType: 'cartographer', label: `inventory:${s}`, phase: 'Inventory', schema: INVENTORY_SCHEMA }
  )
))

const inv = inventories.filter(Boolean)
if (!inv.length) throw new Error('phantom-sweep: all inventory legs died — do not proceed on an empty map')
const allHits = inv.flatMap(r => (r.hits || []))
const discovered = [...new Set(inv.flatMap(r => r.discovered_symbols || []))]
const symbols = [...new Set([...SEED, ...discovered])]
log(`inventory: ${allHits.length} hits across ${inv.length}/${SURFACES.length} surfaces, ${symbols.length} symbols to assay (${discovered.length} discovered)`)

// ---------- Phase: Assay (every symbol vs the h22 table; batches) ----------
phase('Assay')
const BATCH = 12
const batches = []
for (let i = 0; i < symbols.length; i += BATCH) batches.push(symbols.slice(i, i + BATCH))
const assays = await parallel(batches.map(b => () =>
  agent(
    `Assay these Houdini API symbols against the H22.0.368 runtime membership AUTHORITY: ` +
    `python/synapse/cognitive/tools/data/h22_symbol_table.json. Read the table ONCE via Bash or Read, establish ` +
    `its format, then verdict each symbol.\nSYMBOLS: ${b.join(', ')}\n` +
    `Verdict rules: present = the table proves membership | absent = the table proves non-membership (a genuine ` +
    `quarantined phantom) | present-headless-blind = hou.ui/qt/audio/desktop/viewportVisualizers — real but ` +
    `absent from the headless introspection table | unknown = the table cannot prove either way (class-placement, ` +
    `module-depth nuance) — unknown is HONEST, never guess. Report exactly how you matched in match_protocol.`,
    { agentType: 'assayer', label: `assay:${b[0]}`, phase: 'Assay', schema: ASSAY_SCHEMA }
  )
))
const verdicts = Object.fromEntries(assays.filter(Boolean).flatMap(r => r.verdicts.map(v => [v.symbol, v])))
const unassayed = symbols.filter(s => !verdicts[s] || verdicts[s].verdict === 'unknown')
log(`assay: ${Object.keys(verdicts).length}/${symbols.length} verdicted; ${unassayed.length} unknown/unassayed carried to the ledger honestly`)

// ---------- Phase: Classify (join hits × verdicts — a real barrier: classify needs ALL verdicts) ----------
phase('Classify')
// Group hits by path to bound the fan-out; crucible judges path at a time.
const byPath = {}
for (const h of allHits) (byPath[h.path] ||= []).push(h)
let groups = Object.entries(byPath)
let overflowGroups = []
if (groups.length > MAX_HIT_GROUPS) {
  log(`capping classify: ${groups.length} files → first ${MAX_HIT_GROUPS} by hit count (remainder recorded UNCLASSIFIED in the ledger)`)
  groups = groups.sort((a, b) => b[1].length - a[1].length)
  overflowGroups = groups.slice(MAX_HIT_GROUPS)
  groups = groups.slice(0, MAX_HIT_GROUPS)
}
const classified = await parallel(groups.map(([path, hits]) => () =>
  agent(
    `Classify phantom-symbol mentions in ${path}. For each, Read the file around the cited line (~20 lines of ` +
    `context) and verdict KEEP or FIX.\nHITS: ${hits.map(h => `${h.symbol} @ line ${h.line} (assay: ${(verdicts[h.symbol] || {}).verdict || 'unassayed'}): ${h.snippet}`).join('\n')}\n\n` +
    `KEEP = the mention is a WARNING / quarantine / never-use / retrospective note (⚠ callouts, rulebook entries, ` +
    `"do not use", phantom post-mortems). Warnings are learned knowledge — KEEP even when clumsy.\n` +
    `FIX = the text or code presents the symbol as USABLE: instructions to call it, code examples invoking it, ` +
    `"use X to..." with no warning, or a live code call (source surface).\n` +
    `DEFAULT KEEP ON AMBIGUITY. A wrongly-kept teaching-phantom stays visible in the ledger; a wrongly-fixed ` +
    `warning erases learned knowledge — the worst failure this harness can produce. Quote your evidence in why. ` +
    `Set path="${path}".`,
    { agentType: 'crucible', label: `classify:${path.split('/').pop()}`, phase: 'Classify', schema: CLASSIFY_SCHEMA }
  )
))
const classifiedVerdicts = classified.filter(Boolean).flatMap(r => r.verdicts.map(v => ({ ...v, path: r.path })))
const fixQueue = classifiedVerdicts.filter(v => v.action === 'FIX')
const keepCount = classifiedVerdicts.length - fixQueue.length
log(`classify: ${classifiedVerdicts.length}/${allHits.length} hits judged — ${keepCount} KEEP, ${fixQueue.length} FIX queued`)

// ---------- Phase: Ledger (write, then attack the write) ----------
phase('Ledger')
const ledgerPath = `harness/phantoms/SWEEP-${A.date}.md`
const overflowHits = overflowGroups.flatMap(([, hits]) =>
  hits.map(h => ({ symbol: h.symbol, path: h.path, line: h.line ?? null, snippet: h.snippet }))
)
const ledgerData = {
  date: A.date, surfaces: SURFACES,
  assay: symbols.map(s => ({ symbol: s, ...(verdicts[s] || { verdict: 'unassayed' }) })),
  hits_classified: classifiedVerdicts.length, hits_total: allHits.length,
  keep: keepCount, fix_queue: fixQueue,
  capped: groups.length >= MAX_HIT_GROUPS,
  overflow_count: overflowHits.length,
  overflow_unclassified: overflowHits,
}
const writer = await agent(
  `Write the PHANTOM SWEEP ledger to ${ledgerPath} (overwrite a same-date file if it exists; this is a per-day ` +
  `artifact). Markdown, three sections:\n` +
  `1. ASSAY — one table row per symbol: symbol | verdict | evidence (from verdicts, verbatim).\n` +
  `2. CLASSIFICATION — one row per classified hit: path:line | symbol | KEEP/FIX | quoted evidence.\n` +
  `3. FIX QUEUE — the FIX rows only, each with a proposed next step (forge worktree, one commit each).\n` +
  `4. OVERFLOW APPENDIX — if overflow_count > 0, one row per overflow_unclassified hit: path:line | symbol | ` +
  `snippet (verbatim). These were never judged — the classify fan-out was capped; label the section UNCLASSIFIED. ` +
  `Omit this section entirely when overflow_count is 0.\n` +
  `Header: surface list, counts, any CAPPED note (including the overflow_count when capped), and a line stating the harness applies NO fixes — the queue is ` +
  `human-gated. Data (JSON):\n${JSON.stringify(ledgerData, null, 1)}\n` +
  `Then reply with ONLY a one-paragraph summary of what you wrote.`,
  { label: 'ledger:write', phase: 'Ledger' }
)

const attack = await agent(
  `Adversarially attack the just-written ledger at ${ledgerPath}. Read it, then verify against the LIVE tree:\n` +
  `1. UNASSAYED SEEDS — are these seed symbols all present in the ledger's assay table? ${SEED.join(', ')}\n` +
  `2. MISCLASSIFIED WARNINGS — pick 5 random FIX rows, Read the cited files: is any "fix" actually an intentional ` +
  `warning (⚠ callout, never-use note, retrospective)? This is the worst failure class.\n` +
  `3. MISSING HITS — hand-grep ONE seed symbol NOT already well-covered across the in-scope surfaces: does the ` +
  `ledger hold every mention your grep finds?\nVerdict PASS only if all three hold. Cite file:line for every failure.`,
  { agentType: 'crucible', label: 'ledger:attack', phase: 'Ledger', schema: ATTACK_SCHEMA }
)
if (attack && attack.verdict !== 'PASS') {
  log(`ledger attack FAIL — ${(attack.misclassified_warnings || []).length} misclassified, ${(attack.missing_hits || []).length} missing`)
}

return {
  ledger: ledgerPath,
  writer_summary: writer || 'ledger writer died — ledger may be missing',
  symbols_assayed: Object.keys(verdicts).length,
  hits_classified: classifiedVerdicts.length,
  hits_total: allHits.length,
  predicates: { SW1: unassayed.length === 0, SW2: classifiedVerdicts.length >= allHits.length || groups.length >= MAX_HIT_GROUPS, SW3: !!writer, SW4: true },
  attack: attack || { verdict: 'UNKNOWN — attacker died' },
  fix_queue: fixQueue,
  humanNext: 'Review the FIX queue in the ledger, pick items, then dispatch forge in a worktree (one commit per fix). Nothing has been edited — the sweep is read-only by construction.',
}
