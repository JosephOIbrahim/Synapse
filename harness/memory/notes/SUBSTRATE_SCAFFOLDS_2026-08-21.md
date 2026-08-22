# SUBSTRATE SCAFFOLDS — MEMORY board rung M3

> **Papers only.** This document changes no shipped code, no test, and nothing
> under `.synapse/contracts/`. It designs how SYNAPSE connects to four
> substrates — one present and contended, three absent — without lying about
> any of them.
>
> Base: `master` @ `bb348abe`, SYNAPSE v5.55.0, Houdini 22.0.400.
> Authored 2026-08-21 (sprint clock; the host clock rolled to 2026-08-22 mid-run).
> Author: ENVOY, running as a **fallback `general-purpose` base agent** — the
> custom `substrate-envoy` type was not in this session's agent registry.
>
> **Label convention, applied to every claim below:**
> **VERIFIED** — I read the file, ran the command, or read the tool response, and
> the citation is a `path:line` or a command with its real output.
> **INFERENCE** — spec-grounded design only. No substrate was touched. Nothing
> here is a measurement of an absent substrate; absent substrates cannot be measured.
>
> Prior evidence this document **extends and does not re-derive**:
> `harness/memory/notes/AUDIT_2026-08-21.md` (M0) and
> `harness/memory/notes/BLUEPRINT_ADJUDICATION.md`.

---

## 0 · The four shapes, and the two laws they share

`AGENTS.md` §2 fixes the taxonomy. Restated here only to name which substrate is which.

| Substrate | Shape | Live? | Failure mode | Degradation |
|---|---|---|---|---|
| **Moneta** | present-contended | **LIVE** | **ownership**, not absence | one handle per storage URI; the loser is *closed*, never orphaned |
| **Hanish** | write-side | absent | cannot settle | durable local **outbox** + `UNAVAILABLE`; drain on install |
| **Octavius** | read-side | absent | cannot sanitize | **narrow** to the local stage behind a capability that cannot be ignored |
| **SALUS** | gate-side | absent | cannot evaluate | **fail closed** — an unevaluable path is a blocked path |

### Law A — a degradation nobody can measure is indistinguishable from a bug

Every section below names **one number** a hostile reader can compute *today*, its
value *after* the substrate lands, and **what a fabricated resolution would look
like**. A degradation contract without that third column is a promise, not a design.

### Law B — measured zero is not unmeasured zero

`0` means *"I counted, and the count was zero."* A thing not counted renders
`UNKNOWN` / `null` / `UNMEASURED` — never `0`, never `False`.

This is not aspirational; it is already the shipped pattern.
`python/synapse/panel/health_strip.py:288-322` returns the sentinel `UNMEASURED`
when the store module will not import, and keeps `moneta_live: Optional[bool]` at
`None` rather than `False` when the fact is unreadable (**VERIFIED**,
`health_strip.py:288-322`). Every counter proposed in this document inherits that
three-state discipline: a value, a measured zero, or `UNMEASURED`.

---

## 1 · MONETA — present-contended (ownership, not absence)

### 1.1 The shape

Moneta is **live** (`harness/memory/STATE.json` → `substrate_presence.moneta`,
**VERIFIED**). Nothing here degrades for absence. Everything here degrades for
**contention**: a live substrate with two owners is less safe than an absent one,
because the corruption is silent (`AGENTS.md` §3).

The contention is measured, not theorised:

- `python/synapse/memory/store.py:1519-1524` is an **unlocked check-then-create**
  (`if _global_synapse is None: _global_synapse = SynapseMemory()`) — **VERIFIED**
  on master.
- `python/synapse/memory/ledger.py:415-437` does the same job **correctly**: under
  `_MONETA_LOCK` (`ledger.py:322`), keyed by `os.path.abspath(ledger_dir())`, and
  it **closes the previous handle before rebuilding** (`ledger.py:424-431`) —
  **VERIFIED**.
- The M1 cartographer reproduced the defect with **no injected delay**: 8
  barrier-synchronised callers produced **8 distinct `SynapseMemory` objects, 3/3
  runs**; under `SYNAPSE_MEMORY_BACKEND=moneta` the split was **7 JSONL / 1 Moneta**,
  the JSONL loser won the module global, and the single `MonetaBackedStore` holding
  the process URI lock was orphaned *and* atexit-pinned
  (`harness/memory/bus/memory_m1_cartographer.json` — **VERIFIED as a read of the
  receipt**; I did **not** re-run the probe myself).

So the Moneta degradation is not "Moneta is missing." It is: **Moneta was live,
one caller lost the race, and the process silently ran on JSONL for the rest of its
life while believing it had Moneta.** That is a fabricated SUCCESS wearing a backend
name.

### 1.2 The disciplined read — described so it is enforced, not reinvented

`python/synapse/panel/health_strip.py:288-322` is the reference implementation
(**VERIFIED**; M0 §D independently graded it "reference-clean"). Its shape is five
rules. Name them, so the next panel surface copies the pattern instead of inventing
a sixth authority:

