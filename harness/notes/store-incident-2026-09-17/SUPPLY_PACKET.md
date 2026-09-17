# SYNAPSE store supply packet -- 2026-09-17

Produced by a 5-lane support tier (one live-bridge consumer, three offline lanes, one fix assay),
then attacked by `memory-crucible` and an INTENT.md conformance auditor. Authority order: crucible
beats lane; a compositor re-measurement beats both and is stamped with its producer.

---

# SYNAPSE Store Supply Packet — 2026-09-17

**Status:** durable reference. Composed from five read-only lanes (S1, S2, S3a, S3b, S4), one adversarial crucible pass, and one INTENT.md conformance audit, then re-grounded by the compositor against the live machine at **2026-09-17 ~16:30 local**.

**Authority order used throughout:** crucible > lane. Where the crucible killed or corrected a lane fact, the corrected wording is used and the original is preserved, marked killed. Where the compositor re-measured, the compositor's measurement is stamped with its producer and supersedes both.

**Read this first:** the brief's framing — *"ALREADY REPAIRED … store now clean and writing"* — is true of the JSONL file and **false of the incident**. See §8 flag **N1**: the repaired JSONL is **253 records behind** the serving Moneta store, every one created inside the outage window. Reproduced independently by the compositor this session. Closing the incident on the brief's wording bakes that hole in.

---

## 1. Store census

Every store measured. `records` = lines that parse under `store.py`'s own loader; `conflicts` = ids appearing ≥2× with **different** canonical JSON (the condition that raises `conflicting duplicate memory identity` at `python/synapse/memory/store.py:356`).

| Path | Size (bytes) | Records | Distinct ids | Conflicts | Degraded now | Sibling copies | Distinct copy hashes |
|---|---|---|---|---|---|---|---|
| `C:\Users\User\AppData\Local\Temp\houdini_temp\untitled\.synapse\memory.jsonl` **(repaired)** | 1,424,126 | **882** | **882** | **0** | **no** | 12 | 1 (`2d8cc01b70b265fc`) |
| `D:\HOUDINI_PROJECTS_2025\Houdini21_Alien_Spaceship_Saucer\.synapse\memory.jsonl` | 53,762 | 39 (19 lines rejected) | 39 | 1 | **YES** | 1 | 1 (`0a7b9eead973fb2d`) |
| `D:\HOUDINI_PROJECTS_2025\HOUDINI21_SYNAPSE_DEMO\SYNAPSE_DEMO_v0001\scripts\.synapse\memory.jsonl` | 11,737 | 5 (8 lines rejected) | 5 | 3 | **YES** | 0 | — |
| `D:\HOUDINI_PROJECTS_2025\MPM_MASTERCLASS_FILES\.synapse\memory.jsonl` | 1,333 | 0 (2 lines rejected) | 0 | 0 | **YES** (schema, not dupes) | 0 | — |
| `C:\Users\User\SYNAPSE\untitled.hip\.synapse\memory.jsonl` | 32,511 | 21 (18 lines rejected) | 21 | 15 | **YES** | 0 | — |
| `C:\Users\User\.synapse\backups\w1_2026-08-09\10_repo_untitled_hip__dotsynapse\memory.jsonl` | UNKNOWN | UNKNOWN | UNKNOWN | 15 | **YES** | 0 | — |
| `C:\Users\User\.synapse\backups\w1_2026-08-09\POST_MIGRATION_canonical_02_htemp_untitled__dotsynapse\memory.jsonl` | UNKNOWN | UNKNOWN | UNKNOWN | 15 | **YES** | 0 | — |
| `C:\tmp\untitled.hip\.synapse\memory.jsonl` | 34,481 | 41 | 41 | 0 | no | UNKNOWN | — |
| `C:\Users\User\OneDrive\Documents\ChatGPT\SYNAPSE_Refactor\.synapse\memory.jsonl` **(cloud-synced)** | 11,886 | 10 | 10 | 0 | no | UNKNOWN | — |
| 4 further `w1_2026-08-09` backups (`01_home`, `02_htemp_untitled`, `08_repo_LITERAL_HOUDINI_TEMP_DIR`, `12_home_untitled_hip`) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | **UNKNOWN — never scored** | — | — |
| 11 stores under `C:\synapse-build\` | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | **UNKNOWN — never scored** | — | — |

**Producers.**
- Repaired-store row, this session: `scratchpad/packet_verify.py` — decrypts every line via `from synapse.memory.store import _get_crypto`, counts ids, compares canonical JSON per duplicate id. Output verbatim: `LIVE lines_parsed 882 undecodable 0 distinct_ids 882 dup_ids 0 conflicting_ids 0` / `created_at min 2026-09-01T00:16:02Z max 2026-09-17T20:30:36Z`.
- Sizes/mtimes: `stat -c '%s %y' <path>` and `ls -la <dir>`.
- Sibling copies + hash grouping: `ls -la /c/Users/User/AppData/Local/Temp/houdini_temp/untitled/.synapse/` (12 files: 11 `memory.jsonl.degraded-load-*` + 1 `memory.jsonl.pre-repair-1789674797`, each 1,394,474 bytes) and lane S2's sha256 grouping (`siblings=12 distinct_contents=1`).
- Per-store degraded counts: lane S2 replicated `store.py:355-359` verbatim over every store found. Crucible verified these counts as **exact**.
- Backup root located this session: `find /c/Users/User -maxdepth 8 -path "*backups*" -name "memory.jsonl"` → 6 directories under `C:\Users\User\.synapse\backups\w1_2026-08-09\`.

**Six SYNAPSE memory stores are refusing every write right now: `Houdini21_Alien_Spaceship_Saucer`, `HOUDINI21_SYNAPSE_DEMO\SYNAPSE_DEMO_v0001\scripts`, `MPM_MASTERCLASS_FILES`, `C:\Users\User\SYNAPSE\untitled.hip`, and the two W1 backups `10_repo_untitled_hip__dotsynapse` and `POST_MIGRATION_canonical_02_htemp_untitled__dotsynapse`. The repaired `untitled` temp store is the only previously-degraded one now writing.**

Two caveats on that sentence, both load-bearing:

1. **"Refusing writes right now" is proven for file state, inferred for runtime.** A degraded `MemoryStore` refuses writes only once a process opens it. Lane S2 was forbidden from touching the bridge. Which store Houdini PID 54668 has mounted is not established from disk alone. *(S2 unknown #1, unresolved.)*
2. **The census is not exhaustive and its own summary overclaimed.** Lane S2's summary sentence said *"20 memory.jsonl stores exist on this machine."* **CORRECTED (crucible C6):** a full sweep measures **7,605 base `memory.jsonl` files (8,966 including suffixed copies) across C: and D:** — the overwhelming majority pytest tmp dirs. Four non-test stores the census missed are now in the table above. **Not walked:** the remainder of C:, D:, G:, and E:/F:/H: if present. A store outside those paths is still missed.

### 1a. The three distinct failure classes in that list

| Class | Stores | Shape |
|---|---|---|
| **Shape A** — metadata-stripped twin | `untitled` temp store only (5 ids) | Adjacent line pair, identical content, identical `created_at`, second copy stripped: `tags=[]`, `hip_file=''`, `frame=None`, `hip_version=0`, `source 'ai'→'auto'`. Lines 1/2, 6/7, 33/34, 36/37, 39/40 of the pre-repair file. |
| **Shape B** — timestamp-only id collision | Alien Saucer (1), SYNAPSE_DEMO (3), repo `untitled.hip` (15), both W1 backups (15 each) | Non-adjacent repeats of one id, byte-identical content, variants differ **only in `created_at`/`updated_at`** — plus `hip_file` in SYNAPSE_DEMO's three (crucible **C7**). Alien Saucer's `mem_2f1bc0bbb623` occupies 20 lines with 20 distinct variants. |
| **Schema mismatch** | `MPM_MASTERCLASS_FILES` | **Plaintext, no `SYNAPSE_ENC_V1:` prefix**, pre-migration keys `{content, tags, timestamp, type}`, missing all four of `id`/`created_at`/`content`-as-str/`memory_type`. Zero recoverable records. No dedupe repair can fix it. |

**Shape A appears on exactly one store and nowhere else on this machine** — verified across all five other degraded stores including both backups of the same lineage (`ShapeA=0` in every one). One instance is not enough to call it systematic or one-off; what *is* settled is that the other five do not corroborate it.

Shape B is a **historical** id-collision defect. Ids were once timestamp-independent — `mem_2f1bc0bbb623` and `mem_3565ce339c45` each appear in four independent stores with identical content and different `created_at`. The current formula at `python/synapse/memory/models.py:157-162` already fixes that. The Feb-2026 files are fossils.

**But see §4: the Shape B fix is the Shape A cause.**

---

## 2. Live scene ground truth

**Measured by the compositor, 2026-09-17 ~16:30 local, over `ws://localhost:9999/synapse`.**
**Producer:** `synapse_inspect_stage target_path=/stage` — full per-node `inputs`/`outputs`/`display_flag`/`error_state` arrays.

