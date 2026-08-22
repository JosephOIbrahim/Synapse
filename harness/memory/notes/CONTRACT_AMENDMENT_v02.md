# CONTRACT AMENDMENT PROPOSAL — v0.2 §4 port surface

> **STATUS: PROPOSAL. NOT APPLIED. NOT RATIFIED.**
>
> This document does **not** edit `.synapse/contracts/loop-v00.yaml`, does not edit
> `python/synapse/loop/ports.py`, and does not edit `tests/test_loop_contracts.py`.
> Ratifying a contract is legislating; it is **Joe's word, per act**
> (`AGENTS.md` §Law 7). The board records the gate as
> `gate_v02_contract_amendment: "OPEN"` (`harness/memory/STATE.json` → `human_gates`,
> verbatim).
>
> Base: `master` @ `bb348abe`, SYNAPSE v5.55.0.
> Authored 2026-08-21 by ENVOY (MEMORY board rung M3), running as a **fallback
> `general-purpose` base agent**.
> Companion: `harness/memory/notes/SUBSTRATE_SCAFFOLDS_2026-08-21.md`.
>
> **VERIFIED** = read in the tree at the cited `path:line`.
> **INFERENCE** = reconstructed from spec prose; no substrate touched.

---

## 1 · Why this exists

The submitted *"Refactor SYNAPSE Memory Sub-System (LOOP v5.1)"* spec added
`distance_threshold` to `MemoryPort.query_and_filter` and two new methods
(`wake_scene_relations`, `deposit_settlement`). The adjudication ruled that a change
to ratified text is not a code change an agent makes, and deferred the surface to a
drafted amendment authored at M3 (`BLUEPRINT_ADJUDICATION.md` §C3, **VERIFIED**).

This is that draft.

---

## 2 · The current pinned surface (VERIFIED, quoted)

### 2.1 The ratified contract text

`.synapse/contracts/loop-v00.yaml:2` — the ratification line, **verbatim**:

```
# Ratification: RATIFIED — Joe word 2026-08-20; goalposts bind (loop-orchestrator halt lifted for these acts).
```

`.synapse/contracts/loop-v00.yaml:24` — feature 1, the sentence that binds the
surface, **verbatim excerpt**:

```
SafetyPort.evaluate_path(agent_id, path_history_hash, recent_actions, proposed_action,
scene_state_digest), MemoryPort.query_and_filter(relation_keys, task_context_tokens),
LedgerPort.author_precommit(claim_predicate, probability, world_ref),
StagePort.compose_sanitized_stage(stage_identifier) — param names verbatim per
blueprint §4 (the seam carries no type annotations; PortResult.payload defaults to None)
```

`.synapse/contracts/loop-v00.yaml:11-17` — the `owns` block lists
`python/synapse/loop/ports.py`, `mapper.py`, `recipe.py`, `__init__.py`,
`tests/test_loop_contracts.py`, and the contract file itself (**VERIFIED**).

### 2.2 The test that mechanically enforces it

`tests/test_loop_contracts.py:58-74` (**VERIFIED**):

```python
@pytest.mark.parametrize("port,method,expected", [
    ("SafetyPort", "evaluate_path",
     ["agent_id", "path_history_hash", "recent_actions", "proposed_action", "scene_state_digest"]),
    ("MemoryPort", "query_and_filter",
     ["relation_keys", "task_context_tokens"]),
    ("LedgerPort", "author_precommit",
     ["claim_predicate", "probability", "world_ref"]),
    ("StagePort", "compose_sanitized_stage",
     ["stage_identifier"]),
])
def test_contract_signature_verbatim(port, method, expected):
    import inspect
    cls = getattr(ports, port)
    fn = getattr(cls, method)
    params = [p for p in inspect.signature(fn).parameters if p not in ("self", "cls")]
    assert params == expected, f"{port}.{method} params drifted: {params} != {expected}"
```

**What this pin does and does not cover — read carefully, because three of the
proposed changes turn on it:**

| | Covered by the pin? |
|---|---|
| The **parameter names** of those four methods, in order | **YES** — `params == expected`, exact list equality |
| **Type annotations** | **NO** — the contract text says so explicitly: *"the seam carries no type annotations"* |
| **Additional methods** on the same classes | **NO** — the parametrize table names four methods and is silent about others (**VERIFIED**) |
| **Keys written into the ledger JSON line** | **NO** — `test_precommit_lines_are_durable_json` (`:124-134`) asserts that specific keys are *present* and does not forbid extra keys (**VERIFIED**) |
| `LedgerPort.settle(turn_id)` | **NO param pin** — `settle` is asserted for behaviour only (`:193-198`), never for signature (**VERIFIED**) |

