# Release preparation: v5.91.0

Publish one feature commit on top of v5.90.0 (tag `v5.90.0` on `4bf126a3`). Joe's word, 2026-10-01, relayed by
the orchestrator: commit and release the working-tree changes as v5.91.0 before the Tue 10/6 freeze. No quote of
his is on disk; the orchestrator holds it.

| Commit | What it does |
|---|---|
| `36f8e7db` | build_graph inserts between existing nodes with `insert: true` (re-route only), places the splice inline or beside, cooks and badge-checks what it built with whole-build rollback, frames it in the Network Editor; scene_template lays out only its own nodes and keeps the display; panel prompt recipe and build-reply rule, Ollama budget 16,384, a visible token-limit message, capture tool kept from text-only models; 3 new test files |

## Evidence

- **Live take, 10/1 10:58 (before the inline layout and the round-2 polish).** `.token-saver/rc3/claude/conversation.json`
  and `journal.log` line 1371: one `synapse_solaris_build_graph` call at 10:58:51 (40 ms) with `insert: true` on
  rim -> dome; result `created`, `parms_missed` [], connections verified, parameters applied, badges checked with
  no errors, warnings or inherited errors, display `demo_settings` preserved, `framed: true` (pre-P4 code:
  handlers_solaris_graph.py was saved 11:10, and P4 arrived in round 2 per `.token-saver/net/mail/BUILDER_to_DIAG_review2.md`).
  `houdini_query_prims` then found `/lights/dusk_key` and `/lights/dusk_rim`. The text-only model called
  `houdini_capture_viewport` twice and neither capture was sent, which is the receipt for the roster change.
  The orchestrator reports that one undo in the GUI removed the build; there is no on-disk receipt for that GUI undo.
- **hython, round 2, current code.** `.token-saver/net/proof_round2.json` (a fresh copy of rc3_demo.hiplc):
  0.027 s; dusk_key at (-1.692, 1.516) and dusk_rim at (-1.692, 0.622); demo_dome, demo_cam and demo_settings
  shifted dy -1.7884 each, receipt == measured; display unchanged; cobblestone_lane cook count 1 -> 1; one
  `performUndo` restored positions, names, wires and display; `splice_layout: "side"` moved no existing node.
- **hython, round 1.** `.token-saver/net/proof_build.json`: refusal without `insert`, names unchanged; rerun
  `unchanged`; badge rollback (0.154 s, names unchanged), splice rollback restored demo_dome's input to
  look_fade_10, `badge_check: false` kept the node; inherited error from an erroring pythonscript look node kept
  the build with two warnings; scene_template on the populated copy moved no existing node and kept display
  `demo_settings`, and on an empty network displayed `render_settings`.
- **Reviews.** `.token-saver/net/mail/DIAG_review.md` (round 1, fix first: C1-C4, inherited errors, display steal;
  all fixed) and `DIAG_review2.md` (round 2, fix first on the build-reply wording only; fixed with the pin test
  tests/test_build_reply_rule.py). The 4096-token cut (`stop_reason=length`) and the 16,384 probe on
  deepseek-v4.1-flash:cloud come from DIAG_review.md.
- **Tests.** The three new files: 56 passed (run 10/1 by RELEASE-PREP). Full suite, the CI command, Windows,
  Python 3.14, on the fix tree: 10,553 passed, 426 skipped, 120 deselected, 5 xfailed, 0 failed
  (`.token-saver/net/pytest_full_r3.log`). Release tree, same command after the release edits: 10,553 passed,
  426 skipped, 120 deselected, 5 xfailed, 0 failed, exit 0 (`.token-saver/release/pytest_release_tree_v5910.log`).
  `sync_version.py --check` PASS; `harness/notes/readme_check.py` PASS.
- **Jev.** Jev checked the eight claims in the release notes' validation section against the working-tree diff
  since v5.90.0, the three new test files, the drafted feature-commit subject, the code change, the live take and
  the hython receipts (`.token-saver/release/jev_notes_v5910.py`; the RECORDED-TEST placeholder was excluded, so
  the orchestrator's filled-in result is not Jev-checked). All eight came back partial, none unsupported, so each
  went to a direct read: five stood as written, and three were tightened (the test list says framing is tested
  with a faked editor as well as without a UI; the network-box limit says undo restores the box; an unlisted
  Ollama vision model "can" lose the capture tool). Ledger: `harness/jev/ledger/v5.91.0.release.notes.jsonl`.

Recorded test, 12:22 on 10/1 (OBS `2026-10-01 12-22-04.mp4`), the release tree in the GUI on the demo scene: the same prompt became one build_graph call with insert:true; the two lights landed inline between look_fade_10 and demo_dome in a straight column; the capture tool was out of the text-only model's roster (102 tools); one undo restored the chain and every position. The reply took 20 tool calls and about 90 s and said plainly it could not show a render (no vision, no render ROP); tightening that reply is open.

## Decisions

- **Source release.** No installer was asked for; the v5.86.0 Setup stays the download.
- **5.91.0.** build_graph gains a wire flag and three parameters, and its receipt gains fields, so the minor
  version moves.
- **Splice is opt-in and re-route only.** An occupied input is still refused unless the wire says `insert: true`
  and the displaced node feeds the new nodes in the same call.
- **README.** Its Setup paragraph still listed "v5.87.0, v5.88.0 and v5.89.0" after v5.90.0; it now reads
  "v5.87.0 through v5.91.0", as the status page does.

## Not in this release

From DIAG round 2, post-demo: fall back to the side column when a shifted node is in a network box or would
overlap an unrelated node; return `length` instead of an empty tool call when a token-limit stop cuts a tool
call; deny the capture tool at dispatch when it is dropped from the roster; consider `frame: false` by default
for external MCP builds. The "fps = 24" line seen under the new lights is not written by SYNAPSE as far as the
headless check could see; its source is UNKNOWN without the GUI.

This record does not claim that the later CI, push or publication steps have completed. They are checked after
publication.
