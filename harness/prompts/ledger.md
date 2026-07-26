You are ORCHESTRATOR for the LEDGER seam leg. Read harness/AGENT_CONSTITUTION.md first - it binds you.

TWO DEFECTS, both verified 2026-07-26. They are related and land together.

=== DEFECT 1: the ledger never deposits to Moneta ===

python/synapse/memory/ledger.py:275

    # Optional Moneta hook (D-5). Default no-op; Moneta is default-off (v5.10.0).
    def _deposit_to_moneta(rec: "LedgerRecord") -> None:  # pragma: no cover - no-op seam
        return None

ledger.py:329 calls it inside deposit(). It returns None. So ledger records do NOT reach Moneta, and `pragma: no cover` means no test can ever notice.

The comment says "default-off" but there is NO flag - it is a hardcoded stub. SYNAPSE_MEMORY_BACKEND=moneta is now set (commit b2c2c04) and the MonetaBackedStore is fully implemented, so the STORE works. This seam does not.

Very likely the same root as open task 2.5 - "provenance writers have NO live callers, schema built, wiring dormant". Check whether one fix closes both. If it does, say so; if it does not, say why.

WORK:
1. Read the deposit() contract at ledger.py:280-330 carefully. It is FILE FIRST (unconditional, source of truth), THEN USD (best-effort, never raises out). Moneta deposit must follow the SAME discipline: never raise out of deposit(), never make the file write conditional on Moneta.
2. Implement _deposit_to_moneta against the live adapter (synapse.memory.moneta_runtime). Use mr.moneta_available() as the guard - do NOT re-derive availability, and do NOT import moneta at module scope.
3. Remove `pragma: no cover`. A seam that cannot be covered cannot be verified.
4. Ship pins that FAIL against a deliberately broken implementation (R34 mutation standard). At minimum: a record deposited with the backend on lands in Moneta; a record deposited with Moneta unavailable still writes its file and does not raise; the mutation of returning None early makes a pin fail.

=== DEFECT 2: MONETA_SRC points at a working directory ===

The deployed package sets MONETA_SRC=C:/Users/User/Moneta/src - a live git worktree. SYNAPSE's memory substrate is therefore whatever branch is checked out plus any uncommitted files. Moneta currently has two unmerged remote branches and two untracked files at root. Checking out a branch in Moneta silently changes SYNAPSE's memory behaviour, and nothing records which version was in play.

This is a provenance hole in the substrate that now backs live memory.

WORK:
5. moneta_runtime.moneta_provenance() already reports file path and version. Version currently reads None. Make provenance record the resolved Moneta git SHA when MONETA_SRC is a git worktree - read it, do not shell out on every call, cache it.
6. Make that provenance land in the ledger record or its deposit metadata, so any memory written can be traced to the Moneta revision that wrote it.
7. Do NOT change MONETA_SRC to a pinned install. That is a packaging decision for Joe. Report the recommendation in for_ruling with the trade-off stated.

ORACLE:
  pytest -k "ledger or moneta" -> 0 failed, count strictly increases
  every new pin demonstrated to FAIL against its mutation
  gate suite holds at 4881+ with 0 failed
  no pragma: no cover remains on the seam

Write harness/notes/receipts/LEDGER.json (receipt/v1, model + settings_profile per R25). Batch decisions into for_ruling. Never push, never merge, never tag.