| # | Rule | Where it shows in the reference | Why it exists |
|---|---|---|---|
| **R1** | **Peek, never construct.** Read the module global via `getattr(_store, "_global_synapse", None)`. Never call `get_synapse_memory()`. | `health_strip.py:311` | Calling the accessor *builds* the store — "the very act that can fall back / block" (its own docstring, `:288-297`). An observer that constructs is a participant. |
| **R2** | **Import behind a guard; unimportable renders `UNMEASURED`.** | `health_strip.py:297-300` | An import failure is not "no Moneta". It is "I could not look." |
| **R3** | **Every derived fact is `Optional[bool]` and stays `None` when unreadable.** | `health_strip.py:308, 316-320` | Law B. `False` is a claim; `None` is an admission. |
| **R4** | **Acquire no lock on the read path.** | no lock anywhere in `_gather_memory` | A health read that can block is a freeze surface. This repo has three shipped freeze classes already. |
| **R5** | **Write nothing. Reset nothing. Close nothing.** | the whole function is read-only | The panel observes; it does not own. |

**One honest divergence, recorded rather than smoothed.** `AGENTS.md` §3.3 says the
panel "reads memory state over the WebSocket observation channel, *or* peeks an
existing singleton without building one." `health_strip._gather_memory` does the
**second** form — an in-process `getattr` peek, not a WebSocket read (**VERIFIED**,
`health_strip.py:297-322`). Both forms are permitted by the law as written. The
pattern to enforce is *peek-or-observe, never construct* — not "always WebSocket."

**The unresolved sibling.** `python/synapse/panel/shot_login.py:34-44` imports
`ensure_scene_structure` — a **writer** — at module scope (**VERIFIED**). Static
import is not a live call; M0 recorded this as a *candidate* violation needing a
thread-ownership probe, and the probe has not run (bridge unreachable). It stays
**UNKNOWN**. This document does not upgrade it to a violation.

### 1.3 Degraded behaviour (the contract)

| Condition | Required behaviour |
|---|---|
| Moneta reachable, handle held | Serve from the single handle for that URI. |
| Two callers race the accessor | Exactly one handle is published; the **loser is closed**, not left reachable. Closing — not `save()` — is what drops the `moneta-file://` URI lock. |
| A handle refuses to close | Log at **ERROR** (not warning) and clear the global anyway, so a wedged handle cannot own the accessor for the life of the process. |
| Headless / Moneta unimportable | `UNMEASURED`. Never `moneta_live: False`. |
| Backend silently downgraded to JSONL | This **is** the failure, and it must be visible in the census — never inferred later from behaviour. |

The M1 forge branch `mem/m1-handle-law` implements exactly this shape: double-checked
locking with an `RLock`, a post-construction re-check that closes the superseded
handle, and `_close_memory_quietly()` which distinguishes `close()` (releases the URI
lock) from `save()` (does not) —
`C:/Users/User/synapse-m1-handle-wt/python/synapse/memory/store.py:1542-1624`,
**VERIFIED on the branch, NOT on master**.

### 1.4 Drain path

**Not applicable, and saying so is part of the design.** Moneta is present; there is
no backlog to drain. The equivalent of a drain is **release**:
`reset_synapse_memory()` must *close*, not merely `save()`, or the URI stays locked
and the next construction downgrades to JSONL for the rest of the process
(**VERIFIED** — the mechanism is documented in the branch's `_close_memory_quietly`
docstring, citing `moneta_store.py:377-378` atexit pinning and
`moneta_store.py:934-958` close).

### 1.5 OBSERVABLE

| | |
|---|---|
| **Name** | `distinct_handles_per_storage_uri`, plus the two-authority census |
| **Producer** | `synapse.memory.store.memory_handle_census()` — reports **both** authorities (`store._global_synapse` and `ledger._MONETA_STORE`) in one place, peeking exactly the way `health_strip.py:311` does, and reporting `live: False` rather than opening anything (`mem/m1-handle-law` @ `c3b9d1fc`, `store.py:1626-1662`, **VERIFIED on the branch**) |
| **Today (master)** | N barrier-synchronised `get_synapse_memory()` callers → **N distinct objects**; measured at **8/8, 3/3 runs**, backend split **7 JSONL / 1 Moneta** (cartographer receipt, **VERIFIED as a read receipt**) |
| **After resolution** | **1** distinct object for N callers under the same run shape; the census reports one live authority per URI with a non-null `storage_uri` and `backend` |
| **How a hostile reader measures it** | Spawn N threads on a `threading.Barrier`, call `get_synapse_memory()`, compute `len({id(o) for o in results})`. Independently: call `memory_handle_census()` and compare `project_memory.storage_uri` against `ledger_findings.storage_uri`. Neither measurement reads the fix's own assertion. |
| **A fabricated resolution looks like** | (a) The count drops to 1 because the test **serialised** the callers — a concurrency test with no barrier proves nothing. (b) The count drops to 1 because `SYNAPSE_MEMORY_BACKEND` was unset, so every path took the same JSONL branch and Moneta was never in play. (c) A census that **constructs** the handle it reports on — then `live` is always `True` and the observer manufactured its own answer. |

### 1.6 Ratification gate

