# Finding — the Memory id hash collides deterministically inside one wall-clock second

**Date:** 2026-09-18 · **HEAD:** `ca1e9e01` (master) · **VERSION:** 5.75.1
**Status:** open · paper deliverable · **no code changed by this finding**
**Measured against:** `C:/Users/User/AppData/Local/Temp/houdini_temp/untitled/.synapse/.moneta/snapshot.json` (1,162 rows), read-only

---

## What this is, and what it is not

Commit `ae34ed96` (2026-09-17) closed **one producer** of duplicate ids — the scene_memory dual-write, suppressed by a `deposit_to_moneta=False` flag at `python/synapse/session/tracker.py:515`. That incident is closed and is **not** re-opened here.

This finding is about the **mechanism underneath it**, which `ae34ed96` did not touch. Any two writes that agree on `content` and `memory_type` inside the same wall-clock second still receive the same id. That is reachable today by paths that have nothing to do with the dual-write.

The mechanism is **already known and already pinned by a passing test** that calls it a "documented residual":

```
tests/test_memory_models.py:38-45   test_same_content_same_second_still_collides
    # Documented residual: within the SAME second (same defaulted created_at),
    # identical content+type still shares an id. Full uniqueness (time_ns/uuid)
    # is the deferred entropy follow-up.
```

Verified at HEAD — narrowly scoped run of that one file:

```
$ python -m pytest tests/test_memory_models.py -q
5 passed, 2 warnings in 0.32s
```

So this is not a discovery. It is an **escalation**: the 2026-09-15 → 2026-09-17 outage proved the deferred residual is not theoretical, and the live store shows repeat writes landing **1.0 s apart** — the tightest gap physically expressible without being the same row.

---

## 1. The mechanism

### The two lines

**The hash** — `python/synapse/memory/models.py:157-162`:

```python
def _generate_id(self) -> str:
    """Generate a deterministic ID based on content and timestamp."""
    content_hash = hashlib.sha256(
        f"{self.content}:{self.created_at}:{self.memory_type.value}".encode()
    ).hexdigest()[:12]
    return f"mem_{content_hash}"
```

**The timestamp** — `python/synapse/memory/models.py:146-147`:

```python
if not self.created_at:
    self.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
```

### The exact hash inputs

Exactly three, joined by `:` —

| Input | Source | Resolution / variability |
|---|---|---|
| `content` | caller | Constant for every templated writer (see §3) |
| `created_at` | `models.py:147`, defaulted | **Whole seconds.** `%Y-%m-%dT%H:%M:%SZ` has no sub-second component at all |
| `memory_type.value` | caller | Constant per writer |

### Why this is deterministic, not probabilistic

This is **not** a birthday-paradox argument, and SHA-256 is not the weak part. The truncation to 12 hex characters (48 bits) is also not the weak part.

The **input space is collapsed**. For a writer whose `content` and `memory_type` are fixed, `created_at` is the *only* varying input — and it is constant for a full 1000 ms. Two such writes inside one second feed **byte-identical bytes** into `sha256()`. The collision probability is not `2^-48`. It is **1.0**. A full 256-bit digest would collide just as reliably, because the inputs are the same.

### The fields that would have saved it are excluded

`Memory` carries fields that genuinely distinguish two such writes — `tags`, `node_paths`, `hip_file`, `frame`, `source`, `agent_id`, `summary`, `tier` — and **none of them are in the hash.**

That exclusion has already bitten once, in a nearby place. At `python/synapse/session/tracker.py:194-201`, fix H-4 added an explicit session-distinguishing `summary=` because auto-derived summaries were showing N identical rows to the AI:

```python
# H-4: an explicit, session-distinguishing summary. Without it,
# Memory.__post_init__ auto-derives summary from the first content
# line — always the literal "## Session Summary" heading — so
# recent_activity shows N identical rows to the AI on every connect.
```

That fixed the **display** field. It could not fix the **identity**, because `summary` is not hashed. The same content still produces the same id.

---

## 2. The reproduction condition

**Two `Memory(...)` constructions that satisfy all of:**

