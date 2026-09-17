# Decision memo -- quarantine retention and the half-built Solaris scene

Produced 2026-09-17 by a 34-agent adjudication (`synapse-quarantine-and-scene-adjudication`).
Every finding was adversarially refuted before it survived; irreversible recommendations drew a
three-lens panel (data-loss / hidden-distinct-state / recovery-path). Read-only throughout --
nothing was deleted, moved, edited, or executed against the scene.

Findings tested: 15. Survived: 7. Refuted or corrected: 8.

---

# DECISION MEMO — memory store repair, quarantine cleanup, and the half-built Solaris scene

Prepared read-only. Nothing was deleted, moved, edited, or executed against the scene. Every number below I re-derived myself at 2026-09-17 ~16:20 local unless marked otherwise.

**One correction to my own work up front, because it would have sent you chasing a ghost:** my first sweep reported the repaired untitled store as DEGRADED again (2 unreadable). That was my replica being stricter than the real loader. `store.py:349-353` requires the four identity fields to be `str` and requires only `id` and `created_at` to be *truthy* — a record with `content: ""` passes. Two such records exist (L541 `mem_3b5badfa925a`, L845 `mem_7685faad1800`, both `source: "auto"`, all fields blank). **The untitled store is clean: 865 lines, 865 loaded, 0 unreadable, mtime 16:16 and still moving.** The repair held.

---

## 1. DECISION 1 — RETENTION

### Recommendation: delete the 11. No refuter found a reason it is unsafe.

Verified by hash, not by size or mtime. The directory holds exactly **two** distinct contents:

| sha256 | bytes | files |
|---|---|---|
| `2d8cc01b70b265fcbab7ec86a11683bf82d2ba3b50ad422aae3083b29f5ff120` | 1,394,474 | all 11 `.degraded-load-*` **and** `memory.jsonl.pre-repair-1789674797` — twelve files |
| `c0bc9a23e9c7273998a341a6d21f2d475c140b6e5ae9c2be7fd5727431964913` (at 16:03; **changes on every write**) | 1,408,613 | live `memory.jsonl` |

Your "clean backup" is not distinct content. It is the twelfth identical copy under a different name.

### Safe to delete — 11 files, by explicit name

