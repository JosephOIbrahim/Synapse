# Finding — the two substrates disagree about what a colliding id means

**Date:** 2026-09-18 · **HEAD:** `ca1e9e01` (master) · **VERSION:** 5.75.1
**Status:** open · paper deliverable · **analysis only — no code changed, neither disposition touched**
**Upstream:** `harness/notes/findings/id-hash-collision.md` (the mechanism that produces the collisions this document dispositions)

---

## Summary

The brief asks about **two** dispositions. There are **four**, and only three of them run automatically.

| # | Who | When it runs | On a colliding id | Counted? |
|---|---|---|---|---|
| 1 | **Primary** — `MonetaBackedStore.add` | every write | **keeps both.** No id check exists. | no |
| 2 | **USD cortex** — `_write_cortex` | every write | **incoming wins**, prior prim overwritten | no |
| 3 | **Mirror** — `MemoryStore.add` | every write | **incoming wins**, routed to `update()` | yes |
| 4 | **Offline repair** — `primary_repair.richness` | human runs it | **richer wins** | n/a (reports) |

The richness ordering the brief attributes to the primary is **not a runtime disposition**. It lives in a dry-run-by-default CLI tool a human invokes after the fact. The primary at runtime has **no opinion at all** — which is the actual asymmetry, and a sharper one than "they disagree".

Three further things this document establishes, each new:

- **`_metadata_richness` (`store.py:158`) has zero callers.** Its own docstring names `MemoryStore.add` as its consumer. That consumer no longer uses it. Dead code with a stale contract, and the production log captured the exact hour it died.
- **`overwrote_prior` has never been non-zero from production traffic on this seat.** Every one of the 26 collision downgrades in the live log is a pytest fixture id. But a zero is **process-scoped** — it cannot mean "never happened".
- **The guard's central safety argument is namespace-scoped and it does not say so.** "A collision is always metadata-only" is true for `mem_` ids and false for `loop_` ids.

---

## 1. What each path does

### 1.1 Primary — `MonetaBackedStore.add` · keeps both · `moneta_store.py:720`

```
python/synapse/memory/moneta_store.py:720   def add(self, memory, *, require_durable=False) -> str
python/synapse/memory/moneta_store.py:729       self._handle.deposit(payload, embedding, protected_floor=floor)
```

**Trigger condition for a collision-specific branch: there is none.** `add()` reads `memory.id` only to build `payload = memory.to_json()`. It never looks the id up. Both records land, each receiving its own Moneta `entity_id`. Two distinct events, one SYNAPSE identity, zero signal.

The checked sibling one method up **does** look, and shows what an id check costs here:

```
python/synapse/memory/moneta_store.py:690   def add_durable_if_absent(self, memory) -> bool
python/synapse/memory/moneta_store.py:699       matches = [m for m in self._iter_memories(strict=True) if m.id == memory.id]
python/synapse/memory/moneta_store.py:701           if len(matches) != 1 or matches[0].to_json() != memory.to_json():
python/synapse/memory/moneta_store.py:702               raise ValueError("Memory identity already contains different or duplicate data")
```

So the primary already contains an id-checking path. It **raises** rather than choosing a survivor, and the automatic writers do not call it — they call bare `add()` (`require_durable` defaults `False` at `store.py:1585`, per the hazard ticket §5(b)).

**The primary has no `health()`.** Verified:

```
$ grep -c 'def health' python/synapse/memory/moneta_store.py
0
$ grep -c 'overwrote_prior\|rejected_writes' python/synapse/memory/moneta_store.py
0
```

This matters for §3.

### 1.2 USD cortex — incoming wins, silently · `moneta_store.py:965`

```
python/synapse/memory/moneta_store.py:965   def _write_cortex(self, memory, payload) -> None
python/synapse/memory/moneta_store.py:973       cortex.write(memory.memory_type.value, memory.id, payload)
```

**Trigger condition:** every add, unconditionally. The prim is keyed by `(kind, id)`, so a second write to the same id **overwrites the first prim**. Same last-write-wins disposition as the mirror — but with no counter, no log line, and no health surface. The `except Exception` at `:974` makes it best-effort by design.

This is the third disposition, and it is the quietest one.

### 1.3 Mirror — incoming wins, routed and counted · `store.py:697`