1. equal `content` (byte-for-byte),
2. equal `memory_type`,
3. no explicit `id` passed (so `models.py:148-149` generates one),
4. no explicit `created_at` passed (so `models.py:146-147` defaults it),
5. both landing inside the **same UTC second**.

**Smallest live entry point** — two `/synapse` write commands of the same `cmd_type` one second apart or less:

```
handlers.py:633   bridge.log_action(f"Executed: {cmd_type}", session_id=sid)
  -> tracker.py:340   self._synapse.add(content=action, memory_type=MemoryType.ACTION, ...)
     -> models.py:147  created_at = <this second>
     -> models.py:157  id = mem_<sha256(content:created_at:type)[:12]>
```

Note that `handlers.py:637-639` marshals this through `run_on_main`, so the two writes are **serialized**. Serialization does not help. Ordering is not the problem; timestamp resolution is.

### What happens downstream depends on which store receives it

| Layer | File:line | Behavior on a colliding id |
|---|---|---|
| **Primary** (Moneta) | `moneta_store.py:720-729` | **No id check at all.** `self._handle.deposit(payload, ...)` lands both; each row gets its own `entity_id`. Two distinct events, one identity. |
| **Mirror** (JSONL) | `store.py:697+` (B3 guard) | Same id + different payload is re-routed to `update()` and counted into `health()["rejected_writes"]`. The mirror **cannot hold both**. |
| **Restart** | `store.py:410` | `raise ValueError("conflicting duplicate memory identity")` if two differing lines for one id ever reach the JSONL — degrades the whole store, refuses every write. This is the 2026-09-15 outage shape. |
| **USD cortex** | `moneta_store.py:965-975` | Prim keyed by `(kind, id)` — `cortex.write(memory.memory_type.value, memory.id, payload)`. The second write **overwrites the first prim.** |

So the standing consequence at HEAD is: **primary accepts both, mirror and USD keep one, and the two stores diverge silently.** The B3 guard hardened the *mirror* against the outage. It did not harden the *primary* against the collision.

---

## 3. Which code paths can still reach it at HEAD

Ranked by live reachability. "Fixed content" means the content string contains nothing that varies between two calls in one second.

### Rank 1 — `Executed: {cmd_type}` · LIVE · proven on disk

- **Site:** `python/synapse/server/handlers.py:633`, inside `_submit_logs` → `run_on_main(log_memory, ...)`
- **Sink:** `python/synapse/session/tracker.py:320-346` (`log_action` → `self._synapse.add` at `:340`)
- **Content:** `f"Executed: {cmd_type}"` — **fully fixed.** No node path, no payload, no counter.
- **Two in one second realistic?** **Yes, and it is on disk.** 184 byte-identical `'Executed: execute_python'` rows, closest pair **1.0 s** apart (§4).
- **What causes it:** any burst of same-type write commands — an agent issuing two `execute_python` calls back to back, a scripted parameter sweep, a panel retry after a slow response. This fires on **every** `/synapse` write command, so it is the highest-volume writer in the system.

### Rank 2 — session summary · LIVE · proven on disk

- **Site:** `python/synapse/session/tracker.py:173-201` (`end_session` → `self._synapse.add` at `:191`)
- **Content builder:** `python/synapse/session/summary.py:26-30` — heading + `**Duration:** {duration_str}` + `**Commands:** {n}`, with node/decision/error lists appended only if non-empty.
- **Two in one second realistic?** **Yes, and it is on disk.** Two short sessions that both ran 1 command in 1 second with no nodes created produce **byte-identical content**. 97 such rows, closest pair **1.0 s** apart.
- **What causes it:** two clients disconnecting together; a reconnect cycle; the panel and an MCP client both ending short sessions. The distinguishing `summary=` added by H-4 at `:198-201` does **not** protect the id (§1).

### Rank 3 — `AI session started` · LIVE · armed, not yet observed tight

- **Site:** `python/synapse/session/tracker.py:145-170` (`start_session` → `self._synapse.add` at `:164`)
- **Content:** `f"AI session started (client: {client_id})"` — varies **only** by `client_id`.
- **Two in one second realistic?** Yes for a **same-client** double connect. Note `session_id` at `:152` is `f"sess_{int(time.time())}_{client_id}"` — also whole-second, so it does not disambiguate either, and it is not in the content anyway.
- **What causes it:** reconnect storm, panel restart racing a retry, a client that connects twice on startup. Tightest observed gap on disk is 628 s, so this is **armed but unexercised**.

