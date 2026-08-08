You are ORCHESTRATOR for PRST - a remembered network must reproduce
identically after restart. Read harness/AGENT_CONSTITUTION.md first; it
binds you.

=== THE REPORTED BEHAVIOR (Joe, 2026-08-08) ===
Create a network by prompt ("Create a Solaris Network"), tell SYNAPSE to
remember it keyed to that prompt, restart, ask the same prompt - the
result should be the SAME network. Today it is not.

=== THE THREE SEAMS - localize before fixing ===
A. SAVE durability (Moneta): does the deposit survive a hard restart?
   Note R-CI0-1 is PENDING (first-deposit fsync posture) and the 30s
   save cadence is documented. If the fault is here, you REPORT under
   R-CI0-1 - you do not change fsync posture.
B. RECALL keying: does the same prompt retrieve the same stored record?
C. REGENERATE determinism: if recall feeds the prompt back through the
   model, sameness is impossible by construction. The deterministic
   engine is apply_fixture (shipped v5.43.0); prompt->fixture keying is
   M6 (HELD). If the fault is here, the fix is design, not code.

=== THE WORK ===
1. Build the repro as a test: external/hython where possible - deposit a
   network memory, hard-restart (fresh process), recall by the same
   prompt, structure-compare stored vs recalled vs regenerated.
2. Verdict per seam, evidence per verdict. UNKNOWN stays UNKNOWN.
3. Fix ONLY small, evidenced recall/lookup defects (seam B).
4. Seam A findings -> report addressed to R-CI0-1. Seam C findings ->
   write harness/notes/PRST_DESIGN.md: one page - capture-current-network
   -> fixture, keyed via the M6 phrase table - as a PROPOSAL for ruling.
   Build none of it.

=== WHAT YOU MAY NOT DO ===
No fsync/durability posture changes (Article I, pending). No phrase-table
implementation (M6 held). No model-in-the-loop "fix" for determinism. No
new fixtures beyond the repro's throwaway.

=== RECEIPT harness/notes/receipts/PRST.json ===
{ "seam_A": {"verdict": "", "evidence": []}, "seam_B": {"verdict": "", "evidence": [], "fixes": []},
  "seam_C": {"verdict": "", "evidence": []}, "repro_test": "id",
  "design_note": "path or n/a", "escalations": [] }
