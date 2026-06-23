# Goalpost Tests — Report

Wrote the three missing goalpost test files the scout was flagging. These tests
are the harness's reward signal (a paid autonomous worker will later be run to
make them pass), so they are grounded in the real panel code and verified to
resolve to a clean pass/fail with the expected reason — under **both** stock
CPython and hython where each can run.

Files added (unstaged, for review — no panel/harness/contract code touched):

- `tests/panel/test_token_seeding.py`
- `tests/panel/test_failure_trail.py`
- `tests/panel/test_docking.py`

No `tests/panel/__init__.py` / conftest added — the existing convention is a
flat `tests/` with no package `__init__.py` (pytest prepend import mode; the
basenames are unique repo-wide), and `tests/conftest.py` already applies to the
new subdir.

---

## ⚠ The one thing you must know first: 3 of 5 goalposts can't give a real signal under the harness's gate

> **UPDATE — RESOLVED (2026-06-23).** The `failure-trail` and `docking-minimums`
> contracts now route their Qt-bound verifies through `.synapse/hytest.py`, a shim
> that runs the selector under a discovered hython (PySide present), so the harness
> gets a real pass/fail and no longer counts a skip as a pass. Verified end-to-end:
> all three report `rc=1, skipped=0 → not-passing` through `memory._run`. The
> analysis below is kept as the rationale; of the two "not applied" fixes at the
> end of this section, the hython-runner one WAS applied (as the shim — the durable
> form, version-proof rather than a pinned path). The token goalposts still run on
> stock pytest, which is correct.

The harness evaluates a feature by running its `verify` command and checking
`returncode == 0` (`.synapse/memory.py::_run`). The gate is **stock
`pytest -q`** (`config.yaml` / `harness.py::load_config`).

I empirically confirmed (in-tree probe): **a skipped pytest selector exits 0.**
So *a test that SKIPS is counted by the harness as PASSING.*

`python` on this machine has **no PySide** (`import PySide6` and `import PySide2`
both fail). And `synapse_panel.py` / `face_review.py` **hard-import PySide6/2 at
module top** (no third fallback), so they cannot be imported headless at all.
Therefore the three Qt-bound goalposts (`test_runtime_paths_log`,
`test_dead_verb_hidden`, `test_usable_at_min_height`) can only run under hython.
Under the stock gate they SKIP → exit 0 → **false green.**

I did **not** make them hard-fail-when-PySide-absent: that is unsatisfiable on
this machine (no PySide to instantiate), so the worker could never turn them
green and would burn its session budget forever. Between a false-green skip and
an unsatisfiable hard-fail, neither is a valid goalpost — so per the task's
"STOP and report" rule, I'm surfacing it instead of shipping a guess.

I verified all three under hython (PySide6 6.5.3, pytest 9.0.3) and they FAIL
correctly today — they are *real* goalposts, just not on the stock gate. Two
fixes make them honest (pick one, **not applied**):

- **Run the panel verifies under hython.** Change those three `verify:` lines to
  `hython -m pytest -q <selector>` (and ideally the `pytest -q` gate too).
  hython has PySide + pytest and uses the same `pyproject.toml`.
- **or install PySide6 into the harness interpreter** (`pip install PySide6` for
  the Python that runs the harness). Then stock `pytest -q` runs them for real.

The **two token goalposts are immune** to this — `tokens.py` is stdlib-only, so
they run as real assertions on any interpreter. They are the only goalposts that
give a true pass/fail under the gate as it stands.

---

## (a) Per-test detail

Legend: **stock** = `python -m pytest` (no PySide, this machine) ·
**hython** = `hython -m pytest` offscreen (PySide6 present).

### `tests/panel/test_token_seeding.py` — contract `theme-seed-tokens` (C1)

Pure Python (no Qt). Reloads `synapse.panel.designsystem.tokens` with a
controlled `hou` in `sys.modules` (save/restore so it never leaks a fake `hou`
to neighbours — the 46-file residency trap).

**`test_follows_host_scheme`** — Design §2.2 / Codebase §1.3.
Asserts: with `hou.qt.color()` mocked to a LIGHT grey, the panel surface token
`PANEL` resolves LIGHT (relative luminance > 0.5).
- **Now: FAIL (stock + hython).** Exact reason: `PANEL` is the hardcoded
  `#2E2E2E` (luminance 0.18) — `tokens.py` ignores `hou` entirely.