In `C:\Users\User\AppData\Local\Temp\houdini_temp\untitled\.synapse\`:

```
memory.jsonl.degraded-load-1789506731
memory.jsonl.degraded-load-1789507423
memory.jsonl.degraded-load-1789508001
memory.jsonl.degraded-load-1789509778
memory.jsonl.degraded-load-1789513143
memory.jsonl.degraded-load-1789561952
memory.jsonl.degraded-load-1789585035
memory.jsonl.degraded-load-1789603251
memory.jsonl.degraded-load-1789652284
memory.jsonl.degraded-load-1789673481
memory.jsonl.degraded-load-1789674135
```

11 × 1,394,474 = **15,339,214 bytes = 14.63 MiB**.

**The one sentence:** all twelve files are byte-identical and every one of the 841 ids in the pre-repair snapshot is present in the live store — verified field-by-field across all 841, not just the 5 repaired conflicts — so the 11 hold no record, no field, and no incident timestamp that is not preserved elsewhere.

### Keep — four items, not two

1. **`memory.jsonl`** — live, 865 records, the only copy of current state.
2. **`memory.jsonl.pre-repair-1789674797`** — **forensic evidence only, NOT a restore point.** It still contains the 5 conflicting duplicate pairs. Copying it back over `memory.jsonl` re-enters DEGRADED mode, refuses all writes, and restarts the copy spray. It is also 253+ records behind the live store.
3. **`C:\Users\User\.synapse\encryption.key`** — 44 bytes, fingerprint `6aa8f313`, dated 2026-02-06. **One copy. Untracked** (`~/.synapse/.gitignore` contains `*.key`). Both jsonl files are Fernet ciphertext line-by-line and are dead bytes without it. It lives in a different directory nobody is looking at during this cleanup.
4. **`Claude outputs/store-repair/repair.py`** — the only artifact that turns (2) into a loadable store. It is untracked (`?? "Claude outputs/"` in git status) and a `git clean` would take it.

### Two mechanical warnings

**Never `rm memory.jsonl.*`.** In bash and PowerShell that glob matches 12 files and takes your keeper. In **cmd.exe** `del memory.jsonl.*` matches **13** — Windows' legacy matcher treats `name.ext.*` as matching `name.ext` with an empty extension, so in cmd that command destroys the live memory store as well. Use `memory.jsonl.degraded-load-*`, which was verified to return exactly the 11 intended files in cmd.exe, PowerShell and bash, or delete by explicit filename.

**Do not verify against a live-store hash.** The store is actively writing (846 → 850 → 862 → 865 records across this audit). Pin the 12 copies by `2d8cc01b…`; identify the live file by name and by "loads clean, 0 duplicate ids".

### Sequencing condition — do this before deleting, not after

Every item in the keep list except the key sits in `%LOCALAPPDATA%\Temp\houdini_temp\untitled\.synapse\` — Houdini's scratch tree, inside the directory Windows Storage Sense and Disk Cleanup target by policy. The parent currently holds `crash.untitled.User_32908.hiplc` and six `crash.User_*_log.txt` files from 2026-09-15 alone.

That store is **not scratch**. It holds 20 distinct `hip_file` values spanning `D:/HOUDINI_PROJECTS_2025` (Alien_Invasion_Western, Alien_Spaceship_Saucer v075B/v076/v077), `D:/HOUDINI_PROJECTS_2026/SYNAPSE_SUMMER_2026`, `D:/MODEL_COLLECTION/Astra_Saucer_Sept2026`, and eight OneDrive DISC18 revisions. It is months of cross-project memory.

Right now twelve identical copies protect it. The delete takes that to one, in the most volatile directory on the machine.

**Copy `memory.jsonl`, `memory.jsonl.pre-repair-1789674797`, and `encryption.key` to durable storage first** (not `%TEMP%`; and given the auto-push-to-public-GitHub history, not the repo). Then delete.

### One side effect to know before you act

`python/synapse/server/doctor.py:323` computes `degraded_quarantine_count = len(list(store_dir.glob("memory.jsonl.degraded-*")))`. That glob matches the 11 and does **not** match `pre-repair-*`. So the delete takes the count **11 → 0**, not 11 → 1.

Per `docs/moneta-production-harness-architecture.md:610` (`0` = OK, `≥1` = warn, `≥5` = critical) and `:623` (growth between runs → page on-call within 1 hour), a store that silently refused every write for 46.5 hours will report a perfectly clean health check the moment the files are gone. The forensic record survives independently — all 11 quarantine timestamps are in `~/.synapse/logs/synapse.log` as `Quarantined a copy of the store for recovery: <path>` at ERROR — but that log rotates (5 MiB × 3 backups; `synapse.log.2` is already gone). Capture the 11 epochs to a note if the timeline matters.

**INTENT.md §3 governs the decision itself:** *"The host MUST validate this scope. A model-supplied ownership claim, scene identity, permission, or confidence value cannot authorize an operation."* My verification establishes that the delete is lossless. It does not authorize it. There is no undo for `rm`.

---

## 2. DECISION 2 — THE SCENE

### Recommendation: **VALIDATE-FIRST, then resume.** Do not rebuild.

The finding that said "no baseline exists, do not resume, treat the nodes as artist-authored of unknown provenance" was **refuted**, and I verified the refutation first-hand.

### A complete build manifest exists

`C:\Users\User\.synapse\audit\audit_2026-09-17.jsonl` — a second, independent, hash-chained operation ledger that **kept writing normally throughout the entire degraded window**. 138 rows. Session `705e0bc64e515ee3`, **2026-09-17T19:48:17Z → 19:53:01Z**.

The earlier lane missed it because a plaintext grep returns zero hits: the ledger is Fernet-encrypted per line. That absence was an artifact of the search method, not of the data.

**Nodes created (10):**

| UTC | name | parent | type | resulting path |
|---|---|---|---|---|
| 19:48:17 | geo_assets | /obj | geo | /obj/geo_assets |
| 19:48:22 | hero_sphere | /obj/geo_assets | sphere | /obj/geo_assets/hero_sphere |
| 19:48:37 | GEO_sphere | /stage | **sopcreate** | /stage/GEO_sphere |
| 19:48:41 | MTL_matlib | /stage | materiallibrary | /stage/MTL_matlib |
| 19:50:01 | GEO_sphere | /stage | **sopimport** | **/stage/GEO_sphere1** ← renamed |
| 19:50:04 | CAM_main | /stage | camera | /stage/CAM_main |
| 19:50:13 | LGT_area | /stage | light | /stage/LGT_area |
| 19:50:16 | LGT_dome | /stage | light | /stage/LGT_dome |
| 19:50:20 | karma_settings | /stage | karmarendersettings | /stage/karma_settings |
| 19:50:24 | OUTPUT | /stage | null | /stage/OUTPUT |

Plus `create_material` at 19:51:43 — `MTL_hero`, preset `polished_metal`, on `/stage/MTL_matlib`, which returned `matlib_path: "/stage/MTL_hero"` and `material_usd_path: "/materials/MTL_hero_shader"`. **That is the second materiallibrary** — created as a side effect of the material call, not placed by hand. Nine nodes in `/stage`.

**Wiring (7 links, 19:52:42 → 19:53:01):**

```
GEO_sphere1 → MTL_hero → MTL_matlib → CAM_main → LGT_area → LGT_dome → karma_settings → OUTPUT
```

**20 parameter sets with exact values**, including `GEO_sphere1.soppath=/obj/geo_assets/hero_sphere`, `LGT_area.primtype=UsdLuxRectLight` at t(3,4,5) exposure 1.0 intensity 1.0, `LGT_dome.primtype=UsdLuxDomeLight` exposure 0.25, `CAM_main` at t(0,1.5,6) with `lookatenable=1`, and `karma_settings` camera `/cameras/CAM_main`, `engine=xpu`, `res_mode=manual`.

**So:** the nodes are **agent-authored with recoverable provenance**, not artist work of unknown origin. Labeling agent output as the artist's own hand is the more dangerous error under INTENT.md §7 (*"Artist edits are authoritative"*) — it grants agent-made geometry the protection reserved for you.

### Three defects the ledger already recorded

**(a) The empty sopcreate is a name-collision artifact.** `GEO_sphere` was requested twice. The sopcreate took the name at 19:48:37; the sopimport 84 seconds later became `GEO_sphere1`. The collision actively misdirected the camera: `CAM_main.lookatprim` was set to `/GEO_sphere` at 19:51:22 and corrected to `/GEO_sphere1` at 19:51:34. The empty sopcreate is not in the chain.

**(b) The display flag is on the wrong branch — and SYNAPSE said so at the time.** `create_material`'s own output, verbatim:

> `"display": "not_set"`, `"display_node": "/stage/GEO_sphere"`,
> `"needs_rewire": "The edit lives on a side branch -- the display flag is on /stage/GEO_sphere, so the viewport, Karma, and USD export won't see this change until the display flag moves to /stage/MTL_hero or the branch is wired back into the chain."`

That warning has been sitting unread in the ledger. It is the single highest-value thing in this section.

**(c) No `usdrender_rop` was ever created.** It is absent from the create_node list. The chain terminates on the OUTPUT null.

Note (c) is **not** automatically a defect — `solaris_graph_templates._build_render_tail` wires `karmarendersettings → OUTPUT null` as the canonical display chain and branches the ROP off `karmarendersettings`. But you have no render terminal, and SYNAPSE's own preflight will not tell you (§3 below).

### What the ledger cannot give you — state plainly

- **`before_state_hash` and `after_state_hash` are empty in 138 of 138 rows.** I checked every one. The ledger proves what was *executed*, never what the composed stage *became*. It cannot satisfy INTENT.md §3's *"Starting state — Observed revision of affected scene state and dependencies."*
- Every mutating op carries `memory_loop` = UNAVAILABLE, `"Main-thread dispatch was not instrumented"`.
- `level` = `agent_action` on 100% of rows; `user_id`, `agent_id`, `tool` are empty strings. **Manual edits you made in the same window are invisible to it.** It cannot prove the absence of artist changes.
- No INTENT.md §3 engagement record exists anywhere in code — `grep -rli "engagement" --include=*.py python/ tests/` returns 0. Goal, Change boundary, Limits and Handoff were never recorded. **Authorship and sequence are recoverable; authorization and intent are not.** Strictly, the correct operation is a fresh **Engage**, not a Resume.
- **Do NOT mine `memory.jsonl` for a baseline.** `GEO_sphere`, `CAM_main`, `LGT_dome`, `MTL_matlib` and `hero_sphere` all have 09-06 / 09-09 / 09-13 / 09-14 namesakes in that store from prior runs. Using them attributes a different build's state to this network. And `hip_file` is the literal string `untitled.hip` for 333 of 865 records spanning at least four distinct builds — scene identity cannot discriminate them.

### The validation INTENT.md §3 requires before resuming

> *"**Resume:** requires a deliberate artist action and fresh validation of the affected scene. Restart, reconnection, scene replacement, and model suggestions MUST NOT silently resume an engagement."*

All of the following are read-only. None mutates the scene.

1. **Inventory `/stage`** — confirm exactly those 9 nodes, their type names, and nothing else. Anything extra is an edit the ledger cannot see.
2. **Read the actual input wiring node by node** and compare against the 7 links above. The ledger records what was *requested*; it carries no confirmation the connections resolved.
3. **Confirm which node carries the display flag.** Expect `/stage/GEO_sphere` (the empty sopcreate). If so, nothing downstream of the material is in the viewport, Karma, or export.
4. **Confirm `GEO_sphere1.soppath` still resolves** to `/obj/geo_assets/hero_sphere` and that the SOP still cooks.
5. **Confirm each node type resolves on 22.0.400.** `light` is version-qualified (`light::2.0`) — check, do not assume.
6. **Inspect `/stage/GEO_sphere` (the sopcreate) internals.** Its subnet is at `/stage/GEO_sphere/sopnet/create`. If it is empty, decide whether it is an orphan or an unfinished step.
7. **Check the two materiallibrary prim-path prefixes** (`/stage/MTL_matlib` vs `/stage/MTL_hero`) for collision.
8. **`stage.GetCompositionErrors()` is empty.**
9. **`UsdShade.MaterialBindingAPI(...).ComputeBoundMaterial()` on every Mesh prim.** The presence of two materiallibrary nodes is not evidence of binding. `materiallibrary` binds directly via `assign#`/`geopath#` — no `assignmaterial` LOP is required, so its absence proves nothing either way.
10. **Run `_assess_stage` (`solaris_compose_tools.py:487`) as the readiness predicate**, not the panel preflight. It is pxr-level: rendersettings prim present, render-camera rel resolving to a real Camera prim, composition errors empty, materials bound, output_path, AOVs.