```
python/synapse/memory/store.py:697   def add(self, memory: Memory) -> str
python/synapse/memory/store.py:732       existing = self._memories.get(memory.id)
python/synapse/memory/store.py:742       diverged = existing.to_json() != memory.to_json()
python/synapse/memory/store.py:746       return memory.id          # byte-identical re-add -> no-op
python/synapse/memory/store.py:779       self._overwrote_prior += 1
python/synapse/memory/store.py:788       self.update(memory)
```

Three exact branches, in order:

| Condition | Behaviour |
|---|---|
| `self._memories.get(memory.id) is None` | original fast path, buffered append (`:797-801`) |
| id present **and** `existing.to_json() == memory.to_json()` | no-op, returns the id (`:746`) |
| id present **and** `to_json()` differs | `_overwrote_prior += 1` (`:779`), WARNING (`:780`), `self.update(memory)` (`:788`) |

The comparison is `to_json()`, which is `sort_keys=True` — the same canonical form `_load` computes per line — so **"differs here" is exactly "conflicts there"**, as the docstring claims at `:739-741`.

`update()` then makes the incoming record authoritative:

```
python/synapse/memory/store.py:811   def update(self, memory: Memory)
python/synapse/memory/store.py:816       memory.updated_at = time.strftime(...)
python/synapse/memory/store.py:817       self._memories[memory.id] = memory
python/synapse/memory/store.py:820       self._needs_rewrite = True
```

`_needs_rewrite` forces a full JSONL rewrite on the next flush, because append-only cannot express a mutation. **That is the whole point of the routing** — it is what prevents the second differing line from ever reaching disk, and therefore what prevents `store.py:410`'s `conflicting duplicate memory identity` on the next load, which is the 2026-09-15 outage shape.

**The divergent case deliberately does not raise** (`:722-728` docstring). Its production caller is `moneta_store._dual_write_jsonl` (`:977-994`), whose `except Exception` at `:993` exists so the safety net can never break its caller. A raise would be swallowed — trading a loud-but-late outage for a silent permanent divergence.

**The pin:** `tests/test_store_incident_2026_09_17.py:262 test_reload_after_same_id_rewrite_keeps_the_latest_content`, asserting at `:284` `survivor.content == "the second, differing write"`.

```
$ python -m pytest tests/test_store_incident_2026_09_17.py -q
10 passed, 2 warnings in 0.55s
```

### 1.4 Offline repair — richer wins · `primary_repair.py:173`

```
python/synapse/memory/primary_repair.py:173   def richness(payload_obj) -> Tuple[int, int, int, int, int]
python/synapse/memory/primary_repair.py:188       len(payload_obj.get("tags") or []),
python/synapse/memory/primary_repair.py:189       1 if (payload_obj.get("hip_file") or "") else 0,
python/synapse/memory/primary_repair.py:190       0 if (payload_obj.get("source") or "") == "auto" else 1,
python/synapse/memory/primary_repair.py:191       1 if payload_obj.get("frame") is not None else 0,
python/synapse/memory/primary_repair.py:192       1 if (payload_obj.get("hip_version") or 0) else 0,
```

**Trigger condition:** `len(group) > 1` for an id, inside `scan_snapshot` (`:409-413`). Selection is `max(group, key=lambda g: (richness(g[2]), -g[0]))` (`:413`) — richest first, **earlier row on a tie**.

Receipt for the run the brief cites, `harness/notes/store-incident-2026-09-17/OPERATIONS_LOG.md:34-36`:

```
| Before | 1136 rows · 1131 distinct ids · 0 unreadable |
| After  | **1131 rows · 1131 distinct ids · 0 unreadable** |
```

Three properties separate this from the runtime dispositions, and all three are deliberate (`primary_repair.py:68-88`): **dry run is the default**, it **refuses to run while Houdini is live**, and it **cross-checks its intended survivor against the record the mirror kept and refuses on disagreement**.

That last one is the load-bearing part. The module docstring at `:57-65` states why:

> If this repair kept a different copy, the two stores would then disagree on the content of the same id, and `_dual_write_jsonl(only_if_missing=True)` re-appends whenever `existing.to_json() != memory.to_json()` — which is precisely the poisoning case. **Disagreement between the stores is itself a re-poisoning mechanism.**

Confirmed live at `moneta_store.py:985-987`:

```python
existing = get(memory.id) if only_if_missing and callable(get) else None
if existing is None or existing.to_json() != memory.to_json():
    net.add(memory)
```

So a standing content disagreement between primary and mirror on one id is not inert. It is a **loop**: every `add_durable_if_absent` on that id re-fires `net.add`, which re-fires the `update()` downgrade, which re-increments `overwrote_prior`.

### 1.5 The dead ordering — `_metadata_richness` · `store.py:158`

```
$ grep -rn "_metadata_richness" --include=*.py .
./python/synapse/memory/store.py:158:def _metadata_richness(memory) -> tuple:
```

**One hit. The definition. No callers.**

Its docstring (`:159-178`) says:

> Used by :meth:`MemoryStore.add` to decide which of two colliding records survives. […] The ordering is the one the manual repair of the 2026-09-15 corruption used, kept identical on purpose **so the automatic path and the recovery tool can never disagree** about which twin is authoritative.

`MemoryStore.add` does not call it. The automatic path and the recovery tool **do** disagree — the invariant this function exists to hold is not held by anything.

**The production log dates the death to a single 14-minute window on 2026-09-17.** Two different messages, from two different implementations of the same guard:

```
$ grep "add() for existing id" ~/.synapse/logs/synapse.log | grep -v "routed to update" | head -1
2026-09-17 16:52:19,744 [synapse.memory] WARNING: Memory write refused or downgraded
(1 so far in this store): add() for existing id 'mem_incident' carries different content
but NO MORE metadata than the stored record (incoming source='user', tags=0); dropped to
preserve the richer stored record. See store.py add() -- the duplicate-deposit producer
at scene_memory.py:729 is the real fix.

$ grep -n "routed to update" ~/.synapse/logs/synapse.log | head -1
12091:2026-09-17 17:06:49,983 [synapse.memory] WARNING: Memory write refused or downgraded
(1 so far in this store): add() for existing id 'mem_incident' carries different content;
appending it would plant a conflicting duplicate identity and degrade the whole store on
next load; routed to update() (full rewrite) instead
```

`16:52` is the richness-comparing intermediate. `17:06` is the current routing guard. The `add()` comment block at `store.py:747-757` records **why** it was removed, and the reasoning is sound and worth preserving verbatim:

> An intermediate version of this guard kept whichever record carried more metadata and DISCARDED the other, while still returning `memory.id`. An adversarial review measured the consequence: **a caller cannot tell.** `ledger.py:486` sets `status["deposited"]=True` off this return, `seed_corpus.py:179` counts it as written, `vex_capture.py:112` hands it back as the id — all three would report success over a write that never landed. That is the SAME silent-failure class this whole incident is about, so it was removed.

**That argument is correct and this document does not dispute it.** What it leaves behind is a function whose docstring asserts a caller it no longer has, in a file that is the authority on collision behaviour. That is doc drift on a health-critical surface, and it is the kind that reads as reassurance.

---

## 2. Why `update()` is right for an update and wrong for a collision

### The two cases

| | Genuine update | Hash collision |
|---|---|---|
| **What happened** | one record, revised | two records, same identity |
| **Correct outcome** | incoming wins | both survive, or a ruled survivor |
| **What `add()` does** | incoming wins ✅ | incoming wins ❌ |

`update()` is unambiguously right for the first. A revised record *should* replace its prior self, and `_needs_rewrite` is the only honest way to express that in an append-only file. Routing there is also the only branch that cannot plant the conflicting line — which is the outage.

It is wrong for the second for one reason: **the two records are not versions of each other.** They are independent events. Picking one is data loss; the only question is how much and whether anyone is told.

### The core problem: the id cannot distinguish them

`add()` sees exactly one thing — `self._memories.get(memory.id)` at `:732` — and that lookup returns the same shape in both cases. There is no field it could consult. `updated_at` is stamped by `update()` itself at `:816`, *after* the decision. There is no version, no vector clock, no causal parent.

The guard resolves this with an argument from the id's construction (`store.py:769-777`):

> Losing metadata is not the risk it looks like, because **CONTENT PARTICIPATES IN THE ID** (`models.py:157-162` hashes `content:created_at:memory_type`). Two records sharing an id therefore share their content: a collision is always a **METADATA-only difference, never a lost edit.**