```
GEO_sphere (sopcreate, display_flag TRUE, in=[])
  └─> MTL_hero (materiallibrary, ERROR)
        └─> MTL_matlib (materiallibrary)
              └─> CAM_main (camera)
                    └─> LGT_area (light::2.0)
                          └─> LGT_dome (light::2.0)
                                └─> karma_settings (karmarendersettings)
                                      └─> OUTPUT (null)        ← reached

GEO_sphere1 (sopimport, ERROR, in=[], out=[])                  ← ORPHAN
```

**What is wired:** one linear 8-node chain. It **does** reach `OUTPUT`, with `karma_settings` wired in as the last upstream node.

**What is orphaned:** `GEO_sphere1` (`sopimport`) — `inputs:[]`, `outputs:[]`, `display_flag:false`, and it carries an error.

**Errors:** 2 of 9 nodes are in `error_state: "error"` — `GEO_sphere1` and `MTL_hero`, both with the identical message:

> `Unable to evaluate expression (Traceback … IndexError: tuple index out of range (/stage/GEO_sphere/ineditlayerblock)).`

The other seven are `clean`.

### 2a. Lane S1 had the two geometry nodes inverted. This is the packet's most dangerous correction.

**KILLED (crucible K4, re-confirmed by the compositor on a third independent measurement):** S1-1 and S1-3 reported `GEO_sphere1` as the chain root and `GEO_sphere` as the *"fully orphaned, empty"* node and *"a REGRESSION."* The opposite is true.

**`GEO_sphere` is the root of the renderable chain.** A human acting on S1's wording — deleting or rebuilding `GEO_sphere` — **severs the chain that feeds `MTL_hero → … → karma_settings → OUTPUT`.**

**KILLED, second order:** S1-1's *"the viewport shows the orphan, not the renderable chain."* `display_flag:true` sits on `GEO_sphere` — the chain **root**. The display flag is on the right node. *(This kill is the compositor's, derived from the same measurement; it was not stated by the crucible, and it removes one of the two halves of INTENT §7 finding V7-4 in §6 below.)*

### 2b. The reframe this inversion creates — and it is worse, not better

Lane S1 ran `houdini_network_explain root_path=/stage/GEO_sphere depth=3` and found the interior **empty**: `sopnet` has exactly 2 children (a subnet `create` and a null `OUT`), and `create` reports no children — no sphere SOP. That probe was anchored by **path**, not by the inverted label. It therefore describes **the chain root**, not the orphan.

Read correctly: **the renderable chain's source node may contain no geometry.** The `ineditlayerblock` expression error on `/stage/GEO_sphere` corroborates a broken interior.

**Status: UNKNOWN — not re-measured this session.** One `houdini_network_explain root_path=/stage/GEO_sphere depth=3` closes it.

S1's regression claim (live telemetry recorded an earlier selection of `/stage/GEO_sphere/sopnet/create/sphere1`, a node that no longer exists, at frame 127.0) likewise attaches to the chain root. It is **uncorroborated as to authorship** and stays UNKNOWN.

### 2c. Materials: both libraries author shaders bound to nothing

**SURVIVES verification.** Both `MTL_hero` and `MTL_matlib` are `materiallibrary` nodes with byte-identical assignment parms: `assign1=0` ("Assign to Geometry" **off**), `geopath1=""`, `matpath1=""`. The renderable chain contains **no `assignmaterial` LOP at all** — the only one in the whole `/stage` subtree sits inside `/stage/GEO_sphere/assignmaterial`, i.e. inside the chain root's broken interior.
**Producer:** `synapse_inspect_node /stage/MTL_hero` and `/stage/MTL_matlib`; `houdini_network_explain /stage/GEO_sphere`.

**Compositor amendment:** at measurement time `MTL_hero` authors **no** prims (`usd_prim_paths: []`) because it is in error; only `MTL_matlib` authors `/materials/MTL_matlib_shader`. S1's statement that both report authored prims does not hold now. Whether the shader VOPs inside either library author valid MtlX surfaces was never inspected — **UNKNOWN**.

### 2d. Four contradictory recipes are live in recall simultaneously

**SURVIVES.** Four mutually contradictory definitions of the same trigger phrase are in recall at once — v1 canned, v2 gold-flake, v3 named-node (`GEO_sphere` + `MTL_matlib` + `karma_settings1` + `OUTPUT1`), v4 full studio lookdev rig (`Assets`, `lightmixer1`, `usdrender_rop1`). **None retracts its predecessor.** The live scene is a hybrid: it contains v3's `MTL_matlib` alongside an `MTL_hero` and a `sopimport` that appear in no recipe.
**Producer:** `synapse_context` → `recent_decisions` ids `mem_5e63df8d83e6`, `mem_cb67ac3da274`, `mem_9e0826890122` (all 2026-09-06) + a fourth v4 entry in `scene_memory` "Scene Decisions".

### 2e. Two tool defects found while measuring

- **CORRECTED (C4):** S1 reported `houdini_network_explain path=/stage` as *"timed out — Houdini may be busy."* It is **deterministic, not load-related**: the call returns `Type is not JSON serializable: Ramp`. The same error blocks `synapse_inspect_node path=/stage/karma_settings`. A reproducible serialization defect, not a retry candidate.

---

## 3. Live health surfaces

**Question: would a degraded store be visible to the artist through any of them? No.**

| Surface | Actual output about store state | Degraded visible? |
|---|---|---|
| `synapse_memory_status` | keys exactly `[agent, entries_total, project, scene]`; `entries_total: 1108`; `agent` is hardcoded `{"status":"idle","task_count":0,"suspended_count":0}` | **No — no `health` or `degraded` key exists** |
| `synapse_context` | no health/degraded key whatsoever | **No** |
| `synapse_health` | `write_plane.store {"serving_class":"MonetaBackedStore","serving_jsonl":false,"requested_backend":"moneta","durable":true,"status":"ok"}`; `targets.memory {"path":"C:\\…\\untitled\\.synapse","writable":true,"detail":null}` | **No — reports `ok` / `writable: true`** |
| `synapse_doctor` | summary `{"fail":1,"ok":13,"skipped":0}` — the single fail is a version stamp. The outage appears **only** as `degraded_quarantine_count: 11` nested inside the `result` dict of check `memory_key_fingerprint`, whose own `status` is `"ok"` and whose human-readable `detail` reads `"active key fingerprint 6aa8f313 matches the store sidecar"` — never mentioning it | **Effectively no** |
| `synapse_doctor` → `write_plane_store` | `backend_health {"status":"SUCCESS","verdict":"SUCCESS"}` over exactly that substrate (crucible **N3**) | **No** |

All rows verified by the crucible as exact.

### 3a. Why every light stayed green — corrected, and worse than the lane stated

Lane S1-5 said `write_plane`'s per-target check is *"a DIRECTORY-writability probe, not a MemoryStore state read."*

**CORRECTED (crucible C3):** `python/synapse/server/write_plane.py:355-428` **does** evaluate the store — serving class, `store.count()`, moneta durability. It simply **never reads `_degraded_load`**. And `count()` at `store.py:601` carries **no `_require_writable_load` guard**, so it succeeds on a degraded store.

> **Corrected wording (use this):** *"`write_plane` evaluates the serving store but never reads `_degraded_load`; because `count()` succeeds on a degraded store, a serving MemoryStore refusing every write would still report `write_plane=ok`."*

This settles lane S1's open unknown #3 **in the dangerous direction**. The green light is not merely measuring a different object — it would stay green even if the *serving* store were the one refusing writes.

### 3b. The one surface that lied outright

`python/synapse/server/handlers_memory.py:252-253`:

```python
write_memory_entry(paths["scene_dir"], content, entry_type)
return {"written": True, "entry_type": entry_type, "scope": scope}
```

`write_memory_entry` returns `None`. `True` is a **literal**, not a result. For the whole outage, `synapse_memory_write` returned a measured-looking success for a write that was refused. **Survives verification.**

### 3c. What the outage was NOT — the packet's most consequential kill

**KILLED (crucible K3).** Lane S4-4 concluded the two-day silence was caused by swallowed exceptions, singling out the DEBUG-level catch at `python/synapse/memory/scene_memory.py:739-740` as *"worse"* and asserting *"nothing in the return value, the exception surface, or any non-debug log says the memory was dropped."*

Compositor re-verification against `C:\Users\User\.synapse\logs\synapse.log`:

| Producer | Result |
|---|---|
| `grep -c "JSONL dual-write failed"` | **253** WARNING lines |
| `grep -c "Moneta deposit from scene_memory failed"` | **0** — the DEBUG swallow S4 called "worse" **never fired** |
| `grep -c "DEGRADED LOAD"` | **45** total (crucible: 13 non-pytest ERROR) |

**The outage was loud at WARNING and ERROR. It was invisible only in the tool/UI surface.** S4-6's remediation ranking put item (a) on a mechanism that did not fire; that ranking is dead and is re-derived in §5.

---

## 4. Root cause — competing writers

### 4a. The single highest-value fact

**`MemoryStore.save()` is ATOMIC — tmp + fsync + `os.replace`. It does NOT rewrite in place. A halt mid-rewrite cannot produce this corruption.**

