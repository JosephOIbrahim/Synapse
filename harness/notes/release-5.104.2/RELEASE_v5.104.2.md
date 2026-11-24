# Release record — v5.104.2

**Prepared 2026-11-23. This record describes the state at the release commit that carries
it: before the release gate's runs on that commit, the tip review, the crux record, the
push, the tag and the release page exist.** The Gates table is authoritative for that
snapshot and for nothing later. Once the crux record, the tag and the page exist, its open
rows are superseded, and the tag is the authority.

## Candidate

- Base: the `v5.104.1` tag, `8115d3c2`. It was also `origin/master` when the release branch
  was made (fetched just before), so pushing this branch to master is a fast-forward.
- Scope: the session-end lane and the audit lane (the owner's decision, 2026-11-23). A third
  lane, undo work, failed the review that set this release's scope (the owner's S1 fallback)
  and is not in this release; this release's text makes no undo claim.
- Content, in order:
  - `fix/mcp-initialize-no-preload`, merged `--no-ff` as `c19589de`:
    - `b00a4572`: initialize runs no project_setup preload on Houdini's main thread;
    - `63af6a9b`: ending a session does no Houdini or file work on the request thread;
    - `cc454e51`: session-end records are coalesced, cut off at the end time and labelled,
      with the records switch;
    - `dfe7358a`: a WebSocket disconnect queues its session-end record;
    - `b5ababf6`: session-end records end at the last request and say what they wrote.
  - `fix/audit-panel-model-readout`, merged `--no-ff` as `724d766d`: `1c0f7e53`, `d404ab49`
    and `155bc008`, the audit's model-readout checks.
  - The release commit: VERSION and its propagation, the release text, this file,
    `docs/RELEASE_CARD.md` (the new commit chain, and the `TAGS.md` commit after publish),
    and the description of `synapse://project/context` in `python/synapse/mcp/resources.py`
    with its pin in `tests/test_mcp_protocol.py`.
- Read the exact list with `git log --oneline 8115d3c2..HEAD`.
- The merged tree: `git diff --shortstat 8115d3c2 724d766d` gives 19 files changed, 3868
  insertions and 382 deletions, and every changed file's blob equals its lane tip's blob.
  `scripts/product_surface.py --diff 8115d3c2 724d766d` lists 7 shipped files, all under
  `python/synapse/`. `git diff --stat 8115d3c2 724d766d -- installer/ packages/` is empty.
  The release commit changes no file under `packages/`, and under `installer/` only the text
  of `installer/README.md`, which Setup does not package (`installer/build_payload.py`,
  `installer/build_windows.py`).

## Evidence that exists at this commit

**Merge check: the stock suite on the merged tree.** The release's fenced stock runner
(`run-stock.sh`, kept outside the repository) refuses to run while a Houdini-class process
runs, uses scratch HOME, TEMP, log, ledger and audit folders and a dead WebSocket port, sets
`SYNAPSE_JEV=off` and selects `-m "not live"`. Python 3.14.2, `tests/`, on `724d766d` before
the release edits. An excerpt of the run's `stamp.txt` (the tree's local path removed), then
the last line of its log:

```
STOCK_START TREE=<omitted> HEAD=724d766d8aaca7424dd01c3747acb3d4b87dd760 AT=2026-11-23T22:05:17Z PY=Python 3.14.2 EDITS=0
STOCK_DONE HEAD_BEFORE=724d766d8aaca7424dd01c3747acb3d4b87dd760 HEAD_AFTER=724d766d8aaca7424dd01c3747acb3d4b87dd760 EXIT=0 AT=2026-11-23T22:14:43Z TREE_MANIFEST=unchanged
= 13515 passed, 735 skipped, 11 deselected, 10 xfailed, 783 warnings in 556.66s (0:09:16) =
```

The baseline is the same runner's run on `1724cfbf`, a local merge of `b00a4572` onto
`8115d3c2` that is not published (2026-11-23): 13,465 passed, 0 failed, 735 skipped,
11 deselected, 10 xfailed. Per-file comparison (a script kept outside the repository that
follows wrapped progress lines):

| File | Baseline | Merged tree | Why |
|---|---|---|---|
| `tests/test_mcp_initialize_main_thread.py` | 4 passed | 33 passed | the lane's rounds 2 to 4 |
| `tests/test_ws_disconnect_session_end.py` | (new) | 21 passed | the WebSocket disconnect tests |
| `tests/test_agent_state.py` | 74 passed | 75 passed | the end-time cutoff test (`cc454e51`) |
| `tests/test_mcp_protocol.py` | 93 passed | 92 passed | two preload pins deleted, one renamed, one added |