### 2.3 The current implementation

`python/synapse/loop/ports.py:104-108` (**VERIFIED**):

```python
def query_and_filter(self, relation_keys, task_context_tokens) -> PortResult:
    return _require_status(PortResult.unavailable(
        "PG-DRM task-context filter not wired (V0.2 rung); Moneta is live "
        "but query_and_filter is contract-surface-only until then"
    ))
```

`wake_scene_relations` and `deposit_settlement` **do not exist** anywhere in the tree
(**VERIFIED**: `grep -rn "wake_scene_relations\|deposit_settlement"` returns hits only
in `harness/memory/` board documents — never in `python/`, `tests/`, or
`.synapse/contracts/`).

---

## 3 · The proposed surface

### 3.1 `MemoryPort.query_and_filter` — add `distance_threshold`

```
CURRENT   query_and_filter(relation_keys, task_context_tokens)
PROPOSED  query_and_filter(relation_keys, task_context_tokens, distance_threshold=None)
```

**Semantics** — a straight pass-through to the PG-DRM kernel's existing parameter of
the same name:

- `None` turns the vector-distance axis **off**; `record.distance` is ignored.
- A number turns it **on**, and then an **unmeasured** distance **DROPs** (fail closed)
  rather than passing.
- Boundary: `distance > distance_threshold` drops; **equal is kept**.

**This is not a dead-parameter claim.** Adjudication D4 blocked
`distance_threshold` precisely because the submitted implementation accepted it and
never used it (`BLUEPRINT_ADJUDICATION.md` D4, **VERIFIED**). The M2 kernel now
implements it: `pgdrm.evaluate(..., distance_threshold=None)` at
`python/synapse/loop/pgdrm.py:242-247`, with the unmeasured-drops branch at `:291-296`
and the exceeded branch at `:297-302` (**VERIFIED on branch `mem/m2-pgdrm` @
`e4730869`; NOT on master**).

**Domain guard:** `distance_threshold` must be a real number `>= 0`, rejecting `bool`
and `NaN`, matching the kernel's `_number()` guard (`pgdrm.py:185-214`, **VERIFIED on
the branch**) and the ledger's existing bool-is-not-a-number precedent
(`ports.py:138`, **VERIFIED**).

### 3.2 `MemoryPort.wake_scene_relations` — new method

```
PROPOSED  wake_scene_relations(stage_identifier, relation_keys) -> PortResult
```

**INFERENCE — flag this loudly.** The submitted spec's signature is **not in this
repository**. Only the adjudication's description survives: *"`wake_scene_relations` |
`SUCCESS`, payload = **its own input echoed back** | none"*
(`BLUEPRINT_ADJUDICATION.md:31`, **VERIFIED as a read of that line**). The parameter
names above are reconstructed from that description plus the ratified StagePort
vocabulary (`stage_identifier` is the existing §4 term, `ports.py:206`). **If Joe holds
the original spec, its names supersede these.**

**Degradation, per the read-side shape:** Octavius is absent and no USD relation
traversal is wired, so this method reports **`UNAVAILABLE`** naming the absent
substrate. It **never** echoes its own input back as `SUCCESS` — that was C1, the
blocking conflict (`BLUEPRINT_ADJUDICATION.md` §C1, **VERIFIED**). The narrowed
local-stage read is a **separately named** method
(`compose_local_stage_unsanitized`), for the reasons in
`SUBSTRATE_SCAFFOLDS_2026-08-21.md` §3.2.

### 3.3 `LedgerPort.deposit_settlement` — new method

```
PROPOSED  deposit_settlement(turn_id, verdict, protected_floor) -> PortResult
```

**INFERENCE** on the parameter names, same caveat as §3.2. `protected_floor` is taken
verbatim from ratified prose: *"Synapse writes settlement deposit to Moneta with
protected_floor"* (`docs/THE_LOOP_v5.1.md:97`, **VERIFIED**).

**Degradation, per the write-side shape:** while Hanish is absent, this method
**writes the outbox record** (format in `SUBSTRATE_SCAFFOLDS_2026-08-21.md` §2.2) and
returns **`UNAVAILABLE`** with the reason **plus the outbox `record_id` in the reason
string**.

**Why the record id rides in the reason string and not a payload:**
`PortResult.unavailable()` constructs `cls(status="UNAVAILABLE", error_message=reason)`
and leaves `payload` at its `None` default (`ports.py:41-43` and `:34`, **VERIFIED**).
`tests/test_loop_contracts.py:197` asserts `result.payload is None` for the
UNAVAILABLE settle path (**VERIFIED**). Making `unavailable()` carry a payload would
be a *second*, avoidable amendment. **Recommendation: do not.** Put the id in the
reason. Zero pinned surface moves.