- **`gate_m1_merge`** — *"OPEN — mem/m1-\* worktree merge is Joe's word"*
  (`harness/memory/STATE.json` → `human_gates`, verbatim). The fix exists on a branch
  and is not on master.
- **No contract amendment required.** `store.py` is not ratified text.

---

## 2 · HANISH — write-side (outbox, drain, prediction debt)

### 2.1 The shape, and what already exists

Write-side absence costs **latency, never truth** (`AGENTS.md` §2). SYNAPSE already
ships the honest half:

- `python/synapse/loop/ports.py:175-181` — `LedgerPort.settle()` returns
  `UNAVAILABLE` naming `substrate_presence.hanish=absent`. **VERIFIED.**
- `python/synapse/loop/recipe.py:73-77` — the turn verdict is `EXPOSED` **iff**
  settlement came back `UNAVAILABLE`; anything else falls to `UNRESOLVABLE`.
  **VERIFIED.**
- `tests/test_loop_contracts.py:193-198` pins it, including `payload is None`.
  **VERIFIED.**

What is **missing** is the other half: nothing is durably recorded *for* the
settlement that could not happen. Today the precommit line is written
(`ports.py:148-173` — a real `write` + `flush` + `os.fsync`, **VERIFIED**) and the
unsettled claim exists only as an absence. When Hanish lands there is a ledger of
predictions and **no queue of things owed**.

### 2.2 The outbox record format — a superset of what `settle()` will need

**INFERENCE.** The submitted blueprint's `deposit_settlement` signature is *not in
the tree*; only the adjudication's prose description of it survives
(`BLUEPRINT_ADJUDICATION.md:31-33`). The field list below is derived from what a
settlement must be able to *do*, not copied from the submitted spec.

Proposed location: `harness/loop/ledger/v0x_settlement_outbox.jsonl` — a sibling of
the precommit ledger, same append-only + `fsync` discipline as `ports.py:166-169`.

```json
{
  "schema": "loop/settlement-outbox/v1",
  "record_id": "9f1c...",
  "state": "EXPOSED",
  "turn_id": "v00-recipe-t3",
  "precommit_seq": 3,
  "ledger_file": "harness/loop/ledger/v00_precommits.jsonl",
  "ledger_file_id": "sha256:...",
  "claim_predicate": "...verbatim...",
  "probability": 0.0,
  "world_ref": "v0.0/precommit-order",
  "world_digest": "topo:ab12...",
  "authored_at_utc": "2026-08-21T14:02:11.481Z",
  "authored_monotonic_ns": 81234567890,
  "author": "v0.0-recipe",
  "observation": {
    "captured": true,
    "observed_at_utc": "2026-08-21T14:02:12.004Z",
    "channel": "ws-observation",
    "payload": { "prim_count": 41, "cook_result": "ok" }
  },
  "verdict": null,
  "protected_floor": 0.5,
  "drain": { "attempts": 0, "last_attempt_utc": null, "last_error": null,
             "hanish_receipt_id": null },
  "substrate_expected": { "name": "hanish", "min_version": "0.1.2" }
}
```

`state` ∈ `EXPOSED | DRAINED | STALE`. `verdict` ∈ `null | HIT | MISS | UNRESOLVABLE`
and is **only ever written by a drain**, never at author time.

**Why each field is a superset item and not padding:**

| Field | Does `settle()` need it? | Why it is in the record anyway |
|---|---|---|
| `turn_id` | **yes — and it is currently unrecoverable** | `LedgerPort.settle(turn_id)` is keyed on `turn_id` (`ports.py:175`), but the precommit line written at `ports.py:148-155` **contains no `turn_id` field** (**VERIFIED**: the keys are `event, claim_predicate, probability, world_ref, author, seq`). `recipe.py:61` embeds it as a *string prefix* of `claim_predicate`, so joining a settlement to its precommit today requires splitting a human-readable sentence on `": "`. **This is a real, present gap the outbox must close.** |
| `precommit_seq` + `ledger_file` + `ledger_file_id` | yes | `seq` is unique **per file** (`ports.py:183-195` scans exactly one file, **VERIFIED**), and `SYNAPSE_LOOP_LEDGER_DIR` can re-point the whole ledger (`ports.py:71`, **VERIFIED**). A bare `seq` is ambiguous across sessions. |
| `world_digest` | no | The one thing a settlement **cannot reconstruct after the fact**: what the world looked like when the claim was made. Without it, "has the world since changed?" is unanswerable and the drain has to guess. A drain that guesses is a fabricated verdict. |
| `record_id` | no | Idempotency key. A drain interrupted mid-flight must be re-runnable without double-settling. |
| `observation` | yes | Step 8 of THE LOOP emits the observed outcome on the WebSocket channel (`docs/THE_LOOP_v5.1.md:96`, **VERIFIED**). If it was never captured, `captured: false` — and that distinction *decides the drain verdict* (§2.3). |
| `verdict` | — | **Always `null` at author time.** SYNAPSE never writes `HIT`/`MISS` locally. Hanish adjudicates; SYNAPSE records. |
| `protected_floor` | yes | Step 9 writes the settlement deposit to Moneta "with protected_floor" (`docs/THE_LOOP_v5.1.md:97`, **VERIFIED**). The floor is decided at deposit time, not invented at drain time. |
| `drain` | no | Makes a failed drain *visible* instead of silently retried forever. |