All other 778 files are identical; 781 files became 782; skips stayed at 735; 0 new
failures. The lane lowered the except-ratchet baseline for `python/synapse/mcp/server.py`
from 7 to 6 (`tests/fixtures/except_ratchet_baseline.json`). The audit lane's
`tests/test_panel_faces.py` skips under stock CPython, because it needs hython and PySide6.

**Session-end lane, round 4**, on the tree committed as `b5ababf6` (the committed diff's
sha256 equals the reviewed snapshot's). The logs are kept outside the repository.
- 25 test files in one session (the round's 10 named test files, plus every test file that
  imports the WebSocket server, the session module or the resources module), scratch home:
  630 passed, in each of two runs.
- `tests/test_mcp_initialize_main_thread.py` and `tests/test_ws_disconnect_session_end.py`,
  five separate runs each: 33 and 21 passed every time.
- Red control: the round-3 snapshot with round 4's tests gave 9 failed and 137 passed. The 9
  are the new tests written to fail there.
- Earlier red controls: `b00a4572`'s tests on `8115d3c2`, 5 of the 8 new or changed tests
  failed for the intended reason; `63af6a9b`'s 8 new tests on `1724cfbf`, 7 failed for the
  intended reason; `dfe7358a`'s 15 new tests, 14 failed on both `1724cfbf` and `cc454e51`.
- The round-4 review planted 6 faults in the lane's code; each was caught by at least one
  test.

**Audit lane, round 3**, on the tree committed as `155bc008` (the committed diff's sha256
equals the reviewed snapshot's), hython 22.0.400:
- `audit_panel.py --strict`, default scratch settings: `G3 RESULT: pass · 2 WARN`. The same
  audit on unmodified 5.104.1 gave 4 FAIL and 2 WARN. Both WARNs predate the lane (3 distinct
  hierarchy steps; 10 of 32 interactive targets under 26 px).
- Pinned settings: "pass · 2 WARN" for Nemotron, a stale pick, a kept long id and three long
  Ollama tags. A configured Custom engine and the Ollama default each gave 1 FAIL, the
  "model picker" row, which needs at least 2 models. An unconfigured Custom engine gave 4 FAILs:
  label on both readout rows, active engine mark and model picker. Every run kept `provider_id`
  and opened no dialog.
- Negative control: 33 of 33 variants behaved as expected. The 24 planted faults failed (exit
  1), and the 9 baselines and allowed cases passed (exit 0).
- `tests/test_panel_faces.py`: 38 passed (36 of 38 on 5.104.1).

**On the edited tree, before this commit**: the release text writer's runs in the release
worktree on the final text, after round 5's six wording fixes, with Python 3.12.10 and pytest 9.0.2, one
file per run, `-B -p no:cacheprovider`, and scratch HOME, USERPROFILE, TEMP, TMP, log, audit,
ledger and provenance folders. pytest's summary lines:
- `scripts/sync_version.py --check`: `canonical=5.104.2  verdict=PASS`.
- `tests/test_mcp_protocol.py` 92 passed; `tests/test_readme_receipt.py` 9;
  `tests/test_help_page_honest.py` 4; `tests/test_help_pages_older_honest.py` 3;
  `tests/test_sync_version_help_page.py` 2; `tests/test_phase0c_doc1_version_conformance.py` 11;
  `tests/test_help_archive.py` 15; `tests/test_xref_help.py` 42;
  `tests/test_w4_help_build_param.py` 11 passed and 4 skipped (build 22.0.368 is not installed
  here); `tests/test_tag_release_crux_record.py` 32; `tests/test_phase0c_doc1_toolcount.py` 28;
  `tests/test_installation_setup_wording.py` 4; `tests/test_reach_public_agreement.py` 15;
  `tests/test_pass7_per_agent_and_canonical.py` 26; `tests/test_router_internals.py` 30;
  `tests/test_undob_live_undo_grouping.py` 10; `tests/test_needs_houdini_marker.py` 18;
  `tests/test_harness_githooks.py::test_release_card_step_13_names_the_gate` 1. No failures.
- The writer's red control for the description pin (kept outside the repository), in the test
  process: with the served description set to the merged tree's text, 5.104.1's "Auto-loaded
  on session start" text or six other wordings that offer or name the resource, the pinned
  test fails; with this commit's text it passes. 9 of 9 variants behaved as expected. Three of
  the six are built like the wordings review round 2 found passing the round-2 pin (a
  `synapse://` URI, "open this URI", an offer placed before the colon); the round-2 pin's
  checks, re-applied in the same script, pass all three.
- The writer's link check (kept outside the repository) resolved every relative link in the
  notes, this record, README, CHANGELOG, the installation, status, architecture and installer
  pages, the release card and the help page: 357 links, 0 unresolved.

**Owner's checks on the 5.104.1 seat**, 2026-11-23, after its install: `synapse_ping` answered
from a fresh session, which closes 5.104.1's auth limit, and Doctor read 5.104.1 with
`moneta_substrate` PASS.

**Not checked.**
- Nothing in a Houdini window. The first Connect after the 5.104.2 install is the end-to-end
  check of the handshake.
- The session-end recorder on Houdini's real main thread. Its read needs `hdefereval`, which
  imports only in a graphical session, so the tests drive it with a stand-in. The first
  Connect of a fresh launch ends no session, so it does not run the recorder either. The
  recorder first runs for real when a session ends in a graphical session: by
  `DELETE /mcp` (the panel sends none), when a later handshake's sweep removes a session
  (idle more than 30 minutes, or the least recently active of more than 100), or at a
  disconnect from the fallback WebSocket server.
- The release gate's runs on this commit (see Gates).

## Review

- **Session-end lane:** four independent read-only rounds.
  - `63af6a9b`: FAIL on wording, 2 FIX and 8 NITs. The comments left out that the removed
    preload also seeded the `claude/` files and reloaded the show config at every Connect,
    and they said session-end records are written under hython, where none is. Fixed in
    `cc454e51`.
  - `dfe7358a`, two lenses: FAIL, 6 FIX. Among them: with `SYNAPSE_AUTO_MEMORY=1` a
    disconnect still made the summary row's main-thread write from the connection thread
    (now disclosed); the docs claimed a WebSocket-disconnect record that only the fallback
    server writes; under hython the request thread re-imported `hdefereval` on every end;
    the "at most 30 s" wording left out the post's own lock wait. Fixed in round 3.
  - Round 3, an uncommitted snapshot, two lenses: FAIL, 3 FIX. The resource description still
    said "Auto-loaded on session start"; a swept session's cutoff was the sweep time, not its
    last request; a `memory.md` failure was logged as an unwritten record. Fixed in round 4.
  - Round 4, the content committed as `b5ababf6`, two lenses (correctness, claims): PASS,
    0 FIX, 12 NITs. One of them, the resource description that still offered reading the
    resource at session start, is fixed in this commit. The others, some reported by both
    lenses, are carried below.
- **Audit lane:** three rounds, two lenses each (design, correctness).
  - `1c0f7e53`: FAIL. The raw-id rule rejected models the registry labels by their own id,
    the switch checks failed when Nemotron or Ollama was already the active engine, and the
    readout rule forbade an elided label that the shipped design allows. The owner ruled:
    a wider raw-id rule, and the readout may elide, with the accessible name as the identity
    check.
  - `d404ab49`: FAIL. Two comments cited rulings for words those rulings do not contain; the
    elision rule accepted a label cut at any width; long Ollama tags failed the 40-character
    cap with pinned settings, after which the owner limited the cap to the registry's own
    names, defaults and unknown providers; the scratch run accepted an uncurated pair; the
    faces test left a freeze-detection timer armed.
  - `155bc008`: PASS on both lenses, NITs only.
- **NITs carried, not fixed in this release.**
  - Session-end lane:
    - `_schedule_swept_ends`' docstring does not say that an end queued during a sweep's read
      joins that batch, whose latest end becomes the cutoff;
    - the recorder's class docstring sizes the File > Open window without the swept case,
      where for an expired session it lasts more than the session TTL;
    - a WebSocket end is stamped after `end_session` returns, up to 10 s later with
      `SYNAPSE_AUTO_MEMORY` on;
    - no test pins that the real `SynapseMemory.add` runs through `run_on_main`;
    - `agent.usd` writers take no lock (the race predates the lane);
    - the leaked-recorder check in `tests/conftest.py` ignores the return value of `stop()`;
    - one end-cutoff test cannot tell an end cutoff from a write-time cutoff (others can);
    - the comment in `_handle_resources_read` (`python/synapse/mcp/server.py`) still says
      every handler a resource reaches marshals its own `hou` work, which project setup does
      not;
    - comments in `python/synapse/server/handlers.py`, `docs/RFC_agent_usd_ledger.md` and
      `tests/test_autonomy_task_provenance.py` say a record suspends only tasks "created by
      the latest session end its record names", which reads as ownership; the cutoff is by
      time and covers every client's earlier tasks;
    - `docs/studio/DEPLOYMENT.md` says each session the sweep removes "gets a record", where
      the ends one sweep queues share one session_history entry, and that a record suspends
      the scene's "pending agent tasks", where it suspends pending and executing ones
      (`suspend_all_tasks` in `python/synapse/memory/agent_state.py`).
  - Audit lane:
    - when a reading raises after the audit switched the model, only the engine is
      restored, so a pinned settings file can keep the audit's model pick;
    - pinned runs rewrite `model_by_provider` with every engine's current pick (the panel
      does the same on any engine switch);
    - `_elide_px` reads a tokens module bound before the panel's re-import (the values match
      today);
    - one comment says a 50-character label elides, where it shows whole at the default
      width;
    - the negative control has no variant that fails only the model, return, rows or missing
      clause;
    - comments in `synapse_panel.py` and the registry's `_pretty_ollama` docstring still state the old
      never-elide and short-label rules.
  - v5.104.1's crux record accepted two wording NITs in v5.104.1's text. They stay accepted,
    and that text is not edited.