`save()` at `python/synapse/memory/store.py:462` builds full content in memory, then delegates to `write_report(...)` at `store.py:493-497`. The producer, `python/synapse/cognitive/tools/write_report.py:146-163`: `tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")` → write → `fh.flush()` → `os.fsync(fh.fileno())` → **`os.replace(tmp, target)`**, with `os.unlink(tmp)` on any `BaseException`. Its own comment: *"Atomic (tmp + fsync + os.replace) with one generational .bak — a crash mid-save leaves the prior file intact instead of truncated."*

**There is no in-place full rewrite anywhere in this path.** The textbook "interrupted rewrite" hypothesis is **refuted**. Survived crucible verification.

### 4b. PROVEN — one call writes the same content twice

Ranked #1. Every link verified; the crucible confirmed the id formula, the pair shapes and dates, and added one correction.

**Mechanism.** A single call to `tracker.handle_memory_add` writes the same content into the same `memory.jsonl` twice:

1. **Rich record** — `self._synapse.add(..., source="ai")` at `python/synapse/session/tracker.py:492-498`.
2. **Stripped twin** — `write_memory_entry(paths["scene_dir"], {"content": content}, "note")` at `tracker.py:507`, landing at `python/synapse/memory/scene_memory.py:729-734`:

```python
syn.store.add(Memory(
    content=entry.get("content", ""),
    memory_type=MemoryType.NOTE,
    tags=entry.get("tags", []) or [],
    source="auto",
))
```

with `hip_file` / `hip_version` / `frame` left at dataclass defaults.

**CORRECTED (crucible C8):** the deposit is **conditional**, not unconditional — the guard at `scene_memory.py:728` is `if hasattr(syn.store,'add') and not isinstance(syn.store, MemoryStore)`. Mechanism unaffected: moneta is the live backend, so the branch is taken.

**Why the ids collide.** `python/synapse/memory/models.py:157-162`:

```python
content_hash = hashlib.sha256(
    f"{self.content}:{self.created_at}:{self.memory_type.value}".encode()
).hexdigest()[:12]
```

The hash excludes **every field that differs** between the twins — `tags`, `hip_file`, `hip_version`, `frame`, `source`. Two writes of the same content and type inside one whole second produce the **same id with different canonical JSON**, which is exactly the condition `store.py:353-358` raises on.

**Corroboration that type participates:** the lossy path hardcodes `MemoryType.NOTE` (`scene_memory.py:731`), and **all 5** conflicting pairs are type `note`, while `decision` records written 3-4s later in the same sessions (pre-repair lines 35, 38, 41) are **unpaired**.

**Corroboration that `scene_memory.py:729` is the unique producer of the stripped shape:** all four other `_deposit_to_moneta_if_available` call sites (`scene_memory.py:815, 864, 908, 950`) pass **non-empty** tags, and every other `source="auto"` producer in the tree (`tracker.py:168,195,407`; `render_diagnostics.py:365`; `render_farm.py:666`) routes through `SynapseMemory.add`, which populates `hip_file`/`frame`. Only `:729` matches the stripped record field-for-field.

**Timing.** `created_at` is **identical** in every Shape-A pair — the two copies were written in the same second. That rules out a re-add-later path and points at one write emitting two records.

### 4c. PROVEN — the fix for Shape B is the cause of Shape A

Crucible **N5**, not present in any lane. `models.py:145` states `created_at` was added to the hash so *"the same content logged at different times gets distinct ids"* — at **second** granularity. That is precisely what makes two writes in the same second collide. Lane S2-F4 presented the current generator as the fix for the historical Shape B defect; **it is also the cause of Shape A**. Any repair to the id formula must hold both ends.

### 4d. PROVEN — a second MemoryStore handle on the same directory, invisible to the census built to find it

`python/synapse/memory/moneta_store.py:357`: `jsonl_net = MemoryStore(storage_dir)` — a second `MemoryStore` on the same `storage_dir`. Gate at `:348-352`: `dual_write_jsonl = (os.environ.get("SYNAPSE_MEMORY_BACKEND","").strip().lower() == "moneta")`. `packages/synapse.json:27` sets `SYNAPSE_MEMORY_BACKEND` to `moneta`, and `.moneta/cortex_root.usda` + `snapshot.json` exist on disk — **the branch is live**.

Result: one `memory.jsonl`, two `_memories` dicts, two flusher threads, two atexit hooks. And `memory_handle_census()` (`store.py:1838-1874`) reports only `_global_synapse` and `ledger._MONETA_STORE` — **it cannot see `_jsonl_net`**. Six further unregistered `MemoryStore` constructions exist outside `store.py`: `memory_lifecycle.py:341`, `backfill.py:53`, `migrate.py:344`, `sqlite_store.py:755`, `writethrough_store.py:79`.

**Runtime corroboration (crucible N4):** the Alien Saucer store logged two `DEGRADED LOAD` errors **100 ms apart** (`11:17:34,488` / `,588`) and produced **one** quarantine file — same-second epoch, second copy overwrote the first. Two handles, one second, one surviving artifact.

### 4e. Corrected timeline — the outage was a new check meeting old data

**The detector that degrades the store shipped on 2026-09-15 at 15:33:27**, in commit `ef690e50` *"Repair demo layouts and scoped memory ownership (#83)"* — the only commit in `store.py`'s history introducing the string.
**Producer:** `git log --format='%h %ad %s' --date=iso -S "conflicting duplicate memory identity" -- python/synapse/memory/store.py` → single result.

**KILLED (crucible K1).** Lane S3b-F2 concluded *"a full rewrite ran in that 36-second window and emitted 5 pre-existing ids twice,"* resting on `839 + 2 + 5 = 846` and *"an append-only writer cannot insert a line at position 2."* **Both premises are wrong.** `store.py:363` loads into a **dict keyed by id**, and `store.py:409` logs `len(self._memories)` — **`Loaded N` is a distinct-id count, not a line count.** The log shows `Loaded 839` twice (12:13:30 *and* 15:08:53): two clean loads of a file that already held 844 lines / 839 ids, the 5 duplicate lines silently deduped by the pre-`ef690e50` loader. Two appends at 19:09:28/29Z → 846 lines / 841 ids. **No rewrite.** The duplicates were appended adjacently during 2026-09-01..09-06, when line 2 *was* the end of the file. Independent disproof of "position implies write-time": current `memory.jsonl` lines 859–862 are the newest appends and carry `created_at` of 09-13/09-14.

**Corrected sequence:**

| When (local) | What | Producer |
|---|---|---|
| 2026-09-01 .. 09-06 | The 5 duplicate pairs are **appended**. Loader silently dedupes them. | `created_at` on pre-repair lines 1/2 (`2026-09-01T00:16:02Z`), 6/7 (`2026-09-02T13:14:29Z`), 33/34 (`2026-09-06T00:45:17Z`) |
| 09-15 12:13:30, 15:08:53 | Two **clean** loads, `Loaded 839`, zero conflict warnings | `synapse.log:934` |
| 09-15 15:09:28/29 | Last successful writes. File freezes at 846 lines / 841 ids. | max `created_at` `2026-09-15T19:09:29Z`; quarantine copies' preserved mtime `Sep 15 15:09` |
| **09-15 15:33:27** | **Detector ships (`ef690e50`)** | `git log -S` above |
| 09-15 17:12:11 | **First degraded load.** Writes now refused. | quarantine epoch `1789506731` |
| 09-15 17:12:11 → 09-17 15:42:15 | **11 degraded loads**, ~one every 4h over ~46h | 11 epoch suffixes, §4f |
| 09-17 15:53:17 | Repair performed; `pre-repair` copy written | epoch `1789674797` |

**So the brief's "outage 15:09 → 15:53" should read: last successful write 2026-09-15 15:09:29; first refusal 2026-09-15 17:12:11.** The ~2h gap is the interval between the last write and the first load under the new code.

### 4f. Corrected quarantine epoch list

**CORRECTED (crucible C2), re-verified this session by `ls -la` on the store directory.** Lane S2-F6 listed `1789571854` (2026-09-16 11:17:34) among the untitled store's suffixes — that file **does not exist there**; it is the **Alien Saucer** store's sole quarantine epoch. S2-F6 omitted `1789674135` (2026-09-17 15:42:15), which **is** present.

The 11 degraded-load epochs, verified present:

```
1789506731  2026-09-15 17:12:11
1789507423  2026-09-15 17:23:43
1789508001  2026-09-15 17:33:21
1789509778  2026-09-15 18:02:58
1789513143  2026-09-15 18:59:03
1789561952  2026-09-16 08:32:32
1789585035  2026-09-16 14:57:15
1789603251  2026-09-16 20:00:51
1789652284  2026-09-17 09:38:04
1789673481  2026-09-17 15:31:21
1789674135  2026-09-17 15:42:15   ← omitted by S2-F6
+ 1789674797  2026-09-17 15:53:17  (memory.jsonl.pre-repair-*)
```

**Corrected span: 17:12:11 → 15:42:15.** Totals unchanged and verified: **12 files, 1 distinct sha256 (`2d8cc01b70b265fc`), 16,733,688 bytes** (12 × 1,394,474).

