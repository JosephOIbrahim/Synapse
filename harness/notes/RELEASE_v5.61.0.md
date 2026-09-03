# v5.61.0 — the build answered in six and a half seconds

Draft release notes. **Draft only — not published, no tag cut.** Publish is
gated on the release ritual (R.R verify) and Joe's re-signed waiver for the
four standing RC blockers. Every claim is receipt-backed on master (HEAD at
draft time `485aa425`). Where a claim needs eyes on a live Houdini it says
UNKNOWN, not green. Where the CTO seat got something wrong, it says so by name.

Scope: wave **BP3** — a first-principles blueprint (`docs/intake/blueprint-h22-worldlabs-intent.md`,
v0.3) executed as five builder legs (RECON, PROBE, STUBS, CORPUS, PANEL), an
adversarial crucible (CRUX, Fable 5, five parallel audit lanes) and a
house-cleaning census (TIDY). **All five builders SOUND or SOUND-WITH-NITS, zero
BROKEN.** Joe read the verdicts (`harness/battleplan/notes/BP3-CRUX_verdicts.md`)
and said `merge 1-7`; seven `--no-ff` merges landed in dependency order
(22437d4e → 5edbd5ee). **Nothing in this release is ratified**: the promotion
proposal ships `ratified:false`, the spatial lane diff ships unapplied, the
three tool candidates ship as signatures with no bodies.

## For artists

**Nothing moves under your hands in this one.** Five hardcoded values in the
panel stylesheet became design tokens (`python/synapse/panel/designsystem/qss.py`)
and the emitted stylesheet is byte-identical at all five density scales — the
crucible reproduced the five hashes. If the panel looks different to you, that
is not this release. Screenshots are UNKNOWN until your eyes.

**What is coming, said plainly.** Three Solaris tools are proposed, not built:
a Karma blocker light filter, an ordered image-filter list, a render-pass chain
— each with the precondition that makes it refuse (`docs/intake/h22-tool-candidates-2026-09-03.md`).
A spatial lane — floor, walls, openings, what's in frustum — is declared as an
unapplied diff. When those land, they land ratified and probed, not before.

## Under the hood

**The build answered in six and a half seconds.** 22 probes ran on hython
22.0.400 against a World Labs fixture: 21 RAN, 1 BLOCKED (P-6, an `OpNode`
without `.stage`). The crucible re-ran the whole suite on its own pinned hython
and got the identical 22-entry status map and identical fixture hashes
(`harness/battleplan/notes/bp3_crux_probe_rerun/`). Findings, each anchored in
`docs/reviews/bp3-h22-worldlabs-probes-2026-09-03.md`:

- Rob Pieke's SOP-side **`USD Create Component` exists on 22.0.400**; the world
  component was built through it (component path `sop_component`).
- **Gaussian-splat tooling is native** on this build (SOP/LOP/COP label search).
  The "no way to render splats" risk (R-4) is clear.
- **World Labs' collider is 46,993 triangles**, not the 100–200k their docs
  state (WL-EX-03 refuted by fixture; GLB accessor count == Houdini unpack count).
- **App exports carry no scale or ground metadata** (BLU-04 true). SYNAPSE derives
  them — the case the blueprint planned for. `husk --pass` confirmed.
- **One black render is a probe bug, not a Karma verdict.** B-7's EXR is all-zero
  RGB — measured by builder and crucible alike — and husk says `Total Lights: 0`
  with a camera-name mismatch: the CTO-authored probe created its camera after
  the render settings and never assigned it. R-1 stays **UNKNOWN**. Re-run after
  the fix is the first open item on the next capsule.

**138 scatter parameters seeded, 8 promotions proposed.** `harness/notes/scatterinstances_parms_22.0.400.json`
carries the Scatter Instances parameter surface (labels ↔ internal names) with
provenance; the earlier "167 parms" count is disclosed as a counting difference.
`docs/reviews/bp3-h22-promotion-proposal.md` proposes 7 VERIFIED-RUNTIME and 1
FIXTURE-VERIFIED promotions with a checker (`bp3_promotion_check.py`) that
exits 1 on any promotion without a stdout anchor — three crucible mutations
reddened it as designed.

**The panel's problem is adoption, not tokens.** The design-system audit
(`harness/battleplan/notes/BP3_PANEL_AUDIT.md`) scores the token authority
8.5/10 and panel-wide adoption 3.5/10: 492 literal px and 168 off-palette hexes
across 34 modules. Two pre-existing guard holes surfaced by crucible mutations —
the token authority is exempt from the hex scan by construction, and nothing
pins the panel's live timer intervals — are filed as spawns, not fixed here.

**Environment truths that bite.** Five hythons are installed (21.0.773,
22.0.400, 22.0.413, 22.0.417, 22.0.429); the hytest shim picks newest usable,
and 22.0.429 passes its gate — so an unpinned lane **will** probe a build with
no symbol table. Pin `SYNAPSE_HYTHON` to 22.0.400. The H22 prefs dir is the
OneDrive redirect; the old Documents path is absent. A deep-path fresh clone
silently loses `_vendor/anthropic` files without `core.longpaths`.

**Harness findings from running the wave (hardening items, not fixed here).**
The orchestrator died once at 15:04:35, in the drift-check path, on the one
poll where a leg had just settled and another had just launched — no stderr;
relaunched with cap continuity and it recovered all done legs from receipts.
`Backup-Branches` pushed leg branches without a human word, as it does every
wave. `readonly-settings.json` denies `git add`/`git commit` while allowing
scoped versions of both — deny wins, `git -C` is the leak, and the Haiku leg
stopped at the fence and asked; the CTO seat committed its report verbatim and
put the correction in its receipt. Mission-authoring rule learned: never tell a
leg to write anything after its receipt (W5H held CRUX at closing for it).

**Metered, not estimated.** Six Opus legs: ~102.8 M tokens in, ~1.5 M out,
~115 min agent wall. CRUX (Fable 5) and TIDY (Haiku) settle in
`harness/battleplan/runs/2026-09-03/ledger_orch_20260903-151611.json`.

## What does not ride

- **22 rulings** are banked across seven receipts and none is recorded. Merging
  a `ratified:false` proposal is not a ruling.
- **BP3-SPATIAL** (Mile 2, three read-only spatial tools) is held in the manifest
  for Joe's word after the rulings.
- **B-2 handedness** and **PANEL screenshots** are gui_required — UNKNOWN.
- **Four standing RC blockers** — `mutation_fail_closed · hot_reload_gated ·
  installer_host_targeted · ci_covers_shipping_surface` — unchanged since v5.51;
  published-over under Joe's waiver at v5.56.0, v5.58.0, v5.59.0 and v5.60.0.
  This release publishes only if that waiver is re-signed by Joe's word.

Handoff: `harness/notes/CAPSULE_2026-09-03_EOD.md`.