- **Release text:** read-only review rounds on an archive copy of the tree plus this text.
  The text is committed only after a round finds no FIX.
  - Round 1, three lenses (notes, surfaces, mechanics): FAIL on each, 15 FIX findings
    naming 9 distinct faults. Among them: the release commit was said to touch nothing under
    `installer/`, though it edits `installer/README.md`; 9 passing controls were counted as
    planted faults; the first Connect read as the end-to-end check of the session-end
    recorder, which it does not run; a pre-existing `houdini_hda_promote_parm` defect was
    missing from the notes' Limits; `TAGS.md` still names v5.103.0. All but the last are
    fixed in this text. For `TAGS.md`, see Gates.
  - Round 2, the same three lenses: notes PASS, surfaces FAIL with 2 FIX, mechanics PASS. The
    two: `TAGS.md` again, with no step of the release card that updates it; and this record's
    Gates rows, which at this commit would have read as a failed text review and an open
    question. Card step 23 now adds the `TAGS.md` commit after publish, and the Gates rows
    state what holds at this commit.
  - Round 3, the same three lenses: notes PASS, surfaces FAIL with 1 FIX, mechanics PASS. The
    FIX: `docs/architecture/overview.md` still said the tag gate must run with `HEAD` equal to
    the commit Setup was built from. In the card's order the tag goes on the later commit that
    adds the crux record, so that clause is cut.
  - Round 4, the same three lenses: notes FAIL with 1 FIX, surfaces PASS, mechanics PASS. The
    FIX: the notes said the release gate's runs on the release commit happen "while nothing else
    runs". No runner checks that nothing else runs (the stock runner checks only for a
    Houdini-class process, once, before it starts), so the clause is cut.

