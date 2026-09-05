# v5.63.0 — the swarm shipped the seam, and the referee held the door

Release notes. Every claim is receipt-backed on master (HEAD at draft time
`b246b78e`, two `--no-ff` merges on Joe's word, 2026-09-05). Where a claim
needs eyes on a live Houdini it says UNKNOWN or NOT_RUN, not green. Where the
orchestrator seat got something wrong, it says so by name.

Scope: two Codex swarms on `gpt-6-astra`, each worker in its own worktree,
orchestrated from Claude Code (Fable 5.1) — **bp5 Solaris Recipes v3** (six
streams over one frozen seam, blueprint dated 2026-09-04) and **Panel PD** (six
legs: census → lever → three parallel builders → read-only referee, battleplan
dated 2026-09-03). **The Solaris wave merged in full. Of the panel wave, only the
leg the referee ruled SOUND merged; the other five are carried on
`pd/panel-integrate`, unmerged, with the referee's BROKEN verdict attached.**

## For artists

Nothing moves under your hands in this release.

The Solaris recipe path ships **dormant**: the constrained `run_recipe` action
exists in code but is not registered on either transport (the two hookup
patches, `docs/solaris_v3/HOOKUP_AUTHORITY.md` and `HOOKUP_RECEIPT.md`, await
review). The `demo` worker-tool mode exists and is honest about failing closed.
The panel looks exactly as it did in v5.62.0: the panel design work did not ship.

One thing changed under your feet that you may notice: an explicit **unknown**
value of `SYNAPSE_WORKER_TOOL_MODE` now resolves to `strict` (read-only worker)
instead of silently falling back to `standard`. A typo yields a read-only worker,
visibly. Joe DECIDE 2026-09-04. Absent value still means `standard`.

## Under the hood — Solaris Recipes v3 (merged)

A frozen seam, `python/synapse/recipes/contracts.py`, defines the blueprint's
vocabulary once: actions, permission ordering with `max_permission`, card
dimensions, `CheckId`/`CheckStatus` with the rule that a skipped check can never
become a green verdict (`verdict_from_checks`), and the three objects
`RecipeSpec` / `RecipeInstance` / `RunReceipt`. Six streams built against it
without touching it; no stream asked for a change.

- **SPEC** — `fixtures/solaris.spine.json` as a contract-only schema v2 (10 LOPs,
  4 nested VOPs, 11 connections, VOP ports captured from the H22.0.400 catalog
  and SHA-pinned, `plane` not `grid`); `blocks/fixtures.py` gains
  `load_recipe_spec` with v1 bodies byte-unchanged; `recipes/spec.py` validator;
  `recipes/canon.py` semantic vs layout digests reusing the c3 canonicalizer.
  The golden record ships `PENDING_HUMAN` and loads as `Availability.BLOCKED`.
- **AUTHORITY** — `demo` worker-tool mode (read tools + `synapse_run_recipe`,
  everything else denied at dispatch, unknown → strict); typed slot validation;
  exact-phrase matcher that must consume the whole request (trailing "and add
  fog" is refused, not dropped); approval binding rechecked before start;
  per-turn terminal hard stop; `handlers_recipe.py` mixin, unregistered.
- **VERIFY** — P1–P6 verifiers; the stage assessor now resolves the intended
  RenderSettings prim explicitly and reads the camera as a relationship
  (`GetCameraRel`), counts two authored lights and the render-input branch.
- **LIFECYCLE** — instance lifecycle with STALE/CONFLICT refusal, a build
  transaction that establishes terminal state before any recovery and performs
  global undo only when provably on top of the stack, a render job that never
  undoes a build. The undo backend is injected: the worker refused to call
  `hou.undos.*` because the committed H22 symbol table lacks them. **Live probe
  on the open 22.0.400 session (2026-09-04 20:50): all nine members exist**
  (`harness/solaris_v3/runs/live_probe_h22.0.400_undos.json`). Binding is next.
- **RECEIPT** — immutable receipts with an atomic append store, an evidence
  tracker that reports UNKNOWN until every invalidation source is covered, the
  minimal card, a spec cache that can never hold a verdict, request dedup.
- **ACCEPTANCE** — `scripts/solaris_v3_accept.py`, one command, three tiers,
  bound to the checkout it imports; `harness/solaris_v3/GATES.json` with G0–G6
  and T1–T12 all `NOT_RUN` because the test-to-row binding map is deliberately
  empty until reviewed; bench scaffold where every metric defaults `UNMEASURED`.

Every worker's tree was committed by the orchestrator on its behalf: the Codex
sandbox cannot write a linked worktree's index, and adding the repo `.git` to
`writable_roots` did not change that (ACL deny entries). Recorded in the
commit bodies and in `~/.claude` memory for the next swarm.

## Under the hood — Panel PD (one leg merged, five held)

**Merged:** CENSUS — `harness/notes/panel_rhythm_census.py` (source-only, no Qt,
stock CI), `docs/PANEL_REGION_MAP.md` (all six camera regions; the plan's
`synapse_shelf.py` is the protected launcher, not a panel file), 21 tests.
Re-grounded numbers at base `6e3dd963`: 107 imperative spacing sites, 106 inline
sheets, 135 raw hex sites (75 distinct), 0 exemptions.

**Held on `pd/panel-integrate` (aca05ccb), CRUX round 2 verdict BROKEN, no merge
recommendation:** LEVER (`designsystem/rhythm.py`, role rules, compositor hook
of 5+/1−, spec v2, guard + docking tests), CAMERA (five camera regions on roles,
the recall card), SWEEP_A (six modules), SWEEP_B (twelve modules, 104 hex sites
mapped to existing tokens). On that branch the panel-wide census is 18 / 2 / 42
against the plan's "≤ 20 tagged sites"; 47 of the 62 are untagged. Fifteen
docking widths (composed panel 433, QuickActionPills 587–602, HDA ResultView
382–388, HealthStrip 708, SynapseChatPanel 502–514 vs the 380 px bound) are
inherited debt — identical on the pre-LEVER tree — but the strict accept is
unmet. SWEEP_B's HDA Result view changed surface and button treatment beyond
gap/label/tag, which the plan defines as BROKEN. Four chat-panel CSS pins are
obsolete and three sweep pins only pass in isolation; CRUX rules they must be
re-seated, not deleted. The referee's own mutations: four of five bit; the
airy-widening mutation was NOT_RUN (no PySide6 in its sandbox).

**Orchestrator error, named:** the first merge of SWEEP_B onto SWEEP_A resolved
the QSS conflict per hunk and spliced SWEEP_B's block into the middle of
`sweep_a_style`, dropping its repolish calls. CRUX round 1 caught it
(`chain_broken_at 0998cc9e`). Repaired at `38cd9b46` as LEVER prefix + complete
SWEEP_A tail + complete SWEEP_B tail, both tails hash-equal to their leg commits
per CRUX; the three state-colour cases are green under real PySide6
(`harness/panel_pd/runs/2026-09-04/qt_INTEGRATE_post_repair.txt`).

Full verdict: `docs/panel_pd/CRUX_VERDICT.md` and `crux.json` on the held
branch; integration report `docs/panel_pd/INTEGRATION.md`.

## Tests

Full suite on merged master `b246b78e` (Python 3.14.2, no `hou`, 3 m 49 s):
**7431 passed, 1 failed, 198 skipped** (`harness/notes/h22/pytest_v5630_master.txt`).
Base `6e3dd963` was 6941 passed / 1 failed / 192 skipped: +490 passing tests,
same single failure. That failure
(`tests/test_backfill.py::test_backup_is_taken_and_source_intact`) predates
both waves and is carried, unchanged.

Qt tier on the held panel branch (Houdini 22.0.400 python313 + PySide6 6.8.3,
offscreen): 243 passed / 22 failed — 15 inherited widths, 4 SWEEP_B sequence
probes that stop at layout spacing, 3 isolated-green pins.

## Not in this release

The five held panel legs. The Solaris hookups (`run_recipe` unregistered).
Joe's golden sphere/ground HIP and everything that needs it: golden capture,
T1–T3, P2–P5 on a real stage, image smoke, render latency and VRAM. Binding the
LIFECYCLE undo backend to the now-probed `hou.undos` symbols. Regenerating the
h22 symbol table so scout stops flagging them. Test-to-row bindings for the
acceptance command. GUI sign-off on the five camera regions.

## Standing RC blockers — waiver carried

The four standing RC blockers from v5.62.0 (`mutation_fail_closed`,
`hot_reload_gated`, `installer_host_targeted`, `ci_covers_shipping_surface`) are
unchanged by this release; nothing here touched their surfaces. Joe's
publish word on 2026-09-05 ("merge, then commit then push then update git
release") is recorded as re-signing the waiver for this release only.

Handoff: `docs/solaris_v3/INTEGRATION.md`, `docs/panel_pd/INTEGRATION.md`,
swarm dashboard artifact (session-scoped), memory note
`codex-plugin-swarm-traps`.
