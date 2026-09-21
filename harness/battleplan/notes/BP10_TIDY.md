# BP10 Worktree and Ledger Census

**Date:** 2026-09-21 · **Producer:** BP10-TIDY (T1, read-only battleplan wave agent) · **Sources:** git worktree list, receipt files, jev ledger directory

---

## BP10 Worktrees

| Worktree | Branch | HEAD | Status |
|---|---|---|---|
| bp10-bench | `bp10/bench` | `cededc17` | clean |
| bp10-corpus | `bp10/corpus` | `b32a877c` | dirty (7 files) |
| bp10-crux | `bp10/crux` | `1cafa8f7` | clean |
| bp10-guides | `bp10/guides` | `b84bf8e5` | clean |
| bp10-scaffold | `bp10/scaffold` | `845da18e` | clean |
| bp10-tidy | `bp10/tidy` | `816cd36c` | clean |
| **Count** | **6** | — | — |

**Producer path:** `git worktree list --porcelain` at C:/Users/User/SYNAPSE; HEAD via `git -C <worktree> rev-parse --short HEAD`; clean status via `git -C <worktree> status --porcelain`

---

## BP10 Receipts

| Leg | Status | Evidence |
|---|---|---|
| BP10-SCAFFOLD | green | `harness/notes/receipts/BP10-SCAFFOLD.json` line 3 |
| BP10-CORPUS | NO RECEIPT | receipt file absent at `harness/notes/receipts/BP10-CORPUS.json` |
| BP10-GUIDES | NO RECEIPT | receipt file absent at `harness/notes/receipts/BP10-GUIDES.json` |
| BP10-BENCH | NO RECEIPT | receipt file absent at `harness/notes/receipts/BP10-BENCH.json` |
| BP10-CRUX | NO RECEIPT | receipt file absent at `harness/notes/receipts/BP10-CRUX.json` |
| BP10-TIDY | green_with_findings | `harness/notes/receipts/BP10-TIDY.json` line 3 |
| **Count** | **6** | 2 receipts on this branch (SCAFFOLD, TIDY) |

**Producer path:** directory scan at `harness/notes/receipts/BP10-*.json`; status field read from each via grep `'"status"'`

**Scope:** this scan reads the `bp10/tidy` branch, which forked from master at `816cd36c`. The CORPUS, GUIDES, BENCH and CRUX receipts exist on their own `bp10/*` branches and are not merged here, so NO RECEIPT means absent on this branch, not absent from the wave. The ledger scan has the same scope.

---

## Jev Ledger Row Counts by Guard

| Guard | Ledger File | Row Count | Status |
|---|---|---|---|
| route | `harness/jev/ledger/bp10.route.jsonl` | 6 | ✓ file present |
| team | `harness/jev/ledger/bp10.team.jsonl` | 6 | ✓ file present |
| screen | `harness/jev/ledger/bp10.screen.jsonl` | 8 | ✓ file present |
| edge | `harness/jev/ledger/bp10.edge.jsonl` | 5 | ✓ file present |
| drift | `harness/jev/ledger/bp10.drift.jsonl` | 8 | ✓ file present |
| rerank | `harness/jev/ledger/bp10.rerank.jsonl` | UNKNOWN | ✗ file absent |
| harvest | `harness/jev/ledger/bp10.harvest.jsonl` | UNKNOWN | ✗ file absent |
| bench | `harness/jev/ledger/bp10.bench.jsonl` | UNKNOWN | ✗ file absent |
| **Count** | **8** | **33 rows in 5 files on disk; 3 UNKNOWN** | — |

**Producer path:** directory scan at `harness/jev/ledger/bp10.*.jsonl`; row counts via `wc -l` on each file present. Missing files (rerank, harvest, bench) marked UNKNOWN per constitution rule: "Unobtainable renders UNKNOWN — never zero, never an estimate, never a pass."

---

## Validation

- **Worktree table count line:** 6 worktrees listed, 6 rows before count line ✓
- **Receipt table count line:** 6 legs listed, count line reads 6
- **Ledger table count line:** 8 guards listed, count line reads 8; 3 of the 8 are UNKNOWN per constitution

Every number carries a producer path. No UNKNOWN is a pass; three missing ledger files are recorded as unobtainable.