**Within its scope that argument is exactly right**, and the hazard ticket's measurement is what makes it verifiable rather than assumed: all 628 of 628 `mem_`-prefixed rows in the live snapshot reproduce from that hash, zero mismatches. If content is in the id, then same id ⇒ same content, and the only thing `update()` can destroy is metadata — `tags`, `hip_file`, `frame`, `source`, `hip_version`, the five fields `_metadata_richness` was built to rank.

### Where the argument stops, and the guard does not say so

The premise holds **only when the id was generated**. `models.py:148-149`:

```python
if not self.id:
    self.id = self._generate_id()
```

An explicitly supplied id never touches `_generate_id`, and content never enters it. Two live namespaces supply ids:

| Site | id | Content in the id? |
|---|---|---|
| `python/synapse/loop/coordinator.py:169` | `"loop_" + attempt["id"]` | **No** — the attempt identity |
| `python/synapse/memory/source_knowledge.py:61` | `"knowledge_" + sha256(encoded)` | Yes — content-derived, safe |

`loop_` breaks the premise. The id is the attempt; the content is `canonical(body)` including the outcome verdict (`coordinator.py:168-169`). **The same attempt re-delivered with a different outcome is a same-id, different-content write that is a genuine edit, not a metadata-only collision.** 533 such rows are live (hazard ticket §4).

Two consequences, and they cut in opposite directions:

1. **For `loop_`, `update()`'s incoming-wins is the correct disposition** — a redelivered attempt outcome *should* supersede. The guard happens to be right there, for a reason it does not state.
2. **`add()` cannot tell which namespace it is holding**, so it cannot know whether its own safety argument applies to the record in its hand.

Today the exposure is bounded by routing, not by the guard: loop capsules deposit through `ports.py:263` → `add_durable_if_absent`, which **raises** on same-id-different-payload (`moneta_store.py:701-702`) rather than reaching `add()`. That is a routing accident away from being load-bearing, and `_dual_write_jsonl(only_if_missing=True)` at `:705` does call `net.add(memory)` when payloads differ (`:986-987`) — so a `loop_` record with a changed payload **does** reach the mirror's `add()` and **does** take the `update()` branch.

**The honest statement of the invariant is:** a collision is metadata-only *for auto-generated `mem_` ids*. The docstring states it unqualified. Fixing the id (hazard ticket option (b)) narrows this further — it folds the metadata into the id, so two records differing in metadata stop sharing an identity at all.

---

## 3. What the divergence costs today

### 3.1 What `overwrote_prior` means

```
python/synapse/memory/store.py:237   self._rejected_writes = 0
python/synapse/memory/store.py:242   self._overwrote_prior = 0
```

Deliberately two counters (`:238-241`):

> Counted SEPARATELY from `_rejected_writes`. That counter also rises on `add_durable_if_absent`'s **CORRECT idempotency refusal**, so it cannot be promoted to a health signal without false-positiving every deposit. This one rises only where prior data was actually overwritten.

That separation is right. `rejected_writes` rises at three sites — `_require_writable_load` (degraded refusal, `:544`), `add_durable_if_absent` (`:682`), and `add()` (`:780`). Only the third is a loss. `overwrote_prior` rises at exactly one site: `store.py:779`.

**It is verdict-bearing.** `python/synapse/server/write_plane.py:430`:

```python
row["sick"] = bool(degraded) or not writable or bool(row.get("overwrote_prior"))
```

with the reasoning at `:462-467`:

> `overwrote_prior` DOES set the verdict. […] Nothing raises on that path (the dual-write net swallows it), so if this counter did not reach a verdict the loss would be invisible, which is the exact failure this whole module exists to end.

Also read by the panel's independent path at `python/synapse/panel/health_strip.py:431`.

### 3.2 Does the live zero mean "never happened"? **No.**

**It means "not since this `MemoryStore` object was constructed."** Three findings, each verified:

**(a) The counter is never persisted.**

```
$ grep -n "overwrote\|rejected_writes" python/synapse/memory/store.py | grep -i "index\|json\|dump\|write_report"
(no output)
```

`save()` (`:610+`) writes `memory.jsonl` and `index.json`; neither counter is in `serializable_index`. Both are plain ints on the instance, set to `0` at `:237`/`:242` in `__init__`. **Every process restart resets them to zero.** There is no `index.json` on the live seat at all:

```
$ ls C:/Users/User/AppData/Local/Temp/houdini_temp/untitled/.synapse/
.moneta  .w1_incoming_moneta  context.md  decisions.md  key.fingerprint
loop  memory.jsonl  memory.jsonl.degraded-load-1789506731
memory.jsonl.pre-backfill-1789681905  tasks.md
```

**(b) The counter is younger than the outage it exists to catch.**

```
$ git log --format='%h %ad %s' --date=short -S"overwrote_prior" -- python/synapse/memory/store.py
53e4f9cb 2026-09-17 release: v5.75.1 -- the tag that was checked (#108)
```

Landed **2026-09-17**, two days *after* the 2026-09-15 outage began. It could not have counted a single write from the incident that motivated it. A zero covers HEAD-era traffic only.

**(c) In a Moneta-backed seat, the only store that answers this question is the mirror.**

```
python/synapse/server/write_plane.py:353   _HEALTH_CONTRACT_MEMBERS = ("_jsonl_net", "primary", "shadow")
```

Candidates are the serving object plus those members, one level deep (`:356-384`). `MonetaBackedStore` has no `health()` (§1.1), so it returns `answered: False` at `:397-399` and lands in `silent`. **The verdict for the live seat is computed from `MonetaBackedStore._jsonl_net` — the mirror — alone.** The primary is structurally incapable of reporting a collision, because it does not have one.

So `overwrote_prior == 0` is an honest statement about the mirror, in this process, since HEAD. It is **not** a statement about the primary, ever.

### 3.3 Has it ever been non-zero on this seat? Only from tests.

The durable trace is the WARNING at `store.py:780-786`, which survives process death in `~/.synapse/logs/synapse.log`.

```
$ grep -c "add() for existing id" ~/.synapse/logs/synapse.log       # current log
26
$ grep -c "add() for existing id" ~/.synapse/logs/synapse.log.1     # rotated
0
$ grep -c "add() for existing id" ~/.synapse/logs/synapse.log.3     # rotated
0
```

All 26 are tests. Three independent tells:

```
$ grep -o "add() for existing id '[^']*'" ~/.synapse/logs/synapse.log | sort | uniq -c
     20 add() for existing id 'mem_incident'
      6 add() for existing id 'mem_x'
```

1. **The ids are fixtures.** `mem_incident` and `mem_x` are not `mem_` + 12 hex — no production write can produce them. Both appear in `tests/test_store_incident_2026_09_17.py`.
2. **Every line reads `(1 so far in this store)`** — 26 separate store objects each seeing exactly one. That is per-test `tmp_path` stores, not one long-lived production store.
3. **All 26 are dated `2026-09-17`**, the day the guard landed.

Neither id exists in the live primary:

```
rows 1162 parsed ids 1162 distinct 1162
mem_incident present: False
mem_x present: False
ids appearing >1x: 0
```

This is the known pytest-pollutes-the-production-log pattern, and here it is load-bearing: **the only evidence the counter has ever fired is test evidence.**

**Caveat on log coverage.** `synapse.log.2` is absent from `~/.synapse/logs/` — rotation has a gap, so "0 in the rotated logs" covers `.1` and `.3` only. Combined with (b), the log can only speak for 2026-09-17 onward regardless.

### 3.4 The cost that is actually being paid

The collision disposition is **not** where the divergence bill is. The measured bill is store drift, and it is large.

At repair time, `harness/notes/store-incident-2026-09-17/OPERATIONS_LOG.md:53`:

```
| Divergence measured | primary 1131 · mirror 882 · intersection 878 |
```

and `SUPPLY_PACKET.md:620`:

> **The repaired JSONL is 253 records behind Moneta.** `moneta_ids 1131 jsonl_ids 882 moneta_only 253 jsonl_only 4`, and **all 253 have `created_at` inside `2026-09-15T21:14:24Z → 2026-09-17T19:53:56Z`** — the outage window, exactly. Nothing was *lost* (Moneta is the serving store and kept them), but **the safety net has a 48-hour hole.**

Today, counted read-only without decrypting:

```
primary snapshot.json rows : 1162   (1162 distinct inner ids, 0 duplicates)
mirror  memory.jsonl lines : 1166
```

*(Line count, not distinct ids — the file is encrypted and was not decrypted. The append-only format means lines ≥ distinct ids between rewrites, and `jsonl_only 4` was the measured mirror-exclusive count at repair time.)*

