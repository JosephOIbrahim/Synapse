# Handoff — memory dual-write + hython contract

**Status:** CLOSED 2026-09-18. Live store located, second writer named, root cause
stated with evidence below; the defect was already repaired by `ae34ed96` and the
live store is clean. Mirror divergence remains open (see "Still open").
**Written:** 2026-09-18. **Pins:** GUI 22.0.400 (SYNAPSE server live on :9999, path
`/synapse`), hython lane 22.0.417 (Python 3.13.10).

Paste the fenced block below as the opening prompt of a fresh Claude Code session
(Opus 5) from the repo root. It is written to survive a cold start: the new session
has none of the originating context, and the two most likely failure modes are
rebuilding tooling that already exists and auto-deduplicating the memory store.

The guardrail against deduplication is the single most important line. A capable
model looking at that store will see duplicate ids and reach for the obvious fix,
and the obvious fix silently deletes the tagged, frame-anchored versions of the
canonical Solaris recipes.

---

## Resolution — 2026-09-18

Executed against the live GUI seat (Houdini 22.0.400, pid 32804, started
2026-09-18 13:37:21). Read-only: no store mutation, no product-code edits.
`python harness/verify/hython_verbs.py --check all` → exit 0
(`PASS: freshness, no-mutation, ok, tops-defect, ui-bound — build 22.0.417, 44 verbs swept`).

### 1. Live store — located

```
C:\Users\User\AppData\Local\Temp\houdini_temp\untitled\.synapse\.moneta\
  snapshot.json        7,826,160 B   1131 rows   0 duplicated inner ids
  cortex_root.usda     1,729,255 B   (mtime 2026-09-17 16:30 — stale vs snapshot)
  usd/
```

Resolved by `MemoryStore._get_storage_dir` (`python/synapse/memory/store.py:1508`)
→ `<hip dir>/.synapse`, plus `.moneta` appended by
`MonetaBackedStore.from_storage_dir` (`python/synapse/memory/moneta_store.py:294`).
The untitled scene puts the hip dir in `$HOUDINI_TEMP_DIR\untitled`.

Live confirmation, `synapse_memory_status` over the bridge: `entries_total 1132`,
`accepting_writes true`, `rejected_writes 0`, `overwrote_prior 0`. One deposit
landed after the snapshot was written; the count is consistent.

The V0 guess that the live backend is USD is **wrong in emphasis**: the durable
primary is `snapshot.json` (Moneta ECS). `cortex_root.usda` is a typed *mirror*
written by `_write_cortex`, and `memory.jsonl` (encrypted, 1137 lines) is a second
mirror. Three surfaces, one primary.

### 2. Second writer — named

`python/synapse/memory/scene_memory.py:761` — the Moneta deposit inside
`write_memory_entry`, constructing `Memory(..., source="auto")` with `tags`,
`hip_file`, `hip_version` and `frame` left at dataclass defaults.

Call path that produced the five poisoned rows:

```
tracker.handle_memory_add            session/tracker.py:477
  ├─ self._synapse.add(source="ai")  session/tracker.py:492   ← rich record
  └─ write_memory_entry(...)         session/tracker.py:507
       └─ syn.store.add(Memory(source="auto"))   memory/scene_memory.py:761  ← lossy twin
```

A second lossy site with the same shape exists at
`memory/scene_memory.py:812` (`_deposit_to_moneta_if_available`), reached from
`scene_memory.py:848 / :897 / :941 / :983`. It did not produce any of the five.

**V0 suspect refuted.** `host/memory_loop.observe_operation`
(`python/synapse/host/memory_loop.py:182`) sets no `source` — it forwards
`record.get("source")` at `:89`. It is not a writer of `source="auto"` rows.

### 3. Root cause — defect in the writer, not over-strict reading

`Memory._generate_id` (`python/synapse/memory/models.py:157-162`) hashes
`content:created_at:memory_type` only, at whole-second granularity. The lossy twin
shares all three with the rich record, so the two collide on `mem_*` id while
carrying different payloads. `memory_lifecycle._records`
(`python/synapse/host/memory_lifecycle.py:174-175`) is correct to refuse that —
one identity with two payloads has no defined meaning.

Evidence, from `snapshot.json.pre-primary-repair-1789681779` (1136 rows):

- **5** duplicated ids, not "every AI-sourced memory". Sources across the whole
  file: 201 `ai`, 935 `auto` — no 1:1 pairing exists.