**The superset claim, stated precisely:** every argument that
`deposit_settlement(turn_id, verdict, protected_floor)` will carry is derivable from
this record, **and** the record carries three things that call cannot carry —
`world_digest`, `record_id`, `observation.captured` — which are exactly the three
facts needed to decide whether a settlement is still legitimate. **INFERENCE.**

### 2.3 Drain path

Named in ratified text as `LedgerPort.process()` (`docs/THE_LOOP_v5.1.md:156`, V0.3
row: *"Drain points wired (LedgerPort.process())"*, **VERIFIED**).

```
Hanish install detected
   -> read outbox in (ledger_file_id, precommit_seq) order
   -> for each record with state == EXPOSED:
        submit {claim_predicate, probability, world_ref, observation} to Hanish
        Hanish adjudicates -> HIT | MISS | UNRESOLVABLE
        append a settlement line to the ledger   (NEVER rewrite the precommit line)
        write the Moneta deposit with protected_floor
        mark record DRAINED, stamp hanish_receipt_id
   -> conservation check: drained + still_exposed + stale == total
```

**The record whose world has since changed.** Three cases, and only one is a drop:

1. **Observation captured, world since moved → drain normally.** A forecast settles
   against the observation taken at the time, not against today's scene. A prediction
   about a past world does not become wrong because the world moved on. `world_digest`
   is recorded for audit, not as a veto.
2. **No observation captured** (WebSocket timeout, host died, session ended) → drain
   as **`UNRESOLVABLE`**, **never `MISS`**. This is ratified law, not a preference:
   Hanish's stated constraints include *"No MISS from absence"*
   (`docs/THE_LOOP_v5.1.md:61`, **VERIFIED**). An unobserved outcome is missing
   evidence, not a failed prediction.
3. **`world_ref` names a scene that no longer exists AND no observation was captured**
   → mark `state: STALE`, drain as `UNRESOLVABLE` with `reason: world_gone`.
   **Never deleted.** A record removed from the outbox is a prediction the system no
   longer owes — the write-side equivalent of a fabricated SUCCESS.

Two further Hanish constraints bind the drain and are quoted rather than paraphrased:
*"Append-only · Adjudication before evidence · No rescoring retries"*
(`docs/THE_LOOP_v5.1.md:61`, **VERIFIED**). A drain therefore never re-adjudicates a
`DRAINED` record, and a failed drain increments `drain.attempts` without touching
`verdict`.

### 2.4 OBSERVABLE — prediction debt, and it must **fall**

| | |
|---|---|
| **Name** | `prediction_debt` = count of outbox records with `state == "EXPOSED"` |
| **Already ratified as an observable** | `docs/THE_LOOP_v5.1.md:156` — the V0.3 gate reads *"prediction debt visible in panel and falling over sessions"* (**VERIFIED**). This document does not invent the metric; it specifies how it is produced. |
| **Today** | **Structurally monotonic non-decreasing**: every turn adds one unsettleable claim and nothing removes one. That is the degradation, as a number rather than an adjective. But the *current measured* value is **UNKNOWN, not 0** — the outbox does not exist, so the debt exists only as `EXPOSED` turn verdicts with no durable record to count. Law B: uncounted renders UNKNOWN. |
| **After Hanish lands** | Debt for all pre-install records falls to **0** after one drain; thereafter it tracks only in-flight turns and returns to 0 each drain cycle. **Falling, not merely finite.** |
| **How a hostile reader measures it** | Before: `jq -c 'select(.state=="EXPOSED")' outbox.jsonl \| wc -l`. After: the same command. Then the **conservation check** — `drained + exposed + stale == total`, and `settlement lines appended to the ledger == drained`. Two independent counts from two different files. |
| **A fabricated resolution looks like** | (a) Debt falls because records were **deleted** rather than drained — caught by conservation, since `total` shrinks. (b) Debt falls because unobserved records were settled `MISS` — caught by asserting the `MISS` count against records with `observation.captured == true`; a `MISS` on an uncaptured record violates *"No MISS from absence"*. (c) `deposit_settlement` returns `SUCCESS` while writing nothing — the exact failure the adjudication blocked (`BLUEPRINT_ADJUDICATION.md:33-38`); caught by asserting the ledger grew by exactly the drained count. |

**The test that must exist before anyone believes the drain** (design, not code): a
drain run where Hanish is stubbed to raise on the third record. Debt must fall by
exactly 2; `drain.attempts` on record 3 must be 1; `verdict` on record 3 must still be
`null`; and a re-run must settle record 3 **exactly once**. The mutation that proves
it bites: remove the `record_id` idempotency check and record 3 settles twice — the
assertion goes red.

### 2.5 Ratification gate

- **`gate_substrate_install`** — *"OPEN — Hanish / SALUS / Octavius installs; never
  assumed present"* (`STATE.json` → `human_gates`, verbatim).
