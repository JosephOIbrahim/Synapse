# W8-SMEM — memory scout recon (read-only, first-hand)

**Leg:** W8-SMEM · **Branch:** `wave8/smem` · **Band:** TRUTH · **Date:** 2026-08-17
**Source:** `harness/bastion/PROGRAM.md` anchor **B4-MEMORY** (`:24` — "Moneta hardening, SQLite+FTS5 storage (old wave-6 plan folds here), ingest-ladder readiness, capsule persistence | Moneta env-gated; perf envelope UNKNOWN").
**Method:** read-only recon of my own worktree tree + a headless-safe raw SQLite/FTS5 envelope in a scratch tmp DB. Every claim below is anchored to a `file:line` I read this session, or explicitly marked **UNKNOWN** with a reason. Nothing inherited; nothing estimated; no real store touched.

**Verdict:** `green_with_findings`. **No P0** — the memory substrate (Moneta primary + loud JSONL fallback + per-deposit durability + isolated JSONL safety-net) functions; the SQLite+FTS5 line is moot-by-supersession; the capsule footguns are P1 (data-loss under a specific user action, not a blocked pipeline).

---

## 1. Moneta — schema registration, failure modes, write-durability

### Schema registration path (env-gated)
- Backend is selected by **`SYNAPSE_MEMORY_BACKEND`** (`store.py:982`, default `"jsonl"`); the production package sets it (`packages/synapse.json:27`).
- Moneta **importability** is gated by **`$MONETA_SRC`** — primary import, else path-inject that dir on `sys.path` (`moneta_runtime.py:175-182`). Package points it at `$SYNAPSE_ROOT/../Moneta/src` (`packages/synapse.json:18`), **out of this worktree**.
- USD **schema registration** is gated by **`PXR_PLUGINPATH_NAME`** (`moneta_runtime.py:221`); the package sets it to `$MONETA_SRC/../schema` to register `MonetaMemory` (`packages/synapse.json:22-24`).
- The 4-condition ladder: importable → config → `schema_registered()` (`:253`) → `schema_in_use()`. `schema_in_use` alone is NOT evidence (`:64-67`): Sdf-level authoring is schema-blind, so `typeName="MonetaMemory"` lands with or without a registered schema.

### FINDINGS
- **[P1] M1 — schema-registration diagnostic misleads on a broken seat.** `moneta_runtime.py:239-240` (else/unset branch) prints *"PXR_PLUGINPATH_NAME is unset — nothing in packages/synapse.json or in Moneta sets it, so this is the default posture"*, and the docstring `:76-78` repeats it — but `packages/synapse.json:22-24` **does** set `PXR_PLUGINPATH_NAME` ("Register the MonetaMemory USD schema…"). The misleading text fires exactly when the var is unset, i.e. on a seat where the package env failed to load → it **mislabels a broken install as "expected default posture."** Anchor: `python/synapse/memory/moneta_runtime.py:239` + `packages/synapse.json:22`. *(probe+verify CONFIRMED; I re-read both sides first-hand.)*
- **[UNKNOWN] M2 — actual runtime schema-registration state.** `schema_registered()` (`moneta_runtime.py:253`→`:230` `FindConcretePrimDefinition('MonetaMemory')`) needs a live pxr/USD runtime + on-disk schema assets (`$MONETA_SRC/../schema/plugInfo.json,generatedSchema.usda`) that resolve outside this worktree; returns `None` headless (`:224-228`). Cannot observe `registered=True/False` on the production seat.
- **[P2] M5 — per-deposit `save()` is BEST-EFFORT, not a hard guarantee.** `save()` swallows *all* snapshot exceptions into a WARNING (`moneta_store.py:873-874`) and `add()` still returns `memory.id`. Durability is actually underwritten by the **isolated JSONL dual-write safety net** — `add()` also calls `_dual_write_jsonl` (`:684` → `:701-715`, synchronous `net.add()+net.flush()` to `memory.jsonl`) and `_write_cortex` (`:683`). So a silently-failing Moneta snapshot still lands the memory in JSONL, but the operator keeps "moneta" while the primary snapshot quietly failed. Anchor: `moneta_store.py:873` + `:684`.
- **[P2] M4 — durability docstring stale.** Class/factory docstrings still describe a 30s `_save_interval` loss window (`moneta_store.py:165-174`, `:366-376`); `add()` now calls `self.save()` unconditionally per deposit (`:659`, comment `:648-658`) and no periodic daemon is started (`:240-241`). Fields `_last_save/_save_interval` (`:216-217`) no longer gate `add()`. Understates durability.
- **[P2] M3 — WAL "inert" claim is doc-vs-code drift.** `search()` calls `self._handle.signal_attention(weights)` (`moneta_store.py:854`, the sole live caller) while three comments assert *"SYNAPSE never calls signal_attention / the WAL is inert"* (`:176-177`, `:290`, `:370`). Crash class is mitigated by design (signals on Moneta UUIDs + `_quarantine_wal_if_unreplayable`, `:419`), so this is stale docs, not a live crash. *(probe said P1; verify reranked → P2; concur.)*
- **[UNKNOWN] M6 — primary snapshot fsync/atomicity.** `save()` delegates to vendor `durability.snapshot_ecs` (`moneta_store.py:871`); `**/durability.py` is absent from the worktree (`$MONETA_SRC` is out of tree). SYNAPSE's own reconcile write is verified atomic (tmp+flush+`os.fsync`+`os.replace`, `:601-607`) but runs only on a dim mismatch, not per deposit.
- **[P2 · observed-positive] M7 — failure modes are LOUD with recall preserved.** Not-importable → WARNING + `_record_backend_fallback` + `MemoryStore` (`store.py:1001-1011`); import ok but `from_storage_dir` raises → ERROR + `moneta_provenance()` + fallback (`:1017-1050`); shadow unavailable → WARNING + fallback (`:1051-1067`). `backend_fallback()` (`store.py:771`) is read by the doctor. One semi-silent sub-path: `use_real_usd=True→False` retry is WARNING-only (`moneta_store.py:303-323`) — keeps "moneta" with USD authoring silently off.

