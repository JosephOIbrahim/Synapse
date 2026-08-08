You are ORCHESTRATOR for WARN - commit the already-ruled R-M5b-1 change.
Read harness/AGENT_CONSTITUTION.md first; it binds you.

=== RULING (already made - do not relitigate) ===
R-M5b-1, ruled warn-not-refuse, never committed (harness/NEXT_SESSION.md):
an external / no-Houdini process hitting the phantom gate should WARN, not
refuse. Scout scope only. Handoff estimate: one-line change plus a
decision note, ~10 minutes.

=== THE WORK ===
1. CORRECTED 2026-08-08 (CTO-session read, receipts/M5b.json:221-228): the
   external/no-Houdini path does NOT refuse today - it silently loads the
   H21 table as authority reporting stale=false (recorded as M5b-F8). The
   ruled change keeps grounding and ADDS the warning: that path must
   report the authority as stale / prior-major instead of claiming fresh.
   Start at M5b-F8's anchor and
   tests/test_scout.py::test_pkg_table_keyed_on_running_major (second
   branch). In-Houdini behavior unchanged.
2. Write the decision note: harness/notes/R-M5b-1_warn_not_refuse.md -
   ruling text, date ruled, the one-line diff, why scout-scope only.
3. If the change is genuinely not one line, STOP at the smallest honest
   diff and report why the estimate was wrong - do not expand scope to
   make the ruling fit.

=== WHAT YOU MAY NOT DO ===
No behavior change for in-Houdini processes. No disarming of external
grounding - the fallback keeps working; the only change is that its
authority is reported honestly (stale / prior-major), never as fresh.

=== RECEIPT harness/notes/receipts/WARN.json ===
{ "change_at": "file:line", "diff_lines": N, "note_path": "harness/notes/R-M5b-1_warn_not_refuse.md",
  "inhoudini_path_untouched_evidence": "file:line or test id" }