### Rank 4 — `log_error` · LIVE · armed, and structurally the most likely future trigger

- **Site:** `python/synapse/session/tracker.py:395-407` (`self._synapse.add` at `:403`)
- **Content:** the raw error string, `memory_type=MemoryType.ERROR`.
- **Two in one second realistic?** **Yes — this is the most likely of all.** A retry loop that raises the same exception twice is *fast by design*; sub-second retry is the normal case, not the edge case.
- **What causes it:** any bounded-retry path logging each failure. No `error`-typed rows exist in the live `mem_` namespace yet (the 628 rows are note/action/summary/decision only), so this path is **armed and unexercised** — which is exactly the kind that surfaces during an incident, when retries are firing.

### Rank 5 — `memory_write` command · LIVE · agent-facing

- **Site:** `python/synapse/server/handlers_memory.py:236-252` (`_handle_memory_write` → `write_memory_entry(paths["scene_dir"], content, entry_type)`)
- **Sink:** `python/synapse/memory/scene_memory.py:757` — `syn.store.add(Memory(content=..., memory_type=MemoryType.NOTE, ...))`
- **Note the default:** `scene_memory.py:706-707` — `def write_memory_entry(..., deposit_to_moneta: bool = True)`. The Moneta deposit is **on by default**. `ae34ed96` set it `False` at exactly **one** caller (`tracker.py:515`). This caller does not pass it, so it deposits.
- **Two in one second realistic?** Yes. This is an **agent-facing tool** (`synapse_memory_write`). An LLM retrying after a timeout, or writing the same note twice in a burst, is a normal failure mode.
- **What causes it:** agent retry; a workflow that writes the same note from two steps.

### Rank 6 — the four `record_*` scene-memory deposits · LIVE

- **Helper:** `python/synapse/memory/scene_memory.py:784-820` (`_deposit_to_moneta_if_available` → `syn.store.add(Memory(...))` at `:808-813`)
- **Call sites:** `:848` `record_solaris_state` · `:897` `record_render_settings` · `:941` `record_cops_network` · `:983` `record_texture_bake`
- **The trap:** three of these embed a timestamp in the content via `_now()`. That buys **nothing**, because `_now()` has the *same* resolution — `python/synapse/memory/scene_memory.py:448-450`:

  ```python
  def _now() -> str:
      """UTC timestamp string."""
      return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
  ```

  Inside one second, both the embedded timestamp **and** `created_at` are frozen.
- **Worst of the four:** `record_render_settings` (`:862-897`). Its content is built purely from the settings dict plus `_now()` (`:883-893`) — recording the same settings twice in one second is byte-identical. Realistic when two ROPs share settings, or a validate-then-record path records twice.

### Rank 7 — `api_adapter._log_action` · DORMANT today, worst if armed

- **Site:** `python/synapse/server/api_adapter.py:84-93`, called at `:235, :252, :268, :311, :320, :375, :437, :451`
- **Why worst:** it does not marshal. It spawns a **daemon thread per call**:

  ```python
  threading.Thread(target=bridge.log_action,
                   args=(f"Executed: {cmd_type}",),
                   kwargs={"session_id": _session_id}, daemon=True).start()
  ```

  Two `set_parm` calls in one second produce **unordered concurrent** adds into the unchecked primary (`moneta_store.py:720-729`).
- **Reachability today:** `grep -rn "api_adapter" python/ shared/ packages/` returns **no importer** — only a comment reference at `inspector/tool_inspect_stage.py:229`. It is started manually from the Houdini Python Shell (`api_adapter.py:19-20`, `start_api_server(port=8008)`). So: **dormant, not wired.** Rank it as a landmine, not a live fire.

### Not vulnerable — and worth copying

