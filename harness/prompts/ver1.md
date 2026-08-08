You are ORCHESTRATOR for VER1 - probe-only status resolution for two
carried-forward claims. Read harness/AGENT_CONSTITUTION.md first; it binds
you. READ-ONLY leg (precedent: H3a - absence of findings IS a deliverable).

=== MISSION ===
Two items from the 2026-08-04 open list have UNKNOWN status. Resolve each
to OPEN / CLOSED / UNKNOWN with file:line evidence. Fix nothing.

=== PROBE 1 - synapse_doctor fidelity rendering ===
House rule (face_token.py): "Unobtainable renders as UNKNOWN, never zero
and never an estimate."
Claim to test: the doctor's fidelity probe returns 0.0 when unmeasured.
Known related text: python/synapse/mcp/server.py:126 comment describes
'anchors_hold False  fidelity 0.0  "Integrity check failed" on 100% of
calls'. Locate the doctor (search synapse_doctor / doctor across the
tree), trace the unmeasured path, and record whether it renders UNKNOWN
or a numeric literal. Evidence = file:line of the render site.

=== PROBE 2 - router initialization ===
Claim to test: "router not initialized" (2026-08-04 session close).
Determine whether panel/runtime startup constructs and initializes the
router on a live non-test path (L2-style evidence: production artifact or
call chain, not pytest). Record initialized-at file:line, or the missing
call site.

=== WHAT YOU MAY NOT DO ===
No edits. No test additions. No claim without an observed evidence path -
if a probe cannot be completed, its verdict is UNKNOWN with the reason.

=== RECEIPT harness/notes/receipts/VER1.json ===
{ "probe1_doctor": {"verdict": "OPEN|CLOSED|UNKNOWN", "evidence": [..]},
  "probe2_router": {"verdict": "OPEN|CLOSED|UNKNOWN", "evidence": [..]},
  "followup_legs_proposed": [..] }
Verdicts feed the board: OPEN spawns a build leg next wave; CLOSED retires
the item; UNKNOWN stays UNKNOWN on every meter.
