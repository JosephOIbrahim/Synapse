You are ORCHESTRATOR for BASE - close the two dispatch gaps in
harness/orchestrate.ps1. Read harness/AGENT_CONSTITUTION.md first; it
binds you.

=== WHY ===
Two legs this month (M5b, CI0) hit wrong-base dispatch: the orchestrator
cuts worktrees from its OWN HEAD via `worktree add -b` and ignores the
per-leg "base" field that already exists in legs.json data (CI0 carries
"base": "master" - decorative today). Launch line :329 also passes no
model flag, so leg model = terminal default.

=== DOCTRINE: WRONG BASE MEANS HALT, NOT SELF-REPAIR ===
A leg that finds itself on the wrong base STOPS. It does not rebase, does
not reset, and does not write a line. It records what it found in the
receipt under drift[] and halts. Self-repair on a wrong base is worse than
no run: a "clean" run there silently reimplements the leg's own
dependencies from scratch (M5b on feat/repair-heats-01, 2026-08-06, was
stopped by hand for exactly that). Item 1 below closes the gap at the
orchestrator; until it lands, every leg brief carries this halt rule as
its first action, and the fix here must never turn a halt into a rebase.

=== THE WORK ===
1. Per-leg base: when a leg declares "base", cut the worktree from that
   ref (`git worktree add -b <branch> <wt> <base>`). No "base" field ->
   current behavior (own HEAD). Refuse-if-branch-exists stays exactly.
2. Model passthrough: when the manifest declares top-level "model", append
   `--model $($manifest.model)` to the claude launch at line ~329. Absent
   -> current behavior. Same pattern as the existing effort passthrough.
3. Verify with the built-in testability hook: -DryRun -ManifestPath
   against a throwaway control manifest under harness/notes/ exercising
   (a) leg with base, (b) leg without, (c) manifest with model, (d)
   without. Capture the four resolved launch/worktree lines as evidence.

=== PERMISSION SURFACE - READ BEFORE EDITING ===
relay-settings.json does not allow Edit(harness/orchestrate.ps1). If your
session lacks the permission, STOP and report - correct dispatch is the
CTO session or a per-leg profile adding that one Edit line. Do not widen
anything else.

=== WHAT YOU MAY NOT DO ===
No new flags, no refactor, no touching TRUST/receipt/notification logic.
Surgical: two passthroughs plus their DryRun evidence.

=== RECEIPT harness/notes/receipts/BASE.json ===
{ "base_honored_at": "file:line", "model_passthrough_at": "file:line",
  "dryrun_evidence": ["4 resolved lines"], "behavior_unchanged_without_fields": true|false }