- The five: `mem_596cf755cfbf`, `mem_d8486c1c0ee0`, `mem_ae38a9b2736d`,
  `mem_adf58a52df9a` (missing from the brief's list), `mem_d42816c8963c`.
- Each pair: identical `content` and `created_at`, different `entity_id`;
  the `ai` row carries `frame=1`, a real `hip_file` and 4–7 tags, the `auto` row
  carries `frame=None`, `hip_file=""`, `tags=[]`.
- All five are the canonical Solaris recipe/template chain (v1 → v2 → v3).

### 4. Already fixed — this diagnosis confirms a closed incident

The defect is the 2026-09-15 store outage, diagnosed and repaired on 2026-09-17
(`ae34ed96 fix(memory): the duplicate deposit that degraded the store, and the
guards around it (#107)`; dossier at `harness/notes/store-incident-2026-09-17/`).

- **Producer fixed at source:** `session/tracker.py:515` now passes
  `deposit_to_moneta=False`, suppressing the second deposit.
- **Backstop added:** `MemoryStore.add` (`memory/store.py:697`, guard at `:730-790`) routes a
  same-id-different-payload write to `update()` instead of appending a conflicting
  line, counting it into `health()["overwrote_prior"]`.
- **Primary repaired:** `primary_repair` ran 2026-09-17 17:47, 1136 → 1131 rows,
  removing the 5 `auto` twins and keeping the `ai` rows — the disposition this
  handoff's guardrail asks for.
- **Auto-prune disarmed:** `moneta_store.py:792` now routes through
  `_maybe_auto_consolidate()`, opt-in and default OFF.
- **Running process is on the fixed code:** the fix files were written
  2026-09-17 18:04; the live Houdini started 2026-09-18 13:37.

Net: the live store is clean and the writer that poisoned it is closed. The
brief's OBSERVED tier described the pre-repair backup accurately as a snapshot of
damage, but overstated its scope ("every AI-sourced memory") by a factor of ~40.

### Still open — not this session's scope

Carried from `harness/notes/store-incident-2026-09-17/VERDICT.md`, re-checked
against the live seat today:

- **Mirror divergence, unresolved.** Moneta primary 1132 vs JSONL mirror 1136.
  The audit's 253 Moneta-only records and 4 mirror-only records (including the
  binding v4-recipe DECISION `mem_e2e9749cb3c3`) have no backfill run on record.
  `memory/backfill_from_moneta.py` now exists to do it; it has not been run here.
- **`cortex_root.usda` is stale** — 2026-09-17 16:30, i.e. pre-repair.
- **11 `memory.jsonl.degraded-load-*` quarantine copies** still resident in the
  store dir from the outage window.
- The two decisions this handoff reserves for the artist are untouched: which row
  is authoritative (the repair already kept `ai` — worth ratifying or reversing),
  and PDG timeout semantics on the library path.


---

*The original handoff prompt, verbatim:*