**UNKNOWN, and I could not close it read-only:** whether those 7 connections actually resolved, whether the sopcreate is locked, whether a prior delete was refused, and whether `/stage` currently holds exactly those 9 nodes. I did not query the live stage — a stage read risks a cook, and I am read-only. Steps 1-3 close all of it in one pass.

### Before you save that hip — a warning that is bigger than this decision

`MemoryStore._get_storage_dir()` (`store.py:1258-1280`) derives the store address from the hip file's parent directory. `hip_is_unsaved` (`store.py:912-945`) routes never-saved scenes to `$HOUDINI_TEMP_DIR/untitled/.synapse`, and `_announce_unsaved_relocation` (`:955-965`) states outright that stores at a previous address *"are NOT carried over"*, under a comment reading *"never relocate data silently."*

**The moment you save this scene under a real name, SYNAPSE opens a new, empty `.synapse` beside the hip. All 865 records — including everything written since the repair — stay behind in `%TEMP%`, orphaned.**

This is the most plausible mechanism for a second data-loss event this audit surfaced: the 403-record August-9 generation of this same path is absent from the live store *and* from Moneta (0 of 403 in `snapshot.json` and `cortex_root.usda`, against a 40/40 live-id control), surviving only because someone hand-copied it to `~/.synapse/backups/`. The directory was not wiped — files from Aug 9 and Aug 31 are still there. Something changed the address. **Cause remains UNKNOWN.**

Do the backup copy **before** you save the hip, not merely before you delete the 11.

---

## 3. THE REAL DEFECT — the unbounded quarantine generator

### What it is

`python/synapse/memory/store.py:311-326`, the entire producer:

```python
def _quarantine_store(self, reason: str = "degraded") -> Optional[Path]:
    """COPY the on-disk store aside as a timestamped recovery point. We copy,
    never move/delete — the unreadable ciphertext is exactly the recoverable
    asset. Best-effort; never raises (a failed copy still leaves the original)."""
    if not self.memory_file.exists():
        return None
    aside = self.memory_file.with_name(
        f"{self.memory_file.name}.{reason}-{int(time.time())}"
    )
    try:
        shutil.copy2(str(self.memory_file), str(aside))
        logger.error("Quarantined a copy of the store for recovery: %s", aside)
        return aside
    except OSError as e:
        logger.error("Could not quarantine the store (%s); original untouched", e)
        return None
```

No content hash. No check for an existing copy. No retention cap. No manifest. No latch. **The returned path is discarded by the caller.**

Exactly one call site, `store.py:408`, unconditional inside `if degraded_reason:` at the tail of `_load()`. `_load()` runs once per `MemoryStore` construction — and construction is **not** once per Houdini launch: 9 non-test construction sites exist, and `writethrough` + `moneta` can both build one in a single process.

The failure state is **sticky**: the store stays degraded until a human repairs it. So every store construction converts into another full-size copy, forever.

**Measured:** 11 copies, 1,394,474 bytes each, all one sha256, filename epochs spanning 46.50 hours, mean interval 4.65 h, **minimum gap 9.6 minutes** (four gaps under 30 min). Refill rate is one current-store-size per construction — 1.33 MiB today and rising with the store.

**A full disk does not stop it.** The `OSError` is caught at `:324` and `_load` continues; the producer keeps firing and merely fails, silently. The only thing that ever suppresses a write is filename collision at 1-second resolution — and that is **destructive, not benign**: `shutil.copy2` overwrites. Verified live on the D: store, where two constructions 84 ms apart (11:17:34.506 / .590) resolved to the same filename and left 2 logged events but 1 file. With identical content that is harmless; with changed content it silently destroys the earlier snapshot.

**One more trap for whoever writes the fix:** `copy2` preserves mtime, so all 12 files stamp `Sep 15 15:09` — the *source's* mtime. Any retention policy written against mtime ("keep the newest 3", "delete older than 7 days") cannot order these files at all. **Only the filename epoch is truthful.**

### Minimal correct fix

Land **(a) + (b) only**:

**(a) Content-address the name.** Stream-hash the store (1 MiB chunks; ~ms at 1.4 MB, ~100 ms at 50 MB, once per degraded load). Name the copy `{name}.{reason}-{digest[:16]}` and skip the copy when it already exists. One snapshot per distinct state. This also eliminates the same-second overwrite as a side effect.

**(b) Write a manifest.** `quarantine.manifest.json`, appending `{digest, file, bytes, reason, detail, first_seen, last_seen, observations, recovery_status}`. On a repeat, increment `observations` and log WARNING *"still degraded, snapshot already held (seen N×)"* instead of ERROR.

`detail` needs **no signature change** — `self._degraded_reason` is set at `store.py:402` immediately before the call and currently carries the real diagnosis (`"5 incomplete source record/read(s): line 2: conflicting duplicate memory identity"`), which is today thrown into a log line unlinked from the file it produced. That one field is what turns the snapshot into a §6 record.

**Two things the fix must also do, or it makes things worse:**

**Hash against all `memory.jsonl.*` siblings, not just `*.degraded-load-*`.** Your `pre-repair-*` keeper was written outside the quarantine machinery; a dedup scoped to the `degraded-load` name will not see it and will write a redundant 12th copy of bytes already on disk. And `_quarantine_store(reason=...)` is parameterized, so a hardcoded literal glob stops deduping the moment a second reason is introduced.

**Repoint `doctor.py:323` at the manifest's `observations`/`first_seen`/`last_seen` in the same change.** Without it, dedup pins `degraded_quarantine_count` at 1 permanently — a store degrading daily for a month reports 1, and the ≥5 page-on-call threshold can never fire again. You would trade 14.63 MiB of disk for a dead alarm. "One snapshot, seen 47 times over 2 days" reads louder than 11 files ever did.

### Do NOT add a recency cap

The obvious third item — "keep the N most recent distinct digests" — was refuted and is a data-loss bug in the remedy. It evicts the **oldest** snapshot first, which is exactly backwards: under progressive corruption or key rotation, the oldest is nearest last-good and the most recoverable. It also converts a recovery-snapshot producer into a deleter, contradicting the invariant the function states in its own docstring (*"We copy, never move/delete"*). If a bound is genuinely wanted later, it must be "keep the FIRST distinct digest permanently, plus the N most recent", and it must be a separate human-gated change.

**Automated retention must also never delete a file it did not write.** Your `pre-repair-*` backup sits in the same `memory.jsonl.*` namespace and is byte-identical to the litter. A content-hash or glob-based cleaner cannot tell them apart. Key retention on a manifest of paths the generator wrote.

### INTENT.md sections violated — quoted

**§6, line 193:**
> *"| Existing persistence owner | Retains task state, proposals, revisions, results, artist selections, and execution provenance **without a competing registry**. |"*

Eleven undifferentiated timestamped copies plus a directory glob that infers incident state from filenames **is** a second registry, derived from `ls` rather than from a record.

**§6, lines 200-203:**
> *"Each completed or interrupted operation MUST have a record connecting the engagement and proposal to its actual changes, execution route, verification results, and recovery status. Unsupported or unmeasured behavior remains `UNAVAILABLE` or `UNKNOWN`, as appropriate."*