**So the real ledger, ranked:**

| Cost | Size | Where |
|---|---|---|
| Mirror fell behind primary during the outage | **253 records, 48h** | measured, since backfilled |
| Primary silently holds two rows for one id | unbounded until a human runs the repair | `moneta_store.py:729` |
| Cortex prim overwritten, no counter, no log | unknown — **unmeasurable by construction** | `moneta_store.py:973` |
| Mirror overwrote prior metadata | **0 from production** on this seat, HEAD-era only | `store.py:779` |
| Disagreement re-poisons on next deposit | loop, not a one-off | `moneta_store.py:986-987` |

The disposition disagreement costs **nothing observed today**. What it costs is **the ability to notice** — and the four dispositions degrade that ability unequally: one counts and gates health, one is silent, one does not exist, and one only runs when a human already suspects a problem.

### 3.5 One gap worth naming

**No test anywhere asserts on `overwrote_prior`.**

```
$ grep -rn "overwrote_prior" tests/
(no output)
$ grep -rn "overwrote_prior" --include=*.py . | grep -v "memory/store.py"
./python/synapse/panel/health_strip.py:418
./python/synapse/panel/health_strip.py:431
./python/synapse/server/write_plane.py:415
./python/synapse/server/write_plane.py:430
./python/synapse/server/write_plane.py:462
```

Three production consumers, one of which sets a health verdict (`write_plane.py:430`). Zero tests. `test_rejected_writes_increments_when_a_write_is_refused` (`tests/test_store_incident_2026_09_17.py:403`) pins the *other* counter. A refactor that stopped incrementing `_overwrote_prior` would turn the health strip permanently green and no test would fail.

Naming it, not fixing it.

---

## 4. The options

### Option A — make the mirror match the primary's richness ordering

Restore a richness comparison in `MemoryStore.add`, so the mirror keeps the richer twin and agrees with `primary_repair`.

| | |
|---|---|
| **Cost** | `_metadata_richness` already exists at `store.py:158` and is already field-for-field identical to `primary_repair.richness:188-192`. Wiring, not writing. |
| **Gains** | Automatic path and recovery tool stop disagreeing — the invariant `store.py:166-168` claims. Kills the §1.4 re-poisoning loop for the auto-writer shape, where the incoming twin is the stripped one. |
| **Breaks — and this is decisive** | **This was already built and already removed, for a measured reason.** `store.py:747-757`: discarding the incoming record while returning `memory.id` makes `ledger.py:486`, `seed_corpus.py:179` and `vex_capture.py:112` all report success over a write that never landed. **Any revival must change the return contract**, not just the comparison. |
| **Second break** | Richness is right for the *auto-writer* shape and wrong for `loop_` (§2), where the later record is the legitimate successor and may well carry less metadata. |
| **Verdict** | Not viable as a revert. Viable only as "richness **plus** an honest return" — a larger change than it looks. |

### Option B — make the primary match the mirror

Give `MonetaBackedStore.add` a pre-deposit id check and a last-write-wins resolution.

| | |
|---|---|
| **Cost** | Mechanically what `add_durable_if_absent:699` already does. This is hazard-ticket option (c). |
| **Gains** | Closes the only path that silently holds two rows for one id. Makes `primary_repair` a recovery tool rather than standing maintenance. |
| **Breaks** | Converts a silent double-deposit into a raise or a silent drop at ~9 sites documented as best-effort — `scene_memory.py:791`, `:833`, `:872`, `:926`, `:967`. Raise breaks that contract; drop is the §1.5 silent-failure class again. |
| **Performance** | O(n) scan per add on the hot logging path. `save()` is already O(n) per deposit (`moneta_store.py:745-757`), so this doubles a known cost rather than adding a new class. |
| **Missing prerequisite** | The primary has **no `health()`** (§1.1). Adding a disposition without a health surface means adding an *uncounted* one — the cortex's mistake, at the primary. **A counter and a `health()` are the prerequisite, not a follow-up.** |
| **Verdict** | Viable, and it closes the widest hole. Sequence the health surface first. |

### Option C — keep both, document the asymmetry

Change no behaviour. Write the four-way table into the code and rely on `primary_repair` as standing maintenance.

