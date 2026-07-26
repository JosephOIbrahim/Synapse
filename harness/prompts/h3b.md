You are ORCHESTRATOR for H3b — TOPS cancel. Read harness/AGENT_CONSTITUTION.md first; it binds you. Then read rulings R44, R48 and R49 in harness/notes/CTO_RULINGS_01.md.

THIS LEG WAS HELD BY RULING AND IS RELEASED ONLY BY JOE. If you are reading this, he released it. Its scope is NOT what its original name suggests — read the next section before anything else.

=== THE SCOPE CHANGED. READ THIS FIRST. ===

H3b was scoped as "build cook-cancel". H3a's probe made that impossible and the ruling re-scoped it (R48).

H3a-F1, VERIFIED-RUNTIME on 22.0.368, confirmed independently against SideFX's own reference:

  Houdini 22.0.368 exposes NO API to cancel, abort, interrupt or kill an
  in-flight hou.RopNode.render().

The complete public method list is addRenderEventCallback, bypass, inputDependencies, isBypassed, isLocked, setLocked, removeAllRenderEventCallbacks, removeRenderEventCallback, render. Nothing inherited from OpNode/Node/NetworkItem reaches a running render. hou.InterruptableOperation wraps YOUR OWN Python block and cannot reach into a render already blocking in C++. addRenderEventCallback is observation, not control.

THE RENDER HALF IS CLOSED AS NOT-IMPLEMENTABLE. It is a SideFX ask (docs/SIDEFX_ASK_H22_DRAFT.md), not deferred work, and it must stop being described as either. DO NOT ATTEMPT IT. Do not invent a workaround — killing a thread, a process, or a subprocess is not a cancel and will corrupt scene state.

=== WHAT IS ACHIEVABLE, AND IT IS REAL ===

H3a-F2: the TOPS/PDG cancel surface IS COMPLETE on 22.0.368 and carries a direct node-level verb the tree does not use. 68 symbols carry a two-producer verdict with 0 conflicts. Read harness/notes/receipts/H3a.json for the exact symbol list — it is settled evidence, do not re-probe it (R46's obligation was discharged by H3a).

WORK:

1. Wire TOPS cancel through to a control the artist can reach. The verb exists and is unused. This is the entire deliverable.

2. Surface EmergencyProtocol.trigger_emergency_halt as a SECOND, DISTINCT control (R29) — not a rename of Stop, not competing with it in the rail. Stop aborts the agent loop cooperatively and is HONEST about it: _on_stop refuses to claim idle and waits for the worker. DO NOT REPLACE IT. It was written before this relay and is better than what would replace it.

3. Do NOT make Stop always-visible. State-gating is correct — a Stop shown when nothing is running is the same lie as a consent gate that does not gate (R18).

4. The panel has a working test surface now (RES fixed the residency; R30 established tests/panel/ runs under hython3.13). Pins are required, they must fail against their mutation (R34), and their READER must be calibrated too (R60).

=== THE HONEST LIMIT TO STATE IN YOUR RECEIPT ===

After this leg, an artist mid-KARMA-RENDER still has a Stop that cannot stop the render. TOPS cancel does not change that. Say so plainly in the receipt and do not let the leg's success obscure it — v5.34.0's Known-limitations wording already needs correcting for exactly this reason (R48 item 3), and that correction is IN SCOPE here.

=== ORACLE ===

  TOPS cancel reachable from the panel, demonstrated against a REAL cook
  emergency halt present as a distinct control, not a renamed Stop
  _on_stop unchanged in behaviour
  every pin fails against its mutation; readers calibrated
  gate suite green, count strictly increases or holds
  v5.34.0 known-limitations wording corrected: Houdini exposes no render-cancel
    API, and TOPS cancel now exists

Never push, never merge, never tag. Write harness/notes/receipts/H3b.json (receipt/v1, model + settings_profile per R25).
