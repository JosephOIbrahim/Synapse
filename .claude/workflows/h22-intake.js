export const meta = {
  name: 'h22-intake',
  description: 'Blueprint §10 intake protocol: adjudicate one external research artifact into a one-page appendix, then adversarially check the adjudication itself',
  whenToUse: 'Any inbound dossier/whitepaper/thread/transcript. args: { artifact: "<path or URL>", slug: "<kebab-name>" }. Never revises the blueprint — escalations return to the human + CTO.',
  phases: [{ title: 'Adjudicate' }, { title: 'Attack' }],
}

if (!args || !args.artifact || !args.slug) {
  throw new Error('h22-intake requires args: { artifact: "<path or URL>", slug: "<kebab-name>" }')
}

const appendix = await agent(
  `Run the §10 intake protocol on this artifact: ${args.artifact}\n` +
  `Write the appendix to docs/intake/adjudication-${args.slug}.md. Your charter has the full protocol; ` +
  `non-negotiables: tier-label every claim, provenance is not evidence, hou./pdg./node-type claims are V0 ` +
  `regardless of letterhead, rigging inclusions are boundary-pressure events rejected without re-litigation, ` +
  `harvest into EXISTING gaps only, escalate (never execute) anything that smells like a version bump.`,
  { agentType: 'h22-adjudicator', label: `adjudicate:${args.slug}`, phase: 'Adjudicate' }
)

const ATTACK = {
  type: 'object',
  properties: {
    holes: { type: 'array', items: { type: 'string' }, description: 'claims the appendix under- or over-credited; verdicts that contradict a principle; missed boundary pressure' },
    verdict: { type: 'string', description: 'SOUND / SOUND-WITH-HOLES / RERUN' },
  },
  required: ['holes', 'verdict'],
}

const attack = await agent(
  `Attack docs/intake/adjudication-${args.slug}.md. You did not write it. Specifically: ` +
  `(1) any ADOPT/ADAPT that violates a non-goal (§6) or lacks a tier label, ` +
  `(2) any REJECT that threw away a genuinely harvestable mechanism, ` +
  `(3) missed rigging/scope pressure, (4) any claim credited because of who said it (P1 violation), ` +
  `(5) confabulation leakage — Moneta-as-memory-service, H22-has-launched. ` +
  `Adjudicator's summary: ${typeof appendix === 'string' ? appendix.slice(0, 3000) : JSON.stringify(appendix)}`,
  { agentType: 'crucible', label: `attack:${args.slug}`, phase: 'Attack', schema: ATTACK }
)

return {
  appendix: `docs/intake/adjudication-${args.slug}.md`,
  adjudicatorSummary: appendix,
  attack,
  humanNext: attack && attack.verdict === 'RERUN'
    ? 'Crucible voted RERUN — re-dispatch h22-intake after reviewing the holes.'
    : 'Review the appendix; any ESCALATE lines are yours. Merge-to-main is your gate.',
}
