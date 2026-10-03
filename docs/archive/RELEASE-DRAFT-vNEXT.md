# RELEASE DRAFT — vNEXT

> Draft only. **Proposed: `5.57.0`** — minor. `VERSION` reads `5.56.0` and stays
> that way until the `bump` word; nothing here edits a version surface.
>
> **Why 5.57.0 and not 5.56.0:** `v5.56.0` was tagged and pushed from another
> session while this work was in flight. An earlier revision of this draft
> proposed 5.56.0; that number is taken. See *What 5.56.0 already shipped*.

---

## Headline

**The memory substrate stopped having two owners.**

`get_synapse_memory()` was an unlocked check-then-create. Two threads entering
together built two `SynapseMemory` objects; one won the module global and the
other was orphaned **while still holding a Moneta handle on the same storage
dir**. Measured on HEAD, unamplified — no injected sleep, 3/3 runs: **8
barrier-synchronised threads produced 8 distinct objects, 7 orphaned.**

Under `SYNAPSE_MEMORY_BACKEND=moneta` the process ended split 7 JSONL / 1
Moneta, with the JSONL loser owning the global and the Moneta object that won
the URI lock orphaned *and* atexit-pinned — **Moneta unrecoverable for the rest
of the process.** Separately: `reset_synapse_memory()` called `save()` but never
`close()`, so the next accessor call deterministically downgraded
`MonetaBackedStore` → `MemoryStore` with `init failed: MonetaResourceLockedError`.

`ledger.py` had been doing this correctly, under a lock, 1200 lines away in the
same package.

---

## What ships in 5.57.0

### Handle law — `python/synapse/memory/`

- `get_synapse_memory()` is lock-guarded; the double-checked path is pinned by test.
- `reset_synapse_memory()` releases the handle instead of leaking it.
- **Exactly one new module-global: `_GLOBAL_LOCK = threading.RLock()`** — a lock,
  not a store. No new store authority was created; that was the point.
- `MonetaConfig.ephemeral()` multi-store usage still works — a process-global
  scalar singleton would have forbidden it, and several tests depend on it.
- 3 files, +507/−9, 10 new tests.

Its adversarial pass authored **8 independent mutations** rather than trusting
the builder's own claim; all 8 turned red. A separate check confirmed the diff
adds exactly one module-global and that it is a lock.

### Verification harness — `harness/memory/`

Kept because it is reusable, not because it shipped a feature: a live invariant
sweep over in-flight worktrees, a merge-base supply packet, per-role briefing
digests, and **`AGENTS.md`** — agent conduct law for this repo.

---

## What 5.56.0 already shipped

Recorded so this release does not double-claim it. From another session, already
tagged and on origin:

- **`MemoryPort` bound to live Moneta**, manual evolver retired. `synapse_evolve_memory`
  is gone from the registered tool surface — **129 → 128 MCP tools**. The
  ratified §4 parameter names were preserved, so `tests/test_loop_contracts.py`
  needed no change.
- **Deterministic goal planner + durable checkpoints** (`agent/`).
- **LOOP rung blockers corrected against verified substrate truth** — every
  substrate clone-and-import checked, each naming the SHA inspected. SALUS is
  recorded as **"absent-for-purpose"**: it imports and self-verifies 5/5, but its
  public surface is a memory wake-predicate engine, not a path-policy evaluator.
  *Installing more does not fix it.* That is a scope mismatch, and it is a
  different fact from a missing install.

---

## Not shipping — the PG-DRM kernel

Held for two reasons, and the second is the serious one.

**Its own crucible found two defects** via an independent 26-mutation harness:
a surviving mutation (deleting the `str` guard leaves the suite green, so a task
context of `'shot_A'` silently becomes `frozenset({'A','_','h','o','s','t'})`),
and a verdict that changes on the second call (`evaluate()` with a generator
returns `ALLOW` then `DROP`, because the exhausted generator becomes an empty
task context).

**Then its premise was refuted.** The 5.56.0 `MemoryPort` states the law
directly: *"No 4th decay point. Utility is READ off the Moneta row. Decay is
evaluated at exactly three places inside Moneta over one pure function.
Recomputing `e^(-λt)` here would be a second authority for the same number."*

The kernel computes `e^(-λt)` itself — **the same defect class this very release
removes from the store side.** Correct arithmetic is not the objection; a second
authority for one fact is.