| | |
|---|---|
| **Cost** | Near zero. Includes **fixing `_metadata_richness`'s docstring**, which is wrong at HEAD regardless of which option is chosen. |
| **Gains** | No new failure surface. Preserves the measured reasoning behind the current guard. |
| **Breaks** | The primary keeps accumulating duplicate ids between human repairs, and §1.4's re-poisoning loop stays armed. The cortex stays unmeasurable. |
| **Honest framing** | This is the status quo **plus** truth-in-documentation. It is not "do nothing" — three documented statements are currently wrong: `_metadata_richness`'s named caller, the unqualified "collision is always metadata-only", and any reading of `overwrote_prior == 0` as historical. |
| **Verdict** | The correct floor. Whatever else is chosen, the doc fixes are owed. |

### Option D — make the question moot by fixing the id

Hazard-ticket option (b): promote the `require_durable` re-hash at `store.py:1660-1669`, folding `tags`, `node_paths`, `hip_file`, `frame`, `source`, `agent_id`, `summary`, `tier` into the identity.

| | |
|---|---|
| **Cost** | Already written and in-tree. Moves no existing id (`store.py:1663-1664` keeps old ids intact). No stored-format, loader or USD change. |
| **Gains** | **Collapses the disposition question for the metadata case.** Two records that differ only in metadata stop sharing an id, so `add()` never reaches its `update()` branch for them and `primary_repair` finds nothing to rank. |
| **Residual** | Two **byte-identical** records in one second still share an id. But then all four dispositions are correct simultaneously — keeping either, both, or the richer is the same outcome. |
| **Caveat** | Separate the hash change from the `add_durable_if_absent` routing change, which converts best-effort writers into raising ones (hazard ticket §5(b)). |
| **Verdict** | The only option that dissolves rather than resolves the disagreement. |

### How D interacts with the others

**D is upstream of all three, and it changes what they are for.**

```
           ┌─ before D ─────────────────────────┐   ┌─ after D ──────────────────┐
collision  │ metadata-differing  +  identical   │   │        identical only      │
disposition│ ^^^^^^^^^^^^^^^^^^                 │   │                            │
           │ contested: A vs B vs C             │   │ uncontested: all agree     │
           └────────────────────────────────────┘   └────────────────────────────┘
```

- **D before B** makes B safe. The hazard ticket's own sequencing: once D removes the differing-payload case, a uniqueness check on the primary is "choosing between identical twins, which is a safe choice to automate." B's best-effort-contract problem shrinks to almost nothing, because dropping an identical twin loses no data.
- **D before A makes A unnecessary.** With metadata in the identity there is no richer twin to prefer; richness ranking has no input. Doing A first spends the return-contract redesign on a case D is about to delete.
- **D does not subsume C.** The doc fixes are owed either way, and D makes one of them *more* urgent: `_metadata_richness` becomes dead **and** obsolete, and should be deleted rather than re-documented.
- **D does not cover supplied ids.** `loop_` (§2) is outside `_generate_id` entirely and keeps its own disposition question — where incoming-wins is already correct.

**Recommended sequence, offered as analysis and not as a decision:** **C's doc fixes now** (they are true at HEAD and cost nothing) → **D** (dissolves the contested case) → **B with a primary `health()` first** (defence in depth, on the narrowed case) → **A only if a richness ordering is still wanted afterwards**, which D largely removes the need for.

---

## 5. The choice is the human's

**Nothing in this document changes either disposition.** No code was modified, no memory store was written, no repair was run, no commit was made. The mirror still routes to `update()`; the primary still keeps both; the cortex still overwrites; `primary_repair` still ranks by richness and still defaults to dry-run.

The four options are not equivalent and the reasoning behind the *current* behaviour is measured rather than accidental — the routing guard at `store.py:747-757` was built, reviewed adversarially, and revised on evidence within one afternoon. **Any change here reopens a decision that was already made carefully once.** That is a reason for the ruling to be explicit, not a reason to avoid it.

**What is owed regardless of the ruling** — because these are wrong at HEAD, not proposals:

1. `_metadata_richness`'s docstring (`store.py:159-178`) names a caller it does not have.
2. `add()`'s "a collision is always metadata-only" (`store.py:769-777`) is true for `mem_` and false for `loop_`.
3. `overwrote_prior == 0` cannot be read as "never happened" — it is process-scoped, younger than the outage, and mirror-only.

