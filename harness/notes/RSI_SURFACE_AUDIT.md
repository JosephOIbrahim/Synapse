# RSI SURFACE AUDIT — has the recursive self-improvement machinery ever run?

**Leg RSI0 · 2026-07-27 · read-only · commit `2105453` (`feat/repair-heats-01`)**
**Question asked:** not *does the mechanism exist* — *is it connected, and has it ever fired.*

---

## The three mechanisms, as three separate booleans

| Mechanism | WIRED | FIRES | MODIFIES SOMETHING |
|---|---|---|---|
| `python/synapse/routing/adaptation.py` — `EpochAdapter` | **TRUE** | **FALSE in production** (TRUE in pytest only) | **FALSE** |
| `python/synapse/agent/learning.py` — `OutcomeTracker` | **FALSE** | **FALSE** | **FALSE** |
| `python/synapse/memory/evolution.py` — memory evolution | **TRUE** | **TRUE** (detector only) | **FALSE** on the automatic path |

Definitions used, because the whole leg turns on the distinction:

- **WIRED** — a live, non-test code path constructs it and calls into it.
- **FIRES** — it has demonstrably executed its own core action at least once outside a test.
- **MODIFIES SOMETHING** — a value it wrote was subsequently *read* by something that changes behaviour.

**The headline: no RSI loop in this codebase closes.** One is wired and never completes a cycle; one is not wired at all; one completes a cycle that ends in a log line.

---

## Q1 — Has the loop ever completed a single epoch?

**Answer: never, in production. 4,795 epoch-close records exist and every one of them is pytest.**

### Evidence of execution (not wiring)

An epoch boundary emits `adaptation.py:155` —
`logger.info("Epoch %d complete (%d outcomes). Success rates: %s", ...)` on logger `synapse.routing`.

That record **is** persisted: `python/synapse/core/logfile.py:60-95` attaches a `RotatingFileHandler` at `INFO` to the `synapse` logger, installed by the server and panel bootstraps (`server/start_hwebserver.py:57`, `server/hwebserver_adapter.py:285`, `panel/synapse_panel.py:364`). So this is a positive-evidence channel, not a silent one — if a production epoch had ever closed, the line would be on disk.

It is on disk. 4,795 times, across `~/.synapse/logs/synapse.log`, `.log.1`, `.log.3` (2026-07-25 → 2026-07-27).

**Every one of them is a test.** Three independent proofs:

**1. Impossible epoch sizes.** Production constructs `EpochAdapter()` with no argument (`router.py:202`), so `epoch_size` is always `DEFAULT_EPOCH_SIZE = 100` (`adaptation.py:28,121`). The observed sizes across all three logs:

| outcomes | count | only possible producer |
|---|---|---|
| 2 | 4,055 | `tests/test_v5_features.py:258` + `tests/test_routing.py:1792` (`epoch_size=2`) |
| 3 | 185 | `tests/test_v5_features.py:248` (`epoch_size=3`) |
| 5 | 185 | `tests/test_v5_features.py:297` (`epoch_size=5`) |
| 100 | 370 | `tests/test_v5_features.py:276` (`epoch_size=100`) |

Sizes 2, 3 and 5 **cannot be produced by the router**. That alone disqualifies 4,425 of 4,795 lines.

**2. The size-100 lines are the wrong shape for traffic.** All 370 are `Epoch 0` (185) and `Epoch 1` (185) — never `Epoch 2`. That is the exact signature of `test_adapter_thread_safety`: 4 threads × 50 records = 200 outcomes at `epoch_size=100` = exactly two rotations, every run. Real traffic accumulating over a long-lived server process would produce `Epoch 2`, `Epoch 3`, … Across 185 occurrences and three days of logs, epoch 2 at size 100 never appears once.

**3. Only one tier is ever named.** Every single line reads `Success rates: {'instant': ...}` — never `recipe`, `fast`, `standard`, `deep` or `cache`. `_record_metric` records `tier.value` for whichever tier handled the request (`router.py:919-926`); a probe driving 140 realistic inputs through a real router recorded a mix. The tests only ever record the literal string `"instant"`.

