# Phase 0a Spec — `synapse_write_file` + the Floor emit-time hook

**Status:** `DESIGN RATIFIED — 2026-06-02 (signed off by Joe on the §8 registry-invocation
decision). UNBUILT, not verified.` FORGE is unblocked to build §9 in order (0a before the
0a′ hook, §8.4 interlock). "Verified" is **not** claimed and is gated by the §11 acceptance
pins — sign-off ratifies the *design*, not a working artifact.

**Role:** ARCHITECT (spec only — no FORGE implementation in this pass).
**Date:** 2026-06-02.

**Correction log (provenance):**
- *2026-06-02, sign-off.* Joe ratified the §8 resolution (Floor hook at
  `CommandHandlerRegistry.invoke()`, not `handle()`). Harness doc `SYNAPSE_SCIENCE_HARNESS.md`
  amended in the same change: §2 named "the Ledger"; §4a (Tier 0/Tier 1 + emit-time hook +
  §4a.3 Floor provenance) added so this spec's cross-references resolve on disk.
- *2026-06-02, pre-commit adversarial pass.* The load-bearing §8 claim — "`handle()` is the
  single funnel, no other path from emit to run" — was **falsified by code**. There are
  **three** handler-invocation sites sharing `self._registry`: `handle():331` (external
  ingress), `_handle_batch_commands:705`, and `_HandlerAdapter.call:1387` (autonomy
  modules). Batch and autonomy dispatch sub-ops via `registry.get()` directly, **bypassing
  `handle()`**. §8 rewritten: the Floor hook moves from `handle()` to a shared
  **registry-invocation primitive**. The decision (server-side structural enforcement)
  is unchanged and in fact strengthened; only its seat moved one layer down.
- Citation fix: `science/registry.py` does **not** import `write_report`; it exposes a
  `deposit_fn` seam documented as "the Moneta / synapse_write_report injection point."
**Binds to:** `docs/SYNAPSE_SCIENCE_HARNESS.md` §5 (Phase 0a), §2 (the Ledger), §4
(invariants), §4a (Tier 0/Tier 1 + the emit-time Floor hook, added 2026-06-02).
**Grounded in (read, not assumed):**
- `python/synapse/cognitive/tools/write_report.py` (the shipped write path)
- `python/synapse/server/handlers.py:303` (`handle()` dispatch chokepoint), `:335`
  (existing post-exec audit hook), `:994` (`_handle_write_report`)
