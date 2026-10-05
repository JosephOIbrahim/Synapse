# Release preparation: v5.94.1

Publish three commits on top of v5.94.0 (tag `v5.94.0` on `4ee01959`). Joe's words, 2026-10-05: at about 08:30,
"go & fix" (the second resolver run, and the real-USD fallback); at about 08:53, "Merge & label" (the fix onto
local master, with the label change); at about 09:40, "Screen is yours" (the GUI checks and the rehearsal, his
hands off); at about 10:15, "i want to do EVERYTHING pre-demo today. This is the day to wrap ALL coding
pre-demo."; at about 10:30, "borrow now. go!" (the memory question on the demo scene, then this release).

| Commit | What it does |
|---|---|
| `d33570f2` | The README and the architecture overview describe v5.94.0. On origin since 10/4, CI green there. |
| `69faef48` | Closing a Moneta-backed store releases the engine target's root layer, so a reopen keeps real USD. |
| `377e5cca` | The Scatter resolver's collider label reads "import record, grounding collider". |

## Evidence

- **The reopen under hython.** 22.0.400, scratch stores (`.token-saver/usdfix-20261005/repro.py`,
  `rebind_write.py`). Without the fix: open 1 has real USD, the root layer is still registered after the close,
  open 2 logs the failure and returns the mock target. With it: three opens keep real USD and the layer is gone
  after each close. `rebind_owner` carried one record and verified it; a record added afterwards was in the
  snapshot, the mirror and the typed cortex, and a later open read both.
- **The rebind in the GUI.** Houdini 22.0.400 on `377e5cca`, computer use, the pane added in an untitled session,
  then `rc3_scatter20_look.hiplc` opened. `synapse.log`: "Loaded 2026 memories" at 09:44:36.016 and 09:44:37.618,
  no failure line. Doctor: "PASS - use real usd: USD authoring enabled". The two loads again at 10:09:57.835 and
  10:09:59.433, in Joe's own session (pane first, then `rc3_demo.hiplc`); Doctor was not run there. On 10/4 the
  failure line is in the log at 12:54:45, 14:25:41, 19:36:11 and 20:36:21. The commit message of `69faef48` says
  three times; the log says four.
- **The label.** Ledger row 08:38:09, Houdini on `d33570f2`: the vendor's name is in the resolver result and in
  the build result, and in no reply. Row 09:48:28, on `377e5cca`: the new label is in both results and the name
  in neither. Scans of both rehearsal conversations and of the 10:37 conversation: no hit.
- **Resolver runs.** Row 10/4 20:37:32: 3 calls, 71,807 input tokens. Row 10/5 08:38:09: 3 calls, 71,711, 6.7 s.
  Row 09:48:28: 3 calls, 68,397, 8.3 s. Each at `maxangle` 20 with no corrections. The first two were the second
  request of their session, after a memory question; the third was its session's first. Row 08:39:28 read
  `protoIndices` from the stage: 758.
- **The rehearsal.** 09:50 to 10:04 on `377e5cca`, in `rc3_scatter20_look.hiplc` (a copy of the demo scene, never
  saved), typed through computer use with Joe's hands off, not recorded. Row 09:52:00, the landing question:
  1 call, 4.2 s, 43,097 input tokens. The render: 24 frames admitted, 24 outputs, "24 of 24 frames verified",
  1280 x 720, 64 samples. Row 10:00:00, Scatter: 4 calls, 7.3 s, 120,114 input tokens; four nodes at `maxangle`
  20, no corrections, 758 in the reply. The camera-path read was answered by the panel with no model call. Row
  10:02:36, the memory question after a quit and a relaunch: 1 call, 4.5 s; the reply recited "45 degree" and
  "763 instances".
- **Joe's decision.** Row 10:10:23: Joe pasted the 20-degree decision into the panel himself. One `synapse_decide`
  call returned `mem_9a736b186e29`. The scene's notes hold both Scatter decisions, and the next open loaded 2,027
  records.