It also settles a question the submitted blueprint got backwards. Moneta's real
law is `U_now = max(protected_floor, U_last * exp(-λΔt))`, so `protected_floor`
is a floor that **keeps an entry alive** — which makes *"drop when utility <
protected_floor" unreachable by construction*. The real knobs are `utility_floor`
and token contamination.

A disposition is open on whether the kernel has a remaining reason to exist now
that `MemoryPort` filters at the seam. An accurate obituary is an acceptable
outcome.

---

## Known issues

Both pre-existing reds were bisected to an introducing commit rather than
written off. One of the two has since been fixed.

| Test | Introduced by | Nature |
|---|---|---|
| ~~`test_every_source_env_read_is_documented`~~ | ~~`454fbeee`~~ | **FIXED in 5.56.0** — the `ports.py` rewrite documented `SYNAPSE_LOOP_LEDGER_DIR`. Verified green at `129598bb`. |
| `test_backup_is_taken_and_source_intact` | **`e8b691de`** (W3-STORE dual-write armed) | **Genuine logic failure** — duplicate-append via the `_jsonl_net` dual-write sink: 7 → 14 lines where the parent gives 7 → 7. |

The second sits in a backup path and the test it fails is literally *"backup is
taken and source intact."* **Not fixed here.** Whether it blocks the tag is a
human call and should be made deliberately, not by omission.

**New, and flagged rather than asserted:** `python/synapse/memory/consolidation.py`
no longer contains `approval_token`. An audit during this cycle found that token
was **not** a human-consent gate but a **plan-binding CAS nonce** — the only
thing preventing a stale consolidation plan from mutating a store that had moved
underneath it. Its removal may well be deliberate; it is recorded because the
finding was live when the change landed.

The `mcp` `list_tools` collection error carried in earlier notes **does not
reproduce on this host** — zero collection errors. CI behaviour is unverified
from here and is not claimed either way.

---

## Verification

- Merge-base floor at `bb348abe`, main tree: `2 failed, 6773 passed, 180 skipped`
  (`collected 6952 items / 3 skipped`).
- Merged at `c3b9d1fc` (pre-rebase): `2 failed, 6783 passed, 180 skipped` —
  **identical nodeid set, +10 passed** = exactly the 10 new tests. No new red.
- **Rebased head `129598bb`, pushed: `1 failed, 6801 passed, 180 skipped` in 218.70s.**
  The failing nodeid set is `{test_backup_is_taken_and_source_intact}` — a
  strict **subset** of the floor's two. No new red, and one red **disappeared**:
  `test_every_source_env_read_is_documented` now passes, because the 5.56.0
  `ports.py` rewrite documented `SYNAPSE_LOOP_LEDGER_DIR`. Passed moved
  6773 -> 6801 (+28: 10 from the handle-law tests, 18 from the 5.56.0 commits).
  The second attribution run at `c179767b` was **not needed** — it is only
  required when a NEW nodeid appears, and none did.
- **Comparison rule: nodeid SETS, not failure counts.** A third failing nodeid
  is a new red someone owns.
- **Known systematic bias:** a *sibling* worktree runs exactly −2 passed /
  +2 skipped versus a main-tree floor at the same commit — `_find_real_corpus()`
  cannot reach the gitignored corpus outside the main tree. Not a regression.
- 22 live invariant sweeps across the build, all CLEAR, zero breaches. Master
  never moved during the work; no worktree ever wrote into the repo root.
- The push was **refused twice before it succeeded**: first by the Gate C
  pre-push hook (which is deliberately not a deny rule, because deny rules match
  a command FORM and are bypassed by `git -C <path> push`), then by a stale-ref
  rejection — origin had advanced three commits and carried a tag. Rebased with
  `--autostash`, re-verified, **never forced**. `c179767b..129598bb` is on origin.

---

## Release ritual — the parts that are yours

Per `harness/notes/h22/OPERATORS-CARD-release-ritual.md`, section B is hands-on
and cannot be completed by an agent:

**g1** clean install · **g5** Houdini lifecycle · **g6** core smoke · **g9**
rollback · **Ctrl+Z demo** · **drop.json** (human-only by recorded precedent)

then, one word each, in order: **bump** → **verify** → **tag**.

Preflight state: all six version surfaces CONFORM at `5.56.0`
(`scripts/sync_version.py --check` → PASS). The bump to `5.57.0` is yours.