**This is a finding, not a decision. Joe rules.**

---

## Appendix — every claim's source

| Claim | Evidence |
|---|---|
| Primary `add()` has no id check | `python/synapse/memory/moneta_store.py:720,729` |
| Primary's checked sibling raises | `moneta_store.py:690,699,701-702` |
| Primary has no `health()` | `grep -c 'def health' python/synapse/memory/moneta_store.py` → `0` |
| Cortex prim keyed by `(kind,id)`, overwrites | `moneta_store.py:965,973` |
| Mirror's three branches | `store.py:697,732,742,746,779,788` |
| `update()` makes incoming authoritative | `store.py:811,816-817,820` |
| Divergent case deliberately does not raise | `store.py:722-728`; `moneta_store.py:977,993` |
| Mirror disposition is pinned | `tests/test_store_incident_2026_09_17.py:262,284`; `python -m pytest tests/test_store_incident_2026_09_17.py -q` → `10 passed` |
| Repair richness ordering | `primary_repair.py:173,188-192`; selection at `:413` |
| Repair took 1136 → 1131 | `harness/notes/store-incident-2026-09-17/OPERATIONS_LOG.md:34-36` |
| Disagreement is a re-poisoning loop | `primary_repair.py:57-65`; `moneta_store.py:985-987` |
| `_metadata_richness` has no callers | `grep -rn "_metadata_richness" --include=*.py .` → 1 hit, the def at `store.py:158` |
| Its docstring names `MemoryStore.add` | `store.py:161,166-168` |
| The intermediate guard existed and was removed | log `2026-09-17 16:52:19,744` ("dropped to preserve the richer stored record") vs `17:06:49,983` ("routed to update()"); rationale at `store.py:747-757` |
| id generated only when absent | `python/synapse/memory/models.py:148-149` |
| `loop_` ids are not content-derived | `python/synapse/loop/coordinator.py:169` |
| `knowledge_` ids are content-derived | `python/synapse/memory/source_knowledge.py:61` |
| Loop capsules route to the checked path | `python/synapse/loop/ports.py:263` |
| Counters initialised per process | `store.py:237,242` |
| Counters never persisted | `grep -n "overwrote\|rejected_writes" python/synapse/memory/store.py \| grep -i "index\|json\|dump\|write_report"` → no output |
| No `index.json` on the live seat | `ls C:/Users/User/AppData/Local/Temp/houdini_temp/untitled/.synapse/` |
| `overwrote_prior` landed 2026-09-17 | `git log -S"overwrote_prior" -- python/synapse/memory/store.py` → `53e4f9cb 2026-09-17` |
| It is verdict-bearing | `python/synapse/server/write_plane.py:430,462-467`; `panel/health_strip.py:431` |
| Only the mirror answers health in a Moneta seat | `write_plane.py:353,356-384,397-399` |
| 26 collision warnings, all tests | `grep -c "add() for existing id" ~/.synapse/logs/synapse.log` → `26`; ids `mem_incident`(20)/`mem_x`(6); all `(1 so far in this store)`; all `2026-09-17` |
| Rotated logs show none | `grep -c` on `synapse.log.1` → `0`, `synapse.log.3` → `0`; `synapse.log.2` absent |
| Test ids absent from live primary | read-only parse of `snapshot.json`: 1162 rows, 1162 distinct ids, 0 duplicates, neither id present |
| 253-record mirror hole | `OPERATIONS_LOG.md:53`; `SUPPLY_PACKET.md:620` |
| Live counts today | `snapshot.json` 1162 rows; `memory.jsonl` 1166 non-empty lines (not decrypted) |
| No test asserts `overwrote_prior` | `grep -rn "overwrote_prior" tests/` → no output |
| Best-effort contracts B would break | `scene_memory.py:791,833,872,926,967` |
| The `require_durable` re-hash exists | `store.py:1660-1669`; default at `store.py:1585` |

**Read-only conduct:** no memory store was constructed, no `MemoryStore`/`MonetaBackedStore`/`SynapseMemory` object was instantiated, `snapshot.json` was parsed with a filtering script rather than read into context, `memory.jsonl` was line-counted without decryption, and neither `primary_repair.py` nor `backfill_from_moneta.py` was run. Houdini 22.0.400 held the store throughout.