## Gates

| Gate | State at this commit |
|---|---|
| Lane reviews | session-end lane round 4: PASS, 0 FIX, 12 NIT; audit lane round 3: PASS, NITs only |
| Merge check, stock suite on `724d766d` | 0 failed (13,515 passed) |
| Release-text review | rounds on an archive copy before this commit: round 1 FAIL, 15 FIX; round 2 FAIL, 2 FIX; round 3 FAIL, 1 FIX; round 4 FAIL, 1 FIX (see Review). The text is committed only after a round finds no FIX; the G2 packet, kept outside the repository, names that round |
| `TAGS.md` | not in this commit: it still names v5.103.0 as the current release and has no 5.104.x row. Card step 23 updates it in its own commit after publish, adding rows for v5.104.0, v5.104.1 and v5.104.2, with its own Gate C push |
| Current-release lines of `INSTRUCTIONS.md`, `docs/index.md` and `docs/studio/UPGRADE.md` | not in this commit: each still names 5.99.0 as the current release. The card's surfaces list names them from this commit on |
| Stock suite on this commit | not yet: after this commit |
| Seat suite on this commit (hython 22.0.400) | not yet: after this commit, compared by failing test with 5.104.1's run |
| Installer unit tests on this commit | not yet: after this commit |
| Setup build and qualification (card 15-17) | not yet: from this commit, after it |
| Tip review of the committed text (card 18) | not yet: after those runs, the same -0500 day as this commit |
| Crux record `harness/notes/release-5.104.2/CRUX-RECORD.json` (card 19) | not yet: after the tip review; `scripts/tag_release.py` reads it |
| `scripts/tag_release.py --check-only` (card 20) | not yet: after the crux record commit |
| Push (Gate C), CI on the exact SHA | not yet |
| Tag, publish | not yet |
| Seat install, then the first Connect as the end-to-end check of the handshake (not of the session-end recorder; see Not checked) | owner act, after publish |