**The arithmetic closes with zero residual** (VERIFIED-DERIVED, producer = `grep -o "complete ([0-9]* outcomes)" | sort | uniq -c`):

```
185 runs of TestEpochAdaptation:
    test_adapter_epoch_rotation   size 3  × 1  = 185   ✓ observed 185
    test_adapter_threshold_evolves size 5 × 1  = 185   ✓ observed 185
    test_adapter_thread_safety    size 100 × 2 = 370   ✓ observed 370
    test_adapter_stale_pin_epoch  size 2  × 3  = 555
 28 runs of test_epoch_history_capped:
    250 records @ size 2 = 125 rotations × 28  = 3,500
                                       555 + 3,500 = 4,055 ✓ observed 4,055
```

Highest epoch id observed at size 2 is **124** — precisely the 125th rotation (0…124) of `test_epoch_history_capped`'s 250 records. Not one line is left over for production to have written.

**Anchors:** `adaptation.py:145-166` (`_rotate_epoch`), `adaptation.py:155` (the log line), `core/logfile.py:78-92` (the handler that would have caught it), `router.py:202` (size always 100 in production).

### Why it has never closed

`EpochAdapter` has **no persistence** (VERIFIED-RUNTIME, probe P1): `__init__` takes only `epoch_size` and always starts at `epoch_id=0` with `thresholds={}` (`adaptation.py:121-126`). It reads nothing from disk and writes nothing to disk. So an epoch must close **inside one process lifetime**.

The router is constructed lazily on the first chat route (`server/handlers.py:1605-1608`) and needs **100 outcomes that actually reach a tier**. A probe driving 140 realistic inputs produced only **28** recorded outcomes — 112 fell through to the unrecorded fallback. And SYNAPSE's own health report of 2026-07-27 08:39 records the router as *not instantiated at all*.

> **Q1 verdict: the loop has never modified anything in production. The mechanism is decorative.** That is a finding, not a failure.

---

## Q2 — Is `OutcomeTracker` ever constructed with a real memory?

**Answer: no — and the `if memory else None` guard is not the reason. The executor that would construct it has no production caller at all.**

`executor.py:60` reads `self._tracker = OutcomeTracker(memory) if memory else None`. Tracing upward:

`AgentExecutor(` is constructed at exactly **one** non-test site in the whole main tree —
`python/synapse/agent/__init__.py:12` — **which is inside the module docstring** (the docstring spans lines 1-21; line 12 is the illustrative `ex = AgentExecutor()`).

Every other construction is in `tests/test_agent.py` (14 sites, lines 336-826).

```
$ grep -rn "AgentExecutor(" --include=*.py python/ shared/ scripts/ src/ | grep -v _vendor
python/synapse/agent/__init__.py:12:    ex = AgentExecutor()      # <- docstring
```

`python/synapse/__init__.py:339,384` re-exports the symbol lazily; nothing imports it to call it.

**Evidence of execution:** none, and none is possible. `OutcomeTracker.record` writes `MemoryType.FEEDBACK` memories (`learning.py:109-116`). A `FEEDBACK` memory tagged `"outcome"` is the artifact the reward signal would leave. There is no live path that can create one, because there is no live `AgentExecutor`.

The downstream consumers are therefore all reading an empty history by construction:
`OutcomeTracker.get_relevant` (`learning.py:120`), `get_rejections` (`:140`), `success_rate` (`:170`) — the last returns a hard `0.0` when no outcomes exist (`learning.py:191-192`).

**Anchors:** `executor.py:60` (the guard), `executor.py:286,294` (`record_outcome` calls), `executor.py:308-309` (`if self._tracker:`), `agent/__init__.py:1-21` (docstring containing the only non-test construction).

> **Q2 verdict: the reward signal has never recorded a single outcome. It is unreachable, not merely unfed.**

---

## Q3 — What exactly does the loop optimise?

