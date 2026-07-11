export const meta = {
  name: 'h22-reverify',
  description: 'Re-attack revised artifacts against their prior blockers + scan for revision regressions — the re-verify a revise round should always get',
  whenToUse: 'After any revise round, before trusting or pushing. args: { targets: [{file, label, priorBlockers:[...]}] }',
  phases: [{ title: 'Re-attack', detail: 'one crucible per artifact, parallel' }],
}

// args can arrive as an object OR a JSON string depending on the caller — normalize both.
const A = typeof args === 'string' ? JSON.parse(args) : (args || {})
if (!Array.isArray(A.targets) || !A.targets.length) {
  throw new Error('h22-reverify requires args.targets: [{file, label, priorBlockers:[...]}]')
}

const VERDICT = {
  type: 'object',
  properties: {
    file: { type: 'string' },
    stillOpen: { type: 'array', items: { type: 'string' }, description: 'prior blockers NOT genuinely closed in the current file (cite why)' },
    newBlockers: { type: 'array', items: { type: 'string' }, description: 'regressions/new showstoppers the revision introduced' },
    verdict: { type: 'string', description: 'CLEAN | NEEDS_FIX' },
  },
  required: ['file', 'stillOpen', 'newBlockers', 'verdict'],
}

const results = await parallel(A.targets.map(t => () =>
  agent(
    `RE-VERIFY (adversarial). Attack the CURRENT on-disk state of ${t.file}. You did not write it and you are ` +
    `motivated to prove the revision did NOT actually close its blockers.\n\n` +
    `PRIOR BLOCKERS reported CLOSED — for each, confirm it is genuinely fixed in the file NOW (cite the closing ` +
    `line) or declare it stillOpen with evidence:\n` +
    t.priorBlockers.map((b, i) => `${i + 1}. ${b}`).join('\n') + `\n\n` +
    `FRESH PASS — did the revision introduce a NEW defect: a factual error, a citation that no longer resolves, ` +
    `a rebuilt-shipped-code claim, an unprobed phantom hou.*/pdg.*/pxr.* symbol asserted as fact, or ` +
    `rigging/KineFX/APEX scope leakage? Verdict CLEAN only if EVERY prior blocker is genuinely closed AND no new ` +
    `blocker exists. Lead with file:line evidence, not verdicts. Set file="${t.file}".`,
    { agentType: 'crucible', label: `reverify:${t.label}`, phase: 'Re-attack', schema: VERDICT }
  )
))

const done = results.filter(Boolean)
const needsFix = done.filter(r => r.verdict !== 'CLEAN' || r.stillOpen.length || r.newBlockers.length)
log(`${done.length - needsFix.length}/${done.length} CLEAN, ${needsFix.length} need fixes`)
return {
  results: done,
  allClean: needsFix.length === 0 && results.every(Boolean),
  needsFix,
  humanNext: needsFix.length === 0 ? 'All re-verified clean — safe to push.' : 'Fix needsFix items before pushing.',
}
