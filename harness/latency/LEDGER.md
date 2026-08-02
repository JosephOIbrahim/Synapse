# LATENCY LEDGER — scale-parameterized

**Produced by:** 20-agent fan-out `wf_b9c32632-1fc` (5 mappers → 9 prospectors → 4
adversarial crucibles → 2 instrument designers), read-only, 2026-08-02. Raw results:
the run's `journal.jsonl`. Every number below names its producer (Law 2). Verdicts
are the CRUCIBLES' — each hypothesis was attacked by 4 independent adjudicators
before it earned a row here.

---

## 1. The headline: the contradiction is RESOLVED — both sides were part right

The 07-27 report's "Houdini-side work is milliseconds, tuning it is tuning the 5%"
**holds on small scenes and breaks in a real large-scene regime** — but the regime's
axis is not what anyone assumed:

- **The regime is real and per-op.** `Flatten()` uncached: **330–347 ms per call**
  across 5 warm repeats on a 10k-prim stage `[C2 crucible, live probe, wf_b9c32632-1fc]`.
- **The axis is WRONG in the shipped gate.** Cost tracks **authored array volume,
  not prim count**. Measured at identical apparent content (10,000 spheres):
  inline 10,626 prims → 358.8 ms; instanceable=True 101 prims → 5.0 ms;
  payload-unloaded 101 prims → 0.5 ms `[C2, same probe]`.
- **The shipped 4× gate has a bypass class.** A 4-prim PointInstancer at 2,000,000
  instances costs **2,017.9 ms/op** while `_stage_exceeds(stage, 10000)` returns
  **False** — the reduced path would cost 0.06 ms, a **16,677× miss**
  `[C2; real gate _DEFAULT_STAGE_HASH_PRIM_THRESHOLD=10_000 at shared/bridge.py:422 — :427 is a sentinel, a correction G1 made to this harness's own scaffold]`. The gate must re-key on array volume.

**Ruling (C2, severity 4/5): re-parameterize, do not re-litigate.** The scale
dimension is real; every hypothesis and the shipped gate key on the wrong variable.


### 1.5 The anatomy audit of the 4x win itself `[G1-pr61-anatomy, wf_b9c32632-1fc]`

- **The crossover is not exotic — it is the committed default.** The gate fires at
  10,000 prims (`shared/bridge.py:422`), silently switching hash algorithm. Neither
  env override is set anywhere in deploy config, so the compiled-in default runs.
- **The honesty fields are recorded and consumed by NOTHING.** `stage_hash_mode` /
  `stage_hash_full_fidelity` / `composition_checks_reduced` are set (`:530-535`) but
  `anchors_hold` and `fidelity` ignore them (`:537-556`) — a reduced-fidelity op
  finalizes as verified, fidelity 1.0.
- **CORRECTION (2026-08-02, caught by the R306 lane).** This section originally added
  that `panel/session_integrity.py:66` "filters `delta_hash='no_change'` OUT of
  mutation accounting, so the blind-spot case is discarded." **That was wrong**, and
  it was inherited from a fan-out result and published here without my verifying it.
  Reading `session_integrity.record()`: mutations are counted unconditionally at
  `self._total += 1` (`:53`) BEFORE any filter; the `:66` check excludes the sentinel
  strings `""` / `"no_change"` / `"rolled_back"` from `_node_paths` — a NODE-PATH
  extraction guard reading `scene_hash_before/after`, not `delta_hash`, and correct
  as written (a sentinel is not a path). The real gap was narrower and still real:
  nothing reported HOW MANY ops ran in reduced mode. That is what R306 adds.
- **Three passes still run unbounded per stage-touching op**: the reduced signature
  `TraverseAll` x2 (`:986`, ~9.0-9.5 us/prim/pass — extrapolates ~18 s/op at 1M
  prims), `_verify_composition`'s `Traverse` (`:2167`, deliberately ungated, inside
  the open undo group, NEVER measured), and the `node.children()` loop (`:814-818`).
- **Two doc-drift defects introduced by 98b556f**: `bridge.py:449-450` and
  `:2137-2139` still describe the pre-commit unbounded default; the second is
  dangerous — it says the composition-sweep shed never fires by default, false
  above 10k prims.

## 2. The second headline: the 07-27 report's own #1 lever is REFUTED

The report's top recommendation — *"extend declarative coverage per-domain"* — was
killed by its own prospector and the kill was confirmed by 3 of 4 crucibles
`[H7 → C1 KILLED, C2 KILLED, C4 KILLED]`:

