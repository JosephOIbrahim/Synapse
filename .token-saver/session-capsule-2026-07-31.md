# Session Capsule — 2026-07-31 (context-reset bridge)

## RUNNING (background, survives summarization): FREEZE FORENSICS RELAY
Task: diagnose "SYNAPSE freezes all nodes outside Synapse when a prompt is sent".
- Conductor dispatched (general-purpose carrying the freeze-forensics-orchestrator role, .claude/agents/freeze-forensics-orchestrator.md).
- Workflow `.claude/workflows/freeze-forensics.js`, args {date:"2026-07-31"}; phases: historian→seam-map→hypothesize→probe(live telemetry)→attack→verdict.
- Verdict doc target: harness/notes/FREEZE_FORENSICS_20260731.md + remediation ticket. READ-ONLY diagnosis; any fix = separate human-dispatched leg.
- Seeds: (1) no node-lock API in codebase → GUI-grip class; (2) chat_panel.py:883/:973 call _gather_context_if_stale inline on send — does v5.40.1 off-main fix cover those sites?; (3) freeze_chain 30s sustained → breaker force_open + emergency halt → everything wedges; (4) TODAY'S regression: P3.1 340db86 ping gate, P3.3 9c9bc8e recv loop — bisect vs 293484c.
- Discriminator: panel clickable while nodes frozen? Qt-grab vs marshal-starvation vs escalation-wedge.
- ON COMPLETION: relay ranked verdicts + ticket to Joe; if OPENs remain, run LIVE REPRO protocol (Joe sends one prompt while I tail stall/freeze telemetry).

## SHIPPED TODAY
- v5.41.0 pushed + GitHub release (master 8dfa23d, tag v5.41.0). Harness artifacts committed in that release commit.
- CLEAR: L5 fan-out rescued → clear/l5-phantom-scanner @ eb1e110 (unmerged), 24 tests, PROPOSED-P5.1.md ready.

## OPEN HUMAN GATES (Joe's, ranked)
1. Merge fix/corpus-usdrender-rop (14 commits, thrice-attacked SOUND; corpus usdrender phantom teaching dead) + content_digest rebuild after.
2. Merge clear/l5-phantom-scanner — carry hdefereval allowlist at harness/verify/checks.py:392 (rec from Authority leg; hdefereval = 6th headless-blind module, proven live both sides).
3. Ratify PHANTOM SWEEP SPEC + CLEAR P5.1 (both earned falsification evidence).
4. Quarantine-list: 6 confirmed-absent candidates + usdrender → rulebook/phantoms.json (packet: harness/phantoms/QUARANTINE-PACKET-2026-07-31.md).
5. CLEAR bar remaining 3 FAILs all human-gated: P2.1 (C.0), P3.4 (husk-Indie), P3.5 (latency addendum).

## KEY FACTS
- Live build = H22.0.397; symbol table stamped 22.0.368 (regen due per build).
- houdini_execute_python returns no stdout — smuggle payloads via raise RuntimeError('PROBE:'+json).
- Bridge LIVE; 5,336 tests / 0 failures as of v5.41.0 gate.
- Memory written: memory/phantom-sweep-harness.md (+MEMORY.md index). Workflow scripts: phantom-sweep.js (v2 overflow fix attacked, shipped), freeze-forensics.js.
