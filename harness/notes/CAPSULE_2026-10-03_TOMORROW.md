# Capsule - for tomorrow-you (written 2026-10-02, about 15:20)

```
+== PROJECT CAPSULE: SYNAPSE, Demo Done Day (Wed 10/7 11:00) ===================+
| WHERE WE ARE:        v5.93.0 published and Latest (58214dc5, CI 6 of 6 green). |
|                      It carries the two camera-path tools (95fb0af5), the      |
|                      receipt fix (fb8736b1) and the footer's row of three      |
|                      (45210b3c). Claude's recorded panel check passed every    |
|                      step at 14:15. Joe relaunched Houdini at 14:51 on an      |
|                      untitled scene; it runs the shipped code.                 |
| MILE MARKER:         Done-day card: mile 4 of 6 is done. Mile 5 is Monday's    |
|                      take attempt. Freeze: Tue 10/6 EOD.                       |
| WHAT I WAS THINKING: The build is ahead of the take. What is left happens at   |
|                      the panel, and it is Joe's: his own look, and the calls   |
|                      from Friday morning's D6 test.                            |
| NEXT ACTION:         Joe's six-line look at the panel, on the demo scene       |
|                      (done-day card, Sea level, item 2). About two minutes.    |
| BLOCKERS:            Joe's: how Beat 2c shows the path; whether Friday's       |
|                      recording closes D6's last clause; the D5 pick; the OBS   |
|                      crop against the changed rail; RC-3 and RC-4 with his     |
|                      recorder; a saved desktop with the Synapse pane.          |
| ENERGY REQUIRED:     Low. Two minutes at the panel, then four short calls.     |
| IDEAS PARKED:        receipt credit from the undo stack; the receipt that      |
|                      stays after a hand undo; the empty-scene hint worded for  |
|                      a model; F8 test logs; the two release worktrees.         |
+===============================================================================+
```

## Where things live

- The release: https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.93.0, `docs/releases/v5.93.0.md`,
  `harness/notes/RELEASE_v5.93.0.md`.
- Receipts: `.token-saver/receipts/v5930_release.json` (the release) and `b3_build.json` (the row of three and
  its recorded check).
- The recording of the panel check: `2026-10-02 14-15-08.mp4` in OBS's recordings folder.
- Plan and run log: project doc `claude/DEMO_DONE_DAY_BLUEPRINT.md` (Sea level has Joe's calls in order);
  the take: `claude/TAKE_RUN_SHEET.md` (v7); the spatial plan: `claude/SPATIAL_BLUEPRINT.md`.
- The scripts that ran the release: `.token-saver/release/` (runbook at the top) and `.token-saver/b3/`.

## Words that unlock things

- "the beat is <scatter | blocker | passes>" - the on-camera Pieke request for the take.
- "it counts" or "Monday closes it" - D6's last clause.
- "crop it" - the OBS capture, so the footer and the changed rail are framed as wanted.
- "tidy" - remove the two release worktrees (`rel-v5921`, `rel-v5930`) and their branches.

## Three things learned today worth keeping

1. Before taking the screen, check that the PC has a display:
   `nvidia-smi --query-gpu=display_active --format=csv`. With the monitor switched away, Houdini captures white.
2. A suite started from the Windows-MCP shell skips 32 tests, because that tool sets PYTHONUSERBASE and
   VIRTUAL_ENV. Clear both in the .cmd. The skip count is the tell: 427 on a release worktree, 426 in the main
   checkout.
3. When two patches touch one file, commit the first from its patch into the index (`git apply --cached`) and
   the second from the working tree. Prove each tree id before its commit.
