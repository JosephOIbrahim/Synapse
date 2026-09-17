# Operations log — store repair, 2026-09-17 Houdini-closed window

INTENT.md §6: *"Each completed or interrupted operation MUST have a record connecting the engagement
and proposal to its actual changes, execution route, verification results, and recovery status."*

Every operation below ran with **Houdini closed** — verified `none found` for
`houdini|hython|husk|mplay|hindie`, and each tool independently enforced its own liveness and
quiet-period refusal before writing. A live `save()` rewrites these files whole from memory and would
have silently discarded every repair here.

---

## Pre-flight

| | |
|---|---|
| Backup | `~/.synapse/backups/preB2-20260917-174714/` |
| Contents | `.moneta/` (primary), `memory.jsonl` (mirror), `key.fingerprint`, **`encryption.key.COPY`** |
| Verified | `snapshot d3e8d23172c6b3c6933cbe16a0a34c35` · `mirror 4d879d527e62de8c9b9722361f1ced6c` — src == bak |

The encryption key was copied deliberately. It is 44 bytes, exists in exactly one place, is gitignored
(`*.key`), and every line of every store file is Fernet ciphertext. Without it every backup discussed
in this incident is dead bytes, and it lives outside the directory anyone inspects during a cleanup.

---

## OP-1 — B2, primary repair

`python -m synapse.memory.primary_repair <untitled/.synapse> --apply --backup-dir ~/.synapse/backups/preB2-…`

| | |
|---|---|
| Liveness | `houdini processes: none found` · `snapshot last touched 125.1s ago` · verdict **clear** |
| Before | 1136 rows · 1131 distinct ids · 0 unreadable |
| Change | dropped 5 rows — the metadata-stripped twin of each of the 5 audit-known ids |
| After | **1131 rows · 1131 distinct ids · 0 unreadable** |
| Backup | `.moneta/snapshot.json.pre-primary-repair-1789681779` (+ copy in the backup dir) |
| Result | **APPLIED and verified** by read-back |

**Mirror cross-check: agreed 5/5.** This tool and the manual JSONL repair performed hours earlier, by
independent logic, selected the *same* surviving record in all five cases. Two independent repairs,
one answer.

The tool refused twice before this run — at 50.0s and 71.9s and 90.1s after Houdini's `atexit` flush —
because its quiet period is 120s. Those refusals are the gate working, not a fault.

## OP-2 — B5, Moneta → JSONL backfill

`python -m synapse.memory.backfill_from_moneta <untitled/.synapse> --apply`

| | |
|---|---|
| Divergence measured | primary 1131 · mirror 882 · intersection 878 |
| only in PRIMARY | **253** — inside outage window **253**, before **0**, after **0** |
| by type | feedback=219 · note=18 · action=16 |
| only in MIRROR | 4 — reported, **not written** (needs `add_durable_if_absent` + the Moneta URI lock; out of this tool's lane) |
| Change | wrote 253 records into the mirror |
| Verify | fresh cold load: `degraded=False` · `records 1135 = expected 1135` |
| Backup | `memory.jsonl.pre-backfill-1789681905` |
| Result | **WROTE 253, verified by cold load** |

**All 253 fall inside the outage window and none outside it.** That is causal proof rather than
correlation: these are precisely the writes the mirror refused while degraded, and nothing else. The
ungated automatic prune disarmed in this same PR was armed over exactly this class of record — every
one of them existed in a single substrate.

## OP-3 — mirror repair, two dormant project stores

`python harness/notes/store-incident-2026-09-17/mirror_repair.py <dirs> --apply`

| Store | Before | After | Conflicting ids |
|---|---|---|---|
| `D:/…/Houdini21_Alien_Spaceship_Saucer/.synapse` | 58 lines / 39 ids | **39 lines / 39 ids / 0 conflicts** | 1 (`mem_2f1bc0bbb623`, occupying 20 lines) |
| `D:/…/SYNAPSE_DEMO_v0001/scripts/.synapse` | 13 lines / 5 ids | **5 lines / 5 ids / 0 conflicts** | 3 |

Both are **Shape B** — timestamp-only collisions with byte-identical content, fossils of the historical
content-only id formula that `models.py:157-162` already fixed. No content was lost; the repeated
lines were the same memory logged repeatedly under one id.

Backups: `memory.jsonl.pre-mirror-repair-1789682248` in each directory.

---

## Deliberately NOT repaired

| Store | Why |
|---|---|
| `~/.synapse/backups/w1_2026-08-09/10_repo_untitled_hip__dotsynapse` | **It is a backup.** Deduping it destroys the only reason it exists — to hold the original bytes. |
| `~/.synapse/backups/w1_2026-08-09/POST_MIGRATION_canonical_…` | Same. 516 lines / 403 ids / 15 conflicts, left intact. |
| `C:/Users/User/SYNAPSE/untitled.hip/.synapse` | An orphan of a past defect — a directory literally named `untitled.hip`, created next to the process working directory. The log's own warning names this shape: *"Stores previously written next to the process working directory are NOT carried over."* Nothing reads it. |
| `D:/…/MPM_MASTERCLASS_FILES/.synapse` | Pre-migration **plaintext** schema, no `SYNAPSE_ENC_V1:` prefix, missing all four identity fields. **Zero recoverable records.** No dedupe repair can fix it. |

---

## Final state — verified by cold load through `MemoryStore`

```
Houdini21_Alien_Spaceship_Saucer   degraded=False  writable=True  records=39
SYNAPSE_DEMO_v0001/scripts         degraded=False  writable=True  records=5
untitled (primary + mirror)        degraded=False  writable=True  records=1135
```

Stores refusing writes: **6 → 3**, and all three remaining are deliberate exclusions above, not
failures.

## Still open

1. **4 mirror-only records**, including `mem_e2e9749cb3c3` — the decision binding *"Create a Solaris
   Network"* to the v4 recipe. Present in the mirror, absent from the primary and from
   `cortex_root.usda`. Depositing them needs `add_durable_if_absent` plus the Moneta URI lock. Named
   here so it is not forgotten.
2. **`MPM_MASTERCLASS_FILES` is unrecoverable** by any dedupe. If those records matter they need a
   schema migration, not a repair.
3. The primary now holds 1131 rows against the mirror's 1135. That delta **is** item 1 — it is
   accounted for, not drift.