**All 12 carry mtime `2026-09-15 15:09`** because `shutil.copy2` (`store.py:322`) preserves it. **They are 12 snapshots of one frozen file, not 12 corruption events.** Any retention decision that reads those mtimes as incident times reads them wrong.

### 4g. HYPOTHESIS — not proven, not ruled out

**H1 — flush/save interleave loses or duplicates an append.** `_flush_writes` appends with `open(self.memory_file, 'a')` (`store.py:268`) holding only `_write_lock`, while `save()` (`store.py:471`) builds a replacement under the **disjoint** `_lock.write_lock()` and lands it via atomic replace. An append landing between tmp-build and replace is silently **discarded**. Separately, `_flush_writes` (`store.py:237`) drains the buffer *outside* the lock it later saves under (`:249-255`), so an `add()` landing between drain and save can be written **twice**.
**Status:** predicts LOSS at EOF and duplication at EOF — **does not explain** lines 2/7/34/37/40 of the pre-repair file. A separate defect, unruled.
**Settling probe:** instrument `write_report`'s replace and `_flush_writes`' append with a shared counter under a synthetic 50 ms stall; assert appended-line count == on-disk-line delta. Not run — read-only.

**H2 — buffered memories vanish on hard kill.** `add()` (`store.py:529`) never calls `save()`; it appends to `_write_buffer` (`:548`), drained by a 2s background thread. Drain-on-exit is `_shutdown_flush` (`:580`), an **`atexit` handler** — a hard crash or `TASKKILL` skips it and buffered memories disappear with no record. Real defect; silent loss, not duplication.

### 4h. KILLED hypotheses — do not re-run these

- **KILLED (K1):** "a full rewrite ran in the 36-second window." See §4e.
- **KILLED (K2):** lane S3b's *"strongest lead"* — two mirror writers, `WriteThroughStore.add` doing *"a full rewrite on every add."* **`WriteThroughStore` has zero production construction sites** — only `tests/test_w3_migrate.py:287,293,316,336`. **Dead code.** There is exactly one JSONL writer: `moneta_store.py:_dual_write_jsonl` → `net.add()` + `net.flush()`, **append-only**.
- **KILLED (K3):** "the DEBUG swallow is the mechanism of the two-day silence." It never fired. See §3c.
- **REFUTED (lane S3a-6, verified):** the double-construct race from AUDIT 2026-08-21 §C. `get_synapse_memory()` is now double-checked locking under `_GLOBAL_LOCK = threading.RLock()` (`store.py:1750`, `:1790-1821`) with a post-construction re-check calling `_close_memory_quietly(built, "superseded")` at `:1810`. Landed `129598bb` 2026-08-21 — **three weeks before** the corruption window.
- **REFUTED (lane S3b-F3):** crash/freeze/halt near the window. Earliest emergency halt on disk is `emergency_halt_20260915_205342.json` — **5h44m after**. Earliest freeze dump is `freeze_dump_20260916_010648.json`. The session detached cleanly at 15:25:43 (*"runtime beat: panel detached deliberately"*).
- **CLEAN NEGATIVE (lane S3b-F6):** no test writes a real store path. Every test-authored store on 09-15 is under `…\pytest-of-User\pytest-{4181,4294,4298,4301,4319,4326,4330,4333}\…`. The alarming `WRITE-THROUGH NET FAILED … disk full` errors (log lines 415, 1366, 2400, 3229, 5116, 7269, 7661, 8365) are **deliberate fault injection** inside `test_writethrough_write_lands_0` tmp dirs. Contamination is log-channel and port, not data.

### 4i. A live risk found in passing

The log is shared by at least two process families. Non-Houdini runs log `Cannot start hwebserver: hwebserver not available — must run inside Houdini` (15:04:03, 15:16:59, 15:57:34, 16:31:16 …) and **also bind `ws://localhost:9999`** — a port collision with the live bridge is a live risk. Whether they ever raced the bridge: **UNKNOWN, not checked.**

Every `Initialized for project` line on 2026-09-15 resolves to exactly one of the untitled store, a `D:\` project, or a pytest tmp dir. **No two concurrent inits of the untitled store.** The 15:08:53 → 17:12:10 gap is a single writer.

---

## 5. Fix assay

### 5a. Test coverage — the defect is invisible to the suite by construction

`tests/test_store_degraded_load.py` (122 lines, 3 tests) pins the **wrong-key** and **plaintext-garble** degraded paths: `_degraded_load is True`, `save()` raises, original bytes preserved, and a copy exists —

```python
# tests/test_store_degraded_load.py:91-93
quarantines = [p for p in tmp_path.iterdir() if p.name.startswith("memory.jsonl.degraded-")]
assert quarantines
```

`tests/test_m3_logs_doctor.py:369-373` writes one fixture `memory.jsonl.degraded-123` and asserts the doctor count `== 1`.

**Not pinned anywhere in `tests/`:**

| Thing | Coverage |
|---|---|
| the string `conflicting duplicate` | **zero hits** |
| `_quarantine_store` by name | **zero hits** outside `store.py` + `.pyc` |
| **repeat** quarantine | **none** — every test loads a degraded store exactly once |

`quarantines[0]` at `:91` passes identically with 1 copy or 11. **The unbounded-growth defect has no failing test to turn green, and the actual trigger has no test at all.**

### 5b. In-repo precedent to match — both halves already exist

**Content-addressed naming, canonical form** — `python/synapse/server/network_layout.py:170`:

```python
section["box_name"] = "synapse_layout_" + hashlib.sha256(token.encode()).hexdigest()[:16]
```

Same `[:16]` truncation as CLAUDE.md §1.4's `sha256(...).hexdigest()[:16]` in `shared/bridge.py:_topo_hash`.
**Content-addressed path** — `python/synapse/farm/native_driver.py:410`: `package_root / "assets" / receipt["sha256"] / original.name`.

**Atomic write, canonical form** — `python/synapse/cognitive/tools/write_report.py:146-163` (see §4a). Roughly 16 call sites follow it: `memory/store.py:493`, `memory/moneta_store.py:634`, `host/retina_manifest.py:208`, `panel/settings.py:195`, `farm/package.py:35`, `loop/coordinator.py:44`.

**`_quarantine_store` uses plain `shutil.copy2` (`store.py:322`) — it currently matches neither.** A fix can adopt naming *and* atomicity from house style in one change.

### 5c. Blast radius of changing the quarantine filename — one reader, and it does not break; its MEANING changes

`python/synapse/server/doctor.py:323-324`:

```python
result["degraded_quarantine_count"] = len(
    list(store_dir.glob("memory.jsonl.degraded-*"))
)
```

Prefix glob — `memory.jsonl.degraded-load-<sha16>` still matches. Nothing parses the timestamp; nothing breaks.

But `docs/moneta-production-harness-architecture.md:610` thresholds that count at **ok `0` / warn `≥1` / critical `≥5`**, with the rationale *"Quarantined files indicate key-mismatch events. **Each one is a manual-recovery incident.**"*

Content addressing redefines the metric from *incidents* to *distinct degraded states*. **This outage reads 11 (critical) today and 1 (warn) after the fix, from identical reality.**

No other code, script, runbook, doc or test consumes the suffix.

**Consequence: the manifest is not optional.** It is where the incident count has to live, or the doctor's critical threshold stops firing on exactly this class of event.

### 5d. What "isolated" swallows in the dual-write path

Two nested swallows. Both are real; **only the outer one ever fired.**

**Outer** — `python/synapse/memory/moneta_store.py:784-785`:

```python
except Exception as exc:  # noqa: BLE001 -- the safety net must never break the caller
    logger.warning("JSONL dual-write failed (isolated): %s", exc)
```

`_dual_write_jsonl` returns `None`; its caller `add()` then does `return memory.id` (`:753`) unconditionally. Header at `:745-748`: *"a sink failure is logged and never breaks the caller or the moneta write."*
**Fired 253 times.** `grep -c "JSONL dual-write failed" C:\Users\User\.synapse\logs\synapse.log` → `253`.

**Inner** — `python/synapse/memory/scene_memory.py:739-740`:

```python
except Exception as exc:
    logger.debug("Moneta deposit from scene_memory failed (non-critical): %s", exc)
