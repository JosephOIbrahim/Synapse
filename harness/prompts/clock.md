You are ORCHESTRATOR for CLOCK - the three zero-elapsed-time Windows
tests (R-CI0-3). Read harness/AGENT_CONSTITUTION.md first; it binds you.

=== GATE ===
HELD until Joe rules R-CI0-3 as FIX. If ruled LEAVE, this leg is retired
unrun - do not dispatch.

=== WHY ===
Three tests fail only on Windows dev (~15ms system clock granularity),
never on CI ubuntu/macos. Real fix per CI0: time.perf_counter() in the
routing and session product code - two subsystems. Product fix, not a
test fix.

=== THE WORK ===
1. Identify every elapsed-time measurement in the two subsystems that
   uses a wall-clock source (time.time() or equivalent). Swap measurement
   deltas to time.perf_counter(). Timestamps that are genuinely
   wall-clock (logging, persistence) stay wall-clock - do not blanket
   replace.
2. The three failing tests must pass on Windows unmodified. If any test
   itself encodes a wall-clock assumption, that is a finding for the
   receipt, not a license to edit the test.
3. Evidence: the three test ids green on this Windows machine, plus the
   list of swapped sites.

=== WHAT YOU MAY NOT DO ===
No test edits. No sleep() padding. No tolerance widening - the fix is a
correct clock source, not a looser assertion.

=== RECEIPT harness/notes/receipts/CLOCK.json ===
{ "swapped_sites": ["file:line"], "wallclock_kept": ["file:line"],
  "tests_green_on_windows": ["id1","id2","id3"] }