- **The memory question after it.** Row 10:37:23, a fresh launch on `rc3_demo.hiplc` with the scene opened before
  the pane, on `377e5cca`: 1 call; the landing numbers; both Scatter decisions in order; "That tightening
  supersedes the earlier numbers". No vendor name. The scene file's hash was the same before and after
  (`d3c86829`), and Houdini quit with no save prompt. The turn took 22.4 s, where the same question took 4.5 s at
  10:02: 21.2 s to the first token and 1.0 s in the tool. The wait was the cloud model's.
- **The suite.** The CI command on `377e5cca`, Windows, Python 3.14, home folder on scratch, no `SYNAPSE_*`
  variables and none of the venv variables this shell inherits (`.token-saver/usdfix-20261005/full2.log`):
  10,923 passed, 430 skipped, 186 deselected, 5 xfailed, 0 failed. An earlier run inside the inherited venv hid
  32 tests behind skips (10,891 passed, 462 skipped) and is not the one quoted. Not re-run on the release tree:
  the release commit changes version strings and documents only, and CI runs on it before the tag is pushed. On
  the release tree, the README receipt, version conformance and tool-count tests passed on Python 3.14 and on
  3.11, and CI's second and third pytest steps passed on 3.11 with the engine on the path.
- **The tool journal.** `rc3/claude/journal.log` since 9/30: 40 `synapse_project_setup` lines, 24 of them failed
  ("Integrity check failed: fidelity=0.0"). 14 of the 24 are followed by a success within two seconds and 10 are
  not. The four panel turns on `377e5cca` that began with that call (09:48:22, 09:51:58, 10:02:33, 10:37:08)
  each show the failure and the success in the same second, and one successful call in the turn ledger.

## Decisions

- **The fix is in SYNAPSE, not in Moneta.** The cause is in Moneta's `UsdTarget.close()`. Moneta is another
  repository and Joe's word covered this one. The fix clears a private attribute from outside, and the notes say
  so.
- **Released the same day, on Joe's word.** Jev at 08:50: releasing after the rehearsal 0.83, and that the fix's
  go already covered a release 0.09. Jev at 10:04, after the rehearsal: releasing now 0.32, and that Joe's own
  run-through was still needed 0.79. Jev at 10:18: that "everything pre-demo today" covered a public release
  without asking 0.16, and releasing before the memory reply had been seen again 0.36. So Joe was asked, he said
  "borrow now. go!", and the memory question was asked before anything was released
  (`.token-saver/merge-20261004/jev-ledger/`).
- **v5.94.1, not v5.95.0.** Two fixes. No default changes and no tool gains an argument.
- **Not investigated today.** The failed first project-setup call (Jev 0.17) and the remaining post-demo cards
  (0.04).
- **The pin waits for Joe.** His own run-through, voice and hands, comes after this release on a relaunched
  Houdini. The pin names the commit after that.
- **JEV.** For the notes, 28 claims from the validation and limits sections were checked in one request
  (`harness/jev/ledger/v5.94.1.release.notes.jsonl`): 16 came back supported, 11 partial and 1 unsupported. Each
  flagged claim then went to a direct read against the turn ledger, the tool journal, the log and the archived
  conversations. The unsupported one (0.69) said the fourth Scatter turn differed by reading the count back; it
  also made no lookup, and the bullet was rewritten. Reworded after the request: the second rebind session
  (Doctor was not run there), the log sentence (it now names `synapse.log` and points at the journal's failed
  first calls), the resolver runs (two of the three followed a memory question in the same session), the
  camera-path sentence (now what the read said), the ten failures with no success within two seconds, and the
  two hython tests. Left as written after the read: the first rebind check, the new label in both results, the
  one-call memory answer, and the four turns that recovered.

## Not in this release

- **The fix in Moneta's own `close()`.**
- **The cause of the failed first project-setup call.**
- **Doctor's "moneta substrate" row.**
- **A retired note.** The older Scatter note is still in the scene's notes and is still read back.
- **Guarded mutation, the panel layout, the many-parameters tool, history trimming.** After the take.
- **Joe's own run-through, and the pin.** After this release.
- **A recorded take.**
- **A Windows Setup.**