```

**Fired 0 times.** `grep -c "Moneta deposit from scene_memory failed"` → `0`.

**The raise being swallowed is real and constant:** `store.py:450-460` `_require_writable_load` raises `RuntimeError` on `_degraded_load` and guards all six mutators (`:464, 514, 535, 567, 584, 609`).

**The precise defect:** a **correct, complete, artist-ready failure message was authored and then discarded**. `store.py:455-460` raises:

> *"Refusing to write: the store loaded in DEGRADED mode. Original bytes are preserved; recover the source or encryption key, then reopen."*

That text contains the actual limit, the partial result, and the recovery option. It reached the log at WARNING 253 times and reached **no tool surface at all**, because the caller returns `memory.id` as if it succeeded and `handlers_memory.py:253` returns literal `{"written": True}`.

### 5e. Assay verdict — re-derived, because the crucible killed S4's ranking

Lane S4-6 ranked remediation `(a)` the swallows → `(b)` a degraded flag → `(c)` content addressing, on the theory that the swallows were *"why nobody knew."* **K3 killed that premise:** the outage was loud in the log; the DEBUG swallow never fired.

**Corrected ranking:**

| Rank | Fix | What it buys | Why here |
|---|---|---|---|
| **1** | **Surface `_degraded_load` through `_handle_memory_status` and the doctor**, and stop returning literal `{"written": True}` | The artist can ask "is my memory OK?" and get the answer | The message §9 demands **already exists verbatim** at `store.py:455-460`; three handlers discard it. Cheapest conformance gain in the packet, touches **zero bytes of evidence**. |
| **2** | **Propagate the failure to the caller** — a result object instead of an unconditional `return memory.id` / literal `True` | A caller can distinguish "written" from "silently dropped" | The 253 WARNINGs prove the signal exists; nothing carries it up. |
| **3** | **Content-addressed quarantine suffix + manifest** | Stops ~15 MB of byte-identical copies; makes the side effect idempotent | **Must ship bundled with the manifest** — alone it drops the doctor alarm critical→warn (§5c). |

**Shipping (3) alone produces a tidier version of a silent outage.**

**Unresolved design question, flagged not decided:** retention-cap semantics. Under content addressing, capping by **count** would evict the **oldest distinct state** — the most recoverable one. INTENT §3 reserves this to the human.

**New blocker that outranks all three:** §8 **N1** — the 253-record reconciliation hole. None of the three fixes closes it.

---

## 6. INTENT.md conformance

Method note, binding: INTENT.md's own header states *"The requirements in this document define intended behavior. They do not certify that a capability has shipped or passed runtime qualification."* Shipped behavior violating a binding clause is scored as a violation; an unbuilt capability is not.

**One structural fact recurs below:** `grep -rIn 'engagement' python/` → **no hits**. There is no engagement controller, no engagement ID, no change boundary, no action scope. That is an unbuilt capability for §2/§3's *capability* rows — but it means §6's record clause, which requires a record connecting *"the engagement and proposal"* to its outcome, has **no anchor to connect to**. Every §6 finding inherits that.

### §3 — Engagement and control contract

**V3-1 — `Unavailable` was never reported. Two days, eleven reloads.**
> *"| Unavailable | A required execution or observation capability cannot operate; the reason is reported. |"*

The store computed the reason (`store.py:397-401`) and raised it (`store.py:455-460`). It reached the log and **no artist surface** (§3). The reason existed; it was never reported to the operator. **VIOLATION.**

**V3-2 — Eleven silent reloads are eleven silent resumptions.**
> *"**Resume:** requires a deliberate artist action and fresh validation of the affected scene. Restart, reconnection, scene replacement, and model suggestions MUST NOT silently resume an engagement."*

Eleven distinct degraded loads (§4f epoch list). Each was a reconnection that re-attempted the load, re-ran `_quarantine_store`, re-set degraded, and told nobody. No artist action gated any of them; no fresh validation preceded any. **VIOLATION** — and it is the clause the retention decision turns on: **the eleven copies are eleven prohibited silent resumptions, not eleven corruption events.**

**V3-3 — The applied repair has no recorded owner, and §3 forbids inferring one.**
> *"The host MUST validate this scope. A model-supplied ownership claim, scene identity, permission, or confidence value cannot authorize an operation."* / *"**Engage:** requires a deliberate artist action tied to the task."*

The repair is described in the passive voice; on disk the only artifact is `memory.jsonl.pre-repair-1789674797`, unannotated bytes. Searched for an authorization trail: `harness/memory/bus/` newest is `memory_m3_envoy.json` (2026-08-22); `harness/memory/notes/` newest is `CONTRACT_AMENDMENT_v02.md` (2026-08-22); no commit touches `python/synapse/memory/` since 2026-09-16; `decisions.md` in the live store dir is an **empty template** (114 bytes, mtime Sep 15 18:59 — verified by `ls -la`). **VIOLATION, or at minimum unprovable** — and §3 puts the burden on the host to have validated it.

**§3 requirement no lane addressed — the scene resume gate does not exist.**
`grep -rIn -e 'recorded baseline' -e 'baseline_hash' -e 'stale' python/synapse/cognitive/ python/synapse/server/` → **zero hits**. `grep -e 'revalidat' -e 'recheck'` across `propose_graph.py` and `handlers_solaris_graph.py` → **zero hits**. What exists is narrower: `handlers_solaris_graph.py:216 validate_graph(...)` validates the **proposal's structure**, and `:166-178` resolves a name collision by comparing `existing_base` to `wanted_base`. That is node-level type sanity, not a recheck of scene revision against a recorded starting state.

The hazard is live: §2d's four contradictory recipes are *"model suggestions"* in exactly the sense §3's Resume row prohibits as a resumption trigger, and the hybrid scene is evidence one already fired. §3's **Starting state** field (*"Observed revision of affected scene state and dependencies, including unresolved facts"*) was never captured for the repair beyond opaque bytes.

**Recommendations that would violate §3 if acted on:**

| Implied recommendation | §3 risk |
|---|---|
| Retention cap / eviction of quarantine copies | Irreversible destruction of the only pre-repair evidence |
| Batch-repair the other 5 degraded stores | Five stores the artist never asked about, on **model-selected scene identity** — explicitly forbidden |
| Resume/repair the half-built Solaris scene | Requires deliberate artist action **and** fresh validation; neither exists |

### §5 — Computer Use and execution ownership

**V5-1 — The route is not recorded. Not partially: the field does not exist.**
> *"SYNAPSE SHOULD choose the most dependable supported execution route for each operation. … **The route used MUST be recorded.**"*

The `Memory` dataclass (`models.py:95-142`) carries `source: str = "user"  # "user", "ai", "auto", "gate"`, `agent_id`, `confidence` — a **producer label, not a route**. `grep -rIn 'execution_path' python/synapse/memory/` → **zero hits**, while CLAUDE.md §1.3 defines `execution_path` (`"mcp"`/`"live"`) as the path qualifier everywhere else in the system. **The memory substrate is the one persistence surface that drops it. VIOLATION, MUST-level.**

This is not a lane limitation — **it is the violation itself.** Three lanes independently hit this wall: S3a unknowns 1 and 2, S4 unknown 1. None named the clause requiring the wall not to be there. **Zero of five lanes mention route recording.** That is the packet's largest section-level blind spot.

It also bites the forensics: `source: 'ai' → 'auto'` is doing double duty as a de-facto route tell. A four-value producer enum is not a route field.

**V5-2 — Asymmetric serialization.**
`SynapseMemory.add` carries `@_on_memory_main` (`store.py:1319`), routing through `_read_on_main` (`store.py:1076-1090`). `scene_memory.py:729` calls `syn.store.add` **directly**, bypassing the decorator. Two writes of the same content — one marshalled, one not. `handlers_memory.py:237-253` `_handle_memory_write` is not wrapped in `_memory_on_main`, and `integrity_envelope.py:89-93` documents `add_memory` as a *"PURE off-main-thread write by design (zero `run_on_main` in their handlers — verified: … `tracker.handle_memory_add`)."* Scored primarily under §6; recorded here because §5 is where "one owner, serialized route" is stated as law.

**Recommendation risk:** any repair executed on the live scene inherits V5-1 — **there is currently nowhere to record which route performed it.** Landing a scene repair before the route field exists manufactures a second unattributable mutation of exactly the kind this packet is reconstructing.

### §6 — Architectural responsibilities

**V6-1 — Competing writers to persistent state. Stated as prohibited, present by construction.**
> *"Model work, UI interaction, and native execution must not introduce competing writers to scene or persistent state."*
> *"| Existing persistence owner | Retains task state, proposals, revisions, results, artist selections, and execution provenance **without a competing registry**. |"*

`moneta_store.py:357` + the live `moneta` gate + a census that cannot see the handle it creates. Full evidence in §4d. **Clearest MUST-NOT violation in the packet. VIOLATION.**

**V6-2 — The twin-write is a second construction authority.**
> *"Panel code observes and presents state; it must not become a second construction authority."*

Mechanism in §4b. The clause is written about panel code; the mechanism is identical. **VIOLATION by principle, adjacent by letter** — recording the gap rather than overstating it.

**V6-3 — `{"written": True}` is an unmeasured claim where §6 requires `UNKNOWN`.**
> *"Unsupported or unmeasured behavior remains `UNAVAILABLE` or `UNKNOWN`, as appropriate."*

`handlers_memory.py:252-253`, §3b. §6 does not merely permit `UNKNOWN` here — it requires it. **VIOLATION.**

**Does the applied repair have a §6 record? No. Zero of five required connections.**
> *"Each completed or interrupted operation MUST have a record connecting the engagement and proposal to its actual changes, execution route, verification results, and recovery status."*

