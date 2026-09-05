# v5.64.0 — the panel landed, and the loop learned to check itself

Release notes. Every claim is receipt-backed on master (HEAD at draft time
`74dc0219` plus the release bump, 2026-09-05 evening). Where a claim needs eyes
on a live Houdini it says UNKNOWN or GUI-GATE, not green.

Scope: one CTO review swarm over v5.63.0 (15 agents, 7 lanes, one refuter per
lane), one forge swarm that landed seven of its findings (16 agents, one
crucible per branch), one panel support team that took the held Panel PD wave
through a Pentagram-bar audit, a second forge pass and CRUX round 3 (10 agents),
all orchestrated from Claude Code (Fable 5.1) with Joe's pre-approval of
branches and merges. Every merge is `--no-ff`; every item is closed by
re-running its closure predicate on master, never by receipt.

## For artists

**The panel changed.** The Panel PD design wave that v5.63.0 held back is on
master (`74dc0219`, 202 files). One owner of rhythm and colour
(`designsystem/rhythm.py` plus role rules in `designsystem/qss.py`), five camera
regions on roles, the recall card, 18 modules migrated. Panel-wide imperative
spacing 107 to 17 sites (all tagged), inline stylesheets 106 to 0, raw hex 135
to 0 (`harness/notes/panel_rhythm_census.py` on master).

What you will see, in operator words: the same wordmark, header and faces, now
on one spacing grid; the 30 px panel gutter restored on every edge container;
the WORK and REVIEW faces on the same inset as the chat face; the gate widget's
badges back in Space Mono; the composer never pushes Send below a short dock
and never clips the wordmark at 340 px wide.

**GUI sign-off is still Joe's eyes** (Houdini 22.0.400, curious / expert / ml):
profile tab strip, header and ribbon, chat transcript, verb rail, recall card,
TOKEN face. Headless gates are green; the live look is UNKNOWN until seen.

Three fixes you may feel without knowing why: the composer remembers your drag
on a tall dock but caps to a short one (B4); four render recipes now build
`usdrender_rop` instead of the deprecated `karma` LOP (B6); the memory backfill
no longer doubles the source `memory.jsonl` under Moneta dual-write (B5).

## Under the hood — the CTO review loop (`harness/cto/`)

A closure-first review loop: SWEEP re-runs every open item's predicate before
FIND, so the next crank measures what landed. First crank on v5.63.0: 61
findings confirmed, 0 refuted (a calibration flag, recorded as such). Landed
today, each on its own branch with a crucible verdict, merged on Joe's word:

- **B1** an unguarded function-level `pxr` import turned GitHub CI red on both
  v5.63.0 commits. Guarded; CI green at `e8913f83`, the first green master run
  since 2026-07-29.
- **B2** the phantom checker's walker never descended SWIG namespace instances,
  so `hou.undos.*`, `hou.hipFile.*`, `hou.hda.*` were false phantoms.
  `host/introspect_runtime.py` now recurses root-typed namespaces; the h22
  symbol table was regenerated on 22.0.400 (+564 symbols, strict superset);
  recipes `transaction.py` is bound to `hou.undos`; rulebook docs name the
  interim authority honestly (no fake harvest script).
- **B3** the Solaris v3 P4 CompositionVerifier failed on every live LOP stage
  (Houdini `anon:` sublayers read as missing assets). Ignored now; first host
  run of `tests/test_recipe_verify_hython.py`: 4 passed.
- **B4** the panel design gate had been red and unrun since 2026-08-03. The
  composer is capped to its pane, the wordmark audit re-pinned to WORDMARK
  0.16em (7780f649, Joe's call), the audit isolated from artist settings
  (`SYNAPSE_PANEL_SETTINGS`).
- **B5** `test_backfill` was a Moneta dual-write data-safety bug, not flake.
  Fixed; CI now exercises `SYNAPSE_MEMORY_BACKEND=moneta`.
- **B6** the deprecated `karma` LOP emitted by four recipes and `planner.py`,
  and a phantom `grade` node. Now `usdrender_rop` and a real type; the
  extractor gate is extended. The vocabulary ruling (which "recipe" the panel
  teaches, whether `route_chat` gets a command channel) is still Joe's.
- **B7** the RSI registry was stale under its own law. P10 cited-path
  liveness added, A3 retired, loop C evidence corrected, CHAMPION counts fixed.
- **B8** release truth drift. README, CLAUDE.md and the capsule are at v5.63.0
  truth, the three 09-04 predicates recorded OPEN, receipt hashes no longer
  name missing files.
- **B10** the Houdini build pin was folklore. `hytest` prefers the
  symbol-table build and prints its choice (`--which`); `SYNAPSE_HYTHON`
  documented; the deploy skill targets houdini22.0.

## Under the hood — Panel PD landing

Audit verdict on the held branch as it sat: DOES-NOT-MEET the Pentagram bar
(gutter token deleted rather than applied, two type appliers per widget,
profile pills as 116 by 70 blocks, census gamed to raw-zero) but LANDABLE after
nine forge steps. CRUX round 3 (referee plus design warden) then caught three
more the forge's own gate missed: the gate widget fell to Courier after a font
purge, the WORK and REVIEW faces lost their inset, two test-hygiene pins. All
repaired and pinned (`tests/panel/test_docking.py`,
`tests/test_panel_camera_rhythm*.py`, `tests/test_panel_rhythm_docking.py`).

Rulings signed under Joe's delegation (`harness/cto/runs/2026-09-05/`):
RULING-1 residual colour sites owned now, at most 20 all tagged (landed at 17);
RULING-2 docking measurement fixed first (the 15 "too wide" widgets were
measured with an empty font database), the contract stays PANEL_MIN_WIDTH 280,
interim per-density width feature airy 400 / standard 380 / tight 380
(R3-01); RULING-3 the HDA Result stays dark (the "before" was an un-sheeted
Fusion render). Open: **B11**, the verb rail collapsing to icons below about
360 px, the real fix toward 280.

## Tests

Full suite on merged master `74dc0219` (stock Python 3.14.2, no `hou`, 4 m 07 s):
**7604 passed, 0 failed, 331 skipped** (`harness/notes/h22/pytest_v5640_master.txt`),
the first zero-failure full run on record. Skips rose from 198 because the
panel wave's PySide-bound tests skip under stock Python; under hython they run.
Panel tier on Houdini 22.0.400 offscreen: `tests/panel` plus docking **211
passed / 1 failed** (`test_dead_verb_hidden`, the D1 render-view no-op,
pre-existing); python313 docking 91 passed; G3 strict **pass**, 1 pre-existing
WARN (3 interactive targets under 26 px). The hython full tier was not re-run.

## Not in this release

Live GUI sign-off (Houdini was not running during the landing; hython offscreen
only). The recipe vocabulary ruling and the `run_recipe` hookup. Joe's golden
HIP for Solaris v3 and everything behind it. The verb-rail collapse (B11). The
three 09-04 predicates (spatial default-on, panel font floor, splat colour in
EXR), still OPEN and carried. Pushing the `pd/*` backup refs and deleting them.
The Bierut design review (running at draft time; its canvas lands separately).

## Standing RC blockers — waiver carried

The four standing RC blockers from v5.62.0 (`mutation_fail_closed`,
`hot_reload_gated`, `installer_host_targeted`, `ci_covers_shipping_surface`)
are unchanged by this release. Joe's release word on 2026-09-05 ("Release")
carries the waiver forward; nothing here touched their surfaces.