- **`gate_v02_contract_amendment`** — `deposit_settlement` on the §4 surface. See
  `CONTRACT_AMENDMENT_v02.md`.
- **A non-obvious third gate: DOC-1 env conformance.** If the outbox introduces a
  `SYNAPSE_LOOP_OUTBOX_DIR` env read, it **must** ship with a row in the
  `### Environment Variables` section of `docs/studio/DEPLOYMENT.md` in the same
  commit. `tests/test_m3_env_conformance.py` scans production sources mechanically
  and fails in both directions (**VERIFIED**, its docstring lines 1-30). This is not
  hypothetical: one of the two merge-base reds is exactly that test failing on the
  **undocumented** `SYNAPSE_LOOP_LEDGER_DIR` read at `ports.py:71`, introduced by
  `454fbeee` (`STATE.json` → `floor_reds_provenance.red_1_env_conformance`,
  **VERIFIED as a read of the board**). Repeating it with the outbox would be the same
  bug twice.

---

## 3 · OCTAVIUS — read-side (narrow, with a capability a caller cannot ignore)

### 3.1 The shape

Read-side absence means a **true but smaller source still exists**: the local Houdini
stage. THE LOOP's own step-1 fallback says so — *"Fallback: local Houdini scene context
only"* (`docs/THE_LOOP_v5.1.md:89`, **VERIFIED**). The failure to avoid is not
returning less; it is returning less **while the payload looks exactly like the full
thing**.

Current behaviour is correct and must not regress:
`StagePort.compose_sanitized_stage` returns `UNAVAILABLE` naming Octavius and writes
**nothing** — no files, no ledger (`ports.py:206-212`, **VERIFIED**; pinned by
`tests/test_loop_contracts.py:141-161`, which snapshots every file size under
`harness/loop/` before and after, **VERIFIED**). That zero-side-effect property is a
ratified V0.0 goalpost (`.synapse/contracts/loop-v00.yaml:33-35`, **VERIFIED**) and
this design does not touch it.

### 3.2 Designing the flag so it **cannot** be consumed as sanitized

State the failure mode first, because it is the hard part of the charter:

> **A boolean in a dict is passively ignorable.** If the narrowed payload and the
> sanitized payload are the same type with the same field names, `payload["prims"]`
> reads identically in both worlds and `payload["sanitization"]` is a value nobody is
> obliged to look at. Documentation does not close that hole. A hostile reader's
> question — *"could a caller consume this believing it was sanitized?"* — is answered
> **yes** for any flag-only design.

Four layers, in order of strength. Layers 1 and 2 are the design; 3 and 4 make it
auditable.

**Layer 1 — the limit lives in the method name, not in a field.**
`compose_sanitized_stage` stays `UNAVAILABLE` for as long as Octavius is absent. The
narrowed read is a **different, differently-named method**:

```
StagePort.compose_local_stage_unsanitized(stage_identifier) -> PortResult
```

A caller cannot reach the narrowed view by accident, by a default, or by ignoring a
field. They have to type the word `unsanitized`. This is the single strongest property
in the design and it costs nothing at runtime.

**Layer 2 — the payload is a taint type, not a dict.**
The payload carries an `UnsanitizedStageView` whose content accessors **raise**
`UnsanitizedAccessError` until the caller has explicitly acknowledged what it is:

```
view.prims                      -> raises UnsanitizedAccessError
view.accept_unsanitized(reason="prompt assembly, local-only session")
view.prims                      -> returns the prims
view.provenance                 -> always readable, never gated
```

This converts *"the caller should check the flag"* into *"the caller physically cannot
read the data without acknowledging what it is."* The acknowledgement takes a `reason`
string, which lands in the provenance stamp — so every consumption site names itself in
the record, and `grep -rn "accept_unsanitized(" ` enumerates exactly who is trusting an
unsanitized stage.

**Layer 3 — provenance travels with the data, into whatever it produces.**
Every returned view carries, and every downstream artifact inherits:

```json
{ "sanitization": "none", "quine_filter": "NOT_RUN",
  "source": "local_stage", "octavius": "absent",
  "contributing_agents": 1,
  "accepted_by": ["prompt-assembly: local-only session"] }
```

Post-install the same keys carry `"sanitization": "octavius-quine-v<N>"`,
`"quine_filter": "RAN"`, and a `contributing_agents` count that can exceed 1. **Same
keys, different values** — so a diff of two sessions answers the question mechanically,
and a *stripped* stamp is itself detectable, because the key is absent rather than
falsely populated.

**Layer 4 — the negative test, with its mutation named.**
A test asserts that the narrowed view **cannot** reach prompt assembly without an
`accept_unsanitized` call on the path. The mutation that proves it bites: delete the
guard in the accessor, and the test goes red because unacknowledged prims became
readable. A test that only asserts `payload["sanitization"] == "none"` is a decoration —
it passes in exactly the world this design exists to prevent.

### 3.3 Degraded behaviour (the contract)

