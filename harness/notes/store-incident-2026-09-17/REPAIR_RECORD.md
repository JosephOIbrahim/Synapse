# Memory store repair — 2026-09-17

INTENT.md §6 record: *"Each completed or interrupted operation MUST have a record connecting
the engagement and proposal to its actual changes, execution route, verification results, and
recovery status."*

This record exists because a completion audit found none: `grep -l 'repair|memory.jsonl|degraded'
.synapse/provenance/*.json` returned **0 of 5012**. The repair below was performed before this
record was written. That ordering was itself the violation.

---

## Identity

| Field | Value |
|---|---|
| Date | 2026-09-17, 15:53 local |
| Build | Houdini 22.0.400 · SYNAPSE v5.74.0 · PID 54668 |
| Operator | Claude Opus 5, at the artist's explicit instruction ("fix the store") |
| Execution route | Out-of-process Python against the file on disk, then an in-process `_load()` re-derivation |
| Target | `%LOCALAPPDATA%/Temp/houdini_temp/untitled/.synapse/memory.jsonl` |

## Starting state

The store had been **DEGRADED since 2026-09-15 15:09** and refused every write for ~2 days.

- 846 lines, 841 distinct ids, 5 ids each present twice with differing canonical JSON
- Trigger predicate: `MemoryStore._load` (`store.py:355-362`) raises `conflicting duplicate
  memory identity` when a repeated id's `json.dumps(data, sort_keys=True)` differs
- One such line is sufficient — `store.py:396-401` degrades on a non-empty unreadable list

Conflicting ids, all adjacent line pairs with **identical content**, second copy metadata-stripped:

| id | lines | stripped in second copy |
|---|---|---|
| `mem_596cf755cfbf` | 1, 2 | tags(4)→[] · hip_file→'' · frame 1→None · hip_version 19→0 · source ai→auto |
| `mem_d8486c1c0ee0` | 6, 7 | tags(4)→[] · hip_file→'' · frame→None · source ai→auto |
| `mem_ae38a9b2736d` | 33, 34 | tags(5)→[] · hip_file→'' · frame→None · source ai→auto |
| `mem_adf58a52df9a` | 36, 37 | tags(6)→[] · hip_file→'' · frame→None · source ai→auto |
| `mem_d42816c8963c` | 39, 40 | tags(7)→[] · hip_file→'' · frame→None · source ai→auto |

## Change applied

For each conflicting id, the record with **richer metadata** was kept and the stripped duplicate
dropped. Five lines removed; every surviving line is the original ciphertext, byte-for-byte —
nothing was re-encrypted or rewritten.

**Selection rule was deliberately not last-write-wins.** The natural append-log instinct would
have kept the *later* line, which in all five cases was the stripped one, destroying 26 tags that
feed the retrieval index.

```
sort key = (len(tags), hip_file non-empty, source != 'auto', frame is not None, hip_version)
```

## Verification

| Check | Result |
|---|---|
| Post-repair load | 841 records / 841 distinct ids / 0 conflicts / 0 unreadable |
| Live store re-derivation | `_degraded_load` reset, `_load()` re-run against repaired bytes → False |
| Write guard | `_require_writable_load()` returns without raising |
| Production writes resumed | 841 → 846 → 862 → 865 records within 30 minutes |
| Cold-load, fresh process | repaired: **clean / writes PERMITTED** |
| Cold-load, paired control | pre-repair backup: **DEGRADED / writes REFUSED** |

The control arm is load-bearing. Without it, "the repaired file loads clean" is an untested
green — the gate would pass on a store that could not fail.

## Recovery status

| Artifact | Path |
|---|---|
| Pre-repair snapshot (mirror) | `.synapse/memory.jsonl.pre-repair-1789674797` |
| Primary store backup | `~/.synapse/backups/moneta-2026-09-17-preprune/` (9.1 MB, sha `f914a51c18e4b45b10b8984d`) |
| Auto-quarantine copies | 11 × `.degraded-load-*` |
| Producer scripts | `analyze.py` / `repair.py`, this directory |

### Correction — the pre-repair snapshot is NOT a restore point

An earlier draft of this record said *"fully reversible: restore the pre-repair backup over
`memory.jsonl`."* **That was wrong, and acting on it would re-break the store.**

That file still contains the five conflicting duplicate pairs. Copying it back over `memory.jsonl`
re-enters DEGRADED mode on the next load, refuses every write again, and restarts the quarantine
copy spray. It is also 253+ records behind the live store. It is **forensic evidence**, not a
rollback.

There is no clean rollback to the pre-repair state, and there does not need to be: the repair is
additive-safe — it only removed lines whose ids survive, verified field-by-field across all 841.

Two further facts established by the adjudication pass, both of which matter more than the copies:

- **All twelve files are byte-identical** — the 11 `.degraded-load-*` *and* the `pre-repair-*`
  snapshot share sha `2d8cc01b70b265fcbab7ec86a11683bf82d2ba3b50ad422aae3083b29f5ff120`. The
  "clean backup" is the twelfth copy of one state, not a distinct one.
- **`~/.synapse/encryption.key` is a single point of failure.** 44 bytes, fingerprint `6aa8f313`,
  one copy on the machine, gitignored (`*.key`). Every line of every store file is Fernet
  ciphertext. Without that key all of the above are dead bytes, and it sits in a directory nobody
  looks at during a store cleanup.

### The store is not scratch

It resolves to `%LOCALAPPDATA%/Temp/houdini_temp/untitled/` only because the scene is unsaved. Its
contents are not scratch: 20 distinct `hip_file` values spanning `D:/HOUDINI_PROJECTS_2025`
(Alien_Invasion_Western, Alien_Spaceship_Saucer v075B/v076/v077), `D:/HOUDINI_PROJECTS_2026`,
`D:/MODEL_COLLECTION`, and eight OneDrive revisions — months of cross-project memory living in the
directory Windows Storage Sense and Disk Cleanup target by policy.

Saving the scene does **not** move it. `scene_memory.py:259` resolves an unsaved hip to
`unsaved_memory_base()` and a saved hip to the `.hip`'s own folder — a different, empty store. No
migration code exists in the tree.

---

## What this repair did NOT fix

Stated plainly, because a record that hides its own limits is worse than none.

1. **It repaired the mirror, not the primary.** Moneta is the primary store; the JSONL is a
   dual-write mirror. All five duplicate ids **remain resident** in `.moneta/snapshot.json`.
2. **253 records exist only in Moneta**, 245 of them written inside the outage window while the
   mirror refused. No Moneta→JSONL backfill exists (`backfill.py` runs one direction only).
3. **4 records exist only in the JSONL**, including `mem_e2e9749cb3c3` — the decision binding
   *"Create a Solaris Network"* to the v4 recipe. Absent from the primary and from `cortex_root.usda`.
4. **The producer is still armed.** `MemoryStore.add()` (`store.py:529-553`) appends on a
   conflicting id with no collision check. Threshold to re-degrade: **one write**.
5. **Nothing detects it.** `_degraded_load` has three readers, none of them a health, doctor,
   panel or MCP surface. `write_plane.store_health()` returned OK throughout the two-day outage.

Full findings: `VERDICT.md`, this directory.