- `python/synapse/server/handlers.py:705` (`_handle_batch_commands` — bypass site #2),
  `:1384` (`_HandlerAdapter.call`, autonomy — bypass site #3)
- `python/synapse/server/main_thread.py` (`run_on_main`, the marshaling 0a routes around)
- `python/synapse/core/gates.py` (`GateLevel`/`HumanGate` — the *human* gate, distinct
  from the Floor hook)
- `python/synapse/science/registry.py` (a `deposit_fn` callback documented as "the Moneta /
  synapse_write_report injection point" + an append-only JSONL fallback — the Ledger seam;
  it does **not** import the tool, it is the seam the tool plugs into)

---

## 0 — Section reconciliation (done 2026-06-02)

The harness doc (`SYNAPSE_SCIENCE_HARNESS.md`) originally framed the regime as a **§3
build-vs-search admission gate** plus **§4 hard invariants**, with no literal "Tier 0 /
Tier 1" split and no `§4a`. The sign-off request introduced that vocabulary. Rather than
let this spec reference anchors the harness doc couldn't back, the harness doc was
**amended in the same change** (2026-06-02). The mapping is now real on disk:

| Spec term | Harness doc anchor (now present) |
|---|---|
| **Tier 0 / the Floor** | harness §4a (intro) + §4a.1 — §4 invariants applied unconditionally to every emit, incl. straight builds. |
| **Tier 1 / gated search** | harness §4a (intro) — §3-admitted loop + §4 noise-aware promotion. |
| **Floor provenance** | harness §4a.3. |
| **the emit-time hook** | harness §4a.2 — placement resolved *here* (§8), recorded there. |

**Recommendation — DONE.** The "Tier 0 Floor / Tier 1 search" subsection now lives at
harness §4a; this spec's cross-references resolve. One honest note: the "hook placement"
was the *spec's* framing, **not** a literal open bullet in harness §7 (whose open questions
are cadence / compute-yield / registry-surfacing / second-seed). §8 below resolves it and
the resolution is recorded at harness §4a.2 — *not* §7.

---

## 1 — Scope: what exists vs. what 0a adds

`synapse_write_report` is **shipped and solid for its current scope** (PR #15). 0a is *not*
"80% done" as a single unit — it is one done piece plus three genuinely unbuilt pieces:

| Piece | State | Note |
|---|---|---|
| Text write, single confined root (`docs/`) | **DONE** | `write_report.py`; atomic; zero-`hou`; traversal-guarded. |
| **Binary payloads** | **UNBUILT** | text-only today (`open(..., "w", encoding="utf-8")`). |
| **Multi-root path policy** (not just `docs/`) | **UNBUILT** | base_dir is hardcoded to `$SYNAPSE_REPORTS_DIR` else `<repo>/docs`. |
| **The emit-time Floor hook (§4a)** | **UNBUILT — and the largest piece** | Today: only a *post-exec audit log* at `handle():335`, and it does **not** cover batch sub-ops or autonomy ops (§8). Needs a new `registry.invoke()` primitive + 3 call-site changes, not a single wrap. |

Honest status line for the harness doc §5: *0a-text = done; 0a-binary + 0a-multiroot +
the §4a hook = unbuilt.* The hook is the substantive work, not a residual.

---

## 2 — Server-side I/O contract (and why it sidesteps `execute_python` by design)

**Confirmed by construction, not by hope.** The blocker chain for `execute_python` is:
`_handle_execute_python` → `run_on_main(fn, _SLOW_TIMEOUT)` → `hdefereval.executeDeferred`
(`main_thread.py:105`) → waits on the **main thread**; a modal dialog or active cook holds
the main thread, the 30s timeout fires, the write **fails** (`SYNAPSE_SCIENCE_HARNESS.md`
§5/0b).

`write_report` / `synapse_write_file` **never enter that chain**:

- It is **pure Python file I/O with zero `hou` imports** (pinned by
  `tests/test_cognitive_boundary.py`). Because it touches no `hou` API, marshaling to the
  main thread would be *incorrect*, not merely slow.
- `_handle_write_file` runs the write **directly on the calling (WS-handler / daemon)
  thread** — it does **not** call `run_on_main`. Verified against `_handle_write_report`
  (`handlers.py:994`), which is the template.
- Therefore it completes **even when `is_main_thread_stalled()` is True**. This is the
  property the whole bootstrap interlock (§5/§8 below) depends on: the Floor's own
  provenance writes cannot be blocked by the thing the harness is trying to record.

**Contract:** `synapse_write_file` MUST NOT call `run_on_main`, MUST NOT import `hou`, and
MUST be covered by the cognitive-boundary test. Any future change that adds a `hou` import
to this path is a Floor violation, not a refactor.

---

## 3 — Path validation & safety

The dangerous generalization is "general (non-reports-dir) paths." **"General" must NOT
mean "anywhere on disk."** It means a **registry of named, confined roots**, selected by
key — never a free absolute path from the caller.

### 3.1 Root registry (replaces the single hardcoded base)

```python
# spec — not implementation
ROOTS = {
    "reports":    <repo>/docs                        # back-compat: write_report's current base
    "ledger":     $SYNAPSE_LEDGER_DIR  else <repo>/.synapse/ledger      # harness §2 (the Ledger)
    "provenance": $SYNAPSE_PROVENANCE_DIR else <repo>/.synapse/provenance # harness §4a.3 (Floor provenance)
}
```

- Caller passes `(root, relative_path)`. An unknown `root` → hard reject.
- `relative_path` is confined **within the selected root** by the existing `_confine()`
  math (`resolve()` + `base_resolved in candidate.parents`), which already defeats `..`
  and absolute escape, **including via symlink** (because `.resolve()` collapses symlinks
  before the parent check). Keep that; add an explicit symlink-escape test.

### 3.2 Hardening to add (current `_confine` does not cover these; base is Windows)

- **Reserved Windows device names** — reject `CON, PRN, AUX, NUL, COM1–9, LPT1–9` as any
  path component (case-insensitive, with or without extension). On Win11 (Joe's box) these
  are not valid filenames and can hang or misbehave.
- **NUL / control bytes** in the path → reject.
- **Path-length guard** — reject components/total exceeding the platform limit unless a
  `\\?\` long-path strategy is explicitly chosen. Spec a conservative cap (e.g. 240 chars
  for the full resolved path) and reject above it with a clear message.
- **Separator normalization** — accept `/`; normalize before confinement so `a/b` and
  `a\b` confine identically.

### 3.3 Non-goals (explicitly out)

- No writing outside the registered roots, ever (no "trusted caller" bypass).
- No creating roots at call time — roots are config, resolved once, validated at startup.

---

## 4 — Payload model & return contract

### 4.1 Input (extends `WRITE_REPORT_SCHEMA`)

```
root            : str   (enum of ROOTS keys; default "reports" for back-compat)
relative_path   : str   (no abs, no '..'; confined under root)
content         : str?  (UTF-8 text)                 ── exactly one of content / content_base64
content_base64  : str?  (base64 of raw bytes)        ── exactly one of content / content_base64
overwrite       : bool  (default True)
```

- **Exactly one** of `content` / `content_base64` — providing both or neither is a user
  error (§5). Text path writes `"w", encoding="utf-8"`; binary path base64-decodes and
  writes `"wb"`. Atomicity (tmp+fsync+replace) is identical for both.
- Back-compat: `synapse_write_report` stays as a thin alias that forwards
  `root="reports"`, text-only. Existing callers and `science/registry.py` keep working
  unchanged.

### 4.2 Return

```
{ ok: true,
  root: "<key>", path: "<resolved abs path>",
  bytes_written: <int>,
  encoding: "utf-8" | "binary",
  sha256: "<hex of the exact bytes written>" }   ← new
```

`sha256` is **required for the Floor**: provenance records (harness §4a.3) and the dead-end
registry (harness §2) need a content hash to be replayable/auditable — it mirrors the bridge's
`IntegrityBlock.delta_hash`. Cheap to compute over bytes we already hold.

---

## 5 — Error contract (bound to the real dispatch mapping)

`handle()` (`handlers.py:303`) routes exceptions into two response branches — and the
circuit breaker trips *downstream* of that split, off the response/exception type (the
branch comments at `:346/:354/:362` mark the intent, "Don't trip CB" / "DO trip CB"):
`SynapseUserError`/`ValueError` → failure response, **no-CB branch**;
`SynapseServiceError`/bare `Exception` → failure response, **CB-tripping branch**.

The write path must honor that split:

| Condition | Raise | Why |
|---|---|---|
| unknown `root`, abs path, `..` traversal, reserved name, too-long, NUL, both/neither content fields, bad base64, `overwrite=False` collision | `WriteFileError(ValueError)` | caller's mistake → user error, **must not** trip CB |
| disk full / permission denied / I/O failure | `SynapseServiceError` | environment outage → CB should see persistent disk failure |

`WriteFileError` subclasses `ValueError` (as `ReportPathError` already does), so it lands
in the existing user-error branch with **zero changes to `handle()`**. The OSError→Service
mapping is the one new wrapping the FORGE pass adds.

---

## 6 — Atomicity & concurrency

- **Atomic, unchanged:** `mkstemp` in the **target's own dir** → write → `flush` →
  `os.fsync` → `os.replace`. Same-dir tmp guarantees `os.replace` is a same-filesystem
  atomic rename on both Windows and POSIX (no cross-device fallback). On failure, the tmp
  is unlinked. Readers never see a torn file.
- **Binary:** identical sequence in `"wb"`; `fsync` semantics are the same.
- **Concurrency:** two writers to the same target → each atomic, **last-replace-wins**, no
  corruption. No file lock is needed for integrity. If write *ordering* matters, that is the
  **caller's** concern.
- **Tension to resolve (append-only JSONL vs atomic full-replace):** `write_file`'s model is
  *atomic replacement of a whole file* — it has **no append mode**. But the existing
  `science/registry.py` Ledger fallback is **append-only JSONL** (one growing file). These
  are incompatible: you cannot atomically full-replace a 10k-line JSONL on every record
  without O(n) rewrites and a lost-update race between concurrent appenders. Three ways out,
  for sign-off (§10): **(a)** Ledger writes **one immutable file per record**
  (`dead_end_<ts>_<hash>.json`) via `write_file` — no shared file, no ordering problem, at
  the cost of many small files; **(b)** `write_file` gains an explicit `append` mode (gives
  up whole-file atomicity for that path); **(c)** the JSONL stays owned by the registry's own
  append logic, and `write_file` is only the *provenance* + *Moneta-fallback* path. **Spec
  leans (a)** — it preserves the atomic guarantee and is the natural fit for immutable
  provenance — but it is a genuine open decision, not settled here.

---

## 7 — Dual-tier write-path (one endpoint, two tiers, by root key)

`synapse_write_file` is the **single write substrate** for both tiers; the `root` key is
what separates them:

- **Tier 0 — Floor provenance (§4a.3):** the emit-time hook (§8) writes a provenance
  record for **every non-read-only op**, unconditionally, to `root="provenance"`. One
  immutable file per op. This is the audit trail the cognitive-substrate thesis points at
  SYNAPSE's own evolution.
- **Tier 1 — Ledger / dead-end registry (harness §2):** the harness writes `DeadEnd` /
  `Champion` / `Forum` records to `root="ledger"` — leaning one immutable file per record
  (**pending the §10 append-model decision**). Per harness §2,
  **prefer Moneta** when the backend is enabled; **fall back to `synapse_write_file`** when
  Moneta is default-off (current state, v5.10.0). So this endpoint is *both* the always-on
  Floor substrate *and* the Ledger's degraded-mode substrate.

The two tiers never share a file or a root; they share only the confined, blocker-free,
hashed write mechanism. That is exactly the "write-path for BOTH tiers" requirement.

---

## 8 — RESOLVED: where the emit-time Floor check lives (recorded at harness §4a.2)

**Resolution: a server-side gate at the shared handler-invocation primitive of
`CommandHandlerRegistry` (a new `registry.invoke(cmd_type, payload, ctx)`), through which
all three invocation sites are routed — NOT in any tool, NOT in any role's discipline, and
NOT at `handle()` alone (which is only one of the three sites).**

This is the user's read — server-side, structural, substrate-enforced — and after
grounding it against the code I **argue it with one correction the code forced**: the seat
is *one layer below* `handle()`. The user's instinct (and my first draft) put the hook at
`handle()`; the pre-commit pass proved that insufficient (see Correction log).

### 8.1 Why the registry-invocation primitive, not `handle()` — and why not the bridge

**The funnel is not `handle()`. It is the registry.** Verified exhaustively, there are
exactly **three** sites that turn a command-type into a running handler, and all three
share the one `self._registry`:

| # | Site | Code | Through `handle()`? |
|---|---|---|---|
| 1 | external ingress | `handle():316/331` — `registry.get(cmd)` then `handler(payload)` | — (it *is* handle) |
| 2 | **batch fan-out** | `_handle_batch_commands:693/705` — `registry.get(cmd)` then `handler(cmd_payload)` | **NO** |
| 3 | **autonomy adapter** | `_HandlerAdapter.call:1384/1387` — `registry.get(name)` then `handler(params)` | **NO** |

A Floor hook in `handle()` would fire **once** for a `batch_commands` envelope and **zero**
times for the mutations inside it (a batch of `[delete_node, set_parm, execute_python]`
→ one "batch ran" record, three unprovenanced mutations), and would miss **every**
autonomy-driven op entirely. That is a Floor hole, not a corner case — batch and autonomy
are exactly where unattended mutation volume lives.

External ingress *is* fully funneled: every transport (`websocket.py:535/560/623`,
`hwebserver_adapter.py:185/211`, `mcp/server.py:579`, `mcp/tools.py:126`) reaches a handler
**only** via `handler.handle(command)` — none touch the registry directly. So the bypass is
purely *internal* fan-out, and the fix is not "guard every transport" but "make handler
invocation itself the choke."

**The mechanism (altitude-correct — generalize, don't special-case):** add
`CommandHandlerRegistry.invoke(cmd_type, payload, ctx) -> result` that wraps the Floor
check around `self._handlers[cmd_type](payload)`, and route **all three** sites through it
(`handle()`, batch, adapter). Make `get()` invocation-only so the only way to *run* a
handler is `invoke()`. The registry is the one object all three already hold — it is the
true "only code path to emission," the structural guarantee CLAUDE.md gives Houdini
mutations via the bridge ("agents are downstream"), now applied to *every* emit, hou or not.

`ctx` carries nesting: a batch sub-op gets `ctx.parent = <batch op-id>` so its provenance
is a **child** of the batch record (not a sibling, not absent); an autonomy op gets
`ctx.origin = "autonomy"`. The line-335 audit bracket (`_submit_logs`) is **subsumed** by
`invoke()` — it becomes one place fired for all three sites, instead of a post-exec hook
only `handle()` reaches today. (Altitude check passes: we unify three independent
get-then-call sites into one primitive, rather than bolting a hook onto each.)

**Why NOT the `LosslessExecutionBridge`:** the bridge is the only path to *Houdini*, but it
is downstream of dispatch and scoped to `hou` mutations — `write_file`, the Ledger,
autonomy decisions, and batch sub-ops that never touch `hou` all slip past it. The Floor
must sit at the invocation primitive, *above* the hou/non-hou split. The bridge stays the
Floor's *executor* for scene mutations; the registry is its *gate*.

**Coverage caveat — a second registry exists (found in the consistency pass).**
`synapse.cognitive.dispatcher.Dispatcher` (`dispatcher.py:101`) is a *separate* invocation
surface: its own `self._tools` registry, its own `execute()` (`:212` → `fn(**kwargs)` /
`_execute_via_main_thread`), the forward-looking in-process **Agent-SDK** path. It does
**not** share `self._registry`, so the "exactly three sites" claim above (scoped to
`CommandHandlerRegistry`) still holds — *but a Floor hook on `registry.invoke()` alone would
not cover ops emitted through the Dispatcher.* Since the Dispatcher is the autonomy/SDK
seam, that is the same hole one layer over (autonomy slipping the Floor, exactly as batch
slips a `handle()`-only hook). The Floor must therefore wrap **both**
`CommandHandlerRegistry.invoke()` **and** `Dispatcher.execute()` — or the two registries
must converge (the Dispatcher is a Strangler-Fig *meant* to subsume the handler path;
convergence is the clean long-term answer). Tracked in §10.

### 8.2 Why NOT the five alternatives

- **(A) In the tool (`write_file` itself).** A Floor that only fires on file writes is not
  a Floor. Rejected.
- **(B) In each `_handle_*`.** 108 handlers each remembering to call the check — this *is*
  "a role remembering to," relocated into code. The first new handler that forgets is an
  unprovenanced emit. Rejected.
- **(C) In `LosslessExecutionBridge`.** Too narrow — see §8.1's closing paragraph: the
  bridge is the path to *Houdini* only, downstream of dispatch; non-`hou` emits (write_file,
  Ledger, autonomy) slip past it. Executor, not gate. Rejected.
- **(D) In `handle()` alone.** The seductive wrong answer (my first draft). `handle()` is
  only invocation site #1 of three; batch (#2) and autonomy (#3) fan out via `registry.get()`
  and never enter `handle()`. A `handle()`-only hook leaves batch sub-ops and all autonomy
  ops unprovenanced. Rejected — *this is the correction that moved the seat to the registry.*
- **(E) Transport layer (`websocket.py`, pre-dispatch).** Too low — it lacks command
  semantics (`_READ_ONLY_COMMANDS`, category, gate level) that the handler layer already has,
  and would re-derive them. Rejected.

### 8.3 What the hook does (precisely scoped — it does not re-do the bridge's job)

A wrap inside `registry.invoke(cmd_type, payload, ctx)`, around the `handler(payload)` call:

1. **Pre-exec — classify:** read-only? mutating? touches-disk? Tier-1-gated (science)?
   Pull from the registry metadata that `_READ_ONLY_COMMANDS` / `_CMD_CATEGORY` already
   express.
2. **Pre-exec — admission:** if the op is tagged Tier 1 (a harness experiment), require an
   attached gate decision; absent → **halt-and-surface**, do not run. (Tier 1 *gating
   logic* is the harness's; the hook only enforces that a Tier-1 op cannot run ungated.)
3. **Post-exec — Floor provenance (Tier 0, unconditional):** for every non-read-only op,
   write one immutable provenance record via `synapse_write_file(root="provenance")` —
   `{op, payload-digest, result-digest, sha256, ts, session, outcome, parent, origin}`.
   Because the hook lives in `invoke()`, this fires for **batch sub-ops and autonomy ops
   too**, each linked to its parent via `ctx.parent` (batch sub-ops nest under the batch
   record). **Via the blocker-free write path, never `execute_python`.**
4. **Post-exec — halt triggers (§4):** on unverified-API / failed-transaction /
   noise-band-ambiguity / merge-conflict signals in the result, raise the halt-and-surface
   path instead of returning a quiet success.

It does **not** wrap undo groups, marshal threads, or validate USD composition — those are
the bridge's anchors, downstream, for `hou` ops. The hook's currency is **classification +
provenance + admission + halt**, the things true of *every* emit.

### 8.4 The bootstrap interlock (why 0a must precede the hook)

The hook records Floor provenance **by calling the write path**. If that write could be
blocked by a busy main thread, the Floor would be unenforceable exactly when the system is
under load (mid-cook, modal dialog). It can't — §2 guarantees `write_file` runs off the
main thread. So the dependency is strict and correct: **0a (the blocker-free write path)
is a hard prerequisite for the §4a hook.** This is the same interlock the harness §5
describes ("C ships before B"), made precise: the Floor's enforcement mechanism depends on
the Floor's write mechanism, so the write mechanism is Phase 0a and the hook is Phase 0a′,
strictly after.

---

## 9 — FORGE build decomposition (spec only; ordered; all UNBUILT)

1. **`write_file.py`** — generalize `write_report.py`: `root` registry, binary path,
   hardening (§3.2), `sha256` in return, `WriteFileError(ValueError)`. Keep zero-`hou`.
2. **`_handle_write_file`** in `handlers.py` + register `"write_file"`; make
   `_handle_write_report` forward to it (`root="reports"`, text). Map OSError →
   `SynapseServiceError`.
3. **MCP surface** — add `synapse_write_file` in `mcp/_tool_registry.py` alongside
   `synapse_write_report`.
4. **`CommandHandlerRegistry.invoke(cmd_type, payload, ctx)`** — the new shared invocation
   primitive carrying the `FloorGate`; provenance via `write_file(root="provenance")`;
   subsume the line-335 audit bracket. **Route all three sites through it:** `handle():331`,
   `_handle_batch_commands:705`, `_HandlerAdapter.call:1387`. Make `registry.get()`
   invocation-only. **Also cover `Dispatcher.execute()`** (the Agent-SDK registry, §8
   coverage caveat) — wrap it too, or converge the registries. *This is the largest piece of
   0a′ — three+ call-site changes plus the primitive, not a single wrap.* Pins: §11.
5. **`science/registry.py`** — wire `write_file(root="ledger")` as the `deposit_fn`
   (one-file-per-record per §6 lean-(a) — **contingent on the §10 append-model decision**);
   keep Moneta-preferred. (Today `deposit_fn=None` at the science entrypoint — this is the
   wiring that closes it.)

---

## 10 — Open sub-questions for sign-off

- **Ledger record format & append model** — JSON per the `DeadEnd` dataclass (harness §2)?
  And the §6 tension: one-immutable-file-per-record (lean-(a)) vs `write_file` append-mode
  (b) vs registry-owned JSONL (c). Pick one; it changes both `write_file`'s surface and §9.5.
- **Two-registry Floor coverage** — must the hook also wrap `Dispatcher.execute()` (the
  Agent-SDK path, `dispatcher.py`), not just `CommandHandlerRegistry.invoke()`? Decide: wrap
  both now, or converge the two registries (Strangler-Fig). See §8 coverage caveat.
- **Provenance volume / rotation** — one file per non-read-only op could be high-volume.
  Retention/rotation policy for `root="provenance"`? (Out of 0a scope, but the hook's
  cadence forces the question.)
- **`_READ_ONLY_COMMANDS` as Floor source of truth** — the hook keys "is this provenanced"
  off that set. Is that set authoritative and complete, or does the Floor need its own
  classification table?
- **Default `root`** — keep `"reports"` default for back-compat, or force explicit `root`
  on the new tool and let only the `write_report` alias default? (Spec assumes the former.)

---

## 11 — Proposed acceptance pins (proposed — none run)

- Cognitive-boundary test still passes (no `hou` in the write path).
- Traversal/symlink/reserved-name/NUL/length rejections each have a test (§3).
- text↔binary round-trip: bytes out == bytes in; `sha256` matches.
- A Tier-1-tagged op with no gate decision **halts** in `invoke()` and does not execute.
- Every non-read-only op leaves exactly one provenance file with a matching `sha256`.
- **A `batch_commands` of N mutating sub-ops yields N+1 provenance records** (one per sub-op,
  each `parent`-linked to the batch, plus the batch envelope) — the regression test that
  pins the §8 hole closed.
- **An autonomy-driven op (via `_HandlerAdapter`) is provenanced** with `origin="autonomy"`.
- A write issued while `is_main_thread_stalled()` is True still completes.

---

**SIGNED OFF — 2026-06-02.** Design ratified; FORGE unblocked to build §9 in order, 0a
before the 0a′ hook (§8.4 interlock). Still UNBUILT — no "verified" stamp until the §11
acceptance pins pass (notably: a `batch_commands` of N mutating sub-ops yields N+1
provenance records, and an autonomy op is provenanced). Open §10 decisions — chiefly the
Ledger append model (§6) — should be settled before §9.5.