| Condition | Behaviour |
|---|---|
| Octavius absent, caller asks for the **sanitized** stage | `UNAVAILABLE`, reason names the absent substrate, **zero disk side effects**. Unchanged from today. |
| Octavius absent, caller explicitly asks for the **narrowed** stage | Local stage only, wrapped in the taint type, provenance stamped, `contributing_agents = 1`. Never presented as composed. |
| Caller reads content without acknowledging | `UnsanitizedAccessError`. Not a warning; not a log line. |
| The local stage itself is unreadable | `UNMEASURED` — **not** an empty stage. Law B. |
| Octavius present | `compose_sanitized_stage` serves; the narrowed method still exists and still taints, so the two paths never converge on one type. |

### 3.4 Drain path

**Not applicable — and saying so is part of the design.** Read-side absence has no
backlog: a narrowed read that already happened cannot be retroactively sanitized,
because the prompt it fed has already been sent. There is nothing to replay.

What *is* recoverable is the **audit**: the `accepted_by` list names every session that
consumed unsanitized context, so after Octavius lands a retrospective sweep can
enumerate which sessions ran unprotected. That is the read-side analogue of a drain,
and it is the honest limit of one.

### 3.5 OBSERVABLE

| | |
|---|---|
| **Name** | `unsanitized_reads_total` reported alongside `quine_filter_runs`, plus `contributing_agents` per view |
| **Today** | `quine_filter_runs = 0` — a **measured** zero, because the filter does not exist. And every view that can exist has `contributing_agents == 1`. Since only a composed Octavius view can exceed 1, **`contributing_agents == 1` on every view is the measurable narrowing.** |
| **What is NOT measurable today** | The *coverage ratio* — "how much of the composed stage are we missing." The denominator is Octavius, which is absent. Reporting a percentage would mean inventing the denominator. **UNKNOWN**, and it stays UNKNOWN until install. |
| **After resolution** | `quine_filter_runs > 0`; `stripped_metadata_keys` becomes a countable non-negative integer; `contributing_agents > 1` becomes reachable; `sanitization` flips from `"none"` to a versioned filter id. |
| **How a hostile reader measures it** | The panel health strip shows the pair `unsanitized_reads_total` / `quine_filter_runs` side by side. Independently, `grep -rn "accept_unsanitized(" ` enumerates every consumption site in the tree — a count derived from **source**, which a runtime counter cannot fake. |
| **The V0.3 gate's positive control** | V0.3 requires *"Zero USD metadata quine propagation"* (`docs/THE_LOOP_v5.1.md:156`, **VERIFIED**). The test must **plant its own known string** into `customData` and assert that exact string is absent from the composed stage. It must **not** assert a count copied out of the blueprint — repo precedent: a control pinned `161` because the document said 161; the true value was 171 (`AGENTS.md` §4, **VERIFIED**). |
| **A fabricated resolution looks like** | (a) `quine_filter_runs` incremented by a wrapper that calls no filter — caught by the planted-quine positive control, the only assertion here that touches real data. (b) `sanitization: "octavius-quine-v1"` stamped by SYNAPSE rather than returned by Octavius. The stamp must be **echoed from the substrate's response**, never authored locally. |

### 3.6 Ratification gate

- **`gate_substrate_install`** (Octavius) — verbatim above.
- **Adding `compose_local_stage_unsanitized` to `ports.py`** touches a file the
  ratified contract `owns` (`.synapse/contracts/loop-v00.yaml:12-17`, **VERIFIED**).
  It does **not** break the pinned parameter test — `tests/test_loop_contracts.py:58-74`
  asserts the parameters of exactly four named methods and is silent about additional
  methods (**VERIFIED**) — but the contract's feature text enumerates the surface, so
  the addition rides the amendment. See `CONTRACT_AMENDMENT_v02.md`.
- V0.3 is a **LOOP board** rung. This board designs; `loop-orchestrator` builds.

---

## 4 · SALUS — gate-side (fail closed, and the `GATE_POLICY([])` edge)

### 4.1 The shape

Gate-side absence fails closed: *"A safety evaluator that cannot evaluate must not
allow. An unevaluable path is a blocked path. 'Allow until the gate lands' is how a
gate becomes decorative"* (`AGENTS.md` §2, **VERIFIED**).

The port already does the right thing. `SafetyPort.evaluate_path` returns `UNAVAILABLE`
naming `substrate_presence.salus=absent` (`ports.py:89-94`, **VERIFIED**), pinned at
`tests/test_loop_contracts.py:178-182`, which asserts `"SALUS" in error_message`
(**VERIFIED**).

### 4.2 The finding this section exists to surface

**A closed gate that nobody asks is indistinguishable from no gate.**

`grep -rn "evaluate_path" --include=*.py .` returns **five** hits, and **every one is a
definition, a docstring, or a test** — `ports.py:5` (module docstring), `ports.py:89`
(the `def`), `ports.py:93` (its own message), `tests/test_loop_contracts.py:59` and
`:179` (**VERIFIED** — command run, output read). There is **no production call site.**
The same holds for `MemoryPort.query_and_filter` (`ports.py` + tests only,
**VERIFIED**). `StagePort.compose_sanitized_stage` has exactly one non-test caller:
`harness/loop/probes.py:260` (**VERIFIED**).