- **Turns green when:** `tokens.py` seeds the SURFACE-ELEVATION tokens from
  `hou.qt.color(<role>)` at construction (e.g. `PANEL`←`DRKBASE`), inside a
  `try/except` that keeps the hardcoded hex as the fallback. The contract's
  `symbols-in-runtime` check will require `hou.qt.color` to be a verified live
  symbol (it is real — cf. `panel/dnd.py` `hou.qt.mimeType`).

**`test_headless_fallback`** — the "don't break headless" guard.
Asserts: with `hou` absent, `PANEL` is a hardcoded dark hex string (`#RRGGBB`,
luminance < 0.5).
- **Now: PASS (stock + hython).** This is correct — it documents the invariant
  that must KEEP holding after the seeding inversion lands. (Per the task: a
  goalpost that already passes = the guard is already satisfied; its job is to
  stop the fix from regressing headless mode.)

### `tests/panel/test_failure_trail.py` — contract `failure-trail` (C3)

Offscreen-Qt, copied verbatim from `tests/test_panel_faces.py` (sys.path + `hou`
stub + `QT_QPA_PLATFORM=offscreen` + PySide6/2 probe + the genuine-QApplication
stub guard + `pytestmark` skip). **Skips on stock; runs on hython.**

**`test_runtime_paths_log`** — Codebase §1.4.
Asserts: forcing the review's named guarded path `_wire_gate`
(`synapse_panel.py:783-794`) to fail leaves a `logger.debug` trail (caplog: a
DEBUG record carrying the exception). Calls `SynapsePanel._wire_gate` **unbound
with a fake `self`** (a `_gate._proposal_received.connect` that raises) so no
QWidget is built — the swallow is the whole point.
- **Now: stock SKIP · hython FAIL.** hython reason: "`_wire_gate` left no
  logger.debug trail — the bare `except: pass` is still silent."
- **Turns green when:** the bare `except Exception: pass` on the runtime paths
  becomes `except Exception as exc: logger.debug(..., exc_info=exc)` (the test
  pins `_wire_gate`; the contract goal is the whole pattern). Needs a module
  logger in `synapse_panel.py`.

**`test_dead_verb_hidden`** — Design §2.5.
Asserts: the "⤢ open in render view" verb (`face_review.py:212`) is not a
visible control when the render bridge is absent. Builds `FaceReview`, calls
`face.show()` offscreen (so `isVisible()` is meaningful), finds the verb button
by text, asserts none are visible.
- **Now: stock SKIP · hython FAIL.** hython reason: the `DsVerb` QPushButton is
  present and visible at rest.
- **Turns green when:** `face_review.py` gates the verb's creation/visibility on
  render-bridge availability (feature-detect `hou.ui` / the confirmed chain) and
  hides or omits it when absent.
- **Note — caught during verification:** my first version walked parent
  `isHidden()` up to the root; a never-shown top-level QWidget reports
  `isHidden()==True` for itself, which made every child read as "hidden" and the
  test passed falsely under hython. Fixed to `show()` + `isVisible()`. This is
  exactly the "too-weak goalpost that already passes" failure mode the task
  warned about; it is now a true fail.

### `tests/panel/test_docking.py` — contract `docking-minimums` (S2)

Offscreen-Qt, same convention. **Skips on stock; runs on hython.**

**`test_usable_at_min_height`** — Design §2.3.
Asserts: the panel's COMPOSED minimum height (`minimumSizeHint().height()`, the
layout-computed minimum — not rendered pixels, the robust honest form) does not
exceed its own declared `PANEL_MIN_HEIGHT` (400).
- **Now: stock SKIP · hython FAIL.** hython reason: "composed minimum height is
  529px, exceeding PANEL_MIN_HEIGHT=400px." (529, not the ~900 the design doc
  estimates from naive summation — `minimumSizeHint` composes nested/sibling
  minimums, so the honest measured number is lower but still over budget.)
- **Turns green when:** the stacked hard minimums are halved — `_faces`
  `setMinimumHeight(380)` (`synapse_panel.py:401`), the Direct chat 380
  (`:360`/`:367`), the 216px default composer (`:90`), `FaceReview` hero 168
  (`face_review.py:110`), `FaceWork` 150 (`face_work.py:72`) — so the composed
  minimum drops to ≤ 400 and faces collapse gracefully.

---

## (b) Path findings + proposed (NOT applied) edits

**1. Real location of `components.py`:**
`python/synapse/panel/designsystem/components.py` — **not**
`python/synapse/panel/components.py`. The `docking-minimums` contract's `owns`
list names the wrong path, so the scout flags `unconfirmed owns` (glob matches 0
files).
- *Proposed edit (not applied)* — `.synapse/contracts/docking-minimums.yaml`,
  `owns`: change `python/synapse/panel/components.py` →
  `python/synapse/panel/designsystem/components.py`. (Alternatively drop it: the
  min-height changes live in `synapse_panel.py` / `face_work.py` /
  `face_review.py`, which are already owned; `designsystem/components.py` only
  declares base-component chrome and may not need to be in scope.)