Each refused load is an interrupted operation. Its snapshot records a reason-slug and an epoch and nothing else — not which ids conflicted, not the route, not verification, not recovery status. And a count of *load events* presented as a count of *manual-recovery incidents* is not `UNKNOWN`; it is a confident wrong number.

**§3:**
> *"**Stop and Undo are different operations.** Stopping assistance does not erase completed work. Supported scene changes need tested undo behavior and an explicit failure-recovery path. Undo grouping alone is not automatic rollback."*

Nothing in the tree ever *reads* a quarantine copy. `_quarantine_store` has two references: the def and the one call. `tests/test_store_degraded_load.py:91-93` asserts a copy exists and matches the original ciphertext — it pins that a copy is **made**, never that one can be **restored**, and would pass identically with 1 copy or 11. A snapshot generator is standing in for a recovery path, and the restore direction has never been executed.

**§9, line 269:**
> *"| Missing capability or failed action | The actual limit, partial result, and recovery options are visible; a fallback cannot bypass policy. |"*

The recovery artifact is computed, logged, and then discarded at the call site.

**§1:**
> *"Routine construction, repetitive adjustments, navigation, and preview management consume attention that an artist could spend on hero assets…"*

An unbounded pile of identical snapshots is exactly this kind of attention tax, and it is what forced this decision onto you.

### Prior art: this was already adjudicated, at higher severity

`harness/notes/forensic/S2.json:72` carries **S2.F9, severity HIGH, truth VERIFIED-STATIC, class LIMIT**: the degraded path *"writes a memory.jsonl.degraded-load-<ts> litter file beside the hip, and save() raises from then on. Silent. Reads as 'the memory feature does not work'."* `S2_PREMORTEM.md:404` states flatly *"`_degraded_load` has no recovery path."* `S3_PLAN.md:997` planned to give it one. **It never landed.** This week's incident is field confirmation of a known HIGH finding, not a discovery.

The in-repo precedent for doing it right already exists and was explicitly prescribed: `moneta_store.py:413` `_quarantine_if_corrupt` *renames* aside (structurally incapable of producing N copies) and at `:268` **reads the quarantine back** — `if any(base.glob("snapshot.json.corrupt-*")): load_issue = "A quarantined snapshot needs recovery before checked recall"`. `docs/SYNAPSE_CTO_REVIEW_2026-06-09.md:84` told C1 to follow *"the `moneta_store._quarantine_if_corrupt` pattern [which] is already in-repo."* `MemoryStore._quarantine_store` took the copy semantics — correctly, unreadable ciphertext should not be moved — and did not take the reader or the bound. **That half-adoption is the actual defect.**

---

## 4. BLAST RADIUS

My own sweep, replicating `store.py:349-360`'s exact acceptance predicate against real bytes, across `D:\HOUDINI_PROJECTS_2025`, `D:\HOUDINI_PROJECTS_2026`, `D:\MODEL_COLLECTION`, `%TEMP%\houdini_temp` and `~\.synapse` (pytest paths excluded).

### Four project stores are poisoned. All four are unrepaired.

| Store | lines / loaded / unreadable | first conflict | quarantine marker | last write | shape |
|---|---|---|---|---|---|
| `D:\MODEL_COLLECTION\Astra_Saucer_Sept2026\newProject\scripts\.synapse\memory.jsonl` | 12 / 11 / **1** | line 6 | **none** | 2026-09-15 11:40 | **B** |
| `D:\HOUDINI_PROJECTS_2025\Houdini21_Alien_Spaceship_Saucer\.synapse\memory.jsonl` | 58 / 39 / **19** | line 10 | `degraded-load-1789571854` | 2026-02-23 17:44 | **A** |
| `D:\HOUDINI_PROJECTS_2025\HOUDINI21_SYNAPSE_DEMO\SYNAPSE_DEMO_v0001\scripts\.synapse\memory.jsonl` | 13 / 5 / **8** | line 5 | **none** | 2026-02-12 17:47 | **A** (3 conflicting ids) |
| `D:\HOUDINI_PROJECTS_2025\MPM_MASTERCLASS_FILES\.synapse\memory.jsonl` | 2 / 0 / **2** | line 1 | **none** | 2026-02-13 18:32 | **C** |

**Clean:** untitled (865/865, repaired), LinkedinGraphic (11), flow_trail (28), SYNAPSE_TESTS_6.2026 (8), Houdini_KarmaXPU_Play (0 lines), `~/.synapse/memory.jsonl` (0 bytes).

### How many are silently refusing writes *right now*: zero. Four are armed.

`_degraded_load` is a per-**instance**, in-memory flag set once during that instance's `_load`. None of the four projects is open, so nothing is being refused at this second. **They will refuse on the next open.** Three of the four are archaeological — 205 to 217 days idle, zero ongoing loss. **Only Astra is a live project**, poisoned 2026-09-15 11:40 and never reopened since, which is why it has no marker.

