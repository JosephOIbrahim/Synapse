# Release record — v5.104.0

**Prepared 2026-11-21. This record describes the state at the commit that carries
it, before the push, the tag and the release page exist.** The Gates table is
authoritative for that snapshot and for nothing later: once a tag and a page exist,
the CI, Tag and Publish rows below are superseded, and the tag is the authority.

## Candidate

- Base: the `v5.103.0` tag, `353395df`.
- `origin/master` at preparation: `5bbbdda5` (the README redesign, pushed through
  Gate C on 2026-11-21; read with `git ls-remote origin refs/heads/master`). The
  release branch merged it as `8af7b0e0`, so pushing this branch to master is a
  fast-forward.
- Content, in order:
  - four documentation commits after the tag (`51acb57d`, `9c3dd7c8`, `e4bae0ce`,
    `4aab502a`);
  - Waves 0 and 1 of the 2026-11-20 repair program, already on master
    (`9a860b63` through `a5a4fe18`);
  - the README redesign (`5bbbdda5`);
  - R-035, the hands-off render under Houdini's asyncio (`37399dcb`, `9454acef`, and
    the `create_task` guard in `61c27b26`);
  - R-012's undo scope, rebuilt across the review rounds (`da6b953f`, `43ffbce8`,
    `e2dbd6e5`, `e6c90030`, `0738419a`, `61c27b26`, `1191fe48`);
  - one test cleanup (`48ef8c9e`);
  - the release commit: VERSION, version propagation, the release text and this file.
- Read the exact list with `git log --oneline 353395df..HEAD`; a count written here
  would change with the commit that writes it.

## Evidence

**Stock suite**, `run-stock-release.sh` (the `run-stock-tree.sh` fence; the tree's
release edits are checked by a manifest before and after), Python 3.14.2, `tests/`,
`-m "not live"`, run `r3` on `1191fe48` with the release edits:

```
STOCK_START HEAD=1191fe48… AT=2026-11-22T00:23:00Z PY=Python 3.14.2 EDITS=15
STOCK_DONE  HEAD_BEFORE=1191fe48… HEAD_AFTER=1191fe48… EXIT=0 TREE_MANIFEST=unchanged
= 13418 passed, 732 skipped, 11 deselected, 10 xfailed in 513.27s (0:08:33) =
```

Against v5.103.0 (13,057 passed, 0 failed, 727 skipped on `f1a03901`): +361 passed,
0 failed, +5 skipped. The five are new Wave 1 tests that need a module this Python
lacks: four OpenImageIO cases in `tests/test_cv_reader_parity.py` and one Moneta case
in `tests/test_moneta_crucible.py`. The per-file skip diff is the only difference.

**Seat suite**, `run-seat-leg.ps1`, hython 22.0.400 (Python 3.13.10), the same tree
and edits, run `r3`, EXIT=1 as always, TREE_MANIFEST unchanged: 92 failed, 4 errors,
13,562 passed, 512 skipped. Compared by failing test (`compare_seat.py`):

| Reference | Failing | Shared | Here only | Gone |
|---|---|---|---|---|
| v5.103.0 `353395df`, same machine, same night | 97 | 96 | 0 | 1 |
| v5.100.0 published baseline | 120 | 93 | 3 (all failing on v5.103.0) | 27 |

An earlier seat run of this release (on `da6b953f`) had four more failures. Three were
`tests/test_m3_logs_doctor.py` reading a server `tests/test_hwebserver_integration.py`
left running; fixed in `48ef8c9e`, and the two files together then fail the same three
tests as v5.103.0. The fourth, `tests/panel/test_welcome_motion.py`, passes alone (10 of
10) and did not fail in run `r3`.

**Live, Houdini 22.0.400 GUI**, three dedicated sessions on the release tree, each
launched by this session with an isolated preference folder and stopped by it. The
last, on `1191fe48` (process 54956), is the one the release notes report: loopback-only
bind with the LAN address refused; the hands-off render (task id in 0.107 s, joined,
`async`, `max_iterations`); Undo from a worker thread over an artist edit refused; Undo
and Redo through the panel bridge, and the agent's Redo refused after Houdini's own
Undo. The second session (on `48ef8c9e`) found that the panel route could not undo its
own first step, fixed in `0738419a`. Results: `live/final_result{,2,3}.json` and
`live/bind_check_final{,2,3}.json` in the release workspace.

**Changed tests and controls.** Each fix landed with tests that fail on the commit
before it (red controls on `git archive` copies), and the history-match condition was
mutation-checked (removing it fails two tests). Installer unit tests and the two key
mutations (card step 10) ran on the release worktree before the review rounds; the
installer code has not changed since.

After the suites only the release text changed: `README.md`,
`docs/releases/v5.104.0.md` and this file. The doc-reading tests ran on the final text.

## Review

Five refinement rounds, then one verification round, each an independent read-only
code reviewer and an independent read-only release-text checker. The code reviews
covered today's code, `a5a4fe18..1191fe48`; the text checks covered every release-text
change against v5.103.0. Waves 0 and 1 (`v5.103.0..a5a4fe18`) were verified node by
node in the repair program, each node by an independent verifier with a fail-before
control (`WAVE0_RECEIPTS_2026-11-20.md`, `WAVE1_RECEIPTS_2026-11-21.md` in the repair
workspace).

| Round | Code | Text |
|---|---|---|
| 1 | undo route bugs: the baseline read `hou` off the main thread, judge and step in separate calls | 4 FALSE, 23 OVERSTATED |
| 2 | round 1's combined count could undo an older same-label step; 4 red tests | OVERSTATED wording, fixed |
| 3 | artist panel actions counted as agent steps; redo of steps not undone here | 6 OVERSTATED |
| 4 | per-label redo let the agent redo an artist's undo; the Spatial click; R-035 guard point | 1 FALSE ("render through TOPS"), 5 OVERSTATED |
| 5 | a new same-label action passed the redo snapshot; cancel/halt clicks; no-move steps; poll latency | 4 OVERSTATED |
| 6 (verify) | nothing material; one narrow render-worker case documented | 5 OVERSTATED |

Every finding was fixed, except two, which are stated in the notes' Limits: the
artist's Ctrl+Y then Ctrl+Z on a step the agent undid, and the off-main render worker
whose `SYNAPSE: render` step lands after an agent Undo. Both restore the same labels,
which Houdini's history cannot tell apart. Deferred to repair Wave 2: bracketing that
render worker's dispatch, an `autonomous_render` poll case in the poll test, and
building the cancel/halt label in its test through the bridge's own summary code.

## Gates

| Gate | State |
|---|---|
| Stock suite on the release tree | PASS — 13,418 / 0 / 732 on `1191fe48` + edits, EXIT=0, manifest unchanged |
| Seat comparison | 0 new against v5.103.0; 27 gone against the v5.100.0 baseline |
| Version propagation | PASS — `sync_version.py --check`, `canonical=5.104.0 verdict=PASS` |
| Independent review | Six rounds; the last found nothing material in the code (Review above) |
| Crux record | Written after this commit, with this commit as its tip |
| CI, at this commit | NOT RUN — the push has not happened |
| Tag, at this commit | NOT RUN |
| Publish, at this commit | NOT RUN |
| Live seat install | Not part of this release act (card step 20) |
