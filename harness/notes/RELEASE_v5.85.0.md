# Release preparation: v5.85.0

Publish BP11, Identify plus production hardening, from local master
`ac26d127` on top of v5.84.2. Identify writes a short note under each
selected node from exact local sources, with no model call. BP11 also adds
Windows CI jobs and a ratchet on silent broad `except` handlers.

## What merged, and on what evidence

| Leg | What it did | Verdict before merge |
|---|---|---|
| BP11-IDCORE, IDSURF, SALIENCE | Identify core, panel button, `/identify`, Inspector column, LOP writes line, inactive JEV salience lane | BP11-CRUX: SOUND-WITH-NITS x3 |
| BP11-FIXFWD2 | NOTICE hashes from git blobs; ADR-0001 refusals (supersedes FIXFWD, which never merges) | BP11-CRUX: SOUND-WITH-NITS |
| BP11-HARDEN | Windows CI, broad-except ratchet | BP11-CRUX: BROKEN; lands only as fixed forward by HARDFIX (ruling R-A) |
| BP11-HARDFIX, IDFIX | HARDEN repair; save hooks armed on show, capped and memoized lookups, BOM-safe summaries | BP11-CRUX2: SOUND-WITH-NITS (16 mutations, 14 caught) |
| BP11-IDFIX2 | Summaries skip markup-only help paragraphs wherever they sit | Seat verification on Joe's word (17:12): fresh clone, corpus sweep, live G2 |

The release commit itself carries the six version surfaces, this record, the public
notes and CHANGELOG entry, and the README, status, architecture and SideFX library
pages with new Identify diagrams. Joe asked for the README to stay ADHD-friendly and
for the tags line and diagrams to be refreshed.

Referee records: `harness/battleplan/notes/BP11-CRUX_verdicts.md`,
`harness/battleplan/notes/BP11-CRUX2_verdicts.md` and their mutation files.
Leg receipts: `harness/notes/receipts/BP11-*.json`.

## Live gates, Houdini 22.0.400

Gates ran in Houdini 22.0.400 through the SYNAPSE panel, driven by computer use.
G1 (button placement), G3 (one undo step; artist comment kept) and G4 (LOP writes
line) passed at 16:26-16:40 on the pre-repair merge 9e7feb34; later commits did not
change those paths beyond arming the save hooks. G2, G5 and G6 were re-run at 17:44
on c76b7759, after Joe restarted Houdini, with the loaded code checked first.

| Gate | Result on c76b7759 | Producer |
|---|---|---|
| G2 | 7 of 7 notes; PolyExtrude reads "Extrudes polygonal faces and edges."; artist note above the sentinel | `.token-saver/bp11/gates/out_g2_v2.txt` |
| G5 | 200 selected, 60 notes, flash "Identify: 60 of 200 nodes". Cold memo 1,160 ms click-to-note, longest main-thread gap 79.7 ms (idle 55.1). Warm 53 ms, 68.2 ms (idle 55.9). About 40 s before IDFIX | `out_g5_cold_v2.txt`, `out_g5_v2.txt` |
| G6 | Saved with 67 notes: hython reload finds 0 nodes with the sentinel, 0 raw bytes, artist comment on disk; 67 restored in session. A real Ctrl+S to `.hiplc` gives the same | `gate_g6_check.py` output, `out_after_freeze.txt` |

The first scripted save from the untitled scene froze the GUI for about 7 minutes
20 seconds. py-spy placed it in `memory_lifecycle._handle_event` (AfterSave):
`_copy_records` adds 1,458 untitled-root records one at a time and each add writes
a full Moneta snapshot. The code predates BP11 and ships in v5.84.2; the release
notes disclose it and it leads the BP12 list.

## Checks on the release candidate

- IDFIX2 seat verification, fresh clone of ca7bc8cb: 93 passed and 1 skipped on
  Python 3.14 and on the 3.11 CI environment; ratchet OK; disabling the markup
  skip fails 2 tests. Producer: `.token-saver/bp11/verify_idfix2.out`.
- Full-corpus sweep over 4,606 node help pages (`.token-saver/bp11/corpus_sweep.py`,
  row choice checked against the real `help_summary` for 7 of 7 keys): markup-led
  summaries 93 before IDFIX2, 37 after (12 on index or non-node pages); 4,555 clean
  prose. Producer: `sweep_master.json`, `sweep_idfix2.json`.
- Local Windows CI dry run on c76b7759 (CI env; keys, Houdini and SYNAPSE variables
  dropped): Python 3.14 green, 9,875 passed; Python 3.11 had 1 failure,
  `test_session_lifecycle`, a 10 ms sleep against the 15.6 ms monotonic tick. It
  failed 4 of 25 isolated runs; ac26d127 waits on the clock instead, 0 of 25.
  Producer: `.token-saver/bp11/ci_dry/`.
- Local Windows CI dry run on ac26d127, the release code (docs and version surfaces aside):
  Python 3.11 9,874 passed, 0 failed (7 xfailed, 1 xpassed); Python 3.14 9,875 passed,
  0 failed (5 xfailed); JEV harness 77 passed and production-memory environment 14 passed
  on both. Producer: `.token-saver/bp11/ci_dry/<python>/ac26d127_summary.json`.
- `harness/verify/checks.py --task R.R --mode B` on ac26d127 with system Python 3.14 (PyYAML
  added so the suite can collect `tests/test_agent_roster.py`): FAIL on the three standing
  release blockers, `mutation_fail_closed`, `installer_host_targeted` and
  `ci_covers_shipping_surface`. Its suite_baseline guardrail counted 10,191 passed and 2
  failed. Both failures are `tests/test_scout.py` cases that merge this machine's configured
  SideFX library into their results; the same file passes 37 of 37 in a clean clone. That
  test-isolation gap predates BP11 and is queued for BP12. Producer:
  `.token-saver/bp11/rr_before_py314b.out`, `suite_main_py314.out`.
- Release-surface tests on the candidate tree: `sync_version.py --check` PASS at 5.85.0 on all six
  surfaces; toolcount, version-conformance, public-agreement and product-surface tests
  60 passed; `harness/verify/version_agreement.py` public checks ok.

## What the CTO got wrong

The seat pinned BP11-HARDEN to Haiku. JEV's router had sent it to Opus at 0.84.
HARDEN settled green with a broken tip: `salience.py` would not import, three
Identify behaviors changed, and its ratchet counted unparsable files as zero.
The repair took HARDFIX (7.25M weighted) and CRUX2 (5.06M weighted).

Two more misses came from checking the wrong shape. IDCORE's save round trip
passed because its probe installed the save hooks itself; the panel never did,
and live gate G6 caught it. IDFIX's summary fix was tested on a synthetic page
that starts with a BOM; real pages put the directive after the title. The seat
caught that while drawing the bubble mockup, and the full-corpus sweep is now
the proof for this path.

## Budget

60,000,000 weighted-token cap. Legs settled at 56,242,429 across five
orchestrator runs; run restarts followed a desktop-app restart (15:12) and a
dependency bug that dispatched CRUX2 early (16:40).

## Publication steps

The clean-tree tag gate creates the local annotated tag. Push master, require
all six CI jobs (Ubuntu, macOS and Windows with Python 3.11 and 3.14) on the
exact release commit, then push the tag and publish. Finally verify GitHub
master, the peeled tag and local master match; v5.84.2's tag must be unchanged.

This preparation record does not claim that the later CI, push or publication
steps have already completed. Their receipts belong to the GitHub release.