- The claim "declarative collapse is banked for Solaris only" is **factually wrong
  on the coverage axis** — `GraphBuilder.instantiate`
  (`python/synapse/host/graph_builder.py:94-202`) is domain-generic: no LOP/USD/
  Solaris token anywhere in the build path.
- `synapse_batch` **already covers COPs/TOPS in ONE round-trip and is already in
  the prompt.** Extending propose→instantiate there would **ADD one LLM round-trip
  per build** — at the report's own T1 class, that is **seconds LOST, not saved**
  `[H7 prospector; report line 31 vs claude_worker multiplexing]`.

**Do not pull this lever for latency.** (Steering/policy residue is a separate,
non-latency question.)

## 3. The ranked action list (C4, adversarially adjudicated)

Assumption stated by the ranker: no hypothesis has a measured absolute-seconds
figure until the usage instrument lands, so ranking is bin × mechanism-certainty ×
effort. Full reasoning: journal, C4 result.

| # | action | bin | size | note |
|---|---|---|---|---|
| 1 | **`cache_control` breakpoint on the last block of the last message** (`anthropic_provider.py:52-71` `_with_prompt_cache`) | **T1** | ~4 lines | Accumulated tool_results become cache READS instead of full re-prefill on every one of up to 25 iterations — collapses the O(K²) prefill term. Assumes vendor cache reads cut latency, not just price. |
| 2 | **`message_start` usage capture** (input/cache_read/cache_creation/output tokens) onto StreamProvider | instrument | small | Saves 0 s itself; it is the ONLY producer that can price rank 1, and it closes U1/U3's blocker. |
| 3 | H6 probe: un-stub `_handle_message` in a scratch copy of `tests/test_websocket_cancel_reachable.py` | T3 | offline | The stub at :157 is what hid the cancel-unreachable defect. Decisive, no bridge needed. |
| 4 | H5(a): repair-or-delete the `attr.floatListData()` phantom + rulebook/phantoms.json entry | correctness | 1 identifier | Deterministic, no probe needed. |
| 5 | H3 free-half: cache `_stage_exceeds` in the per-op thread-local (~2 ms/op above threshold), assign `composition_valid` (currently **zero assignment sites** — verified), fix the stale docstring | T4 + honesty | small | |
| 6 | **Shared T4 instrument**: timers on `_verify_composition` + `_infer_stage_touch` with NON-saturating buckets | instrument | small | One change prices H1+H2+H3 at once. Existing histograms saturate at 4000–5000 ms `[G4]`. |
| 7 | H1/H2 hython probes (one line each) | T4 | trivial | Kill-or-confirm single terms. |
| 8 | H5(b): port the Mile-3a `include_geometry` gate onto `inspect_selection` | T4 | ~6 lines | Dies if `_geometry_summary` < 70 ms at 1M points — probe first. |
| 9 | H3 gating-half: scope composition validation to the mutation subtree | T4 | careful | Largest T4 seconds, ranked LOW: only item that can create a NEW integrity blind spot. Probe (>100 ms @100k, H3's own decision threshold `[C4]`) must justify it first. |
| 10 | H6 fix-half: control-plane lane + data-plane worker on the WS loop | T3 | largest | Bounded seconds large in the artist's currency (cancel a render sequence), highest effort. |
| 11 | H4 fix-3: payload budget with stamped degradation | T1 | risky | Only fix that can make the agent WORSE (silently blinded model); last. |

**Plus the gate re-key from §1** (array-volume term in `_stage_exceeds`) — surfaced
by C2 after C4 ranked, so it carries no rank yet; its mechanism evidence is the
strongest on the board (16,677× measured miss).

## 4. Verdict table (all 9 hypotheses × 4 crucibles)

| id | prospector | C1 refuted-check | C2 scale-attack | C3 measurable | C4 rank | net |
|---|---|---|---|---|---|---|
| H1 double-topo-hash | REAL_AND_OPEN | DOWNGRADED (3/4 self-refuted) | BLOCKED_ON_INSTRUMENT | SURVIVES | DOWNGRADED | residue only |
| H2 blast-radius | REAL_AND_OPEN | SURVIVES | BLOCKED_ON_INSTRUMENT | SURVIVES | BLOCKED_ON_INSTRUMENT | probe first |
| H3 composition-validation | REAL_AND_OPEN | SURVIVES | **SURVIVES (probe ran)** | SURVIVES | SURVIVES | **open, strongest T4** |
| H4 observation-payload | REAL_AND_OPEN | SURVIVES | SURVIVES | DOWNGRADED (split) | SURVIVES | **open, rank 1 fix** |
| H5 residual-serialization | REAL_AND_OPEN | SURVIVES | SURVIVES | SURVIVES | DOWNGRADED (split) | open, 2 halves |
| H6 mainthread-queue | REAL_AND_OPEN | SURVIVES (corrects ground) | SURVIVES | **SURVIVES (strongest)** | SURVIVES | **open** |
| H7 declarative-coverage | **REFUTED (self)** | KILLED | KILLED | confirmed | KILLED | **dead — negative win** |
| H8 perceived-latency | REAL_AND_OPEN | DOWNGRADED | SURVIVES | DOWNGRADED (split) | not ranked (UX track) | UX track, own currency |
| H9 schema-prefill-tax | REAL_AND_OPEN | DOWNGRADED | BLOCKED_ON_INSTRUMENT | BLOCKED_ON_INSTRUMENT | DOWNGRADED | folded into H4 |

## 5. Instrument state at HEAD `92d497e` (G4, verified against tree — not the report)

- **U1 TTFT**: ABSENT. Zero `ttft|time_to_first_token` symbols repo-wide. Natural
  hook exists unused: `synapse_panel.py:1944-1947` (`_on_token` flips
  `_streaming_started`), t0 at `:1942` (`self._worker.start()`).
- **U2 turns-per-build**: ABSENT — still log-only, now at `claude_worker.py:225-229`
  (the report's `:190-196` citation has drifted; iteration cap is `:35` not `:34`).
- **U3 provider stream timer**: ABSENT — zero timing in any of the six providers.
- **U4 percentiles**: ABSENT; and every existing histogram **saturates at
  4000–5000 ms**, useless for the T4 regime.
- New since the report (its "unchanged" is stale in one direction): a fourth timing
  histogram `main_thread_hold` landed 2026-08-01 at `8239410`.

## 6. Standing refuted — carried forward, do not re-propose

- **Batching for latency** (PR #28 adversarial kill; worker already multiplexes —
  `claude_worker.py:139-185`). Confirmed intact by C1.
- **H7 as posed** (this run — see §2).
- **U5/U6/U7** stay parked behind their numeric reopen-gates; U6's anchor must be
  re-stated before use.

---

## 7. The scale curve, MEASURED (R305 lane I1 — the missing denominator)

Sections 1–6 established that the axis is **authored array volume, not prim
count**, from live probes. This section is the first *swept* measurement of that
axis: an offline, deterministic, counted sweep that emits the CURVE (intercept +
slope + r² per counter) rather than two endpoints.

**Producer for every number in this section:**
`python scripts/bench_scale.py --json-out -`
(equivalently `python _benchmark_latency.py --tier offline --json-out -`).
Instrument `scripts/bench_scale.py::measure_rung`, driving the real
`LosslessExecutionBridge.execute()` through `tests/perf_counters.py`'s fake-hou
seam. Interpreter CPython 3.14.2, git `a34d1c3`, builder `bce16327b2f14e0f`.

**These are COUNTS, not milliseconds.** The offline tier emits no wall-clock key
of any kind — `bench_scale.assert_record_honest` raises on one, and
`tests/test_bench_scale.py` scans the whole emitted run to prove it. Nothing in
this section is quotable as a latency figure.

### 7.1 The volume axis, with prim count HELD CONSTANT at 4

The sweep the earlier design could not produce, because it parameterized by prim
count alone. Four prims is 2,500× below the shipped 10,000-prim gate, so the prim
term **cannot** fire anywhere on this sweep — every response below is the volume
term or nothing.

| authored elements | gate mode | `flatten_exports` | `value_reads` | `prim_visits` |
|---|---|---|---|---|
| 100,000 | full | 2 | 4 | 12 |
| 200,000 | full | 2 | 4 | 12 |
| 500,000 | full | 2 | 4 | 12 |
| 1,000,000 | **reduced** | **0** | 3 | 19 |
| 4,000,000 | **reduced** | **0** | 1 | 17 |

- **The gate flips on volume alone.** `flatten_exports` 2 → 0 between 500,000 and
  1,000,000 authored elements at **four prims** — exactly where a prim-keyed gate
  answers False. The H10 bypass class, now a swept curve rather than a single
  repro `[C2]`.
- **Below the gate every counter is FLAT** (slope 0/element, r² 1.0 across
  100k–500k) while the *real* cost grows linearly in volume `[section 1: 100k
  elements = 46.0 ms/hash … 4M = 1361.5 ms/hash]`. That gap is the instrument's
  stated precision limit, not a finding — §7.4.
- **`value_reads` 4 → 3 → 1** is the volume probe short-circuiting earlier as
  arrays get bigger: `_stage_volume_exceeds` accumulates until
  `total > threshold`, reaching its verdict at attribute 3, then at attribute 1.
  The probe gets *cheaper* as the stage gets *heavier*.

### 7.2 The prim axis, with authored volume held at ZERO

| prims | gate mode | `flatten_exports` | `prim_visits` | `prim_state_reads` | `attrs_examined` |
|---|---|---|---|---|---|
| 100 | full | 2 | 300 | 200 | 100 |
| 1,000 | full | 2 | 3,000 | 2,000 | 1,000 |
| 10,000 | full | 2 | 24,097 | 20,000 | 4,096 |
| 10,001 | **reduced** | **0** | 40,004 | 80,008 | 0 |
| 20,000 | **reduced** | **0** | 70,001 | 160,000 | 0 |

Per-regime slopes. A single slope across the boundary averages two different
algorithms and is **not** quotable — the instrument refuses to present one:

| counter | below gate (100→10,000) | above gate (10,001→20,000) |
|---|---|---|
| `prim_state_reads` | **2.0** /prim (r² 1.0) | **8.0** /prim (r² 1.0) |
| `prim_visits` | 2.38 /prim (r² 0.9995) | **3.0** /prim (r² 1.0) |
| `attrs_examined` | 0.379 /prim (r² 0.982 — SATURATING) | 0 |
| `flatten_exports` | 2 (constant) | 0 (constant) |

- **The price of the 4× win, in counted units, stated for the first time.**
  Crossing at 10,000 → 10,001 removes 2 `Flatten` calls *and* quadruples per-prim
  state reads (2.0 → 8.0/prim), raising prim visits 24,097 → 40,004. The win is
  real and it is a trade, not a free lunch.
- **`attrs_examined` saturates at 4,096** — that is
  `_STAGE_HASH_VOLUME_ATTR_BUDGET` `[shared/bridge.py:596]` visible in a curve.
  Its r² of 0.982 is the flag: a linear slope on a saturating counter reads as a
  growth rate it does not have, so fit quality ships beside the fit.
- **Above the prim gate `attrs_examined` is 0** — the prim probe returns True
  first, so the volume probe never runs at all.

### 7.3 What the offline tier may NOT claim

- No wall-clock. Not one key. Enforced in the emitter, pinned by a test that
  feeds it a poisoned row.
- No share-of-turn / percent-of-wall-clock at ANY tier: there is no
  absolute-seconds producer for the LLM turn at HEAD, and the bench prints
  `T1_reference: UNAVAILABLE` rather than omitting it silently.
- No cross-tier comparison. Live rows carry `cross_tier_comparable: false` and a
  different `builder_sha256` by construction; `fit_curve` refuses to place rows
  from two builders on one curve.

### 7.4 The stated precision limit — read this before quoting §7.1

`flatten_exports` counts **calls** to `stage.Flatten().ExportToString()`. It does
**not** price the bytes that call serializes. On the volume axis the counters
move because the **gate responds**, not because this instrument timed a Flatten.
Reading the flat 100k–500k row as "volume is free" would be exactly the error the
07-27 report made — the real cost over that same span is `46.0 → 232.9 ms/hash`
`[section 1, C2 probe]`. Pricing volume needs the LIVE tier or a pxr-present
envelope probe; the counted tier's job is to show WHERE the algorithm changes,
and it does that deterministically, on any interpreter, with no Houdini present.

### 7.5 What did NOT get measured (stated, not omitted)

- **The LIVE tier is UNEXERCISED.** `_benchmark_latency.py --tier live` was
  written and never run — no bridge was reachable in this lane. It emits nothing
  and returns 2 when the socket is absent. No live number from it exists anywhere
  in this repo, and none may be cited until someone runs it.
- **The in-process L0b arm is NOT built.** The stage-hash term is ABSENT BY
  CONSTRUCTION on the live WS path `[python/synapse/server/integrity_envelope.py:219
  — _compute_scene_hash(target, include_stage=False)]`, so no live WS run can ever
  price it. Reaching it needs `bridge.execute()` under hython.
- **No pxr-present envelope probe.** The counted tier cannot rank a Flatten byte
  against a prim visit; nothing here attempts to.
