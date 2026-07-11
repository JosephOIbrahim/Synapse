export const meta = {
  name: 'h22-drop-week',
  description: 'Blueprint §9 runbook, steps 1–9: baseline check → ABI verdict → quarantine re-litigation → sweep diff → COP audit → Qt smoke → release-notes scan → perception re-audit → new-symbol probes. Stops before step 10 (human ratify).',
  whenToUse: 'Exactly once, after the human writes harness/state/drop.json (Leg 1). Every step produces an artifact; no output is trusted without one. Complements run.ts (which grinds tasks.json) — this executes the blueprint runbook artifacts.',
  phases: [
    { title: 'Gate', detail: 'step 1 — drop.json + frozen baselines or full stop' },
    { title: 'Re-ground', detail: 'steps 2–4 — ABI, quarantine, sweep (order-dependent)' },
    { title: 'Audit', detail: 'steps 5–7 in parallel — COP, Qt smoke, release notes' },
    { title: 'Probe', detail: 'steps 8–9 — perception re-audit, adjudicated-symbol probes' },
  ],
}

phase('Gate')
const verdict = await agent(
  `Runbook step 1 baseline check. Work item: execute blueprint §9 steps 2–9 (MODE B; probes + audits + ` +
  `worktree-only writes). Verify BOTH: harness/state/drop.json exists and parses, AND ` +
  `harness/state/leg0_baselines.json exists (the frozen left side). Emit your standard verdict block, ` +
  `including drop.json's python field verbatim (gate-0.1 hinges on it).`,
  { agentType: 'h22-gatewarden', label: 'gate:step1' }
)
if (typeof verdict !== 'string' || !verdict.includes('GATE VERDICT: ALLOW')) {
  log('Runbook refused at step 1 — the diff has no left side or no drop trigger. Nothing ran.')
  return { status: 'REFUSED', verdict }
}

phase('Re-ground')
// Step 2 — ABI verdict (read-only reasoning over drop.json + vendored tree).
const abi = await agent(
  `Runbook step 2, ABI verdict → write docs/reviews/h22-abi-verdict.md. Read harness/state/drop.json. ` +
  `python == cp311 → the vendored tree holds; record it. Else → gate-0.1 re-opens: enumerate the vendored ` +
  `compiled-extension list to re-vendor (verify locally; expected to start pydantic_core, jiter — derive, ` +
  `don't trust). Cite every path you checked.\n\nGate context:\n${verdict}`,
  { agentType: 'h22-scribe', label: 'step2:abi' }
)

// Step 3 — quarantine re-litigation (P6: the ONE legitimate re-probe event).
const quarantine = await agent(
  `Runbook step 3, quarantine re-litigation → artifact docs/reviews/h22-quarantine-repin.md (write via Bash ` +
  `heredoc is not available to you — emit the full artifact body as your report and PASS/QUARANTINE lines; ` +
  `the orchestrator persists it). Take the exact quarantine membership from harness/state/leg0_baselines.json ` +
  `(never from memory). Probe each symbol ONCE against the live H22 runtime per your charter. Re-pin each ` +
  `with the H22 runtime tag. hou.secure PASS is significant: the auth resolver auto-adopts it.`,
  { agentType: 'assayer', label: 'step3:quarantine' }
)

// Step 4 — sweep re-run, diff vs the U.1 catalog; deposits a ratified:false flywheel candidate.
const sweep = await agent(
  `${verdict}\n\nRunbook step 4, sweep re-run. Re-run the connectivity sweep against H22 and diff vs ` +
  `harness/notes/verified_connectivity_21.0.671.json (hash-check against leg0_baselines.json first). ` +
  `Locate the sweep tooling via harness/notes/spec-U1-wiring-flywheel.md — reuse it, never rewrite it. ` +
  `Output: harness/notes/verified_connectivity_H22.json + append a U.1-H22 cycle to ` +
  `harness/state/flywheel_queue.json with status:"candidate", ratified:false, evidence paths. ` +
  `You NEVER write ratified:true. Expected churn to look for: Copernicus heightfield set, ML/ONNX, ` +
  `splat nodes, Solaris procedurals.`,
  { agentType: 'h22-forge', label: 'step4:sweep' }
)

phase('Audit')
const [copAudit, qtSmoke, releaseNotes] = await parallel([
  () => agent(
    `Runbook step 5, COP audit refresh. Re-validate the COP tool surface (find the audited list — blueprint ` +
    `says 21 tools [INFERENCE]; derive the real inventory from the registry) against H22 Copernicus. Flag ` +
    `every tool touched by the SOPs→COPs heightfield migration. Report per-tool PASS/CHANGED/GONE with ` +
    `probe evidence. G9's COP conformity pass blocks on this output.\n\nSweep summary:\n${typeof sweep === 'string' ? sweep.slice(0, 2000) : ''}`,
    { agentType: 'assayer', label: 'step5:cop-audit' }
  ),
  () => agent(
    `${verdict}\n\nRunbook step 6, Qt/PySide smoke → artifact docs/reviews/h22-qt-smoke.md. Panel boot on the ` +
    `Vulkan-era build via hython offscreen ONLY (no PySide in stock python — house rule). Compare drop.json's ` +
    `pyside field vs panel assumptions; include the QFont letter-spacing path. Record pass/fail with output.`,
    { agentType: 'h22-forge', label: 'step6:qt-smoke' }
  ),
  () => agent(
    `Runbook step 7, release-notes scan → docs/intake/adjudication-h22-release-notes.md. Fetch the actual ` +
    `H22 release notes/launch materials. Answer: (a) first-party MCP/agent surface — confirm or deny, this ` +
    `CLOSES C2 either way; (b) KineFX/APEX scope — record it and re-affirm the drift term as a boundary- ` +
    `pressure log if the pressure grew; (c) anything that changes a G1–G9 gap. §10 discipline applies.`,
    { agentType: 'h22-adjudicator', label: 'step7:release-notes' }
  ),
])

phase('Probe')
const perception = await agent(
  `Runbook step 8, perception re-audit. Spike 3.0-style dir() audit of the pdg surface on H22; diff vs the ` +
  `Mile 2 findings (locate via harness/notes/ mile2 artifacts) before trusting the event bridges on H22. ` +
  `Known H21 truths to re-test: raw-callable addEventHandler (PyEventHandler has no constructor), events ` +
  `fire on a worker thread, event.workItemId not event.workItem. Verbatim probes + outputs.`,
  { agentType: 'assayer', label: 'step8:perception' }
)
const newSymbols = await agent(
  `Runbook step 9, adjudicated-document symbol probes. Probe on H22: (a) hou.imageResolution and any ` +
  `image-header-reading path (G9 Pass 2 candidates); (b) the actual TOP splat/ML training node names — ` +
  `the whitepaper's top::gaussian_splat_train is phantom-shaped until proven. Nothing from either external ` +
  `document enters code without this V1 verdict. PASS/QUARANTINE with verbatim evidence.`,
  { agentType: 'assayer', label: 'step9:new-symbols' }
)

log('Runbook steps 1–9 complete. Step 10 (ratify) is yours: review the flywheel candidates and every artifact above. MODE B opens per §8 only after your ratification.')
return {
  status: 'STEPS_1_9_COMPLETE',
  artifacts: { abi, quarantine, sweep, copAudit, qtSmoke, releaseNotes, perception, newSymbols },
  humanNext: 'Blueprint §9 step 10 — human ratify. Flip nothing until every artifact reads clean.',
}
