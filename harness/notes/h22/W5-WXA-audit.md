# W5-WXA — crucible shard A: acceptance-1 contracts re-executed first-hand

**Leg:** W5-WXA (wave5/wxa) · **Band:** TRUTH · **Model:** Opus 4.8
**Audits:** the `wave5/measures` cook-verify charter delivered at `520a10d4` (product `a6db2286`)
**Method:** first-hand re-execution in a side worktree — never inherited (crucible criterion 1).

---

## Method — the side tree

`wave5/measures` was **already checked out** at `.claude/worktrees/w5-measures`, so the
brief's `git worktree add _m wave5/measures` would have failed (branch-in-use). Used
`git worktree add --detach _m 520a10d4` instead — **semantically identical** for read-only
re-execution, moves **no ref**, and honors "never touch wave5/measures state". Everything below
ran in `_m` (the branch's own tree at its tip); my products commit to `wave5/wxa` only.

- Module under audit: `_m/python/synapse/validation/measures.py` (261 L) + `_m/python/synapse/validation/explosion.py` (174 L)
- Test slice: `_m/tests/test_measures_contracts.py` (24 tests) + `_m/tests/test_phase3_exposure.py` (12 tests)
- Builder receipt (claims audited): `_m/harness/notes/receipts/W5-MEASURES.json`
- Interpreter: Python 3.14.2 (headless; the live hython cook that PRODUCES observations is `gui_required` → legitimately UNKNOWN here — I audit the JUDGEMENT half only).

---

## Target 2 — contract slice re-executed FIRST-HAND

```
python -m pytest tests/test_measures_contracts.py tests/test_phase3_exposure.py -q   @ _m/520a10d4
=> 36 passed, 0 failed, 2 warnings in 0.58s   (24 measures-contract + 12 exposure)
```

**PASS.** Count matches the builder's `M-E1` claim exactly (36 passed;
`W5-MEASURES.json:72`). Confirmed first-hand, not inherited:

- Acceptance 1 — all 5 output kinds present, each with an UNKNOWN condition; every kind
  renders UNKNOWN (not a fabricated pass, not zero) on the **absent** observation
  (`test_missing_observation_renders_unknown_not_pass`, parametrized ×5).
- Acceptance 2 — the explosion detector fires on the exploding golden (`signal=ke_growth`,
  `offending_frame=5`) and stays STABLE on the healthy one.
- Acceptance 3 (extends-not-forks) — `test_phase3_exposure.py` byte-green; the tier ladder
  emits existing `synapse.science.exposure` rungs without editing that module.

The 2 warnings are ambient (vendored-SDK ABI mismatch on Py3.14 + a pytest-asyncio
deprecation), not this leg's — see `_m/tests/conftest.py:507`.

---

## Target 3 — adversarial malformed-input matrix (FIRST-HAND)

Probe: `harness/probes/wxa/adversarial_matrix.py` (17 cases) · raw output:
`harness/probes/wxa/matrix_results.txt`.

The builder fixtured **absent** and present-but-**hollow/empty** inputs (`{}`, `[]`,
`{"R":{}}` stats; too-few-frames; KE-gaps — `test_measures_contracts.py:155-199`).
The matrix attacks a class the builder did **not** fixture: present-but-**wrong-TYPE**
observations. Tally: **CRASH 9 · MEASURED 4 · FAIL 3 · UNKNOWN 1.**

| case | contract | input | outcome |
|---|---|---|---|
| img/stats-scalar | image | `stats=0.5` | **MEASURED** (soft) |
| img/res-noniter | image | `resolution=1080` | FAIL (graceful) |
| img/res-string-elems | image | `resolution=["a","b"]` | FAIL (graceful) |
| sim/frames-string | sim | `frames="boom"` | **CRASH** `AttributeError: str.get` |
| sim/frames-list-nondict | sim | `frames=[42,43]` | **CRASH** `TypeError: not a container` |
| sim/frames-int | sim | `frames=7` | **CRASH** `TypeError: int not iterable` |
| geo/bbox-noniter | geometry | `bbox=5` | **CRASH** `TypeError: list(int)` |
| geo/bbox-string | geometry | `bbox="box"` | **MEASURED** (soft) |
| geo/weightsum-string | geometry | `weight_sum="1.0"` | **CRASH** `TypeError: isclose(str)` |
| geo/counts-zero | geometry | `point/prim=0` | **MEASURED** (CORRECT) |
| chan/range-noniter | channels | `range=5` | **CRASH** `TypeError: list(int)` |
| chan/range-short | channels | `range=[1]` | **CRASH** `IndexError: rng[1]` |
| chan/samples-float | channels | `samples=3.5` | **CRASH** `TypeError: len(float)` |
| chan/variance-string | channels | `variance="bad"` | **MEASURED** (soft) |
| graph/errors-string | graph | `errors="boom"` | FAIL (graceful) |
| disp/obs-none | dispatch | `measure("image", None)` | **CRASH** `AttributeError: None.get` |
| disp/kind-none | dispatch | `measure(None, {})` | UNKNOWN (honest) |

