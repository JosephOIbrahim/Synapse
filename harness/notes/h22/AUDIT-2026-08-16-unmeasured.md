# AUDIT — "unmeasured" whole-tree honesty sweep — 2026-08-16

**Branch:** `wave5/measures` · **CTO-decided, unmerged.** No push, no VERSION touch.
**Law under test:** wave-5 — *UNKNOWN is never zero, never a default, never an estimate.
Every number shown to a human carries a producer path (Law 2).*
**Provenance:** workflow `wf_45917594-80b` — 6 blind finders + 8 adversarial verifiers
(14 agents, 210 tool calls, 1.49M subagent tokens, ~410s). 6-lens sweep; 24-slot verify
budget; cap never hit ⇒ **whole surface, not a sample.**

---

## Verdict

**5 confirmed · 3 refuted · 0 deferred. None critical** (medium and below,
verifier confidence 0.66–0.78). The tree is close to clean; these are the residuals.

> **R2 addendum (2026-08-16, same day):** Bug A + Bug B-consumer shipped; a 4-agent
> adversarial verify of Bug A then surfaced **two more same-shape seams** (Resilience HIGH,
> Routing MEDIUM) in the same file, now also shipped. Running tally: **7 confirmed** (5 static
> + 2 from the verify pass), Bug B-producer still blocked on the write-denied `shared/` surface.
> See **Status / queue** at the bottom for the shipped record.

Every confirmed finding is the **same shape** as the Layer-6 `synapse_doctor`
`fidelity=0.0` bug (`docs/INTERPRETATION_INTEGRITY.md` §Layer 6), living in two other
places. Layer 6's fix note ended with an un-run to-do — *"audit every other probe for
the same shape."* **This is that audit.**

### Layer-6 status (the gap that seeded this run)

