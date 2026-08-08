You are ORCHESTRATOR for FID - unmeasured fidelity renders UNKNOWN. Read
harness/AGENT_CONSTITUTION.md first; it binds you.

=== GOVERNING LAW (standing, not a new ruling) ===
The house rule, documented in face_token.py: "Unobtainable renders as
UNKNOWN, never zero and never an estimate." Spawned by VER1's receipt -
sites already pinned by CTO-session probe 2026-08-08.

=== THE VIOLATION ===
python/synapse/panel/gate_widget.py:388 constructs the label as literal
'Fidelity 1.0' before anything is measured - a fabricated perfect score,
same claim-without-observation class as the hardcoded success=True.
gate_widget.py:598 updates via 'Fidelity {f:.1f}'.format(f=fidelity)
unconditionally - no UNKNOWN branch exists on the update path either.

=== THE WORK ===
1. Construct-time: label and dot render UNKNOWN (neutral styling, not
   green, not red) until the first observed update arrives.
2. Update path (:598): when fidelity is None / absent from the payload,
   render UNKNOWN - never a formatted number, never a default. Trace the
   feeder dict around :578 ('Expected keys: session_fidelity, ...') and
   remove any fabricated .get default on the way in.
3. Tests: (a) constructed widget, no update -> reads UNKNOWN; (b) update
   with a real value -> numeric; (c) update missing session_fidelity ->
   UNKNOWN, no crash, no default.

=== WHAT YOU MAY NOT DO ===
Do not touch the latching-floor semantics in memory/agent_state.py - the
floor plus its WHY stamp is separate, already attributed, and correct.
No styling redesign beyond the neutral UNKNOWN state.

=== RECEIPT harness/notes/receipts/FID.json ===
{ "construct_fix": "file:line", "update_fix": "file:line",
  "feeder_default_removed": "file:line or none-found",
  "tests": ["id-a","id-b","id-c"] }