**2. Why `synapse.panel.designsystem` is flagged "missing goalpost"
(quarantine-dead-tree):**
This is a **scout resolver false positive, not an import failure.** The verify is
`python .synapse/verify.py importable synapse.panel.designsystem`. The scout's
`_verify_targets` (`.synapse/scout.py:64-79`) uses
`_VERIFY_PATH = re.compile(r"verify\.py\s+\S+\s+(\S+)")`, which captures the
**module argument** `synapse.panel.designsystem` and then checks
`os.path.exists("synapse.panel.designsystem")` — a dotted module name is never a
literal file path, so it always reports "missing."
The module **imports fine headless** (verified: `import
synapse.panel.designsystem` succeeds; its `__init__.py` only does
`from . import tokens`, which is stdlib-only — the PySide-dependent components
are *not* imported by the package init).
- *Proposed fix (not applied; this is the scout's bug, and quarantine is
  verify.py-based — no pytest written for it):* in `.synapse/scout.py`
  `_verify_targets`, skip path-existence for the `importable` check (its arg is a
  module, not a path) — e.g. don't emit a target when the verify matches
  `verify.py importable <arg>`. Or have the scout actually run the `importable`
  check instead of doing `os.path.exists` on its argument.

**3. Reward-signal / gate edits (proposed, not applied):** see the ⚠ section —
run the three Qt-bound verifies (and ideally the `pytest -q` gate) under
`hython -m pytest`, or install PySide6 into the harness interpreter.

---

## (c) Post-write scout result

```
quarantine-dead-tree  [green]  needs-attention: goalpost target(s) missing
                               missing goalposts: ['synapse.panel.designsystem']   (scout false positive — §b.2)
failure-trail         [green]  ready          ✅ cleared
theme-seed-tokens     [amber]  ready          ✅ cleared
docking-minimums      [amber]  needs-attention: unconfirmed owns path(s)
                               unconfirmed owns: ['python/synapse/panel/components.py']   (wrong path — §b.1)
```

- `failure-trail` and `theme-seed-tokens`: **now `ready`** — writing the goalpost
  files cleared their only flag.
- `docking-minimums`: the missing-goalpost flag cleared; the remaining
  `unconfirmed owns` is the wrong `components.py` path (contract edit, §b.1 — not
  mine to apply).
- `quarantine-dead-tree`: unchanged — its flag is the scout-resolver false
  positive (§b.2), not something a test fixes.
- Baseline `pytest -q` is still **RED** (it was RED before this work too;
  `test_follows_host_scheme` now adds one *intended* goalpost failure to it).

---

## (d) What I could NOT write a clean goalpost for, and why

Per the task's rule ("if you cannot make it fail cleanly as an assertion, STOP
and report"):

- **`test_runtime_paths_log`, `test_dead_verb_hidden`, `test_usable_at_min_height`
  could not resolve to a clean PASS/FAIL under *stock* `pytest`** — RESOLVED
  (2026-06-23) by routing those contract verifies through `.synapse/hytest.py`
  (hython). Their owning modules hard-import PySide, absent from `python` here,
  so under stock `pytest` the only collectable outcome was SKIP → exit 0 →
  counted as PASSING (false green). They ARE real, correct goalposts — verified
  to FAIL today under hython with the right reasons — so the fix was to make the
  harness run them under hython (the shim), not to weaken the tests. There was no
  honest middle option on a PySide-less *stock* interpreter (skip→false-green, or
  hard-fail→unsatisfiable); the shim removes that dilemma by changing interpreter.
- The two **token** goalposts have no such issue — they are clean on every
  interpreter and are the dependable signal for `theme-seed-tokens`.
- Residual coupling worth knowing (not a blocker): `test_follows_host_scheme`
  mocks `hou.qt.color()` specifically (as the contract's own wording dictates).
  If the implementer instead reads the host via a different API
  (`hou.ui.colorFromName`, etc.), the mock wouldn't feed it and the test could
  stay red after a correct fix. `hou.qt.color()` is the named seam in both the
  contract and the design review, so this is the right thing to pin — just noting
  the assumption.

---

*No feature code, contract YAML, or `runtime_symbols` were modified. No real
harness run; `--skip-scout-gate` never used. New files are unstaged for review.*
