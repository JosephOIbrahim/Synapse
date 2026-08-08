You are ORCHESTRATOR for STAT - make statusline.py worktree-aware
(R-CI0-5). Read harness/AGENT_CONSTITUTION.md first; it binds you.

=== GATE ===
HELD until Joe rules R-CI0-5 (see harness/NEXT_SESSION.md). Ruled fix
direction: in a linked worktree .git is a FILE containing a "gitdir: "
pointer, not a directory - statusline currently shows '?' branch and 4
phantom red tests in every agent worktree. Read the pointer.

=== THE WORK ===
1. harness/statusline.py: when .git is a file, parse the gitdir: line and
   resolve HEAD/branch through the linked gitdir. Directory case unchanged.
2. The 4 phantom red tests trace to the same misresolution - verify they
   disappear in a worktree after the fix (evidence: before/after output
   captured from a real linked worktree, not reasoned about).
3. Keep the suite-figure stamp path untouched: it is piped, never typed.

=== PERMISSION SURFACE - READ BEFORE EDITING ===
relay-settings.json does not allow Edit(harness/statusline.py) (allow list
covers python/, tests/, harness/notes/, checks.py, tasks.json only). If
your session lacks the edit permission, STOP and report - do not work
around it. Correct dispatch: CTO session, or a per-leg settings profile
with Edit(harness/statusline.py) added. Gate-refuse in-band is correct
behavior, not failure.

=== WHAT YOU MAY NOT DO ===
No edits outside harness/statusline.py. No suppressing the phantom reds by
filtering output - fix the resolution, not the symptom.

=== RECEIPT harness/notes/receipts/STAT.json ===
{ "gitdir_fix": "file:line", "before": "<worktree statusline output>",
  "after": "<worktree statusline output>", "phantom_reds_gone": true|false,
  "tests_touched": [] }