---

## 2. Capsule persistence + SESSCOPE (boot-scope) semantics

**Orientation:** the runtime "session capsule" is **`conversation.json`** — an Anthropic message list persisted by `server/session_store.py` under `$HIP/claude/` (headless: `%TEMP%/synapse_session/`), atomic `.tmp`+`os.replace` (`:57-114`). There is no separate capsule object; `CAPSULE_*.md` are harness notes, and the CLAUDE.md "capsule" is a Claude-Code construct. Load-on-boot: panel `__init__` → `load_conversation_scoped()` (`synapse_panel.py:341`).

**What survives a restart (SESSCOPE / W7, shipped v5.51.0):** the disk store survives **everything** (widget death, pypanel module flush, full Houdini restart, `session_store.py:165-166`). The boot token is minted once/process via `uuid4` on `hou.session` (Houdini) / `builtins` (headless) (`:181-198`) and stamped in a `conversation.json.owner.json` sidecar (`:211-221`). **same boot → auto-reattach** (`:245-246`); **new boot → park to `conversation.previous.json` + start clean** (`:247-259`), recoverable only via `/restore-session`.

### FINDINGS
- **[P1] C1 — `/restore-session` is a destructive footgun.** `restore_previous_conversation` (`session_store.py:275`) does `os.replace(prev, target)` with **no park of the current active conversation first**. If the artist builds new work in the current boot (saved to `conversation.json` by the panel turn-save `:2355` / close-save `:2650`) and then restores, the current work is clobbered on disk **and** replaced in memory (panel `:2206`) with no recovery path. Anchor: `python/synapse/server/session_store.py:275`. *(re-read first-hand.)*
- **[P1] C2 — single previous-slot: one-generation retention bound.** Park is `os.replace(target, prev)` (`session_store.py:250`); the docstring admits *"the slot always holds the most recent prior boot's work"* (`:239-240`). Two un-restored boots **permanently overwrite** the older parked conversation. Likely intended (g5 "start clean without destroying old work"), but the retention bound is undocumented to the artist → **for_ruling.** Anchor: `session_store.py:250`.
- **[P1] C3 — CLAUDE.md "provenance writers dormant" is STALE/partial.** First-hand: `agent_state.py` `log_decision`/`log_session`/`write_verification`/`create_task`/`update_task_status` **are wired** at real product sites — `host/graph_synth_runtime.py:122`, `server/handlers.py:1896/1928/2027`, `mcp/session.py:208`, `server/websocket.py:613`. Only the triplet `log_integrity` (`agent_state.py:329`), `log_routing_decision` (`:492`), `log_handoff` (`:601`) remain **test-only dormant** (callers only in `tests/test_agent_state.py`). Anchor: `agent_state.py:329` + the wired call sites.
- **[P2] C4 — session artifact identity.** `conversation.json` (Anthropic format), `$HIP/claude/` else `%TEMP%/synapse_session/`, atomic save (`session_store.py:53`, `:57-114`, `:21`). No separate capsule persistence object exists in `python/synapse`.
- **[P2] C6 — restore display gap.** Restore swaps `self._messages` (model context) but the **visible transcript is not repainted** — *"full re-render of old turns is docketed"* (`synapse_panel.py:2197-2198`).
- **[UNKNOWN] C7 — actual agent.usd prim authoring.** Wired writers self-no-op without pxr (`agent_state.py:301/314/338` `if not PXR_AVAILABLE: return`; `handlers.py:1886`). On-disk USD writes need a live pxr/Houdini render/session.
- **[UNKNOWN] C8 — `hou.session` boot-token real lifetime.** Whether the token survives the pypanel `sys.modules` flush on reopen but resets on full restart is only observable in a live Houdini GUI; tests use explicit `token=` overrides (`test_session_scope.py`).

