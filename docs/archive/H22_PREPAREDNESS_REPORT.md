# Houdini 22 Preparedness — What Was Addressed

Status of the H22-lens panel reviews' punch lists, after this session's work.

> **Read this first — what "addressed" means here.** This session built **none**
> of the actual H22 fixes. `git diff 404d2b7..HEAD -- python/synapse/panel/` is
> empty: the panel code is byte-for-byte unchanged. What was addressed is the
> **reward signal** — the goalpost tests and harness plumbing that let a paid
> autonomous worker be pointed at each punch-list item and *prove* when it's
> done. The items moved from "scout-held, no goalpost" to "ready to build."
> Building them is the next, separate step (a real `harness run`, which spends).

Source of truth: `docs/SYNAPSE_PANEL_DESIGN_REVIEW_H22_LENS.md` and
`docs/SYNAPSE_PANEL_CODEBASE_REVIEW_H22_LENS.md` (the "Prioritized punch list"
in each). Harness contracts in `.synapse/contracts/`.

---

## Status at a glance

| # | Punch-list item | Review § | Contract | Tier | This session | Scout | Built? |
|---|---|---|---|---|---|---|---|
| 1 | **Seed tokens from `hou.qt.color()`** at construction; hex as headless fallback; collapse to one token system | Design §2.2 / Code §1.3 (+ §1.3 reskin) | `theme-seed-tokens` | amber | 2 goalposts written (real signal) | **ready** | ❌ |
| 2 | **Halve stacked min-heights** — usable at `PANEL_MIN_HEIGHT=400` | Design §2.3 | `docking-minimums` | amber | 1 goalpost written + owns-path fixed | **ready** | ❌ |
| 3 | **Quarantine the dead tree** (chat_panel → legacy/, 14 orphans → _attic/) | Code §1.2 | `quarantine-dead-tree` | green | scout resolver false-positive fixed | **ready** | ❌ |
| 4a | **logger.debug trail** on bare `except: pass` runtime paths | Code §1.4 | `failure-trail` | green | 1 goalpost written | **ready** | ❌ |
| 4b | **Hide the dead "open in render view" verb** until real | Design §2.5 | `failure-trail` | green | 1 goalpost written | **ready** | ❌ |
| 5 | **Move freeze-chain heartbeat off the panel** (+ drop 2s context poll) | Design §2.4 / Code §1.5 | `heartbeat-relocation` | **red** | **untouched** — not queued | n/a | ❌ |
| 6 | Brand intensity (bundled type, dual accent, gradient, toy) | Design "worth a conversation" | — | — | none (by design) | n/a | ❌ |

**Net:** 4 of the 6 punch-list items (items 1–4) are now **goalpost-ready and
unblocked** for the worker. Item 5 is a RED, live-Houdini + human-sign-off task
the harness refuses to automate. Item 6 was flagged "a conversation, not a fix"
by the reviewer — no contract, intentionally.

---

## What was actually done (per item)

### 1 · Token seeding — `theme-seed-tokens` (amber) → ready
The single biggest "doesn't read as native" finding: `designsystem/tokens.py`
hardcodes the matched hex and even says "the hex stays source of truth" — the
inversion the review calls out. Two goalposts encode the fix
(`tests/panel/test_token_seeding.py`):
- `test_follows_host_scheme` — mock `hou.qt.color()` LIGHT → a surface token
  must resolve LIGHT. **Fails today** (PANEL = `#2E2E2E`, luminance 0.18).
- `test_headless_fallback` — `hou` absent → hardcoded hex fallback. **Passes
  today**; pins the headless guard so the fix can't regress it.
- **Real signal everywhere:** `tokens.py` is stdlib-only, so these run as true
  assertions under stock `pytest` *and* hython — no PySide needed.
- **Still needed (the build):** seed the SURFACE-ELEVATION tokens from
  `hou.qt.color(<role>)` at construction inside a `try/except` that keeps the
  hex as fallback; retire `panel/tokens.py` + `panel/styles.py`; reskin
  `chat_display` + `gate_widget` (Code §1.3 / §1.4 reskin half).

### 2 · Docking min-heights — `docking-minimums` (amber) → ready
Goalpost `tests/panel/test_docking.py::test_usable_at_min_height` asserts the
**composed** minimum height (`minimumSizeHint().height()`, not rendered pixels)
≤ `PANEL_MIN_HEIGHT` (400). **Fails today** — measured **529px** under hython.
- Also fixed the contract's `owns` path (see Infra fixes below) so the scout
  stopped flagging it `unconfirmed owns`.
- **Still needed:** halve the hard `setMinimumHeight()` values — `_faces` 380
  (`synapse_panel.py:401`), Direct chat 380 (`:360`/`:367`), 216 composer
  (`:90`), `RenderHero` 168 (`face_review.py:110`), `FaceWork` 150
  (`face_work.py:72`) — so the composed minimum drops to ≤ 400.