| Required connection | Present? | Evidence |
|---|---|---|
| engagement + proposal | No | `engagement` = 0 hits in `python/`; no proposal artifact |
| actual changes | No | only `memory.jsonl.pre-repair-1789674797` — raw bytes, no diff, no annotation |
| execution route | No | no route field exists anywhere (V5-1) |
| verification results | No | no receipt in `harness/memory/bus/` (newest 2026-08-22) or `harness/memory/notes/` (newest 2026-08-22) |
| recovery status | No | `decisions.md` in the live store dir is an empty template |

**The packet proves its own gap in arithmetic.** The brief asserted 846/846. Lane S3a measured 846 lines / 841 ids. Lane S3b refused to call the repair clean over exactly this. Lane S2 measured 847/847. The compositor measures **882/882** today. Four numbers across four hours. **The count dispute is the §6 violation rendered as arithmetic** — nobody can settle it because the mandated record was never written. (See §7 **C1** for the one number that is settled.)

**Does the quarantine have a §6 record? No.** `store.py:316-327`: `_quarantine_store` builds `f"{name}.{reason}-{int(time.time())}"`, calls `shutil.copy2`, logs `logger.error("Quarantined a copy of the store for recovery: %s", aside)`, returns a path. **The `degraded_reason` — computed twelve lines earlier at `:396-399` — is never written beside the copy.** Twelve files record *that* something happened, twelve times. Not what changed, not the route, not verification, not recovery status. Its one reader (`doctor.py:322-324`) counts them and reports `status: "ok"`.

The docstring's instinct is right and worth preserving — *"We copy, never move/delete — the unreadable ciphertext is exactly the recoverable asset."* **Preserving the asset is not recording the operation.** §6 requires both.

**Recommendation risk — the sharpest finding in this audit.**
**S4's proposed manifest, implemented as a new sidecar file, would itself violate §6.** §5c argues correctly that the manifest is mandatory. What it does not check is **where §6 permits it to live.** A fresh `quarantine_manifest.json` beside `memory.jsonl` is, by the letter of the "without a competing registry" row, **a third registry in a directory that already has two writers for one file** (V6-1). The requirement is that the **existing persistence owner** retain it. No lane raised this. It is the one place where the packet's best-engineered recommendation and the recorded intent collide.

**§6 requirement no lane addressed:**
> *"| Outcome verification | Checks actual graph, geometry, material, render, or other domain results against the requested conditions. |"*

Nobody stated the requested condition ("keep the richer record per id") in a form a check could run against. Measuring the store as clean **now** is a post-hoc read of the artifact, not a check of the result against its condition.

### §7 — Artist experience and attention

**V7-1 — None of the four questions is answerable about the memory substrate.**
> *"The ordinary interface should answer four questions: **What help is engaged? What is it doing? What can it change? How do I take control back?**"*

§3's table. The artist asking *"what can it change?"* got `writable: true` for two days while every write was refused. **VIOLATION.** §3a explains why every light stayed green — and note the corrected form: the green light would stay green even if the *serving* store were the one refusing.

**V7-2 — A two-day failure produced no notification.**
> *"Notifications should mark meaningful completion, failure, or a decision that needs the artist."*

Eleven degraded loads, 253 WARNING lines, 13 non-pytest `DEGRADED LOAD` ERRORs, **zero notifications**. The only non-log surface is a counter rendering inside an `"ok"`. Whether `degraded_quarantine_count` reaches a human at all: producer found (`doctor.py:323`), threshold doc found, **no consumer that displays it in the panel — UNKNOWN. VIOLATION.**

**V7-3 — Prior work disappeared, with no baseline comparison to catch it.**
> *"Artist edits are authoritative. Follow-up work MUST compare the current scene to the recorded baseline and preserve changes outside the agreed boundary."*

The missing-comparison half is **VIOLATION** and independent of §2's inversion: `grep` for `recorded baseline` / `baseline_hash` / `stale` across `cognitive/` and `server/` returns **zero hits**. The disappearance half now attaches to the **chain root** rather than the orphan (§2b), is **UNKNOWN** pending one re-measure, and its authorship is asserted by nobody.

**V7-4 — WEAKENED. One of its two halves is killed.**
> *"Generated results should expose useful controls, understandable organization, and provenance without requiring the artist to maintain an AI conversation to keep editing them."*

- *"the display flag sits on the orphan / the viewport shows the wrong thing"* — **KILLED** by the compositor's measurement (§2a). The display flag is on the chain root.
- Both `materiallibrary` nodes unbound, no `assignmaterial` in the chain — **SURVIVES** (§2c).
- Four contradictory recipe definitions, none retracted — **SURVIVES** (§2d). Provenance that offers four answers is not provenance.

**VIOLATION stands on the surviving two halves, at reduced weight.**

**§7 requirement no lane addressed:** the four questions were never asked as a set — S1-4 answered the narrower *"is there a degraded field."* And S1's own closing unknown is the honest boundary: whether the **SYNAPSE panel** surfaces store health was never determined. **§7 is written about the ordinary interface, which is the panel. The packet has no evidence about the surface §7 actually governs.** Every §7 verdict above rests on the tool layer and must be read as such.

### §9 — Qualification and success criteria

**The flagged question — is a store that fails closed silently conformant? Split verdict. Do not let a fix confuse the two halves.**

> *"| Missing capability or failed action | The actual limit, partial result, and recovery options are visible; a fallback cannot bypass policy. |"*

**The fail-closed half CONFORMS, and it is the best-behaved code in this packet.** `_require_writable_load` (`store.py:450-460`) refuses on `_degraded_load` and guards all six mutators. The comment at `store.py:395-396` states the principle exactly: *"Plaintext corruption and identity conflicts are as recoverable as a wrong encryption key. **A partial read cannot authorize a rewrite.**"* The raise text already contains all three §9 elements. **And no fallback bypassed policy** — the moneta primary stayed up and the JSONL net refused, which is the fallback *respecting* policy.

**The silent half VIOLATES**, at the surfaces: the outer `warning`-then-`return memory.id` (`moneta_store.py:785`/`:753`), the literal `{"written": True}` (`handlers_memory.py:253`), and the tool layer's total absence of a health field. *(The DEBUG swallow at `scene_memory.py:740` is **removed from this list** — K3: it never fired.)*

**§9, second violation:**
> *"| Resume or recovery | Fresh scene validation precedes a deliberate resumption; restart/reconnect cannot silently reengage or duplicate prior work. |"*

Eleven reconnections, eleven silent re-attempts, twelve byte-identical quarantine copies of one frozen file (§4f). *"Cannot … duplicate prior work"* is met at the semantic level and broken at the artifact level. **VIOLATION** — and it is the clause that should frame the retention decision.

**§9 recommendation risk:** shipping content-addressing alone leaves the row unmet and drops the doctor's alarm from critical to warn on identical reality (§5c). **Conditionally non-conformant: conformant bundled with visibility, non-conformant alone.**

**§9 requirements no lane addressed:**

1. **The evidence standard for the repair.** *"Behavioral tests need observed execution evidence on the supported Houdini build. Mock or stock-Python tests can verify control logic, but cannot establish native scene correctness."* The repair was performed and verified by **stock Python 3.14.2 against files on disk**, while Houdini 22.0.400 runs 3.13 and holds PID 54668. **Under this clause the repair's verification is UNKNOWN on the supported build, not green.**
2. **The failing-test gap.** *"Include failed and abandoned attempts."* §5a: `conflicting duplicate` has zero hits in `tests/`; `_quarantine_store` has zero hits by name outside `store.py`; the repeat-quarantine assertion passes with 1 copy or 11. **Nothing in the suite would notice a recurrence.**
3. **Creative comparison.** *"| Creative comparison | Candidate identity and viewing conditions remain consistent; the chosen result can be reproduced in the final preparation. |"* §2d's four contradictory live definitions are four candidates with no stable identity and no retraction. **There is currently no way to say which candidate a scene resume would be resuming.**

### §6 conformance summary

| § | Violations | Recommendation risk | Unaddressed by every lane |
|---|---|---|---|
| **3** | V3-1 `Unavailable` never reported · V3-2 eleven silent resumptions · V3-3 repair has no validated authorization | eviction destroys evidence; batch-repair is model-selected scene identity; scene resume is ungated | **the scene resume gate does not exist** (0 hits); Starting-state never captured |
| **5** | V5-1 **route not recorded — field absent entirely** · V5-2 asymmetric serialization | a scene repair lands as another unattributable mutation | **the entire section** — 0 of 5 lanes mention it, while 3 lanes' unknowns are caused by its absence |
| **6** | V6-1 **competing writers, census-invisible** · V6-2 twin-write second authority · V6-3 `written: True` where `UNKNOWN` is required | **a sidecar manifest is itself "a competing registry"** | Outcome-verification row; nothing checked the repair against its requested condition |
| **7** | V7-1 four questions unanswerable · V7-2 no notification in 2 days · V7-3 no baseline machinery · V7-4 **weakened** (display-flag half killed) | health field must stay quiet while the failure notifies | **no evidence about the panel** — the surface §7 governs |
| **9** | **Refusal CONFORMS; silence VIOLATES** · silent reconnect duplication | content-addressing alone leaves the row unmet and drops the alarm critical→warn | repair verified on stock 3.14 not the supported build; **zero tests**; creative-comparison row |