- **Items 1–2 (the doctor's own fidelity): CLOSED by redesign.** `python/synapse/server/doctor.py`
  `run_doctor()` computes **no** `fidelity`; it runs 14 named checks, each `ok|fail|skipped`
  with a stated truth contract. The fabricated `fidelity=0.0` cannot be emitted. The doctor
  is now the reference honesty model.
- **Items 3–4 (audit every other probe; reuse the honesty vocabulary): THIS DOC.** The two
  seams below are the residuals; the correct vocabulary (`has_data` / `inconclusive`) already
  exists in-tree and just needs to reach them.

---

## Bug A — a shed metrics cycle overwrites the last good reading with defaults

**Seam:** `python/synapse/server/live_metrics.py` — `_collect_scene()` (~L202-272) returns a
bare `SceneMetrics()` on every unmeasured path (`hou` unimportable, main-thread-busy past the
1s timeout, or a walk exception); `_run()` (~L181-183) **unconditionally overwrites
`self._latest`** with it. No stale/shed marker. Those defaults then export as if measured.

| Producer path | Surfaces as | Truth | Conf |
|---|---|---|---|
| `server/metrics.py:304` | `synapse_scene_nodes_total 0` | walk skipped (a live root walk is never 0) | 0.78 |
| `server/metrics.py:309` | `synapse_scene_warnings 0` | "clean scene" — but unmeasured | 0.66 |
| `server/live_metrics.py:39` (`fps: float = 24.0`) | dashboard `FPS 24` | invented framerate (only non-zero default in the class) | 0.68 |

Reached by: `/metrics` scrape (`handlers.py` ~L1584) · `synapse_live_metrics` MCP tool
(`snapshot_to_dict`, `handlers.py:1748-1753`) · `server/dashboard.py:195` (fps row). The
`fps=24` on a shed cycle sits inside an otherwise-empty readout (HIP `-`, Frame 0, Nodes 0)
— a fabricated number with no producer path. Worst case: an operator scraping `/metrics`
while debugging a **freeze** — exactly when the main thread is busy and cycles shed — reads
"0 warnings, 0 errors, scene emptied to 0 nodes." Under-reporting when the instrument matters.

**Fix shape (one guard covers all three):** carry a `measured: bool` / `inconclusive` flag on
`SceneMetrics` (or don't overwrite last-good on a skip; keep last-good + mark stale), and let
`metrics.py` + `snapshot_to_dict` render UNKNOWN when unmeasured. Vocabulary exists:
retina's `inconclusive`, `face_token`'s UNKNOWN. **Owner: SUBSTRATE** (`src/server/`).
Test-first: golden pinning "shed cycle ⇒ UNKNOWN, not 0/24" before code.

---

## Bug B — `success_rate = 0.0` on zero samples paints a healthy install red

**Seam:** `shared/bridge.py:914-917` (producer) → `python/synapse/panel/health_infographic.py:111/120/132`
(consumer). Fresh bridge, zero ops → `operation_stats()` returns `success_rate=0.0` (bare
default, no `has_data`). The infographic's `if not self._data` guard (:111) catches only a
*missing* bridge, not `operations_total==0`, so the **hero success gauge paints RED at 0%**
for a healthy just-started install until the first op flows. This is literally the doctor
bug on the panel. Conf 0.72 (consumer) / 0.66 (producer).

**Antidote already in-tree:** the sibling `session_fidelity` (`shared/bridge.py:2835`) guards
the zero-sample case, and the `has_data` doctrine (`panel/gate_widget.py:84-97`,
`panel/session_integrity.py:138-157`, `panel/integrity_readout.py:47`) suppresses exactly
this rest-state to UNKNOWN. `success_rate` is the one metric that never got it.

**Fix shape:** `operation_stats()` carries `has_data` (or returns `success_rate=None`) at
`operations_total==0`; the infographic renders the hero gauge UNKNOWN, not red 0%.
**Owner: SUBSTRATE** (bridge) + panel. Test-first: golden pinning "0 ops ⇒ UNKNOWN gauge."

---

## Refuted (kept — this is the honesty check; it proves the survivors aren't grep-noise)

- **`panel/agent_health.py:174`** — same `0.0`, but renders `"0% (0 ops)"` with the sample
  count welded inline. The number carries its producer context; only the red *color* is off
  (cosmetic, not a fabricated measurement). *Refuted.*
- **`server/metrics.py:314` (`scene_errors`)** — co-moves with `nodes 0`, and errors can't
  exceed nodes, so `errors=0` beside `nodes=0` reads as "no scene observed," not "verified
  clean." The gap tells on itself. *Refuted, conf 0.62.*
- **`memory/agent_state.py:648`** — the `else 0.0` handoff default is dead code (no production
  caller; `run_team.py` does not exist) over an unreachable branch (`log_handoff` always sets
  the attr). *Refuted, conf 0.85.*

---

## Coverage, stated plainly (no silent caps)

- **Docs / README came back clean.** The Law-2 lens found nothing in README/CHANGELOG/docs —
  those numbers have producer paths. The wave did that work.
- **Nothing deferred.** 8 unique candidates, 24-slot budget, cap never hit — the whole surface.
- **Not a live probe.** All findings are static (code-read) with named producer→consumer paths;
  a live seat would confirm the render, not change the verdict.

---

## Status / queue (updated 2026-08-16 R2 — merge/push/tag stay human)

### Bug A — ✅ SHIPPED (commit `eeebca16`, branch wave5/measures)
`SceneMetrics` gained `measured: bool = True`; every shed path in `_collect_scene()` returns
`SceneMetrics(measured=False)`; `_snapshot_to_dict` nulls the fabrication-prone scene fields
(fps + all counts) when unmeasured — one chokepoint fixing the `synapse_live_metrics` MCP tool
AND the dashboard; `render_prometheus` emits `synapse_scene_measured {0|1}` and OMITS the scene
counts on a shed cycle; dashboard renders `—`. Goldens in `test_live_metrics.py` +
`test_metrics_invariants.py`; the three `test_live_metrics_threadsafe.py` shed-path tests moved
from `== SceneMetrics()` to the `measured=False` contract. **Verified** by a 4-agent adversarial
pass (`wf_333e65c3-406`): missed-shed-path and consumer-crash lenses both CLEAN; Prometheus lens
clean but for one latent default (folded into the sibling commit below).

### Bug A siblings — ✅ SHIPPED (commit `a1e3fa03`) — found by the Bug A verify pass
The adversarial completeness critic found the identical shape untreated in two SceneMetrics
siblings in the same file; on the dominant hwebserver transport (router + health_monitor never
wired) they shed **every** cycle:
- **ResilienceMetrics (HIGH)** — bare `circuit_state='closed'` / `health_status='healthy'`, an
  affirmative all-clear rendered green when nothing was measured; a throwing health monitor also
  sheds here and reports itself healthy. Fixed: `measured` flag; serializer nulls
  circuit_state/health_status; dashboard renders `—` with a neutral class (no false green).
- **RoutingMetrics (MEDIUM)** — bare `cache_hit_rate=0.0` / `avg_latency_ms=0.0`, computed rates
  indistinguishable from measured-zero. Fixed: `measured` flag; serializer nulls the rates;
  dashboard guards `toFixed` against the resulting null.
- **SessionMetrics** — examined and CLEARED (no shed-return; its zeros read as resting).
- Also folded: `render_prometheus` scene honesty default flipped `True`→`False` (unknown-provenance
  scene dict ⇒ treat as unmeasured); latent-trap comment that the null-out is a dict-only chokepoint.
Two blessing goldens moved to the `measured=False` contract; sibling + hardening goldens added.
546 passed / 0 failed across the metrics+observability+resilience slice.

### Bug B — consumer half: ✅ SHIPPED (commit `9bd298c4`)
`panel/health_infographic.py` hero gauge renders UNKNOWN (slate + "—") instead of a red 0% at
zero samples, via a self-sufficient `total>0` fallback. Pixel render remains the offscreen gate.

### Bug B — producer half: ⛔ STILL BLOCKED — `shared/` is write-denied (CONFIRMED this session)
Re-confirmed empirically: an Edit to `shared/bridge.py` is denied at the permission layer
(not the `guard-edit-targets.py` hook — that only fences deployed copies — but a higher policy
layer; SUBSTRATE crown-jewel, one-writer-per-surface). Per the `2026-07-25_push_denied`
precedent, this was NOT routed around via Bash/git-apply. Awaits the surface owner (Joe's hands
or a dispatched SUBSTRATE leg). It is **source-hardening**, not a visible-bug fix — the consumer
already self-defends. Exact, self-contained patch:

**`shared/bridge.py`** — in `operation_stats()`'s return dict, after `"success_rate": success_rate,`:
```python
                "has_data": self._operations_total > 0,
```
(with the doctrine comment: zero-sample success_rate is 0.0 both when all-failed and when
nothing has run; `has_data` lets consumers render UNKNOWN, mirroring `session_integrity.summary()`.)

**`tests/test_evolution_bridge_internals.py`** (`TestOperationStats`), golden pairs with the code:
- shape test key tuple: add `"has_data"`
- after `assert stats["success_rate"] == 1.0`: `assert stats["has_data"] is True`
- after `assert stats["success_rate"] == 0.0`: `assert stats["has_data"] is False`

Verify: `python -m pytest tests/test_evolution_bridge_internals.py::TestOperationStats -q` (one atomic commit).

### Follow-on (not a honesty bug — a wiring gap the honest fix exposes)
The hwebserver transport builds `MetricsAggregator()` with `router`/`health_monitor`/
`session_manager` all `None` (no setters), so resilience/routing now correctly read UNKNOWN there.
Wiring those monitors into the hwebserver aggregator would make them genuinely measured — a
separate feature, out of scope for the honesty wave.
