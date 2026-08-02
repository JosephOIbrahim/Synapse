# BENCHMARK DESIGN — SCALE ADDENDUM

**`docs/BENCHMARK_DESIGN_SCALE_ADDENDUM.md`** · R305 lane I1 · 2026-08-02 · base `a34d1c3`

This is an **addendum**, not an edit. `docs/BENCHMARK_DESIGN.md:51` freezes its
contract — *"critics may attack; builders may NOT change"* — so the scale axis is
stated here and the frozen spec is left alone.

---

## Why the frozen latency track has no scale term

`docs/reviews/synapse-latency-report-2026-07-27.md:20` states T4 = **"1–70 ms per
op"** with no scene-scale term at all. That missing denominator is what let a
6.9–7.7 s per-op cost coexist with a ledger calling the same bin "the 5%".

The frozen track could not have caught it, for a **structural** reason rather
than a sizing one. `_benchmark_latency.py`'s legacy sequence benchmarks
`set_parm` on an `/obj` null. `shared/bridge.py::_infer_stage_touch` only sets
`stage_path` when a `hou.LopNode` appears within depth 3 downstream; an `/obj`
null has none, so the hash target stays `/obj` and the stage block never runs.

**The bench is not "missing a bigger scene." It is pointed at a path that has no
stage term at all.** The scale arm reaches the stage term by pointing at a LOP —
it does not "fix" `_infer_stage_touch`, and nothing in this addendum changes
`shared/bridge.py`.

---

## The axis is AUTHORED ARRAY VOLUME, not prim count

The original I1 design parameterized by prim count. **That is now known wrong on
its central axis.** Measured (`harness/latency/LEDGER.md` §1, producer: C2
crucible live probe):

| same apparent content | prims | cost |
|---|---|---|
| 10,000 inline spheres | 10,626 | 358.8 ms |
| the same, `instanceable=True` | 101 | 5.0 ms |
| 4-prim PointInstancer @ 2,000,000 instances | 4 | 2,017.9 ms — prim gate says **False** |

The shipped gate now carries **both** terms — `_stage_exceeds` (prims) and
`_stage_volume_exceeds` (authored array volume). A bench parameterized only by
prim count would reproduce the exact blind spot it exists to remove, so the
sweep carries both axes and the emitter **rejects** any rung declaring a prim
count with no `authored_elements`.

The volume sweep holds prims **constant at 4** — 2,500× below the 10,000-prim
gate — so the prim term cannot fire anywhere along it. Any response is the volume
term or nothing. That is what makes the curve *show* the axis instead of
asserting it. Result: `harness/latency/LEDGER.md` §7.1.

---

## Two tiers, and the honesty boundary between them

| quantity | OFFLINE (counts) | LIVE (wall-clock) |
|---|---|---|
| algorithmic work per op (traversals, prim visits, Flatten **calls**) | **YES — exact, deterministic, host-independent** | no |
| gate regime + where the algorithm changes | **YES** | yes |
| milliseconds of anything | **NO — not one key** | yes, build-stamped |
| cost of the bytes a Flatten serializes | **NO** | yes |
| share-of-turn / percent-of-wall-clock | **NO** | **NO** |
| LLM turn (T1) | **NO** | **NO** |

**Enforced in code, not in prose** (`scripts/bench_scale.py::assert_record_honest`):

1. An **offline** record carrying any `*_ms` / `*_seconds` / `*_latency` /
   `*_duration` key — at any nesting depth — raises. An offline tier that reports
   latency numbers is the exact dishonesty this repo guards against.
2. A record of **any** tier carrying a share-of-turn or percent field raises.
   There is no absolute-seconds producer for the LLM turn at HEAD, so the bench
   prints `T1_reference: UNAVAILABLE` — an explicit refusal, never a silent
   omission.
3. A record whose `producer.cmd` / `git` / `interpreter` / `builder_sha256` /
   `producer_path` is empty raises (Law 2).
4. A rung with `prim_count` and no `authored_elements` raises (the H10 blind
   spot).

Each of the four is pinned by a test that feeds the emitter a poisoned row and
expects it to raise (`tests/test_bench_scale.py::TestEmitterHonesty`).

---

## One counter vocabulary

