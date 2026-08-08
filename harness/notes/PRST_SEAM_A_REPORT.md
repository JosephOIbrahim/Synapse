# PRST — seam A report, addressed to R-CI0-1

**Nothing in this report was acted on. Durability posture is untouched — not one line.**
R-CI0-1 is a pending human ruling under Constitution Article I.

Date 2026-08-08 · leg PRST · branch `finish/network-persistence` @ `1f18ab46` ·
Houdini NOT running this session (verified: no `houdini.exe`/`hython.exe`)

---

## The headline, and it is operational before it is technical

> **355 real deposits — including both of the only two DECISION records — are sitting
> readable-but-unopenable at**
> `C:\Users\User\AppData\Local\Temp\houdini_temp\untitled\.synapse\.moneta\snapshot.json`
> **That path is inside `AppData\Local\Temp`. It is one temp sweep from gone, and it is
> currently the only copy.**

Nothing in this leg moved, copied, or opened it. Deciding whether to copy it somewhere
durable is a human call and it is time-sensitive — it should happen before any fix work
starts, not after.

**There is a recovery path, and it is cheap.** The crucible copied the snapshot to a
scratch dir and opened the copy: under `HashEmbedder` (dim 256) it opens cleanly with all
355 memories and both DECISIONs intact. The bytes are fine. Only the *opener* is wrong.

---

## Verdict: FAULTY — but not for the reason R-CI0-1 is about

