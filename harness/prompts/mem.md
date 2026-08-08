You are ORCHESTRATOR for MEM - the Moneta store must fail LOUD, and open
again. Read harness/AGENT_CONSTITUTION.md first; it binds you.

=== THE DEFECT (VERIFIED-RUNTIME, PRST seam A) ===
The production store has failed to open on EVERY session since
2026-08-05 13:35 - eleven consecutive times - with
`ValueError: embedding dim mismatch: expected 384, got 256`, and each
failure SILENTLY served an empty JSONL store. Full evidence + log-line
anchors: harness/notes/PRST_SEAM_A_REPORT.md. Read it end to end first.

=== THE WORK ===
1. Fail loud, forever: an open failure must surface to the operator and
   the panel - never a silent empty-store fallback. This is the house
   rule's sibling: a dead store rendered as a working one is a claim
   asserted where nothing was observed. Regression test: open failure
   raises/reports; no code path returns an empty store as success.
2. Resolve the dim mismatch per the report's analysis - reconcile the
   configured embedder against the persisted index. Do not guess the
   mechanism; the report carries it. Preserve existing deposits - if
   migration risks data, STOP and escalate with the exact tradeoff.
3. Live proof: open succeeds on the operator's real store; one deposit +
   fresh-process recall round-trips. Evidence in the receipt.

=== WHAT YOU MAY NOT DO ===
No fsync/durability posture changes (R-CI0-1 pending, Article I). No
deleting or rewriting existing store files without escalation. No
disabling the store to make the error disappear.

=== RECEIPT harness/notes/receipts/MEM.json ===
{ "fail_loud_at": "file:line", "mismatch_resolved": "how, per report",
  "deposits_preserved": true|false, "roundtrip_evidence": "...",
  "regression_test": "id", "escalations": [] }