The counters, the counting fakes and the module-attribute seam are **imported
from `tests/perf_counters.py`** — the armed perf ratchet's instrument — never
re-declared. Two vocabularies is how the ratchet and the bench drift apart, and
`tests/test_bench_scale.py::TestSharedVocabulary` asserts `bench.COUNTERS is
pc.COUNTERS` (identity, not equality).

`tests/perf_counters.py` is **not modified**. The armed instrument stays
byte-identical; the bench composes volume-bearing fakes on top of it and adds no
scenario to `SCENARIOS`.

**The seam is module attributes on `shared.bridge`, never `sys.modules['hou']`** —
the documented fake-residency trap (`tests/conftest.py`). A sweep that leaked
either the env pins or the fake-hou globals would poison every measurement after
it; both are pinned by tests.

---

## Extend, never rebuild

`docs/BENCHMARK_DESIGN.md:140` forbids the rebuild. Both root scripts keep their
entry points, their `benchmark()`/`send_command()` machinery, their
`WARMUP`/`ITERATIONS`/statistics code, and their **exact** no-argument op
sequence. `tests/test_bench_scale.py::TestLegacySequenceUnchanged` monkeypatches
the call surface and compares the ordered call list against a frozen literal —
this is the binary "extend, never rebuild" check, for both scripts.

The `websockets` import became **lazy**. It sat at module top, which made
`--help` exit non-zero wherever websockets is absent (hython, a pxr-less CI leg)
— the single thing `harness/latency/verify.py::p5_offline_bench` gates on. A test
asserts no websockets import appears above `_connect`.

Latent bug fixed while extending `_benchmark_api.py`: it called
`urllib.parse.urlencode` while importing only `urllib.request`/`urllib.error`. It
worked *only* because importing `urllib.request` binds `parse` on the package as
a side effect. `import urllib.parse` is now explicit.

---

## Deliberate non-goals

- **Not a gate.** `harness/verify/perf_ratchet.py` is the gate; this bench is the
  map. Nothing here reads or writes `harness/verify/perf_baseline.json`, and the
  armed floor is untouched.
- **Not a change to the frozen op set** (`docs/BENCHMARK_DESIGN.md:73`) or the
  L0/L1/L2 arm definitions. The scale axis is orthogonal: the same ops run in
  differently-sized scenes.
- **Not a fix for any hypothesis.** This instrument measures. It changes no
  behaviour in `shared/bridge.py`, adds no timer to product code, and does not
  move the gate.
- **Not an edit** to `docs/BENCHMARK_DESIGN.md` or to the 07-27 report. Both are
  frozen / human-gated; this file is the addendum instead.

---

## Open, and stated rather than hidden

- **The LIVE tier is UNEXERCISED.** `_benchmark_latency.py --tier live` was
  written and never run — no bridge was reachable in this lane. It refuses and
  returns 2 when the socket is absent. **No live number from it exists in this
  repo and none may be cited until someone runs it.**
- **The in-process L0b arm is not built.** The stage-hash term is ABSENT BY
  CONSTRUCTION on the live WS path
  (`python/synapse/server/integrity_envelope.py:219` passes
  `include_stage=False`), so no live WS run can price it at any scale. Reaching
  it needs `bridge.execute()` under hython. The live arm prints that verdict
  rather than presenting a flat curve as a null result.
- **No pxr-present envelope tier.** The counted tier cannot rank a Flatten byte
  against a prim visit and does not try.
- **Build pin drift.** `harness/state/drop.json` does not exist in this tree.
  `CLAUDE.md` states the target as Houdini 22.0.368; this host runs 22.0.397. The
  live arm reads `hou.applicationVersionString()` and prints the drift against
  the doc pin; it never assumes a build.
- **`harness/latency/REGISTRY.json` was not touched.** Its `ratchet` block is
  fenced to another lane, and wiring the H1/H2/H3/H5 `probe` fields to the new
  bench command is a followup, not this lane's write.

---

## Run it

```
python _benchmark_latency.py                       # legacy run, unchanged
python _benchmark_latency.py --tier offline        # the counted scale sweep
python _benchmark_latency.py --tier offline --json-out -
python _benchmark_latency.py --tier offline --axis volume --volume 25000,250000,1000000
python scripts/bench_scale.py --help               # the core, standalone
```

Needs no Houdini, no bridge, no pxr and no websockets.