R-CI0-1 asks a **write-path** question (does deposit #1 fsync). The fault that has actually
been costing Joe his memory is on the **load path**, and it fires on perfectly clean exits.

**The production Moneta store has failed to open on every session since 2026-08-05
13:35:47 — eleven consecutive times, through 2026-08-07 11:23:28**, always with:

```
ValueError: embedding dim mismatch: expected 384, got 256
```

Each failure silently served an **empty JSONL store** instead. The most recent occurrence is
inside a live Houdini panel session, not a test: hwebserver up at 11:22:25, store fails at
11:23:28, session proceeds on a 3-record JSONL store and runs `claude_worker` turns against
it.

- Producer: `grep -n "houdini_temp.untitled" ~/.synapse/logs/synapse.log | grep "failed to initialize"` → 12 hits
- Anchors: `~/.synapse/logs/synapse.log:21968, :24186, :24390, :25601, :25907, :26120, :27612, :27640, :28139, :31064, :31097`
- Corroborated on disk: snapshot froze 2026-08-05 13:24:58 at 355 rows / vector dim 256, while `memory.jsonl` kept being written to 2026-08-07 11:06.

**Mechanism** (VERIFIED-STATIC): `from_storage_dir` sets Moneta's `embedding_dim` from
whichever embedder resolves *in this process* and never reconciles it against the vectors
already persisted; hydrate rebuilds the index and the dimension check raises.
`moneta_store.py:243-261`, `:194-196` (the re-embed intent, PARKED),
`moneta/vector_index.py:110-113` (the raise).

**Why it changed underneath him** (VERIFIED-RUNTIME): the seat logged
`moneta (hash-ngram-v1-d256-n1_3)` from 2026-08-04 08:04 to 2026-08-05 12:59, then
`moneta (minilm-l6-v2-d384)` from 2026-08-05 13:40 onward. The 256-dim snapshot was written
by the former; every later open is attempted by the latter.

---

## The correction that reorders everything

The seam-A verdict originally claimed the load-path defect was what costs Joe his memory.
**The crucible refuted that**, and the refutation matters:

The record Joe actually asked SYNAPSE to remember — note
`RECIPE: "Create a Solaris Network" (verified working result)`, created 2026-08-07T15:06:37Z,
one second after the `synapse_add_memory` call at `~/.synapse/logs/synapse.log:31087` — **is
on disk, readable today, and was lost by nothing.** It is unreachable because it is a
**NOTE**, and recall reads **DECISION only** (`tracker.py:558` → `store.py:1200-1202`).

The live JSONL store holds 3 records and **zero decisions**, so `synapse_recall` returns
`found=False` for every query on Joe's seat right now — no crash, no restart required.

**Joe's reported symptom is reached at the KEYING seam before seam A is ever exercised.**
Priority order for ruling: **(1) DECISION-only keying, (2) the load-path defect, (3) R-CI0-1.**

---

## R-CI0-1 itself — two facts the ruling note does not yet carry

**(i) Option A is not a guarantee. It is an artefact of the monotonic clock epoch.**
`_last_save = 0.0` (`moneta_store.py:205`) against `_save_interval = 30.0` (`:206`) makes
deposit #1 force-save only because `time.monotonic()` at process start is large — measured
**100701.77** on this host, i.e. system uptime. **On a process launched within 30 s of boot,
option A silently degrades into option B** and deposit #1 is not saved either.

**(ii) The observed loss today is deposit #2, not deposit #1.** Reproduced through the real
handlers: two `handle_memory_decide` calls + one `handle_memory_search` + `os._exit(0)` left
`snapshot rows=1` — deposit #2 never reached disk. The byte-identical sequence with
`sys.exit(0)` left `rows=2`, no WAL, `count=2`, `recall found=True`. Shutdown shape is the
single isolated variable.

So: **choosing B would make the already-observed loss strictly larger. Choosing A leaves it
where it is.** Neither closes the load-path fault.

Pinned by `tests/test_prst_network_persistence.py::test_second_deposit_of_a_session_survives_abrupt_restart` (RED — a finding, Law 7).

---

## Three further faults found, none acted on

**WAL poison (permanent, self-inflicted).** `MonetaBackedStore.search()` writes SYNAPSE
string ids (`mem_…`) into Moneta's WAL via `signal_attention` (`moneta_store.py:494-495`).
The next cold start calls `UUID(d['entity_id'])` unguarded (`moneta/durability.py:170`) and
raises; nothing self-heals; deleting `wal.log` by hand recovers the store intact. Armed by
`synapse_search` and `synapse_knowledge_lookup` — ordinary use. Conditional on a **non-clean**
exit only, because a clean `save()` unlinks the WAL first — which is exactly why it has never
been caught.
Pinned by `::test_store_still_opens_after_a_search_then_abrupt_restart` (RED).

> **Stale contract worth fixing whenever this is ruled:** docstrings at
> `moneta_store.py:176-180`, `:265-270`, `:302` still assert the WAL is inert because
> "SYNAPSE never calls `signal_attention`" — line 495 of the same file calls it on every
> text search. That stale sentence is why nobody looked.

**Correction to the seam map:** `synapse_recall` does **not** poison the WAL — it never
touches the vector path. Aim any WAL fix at the **search** path.

**Reload leaks the URI lock.** `reset_synapse_memory` calls `save()` but never `close()`, so
the in-process "restart SYNAPSE" path downgrades to an empty JSONL store with no crash at
all. It has fired in production once: `MonetaResourceLockedError` at
`~/.synapse/logs/synapse.log:21749`.

**The store lives at the unsaved-scene address.** `$HOUDINI_TEMP_DIR/untitled` — so it will
move the first time Joe saves the hip. A fifth, crash-free route to "nothing recalled".

---

## The design choice that turned four defects into one invisible symptom

`_make_store` swallows **any** construction failure and returns an empty `MemoryStore`
(`store.py:906-911` → `:967`) while the panel keeps accepting "remember this" and keeps
answering recalls — from a different, empty backend. The only signal is one ERROR line in a
log file nobody reads.

And the fallback is **strictly less durable than the path it replaces**: deposit then
`os._exit(0)` under jsonl leaves no `memory.jsonl` on disk at all (2 s buffered flusher, no
first-deposit force-save), where moneta at least force-saves deposit #1. It also moves the
operator onto the backend this leg proved order-unstable across processes — so seam A does
not merely lose records, it **strands the operator on the non-deterministic recall backend**.

The one guard built for this — `_quarantine_if_corrupt` (`:313-349`) — validates only that
`snapshot.json` has eight required keys. The production snapshot passes that check
perfectly. The fault is dimensional, not structural, so the guard is blind by construction,
and equally blind to `wal.log`.

---

## For ruling (all human, none actioned)

1. **Copy the 355-deposit snapshot somewhere durable — today.** Temp path, single copy.
2. **R-CI0-1 A vs B**, now knowing (i) A is an accident of the clock epoch and (ii) the
   observed loss is deposit #2. B strictly widens it.
3. **The load-path defect.** Three SYNAPSE-local remedies, none touching fsync posture:
   (a) persist embedder id/dim beside the snapshot and refuse-or-re-embed on mismatch;
   (b) **pin the embedder for a store once written** — smallest, and demonstrated sufficient
   to recover all 355 rows; (c) extend `_quarantine_if_corrupt` from "is the JSON well-formed"
   to "can this store actually be opened".
4. **Should a failed backend be allowed to serve silently at all?** Keep the silent fallback,
   surface it in the panel, or make an unservable requested backend a hard startup error.
   This posture question is what converted four defects into one symptom.
5. **WAL poison — aim it, don't spray it.** (a) stop sending non-UUID keys at
   `moneta_store.py:494` (SYNAPSE-local, smallest); (b) harden `wal_read` upstream in Moneta
   (separate release train); (c) extend quarantine to `wal.log`. Choice decides ownership.

## Residual unknown, named so it is not assumed closed

**Does Python's `atexit` actually fire on a Houdini 22 shutdown?** Every "clean exit
persists" green in this leg came from `sys.exit(0)` in a bare interpreter; Houdini was not
running. The experiment: deposit through hython, quit once via `hou.exit()` and once by
closing the window, check `snapshot.json` mtime each time. **If atexit does not run, the
graceful column collapses into the abrupt one and the 30 s window applies to every deposit,
not just #2..n.** This does not change the FAULTY verdict — the load-path fault fires on
clean exits already — it only bounds how much worse it gets.

---

**Method / safety.** The operator's production store was **READ ONLY** — `os.stat`,
`os.listdir`, `json.load`. No `MonetaBackedStore` was ever constructed against it,
deliberately: doing so would take the URI lock and, via the atexit close at
`moneta_store.py:309-310`, rewrite `snapshot.json`. Every mutating probe ran in
`tempfile.mkdtemp` dirs. The one experiment run against operator bytes was on a **copy**.