**The quarantine copy is not a detector.** It missed 3 of 4. `_quarantine_store` fires only inside `if degraded_reason:` in `_load`. A store poisons itself mid-session (Astra's conflict is at line 6 of 12 — six lines were written after it) and the poison does not bite until the *next* open. No marker means not-yet-reopened, not healthy. **Triage by load-replay, never by marker presence** — and do the replay read-only, because *opening* one of these to check mints a fresh 1.4 MB quarantine copy from the generator described above.

### The critical part: two of these need OPPOSITE repairs

Applying the untitled store's "keep the richer record per id" recipe to Alien or DEMO **permanently deletes real events.**

**Shape A — legacy time-independent ids (Alien, DEMO).** The id was minted before `created_at` was defaulted, so it hashed content+type only. Proven by exact reproduction: `sha256("Executed: execute_python::action")[:12] == 2f1bc0bbb623`, matching the on-disk id bit for bit. The fix is documented in-tree at `models.py:140-145`: *"generating the id first (when created_at is still \"\") made it time-independent — identical content+type then collided forever."*

- **Alien:** one id, `mem_2f1bc0bbb623`, occurring **20 times**, non-adjacent, differing *only* in `created_at`/`updated_at` (spanning 22:32:10Z → 22:42:29Z). "Keep the richer" collapses 20 → 1 and **destroys 19 genuinely distinct `execute_python` events — 33% of the store.** With every metadata field tied, "richer" is a coin flip.
- **DEMO:** **three** colliding ids (`mem_3565ce339c45` ×3, `mem_2f1bc0bbb623` ×4, `mem_cf346dac465c` ×4). The wrong recipe destroys **8 of 13 lines — 62%.** And DEMO's collided records span **three different .hip versions** (`Synapse_demo_v0004`/`v0011`/`v0012`) across four days. One memory record cannot belong to three scenes. That is semantic proof, independent of any hash argument.
- **Correct repair: RE-KEY.** Recomputing under the current `content:created_at:type` rule yields 20 distinct ids for Alien (0 collisions against surviving ids, 0 against each other) and clean ids for DEMO. Nothing is lost. Both stores carry zero `links[]` and zero `consolidated_into` references, so re-keying orphans nothing.

**Shape B — the live double-write bug (Astra, and the untitled store).** Adjacent line pair, `created_at` **identical**, content byte-identical, the second copy metadata-stripped: `tags` → `[]`, `hip_file` → `""`, `frame` → `null`, `source` `'ai'` → `'auto'`. Astra L5/L6, id `mem_043ce93ca4e5`, both stamped `2026-09-15T15:24:47Z`. The stripped copy is a strict subset carrying nothing its twin lacks. **Correct repair: drop the stripped copy.** This is the same shape and the same week as the untitled store (untitled degraded 15:09, Astra poisoned 15:24) — **a systematic live producer bug, still active.**

**Shape C — MPM.** Both records are *plaintext* in a foreign schema (`content`/`tags`/`timestamp`/`type`, `content` is a dict not a str). This store has never been loadable by the current code. Neither repair applies.

### The discriminator to use — and the one NOT to use

Do **not** use "created_at differs → re-key, created_at identical → drop". The first half is sound; the second is a proxy that can destroy data, because two genuinely distinct events sharing content+type inside the same one-second bucket collide under the *current* rule too and present identical timestamps. This is reachable — Alien's events fire 6-9 seconds apart, and a faster agentic loop puts two in one second.

**Use the decisive test instead:** recompute the id under the current rule and compare to the on-disk id.
- Reproduces under the **current** rule → Shape B → drop the stripped copy, **and additionally require** that every differing field in the dropped copy is empty, null, or a strict subset (whitelist `source`, which is a writer tag, not payload).
- Reproduces only under the **legacy** rule (`created_at` treated as empty) → Shape A → re-key, never drop.

Both discriminators were run against all 5 colliding ids across the three stores and agree everywhere. In Alien and DEMO, 58/58 and 13/13 records respectively match the legacy rule and 0 match the current one, so the test is decisive rather than heuristic.

### Three things any repair plan must also carry

1. **Snapshot first, where none exists.** Alien has a byte-identical quarantine copy (sha `0a7b9eea…`). **Astra and DEMO have no backup and no quarantine copy at all.** Take an explicit pre-repair snapshot of those two before writing a byte. INTENT.md §3's failure-recovery requirement is unmet for both.
2. **Never sweep quarantine copies globally.** Alien's single copy is the only recovery point for a store that is still broken. Scope any deletion to the untitled directory by explicit path.
3. **Reconcile the Moneta sidecar.** Memory ids leak outside the jsonl — `mem_043ce93ca4e5` appears in plaintext inside Astra's `.moneta/cortex_root.usda` *and* `snapshot.json`. Astra's repair is a drop and keeps that id valid, so Astra is fine today. **Any re-key applied to a store with a populated `.moneta` leaves dangling cortex references.** Alien's `.moneta` is a 78-byte stub with no ids, so re-keying Alien is safe now; the generic recipe still needs a reconciliation step.

**Also worth deciding separately:** re-keying is a one-way external migration with no self-healing (`Memory.from_dict` preserves whatever id is on disk; `_generate_id` fires only when id is falsy). Its success signature — "loads clean, 58 records, 0 conflicts" — is satisfied by *any* 58 distinct ids, including wrong ones. Any re-key must ship with a verification predicate that recomputes `sha256(f"{content}:{created_at}:{memory_type}")[:12]` per record and asserts it equals what was written. A clean load is not evidence of a correct re-key.

---

## 5. THE SILENCE

### Why a 46-hour write outage was invisible — three independent reasons

**(1) The degraded store was the safety net, and its failure is swallowed by design.**

`packages/synapse.json` sets `SYNAPSE_MEMORY_BACKEND = "moneta"`, so the live store is a `MonetaBackedStore` and the degraded JSONL store was `_jsonl_net` — referenced **only** inside `moneta_store.py`. No doctor check, no health probe, no panel cell reads it. It is unobservable by construction.

`moneta_store.py:784-785`, verbatim:

```python
except Exception as exc:  # noqa: BLE001 -- the safety net must never break the caller
    logger.warning("JSONL dual-write failed (isolated): %s", exc)
```

The Moneta deposit precedes the mirror, and `add()` returns `memory.id` regardless. **The caller received a success id every single time.**

**Measured in `~/.synapse/logs/synapse.log`: 253 occurrences**, first `2026-09-15 17:14:24,502`, last `2026-09-17 15:53:57,228`, **none since**. The mirror is writing again.

The invariant that broke is stated in the code itself at `moneta_store.py:189-190`: *"`_jsonl_net` is a JSONL MemoryStore safety net so a memory never lands ONLY in moneta (dual-write, the wave non-negotiable)."*

**So this was not two days of lost memory. It was two days with no redundancy.** Which is materially better news than it first looked — and it leaves a live, unrepaired consequence, below.

**(2) SYNAPSE's designated write-acceptance authority never asks whether writes are accepted.**

`mcp/_tool_registry.py:134-135` advertises: *"write_plane (ok | degraded | unknown) — whether the memory/report write targets actually accept a write. Check write_plane before trusting a write."*

`write_plane.py:321` `store_health()` derives its verdict from exactly three facts, all read-side: serving-class identity, `store.count()` reachability, Moneta durability. I confirmed it myself: **`grep -c "_degraded" write_plane.py` = 0.** And **`grep -c "write_plane" health_strip.py` = 0** — the always-on panel strip has never heard of it.

The near-miss is one line wide. `count()` (`store.py:601-605`) calls `_wait_loaded()` and returns `len(self._memories)`. Its sibling `clear()` (`:609`) calls `_require_writable_load()`. **The degradation guard is one method away and on the wrong one.** So every read stayed truthful and healthy-looking while every write raised.

The generalizable lesson is bigger than the one clause: `all()`, `search()` and `count()` all call only `_wait_loaded()`. The degradation is **write-only**, so every read-side probe is structurally incapable of seeing it, and recall worked flawlessly throughout. **A write plane must be probed by asking the write guard, not by reading.**

**(3) A second, quieter silence.** `store.py:246-247`:

```python
if not self._loaded.is_set() or self._degraded_load:
    return
```

A bare return in the flush path. No raise, no log, no counter. Anything already in `_write_buffer` — including at the `atexit` shutdown flush — is discarded with zero signal.

### What the degradation *did* say, and to whom

`store.py:403` logs `DEGRADED LOAD: … Refusing writes; recover the source or encryption key, then reopen. Original bytes are preserved.` at **ERROR**, 11 times over 46.5 hours. The store side was already shouting at the loudest level it has. **The gap is not signal strength — it is that no status surface reads the log.**

### Minimum viable signal — three small changes, no new surface

**(a) One clause in `store_health()`** (`write_plane.py`), alongside the existing three:

```python
if getattr(store, "_degraded_load", False):
    broken.append(f"store loaded DEGRADED and is refusing all writes: "
                  f"{getattr(store, '_degraded_reason', '')}")
```

That flips `write_plane` → `degraded`, which flips the existing doctor check `write_plane_store` → `fail` (`doctor.py:970`), which populates the `write_plane` field **already present** in `synapse_health` (`api_adapter.py:190`). Nothing new to build. Use `getattr` for the reason too — a health read must never raise. Existing tests use stubs without the attribute, so the `getattr` default keeps them green; ship it with a test that constructs the degraded case.

**(b) That clause must probe the secondary sink, not just the primary.** On a Moneta seat a `store_writable` boolean read from the primary reads **True** for the entire outage and catches nothing — the primary genuinely *was* writable. It must read `_jsonl_net._degraded_load` and a per-sink failure counter, and report *"the dual-write safety net has refused N writes since HH:MM; memories are landing only in Moneta."* Counters on the object are what make the failure answerable without a logfile; today the only trace is repeating log spam with no escalation and no queryable state.

**(c) The always-on surface.** `health_strip.cell_memory()` (`:209-248`) currently returns `Verdict.OK` with the class name for any live jsonl store, commented *"real and not a degradation"*. The cheaper fix than plumbing `write_plane` into the snapshot: `_gather_memory()` already holds the live store object — one `getattr(live_store, "_degraded_load", False)` there yields a RED cell with zero new coupling. The strip already renders degraded reasons **inline, not in a tooltip** (`health_strip.py:377`). **That is the surface that would have caught this on day one, because it is the only one you see without asking.**

**Scope caveat:** the clause fires only where the store is actually resident — i.e. inside Houdini. `_live_store()` returns None in any process without `_global_synapse`, so an external-MCP process asking `write_plane` still gets a directory-only verdict. Don't describe the fix as covering `/mcp`.

**Cheapest third option, worth considering ahead of both:** an alert on ERROR-level records from the `synapse.memory` logger. The store was already logging at ERROR. That single hook would have caught this incident *and* the Alien store on day one, and costs less than either code change.

### The live consequence nobody has closed

**253 records exist in Moneta and not in the JSONL mirror, and the repair did not backfill them.**

Verified by id, just now:
- `memory.jsonl` — **865** ids
- `.moneta/snapshot.json` — 1,119 rows, **1,113** memory/loop ids
- **in Moneta, not in jsonl: 253** — exactly matching the 253 logged dual-write refusals
- in jsonl, not in Moneta: 5

The repair restored *writability*. It never restored *parity*. **Anything that later treats `memory.jsonl` as canonical — `migrate.py`, `backfill.py`, or a Moneta rebuild from the net — silently adopts a history missing ~23% of its records, including everything authored 2026-09-15 through 2026-09-17.** That is a bigger exposure than the 15 MB that started this, and it should be measured and closed before either store is trusted as the source of truth.

### Two more gaps the delete interacts with

- **`degraded_quarantine_count` is a load counter sold as an incident counter.** `doctor.py:323-324` is its only consumer. `docs/moneta-production-harness-architecture.md:610` declares *"Quarantined files indicate key-mismatch events. **Each one is a manual-recovery incident.**"* with warn ≥1 / critical ≥5, and `:623` pages on-call on **any** increase between runs. Ground truth here: **one** incident, re-observed 11 times, all files sha-identical. The metric is structurally incapable of the meaning assigned — the filename is `int(time.time())`, which encodes *when a load happened*, never *which state was found*. It is also documented for the wrong cause: this episode was duplicate identity (`store.py:359`), not key mismatch — I confirmed the active key fingerprint matches the sidecar (`6aa8f313` == `6aa8f313`), so `_key_fingerprint_mismatch` would have returned None. And the metric is hip-scoped (`_resolve_store_dir()` reads `hou.hipFile.path()`), so it is presented as a deployment-wide signal it cannot be — the Alien degradation is invisible to doctor no matter what.
- **`memory_status` actively reassures on a dead store.** `handlers_memory.py:315-337` overwrites `entries_total` with `store.count()`, which succeeds. There is no degraded flag, no store path, no write health, and the `except Exception: pass` at `:334-335` means even a failed count read is silent. Everything else it reports — evolution stage, `size_kb` from `os.path.getsize`, `session_count` from counting `"## Session "` substrings, a hardcoded `"agent": {"status": "idle"}` — measures markdown files, not the live store.

---

## 6. WHAT THE REFUTERS KILLED

**Eight findings did not survive.** Stated plainly, including the one that inverts a recommendation you were about to receive.

**1. "No external redundancy — the keeper must leave %TEMP% before any deletion" (retention, high).** Its facts held and I confirmed the key ones: all six external backup candidates have **0% id overlap** with this store's generation, and `~/.synapse/memory.jsonl` is 0 bytes. But the conclusion inverted. The keeper is a **strict content subset of the live store** — 0 of its 841 ids are missing from live, and its only unrepresented content is the 5 stripped duplicates the repair deliberately dropped. Gating the delete on protecting it protects the wrong file. **The unbacked singleton is the LIVE store.** Its second claim — "in-place retention at this exact path already failed" — is a misdiagnosis: the eras are disjoint because the **store directory moves** with `hou.hipFile.path()`, not because retention failed in place. Its precedent argument also ran backwards: those 403 August records were copied aside five weeks ago and 0% of them are in any live store today. That is a demonstrated failure to *restore*, not a demonstrated restore.

**2. "No test pins the bound" (generator, medium).** Its conclusion survives — no test anywhere pins `_quarantine_store` cardinality or idempotence — but its coverage map is wrong in a way that matters. "The only test exercising the real producer is `test_store_degraded_load.py`" is false: at least **six cases across three files** drive the real producer and write real quarantine files, every one tolerating unbounded output (`test_plaintext_garble_…` emits one and asserts nothing; `test_store_key_escrow.py::test_changed_key_on_empty_store_is_degraded`; `test_demo_memory_scope.py::test_decision_refuses_incomplete_source…` ×4 parametrizations). Two consequences it missed: the test it recommends is **RED on master**, so it must ship in the same commit as the fix or as `xfail(strict=True)`; and it **requires a forced clock advance**, because two degraded loads inside one wall-clock second resolve to the same filename and `copy2` overwrites — a repeat-load test without it passes green against today's broken producer.

**3. "Four stores are currently in DEGRADED mode and refusing all writes" (blast radius, critical).** The four stores are real — my own sweep reproduces the counts exactly. The wording is not. `_degraded_load` is a per-instance in-memory flag set at load; none of the four is open, so nothing is refusing. **They are armed, not refusing.** It also flattened the harm: three are 205-217 days idle with zero ongoing loss, and only Astra is live. And it presented one blast radius where there are **three distinct root causes** (Shape A / B / C) requiring opposite repairs.

**4. "Copies 2..N are byte-identical by construction" (second-store, medium).** The delete answer holds; the word "construction" does not. `_degraded_load` is per-instance, decided once at load, so an instance loaded *before* degradation stays writable and keeps appending — a constructible divergence. What licenses the delete is the **hash**, not the construction argument. Its protective caveat ("do NOT delete the Alien store's quarantine copy — it is that store's only recovery point") is also self-defeating as reasoned: that copy is byte-identical to an intact live file. Keeping it is still correct (it is the only *pristine* copy if the live file is touched), but the stated reason is looser than the evidence.

**5. "No baseline exists for this scene — do not resume" (scene, critical).** **Killed, and this is the one that changes your decision.** I verified the refutation first-hand. `~/.synapse/audit/audit_2026-09-17.jsonl` is a second, independent, hash-chained ledger that kept writing normally throughout the degraded window and contains the entire build: 10 `create_node` with type and parent, 20 `set_parm` with exact values, `create_material`, and the full 7-link wiring chain. The finding missed it because the ledger is Fernet-encrypted per line, so a plaintext grep returns zero hits for content that is present. **Standing lesson for this codebase: never conclude "nothing exists" from a plaintext search of an encrypted store.** The correct narrower disposition: authorship and sequence *are* recoverable; authorization, intent, and stage state are not (`before_state_hash`/`after_state_hash` empty in 138 of 138 rows — I checked every one). Its recommendation to "treat all 9 /stage nodes as ARTIST-AUTHORED work of unknown provenance" is the more dangerous error, inverting the INTENT §7 protection.

**6. "Not a Karma chain, and preflight says otherwise" (scene, high).** Killed on two of three legs. **The preflight defect is real and I verified both accept-lists** — `render_preflight.py:142` (`"karma", "karmarendersettings", "usdrender_rop"`) and, worse, the live execution path `handlers_render.py:156-162` `_RENDER_TYPES`, which hands the node to `node.render()`. Worse still, `PreflightReport._build_summary` grades `ready = (n_fail == 0)` while only 3 of 9 checks can emit a `fail` at all, and `karmarendersettings` ships defaults that satisfy all three. But: "all three canonical definitions require a `primitive` root" is **false** — `grep '"primitive"' solaris_graph_templates.py` returns **zero hits**, and that file is a *tail* builder. The 900-vs-800 rank argument contradicts its own quoted evidence, since `karmarendersettings → OUTPUT null` is the canonical display chain in `_build_render_tail`. And the absence of `assignmaterial` proves nothing about binding — `materiallibrary` binds directly via `assign#`/`geopath#`. Its recommended substitute, `_assess_stage`, is also pure-pxr over the composed stage and **cannot see a missing ROP either** — detecting "no render terminal" needs a node-graph check neither predicate performs.

**7. "The empty sopcreate and second matlib are debris — rebuild clean" (scene, high).** Killed. The memory store holds your own ratified recipes from 2026-09-06 (v1 00:45, v2 00:48, v3 13:35, v4 14:00) in which the `sopcreate` is **step 1 of the canonical chain** (with its sphere SOP specified to live at `/stage/GEO_sphere/sopnet/create`) and **two chained materiallibraries are a deliberate feature** — v4: *"The hero material is a SEPARATE materiallibrary (mat_hero) chained after asset_materials, NOT folded into it — keeps hero lookdev isolated."* Your v1 and v3 **decision** records also explicitly considered and rejected `scene_template` as the tool, so the finding nominated the alternative you twice disqualified — and it cannot emit the `light::2.0` rect+dome pair or the null OUTPUT terminator your recipe requires. **Honest caveat on the refutation:** the audit ledger I read myself shows the second materiallibrary at `/stage/MTL_hero` was created by *this session's* `create_material` call at 19:51:43 (`matlib_path: "/stage/MTL_hero"`), not authored per the v4 recipe. So the refuter's specific mapping of *this* scene onto v4 is **UNPROVEN**; its general warning against calling those nodes debris stands, and its "rebuild beside" alternative carries its own hazard (`scene_template.execute()` hardcodes `camera1` while the idempotency guard checks only `primitive_{scene_name}`, so building beside an existing camera yields a RenderSettings pointing at a prim that does not exist).

**8. "memory_status reported a healthy-looking 846 entries" (visibility, medium).** The status-handler gap is real and I verified it. The mechanism and the number are not. On this seat the count comes from `MonetaStore.count()` → `self._handle.ecs.n` — an object with **no degraded concept whatsoever** (`grep "degraded" moneta_store.py` = 0 hits) — so the number reported was honest and **rising**, not a frozen 846. It could not have been 846 on a jsonl-primary seat either, since `_load` keeps only the first copy of a conflicting id and would have reported 841. **Consequence that matters for the fix:** a `store_writable` boolean read from the primary would have read True for the entire outage and caught nothing. The missing measurement is a **primary-vs-mirror divergence field**, not a boolean — which is why item (b) in §5 is load-bearing rather than cosmetic.

---

## What remains UNKNOWN

- **Whether `/stage` currently matches the ledger.** I did not query the live stage — a read risks a cook, and I am read-only. The 7 connections are recorded as *requested*; I have no confirmation they resolved. Validation steps 1-3 close this in one pass.
- **Why the 403-record August-9 generation vanished from this store path.** The directory survived (files from Aug 9 and Aug 31 are still there) while `memory.jsonl` restarted at 2026-09-01. "Temp was cleaned" does not account for it. Until the mechanism is identified it can recur, and no retention fix to `_quarantine_store` addresses it — the quarantine copies are a symptom, not the loss channel.
- **Whether the 253 Moneta-only records can be backfilled into the JSONL mirror**, and whether the 5 jsonl-only ids indicate a reverse gap. Neither has been attempted.
- **Whether a restore from `memory.jsonl.pre-repair-*` actually works.** `repair.py` has been run exactly once, forward, against the degraded live file. The restore direction has never executed. Cheap to close: dry-run it against a copy in a scratch directory, zero risk to live. Until then INTENT.md §3's *"explicit failure-recovery path"* is unmet.
- **Whether `save()` round-trips on the repaired store.** No `memory.jsonl.bak.1` exists in the store directory, which is consistent with no `save()`-path write having landed since the repair — the hot path is buffered append, not `save()`. The repair is verified at *load* level; the disk round-trip has not been demonstrated. One write plus a fresh-process reload closes it.
- **The audit ledger's chain integrity.** 129 of 136 adjacent pairs on 2026-09-17 link `previous_hash` → `entry_hash` correctly; 7 do not (most likely session boundaries, unverified). `sequence_id` is empty on every row. Characterize this before relying on the ledger as tamper-evident.

---

**Nothing in this memo authorizes an operation.** INTENT.md §3: *"The host MUST validate this scope. A model-supplied ownership claim, scene identity, permission, or confidence value cannot authorize an operation."* The delete and the resume are both yours.

---

# Completeness critic

## COMPLETENESS CRITIC — concrete gaps, verified with my own read-only commands

**Verdict: do NOT act on either decision yet.** Three blockers below are decision-changing. The memo's core Decision-1 fact does hold — I re-hashed all 12 files myself and got exactly one sha256 (`2d8cc01b70b265…`, 12/12). The problem is not that hash. It is what the keep-list leaves out and what is happening to the store *right now*.

---

### BLOCKING — the human should not delete or resume until these are closed

**1. The backup list protects the mirror and abandons the primary.**
`…\untitled\.synapse\.moneta\` — `snapshot.json` 7,803,261 B + `cortex_root.usda` 1,714,320 B, 9.3 MB — sits in the *same* volatile `%TEMP%` directory. On this seat it is the **primary** store; `memory.jsonl` is the safety net. The memo's copy-out set is `memory.jsonl`, `pre-repair`, `encryption.key`. It names the two files that are redundant with each other and omits the only copy of the 253 divergent records.
→ **Copy `.moneta/` and `loop/` out with the rest.**

**2. A Moneta prune is staged right now, mid-audit.**
`~/.synapse/backups/moneta-2026-09-17-preprune/` — created **16:21 today**, after the memo's own 16:20 derivation. I hashed it: byte-identical to live (`f914a51c…` / `791b71c1…`), so the prune has taken its pre-image but has **not yet written**. `prune_memory` is APPROVE-gated (CLAUDE.md §1.2). Something armed a prune against the one store that solely holds the 34 memories and 219 loop rows the memo says must be backfilled.
→ **Find what armed it and stop it before any cleanup.** The memo's §5 remedy is racing it.

**3. The designated recovery asset for the memo's biggest UNKNOWN is itself DEGRADED — and no lane load-replayed it.**
Running the real `store._load` predicate against every store on the machine (two independent sweeps agree):
- `~/.synapse/backups/w1_2026-08-09/POST_MIGRATION_canonical_02_htemp_untitled__dotsynapse/memory.jsonl` — **516 lines, 403 loaded, 18 unreadable, `conflicting duplicate memory identity`**
- `~/.synapse/backups/w1_2026-08-09/10_repo_untitled_hip__dotsynapse/memory.jsonl` — **39 / 21 / 18 unreadable**

That first one *is* the "403-record August-9 generation" the memo calls the sole survivor of the earlier loss. It is poisoned, unrepaired, and would refuse writes if restored. **Six degraded stores, not four** (non-test; everything else degraded is pytest fixture litter).

---

### MATERIAL — correct before acting

**4. "253 Moneta-only records" is 87% loop-feedback rows.** I reproduced 253 exactly, then decomposed it: **34 `mem_` + 219 `loop_`** (jsonl-only: 4, not 5 — the store moves). By day, the mem_ gap is 21 on 09-15, 13 on 09-17, **zero on 09-16**. So it is ~5.7% of memories, not "~23% of its records," and "everything authored 09-15 through 09-17" is wrong. Real gap, different size, different remedy. The memo's ranking of this above the 15 MB rests on the inflated framing. (jsonl id space: 559 `mem_`, 305 `loop_`, 1 `exp_`.)

**5. The scene lane read one day's ledger out of four.** `audit_2026-09-14/15/16.jsonl` exist and decrypt fine. They hold **63 more `/stage` create_node ops** the memo never saw: a whole `/stage/MATERIALS/` tree (`metal_flake`, `machined_nickel`, `dark_titanium`, `studio_matte`), `/stage/fabric_ball_sub`, a **prior `/stage/GEO_sphere` sopcreate with a sphere and OUTPUT inside it (09-14 19:51)**, and a complete parallel chain on 09-16 (`GEO_asset`, `MTL_library`, `MTL_assign`, `CAM_lookdev`, `LGT_key`, `LGT_dome`, `RENDER_settings`, `OUTPUT`). Validation step 1 as written — *"confirm exactly those 9 nodes… anything extra is an edit the ledger cannot see"* — would have misattributed every one of those to the artist, the exact INTENT §7 inversion the memo accuses finding #5 of.
→ **I closed it in the memo's favour, with evidence the memo never produced:** Houdini is PID **54668, started 15:41 local**, after all that work; and 09-17's `LGT_dome` and `OUTPUT` landed unsuffixed despite 09-16 creating those same names at `/stage`. The scene is fresh and the 9-node manifest stands. But it stood on an unchecked assumption, and **step 1's predicate is still wrong as written.**

**6. The 09-17 ledger is not one session and not only the build.** 138 rows span **≥5 sessions**; `705e0bc64e515ee3` is **53** of them, not 138. It also carries 8 `execute_python`, 8 `project_setup`, 10 `cops_create_copnet`, 6 `batch_commands`, 4 `instantiate_graph` — and **6 `fake_mutate`** rows (plus `c5_mutate` on other days). I read the execute_python bodies: read-only `panel_workers` probes, so the manifest survives. But "138 rows, session X" and "`agent_action` on 100% of rows" mischaracterize the file, and synthetic harness rows in the production audit ledger are the same class of defect as the known pytest-pollutes-the-log issue — it weakens the ledger as a provenance authority.

---

### FAILURE MODES NOBODY ATTACKED

**7. The scene exists only in volatile process memory, and the memo never says so.** Unsaved `untitled`; PID 54668 up since 15:41; store quiescent since 16:16. In the 09-15→09-17 window there are **five `emergency_halt_*.json`, five `freeze_dump_*.json`**, and a `crash.untitled.User_32908.hiplc`. The latest halt record reads `pending_dispatches_cancelled: 0` with `pdg sweep failed: AttributeError` — by its own record it could not establish remaining state (INTENT §3: *"A timeout or a stop request alone is not proof that work has stopped"*). If that process dies, `/stage` is gone; the ledger replays **commands, not stage state**. The memo warns only about the risk of *saving*. Not saving is the larger risk and it has a clock.
→ **Ordering: copy the store dir out first (minutes), then save the hip, then delete the 11.**

**8. `loop/` — 551 attempt dirs, 17 `pending/`, 2.4 MB — examined by no lane.** Those 17 pending entries are interrupted operations, in the delete-adjacent volatile directory, absent from the keep list. INTENT §6: *"Each completed or interrupted operation MUST have a record connecting the engagement and proposal to its actual changes, execution route, verification results, and recovery status."* §3 `Paused`: *"the reason and any unfinished work are visible."* Those files are that record.

**9. The memo's UNKNOWN #2 is answered, and its evidence for "the directory was not wiped" is wrong.** `W1_MIGRATION_APPLY.json` (2026-08-09) records writing seven safety artifacts into that exact directory: `memory.jsonl.w1-pre-1786311015`, three `*.w1-collision-*`, and three preserved moneta files. **None of the seven is there now.** The pre-image and collision files were relocated to `~/.synapse/backups/w1_2026-08-09/POST_MIGRATION_…`; the three preserved moneta files are simply gone, leaving an empty `usd/`. The memo read *directory* mtimes (`.w1_incoming_moneta` Aug 9, `context.md` Aug 31) and concluded contents survived. The address-change mechanism is `scripts/w1_consolidate_stores.py` (on master, `4a0574cb`) plus a post-migration relocation — not UNKNOWN.
→ This is also the hard evidence that **"keep one copy in that directory" is not a retention plan.** Seven safety artifacts have already vanished from it.

**10. The 44 bytes nobody sized correctly.** `~/.synapse/encryption.key` decrypts the jsonl store, **and every audit ledger back to February — 147 MB across ~200 files** (I decrypted 09-14…09-17 with the same `CryptoEngine` to prove it), and the backups. One copy. And `~/.synapse` is **a git repo** whose `.gitignore` lists `*.key`, `audit/`, `memory.jsonl` — so a single `git clean -xfd` there destroys the key, the ledgers, and the store together. That is a larger single-command blast radius than anything in the memo's two mechanical warnings.

**11. INTENT.md §2 — cited by no lane — is stricter than the §3 argument the memo used.** *"Both optional capabilities MUST start disengaged in a new session… a saved preference MUST NOT restore an active delegation."* PID 54668 is a new session. Under §2 "pick that back up" cannot be a resume of the 19:48 engagement under any reading — it is a fresh Engage, full stop. The memo reached that conclusion hedged ("strictly"); §2 makes it unhedged.

**12. Unexamined risk in the applied repair.** The loader accepts `content: ""` (verified at `store.py:349-353`), so the repaired store's success signature — "865 loaded, 0 conflicts" — tolerates the two empty-content records the memo found (L541, L845). The memo noted them and drew no consequence: under the current id rule `sha256(content:created_at:type)`, two empty-content records of the same type sharing a one-second bucket collide. Any re-key or backfill touching this store must be checked against those two first. Also worth stating plainly: `_load` silently keeps the **first** copy when duplicates are canonically identical and raises only when they differ — so "0 conflicts" does not mean "no duplicates."

---

### What I checked and found nothing wrong with

Decision 1's central claim. All 12 files one hash, verified independently. The delete is lossless **as to those bytes**. Every gap above is about what else is in that directory, what is about to happen to it, and what the memo told you to back up.