```
# SYNAPSE - memory dual-write: diagnose, then land the hython contract

Repo: C:\Users\User\SYNAPSE   Build pins: GUI 22.0.400 (running, SYNAPSE server live
on :9999 path /synapse), hython lane 22.0.417 (Python 3.13.10).

## Ground rules
- Single session. No subagent fan-out, no parallel runners. Solo dev on a
  subscription - one mission at a time.
- Do NOT rebuild tooling that already exists (see "Already on disk").
- PowerShell: use `-File` with a script, never `-Command`. `-Command` strips
  $-variables and will silently break every $env: assignment.
- Never read a large JSON artifact raw into context. Stream it through a
  filtering script and print only counts and a handful of examples. A prior
  session burned its window reading a memory snapshot whole. Don't repeat it.

## Already on disk - use, don't recreate
  tools/hy.ps1                  pinned hython launcher; $env:HY_BUILD overrides the
                                build, $env:HY_TIMEOUT the watchdog (exit 124 on hang)
  tools/hy_verbs.py             runtime + dispatch probe
  tools/hy_verbs_sweep.py       read-only verb sweep; $env:HY_OUT sets output path
  tools/hy_parity.py            GUI-vs-headless parity client (plain python, no license)
  harness/verify/hython_verbs.py  pure-python verifier (--check all|freshness|ok|
                                ui-bound|tops-defect|no-mutation, --freeze)
  tools/hy_verbs_baseline.json  frozen baseline, build 22.0.417
  .synapse/contracts/hython-verbs.yaml   green contract, 6 features, all passing

## Findings, tiered

PROBED (evidence on disk, 22.0.417 and 22.0.400, identical on both):
- 144 verbs register headless; 44 are read-only per `_READ_ONLY_COMMANDS`.
- 22 return ok, 14 needs_params, 7 headless_fail, 1 empty-stage error.
- run_on_main fast path 2 fires on the main thread; hdefereval is never imported.
- Six tops_* verbs fail on a bare `import hdefereval` in the handler body:
  handlers_tops/diagnostics.py:248 and handlers_tops/work_items.py:40.
  The shared marshal is handlers_tops/_common.py, wrapping
  hdefereval.executeInMainThreadWithResult - the pre-migration pattern that
  main_thread.py replaced. Those six have no timeout, no stall detector, no
  C4 zombie-kill, no C6 telemetry. RECORDED, NOT FIXED.

OBSERVED (read from .synapse/backups/moneta-2026-09-17-preprune/snapshot.json,
one day old, not the live store):
- memory_lifecycle._records raises "Source memory has duplicate identities" when
  inner payload `id` values collide. This breaks recall, search and context in
  the live GUI session while they pass headless.
- Every AI-sourced memory is written TWICE: same inner `mem_*` id, different
  `entity_id`. One row has source="ai" with frame, hip_file and tags populated;
  the twin has source="auto" with frame null, hip_file "" and tags stripped.
  Confirmed pairs: mem_596cf755cfbf, mem_d8486c1c0ee0, mem_ae38a9b2736d,
  mem_d42816c8963c.
- The pairs predate the 2026-09-17 prune, so this is an ingestion-time
  double-write, not prune damage.

V0 (unproven, do not build on):
- Which writer emits the source="auto" row. Prime suspect is the session or
  observation path - host/memory_loop.observe_operation is imported lazily
  inside server/handlers.py handle(). Verify; do not assume.
- Location of the LIVE store. ~/.synapse/memory.jsonl is 0 bytes from February,
  a legacy stub. The live backend takes the `_iter_memories` strict path and is
  USD (cortex_root.usda / cortex_protected.usda). Not under C:\Users\User\Moneta.
  Find it before reasoning about live data.

## Tasks, in order

1. Locate the live memory store. Report the path, row count, and how many inner
   ids are duplicated. Read-only.

2. Find the second writer. Search for where source="auto" is set on a memory
   record. Name the file:line and the call path that reaches it. Read-only.

3. Report back before writing anything. State whether the duplication is a
   defect in the writer, intended dual-recording that _records is too strict
   about, or something else. Give the evidence for whichever you claim.

## Guardrails
- Do NOT deduplicate the store. The source="auto" twin is LOSSY, not an
  identical copy - a naive dedup destroys the tagged, frame-anchored versions of
  the canonical Solaris recipes. Any repair keeps the "ai" row.
- Do NOT edit python/synapse/server/main_thread.py - C4/F3/H3/C6 incident surface.
- Do NOT edit python/synapse/server/handlers_tops/** - recorded defect, not this
  session's scope.
- Any write to the memory store requires a fresh backup alongside
  .synapse/backups/ first, and my explicit go-ahead.

## Decisions that are mine, not yours - surface, don't make
- Whether the "ai" or "auto" row is authoritative.
- PDG timeout semantics on the library path. _common.py's timeout is enforced at
  the WebSocket layer via _SLOW_COMMANDS, which does not exist when handlers are
  called in-process, so headless PDG currently has NO timeout from any source and
  tools/hy.ps1's watchdog is the only backstop. Pick too short and legitimate
  graph-context init dies; too long and a hung cook eats the budget.

## Also do
- `git add -f .synapse/contracts/hython-verbs.yaml` (contracts dir is ignored at
  repo level), plus tools/ and harness/verify/hython_verbs.py. Commit them.
- Re-run `python harness/verify/hython_verbs.py --check all` and confirm exit 0
  before committing. If freshness fails, re-run the sweep via
  `powershell.exe -File tools\hy.ps1 tools\hy_verbs_sweep.py` first.

## Done when
Live store located, second writer named with file:line, root cause stated with
evidence, contract committed and green. No store mutation, no product-code edits.
```