So the honest statement of SALUS's degradation today is **not** "the gate is closed."
It is: **the gate is unwired, and its closure has never been exercised by anything that
could otherwise have proceeded.** That distinction is the entire reason §4.5's
observable is a *call counter* and not a *status string*.

### 4.3 Degraded behaviour — the caller's contract, which is where fail-closed actually lives

`UNAVAILABLE` is only fail-closed if the caller treats it as a block, and the port
cannot enforce that. So the design puts the mapping in **one named, testable function**
rather than in every call site's judgement:

```
gate_decision(result: PortResult) -> "ALLOW" | "BLOCK"

  status == "SUCCESS" and payload is a dict and payload["allow"] is True   -> ALLOW
  everything else                                                          -> BLOCK
```

"Everything else" is load-bearing and must be spelled out, because the default branch
*is* the safety property:

| Input | Decision | Why |
|---|---|---|
| `UNAVAILABLE` (substrate absent) | **BLOCK** | absence never opens |
| `BLOCKED` | **BLOCK** | trivially |
| `SUCCESS` with `payload is None` | **BLOCK** | `PortResult.payload` defaults to `None` (`ports.py:34`, **VERIFIED**) — a SUCCESS with no payload is malformed, not permissive |
| `SUCCESS`, payload lacks `allow` | **BLOCK** | a missing key is missing evidence |
| `SUCCESS`, `payload["allow"]` truthy-but-not-`True` (`1`, `"yes"`) | **BLOCK** | `is True`, not truthiness. `True` is an `int` subclass; the ledger's own probability guard already refuses bools for exactly this reason (`ports.py:138`, **VERIFIED**) |
| an unrecognised future status | **BLOCK** | a new status must never inherit `ALLOW` by falling off the end of a chain |
| the call raised | **BLOCK** | an exception is not a decision |

The test that proves this bites: feed `PortResult("SUCCESS", None, None)` and assert
`BLOCK`. Mutation — change the guard to `payload.get("allow")` truthiness and the
malformed-payload case flips to `ALLOW`; the test goes red.

### 4.4 Resolving the recorded `GATE_POLICY([]) -> ALLOW` edge — in the DESIGN

**The edge, verified.** `mapper.GATE_POLICY` iterates the predicates; an empty iterable
never enters the loop, `seen_unevaluable` stays `False`, and the function returns
`ALLOW` by vacuous truth (`python/synapse/loop/mapper.py:27-36`, **VERIFIED**).

It is recorded, not hidden. The ratified contract says: *"Known edge (spec-only,
unreachable in V0.0): `GATE_POLICY([])` returns ALLOW by vacuous truth — carried to the
V0.1 live-gate leg to resolve, not a V0.0 blocker"* (`.synapse/contracts/loop-v00.yaml:27`,
**VERIFIED**).

It is **not pinned by any test**: `tests/test_loop_contracts.py:81-91` exercises all 27
combos of length **three**, and nothing asserts the empty case (**VERIFIED** — read the
test, and a grep for `GATE_POLICY([])` across `tests/` returns nothing).

**Why it contradicts the principle.** The docstring at `mapper.py:21-22` states the
law: *"unevaluable blocks: absent evidence is a block, never a pass-by-omission."* An
empty predicate list is the **maximal** case of absent evidence — not one unevaluable
predicate but zero evaluated ones — and it returns `ALLOW`.

Vacuous truth is the correct answer to the *proposition* "every element of P is True."
It is the wrong answer to the *safety question* "has this path been evaluated?"
**One function is being asked to be both an algebra and a verdict, and the two roles
disagree on the empty set.**

**Three resolutions, and the recommendation:**

| | Design | Cost / risk |
|---|---|---|
| **A** | Special-case: `GATE_POLICY([]) -> BLOCK`. | Breaks the `all()` algebra. A caller composing predicates from optional sources now gets `BLOCK` for "nothing to check" — the right *safety* answer but a surprising *function* answer, and the surprise invites a future contributor to "fix" it back. |
| **B** | Raise on empty, symmetric with the existing `TypeError` for non-bool predicates (`mapper.py:32-33`). | A raise is not a decision. It pushes the safety answer one layer out, where a bare `except` can swallow it into a proceed. Trades a visible wrong answer for an invisible one. |
| **C — recommended** | **Separate the algebra from the decision.** `GATE_POLICY` keeps its ratified truth-table semantics untouched (the 27-combo pin stays green; no ratified behaviour moves). A new `evaluate_gate(predicates) -> (decision, reason)` is what any live gate calls: empty → `BLOCK / NO_PREDICATES_EVALUATED`; any `None` → `BLOCK / UNEVALUABLE`; any `False` → `BLOCK / PREDICATE_FALSE`; all `True` → `ALLOW / ALL_TRUE`. | Two functions where there was one. |

**Why C.** It is the shape this repo already chose for the same problem one rung over:
`pgdrm.py` deliberately separates `decay_utility` (pure math) from `evaluate` (the
verdict), precisely so the math is not also the decision (`mem/m2-pgdrm` @ `e4730869`,
`pgdrm.py:217-234` vs `:242-313`, **VERIFIED on the branch**). C also adds a `reason`
string, which is what makes §4.5's observable countable — `GATE_POLICY` returns a bare
`"BLOCK"` with no way to distinguish "a predicate was false" from "nothing was
evaluated."