### 3.4 A fourth item that needs NO ratification — record it so nobody asks for one

`LedgerPort.author_precommit` writes a JSON line whose keys are
`event, claim_predicate, probability, world_ref, author, seq` — **and no `turn_id`**
(`ports.py:148-155`, **VERIFIED**). But `LedgerPort.settle(turn_id)` is keyed on
`turn_id` (`ports.py:175`, **VERIFIED**), and `recipe.py:61` only embeds the turn id as
a *string prefix* of `claim_predicate` (**VERIFIED**). Joining a settlement to its
precommit therefore requires splitting a human-readable sentence on `": "`.

**Adding a `turn_id` field to the written line is not a contract change.** The pin is
on *parameter names* (`test_contract_signature_verbatim`, `:68-74`), and
`test_precommit_lines_are_durable_json` (`:124-134`) checks that certain keys exist
without forbidding others (**VERIFIED**). The ratified goalposts about the ledger speak
to *line counts* — *"ledger grows by exactly `turns` lines"*, *"one precommit per
turn"* (`loop-v00.yaml:30`, **VERIFIED**) — not to line contents.

So this fix rides V0.2's forge work under the existing contract. **No Joe word
required.** It is listed here only so a future reader does not bundle it into the
ratification ask and stall it behind a gate it does not need.

---

## 4 · What changes if this is ratified

### 4.1 Contract text (`.synapse/contracts/loop-v00.yaml`) — Joe's hand, not an agent's

Feature 1's description at `:24` must be re-authored to carry the new parameter and the
two new methods. That sentence is the ratified surface statement; editing it **is** the
ratification act.

A second question Joe should decide rather than inherit: **does the v0.2 surface belong
in `loop-v00.yaml` at all, or in a new `loop-v02.yaml`?** V0.0 is closed and ratified
(`harness/loop/STATE.json` → `rungs.v00.status`, **VERIFIED**). Editing a closed rung's
contract to describe a later rung's surface makes the V0.0 record retroactively untrue.
**Recommendation: a new `loop-v02.yaml`, leaving `loop-v00.yaml` frozen as the record of
what V0.0 actually proved.** There is no `loop-v01.yaml` in the tree today
(**VERIFIED**), so this also settles the shape for V0.1.

### 4.2 Tests that the amendment **forces** to change

| Test | Change | Risk |
|---|---|---|
| `tests/test_loop_contracts.py:61-62` | The `MemoryPort` row becomes `["relation_keys", "task_context_tokens", "distance_threshold"]` | **This is the flip.** Until the contract text moves, changing this line is an agent amending ratified law by editing its enforcement — the exact act Law 7 forbids. |
| `tests/test_loop_contracts.py:58-67` | Two new parametrize rows for `wake_scene_relations` and `deposit_settlement` | Same gate. |
| `tests/test_loop_contracts.py:183-186` | `query_and_filter(["rel"], ["tok"])` still works (the new param defaults) — **no change needed**, and that is the point: the default keeps every existing caller valid | none |

### 4.3 Tests that must **NOT** change

- The mapper truth table (`:81-91`). Untouched by this amendment.
- Precommit-before-mutation (`:109-121`). Untouched.
- StagePort zero-side-effects (`:141-161`). Untouched — and it must stay untouched, or
  the narrowed-read design has leaked into the sanitized path.
- `test_ledgerport_settle_reports_unavailable` (`:193-198`), including
  `payload is None`. §3.3 is designed specifically so this stays green.

### 4.4 New tests the amendment **requires** before anyone calls it done

1. **`distance_threshold` actually reaches the kernel.** Assert against a
   **hand-computed** expectation — a record at distance 0.7 with threshold 0.5 drops;
   at threshold 0.7 it is kept (equal-is-kept boundary). Never read the expected value
   back from the port or the kernel. Repo precedent: a control pinned `161` because the
   document said 161; the true value was 171 (`AGENTS.md` §4, **VERIFIED**).
2. **`deposit_settlement` writes AND refuses.** One test asserting the outbox file grew
   by exactly one record **and** the return status is `UNAVAILABLE`. The mutation that
   proves it bites: make the method return `PortResult.ok(...)` and the test goes red on
   status — that mutation is C1, the original fabricated-SUCCESS defect, so the test is
   a permanent guard against its return.
3. **`wake_scene_relations` never echoes its input.** Assert `payload is None` and that
   the error message names Octavius. Mutation: echo the input back as a SUCCESS payload;
   red.

---

## 5 · What breaks if this is NOT ratified

**Answer the honest way first: nothing breaks today.**