**One sentence:** *Raise the confidence threshold of any tier whose success rate over the last 100 routed outcomes fell below 0.5, and lower it for any tier above 0.9, so that new unpinned inputs are steered toward tiers that recently succeeded.*

Mechanism: `adaptation.py:98-112` (`TierThresholds.adjust`), constants at `:31-32`, step sizes `+0.1` / `-0.05`, clamped to `[0.1, 1.0]`.

**The objective is statable. It is also unreachable, for two independent reasons.**

**(a) The output is read by nothing.** `self._thresholds` is written at `adaptation.py:153` and read at exactly one place — `adaptation.py:184`, inside `stats()`, for display. An exhaustive tree-wide grep finds **zero callers** of `TierThresholds.get()` (`adaptation.py:95`) and **zero callers** of `EpochAdapter.get_stale_pin_epoch()` (`adaptation.py:168`) outside `tests/`.

The router's actual routing decisions use static config values that the adapter never touches:

| decision site | threshold consulted | source |
|---|---|---|
| `router.py:523` | `self._config.tier0_confidence` = 0.8 | `RoutingConfig` (`router.py:107`) |
| `router.py:565` | `self._config.tier1_confidence` = 0.5 | `RoutingConfig` (`router.py:108`) |

**Live probe P3b (VERIFIED-RUNTIME).** Input `"delete /obj/thing1"` reaches Tier 0 with confidence 0.95, so it genuinely *executes* the comparison at `router.py:523` — the check is able to fail. Routed three times with the adapter's thresholds set to empty, then all `1.0` (maximum difficulty), then all `0.0`:

```
default {}       -> tier=instant  confidence=0.95
all 1.0          -> tier=instant  confidence=0.95
all 0.0          -> tier=instant  confidence=0.95
routing_changed_by_adapted_thresholds: false
```

*(A first version of this probe used an input that fell to the fallback tier, which consults no threshold at all — that run was vacuous and was discarded rather than reported.)*

**(b) The input is a constant.** See Q4.

> **Q3 verdict: the objective is auditable and clearly stated in code. It optimises a number that nothing reads, from a signal that never varies.**

---

## Q4 — Can the loop game its own metric?

**It does not need to. The metric is already pinned at its maximum, permanently.**

The coupling is not subtle and it is worse than the question anticipates.

### The traced coupling

`router.py:917` — `def _record_metric(self, tier, latency_ms, success: bool = True)`.

An AST walk of the module finds **8 call sites, and not one of them passes `success`** (VERIFIED-RUNTIME, probe P8):

| call site | positional args | passes `success`? |
|---|---|---|
| `router.py:285` (cache) | 2 | no |
| `router.py:448` (recipe) | 2 | no |
| `router.py:515` (plan) | 2 | no |
| `router.py:554` (tier 0) | 2 | no |
| `router.py:584` (tier 1) | 2 | no |
| `router.py:706` (tier 2) | 2 | no |
| `router.py:742` (tier 3 async) | 2 | no |
| `router.py:819` (tier 3 sync) | 2 | no |

So `router.py:926` — `self._epoch.record(tier.value, success, latency_ms)` — passes the literal default `True` on every route, forever. **The reward signal is a constant.**

### It is a constant even when the operation demonstrably failed

**Probe P7b (VERIFIED-RUNTIME).** A router given a `command_fn` that always fails, driven with six real recipe triggers. In all six the route genuinely failed — `RoutingResult.success == False`, `failed_step == 1`, the answer string tells the artist to undo. The adapter was told `True` in all six:

```
"create a controller"      recipe=null_controller          success=False -> adapter told True
"set up a camera"          recipe=camera_rig               success=False -> adapter told True
"setup a terrain"          recipe=terrain_environment      success=False -> adapter told True
"create a null controller" recipe=null_controller          success=False -> adapter told True
"set up color correction"  recipe=color_correction_setup   success=False -> adapter told True
"set dressing"             recipe=solaris_scatter_instances success=False -> adapter told True
```