| Path | File:line | Why it is safe |
|---|---|---|
| Loop outcome capsules | `python/synapse/loop/coordinator.py:169` | `Memory(id="loop_" + attempt["id"], ...)` — id supplied from the attempt identity, never hashed from content. **533 such rows live, zero repeats.** Working precedent for fix (b). |
| Checked experience | `python/synapse/memory/experience.py:226` | Uses `add_durable_if_absent` — the id-guarded path. |
| Loop ports | `python/synapse/loop/ports.py:263` | Uses `add_durable_if_absent`. |

---

## 4. Live near-miss evidence (re-measured 2026-09-18)

All numbers below were produced by scripts written for this finding and run against the live snapshot read-only. Nothing was written to any memory store.

### Command

```
python C:/Users/User/AppData/Local/Temp/claude/C--Users-User-SYNAPSE/\
f1c652fa-7459-4560-81ac-291364e46ae1/scratchpad/idhash_measure.py
```

(Scripts: `idhash_measure.py`, `idhash_ns.py`, `idhash_nearmiss.py` in that scratchpad. Each loads `snapshot.json`, parses `row["payload"]` as JSON, and groups by `(content, memory_type)`.)

### Output — store shape and namespaces

```
rows: 1162
unparsable payloads: 0
parsed records: 1162
id reproduces from hash: 628  mismatch: 534
distinct inner ids: 1162  ids appearing >1x: 0
distinct (content, memory_type) keys: 641
keys written more than once: 69
```

```
id prefix counts: {'mem': 628, 'exp': 1, 'loop': 533}
  mem  -> {'note': 273, 'action': 200, 'summary': 152, 'decision': 3}
  exp  -> {'feedback': 1}
  loop -> {'feedback': 533}
mem_ rows: 628 of which id does NOT reproduce from _generate_id: 0
mem_-namespace distinct (content,type) keys: 107 repeated: 69
```

**Four things this establishes:**

1. **The mechanism is the live id generator, not a historical one.** All **628 of 628** `mem_` rows reproduce exactly from `sha256(f"{content}:{created_at}:{memory_type}")[:12]`. Zero mismatches.
2. **The store is currently clean** — 1,162 distinct inner ids, **0 duplicates**. `ae34ed96` plus the repair held.
3. **The 534 "mismatches" are a different namespace, not a defect** — 533 `loop_` capsules and 1 `exp_` record, which construct ids by other schemes and are not vulnerable.
4. **Inside the vulnerable namespace the repeat rate is high.** 69 of 107 distinct `(content, memory_type)` keys — **64.5%** — are written more than once. **590 of 1,162 rows** live in a repeated key.

### Output — repeat counts and tightest gaps

```
TOP 12 repeated (content, memory_type) by copy count:
   184 copies | tightest gap 1s    | type=action  | 'Executed: execute_python'
    97 copies | tightest gap 1s    | type=summary | '## Session Summary\n**Duration:** 0m 1s\n**Commands:** 1\n'
    30 copies | tightest gap 20s   | type=summary | '## Session Summary\n**Duration:** 0m 0s\n**Commands:** 1\n'
    15 copies | tightest gap 46s   | type=summary | '## Session Summary\n**Duration:** 0m 2s\n**Commands:** 1\n'
    14 copies | tightest gap 763s  | type=note    | 'AI session started (client: client_4.0.0_00002)'
    12 copies | tightest gap 2184s | type=note    | 'AI session started (client: client_4.0.0_00003)'
    12 copies | tightest gap 628s  | type=note    | 'AI session started (client: client_4.0.0_00004)'
    11 copies | tightest gap 5119s | type=note    | 'AI session started (client: client_4.0.0_00006)'
     9 copies | tightest gap 16s   | type=action  | 'Executed: memory_status'
     9 copies | tightest gap 9230s | type=note    | 'AI session started (client: client_4.0.0_00005)'
     8 copies | tightest gap 9175s | type=note    | 'AI session started (client: client_4.0.0_00007)'
     7 copies | tightest gap 5162s | type=note    | 'AI session started (client: client_4.0.0_00008)'

repeated keys whose tightest gap is 0s (same-second, same content+type): 0
rows living in a repeated key: 590
```

**1.0 s is the floor.** Because `created_at` has no sub-second component, two rows cannot be closer than 1 s apart without being the *same* row. The system is running **one tick** off the collision, twice, on its two highest-volume writers.