---

## 3. SQLite+FTS5 readiness — old wave-6 plan vs current truth

**The "old wave-6 plan"** = **"Wave S — storage: SQLite + FTS5, lazy serve; JSONL shards stay the git-tracked build"** (`harness/notes/h22/BLUEPRINT.md:57`, `:99`), enumerated earlier in the v5 review (`docs/plans/2026-02-10-synapse-v5-review.md:37` factory-via-env-var, `:99` FTS5 recall, `:131` "SQLite migration framework"). `PROGRAM.md:24` (B4-MEMORY) folds it into W8 **for disposition**.

**Prereq-by-prereq current truth:**

| Wave-6 assumed prereq | Current truth | Anchor | Verdict |
|---|---|---|---|
| SQLite selectable via env-var factory | **FALSE / dead code** — live selector accepts only `jsonl\|moneta\|shadow`; `SYNAPSE_MEMORY_BACKEND=sqlite` warns "not a live backend … using jsonl". `create_memory_store` has **zero** product callers (tests+docs only). | `store.py:1068-1073`; `sqlite_store.py:749-752`; `docs/api/memory/sqlite_store.md:5-8` | **P2 (moot-by-supersession)** |
| FTS5 compiled into runtime sqlite3 | **UNKNOWN** for Houdini 22 py3.13. Store degrades gracefully either way (`try/except OperationalError` → fallback text search). Probe interpreter reported FTS5=YES on sqlite 3.50.4 — **a hint, not Houdini's runtime.** | `sqlite_store.py:104-111`, `:189-194` | **UNKNOWN** |
| recall reads the FTS index | reachable **inside the store** (FTS MATCH → +0.4 bonus) but **UNREACHABLE in production** (store never instantiated live; live recall = Moneta vector + keyword rerank, reads no `memory_fts`). | `sqlite_store.py:578-623`; `moneta_store.py:801-861` | **P2** |
| SQLite schema-migration framework | **ABSENT** — `SCHEMA_VERSION=1`, one-time version write, no upgrade arm. `migrate.py` is JSONL→Moneta only. | `sqlite_store.py:37`, `:170-186`; `migrate.py:1` | **P2** |

- **[P2] S1 — overarching: SQLite+FTS5 line is superseded by Moneta.** `moneta_store.py:1-21` "…there is one store"; `store.py` wires `moneta`/`shadow` live, no `sqlite` branch. SQLite is complete-but-orphaned inventory to adjudicate, not an active production gap → **for_ruling** (activate vs delete vs keep-inventory).
- **[P2] S5 — v5 review doc overclaim.** `docs/plans/2026-02-10-synapse-v5-review.md:37` presents "SQLite (WAL, FTS5) … factory via env var" as a shipped second backend; it is unreachable. Doc-drift.

---

## 4. Perf envelope — measured (headless-safe) vs UNKNOWN