**Highest-conformance-value action if one thing is done first:** the visibility half (§9 / §3-Unavailable / §7). **The message §9 demands already exists verbatim at `store.py:455-460`; three handlers discard it.** Cheapest conformance gain in the packet, touches zero bytes of evidence.

**Do not act on:** any quarantine eviction, any batch repair of the other five stores, any scene resumption. §3 reserves all three to the artist; the second and third have no validation gate to pass through even if authorized.

---

## 7. What the crucible killed or corrected

**Four kills, eight corrections, six findings the lanes never produced. One further kill added by the compositor.**

### Killed

| # | Claim | Why it died |
|---|---|---|
| **K1** | S3b-F2: *"a full rewrite ran in that 36-second window and emitted 5 pre-existing ids twice"* | **`Loaded N` is a distinct-id count, not a line count** (`store.py:363` dict-keyed load, `:409` logs `len(self._memories)`). The arithmetic `839+2+5=846` is void. `Loaded 839` appears twice — two clean loads of a file already at 844 lines/839 ids, the 5 dups silently deduped by the pre-`ef690e50` loader. The duplicates were **appended** in 09-01..09-06 when line 2 was EOF. Disproof: current lines 859–862 are the newest appends and carry 09-13/09-14 `created_at`. |
| **K2** | S3b's *"strongest lead"* — two mirror writers, `WriteThroughStore.add` doing *"a full rewrite on every add"* | **`WriteThroughStore` has zero production construction sites** — only `tests/test_w3_migrate.py:287,293,316,336`. Dead code. One JSONL writer exists: `_dual_write_jsonl`, append-only. |
| **K3** | S4-4: *"That is the mechanism of the two-day silence"* / *"nothing … or any non-debug log says the memory was dropped"* | `grep -c "JSONL dual-write failed"` = **253 WARNING lines**, each naming the reason and the offending line number. The DEBUG swallow S4 called *"worse"* fired **0** times. The outage was loud at WARNING and ERROR; it was invisible only in the tool/UI surface. **S4-6's remediation ranking (a) is built on a mechanism that did not fire.** |
| **K4** | S1-1 / S1-3: `GEO_sphere` is the orphan / empty / a regression | **Inverted.** `GEO_sphere` (sopcreate) is the **chain root**, `outputs:['/stage/MTL_hero']`. `GEO_sphere1` (sopimport) is the orphan, `in=[] out=[]`. Measured twice by the crucible, a third time by the compositor 2026-09-17 ~16:30. **The packet as S1 wrote it would have a human sever the renderable chain.** |
| **K5** *(compositor)* | S1-1: *"the viewport shows the orphan, not the renderable chain"* | `display_flag:true` sits on `GEO_sphere` — the chain root. The flag is on the right node. Removes one half of INTENT V7-4. |

### Corrected

