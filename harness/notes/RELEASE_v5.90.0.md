# Release preparation: v5.90.0

Publish two commits on top of v5.89.0 (tag `v5.89.0` on `d193b7ec`). Joe's word, 2026-09-30, evening:
"commit, git push, git release when ready", after "we need to use Karma XPU via GPU as well" (18:45) and
"continue". The Render row commit was pushed on his "yes" earlier that evening.

| Commit | What it does |
|---|---|
| `4a64b966` | Render returns as a full-width row at the foot of the panel, under the footer's unchanged grid; it opens the render workspace |
| `9bdd994f` | XPUCACHE: the workstation render worker reuses this machine's Karma XPU caches (OptiX's module cache and houdini_temp); 4 tests |

## Evidence

- **The cache is the lever, measured 9/30 19:00 on the RTX 4090.** RC-2c's frozen frame 1 rendered with the
  worker's exact environment and husk flags (`.token-saver/xpucache/ab_*`): fresh cache 40.3 s wall, 0% GPU,
  21 kernel and 4 shader compiles; this machine's caches 5.8 s, 64% GPU, no compiles. OptiX's cache alone and
  houdini_temp's alone each gave 0%. A new persistent folder stayed at 0% over three runs, falling to 3
  compiles a run (max 14 s), the same pattern as RC-2c's 120 frames.
- **Through the Render view's own service.** Request `b9284233f9284d8eae891eb084614dbe` (2 frames) through
  `FarmService` and `NativeTopsBackend` with the change: complete, both frames verified, 1.6 s render each,
  GPU 59%, no compiles, 16.3 s render phase. Then request `5ea003275984434d84fff62567dd0bbf`, the demo scene's full 120-frame arc through the same path: complete, 120 expected, decoded and verified; sha256 matches the record on all 120; all finite, none constant, all distinct; camera on the arc to 0.0 m at frames 1, 30, 60, 90 and 120; GPU 57.8-68.8% of samples on every frame (median 62.5%); no kernel compiles; per frame 1.53 s of render and 5.52 s of husk wall at the median; 790.9 s render phase, against RC-2c's 3,141.9 s at 0% GPU. Gate PASS, Jev `evidenced` 0.93. Receipt: `.token-saver/receipts/rc2c_gpu.json`.
- **Tests.** Full suite, Windows, Python 3.14, Houdini-only tests deselected (the CI command), on the fix tree and again on the release tree: 10,497 passed, 426 skipped, 120 deselected, 5 xfailed, 0 failed, both times. Under hython 22.0.400, the farm tests: 77 passed. Except ratchet 1,360 broad and 983 silent, unchanged. `sync_version.py --check` PASS; `readme_check.py` PASS. CI on `4a64b966`: run 36781255180, all six jobs passed; CI on `9bdd994f`: run 36790967056.
- **Jev.** The scope guard scored XPUCACHE 0.38 (park) with route claude_now (0.41); Joe's call stood. Jev checked the six claims in the release notes' validation section against the diff since v5.89.0, the commit subjects, the code change and the measurement records (citation-check pattern). All six came back partial, under the supported bar, so each went to a direct read: five stood as written, and one was tightened (the eight hython panel failures were measured on the Render row's tree and a clean v5.89.0 tree, not on the release tree). The 120-frame result was added to the notes after this check. Ledger: `harness/jev/ledger/v5.90.0.release.notes.jsonl`.

## Decisions

- **Source release.** No installer was asked for; the v5.86.0 Setup stays the download.
- **5.90.0.** The panel gains a control and the render worker's environment changes, so the minor version moves.
- **The machine's caches, not a persistent SYNAPSE folder.** A persistent folder was the first design; three
  runs showed it never fills from one-frame husks, so the worker reuses the caches interactive Houdini and
  longer husk runs already complete.

## Not in this release

Batching frames per husk process, which would let a cold machine warm its own kernels inside one job, is not
built. The H22 Render Queue's resolution check (it compares EXRs to a resolution attribute's default, not its
time samples) is Joe's tool and is logged in the blueprint, not changed here.

This record does not claim that the later CI, push or publication steps have completed. They are checked after
publication.