**Probe P7a — a second, deeper layer of the same blindness.** On the Tier 0 path the `RoutingResult` itself is dishonest before the adapter ever sees it. `_try_tier0` hardcodes `success=True` (`router.py:538`) without consulting the responses it just collected:

```
input:                        "delete /obj/thing1"
underlying response.success:  [False]
underlying response.error:    ["probe: forced failure"]
RoutingResult.success:        True        <- router.py:538
adapter told:                 [("instant", True, 0.719)]
```

This is a Law 3 violation on the live path: a status describing what was attempted, not what happened.

**Probe P5 — failures are not merely mislabelled, they are invisible.** The `no_tier_matched` fallback (`router.py:367-373`) returns `success=False` and **never calls `_record_metric` at all**. `total_routes` was 0 before and 0 after. Genuine routing failures do not even enter the sample.

### The consequence

Success rate is therefore always exactly `1.0`, which is `> HIGH_SUCCESS_THRESHOLD` (0.9), so `adjust()` takes the "great performance" branch on every epoch for every tier. **Probe P4 (VERIFIED-RUNTIME)** — 300 outcomes at `epoch_size=10`, feeding exactly what the router feeds:

```
0.45 → 0.40 → 0.35 → 0.30 → 0.25 → 0.20 → 0.15 → 0.10 → 0.10 → 0.10 → … (30 epochs)
monotonic_non_increasing: true    final: 0.10 (the clamp floor, adaptation.py:111)
```

It is not an adaptive controller. It is a **one-way ratchet to the floor**, and it would reach the floor in 8 epochs and stay there for the life of the process.

> **Q4 verdict: coupling confirmed and named. The component that routes also authors the outcome, and authors it as a hardcoded literal — `router.py:917` default, unoverridden at all 8 sites in `router.py`. The loop cannot observe failure of any kind, so its metric is not gameable; it is already saturated.**

---

## Q5 — What reverses a bad adaptation?

**Nothing. And nothing needs to, only because the output is currently unread.**

| property | state | anchor |
|---|---|---|
| persisted? | **no** — memory only, dies with the process | `adaptation.py:121-126`; probe P1 |
| versioned? | **no** — no snapshot, no epoch tagging of thresholds | `adaptation.py:98-112` |
| bounded? | **partly** — `_epoch_history` is a `deque(maxlen=100)`; thresholds clamped to `[0.1, 1.0]` | `adaptation.py:38,125,108,111` |
| rollback path? | **none** — `adjust()` mutates in place; no prior value is retained | `adaptation.py:104-112` |

There is no mechanism that restores epoch 39 after epoch 40. The *de facto* reversal is **process restart**, which is total amnesia rather than rollback: probe P1 drove an adapter through three failing epochs to `thresholds={'instant': 0.8}`, then constructed a fresh adapter in the same process — `epoch_id=0`, `thresholds={}`.

That is the R91/R93 shape exactly, with one mitigating accident: **the blast radius is currently zero because nothing consumes the output (Q3a).** The instant anyone wires `TierThresholds.get()` into `router.py:523`, this becomes a live mechanism with no reversal, no persistence, and — given Q4 — a guaranteed one-way drift to the clamp floor.

> **Q5 verdict: no reversal exists. The mechanism is safe today only by virtue of being disconnected.**

---

## Q6 — Is `evolution.py` still firing?

**Verified, not cited — and the answer splits: the detector fires on the live default configuration; the converter does not.**

### The claim, tested with the negative control the test does not have

`tests/test_moneta_crucible.py:256` asserts `check_evolution` is never called under `SYNAPSE_MEMORY_BACKEND=moneta`. It has no paired control proving the call *does* happen otherwise — so on its own it could pass vacuously. Supplying that control (VERIFIED-RUNTIME, probe Q6, 25 `add()` calls per arm):

| backend | store class | `check_evolution` calls |
|---|---|---|
| `moneta` | `MonetaBackedStore` | **0** |
| `jsonl` *(negative control)* | `MemoryStore` | **2** |
| unset *(the live default)* | `MemoryStore` | **2** |