**C is not complete without one more act, and I will not pretend otherwise.**
C resolves the *safety* contradiction: after C, no live gate can be opened by an empty
list, ever. It leaves the *surface* contradiction — a reader of `GATE_POLICY` alone
still sees `ALLOW` for `[]`. So C ships **with** a test that pins
`GATE_POLICY([]) == ALLOW` as **deliberate vacuous-truth algebra, explicitly not a gate
decision**, plus a docstring that says so and points at `evaluate_gate`. Pinning the
edge is what converts it from an accident into a documented choice. Without that pin,
C is a dodge.

**Where this lands.** Resolving the edge at V0.1 is *inside* the ratified plan — the
contract text itself carries it there (`loop-v00.yaml:27`), so this is **not** a
ratification flip. It is also **not this board's code**: `mapper.py` is owned by
`.synapse/contracts/loop-v00.yaml:13` and V0.1 belongs to `loop-orchestrator`. M3 hands
the design over; it does not build it.

### 4.5 OBSERVABLE

| | |
|---|---|
| **Name** | `safety_evaluations_total` and `safety_blocks_total`, reported next to `mutating_turns_total` |
| **Today** | `safety_evaluations_total = 0` — a **measured** zero, and it is the finding, because `mutating_turns_total` is also 0 in V0.0 (the mutation step is an honest no-op marker, `recipe.py:68`, **VERIFIED**). The pair `(0, 0)` is honest. The pair that would be a **breach** is `evaluations = 0` while `mutating_turns > 0` — a decorative gate, and that is the number that must be published before anyone claims fail-closed is working. |
| **After SALUS lands** | `safety_evaluations_total == mutating_turns_total` still holds, but `safety_blocks_total < safety_evaluations_total`, and at least one `ALLOW` carries a SALUS receipt id **echoed from the substrate**. |
| **The transition that proves the degradation was real** | The **ALLOW rate moves 0 → >0 with the evaluation count unchanged.** That is the signature of a gate going from *closed-because-absent* to *closed-because-evaluated*. A gate that was never asked cannot produce that signature — which is exactly why the observable is the call counter and not the status. |
| **How a hostile reader measures it** | Two counters and one ratio per session, in the panel or the run artifact. Plus a source-derived check: `grep -rn "evaluate_path" --include=*.py .` must return at least one **non-test** call site. Today it returns none (**VERIFIED**). |
| **A fabricated resolution looks like** | (a) `safety_blocks_total < safety_evaluations_total` while `substrate_presence.salus == absent` — a fabricated ALLOW, caught by a one-line assertion. (b) An `ALLOW` whose receipt id was authored locally rather than echoed from SALUS. (c) Counters incremented at a wrapper rather than at the call, so evaluations rise without SALUS ever being asked — caught by reconciling `evaluations` against SALUS's own request count after install. |

### 4.6 Ratification gate

- **`gate_substrate_install`** (SALUS) — verbatim above.
- **V0.1 arming on the LOOP board** (`harness/loop/STATE.json`) — not this board's to
  arm. This board writes `harness/memory/` and reads `harness/loop/`
  (`harness/memory/SPEC.md`, "Boundary", **VERIFIED**).
- The `evaluate_gate` addition rides `loop-v01.yaml`, **which does not exist yet**
  (**VERIFIED**: `.synapse/contracts/` carries `loop-v00.yaml`; there is no v01).

---

## 5 · What this document deliberately does not do

- **It installs nothing, mocks nothing, vendors nothing.** No substrate was made to
  appear present.
- **It edits no ratified contract.** The §4 surface changes are a *proposal*
  (`CONTRACT_AMENDMENT_v02.md`) that waits for Joe.
- **It changes no shipped code, no test, and no `VERSION`.**
- **It does not upgrade M0's UNKNOWNs.** `shot_login.ensure_scene_structure` thread
  ownership stays unproven; live Moneta reachability stays unmeasured.
- **It reports no coverage percentage for Octavius.** The denominator is absent, so the
  ratio is `UNKNOWN` rather than estimated.

---

## 6 · Open questions a hostile reader should press on

1. **The outbox has no writer yet.** Every number in §2.4 is a design target;
   `prediction_debt` today is uncountable, not zero. §2.2-2.4 are INFERENCE throughout.
2. **The submitted `wake_scene_relations` / `deposit_settlement` signatures are not in
   this repository.** Only the adjudication's prose description survives
   (`BLUEPRINT_ADJUDICATION.md:31-33`). The signatures in the amendment proposal are
   reconstructions, and they are labelled as such.
3. **The taint type (§3.2 Layer 2) has no prototype.** Its ergonomic cost at real call
   sites is unmeasured. If it proves unusable, Layer 1 (the method name) survives on its
   own and is still stronger than a flag.
4. **`memory_handle_census()` lives on an unmerged branch.** Every Moneta observable in
   §1.5 is conditional on `gate_m1_merge`.
5. **No live bridge was reachable this session.** Nothing here was confirmed against a
   running Houdini.