**Measured — raw SQLite/FTS5 envelope, scratch tmp DB (NOT the live store).** Method: built `memories` + `memory_fts` (fts5, `tokenize='porter'`, WAL) in an OS-temp file mirroring the store schema; inserted 5000 synthetic rows, one commit/row (mirrors `sqlite_store.py:383`); timed. **Base table + FTS only — excludes the store's real per-add tags/keywords/links + Memory JSON, so real add cost is higher.**
- FTS5 available in the probe interpreter: **sqlite 3.50.4, FTS5 YES**.
- insert+commit ≈ **2.6 ms/row** · FTS5 MATCH ≈ **4.2 ms/query** · full-table-scan+py-filter ≈ **5.1 ms/query** · db ≈ **3.85 MB** @ 5000 rows.

### FINDINGS (architecture, first-hand from code)
- **[P1] P2f — Moneta per-add cost is O(n) + fixed synchronous extras.** `add()` = full atomic **O(n) snapshot** every deposit (`moneta_store.py:659`, docstring "Cost is O(n) per deposit") + `_write_cortex` typed-USD authoring (`:683`) + `_dual_write_jsonl` add+flush (`:684`), all synchronous under `_lock`; plus an **inline `run_sleep_pass()` consolidation every 100th add when `ecs.n>1000`** (`:660-675`). Per-add write cost grows with store size — the exact scaling wall the wave-6 SQLite plan ("capacity before mass") was meant to remove.
- **[P1] P3f — SQLite recall is O(n) as-built.** Text recall `SELECT * FROM memories WHERE 1=1` then scores **every** row in Python; FTS is a +0.4 bonus, **not** a candidate prefilter (`sqlite_store.py:571-644`). Even the "capacity" backend does not give sublinear text recall without a rework.
- **[P2] P4f — Moneta reads deserialize ALL rows' JSON per call.** `_iter_memories` (`moneta_store.py:744-764`) backs `get`/`get_by_type`/`get_by_tag`/`get_linked`/search-fallback; only `count()` is O(1) (`:768`).
- **[P2] P5f — SQLite store durability/throughput config.** No `PRAGMA synchronous` (stays **FULL**), per-operation commit, no batch/`executemany` (`sqlite_store.py:163-165`, `:383`). Indexes present so filtered reads are indexed. Also `background_load=True` daemon init with `_wait_loaded(timeout=5.0)` — first ops can block up to 5s (`:122-140`, `:208-212`).

### UNKNOWN (require live runtime; not estimated)
- Live recall latency end-to-end (`synapse_recall`/`memory_query` + LLM turn).
- Real on-disk store size/latency at production row count (`~/.synapse`, `G:/` — never touched).
- Vector-index recall perf (Moneta `query` overfetch = `max(limit*3, 50)`, `moneta_store.py:811-836`).
- Real ms/add magnitude of the O(n) Moneta snapshot + cortex + JSONL stack at real store size.

---

## Rankings summary

- **P0 (production-blocking):** none.
- **P1 (hardening):** C1 restore footgun · C2 one-generation retention bound · C3 stale "writers dormant" doc · M1 schema-reg diagnostic misleads · P2f Moneta O(n)/add stack · P3f SQLite O(n) recall.
- **P2 (polish/doc-drift):** M3 WAL-inert drift · M4 30s-window docstring · M5 best-effort save · M7 loud-fallback (positive) · C4/C6 · S1/S5 SQLite supersession + overclaim · S4 no migration arm · P4f/P5f.
- **UNKNOWN (need live Houdini/Moneta):** M2 schema-registered state · M6 vendor snapshot fsync · C7 agent.usd authoring · C8 hou.session lifetime · S2 FTS5-in-Houdini-py3.13 · perf live-latency set.

## For ruling
1. **C2** — is one-generation park retention the intended contract? Document or widen.
2. **S1** — SQLite+FTS5 disposition: activate (wire selector + build migration arm) vs delete `SQLiteMemoryStore` vs keep-as-inventory.
3. **M1/M4/M3** — product doc-drift fixes in `moneta_runtime.py`/`moneta_store.py` (human/forge-owned; readonly leg cannot touch product).

## Spawn proposals
- **(probe)** LIVE memory probe under hython/live Houdini to close the UNKNOWNs: schema_registered() on the real seat, FTS5-in-Houdini-py3.13, live recall latency + real store size, hou.session token lifetime, O(n)-per-add magnitude.
- **(held — build/forge, outside spawn_classes)** fix C1 (park current before restore) + M1/M3/M4 doc-drift + adjudicate S1.