| # | Was | Now |
|---|---|---|
| **C1** | Brief's ESTABLISHED FACT: *"Store now clean (846 records/846 ids)"* | **841.** Pre-repair measured 846 lines / 841 ids / 5 conflicts. Repair is otherwise clean: **0 ids lost**, all 5 pairs kept the rich twin, byte-identical to the pre-repair rich record. |
| **C2** | S2-F6's epoch list included `1789571854` and omitted `1789674135` | `1789571854` is the **Alien Saucer** suffix, not the untitled store's. Corrected span **17:12:11 → 15:42:15**. Re-verified this session by `ls -la`. Totals unchanged (12 files, 1 sha, 16,733,688 bytes). |
| **C3** | S1-5: *"write_plane's check is a DIRECTORY-writability probe, not a MemoryStore state read"* | **Worse than stated.** `write_plane.py:355-428` *does* evaluate the store — it never reads `_degraded_load`, and `count()` (`store.py:601`) has no `_require_writable_load` guard. **A serving store refusing every write would still report `write_plane=ok`.** |
| **C4** | S1: `network_explain path=/stage` *"timed out — Houdini may be busy"* | **Deterministic defect:** returns `Type is not JSON serializable: Ramp`. Same error blocks `inspect_node /stage/karma_settings`. Not a retry candidate. |
| **C5** | S1-1: *"all 9 nodes error_state 'clean'"* | `GEO_sphere1` and `MTL_hero` each carry 1 error: `IndexError: tuple index out of range (/stage/GEO_sphere/ineditlayerblock)`. Re-confirmed by the compositor. |
| **C6** | S2 summary: *"20 memory.jsonl stores exist on this machine"* | **7,605 base `memory.jsonl` (8,966 incl. suffixed) on C:+D:.** Non-test stores missed: `C:\tmp\untitled.hip\…` (41 ids, clean), `C:\Users\User\OneDrive\…\SYNAPSE_Refactor\…` (10 ids, clean, **cloud-synced** — a store class the packet never contemplated), 11 under `C:\synapse-build\`, 4 unlisted W1 backups. S2's own unknown disclosed the root gap; the summary sentence was the overclaim. |
| **C7** | S2-F2: SYNAPSE_DEMO's conflicts differ *"ONLY in created_at/updated_at"* | They also differ in **`hip_file`**. |
| **C8** | S3a-1 quoted `scene_memory.py:729-734` as an unconditional deposit | Omits the guard at `:728`: `if hasattr(syn.store,'add') and not isinstance(syn.store, MemoryStore)`. Mechanism unaffected (moneta is live); the deposit is **conditional**. |

### Verified and standing

S2-F1 per-store counts (Alien 58/19/39/1; DEMO 13/8/5/3; MPM 2/2; repo `untitled.hip` 39/18/21/15; both W1 backups 15 conflict ids) — exact. S2-F3 Shape-A exclusivity — 0 Shape A in all five other stores including both backups of the same lineage. S1-2 material binding. S1-4 health-surface outputs. S1-1 chain **order** and `OUTPUT ← karma_settings`. S3a-2 id formula. S3a-3 pair shapes and dates. S3a-4 detector provenance (`ef690e50`, single commit, 2026-09-15 15:33:27). S3a-5 the third store authority and the census blind spot. S3b-F1 `save()` atomicity. S4-5 literal `written: True`. Quarantine copies byte-identical, Alien Saucer's live file == its quarantine copy.

### Findings no lane produced

| # | Finding |
|---|---|
| **N1 (blocking)** | **The repaired JSONL is 253 records behind Moneta.** Independently reproduced by the compositor: `moneta_ids 1131 jsonl_ids 882 moneta_only 253 jsonl_only 4`, and **all 253 have `created_at` inside `2026-09-15T21:14:24Z → 2026-09-17T19:53:56Z`** — the outage window, exactly. 253 records ↔ 253 WARNING lines. Nothing was *lost* (Moneta is the serving store and kept them), but **the safety net has a 48-hour hole and nothing reconciles it.** Every lane says "repaired / clean / writing again"; none quantifies this. |
| **N2** | **Divergence is bidirectional.** 4 ids exist in the JSONL and **not** in Moneta, all dated 2026-09-06: `mem_3f27b6d52222` (14:00:47Z), **`mem_e2e9749cb3c3` (14:00:50Z, a `decision` record)**, `mem_1ed48dbc06ea` (14:03:51Z), `mem_cb73dd2c8061` (14:06:35Z). **Neither store is a superset. Any "rebuild one from the other" is lossy in both directions.** |
| **N3** | Live `doctor` → `write_plane_store` reports `backend_health {"status":"SUCCESS","verdict":"SUCCESS"}` over exactly that substrate. |
| **N4** | **The timestamp key is lossy within a second, not merely non-deduping.** Alien Saucer logged two `DEGRADED LOAD` errors 100 ms apart (`11:17:34,488` / `,588`) and produced **one** quarantine file — same-second epoch, second copy overwrote the first. Runtime corroboration of the double-handle claim. |
| **N5** | **Shape A is caused by the Shape B fix.** `models.py:145` added `created_at` to the hash so *"the same content logged at different times gets distinct ids"* — at **second** granularity, which is what makes two same-second writes collide. |
| **N6** | **The lossy deposit is still firing post-repair.** Pre-count `memory.jsonl` line 845: `content='' source=auto tags=[] type=note` at `2026-09-17T19:54:14Z`, one minute after the repair — `handlers_memory.py:249-252` wraps a non-str payload and `entry.get("content","")` yields `''`. Junk record, not a twin, but the same path. |

### Weakest remaining link

**N1, amplified by the packet's own framing.** *"ALREADY REPAIRED … clean and writing"* is the sentence most likely to make a human close an incident that still has a **253-record unreconciled hole**, a **live generator defect still firing** (N6), and **five other stores refusing writes**.

### Reproduction scripts (read-only, disposable)

`C:\Users\User\AppData\Local\Temp\claude\C--Users-User-SYNAPSE\38161343-b2fd-4984-9b7f-98f65db233c8\scratchpad\` — crucible: `probe1.py … probe5.py`, `scan.py`, `shapes.py`, `exact.py`, `ws7.py`, `ws10.py`, `ws11.py`, `ws12.py`. Compositor: `packet_verify.py` (store recount + window), `n1.py` / `n1b.py` / `n1c.py` (Moneta ↔ JSONL reconciliation; **`n1c.py` is the working one** — the snapshot's `rows[].payload` is a **JSON string**, and its ids live inside it, not at `entity_id`, which is a UUID).

---

## 8. Known unknowns

Each row: what is not known, and the single cheapest thing that closes it.

### Blocking

| # | Unknown | What closes it |
|---|---|---|
| **U1** | **Who reconciles the 253 Moneta-only records into the JSONL, and whether they should be.** N1/N2 establish the divergence is real and bidirectional; nobody has decided the disposition. Under INTENT §3 this is the artist's call, not a model's. | A human ruling on whether the JSONL net is a mirror or a log. Then a reconciliation with a recorded outcome (§6). |
| **U2** | **Whether the chain root `/stage/GEO_sphere` is actually empty.** The S1 interior probe was path-anchored and therefore describes the **renderable chain's source**, not the orphan (§2b). Not re-measured. | One call: `houdini_network_explain root_path=/stage/GEO_sphere depth=3`. |
| **U3** | **Whether the generator defect is still producing twins**, as opposed to the junk record N6 caught. Shape A has **n=1 store**; one instance settles neither "systematic" nor "one-off". | Instrument or watch `tracker.handle_memory_add` for one session and diff the resulting lines. Requires a write — human-gated. |

### Scene

| # | Unknown | What closes it |
|---|---|---|
| **U4** | **When `/stage` was rewired.** No scene-mutation audit trail is available read-only, so K4 is *"the packet is wrong **or** stale,"* not *"S1 misread."* An `Executed: execute_python` at 16:03 local sits in the window. | A mutation audit trail — which INTENT §5's route field and §6's record clause would have provided and do not (V5-1, V6-1). |
| **U5** | **Whether `GEO_sphere`'s contents are LOCKED.** No lock/HDA flag appears in any tool output. `network_explain` traversed all 10 internal nodes with full parameter visibility, which argues against a black box. Reported as unknown, not refuted. | Read `node.isLockedHDA()` / `matchesCurrentDefinition()` via a read-only `execute_python` — but that path is **CRITICAL-gated on `/mcp` and ungated on `/synapse`**; treat accordingly. |
| **U6** | **Whether `MTL_hero` / `MTL_matlib` child shader VOPs author valid MtlX surfaces.** Binding was the question answered; shader correctness was not inspected. At measurement time `MTL_hero` authors no prims at all because it errors. | `synapse_inspect_node` on each library's children. |
| **U7** | **Which of the four contradictory recipes a scene resume would be resuming.** None retracts its predecessor; the live scene is a hybrid. | A retraction/supersession mechanism in recall — does not exist. INTENT §9 creative-comparison row. |

### Store / substrate

| # | Unknown | What closes it |
|---|---|---|
| **U8** | **Whether any process currently holds the 4 live degraded stores open.** "Refusing writes right now" is proven for file state, inferred for runtime. Houdini PID 54668 is running; which store path it has mounted is unverified from disk alone. | `synapse_health` / `memory_handle_census()` on the live bridge — **but the census cannot see `_jsonl_net`** (V6-1), so it will under-report by construction. |
| **U9** | **Root coverage.** Exhaustively walked: `houdini_temp`, `D:\HOUDINI_PROJECTS_2025`, `D:\HOUDINI_PROJECTS_2026`, `C:\Users\User\.synapse`, `C:\Users\User\SYNAPSE`. Cheaply swept: `D:\Houdini_Temp`, `D:\HOUDINI_2025_PROJECTS`, `D:\Houdini_Backup`, `F:\houdini_temp`, `E:\`, `G:\Comfy-Cozy`, Documents, Desktop. **Not walked:** remainder of C:, D:, G:, and E:/F:/H: if present. The crucible's full-drive non-ephemeral enumeration **did not finish**. | A completed enumeration. Note C6 already found two non-test stores outside the census, one of them **cloud-synced** — a store class nothing in this packet contemplates. |
| **U10** | **The 4 unlisted W1 backups and the 11 `C:\synapse-build\` stores were never scored.** | Re-run the S2 replication of `store.py:355-359` over those 15 paths. |
| **U11** | **Per-store `key.fingerprint` was never audited machine-wide.** The S2 replication covers the unreadable-records branch faithfully but reads every store with the one global `CryptoEngine`, so a **wrong-key degradation** (`store.py:396-399 _key_fingerprint_mismatch`, the second `degraded_reason` branch) could exist in a store scored clean. | Compare each store's `key.fingerprint` sidecar against the active key before scoring. |
| **U12** | **Why 3 of the 4 live degraded stores have no quarantine sibling** (SYNAPSE_DEMO, MPM, repo `untitled.hip`) while Alien Saucer has exactly one. Either `_quarantine_store` postdates their last load, or they have not been opened since the feature landed. | Load-time telemetry, which does not exist per store. |
| **U13** | **The exact legacy id formula that produced `mem_2f1bc0bbb623`.** Three reconstructions miss: `content:type` → `90d464586375`, `content:created_at:type` → `e9fa591c740a`, `content` alone → `a5cadd52a3d1`. Confirming Shape B is a fixed historical defect rather than a still-live one needs `models.py` history. | `git log -p -- python/synapse/memory/models.py` filtered on `_generate_id`. |
| **U14** | **H1 (flush/save interleave) is unruled.** Predicts loss and EOF duplication, not mid-file duplication — so it does not explain the observed evidence, but it is not ruled out as a separate defect. | The settling probe in §4g. Requires writes — human-gated. |
| **U15** | **Whether the `.w1_incoming_moneta/` staging directory beside the untitled store ever wrote into `memory.jsonl`.** It contains one nested empty directory (`C_Users_User_Synapse_HOUDINI_TEMP_DIR_untitled_synapse`, mtime 2026-08-20 18:29) and no files. No code path referencing that directory name was found, but no exhaustive grep was run. | `grep -rIn 'w1_incoming_moneta' python/ scripts/ harness/`. |
| **U16** | **One record's `created_at` falls strictly inside the outage window** (compositor: `jsonl records inside outage window: 1`), against N1's *"zero records between"*. Most likely the first post-repair write at ~`19:53:5x`Z landing on the boundary. **Unreconciled.** | Print that record's id and `created_at` from `packet_verify.py`. One line. |

### Route / thread / transport — all caused by the same missing field

| # | Unknown | What closes it |
|---|---|---|
| **U17** | **Which OS thread each twin write ran on.** `SynapseMemory.add` is decorated `@_on_memory_main`; the `scene_memory` deposit is not. No per-record provenance field records the executing thread; no runtime trace from 09-01/09-06 exists. | A thread field on the record. Does not exist. |
| **U18** | **Whether the rich twins arrived over `/synapse` WS or `/mcp`.** Both reach `tracker.handle_memory_add`; nothing persisted carries a transport or `execution_path` field. | **This is INTENT §5's `execution_path` (V5-1). It is not a lane limitation — it is the violation.** Closing it means adding the field. |
| **U19** | **Which backend was live in the `untitled` session** (moneta-primary vs jsonl-primary) — decides which swallow fired. K3 answers it empirically for this incident (253 outer, 0 inner), but not structurally. | Same field as U18. |
| **U20** | **Whether `write_plane` would correctly flip to `degraded` if the SERVING backend failed.** C3 makes this worse than S1 thought: `count()` succeeds on a degraded store, so it likely would **not**. Proving it requires inducing a write failure — a mutation. | A test that injects a degraded serving store and asserts `write_plane` reports it. Does not exist (§5a). |

### Visibility / process

| # | Unknown | What closes it |
|---|---|---|
| **U21** | **Whether the SYNAPSE panel surfaces store health.** No read-only tool in the permitted set exposes the panel's rendered state. **§7 is written about the panel; the packet has no evidence about it.** | Read the panel's memory-status widget source, or an offscreen hython panel render. |
| **U22** | **Whether `degraded_quarantine_count` reaches a human at all.** Producer found (`doctor.py:323`), threshold doc found (`docs/moneta-production-harness-architecture.md:610`), **no display consumer found**. | `grep -rIn 'degraded_quarantine_count' panel/ python/synapse/panel/`. |
| **U23** | **Effective log level of `scene_memory`'s logger inside the Houdini host.** Moot for this incident (0 hits), but unconfirmed. | Read the host logging config. |
| **U24** | **Whether the 15:04 / 15:16 / 15:57 non-Houdini processes binding port 9999 ever raced the live bridge.** | Correlate their bind attempts against the bridge's uptime in `synapse.log`. |
| **U25** | **Retention-cap semantics are unspecified.** Under content addressing, capping by count evicts the **oldest distinct state** — the most recoverable one. | INTENT §3: **the human decides.** Not a model call. |
| **U26** | **No receipt exists for any of this.** No file written to `harness/memory/bus/` (newest 2026-08-22) or `harness/memory/notes/` (newest 2026-08-22). Every lane and the crucible were read-only by construction. **This packet is the only artifact.** | Save this packet, and write the §6 record the repair still lacks. |

---

**Packet ends.** Every number above carries the command or `path:line` that produced it. Anything not measured is marked UNKNOWN rather than smoothed.
