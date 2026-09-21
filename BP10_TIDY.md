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
| BP10-TIDY | NO RECEIPT | receipt file absent at `harness/notes/receipts/BP10-TIDY.json` (in progress) |
| **Count** | **1 receipt on disk** | — |

**Producer path:** directory scan at `harness/notes/receipts/BP10-*.json`; status field read from each via grep `'"status"'`

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
| **Count** | **5 files on disk** | **33 rows total** | — |

**Producer path:** directory scan at `harness/jev/ledger/bp10.*.jsonl`; row counts via `wc -l` on each file present. Missing files (rerank, harvest, bench) marked UNKNOWN per constitution rule: "Unobtainable renders UNKNOWN — never zero, never an estimate, never a pass."

---

## Validation

- **Worktree table count line:** 6 worktrees listed, 6 rows before count line ✓
- **Receipt table count line:** 1 receipt on disk listed, 6 legs total (count reports disk state only) ✓
- **Ledger table count line:** 5 files on disk listed, 8 guards total; missing 3 marked UNKNOWN per constitution ✓

Every number carries a producer path. No UNKNOWN is a pass; three missing ledger files are recorded as unobtainable.