**The claim holds, and the test can fail.** Two calls at 25 adds is exactly right: `store.py:525` fires every `_EVOLUTION_CHECK_INTERVAL = 10` adds (`store.py:165`).

### But the flag is not set, so evolution IS on the live path

- `store.py:810` — `os.environ.get("SYNAPSE_MEMORY_BACKEND", "jsonl")`. **The default is `jsonl`, not `moneta`.**
- On this machine, right now: `SYNAPSE_MEMORY_BACKEND` is **unset** (`None`).
- `.synapse/config.yaml:17` says `memory_backend: "flat"` — a **different key that the store selector never reads**. It is not a moneta selector and does not change the backend.
- Moneta itself *is* importable here (`moneta_runtime.moneta_available() → True`), so the flag is the only thing standing between the two paths.

So the deprecated mechanism is live by default, and the docstring's own condition for removal — "*will be removed when `SYNAPSE_MEMORY_BACKEND` defaults to `moneta`*" (`evolution.py:14-16`) — **has not been met**.

### What "firing" actually amounts to

Both automatic call sites invoke only the **detector** and then log a recommendation:

- `store.py:530-547` — calls `check_evolution`, and on `should_evolve` emits `logger.info("Memory evolution triggered: …")`. It does not convert.
- `memory/scene_memory.py:486-500` — background thread, calls `check_evolution`, logs `"… Call synapse_evolve_memory to upgrade."`. It does not convert.

The **converter**, `evolve_to_charmeleon` (`evolution.py:217`), has exactly one caller in the tree: `server/handlers_memory.py:263` — inside `_handle_evolve_memory`, reachable only through the explicit `synapse_evolve_memory` tool, and **gated behind `dry_run` which defaults to `True`** (`handlers_memory.py:252`). No automatic path can reach it.

No `memory.usd` artifact exists anywhere outside pytest temp directories.

> **Q6 verdict: WIRED true, FIRES true (detector, ~2 calls per 25 memory writes on the default backend), MODIFIES SOMETHING false on every automatic path. The deprecated RSI mechanism is alive, running, and producing log advice that nothing acts on.**

---

## A finding the leg was not looking for: pytest writes into the operator's production log

`core/logfile.py:60` attaches the rotating file handler to `~/.synapse/logs/synapse.log` **whenever it is called** — and the test suite imports and exercises the same modules. The result is 4,795 `Epoch N complete` records in the operator's live audit trail that were authored by unit tests.

This is not cosmetic. **Grepping the production log for evidence that the RSI loop is running returns 4,795 hits, all false.** This audit's first pass read those hits as production traffic and had to be reversed by examining the epoch-size fingerprints. Any future investigator — human or agent — takes the same bait.

The contaminated log is the same file `server/doctor.py` and `server/telemetry_dump.py` point operators at.

**Truth tier:** VERIFIED-RUNTIME. **Anchors:** `core/logfile.py:60-95`; `~/.synapse/logs/synapse.log` (4,540,722 bytes at time of audit).

---

## What this leg did not do

Not building. Not fixing. Not designing a new loop. Nothing in `python/`, `tests/` or `shared/` was modified; the only writes are this file and `harness/notes/receipts/RSI0.json`.

**One question left open and named rather than guessed:** the epoch-line decomposition implies `test_v5_features.py::TestEpochAdaptation` ran 185 times against 28 runs of `test_routing.py::test_epoch_history_capped`. Log rotation truncates the history (`.log.2` is absent), so the ratio is not independently confirmed. The Q1 conclusion does **not** rest on it — proofs 1 and 2 (impossible epoch sizes; no `Epoch 2` at size 100 across 185 occurrences) are each sufficient alone.

---

## The sentence this leg exists to produce

**SYNAPSE has three RSI mechanisms. One has never completed a cycle in production and writes to a value nothing reads. One cannot be reached by any live code path. One runs on every memory write and ends in a log line. Nothing in this codebase has ever improved itself.**
