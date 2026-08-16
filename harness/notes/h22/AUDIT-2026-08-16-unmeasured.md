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

## Status / queue (updated 2026-08-16 — merge/push/tag stay human)

### Bug B — consumer half: ✅ SHIPPED (commit `9bd298c4`, branch wave5/measures)
`panel/health_infographic.py` hero gauge now renders UNKNOWN (slate + "—") instead of a
red 0% at zero samples, via a self-sufficient `total>0` fallback. py_compile OK; honesty +
observability suite green (21 passed). Pixel render remains the offscreen-at-seat gate.

### Bug B — producer half: ⛔ READY TO APPLY, blocked on the guarded surface
`shared/bridge.py` is denied to automated Edit/Write by permission settings (SUBSTRATE
crown-jewel; one-writer-per-surface). This change was NOT auto-applied by design — it awaits
the surface owner (Joe's hands, or a dispatched SUBSTRATE leg). It is **source-hardening**,
not a visible-bug fix: the consumer already self-defends. Exact, self-contained patch:

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

### Bug A — ⛔ QUEUED (SUBSTRATE, guarded surfaces)
One guard at the `live_metrics` `_collect_scene()`/`_run()` seam so a shed cycle marks
`inconclusive` instead of overwriting last-good with defaults; `metrics.py:304/309` +
`live_metrics.py:39` (fps 24.0) inherit it. Golden-first.

### Optional
Fold both goldens into the wave-5 honesty suite so the pattern can't regress.