### The counterfactual, computed rather than asserted

`idhash_nearmiss.py` takes each tightest pair and recomputes what the second row's id *would* have been had it landed in the first row's second:

```
KEY: 'Executed: execute_python' | type: action
copies: 184 | distinct seconds: 184 | adjacent pairs exactly 1s apart: 1
  near-miss pair:
    A created_at=2026-09-09T00:12:28Z  id=mem_e450b09bf37c  entity=8346fb03-6009-481f-965b-f6bac1004de9
    B created_at=2026-09-09T00:12:29Z  id=mem_a1b8c2cba9df  entity=5b321cb6-c928-42c2-82c5-a6f3501cd8e8
    counterfactual: if B had landed in A's second, B.id would be mem_e450b09bf37c == A.id (YES)

KEY: '## Session Summary\n**Duration:** 0m 1s\n**Commands:** 1\n' | type: summary
copies: 97 | distinct seconds: 97 | adjacent pairs exactly 1s apart: 1
  near-miss pair:
    A created_at=2026-09-09T00:12:28Z  id=mem_f99dc3d1ca6b  entity=cc5021bb-311d-41b3-a32b-57d87ed8f3a4
    B created_at=2026-09-09T00:12:29Z  id=mem_6c81c417010b  entity=fbf33560-a502-49bb-be0b-5b96ddaee190
    counterfactual: if B had landed in A's second, B.id would be mem_f99dc3d1ca6b == A.id (YES)
```

**Note the timestamps.** Both near-misses are the *same* `00:12:28 → 00:12:29` boundary. A single burst on 2026-09-09 produced an `action` row and a `summary` row one second apart on two independent writers simultaneously. One scheduler tick, or one slightly faster command, and that burst writes two colliding ids on two different writers at once.

---

## 5. Candidate fixes

### (a) Sub-second granularity in `created_at`

**Change:** `models.py:147` — emit a sub-second component (e.g. `time.time_ns()` formatted, or `%f`).

| | |
|---|---|
| **Cost** | One line. Cheapest by far. |
| **Breaks — sort order** | **9 lexical sort sites** compare `created_at` as a *string*: `consolidation.py:157`, `markdown.py:207`, `moneta_store.py:167`, `moneta_store.py:1078`, `sqlite_store.py:660`, `store.py:980`, `store.py:1019`, `store.py:1846`, `vector_recall.py:137`. Mixed-format data sorts **wrong**, proven: `'2026-01-01T00:00:00.500000Z' < '2026-01-01T00:00:00Z'` is `True` (`.` = 0x2E < `Z` = 0x5A). Two of those sites (`moneta_store.py:167`, `:1078`) are the `reverse=True` recency sorts feeding recall, so the visible symptom is **recall ordering**, not a crash — the worst kind of symptom. |
| **Breaks — tests** | `tests/test_memory_models.py:38-45` asserts `a.id == b.id` and would **fail**. That test pins the bug, not a requirement, so it must be rewritten. `:22-29` monkeypatches `models.time.strftime` and its stub would need updating. |
| **Not affected** | `tracker.py:64-67` `strptime(..., "%Y-%m-%dT%H:%M:%SZ")` parses `SynapseSession.started_at/ended_at`, **not** `Memory.created_at` — unaffected. `experience.py:49-54` hard-rejects any sub-second form via `re.fullmatch`, but it validates experience `checked_at` (called at `:150`, `:179`), not `Memory.created_at` — **not a blocker**, though it does establish a repo-wide "canonical UTC timestamp" convention that would now have two shapes. |
| **Stored format / loader / USD** | Unchanged. `created_at` is a plain string field; no schema migration. |
| **Backward compatible with the 1,162 rows?** | **Yes** for storage — old rows keep whole-second values and still load. **No** for ordering — the store becomes permanently mixed-format against those 9 lexical comparisons. |
| **Residual** | Buys *probabilistic* distinctness. Two writes in the same microsecond still collide, and the distinguishing fields (`tags`, `node_paths`, `hip_file`, …) remain outside the identity. |

### (b) Provenance / entity identity inside the hash — **already written, gated off**

**This is not a new design.** It exists in-tree at `python/synapse/memory/store.py:1660-1669`, behind `require_durable=True`:

```python
if require_durable:
    # The legacy Memory ID hashes prose + whole-second timestamp +
    # kind. Identical prose recorded at two scopes in one second must
    # not overwrite the first decision. Keep old/deserialized IDs
    # intact; checked new records include all canonical provenance.
    identity = memory.to_dict()
    identity.pop("id", None)
    memory.id = "mem_" + hashlib.sha256(json.dumps(
        identity, sort_keys=True, allow_nan=False,
    ).encode("utf-8")).hexdigest()[:12]
```

It drops `id` and re-hashes the **whole canonical dict**, so `tags`, `node_paths`, `hip_file`, `frame`, `source`, `agent_id`, `summary` and `tier` all become identity-bearing. Its own comment names this exact hazard.

| | |
|---|---|
| **Change** | Promote it to the default for the automatic writers — pass `require_durable=True` at `tracker.py:164`, `:191`, `:340`, `:403`, or flip the default at `store.py:1585` (`require_durable: bool = False`). |
| **The real cost — not the hash, the routing** | `require_durable` also routes to `add_durable_if_absent` (`store.py:1670-1672` → `moneta_store.py:690-708`), which calls `_require_durable()` (`moneta_store.py:710-718`) and **raises** when the handle has no durability or the identity holds different data. That converts the auto-writers from best-effort to raising. A raise inside `tracker.log_action` reaches the `except Exception` at `handlers.py:640-641` and downgrades to a warning — survivable, but it turns a silent success into a **silent skip**. **This needs a decision, not a patch.** The hash change and the routing change can be separated. |
| **Performance** | `add_durable_if_absent` scans all memories per add (`moneta_store.py:699`), on top of the already-O(n) per-deposit `save()` (`moneta_store.py:745-757`). At 1,162 rows this is fine; it is a scaling note, not a blocker. |
| **Stored format / loader / USD** | **Unchanged.** Still `mem_` + 12 hex. No loader change, no JSONL change, no USD schema change (`moneta_store.py:965-975` keys prims by `(kind, id)` and does not care how `id` was derived). |
| **Backward compatible with the 1,162 rows?** | **Yes, decisively.** The re-hash runs only on new records; `store.py:1663-1664` explicitly keeps "old/deserialized IDs intact". **No existing row's id moves.** The five literal ids pinned at `primary_repair.py:124-128` and the one at `backfill_from_moneta.py:132` do not churn. |
| **Existing tests** | `tests/test_memory_models.py` passes **unchanged** — all 5 — because `Memory._generate_id` is untouched; the re-hash happens one layer up in `SynapseMemory.add`. The fix does not disturb the model-level contract those tests pin. |
| **Residual — stated honestly** | Two byte-identical events in one second still produce one id. But that is now *correct*: `add_durable_if_absent` (`moneta_store.py:700-706`) treats an identical payload as an **idempotent retry**, not as data loss. The destructive case — same id, **different** payload — is eliminated. If you need to *count* two indistinguishable `execute_python` calls in one second, (b) alone will not do it; you need (a) or a counter as well. |

### (c) Explicit uniqueness check on insert

**The mirror already has this. The primary does not.**

- Mirror: `store.py:697+` (B3 guard) and `store.py:673-695` (`add_durable_if_absent`).
- Primary: `moneta_store.py:720-729` — `add()` calls `self._handle.deposit(payload, ...)` with **no id lookup at all**.

| | |
|---|---|
| **Change** | Add a pre-deposit id scan to `MonetaBackedStore.add` — mechanically what `add_durable_if_absent:699` already does. "Make the unchecked path checked." |
| **Breaks** | It converts today's silent double-deposit into either a **raise** or a **silent drop**, at ~9 auto-writer call sites documented as best-effort — "Swallows all exceptions so callers never break from a Moneta failure" (`scene_memory.py:791`) and "Best-effort: never raises, never breaks the caller" (`scene_memory.py:833`, `:872`, `:926`, `:967`). Raise breaks that contract; drop loses the second event without telling anyone. Neither is obviously right — which is precisely why this is a ruling, not a patch. |
| **Performance** | O(n) scan per add on the hot automatic-logging path (every write command). The per-deposit `save()` is already O(n), so this doubles a known cost rather than introducing a new class. |
| **Stored format / loader / USD** | Unchanged. |
| **Backward compatible with the 1,162 rows?** | **Yes**, fully. Pure insert-time behavior. |
| **Residual** | **It does not fix the mechanism — it contains the blast.** Two distinct events still map to one identity; the check only decides which one survives and whether anyone is told. |

