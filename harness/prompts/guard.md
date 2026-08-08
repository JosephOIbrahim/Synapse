You are ORCHESTRATOR for GUARD - fix the shot_layers/ write-site root
cause. Read harness/AGENT_CONSTITUTION.md first; it binds you.

=== WHY ===
TIDY 2026-08-07 root-caused repo-root tree-dirtying: a missing
absolute-path guard at python/synapse/.../solaris_compose_tools.py lines
133-136 writes shot_layers/ relative to the process CWD. The gitignore
append (TIDY-19/20) covers the symptom; this leg fixes the cause.

=== THE WORK ===
1. Read solaris_compose_tools.py:120-160 first. Add the guard: resolve the
   layer output path to an absolute, sanctioned location before any write;
   a relative/unsanctioned path is an error raised to the caller, not a
   silent redirect. Match the module's existing error style.
2. Regression test in tests/: invoking the compose path from a foreign CWD
   must NOT create shot_layers/ at that CWD. Assert on the observed
   filesystem, not on a mocked path join.
3. If lines 133-136 have drifted since TIDY's report, follow the code, not
   the line numbers - cite the actual site in the receipt.

=== WHAT YOU MAY NOT DO ===
No .gitignore edits (that is TIDY-19/20, human-gated). No relocation of
existing shot_layers/ content. No API change to the compose tools -
callers see the same signature, plus one honest failure mode.

=== RECEIPT harness/notes/receipts/GUARD.json ===
{ "guard_at": "file:line", "test_id": "tests/...::...",
  "foreign_cwd_clean": true|false, "drift_note": "" }
