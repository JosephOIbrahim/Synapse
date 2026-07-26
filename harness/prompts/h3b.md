You are ORCHESTRATOR for H3b — render and cook cancellation. Read harness/AGENT_CONSTITUTION.md first; it binds you. Then read rulings R44, R48, R49 and **R73** in harness/notes/CTO_RULINGS_01.md. R73 AMENDS R48 and changes this leg's scope — read it before anything else.

THIS LEG WAS HELD BY RULING AND IS RELEASED ONLY BY JOE. If you are reading this, he released it.

=== SCOPE HISTORY — READ THIS, IT HAS CHANGED TWICE ===

Originally: "build cook-cancel".
R48 narrowed it to TOPS-only, on the belief that no render-cancel API existed.
**R73 REFUTED THAT.** An earlier version of this brief told you not to attempt the render half. That instruction is WITHDRAWN.

What actually holds, VERIFIED-RUNTIME on 22.0.368:

  hou.RopNode              no cancel/abort/interrupt/stop method   (true, twice-verified)
  hou.ActiveRender         ABSENT at runtime, docs say #status: ni  (documented, unimplemented)
  hou.activeRenders()      ABSENT at runtime, same
  hou.IPRViewer.killRender PRESENT
  rps    hscript           EXISTS - "Lists background render processes"
  rkill  hscript           EXISTS - "Stop or pause/unpause a render"
  TOPS/PDG cancel surface  COMPLETE, with a node-level verb the tree does not use

**A render CAN be stopped.** Not from `RopNode`, but `hou.hscript("rkill ...")` does it, and it has been available the whole time. The earlier claim that this was a platform gap was mine and it was wrong.

=== WORK — THREE PARTS ===

**PART A — TOPS cancel.** The verb exists on 22.0.368 and the tree does not use it. Read harness/notes/receipts/H3a.json for the exact symbol list: 68 symbols, two-producer verdict, 0 conflicts. Settled evidence — do not re-probe it (R46 discharged by H3a). Wire it to a control the artist can reach.

**PART B — rkill-based render stop.** This is the part R48 wrongly closed.
  1. Probe `rps` first: it lists background render processes and their PIDs. A stop that cannot identify WHAT it is stopping is not a stop.
  2. `rkill` takes a process_pattern, not a node reference. Establish how a RopNode maps to a killable process — that mapping is the real engineering here, and if it cannot be made reliable, THAT is the finding and the leg reports it rather than shipping something that kills the wrong render.
  3. **MANDATORY FINDING: what does rkill do to a partially-written frame?** It is process-level and blunt. A half-written EXR, a corrupt .usdc, a lock file left behind — probe it against a real render and report what you find. **Do not ship a stop that silently corrupts output.** If the answer is bad, an honest "stop leaves a partial frame, here is how to detect it" is a better deliverable than a clean-looking button.
  4. `hou.IPRViewer.killRender` exists and is a DIFFERENT case — interactive preview, not a ROP render. Note whether it is the right tool for IPR and leave it there.

**PART C — emergency halt.** Surface EmergencyProtocol.trigger_emergency_halt as a SECOND, DISTINCT control (R29). Not a rename of Stop, not competing with it in the rail.

=== WHAT NOT TO TOUCH ===

`_on_stop` aborts the agent loop cooperatively and is HONEST about it — it refuses to claim idle and waits for the worker. It was written before this relay and is better than what would replace it. **Do not replace it. Do not make Stop always-visible** — state-gating is correct, and a Stop shown when nothing is running is the same lie as a consent gate that does not gate (R18).

=== ORACLE ===

  TOPS cancel reachable from the panel, demonstrated against a REAL cook
  rkill path demonstrated against a REAL render, with the RopNode->process mapping shown
  partial-frame behaviour PROBED and reported, whatever the answer
  emergency halt present as a distinct control, not a renamed Stop
  _on_stop unchanged in behaviour
  every pin fails against its mutation (R34); readers calibrated (R60)
  gate suite green, count strictly increases or holds
  v5.34.0 known-limitations wording corrected: a render CAN be stopped via rkill;
    what is missing is a RopNode-level verb and a working hou.ActiveRender

=== STANDING ===
Probes beat memory. Never push, never merge, never tag.
Write harness/notes/receipts/H3b.json (receipt/v1, model + settings_profile per R25).