### F1 — robustness, MEDIUM — 9/17 wrong-type inputs CRASH instead of UNKNOWN

A raised exception is **neither UNKNOWN nor a verdict** — the honesty guard aborts before
reaching one. Under the crucible criterion *"unobtainable renders UNKNOWN, never zero"*, a
malformed-type observation is unobtainable-as-judged and should render UNKNOWN; instead it
raises. Root causes (all assume the input's shape without a type guard):

- `measure_geometry`: `list(bbox)` (`measures.py:163`), `math.isclose(weight_sum, …)` (`measures.py:169`)
- `measure_channels`: `list(range)` / `rng[1]` (`measures.py:186`), `len(samples)` (`measures.py:181`)
- `measure_sim` → `detect_explosion`: assumes `frames` is a list-of-dicts (`explosion.py:95,102,112`)
- `measure()` dispatcher: `obs.get(...)` on a `None` obs (`measures.py:76` via each contract)

### F2 — type-laxity, LOW — 3/17 garbage-typed values ACCEPTED as MEASURED

- `img stats=0.5` (scalar) → `_flatten_stats` returns `[0.5]`, numeric → MEASURED (`measures.py:122`)
- `geo bbox="box"` → `list("box")=['b','o','x']`, no NaN-float so `_any_bad` False → MEASURED (`measures.py:163`)
- `chan variance="bad"` → `_bad` only flags NaN/inf floats, a string slips through → MEASURED (`measures.py:188`)

Present-but-garbage read as a measurement — the FP2-adjacent risk, but at LOW severity.

### CORRECT — the "never zero" line is handled right

`geo/counts-zero` (`point_count=0, prim_count=0` → **MEASURED**) is the **right** call, not a
soft-pass: a cooked-empty geometry legitimately measures 0 points, and the guard distinguishes
**present-0** (measured) from **absent-None** (UNKNOWN) via `_has`'s `is not None` test
(`measures.py:76`). This is exactly *"never coerce absent → 0"* done correctly.

---

## Honest scope caveat (do not overclaim)

These contracts consume observations from a **trusted producer** — a live hython cook that
emits typed dicts. It would not emit `bbox=5` or `frames="boom"`. So F1/F2 are
**defense-in-depth / robustness** findings, **not** proof the shipped guard fabricates passes
on realistic cook output. The builder's FP2 threat model (a cook that ran but produced
**empty/partial** output) **holds first-hand** — that is what the 36-green slice and the six
fixed FP2 holes demonstrate. My matrix attacks a **different** surface (wrong-type inputs) the
builder explicitly scoped out (ABSENT + HOLLOW, not wrong-TYPE).

---

## Verdict (this shard)

- **W5-MEASURES Acceptance 1 & 2 UPHELD first-hand** (36/36 green; matches M-E1).
- **Robustness caveat raised** for the synthesizer (W5-WCRUX): the honesty guard does not
  extend to wrong-type inputs (9 crash, 3 soft-pass). Hardening proposed as a spawn, not an
  acceptance failure — it is out of the builder's declared input domain.
- **No FP2 falsification found** on the leg's own threat model. Charter delivery is sound.

## Spawns

- **S1 (build, held):** add a per-contract type guard so a wrong-TYPE observation renders
  UNKNOWN (or FAIL) rather than raising — `measure_geometry`/`measure_channels`/`measure_sim`
  + `detect_explosion` frame-shape guard + `measure()` None-obs guard. Closes F1.
- **S2 (probe):** add a wrong-type fuzz slice to `tests/test_measures_contracts.py` pinning
  "malformed-type → UNKNOWN, never crash / never soft-pass" once S1 lands. Closes F2 + regresses F1.
