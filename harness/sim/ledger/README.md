"""Ledger format and rules for the SIM plane.

One file per problem cluster:

    <cluster_id>.cluster.json    the cluster declaration (written once)
    <cluster_id>.attempts.jsonl  one AttemptRecord per line, append-only

Rules that the store enforces and this file explains:

1. **Append-only.** There is no update and no delete. A correction is a new
   record that supersedes the old one by timestamp and verdict.
2. **Validate on read as well as write.** Each line is parsed back into a
   record on read, so a line that no longer parses raises instead of being
   trusted.
3. **No concurrent writers.** A per-cluster lock file is created exclusively for
   the duration of an append. A second writer is refused, not merged.
4. **Declare before you record.** An attempt for an undeclared cluster is
   refused, so a typo cannot create a cluster nobody can find.

What does not belong here: scene state, tool output, conversation content, or
anything a runtime turn needs. This ledger is read by the metrology plane only.
"""
