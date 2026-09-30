# Release preparation: v5.89.0

Publish six commits on top of v5.88.0 (tag `v5.88.0` on `507153d4`): the three cook-fix commits
already pushed on Joe's word earlier on 9/30, and three from the Demo Done Day run. Joe's word, 2026-09-30, mid-run: "commit, git push & git release when you
close the loop", after "Confirm and execute all legs" for the Demo Done Day run
(`claude/DEMO_DONE_DAY_BLUEPRINT.md`, Miles 1-2). Rulings he gave the same day: R-2 ratified (a
named workstation profile), the recommended fix legs (D1 grounding, the 413 cap), a known
dimension as the scale source, and no preference on the ground tolerance (5 cm used).

| Commit | What it does |
|---|---|
| `d2811702`, `917cdbda`, `006c0ce9` | Already on master: TOP nodes cook via `cookWorkItems` at all seven call sites, and the tests assert it |
| `d4a139f8` | D1: a Marble world lands metric and on its ground under one `<import>_ground` Transform LOP; scale from export metadata or a sidecar naming its source; floor from the collider; 13 pure tests, the hython import test updated |
| `79303302` | R-2: the `workstation` render profile, Karma XPU with the local limits; 5 tests |
| `4f9a43f9` | F13: array attributes over 256 elements return a bounded summary; every tool result is bounded at 96,000 characters before it enters the panel's history; 5 tests |

The three new commits went to master first, on that word, with Gate C set for that one push
(`006c0ce9..4f9a43f9`).

## Evidence

- **Live, Houdini 22.0.400, fresh boot at about 13:45 loading this source.** RC-3: the 500k
  cobblestone-lane export imported through the World Labs dialog landed at scale 2.1362 (known
  dimension, two doorways at 2.10 m), ground offset 1.2897 m, measured ground height -0.016 m;
  USD's composed transform agrees within 3.7 mm. Gate PASS, Jev `evidenced` 0.91. RC-2b: request
  `b56ec003f6d44bdbb8215a461e1ad32e` on the workstation profile, 1 frame at 1280x720 and 64
  samples, complete, decoded and verified (render phase 44.6 s); hoiiotool decoded all 921,600
  pixels finite, and the sha256 matches the job record. Gate PASS, Jev `evidenced` 0.95. Receipts:
  `.token-saver/receipts/rc3.json`, `rc2b.json`.
- **GPU caveat, measured.** In that job the RTX 4090 rendered 0 of 64 samples (XPU compiled its
  kernels in the job's fresh runtime folder while its CPU device rendered). The notes say so.
- **Tests.** 23 new tests. Under hython 22.0.400: `test_worldlabs_native`, `test_worldlabs_grounding`,
  `test_farm_integration`, `test_farm_workstation_profile`, `test_tool_result_cap`: 70 passed.
  Full suite, Windows, Python 3.14, Houdini-only tests deselected, on the fix tree and again on
  the release tree: 10,493 passed, 426 skipped, 120 deselected, 5 xfailed, 0 failed, both times.
  Except ratchet: 1,360 broad and 983 silent, unchanged. `sync_version.py --check` PASS;
  `readme_check.py` PASS. CI on `4f9a43f9`: run 36757545039, all six jobs passed.
- **Jev.** Jev checked 13 claims from the notes against the code, or for the two measured
  claims the receipts, that could contradict them (citation-check pattern; supports at 0.8 or
  more stands). Eight stood. Five went to a direct read: three stood as written (the workstation
  profile's threads and limits, the seven `cookWorkItems` sites, the RC-3 numbers), and two were
  tightened (the ground node is named after the import with `_ground` appended, not
  `<world>_ground`, and acts on the world's parent prim; array bounds are returned only for
  numeric arrays). Ledger: `harness/jev/ledger/v5.89.0.release.notes.jsonl`.

## Decisions

- **Source release.** No installer was asked for, so no v5.89.0 Setup is built. The v5.86.0
  Setup stays the download.
- **5.89.0.** The importer now adds a node and moves the display flag, and the render workspace
  gains a profile, so the minor version moves.
- **Timing.** Published before RC-4 has run. On Joe's "use JEV for decisions and routing
  suggestions and orchestrating legs", Jev chose release now over holding for RC-4 (0.95,
  confidence 0.91; `.token-saver/legs/orchestrate_m2.json`). A memory-path fix, if RC-4 needs one,
  goes in a later release before the freeze.
- **Docs corrected in passing.** `docs/tops/RENDER_WORKSPACE.md` still said the workspace was being
  qualified in an isolated worktree and had not been deployed; it ran live on 9/30 from the
  repository, and the paragraph now says so. The status page no longer says a Karma beauty render
  is unestablished; an authenticated World Labs import still is.

## Not in this release

RC-4 (memory round-trip after a fresh reopen) needs Joe's permission click and voice, and has not
run. Parked by the Jev scope guard until after Oct 7: a kernel cache shared across render jobs,
the render workspace starting the bridge by itself (0.51 alone, 0.35 in the batched screen with
fuller facts), freezing the splat once per
job instead of per frame, worker-log text in failed-job reports, and TOP-network lookups under
/obj.

This record does not claim that the later CI, push or publication steps have completed. They are
checked after publication.