### 3 · Quarantine dead tree — `quarantine-dead-tree` (green) → ready
No pytest goalpost (the contract's checks are `verify.py`-based: `no-importers`,
`absent-file`, `importable`). What was holding it was a **scout false positive**,
now fixed:
- The scout read `verify.py importable synapse.panel.designsystem` and ran
  `os.path.exists("synapse.panel.designsystem")` — a dotted module is never a
  literal path, so it always reported "missing goalpost." The module imports
  fine headless (`__init__.py` only does `from . import tokens`).
- **Still needed:** the actual relocation — `chat_panel` subtree → `legacy/`,
  the 14 orphans → `_attic/`, preserving the surviving knowledge tables.

### 4 · Failure trail + dead verb — `failure-trail` (green) → ready
Two goalposts (`tests/panel/test_failure_trail.py`):
- `test_runtime_paths_log` — forces the review's named guarded path
  `_wire_gate` (`synapse_panel.py:783-794`) to throw and asserts a
  `logger.debug` trail (caplog). **Fails today** under hython (bare
  `except: pass`, silent).
- `test_dead_verb_hidden` — the "⤢ open in render view" verb
  (`face_review.py:212`) must not be a visible control with no render bridge.
  **Fails today** under hython (the `DsVerb` button is visible at rest).
- **Still needed:** replace bare `except: pass` on runtime paths with
  `logger.debug(..., exc_info=exc)` (add a module logger); gate the verb's
  visibility on render-bridge availability (feature-detect `hou.ui`).

### 5 · Heartbeat off the panel — `heartbeat-relocation` (red) → NOT addressed
The contract exists but is **autonomy: red, verify: e2e-houdini** — the harness
*refuses* to run it. Its `done_when` requires the freeze chain firing daemon-side
**with the panel tab closed, human-verified in a live H22 session.** pytest can't
prove that, so there's no goalpost to write. It is **not in the queue** and was
not touched this session. This is the one ship-blocker (Code §1.5) still fully
open, by design — it needs a person + a live engine.

### 6 · Brand intensity — no action (by design)
The design reviewer explicitly filed this as "worth a conversation, not a fix."
No contract, no goalpost; a deliberate product decision, not preparedness work.

---

## Infrastructure fixes made this session (harness, not panel)

These are corrections to the harness itself, surfaced while grounding the
goalposts. (Committed: `3ef8e92`, `728f9fc`.)

1. **`docking-minimums.yaml` owns path** — `python/synapse/panel/components.py`
   → `python/synapse/panel/designsystem/components.py` (the real location;
   the old path matched zero files → `unconfirmed owns`).
2. **`scout.py` resolver** — the path-existence check now skips the `importable`
   *and* `absent-file` verify checks. `importable` takes a dotted module (not a
   path); `absent-file` asserts a path *should not* exist (absence is the goal,
   e.g. `scene_doctor.py` after quarantine — without this, quarantine would
   flip to needs-attention the moment the work succeeded).

---

## ✅ False-green caveat — RESOLVED (2026-06-23)

"Ready" means the scout can resolve each goalpost. Whether each gives a *real*
signal to the harness:

- The **token goalposts (item 1)** are pure-Python → real pass/fail on stock
  `pytest`. Dependable, always were.
- The **Qt-bound goalposts (items 2 and 4)** import modules that hard-import
  PySide6/2, absent from the harness `python`. Under stock `pytest` they would
  **skip → exit 0 → counted as passing (false green)**. **Fixed:** the
  `failure-trail` and `docking-minimums` contract verifies now run through
  `.synapse/hytest.py`, a shim that executes the selector under a discovered
  hython (PySide present; auto-picks the newest install with pytest+PySide, or
  `$SYNAPSE_HYTHON`). Verified through `memory._run`: all three now report
  `rc=1, skipped=0 → not-passing` (they fail because the feature is unbuilt — the
  correct goalpost state — instead of false-greening). The tests themselves still
  *skip* under a bare stock `pytest`, but the harness no longer invokes them that
  way, and the full-suite `pytest -q` regression gate is unaffected.

**Verification done:** all five goalposts confirmed under stock (isolated),
hython (offscreen, real fail), and a full-suite-interaction probe (with the
sibling PySide/hou stubs resident, the Qt tests *skip* cleanly — no
broken-goalpost errors; the genuine-QApplication guard holds).

---

## To actually close items 1–4

Point the worker at the ready contracts — e.g.
`python .synapse/harness.py run --autonomy amber --budget <N>` (this **spends**:
it spawns paid headless `claude -p` workers). The scout gate passes now, so all
four would run. After each, the contract is left on a branch, unmerged, for human
review. Item 5 (heartbeat) stays manual until a live H22 session + sign-off.

---

*No panel/feature code, contract features, or `runtime_symbols` changed this
session. This report is unstaged.*