### Recommendation

**Take (b) — promote the existing `require_durable` re-hash, and split it from the routing change.**

The reasons, in order:

1. It is the only option that makes the **identity structurally match the record**. (a) buys entropy; (c) picks a survivor. (b) makes two genuinely different records genuinely different.
2. It is **already written, shipped and exercised** in-tree at `store.py:1660-1669`, with a comment that names this exact hazard.
3. It **moves no existing id** — the 1,162 rows on disk, and the six literal ids pinned in `primary_repair.py` / `backfill_from_moneta.py`, are untouched.
4. It changes **no stored format, no loader, no USD schema**, and `tests/test_memory_models.py` passes unchanged.

Sequence it as: **(b) hash first** (the four `tracker.py` call sites, or the default at `store.py:1584`), holding the `add_durable_if_absent` routing change back as a separate decision, since that is what converts best-effort writers into raising ones. Then **(c) on the primary** as defence in depth, once (b) has removed the case where the two payloads differ — at that point a uniqueness check is choosing between identical twins, which is a safe choice to automate.

Treat **(a) as optional and orthogonal.** Take it only if you need to count same-second repeats, and only after the 9 lexical sort sites are converted to parsed comparison — otherwise it fixes ids and quietly corrupts recall ordering.

**This is a recommendation, not a decision. The choice is the human's.** This finding changes no code and commits nothing.

---

## Appendix — every claim's source

| Claim | Evidence |
|---|---|
| Hash inputs and truncation | `python/synapse/memory/models.py:157-162` |
| Whole-second `created_at` | `python/synapse/memory/models.py:146-147` |
| Collision pinned by a passing test | `tests/test_memory_models.py:38-45`; `python -m pytest tests/test_memory_models.py -q` → `5 passed` |
| Distinguishing `summary` not hashed | `python/synapse/session/tracker.py:194-201` (H-4 comment) |
| `ae34ed96` suppressed one producer via a flag | `python/synapse/session/tracker.py:507-516`; default is `True` at `scene_memory.py:706-707` |
| Primary `add()` has no id check | `python/synapse/memory/moneta_store.py:720-729` |
| Mirror B3 guard | `python/synapse/memory/store.py:697+` |
| Loader refuses conflicting identity | `python/synapse/memory/store.py:410` |
| USD prim keyed by `(kind, id)` | `python/synapse/memory/moneta_store.py:965-975` |
| `_now()` same resolution as `created_at` | `python/synapse/memory/scene_memory.py:448-450` |
| `api_adapter` spawns daemon threads | `python/synapse/server/api_adapter.py:84-93` |
| `api_adapter` has no importer | `grep -rn "api_adapter" python/ shared/ packages/` → only `inspector/tool_inspect_stage.py:229` (a comment) |
| Loop capsules use a supplied id | `python/synapse/loop/coordinator.py:169`; 533 live rows, 0 repeats |
| The `require_durable` re-hash exists | `python/synapse/memory/store.py:1660-1669`; its parameter default at `store.py:1585` |
| Best-effort contracts the primary check would break | `scene_memory.py:791`, `:833`, `:872`, `:926`, `:967` |
| 9 lexical `created_at` sorts | `consolidation.py:157`, `markdown.py:207`, `moneta_store.py:167`, `moneta_store.py:1078`, `sqlite_store.py:660`, `store.py:980`, `store.py:1019`, `store.py:1846`, `vector_recall.py:137` |
| Mixed-format sorts wrong | `python -c "print('2026-01-01T00:00:00.500000Z' < '2026-01-01T00:00:00Z')"` → `True` |
| All live measurements | `idhash_measure.py`, `idhash_ns.py`, `idhash_nearmiss.py` (scratchpad), outputs quoted verbatim in §4 |