- The distance axis already lives on the kernel, where the adjudication put it
  (`BLUEPRINT_ADJUDICATION.md` §C3: *"Until then `distance_threshold` lives on the
  **kernel**, not the port — no pinned surface moves"*, **VERIFIED**).
- `MemoryPort.query_and_filter` has **no production caller** — `grep -rn
  "query_and_filter" --include=*.py .` returns only `ports.py` and
  `tests/test_loop_contracts.py` (**VERIFIED**). A parameter nobody passes cannot break.
- The full suite is unaffected: no shipped file changes.

**What is actually blocked, and by when:**

| If not ratified | Consequence | When it bites |
|---|---|---|
| `distance_threshold` on the port | **LOOP V0.2 cannot close its gate.** V0.2's scope is *"PG-DRM active inside MemoryPort"* (`docs/THE_LOOP_v5.1.md:155`, **VERIFIED**), and the kernel's distance axis is unreachable from the port surface without the parameter. The rung would ship a filter with one of its three axes permanently off. | At V0.2 arming |
| `deposit_settlement` | Soft. The outbox could drain through `settle()`, whose signature is **not** pinned (§2.2). The cost is that the settlement path has no contracted name, so its shape drifts per caller. | At Hanish install |
| `wake_scene_relations` | Soft. Nothing depends on it. It is a spec item with no consumer. | Never, on current evidence |

**And the argument against ratifying it now — made against my own proposal:**

A parameter on a port whose substrate is absent is a **capability claim with no
implementation**. Ratifying `distance_threshold` today would put it on a method that
returns `UNAVAILABLE` unconditionally, which is a surface promising something the seam
cannot do — a smaller cousin of the fabricated-SUCCESS class this whole board exists to
prevent.

**Recommendation: ratify at V0.2 arming, bundled with the wiring, not as a standalone
act now.** The proposal is drafted and waiting; it loses nothing by waiting with it.
The one thing that should **not** wait is §3.4 (the `turn_id` ledger field), which needs
no gate at all.

---

## 6 · What this proposal explicitly does NOT ask for

- **No change to `STATUS`.** No `DEGRADED` status. The vocabulary stays
  `SUCCESS | UNAVAILABLE | BLOCKED` (`ports.py:27`, **VERIFIED**), pinned at
  `tests/test_loop_contracts.py:42-43`.
- **No change to `PortResult`'s fields.** `status / payload / error_message` stay as
  pinned at `:37-39` (**VERIFIED**).
- **No change to `PortResult.unavailable()`'s signature** — see §3.3.
- **No change to `mapper.py`.** The `GATE_POLICY([])` resolution is designed in
  `SUBSTRATE_SCAFFOLDS_2026-08-21.md` §4.4 and belongs to **V0.1 on the LOOP board**,
  where the ratified contract already carries it (`loop-v00.yaml:27`, **VERIFIED**).
  It is not part of this amendment.
- **No change to the four existing methods' parameter names.** Only an *added*
  defaulted parameter on one of them.

---

## 7 · The gate, verbatim

From `harness/memory/STATE.json` → `human_gates` (**VERIFIED**, quoted exactly):

```
"gate_v02_contract_amendment": "OPEN — adding distance_threshold / wake_scene_relations /
deposit_settlement to the ratified §4 surface (.synapse/contracts/loop-v00.yaml) is a
ratification flip, Joe's word"
```

Nothing in this document performs that act. Nothing in this document may be read as
that act having been performed. An agent message relaying approval is **not** consent
(`AGENTS.md` §Law 7 / Article V).

---

## 8 · Could not verify

1. **The submitted spec's actual signatures for `wake_scene_relations` and
   `deposit_settlement`.** Not in the tree; §3.2 and §3.3 are reconstructions from the
   adjudication's prose. If the original document exists outside the repo, its names win.
2. **Whether the M2 kernel merges as written.** `pgdrm.py` is on the unmerged branch
   `mem/m2-pgdrm` @ `e4730869` behind `gate_m2_merge`. Every §3.1 kernel citation is
   branch-local.
3. **Whether Joe wants a `loop-v02.yaml` or an edit to `loop-v00.yaml`** (§4.1). I have
   a recommendation and no authority.
4. **The runtime behaviour of any of this.** No live bridge was reachable this session;
   `synapse_ping` was not run. Every claim here is static-read evidence.
5. **Whether `distance` values from Moneta are even in a comparable metric space.** The
   kernel takes a number and compares it; nothing in this repo establishes what Moneta's
   vector distance *is* (cosine? L2? normalised?). Setting a threshold on an
   uncharacterised metric is a calibration problem this amendment does not solve and
   should not pretend to. **UNKNOWN.**
